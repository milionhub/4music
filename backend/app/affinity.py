"""Canciones afines a una grabación (Inicio, «Tu frecuencia»): temas propios de artistas relacionados en Deezer.

- Criterio: los artistas que Deezer relaciona con el de la canción (`/artist/{id}/related`, uso no comercial) y, de
  cada uno, su tema propio más escuchado (mismas reglas que essentials.pick: sin remixes de otros, la original antes
  que sus edits). Es afinidad de escucha en una plataforma, no un juicio musical: la app lo dice así.
- Partida: la grabación verificada en Deezer (deezer.track_match: ISRC y duración) y su artista; si Deezer no la
  tiene por ISRC, la ficha de Deezer del artista principal (deezer.resolve, la misma del perfil). Nunca se propone
  una canción con el mismo título base que la de partida (sus remixes o versiones firmados por otro artista).
- Enlace: el MBID de la grabación si MusicBrainz tiene ese ISRC con el mismo nombre de artista y la misma duración
  (±3 %), para abrir el TrackDNA completo y poder guardarla; si no, la ficha `deezer:<id>`.
- Artistas pequeños sin relacionados en Deezer: otros artistas del mismo sello que la canción de partida (búsqueda
  de Deezer por sello, confirmada con el sello de cada álbum; nunca recopilatorios ni autoediciones).
- Caché propia de 7 días (los fallos temporales no se guardan).
"""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any

from app import deezer, essentials, schemas, store
from app.musicbrainz import MB_BASE_URL, MusicBrainzClient, ProviderError

KIND = "affinity"
VERSION = 4  # v2: reserva desde la ficha del artista · v3: sin dubs ni edits · v4: reserva por sello
TTL_S = 7 * 24 * 3600
EMPTY_TTL_S = 24 * 3600
LIMIT = 4
RELATED_FETCH = 8
TOP_FETCH = 8
BASIS = "Artistas afines en Deezer · su tema más escuchado; si no hay, artistas de su mismo sello"
LABEL_SEARCH = 40
LABEL_CHECKS = 12  # álbumes que se abren como mucho para confirmar el sello
NO_LABEL_RE = re.compile(r"^(not on label|self[- ]released|independent)\b|^\[?no label\]?$", re.IGNORECASE)
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
    """Artista, título y sello de partida a partir de la grabación verificada en Deezer. None si no hay."""
    if not match:
        return None
    get = transport or deezer._default_transport
    found = deezer._get(f"track/{match['id']}", None, get) or {}
    artist = found.get("artist") or {}
    if not artist.get("id"):
        return None
    label = match.get("label") if match.get("own_release") else None
    album_id = (found.get("album") or {}).get("id")
    if not label and album_id:
        album = deezer._get(f"album/{album_id}", None, get) or {}
        own = album.get("record_type") != "compile" and str((album.get("artist") or {}).get("id")) == str(artist["id"])
        label = album.get("label") if own else None
    return {"artist_id": str(artist["id"]), "artist_name": artist.get("name"),
            "title": found.get("title_short") or found.get("title") or "", "label": _label(label)}


def seed_from_artist(record: dict[str, Any] | None, name: str | None, title: str,
                     label: str | None = None) -> dict[str, Any] | None:
    """Partida desde la ficha de Deezer del artista (deezer.resolve) cuando la grabación no está por ISRC; `label`, el
    sello de la grabación según su ficha (si consta)."""
    if not record or not record.get("id"):
        return None
    return {"artist_id": str(record["id"]), "artist_name": name, "title": title, "label": _label(label)}


def _label(name: Any) -> str | None:
    """Sello utilizable para buscar afines: nunca una autoedición ni un «sin sello»."""
    text = str(name or "").strip()
    return text if text and not NO_LABEL_RE.search(text) else None


def _usable(t: dict[str, Any], seed_core: str) -> bool:
    """Una canción propia que no es otra versión de la de partida ni un remix, dub o edit."""
    return (essentials._core(t.get("title_short") or t.get("title") or "") != seed_core
            and not VERSION_RE.search(f"{t.get('title_version') or ''} {t.get('title') or ''}"))


def _item(t: dict[str, Any], client: MusicBrainzClient, get: deezer.Transport) -> schemas.EssentialTrack:
    """La propuesta, con el MBID de MusicBrainz si tiene ese ISRC del mismo artista y duración; si no, `deezer:<id>`."""
    full = deezer._get(f"track/{t['id']}", None, get) or {}
    length_ms = deezer._length_ms(t)
    name = str((t.get("artist") or {}).get("name") or "")
    isrc = full.get("isrc") if isinstance(full.get("isrc"), str) else None
    rec = recording_for(client, isrc, name, length_ms) if isrc else None
    album = t.get("album") or {}
    date = (rec or {}).get("first-release-date") or full.get("release_date") or ""
    return schemas.EssentialTrack(
        id=rec["id"] if rec else deezer.ext_id(t["id"]), catalog="musicbrainz" if rec else "deezer",
        title=str(t["title"]).strip(), artist_name=name, length_ms=length_ms, year=str(date)[:4] or None,
        cover_url=deezer._https(album.get("cover_xl")), release_title=album.get("title"),
        deezer_url=deezer.track_url({"id": t["id"], "link": t.get("link")}))


def _by_label(label: str, skip_artists: set[str], seed_core: str, limit: int,
              get: deezer.Transport) -> list[dict[str, Any]]:
    """Temas de otros artistas en lanzamientos propios del mismo sello. La búsqueda de Deezer por sello mezcla títulos
    que solo contienen la palabra: cada candidato se confirma con el sello de su álbum."""
    found = (deezer._get("search", {"q": f'label:"{label}"', "limit": str(LABEL_SEARCH)}, get) or {}).get("data") or []
    out: list[dict[str, Any]] = []
    checked = 0
    for t in found:
        if len(out) >= limit or checked >= LABEL_CHECKS:
            break
        artist_id = str((t.get("artist") or {}).get("id") or "")
        album_id = (t.get("album") or {}).get("id")
        if not t.get("id") or not artist_id or artist_id in skip_artists or not album_id or not _usable(t, seed_core):
            continue
        checked += 1
        album = deezer._get(f"album/{album_id}", None, get) or {}
        own = album.get("record_type") != "compile" and str((album.get("artist") or {}).get("id")) == artist_id
        if own and deezer.fold(album.get("label")) == deezer.fold(label):
            out.append(t)
            skip_artists.add(artist_id)
    return out


def build(recording_mbid: str, seed: dict[str, Any] | None, client: MusicBrainzClient,
          transport: deezer.Transport | None = None) -> schemas.AffinityResponse:
    """`seed`: {artist_id, artist_name, title, label} (seed_from_track / seed_from_artist). Primero los artistas
    relacionados en Deezer; si no llegan a LIMIT (artistas pequeños: Deezer no relaciona a nadie), otros artistas del
    mismo sello. Lanza deezer.Unavailable ante un fallo temporal de Deezer (no se guarda nada)."""
    empty = schemas.AffinityResponse(recording_mbid=recording_mbid, status="unavailable")
    if not seed:
        return empty
    get = transport or deezer._default_transport
    seed_artist = {"id": seed["artist_id"], "name": seed.get("artist_name")}
    seed_core = essentials._core(seed.get("title") or "")
    related = (deezer._get(f"artist/{seed_artist['id']}/related", {"limit": str(RELATED_FETCH)}, get) or {}).get("data") or []
    picked: list[dict[str, Any]] = []
    skip = {str(seed_artist["id"])}
    for artist in related[:RELATED_FETCH]:
        if len(picked) >= LIMIT:
            break
        if not isinstance(artist, dict) or not artist.get("id") or str(artist["id"]) in skip:
            continue
        top = (deezer._get(f"artist/{artist['id']}/top", {"limit": str(TOP_FETCH)}, get) or {}).get("data") or []
        own = [t for t in essentials.pick(top, str(artist["id"]), limit=5) if _usable(t, seed_core)]
        if own:
            picked.append(own[0])
            skip.add(str(artist["id"]))
    by_related = len(picked)
    label = seed.get("label")
    if len(picked) < LIMIT and label:
        picked += _by_label(label, skip, seed_core, LIMIT - len(picked), get)
    if not picked:
        return empty
    return schemas.AffinityResponse(recording_mbid=recording_mbid, status="ready", seed_artist=seed_artist.get("name"),
                                    tracks=[_item(t, client, get) for t in picked], basis=BASIS,
                                    label=label if len(picked) > by_related else None, related_count=by_related)


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
