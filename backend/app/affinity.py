"""Canciones afines a una grabación (Inicio, «Tu frecuencia»): temas propios de artistas relacionados en Deezer.

- Criterio: los artistas que Deezer relaciona con el de la canción (`/artist/{id}/related`, uso no comercial) y, de
  cada uno, su tema propio más escuchado (mismas reglas que essentials.pick: sin remixes de otros, la original antes
  que sus edits). Es afinidad de escucha en una plataforma, no un juicio musical: la app lo dice así.
- Partida: la grabación verificada en Deezer (deezer.track_match: ISRC y duración) y su artista; si Deezer no la
  tiene por ISRC, la ficha de Deezer del artista principal (deezer.resolve, la misma del perfil). Nunca se propone
  una canción con el mismo título base que la de partida (sus remixes o versiones firmados por otro artista).
- Enlace: el MBID de la grabación si MusicBrainz tiene ese ISRC con el mismo nombre de artista y la misma duración
  (±3 %), para abrir el TrackDNA completo y poder guardarla; si no, la ficha `deezer:<id>`.
- Caché propia de 7 días (los fallos temporales no se guardan).
"""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any

from app import deezer, essentials, schemas, store
from app.musicbrainz import MB_BASE_URL, MusicBrainzClient, ProviderError

KIND = "affinity"
VERSION = 3  # v2: reserva desde la ficha del artista · v3: sin dubs ni edits
TTL_S = 7 * 24 * 3600
EMPTY_TTL_S = 24 * 3600
LIMIT = 4
RELATED_FETCH = 8
TOP_FETCH = 8
BASIS = "Artistas afines en Deezer · su tema más escuchado"
# Más estricto que en los esenciales: en una recomendación tampoco entran dubs, edits ni versiones VIP de nadie.
VERSION_RE = re.compile(r"\b(remix|rmx|rework|re-?edit|edit|dub|bootleg|vip|mashup)\b", re.IGNORECASE)


def recording_for(client: MusicBrainzClient, isrc: str, artist_name: str, length_ms: int | None) -> dict[str, Any] | None:
    """Grabación de MusicBrainz con ese ISRC, del mismo artista (por nombre) y con la misma duración. None ante la duda."""
    try:
        data = client.get(f"{MB_BASE_URL}/isrc/{isrc}", {"inc": "artist-credits", "fmt": "json"}).data
    except ProviderError:
        return None
    for rec in data.get("recordings") or []:
        names = {deezer.fold((c.get("artist") or {}).get("name")) for c in rec.get("artist-credit") or [] if isinstance(c, dict)}
        length = rec.get("length")
        same = bool(length_ms and isinstance(length, int) and abs(length - length_ms) <= length_ms * essentials.LENGTH_TOLERANCE)
        if deezer.fold(artist_name) in names and same and isinstance(rec.get("id"), str):
            return rec
    return None


def seed_from_track(match: dict[str, Any] | None, transport: deezer.Transport | None = None) -> dict[str, Any] | None:
    """Artista y título de partida a partir de la grabación verificada en Deezer. None si no hay."""
    if not match:
        return None
    found = deezer._get(f"track/{match['id']}", None, transport or deezer._default_transport) or {}
    artist = found.get("artist") or {}
    if not artist.get("id"):
        return None
    return {"artist_id": str(artist["id"]), "artist_name": artist.get("name"),
            "title": found.get("title_short") or found.get("title") or ""}


def seed_from_artist(record: dict[str, Any] | None, name: str | None, title: str) -> dict[str, Any] | None:
    """Partida desde la ficha de Deezer del artista (deezer.resolve) cuando la grabación no está por ISRC."""
    return {"artist_id": str(record["id"]), "artist_name": name, "title": title} if record and record.get("id") else None


def build(recording_mbid: str, seed: dict[str, Any] | None, client: MusicBrainzClient,
          transport: deezer.Transport | None = None) -> schemas.AffinityResponse:
    """`seed`: {artist_id, artist_name, title} (seed_from_track / seed_from_artist). Lanza deezer.Unavailable ante un
    fallo temporal de Deezer (no se guarda nada)."""
    empty = schemas.AffinityResponse(recording_mbid=recording_mbid, status="unavailable")
    if not seed:
        return empty
    get = transport or deezer._default_transport
    seed_artist = {"id": seed["artist_id"], "name": seed.get("artist_name")}
    seed_core = essentials._core(seed.get("title") or "")
    related = (deezer._get(f"artist/{seed_artist['id']}/related", {"limit": str(RELATED_FETCH)}, get) or {}).get("data") or []
    tracks = []
    for artist in related[:RELATED_FETCH]:
        if len(tracks) >= LIMIT:
            break
        if not isinstance(artist, dict) or not artist.get("id") or str(artist["id"]) == str(seed_artist["id"]):
            continue
        top = (deezer._get(f"artist/{artist['id']}/top", {"limit": str(TOP_FETCH)}, get) or {}).get("data") or []
        own = [t for t in essentials.pick(top, str(artist["id"]), limit=5)
               if essentials._core(t.get("title_short") or t["title"]) != seed_core
               and not VERSION_RE.search(f"{t.get('title_version') or ''} {t['title']}")]
        if not own:
            continue
        t = own[0]
        full = deezer._get(f"track/{t['id']}", None, get) or {}
        length_ms = deezer._length_ms(t)
        name = str((t.get("artist") or {}).get("name") or "")
        isrc = full.get("isrc") if isinstance(full.get("isrc"), str) else None
        rec = recording_for(client, isrc, name, length_ms) if isrc else None
        album = t.get("album") or {}
        date = (rec or {}).get("first-release-date") or full.get("release_date") or ""
        tracks.append(schemas.EssentialTrack(
            id=rec["id"] if rec else deezer.ext_id(t["id"]), catalog="musicbrainz" if rec else "deezer",
            title=str(t["title"]).strip(), artist_name=name, length_ms=length_ms, year=str(date)[:4] or None,
            cover_url=deezer._https(album.get("cover_xl")), release_title=album.get("title"),
            deezer_url=deezer.track_url({"id": t["id"], "link": t.get("link")})))
    if not tracks:
        return empty
    return schemas.AffinityResponse(recording_mbid=recording_mbid, status="ready", seed_artist=seed_artist.get("name"),
                                    tracks=tracks, basis=BASIS)


def cached_or_build(recording_mbid: str, seed: Callable[[], dict[str, Any] | None], client: MusicBrainzClient,
                    transport: deezer.Transport | None = None) -> schemas.AffinityResponse:
    hit = store.get(KIND, recording_mbid)
    if hit is not None and hit.get("version") == VERSION:
        try:
            return schemas.AffinityResponse.model_validate(hit["response"])
        except ValueError:
            pass
    response = build(recording_mbid, seed(), client, transport)
    store.put(KIND, recording_mbid, {"version": VERSION, "response": response.model_dump()},
              TTL_S if response.tracks else EMPTY_TTL_S)
    return response
