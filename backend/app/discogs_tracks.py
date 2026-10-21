"""Canciones fuera de MusicBrainz documentadas en Discogs (V5.6). MusicBrainz sigue siendo el catálogo principal:
esto solo entra cuando su búsqueda no encuentra nada, y cada canción tiene su propia ruta (/v1/tracks/ext/{id}).

Identidad: `discogs:<release>:<posición>`, una pista concreta de un lanzamiento concreto. Nunca un MBID inventado y
nunca una fusión por título o ISRC: dos ediciones solo se presentan como una si coinciden título, artistas (por ID de
Discogs) y duración (±3 %); un remix, un edit o una extended son siempre otra canción.

Condiciones de la API (docs/fase-1-generos-electronicos.md, «API Terms of Use», 2025-05-27; docs/v5-6-catalogo-externo.md):
- Títulos, tracklists, fechas, formatos, identificadores y créditos son CC0. Las imágenes son «Restricted Data»: no se
  usan (sin portada). Los estilos no son CC0: se muestran con atribución y como dato del lanzamiento.
- Nada se muestra con más de 6 horas de antigüedad y no se guarda más de lo necesario: caché de 6 h.
- «Data provided by Discogs» con enlace a la página de Discogs junto a los datos, y aviso de no afiliación (la app).
- Sin token: 25 peticiones/min. Pocas por búsqueda (1 + MAX_RELEASES) y con una pausa mínima entre ellas.
"""

from __future__ import annotations

import json
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any

from app import discogs, schemas, store, tracks
from app.musicbrainz import MusicBrainzClient, NotFound, ProviderError, Unavailable

KIND = "discogs_api"
TTL_S = 6 * 3600                  # máximo que permiten las condiciones de la API
BASE_URL = "https://api.discogs.com"
SITE = "https://www.discogs.com"
MB_URL_LOOKUP = "https://musicbrainz.org/ws/2/url"
TIMEOUT_S = 6
MIN_INTERVAL_S = 1.0              # ritmo sin token: 25/min; ráfagas cortas de una búsqueda
SEARCH_PER_PAGE = 10
MAX_RELEASES = 3                  # lanzamientos que se abren por búsqueda
MAX_LINKED_ARTISTS = 3
LENGTH_TOLERANCE = 0.03
USER_AGENT = "music-discovery/0.1 (TrackDNA; Discogs catalogue lookup)"
ATTRIBUTION = "Data provided by Discogs"
LICENSE = "Discogs API Terms of Use (tracklist CC0)"
ID_RE = re.compile(r"^discogs:(\d{1,10}):([A-Za-z0-9][A-Za-z0-9.\-]{0,9})$")
DURATION_RE = re.compile(r"^(?:(\d+):)?(\d{1,3}):(\d{2})$")
NOT_ON_LABEL_RE = re.compile(r"^not on label\b", re.IGNORECASE)
# Pistas que no son la canción en sí: sesiones mezcladas (fragmentos de DJ mix), igual que en la búsqueda de MusicBrainz.
MIXED_FORMATS = {"Mixed", "Partially Mixed"}
TYPE_BY_DESCRIPTION = {"Single": "Single", "EP": "EP", "Mini-Album": "EP", "LP": "Album", "Album": "Album"}

Transport = Callable[[str], dict[str, Any]]
_lock = threading.Lock()
_last_request = 0.0


def _default_transport(url: str) -> dict[str, Any]:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _get(path: str, transport: Transport | None = None) -> dict[str, Any] | None:
    """Respuesta de la API (caché de 6 h). None si no existe (404); Unavailable ante cualquier otro fallo, sin guardarlo."""
    global _last_request
    url = BASE_URL + path
    hit = store.get(KIND, url)
    if hit is not None:
        return hit.get("body")
    with _lock:  # una petición cada MIN_INTERVAL_S como mínimo, también entre peticiones simultáneas
        wait = _last_request + MIN_INTERVAL_S - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        _last_request = time.monotonic()
    try:
        body = (transport or _default_transport)(url)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise Unavailable(f"Discogs respondió {e.code}") from e
    except (OSError, ValueError) as e:
        raise Unavailable("Discogs no responde") from e
    if not isinstance(body, dict):
        raise Unavailable("Respuesta de Discogs con forma inesperada")
    store.put(KIND, url, {"body": body}, TTL_S)
    return body


# --- Lectura de un lanzamiento ------------------------------------------------------------------------------------
def track_id(release_id: int | str, position: str) -> str | None:
    tid = f"discogs:{release_id}:{position}"
    return tid if ID_RE.match(tid) else None


def parse_duration(text: Any) -> int | None:
    m = DURATION_RE.match(text.strip()) if isinstance(text, str) else None
    if not m:
        return None
    ms = ((int(m.group(1) or 0) * 60 + int(m.group(2))) * 60 + int(m.group(3))) * 1000
    return ms or None


def release_date(release: dict[str, Any]) -> str | None:
    """«2022-11-18», «2022-11» o «2022» (Discogs rellena con «-00» lo que no sabe)."""
    raw = tracks._str(release.get("released")) or (str(release["year"]) if release.get("year") else None)
    if not raw:
        return None
    parts = [p for p in raw.split("-") if p.strip("0")]
    return "-".join(parts) or None


def _join(join: str) -> str:
    j = (join or "").strip()
    if not j:
        return ""
    if j == ",":
        return ", "
    return f" {'feat.' if j.lower() in {'feat.', 'feat', 'ft.', 'featuring'} else j} "


def credit(artists: list[dict[str, Any]]) -> tuple[list[schemas.CreditedArtist], str, list[str]]:
    """(créditos, texto del crédito, IDs de Discogs). Los IDs van con espacio de nombres: no son MBID."""
    out, ids = [], []
    valid = [a for a in artists if isinstance(a, dict) and a.get("id") and tracks._str(a.get("name"))]
    for i, a in enumerate(valid):
        name = discogs.clean_name(tracks._str(a.get("anv")) or a["name"].strip())
        out.append(schemas.CreditedArtist(mbid=f"discogs:artist:{a['id']}", name=name,
                                          join_phrase=_join(a.get("join", "")) if i < len(valid) - 1 else ""))
        ids.append(str(a["id"]))
    return out, "".join(c.name + c.join_phrase for c in out), ids


def _descriptions(release: dict[str, Any]) -> list[str]:
    return [d for f in release.get("formats") or [] if isinstance(f, dict) for d in f.get("descriptions") or [] if isinstance(d, str)]


def mixed(release: dict[str, Any]) -> bool:
    return bool(MIXED_FORMATS & set(_descriptions(release)))


def _formats(release: dict[str, Any]) -> list[str]:
    out = []
    for f in release.get("formats") or []:
        name = tracks._str((f or {}).get("name"))
        if not name:
            continue
        sizes = [d for d in f.get("descriptions") or [] if isinstance(d, str) and d.endswith('"')]
        label = "Digital Media" if name == "File" else f"{sizes[0]} {name}" if sizes else name
        if label not in out:
            out.append(label)
    return out


def release_summary(release: dict[str, Any]) -> schemas.TrackRelease:
    desc = _descriptions(release)
    labels, catno, self_released = [], None, False
    for lab in release.get("labels") or []:
        name = tracks._str((lab or {}).get("name"))
        if not name:
            continue
        if NOT_ON_LABEL_RE.match(name):
            self_released = True
            continue
        clean = discogs.clean_name(name)
        if clean not in labels:
            labels.append(clean)
        cat = tracks._str(lab.get("catno"))
        if catno is None and cat and cat.lower() != "none":
            catno = cat
    primary = next((TYPE_BY_DESCRIPTION[d] for d in desc if d in TYPE_BY_DESCRIPTION), None)
    secondary = ["Compilation"] if "Compilation" in desc else []
    secondary += ["DJ-mix"] if mixed(release) else []
    return schemas.TrackRelease(
        mbid=f"discogs:release:{release['id']}", title=tracks._str(release.get("title")) or "", primary_type=primary,
        secondary_types=secondary, date=release_date(release), labels=labels, catalog_number=catno,
        formats=_formats(release), own=not secondary, self_released=self_released and not labels,
        url=_page(release))


def _page(release: dict[str, Any]) -> str:
    uri = tracks._str(release.get("uri"))
    return uri if uri and uri.startswith(SITE) else f"{SITE}/release/{release['id']}"


def release_tracks(release: dict[str, Any]) -> list[dict[str, Any]]:
    """Pistas de un lanzamiento con identidad propia. Nada de las sesiones mezcladas (fragmentos de DJ mix)."""
    if mixed(release) or not isinstance(release.get("id"), int):
        return []
    out = []
    for t in release.get("tracklist") or []:
        if not isinstance(t, dict) or t.get("type_", "track") != "track":
            continue
        title, position = tracks._str(t.get("title")), tracks._str(t.get("position"))
        tid = track_id(release["id"], position) if position else None
        if not title or not tid:
            continue
        artists, text, ids = credit(t.get("artists") or release.get("artists") or [])
        if not artists:
            continue
        out.append({"id": tid, "position": position, "title": title, "artists": artists, "artist_name": text,
                    "artist_ids": frozenset(ids), "length_ms": parse_duration(t.get("duration")),
                    "version": tracks.version_label(title), "raw": t})
    return out


def same_recording(a: dict[str, Any], b: dict[str, Any]) -> bool:
    """La misma grabación en dos ediciones: título exacto, mismos artistas y duración conocida en ambas (±3 %)."""
    if a["artist_ids"] != b["artist_ids"] or tracks._fold(a["title"]) != tracks._fold(b["title"]):
        return False
    la, lb = a["length_ms"], b["length_ms"]
    return bool(la and lb) and abs(la - lb) <= max(la, lb) * LENGTH_TOLERANCE


# --- Búsqueda -----------------------------------------------------------------------------------------------------
def eligible(query: str) -> bool:
    """Solo búsquedas de artista y título (dos palabras significativas o más): con una sola, los homónimos sobran."""
    return len(tracks._tokens(query) - tracks.NEUTRAL_TOKENS) >= 2


def search(query: str, limit: int, transport: Transport | None = None) -> list[schemas.TrackSearchResult]:
    """Pistas de Discogs que contienen todas las palabras de la búsqueda (título + artistas). Nunca falla: si Discogs no
    responde, no hay resultados externos (la búsqueda de MusicBrainz ya se ha respondido igual)."""
    if not eligible(query):
        return []
    tokens = tracks._tokens(query)
    try:
        data = _get("/database/search?" + urllib.parse.urlencode(
            {"q": query, "type": "release", "per_page": SEARCH_PER_PAGE}), transport) or {}
        release_ids, masters = [], set()
        for r in data.get("results") or []:
            if not isinstance(r, dict) or not isinstance(r.get("id"), int):
                continue
            master = r.get("master_id") or None
            if master and master in masters:  # otra edición del mismo master: la primera ya las representa
                continue
            masters.add(master)
            release_ids.append(r["id"])
            if len(release_ids) >= MAX_RELEASES:
                break
        found: list[tuple[dict[str, Any], dict[str, Any]]] = []
        for rid in release_ids:
            release = _get(f"/releases/{rid}", transport)
            for t in release_tracks(release or {}):
                if not tracks.covers_query(tokens, t["title"], t["artist_name"]):
                    continue
                if any(same_recording(t, prev) for prev, _ in found):
                    continue
                found.append((t, release))
    except ProviderError:
        return []
    results = []
    for t, release in found[:limit]:
        summary = release_summary(release)
        results.append(schemas.TrackSearchResult(
            mbid=t["id"], catalog="discogs", title=t["title"], artist_credit=t["artists"], artist_name=t["artist_name"],
            length_ms=t["length_ms"], first_release_date=summary.date, version=t["version"],
            release_title=summary.title or None, release_type=summary.primary_type))
    return results


# --- Ficha --------------------------------------------------------------------------------------------------------
def linked_artist(client: MusicBrainzClient, discogs_artist_id: str) -> str | None:
    """MBID del único artista de MusicBrainz que enlaza ese artista de Discogs. Ante la duda (ninguno, varios o un
    fallo), ninguno: el artista se muestra sin enlace."""
    try:
        fetched = client.get(MB_URL_LOOKUP, {"resource": f"{SITE}/artist/{discogs_artist_id}", "inc": "artist-rels",
                                             "fmt": "json"})
    except ProviderError:
        return None
    ids = {(r.get("artist") or {}).get("id") for r in fetched.data.get("relations") or []
           if isinstance(r, dict) and r.get("target-type") == "artist"}
    ids.discard(None)
    return next(iter(ids)) if len(ids) == 1 else None


def profile(tid: str, client: MusicBrainzClient, transport: Transport | None = None) -> schemas.TrackResponse:
    """Ficha TrackDNA de una pista de Discogs con el contrato de siempre (TrackResponse, catalog = discogs). Solo lo
    documentado: sin portada (imágenes restringidas), sin BPM ni tonalidad, sin interpretación con IA."""
    m = ID_RE.match(tid)
    if not m:
        raise NotFound("Identificador externo no válido")
    release = _get(f"/releases/{m.group(1)}", transport)
    track = next((t for t in release_tracks(release or {}) if t["position"] == m.group(2)), None)
    if release is None or track is None:
        raise NotFound("Esta pista no existe en Discogs")
    summary = release_summary(release)
    page = summary.url
    ref = schemas.SourceRef(label=ATTRIBUTION, url=page, license=LICENSE)

    artists = list(track["artists"])
    for i, a in enumerate(artists[:MAX_LINKED_ARTISTS]):
        mbid = linked_artist(client, a.mbid.rsplit(":", 1)[1])
        if mbid:
            artists[i] = a.model_copy(update={"mbid": mbid})
    first = artists[0]
    main = schemas.TrackArtist(mbid=first.mbid, name=first.name) if not first.mbid.startswith("discogs:") else None

    traits: list[schemas.DnaTrait] = []
    # Misma regla que en MusicBrainz (tracks.release_genre_values): estilos antes que el género amplio, nunca los de
    # un recopilatorio y, en un lanzamiento de varias canciones, nada concreto si sus estilos son de familias distintas.
    names = [n.strip().lower() for n in (release.get("styles") or []) + (release.get("genres") or [])
             if isinstance(n, str) and n.strip()]
    songs = {tracks._fold(tracks._core_title(t["title"])) for t in release_tracks(release)}
    values = tracks.release_genre_values(names, summary.secondary_types, len(songs) > 1) if summary.own else []
    if values:
        traits.append(schemas.DnaTrait(key="genre", group="classification", label="Género", status="community",
                                       scope="release", values=values,
                                       detail=f"Género y estilos de «{summary.title}» en Discogs: describen el lanzamiento.",
                                       sources=[ref]))
    else:
        traits.append(schemas.DnaTrait(key="genre", group="classification", label="Género", status="unavailable",
                                       detail="Discogs no clasifica de forma atribuible a esta pista su lanzamiento."))
    if summary.labels or summary.self_released:
        traits.append(schemas.DnaTrait(key="label", group="context", label="Sello", status="verified",
                                       values=summary.labels[:tracks.LABELS_LIMIT] or [tracks.SELF_RELEASED],
                                       detail="Sello del lanzamiento en Discogs.", sources=[ref]))
    else:
        traits.append(schemas.DnaTrait(key="label", group="context", label="Sello", status="unavailable",
                                       detail="Sin sello documentado en Discogs."))
    if track["version"]:
        traits.append(schemas.DnaTrait(key="version", group="context", label="Versión", status="verified",
                                       values=[track["version"]], detail="Según el título en Discogs.", sources=[ref]))
    for key, label in (("bpm", "BPM"), ("key", "Tonalidad"), ("energy", "Energía")):
        traits.append(schemas.DnaTrait(key=key, group="acoustic", label=label, status="unavailable",
                                       detail="Requiere análisis de audio autorizado. No se estima con IA."))

    remixers = [schemas.ArtistSummary(mbid=f"discogs:artist:{e['id']}", name=discogs.clean_name(e["name"]))
                for e in track["raw"].get("extraartists") or []
                if isinstance(e, dict) and e.get("id") and tracks._str(e.get("name")) and "Remix" in (e.get("role") or "")]
    source = schemas.Source(provider="discogs", url=page, fetched_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
                            license=LICENSE)
    return schemas.TrackResponse(
        mbid=tid, catalog="discogs", title=track["title"], artist_credit=artists,
        artist_name="".join(a.name + a.join_phrase for a in artists), main_artist=main, length_ms=track["length_ms"],
        first_release_date=summary.date, version=track["version"], original_release=summary, releases=[summary],
        release_count=1, releases_status=schemas.SectionStatus(status="ok", total=1, source=source),
        credits=[schemas.TrackCredit(role="Remezcla", artists=remixers)] if remixers else [],
        relations=schemas.TrackRelations(),
        links=[schemas.Link(url=page, label="Discogs", platform="Discogs", scope="release", target="release",
                            release_type=summary.primary_type, formats=summary.formats)],
        dna=schemas.TrackDna(recording_mbid=tid, traits=traits), sources=[ref], source=source)
