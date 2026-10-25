"""Tracks esenciales de un artista (perfil, «Más allá de la cabina»): 3–4 canciones propias con enlace a su TrackDNA.

- Criterio: las más escuchadas del artista en Deezer (`/artist/{id}/top`, uso no comercial), con la ficha de Deezer
  verificada por identificadores (deezer.resolve). Es popularidad en una plataforma, no un juicio de calidad: la app
  lo dice así.
- Solo canciones del propio artista (artista principal en Deezer); los remixes que otros hacen de sus temas y las
  versiones repetidas de una misma canción (edit, dub, extended…) se quedan fuera si está la original.
- Enlace: el MBID de la grabación si MusicBrainz tiene ese ISRC acreditado al artista y con la misma duración (±3 %),
  para abrir el TrackDNA completo; si no, la ficha `deezer:<id>` del catálogo de reserva.
- Caché propia de 7 días (los fallos temporales no se guardan). Se pide aparte del perfil, como las historias.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any

from app import deezer, schemas, store
from app.musicbrainz import MB_BASE_URL, MusicBrainzClient, ProviderError

KIND = "essentials"
VERSION = 2  # v2: criterio en una línea
TTL_S = 7 * 24 * 3600
EMPTY_TTL_S = 24 * 3600
LIMIT = 4
TOP_FETCH = 15
LENGTH_TOLERANCE = 0.03
REMIX_RE = re.compile(r"\bremix\b|\brework\b|\bre-?edit\b", re.IGNORECASE)
BASIS = "Las más escuchadas en Deezer · solo temas propios"


def _core(title: str) -> str:
    return deezer.fold(re.sub(r"\s*[(\[].*?[)\]]\s*|\s+-\s+.*$", " ", title or ""))


def pick(top: list[dict[str, Any]], deezer_id: str, limit: int = LIMIT) -> list[dict[str, Any]]:
    """Canciones propias del ranking, en su orden, una por título: la original antes que sus versiones."""
    own = [t for t in top if isinstance(t, dict) and t.get("id") and str((t.get("artist") or {}).get("id")) == deezer_id
           and str(t.get("title") or "").strip()]
    chosen: dict[str, dict[str, Any]] = {}
    for t in own:
        if REMIX_RE.search(str(t.get("title_version") or t.get("title") or "")):
            continue  # remix de un tema suyo (otro artista lo firma como versión): no es «su» canción
        key = _core(t.get("title_short") or t["title"])
        if key and key not in chosen:
            chosen[key] = t
        elif key and not str(t.get("title_version") or "").strip() and str(chosen[key].get("title_version") or "").strip():
            chosen[key] = t  # la original sustituye a un edit que aparecía antes
    order = [t for t in own if t in chosen.values()]
    return order[:limit]


def recording_for(client: MusicBrainzClient, isrc: str, artist_mbid: str, length_ms: int | None) -> dict[str, Any] | None:
    """Grabación de MusicBrainz con ese ISRC, acreditada al artista y con la misma duración. None ante la duda."""
    try:
        data = client.get(f"{MB_BASE_URL}/isrc/{isrc}", {"inc": "artist-credits", "fmt": "json"}).data
    except ProviderError:
        return None
    for rec in data.get("recordings") or []:
        ids = {(c.get("artist") or {}).get("id") for c in rec.get("artist-credit") or [] if isinstance(c, dict)}
        length = rec.get("length")
        same = bool(length_ms and isinstance(length, int) and abs(length - length_ms) <= length_ms * LENGTH_TOLERANCE)
        if artist_mbid in ids and same and isinstance(rec.get("id"), str):
            return rec
    return None


def build(artist_mbid: str, record: dict[str, Any] | None, client: MusicBrainzClient,
          transport: deezer.Transport | None = None) -> schemas.EssentialsResponse:
    """Lanza deezer.Unavailable ante un fallo temporal de Deezer (no se guarda nada)."""
    if not record:
        return schemas.EssentialsResponse(artist_mbid=artist_mbid, status="unavailable")
    get = transport or deezer._default_transport
    top = (deezer._get(f"artist/{record['id']}/top", {"limit": str(TOP_FETCH)}, get) or {}).get("data") or []
    tracks = []
    for t in pick(top, str(record["id"])):
        full = deezer._get(f"track/{t['id']}", None, get) or {}
        length_ms = int(t["duration"]) * 1000 if isinstance(t.get("duration"), int) and t["duration"] > 0 else None
        isrc = full.get("isrc") if isinstance(full.get("isrc"), str) else None
        rec = recording_for(client, isrc, artist_mbid, length_ms) if isrc else None
        album = t.get("album") or {}
        date = (rec or {}).get("first-release-date") or full.get("release_date") or ""
        tracks.append(schemas.EssentialTrack(
            id=rec["id"] if rec else deezer.ext_id(t["id"]), catalog="musicbrainz" if rec else "deezer",
            title=str(t["title"]).strip(), artist_name=str((t.get("artist") or {}).get("name") or ""),
            length_ms=length_ms, year=str(date)[:4] or None, cover_url=deezer._https(album.get("cover_xl")),
            release_title=album.get("title"), deezer_url=deezer.track_url({"id": t["id"], "link": t.get("link")})))
    sources = [schemas.SourceRef(label="Deezer (popularidad)", url=f"https://www.deezer.com/artist/{record['id']}",
                                 license=deezer.LICENSE)]
    if any(t.catalog == "musicbrainz" for t in tracks):
        sources.append(schemas.SourceRef(label="MusicBrainz (ISRC)", url=f"https://musicbrainz.org/artist/{artist_mbid}",
                                         license="CC0"))
    return schemas.EssentialsResponse(artist_mbid=artist_mbid, status="ready" if tracks else "unavailable",
                                      tracks=tracks, basis=BASIS if tracks else None, sources=sources if tracks else [])


def cached_or_build(artist_mbid: str, resolve: Callable[[], dict[str, Any] | None], client: MusicBrainzClient,
                    transport: deezer.Transport | None = None) -> schemas.EssentialsResponse:
    hit = store.get(KIND, artist_mbid)
    if hit is not None and hit.get("version") == VERSION:
        try:
            return schemas.EssentialsResponse.model_validate(hit["response"])
        except ValueError:
            pass
    response = build(artist_mbid, resolve(), client, transport)
    store.put(KIND, artist_mbid, {"version": VERSION, "response": response.model_dump()},
              TTL_S if response.tracks else EMPTY_TTL_S)
    return response
