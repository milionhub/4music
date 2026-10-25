"""Deezer (V6, fuentes de uso no comercial): identidad del artista en Deezer y su foto. Sin clave.

Condiciones (https://developers.deezer.com/termsofuse y /guidelines, leídas el 2026-10-25): uso «strictly limited for a
non-commercial purpose»; las fotos e imágenes pertenecen a Deezer o a sus titulares (no tienen licencia libre: se
muestran como dato de Deezer, con enlace a su ficha); prohibido guardar audio en local. Solo activo con
DATA_USE=noncommercial (config.noncommercial_sources); con DATA_USE=commercial no se hace ninguna petición.

Identidad, nunca por la primera coincidencia de un nombre (la búsqueda por nombre falla, además, con los cambios de nombre:
Chris Stussy figura en Deezer como «CHRIS STASSY»). Por orden:
1. Enlace de MusicBrainz a deezer.com/artist/<id>. Con varios (fichas duplicadas en Deezer), la que tiene foto y más
   seguidores.
2. ISRC de grabaciones acreditadas solo a ese artista → pista de Deezer → artista principal. Dos ISRC que coinciden, o uno
   si el nombre también coincide.
3. Nombre exacto (o alias de MusicBrainz) y al menos dos títulos en común entre su discografía de MusicBrainz y la de
   Deezer (uno si MusicBrainz solo tiene uno). Si pasan dos candidatos, ninguno.
Caché propia por MBID (30 días con ID, 7 sin él); un fallo de red no se guarda.
"""

from __future__ import annotations

import json
import re
import threading
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any

from app import reccobeats, schemas, store, tracks
from app.musicbrainz import MusicBrainzClient, NotFound, ProviderError

KIND = "deezer_artist"
VERSION = 1
TTL_S = 30 * 24 * 3600
EMPTY_TTL_S = 7 * 24 * 3600
BASE_URL = "https://api.deezer.com"
TIMEOUT_S = 4
MIN_INTERVAL_S = 0.2  # Deezer admite 50 peticiones cada 5 s; vamos muy por debajo
USER_AGENT = "music-discovery/0.1 (portfolio demo, non-commercial)"
MAX_ISRCS = 3
MAX_NAME_CANDIDATES = 2
MAX_LINKED = 3
IMAGE_SIZE = 1000
LICENSE = "© titulares de derechos · Deezer API (uso no comercial)"
TERMS_URL = "https://developers.deezer.com/termsofuse"
NO_DATA = 800  # código de error de Deezer para «no data» (responde 200 con {"error": …})

ARTIST_URL = re.compile(r"^https?://(?:www\.)?deezer\.com/(?:[a-z]{2}(?:-[a-z]{2})?/)?artist/(\d+)/?$", re.IGNORECASE)
PICTURE_HASH = re.compile(r"/images/artist/([0-9a-f]*)/")
EMPTY_HASHES = {"", "d41d8cd98f00b204e9800998ecf8427e"}  # Deezer sirve una silueta genérica con el hash vacío
TITLE_SUFFIX = re.compile(r"\s+(ep|single|lp)$")

Transport = Callable[[str], dict[str, Any]]
_lock = threading.Lock()
_last_request = 0.0


class Unavailable(Exception):
    """Fallo temporal (red, cuota o respuesta inesperada): no se guarda."""


def _default_transport(url: str) -> dict[str, Any]:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _get(path: str, params: dict[str, str] | None, transport: Transport) -> dict[str, Any] | None:
    """JSON de Deezer o None si no tiene la entidad. Espacia las peticiones de todo el proceso."""
    global _last_request
    url = f"{BASE_URL}/{path}" + (f"?{urllib.parse.urlencode(params)}" if params else "")
    with _lock:
        wait = MIN_INTERVAL_S - (time.monotonic() - _last_request)
        if wait > 0:
            time.sleep(wait)
        _last_request = time.monotonic()
        try:
            data = transport(url)
        except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
            raise Unavailable(exc.__class__.__name__) from exc
    if not isinstance(data, dict):
        raise Unavailable("respuesta con forma inesperada")
    error = data.get("error")
    if isinstance(error, dict):
        if error.get("code") == NO_DATA:
            return None
        raise Unavailable(f"Deezer error {error.get('code')}")  # cuota (4) u otro: temporal
    return data


def fold(text: str | None) -> str:
    plain = unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode()
    return " ".join(re.sub(r"[^a-z0-9]+", " ", plain.lower()).split())


def _title(text: str | None) -> str:
    return TITLE_SUFFIX.sub("", fold(text))


def linked_ids(mb_artist: dict[str, Any]) -> list[str]:
    """IDs de Deezer que MusicBrainz enlaza al artista (relaciones de URL)."""
    out = []
    for rel in mb_artist.get("relations") or []:
        match = ARTIST_URL.match(((rel.get("url") or {}).get("resource") or "").strip())
        if match:
            out.append(match.group(1))
    return list(dict.fromkeys(out))


def recording_isrcs(recordings: list[dict[str, Any]], mbid: str) -> list[str]:
    """Un ISRC por grabación acreditada solo a ese artista (sin colaboraciones: su artista principal podría ser otro)."""
    out = []
    for rec in recordings:
        credit = [c for c in rec.get("artist-credit") or [] if isinstance(c, dict)]
        if [((c.get("artist") or {}).get("id")) for c in credit] != [mbid]:
            continue
        isrc = next((i for i in rec.get("isrcs") or [] if isinstance(i, str) and i.strip()), None)
        if isrc and isrc not in out:
            out.append(isrc)
        if len(out) == MAX_ISRCS:
            break
    return out


def picture(artist: dict[str, Any]) -> str | None:
    """Foto de 1000×1000 de la ficha de Deezer; None si es la silueta genérica."""
    url = artist.get("picture_xl")
    if not isinstance(url, str) or not url.startswith("https://"):
        return None
    match = PICTURE_HASH.search(url)
    return None if not match or match.group(1) in EMPTY_HASHES else url


def _names(mb_artist: dict[str, Any]) -> set[str]:
    names = {fold(mb_artist.get("name"))} | {fold(a.get("name")) for a in mb_artist.get("aliases") or []
                                              if isinstance(a, dict)}
    return {n for n in names if n}


def _by_isrc(isrcs: list[str], names: set[str], transport: Transport) -> str | None:
    votes: Counter[str] = Counter()
    matching_name: set[str] = set()
    for isrc in isrcs:
        track = _get(f"track/isrc:{urllib.parse.quote(isrc)}", None, transport)
        artist = (track or {}).get("artist") or {}
        if artist.get("id"):
            votes[str(artist["id"])] += 1
            if fold(artist.get("name")) in names:
                matching_name.add(str(artist["id"]))
    if not votes:
        return None
    (best, count), *rest = votes.most_common()
    if rest and rest[0][1] == count:
        return None  # empate entre dos artistas: ambiguo
    return best if count >= 2 or best in matching_name else None


def _by_name(name: str, names: set[str], titles: list[str], transport: Transport) -> str | None:
    wanted = {t for t in (_title(x) for x in titles) if t}
    if not wanted:
        return None
    hits = (_get("search/artist", {"q": name, "limit": "10"}, transport) or {}).get("data") or []
    candidates = [h for h in hits if isinstance(h, dict) and h.get("id") and fold(h.get("name")) in names]
    passed = []
    for cand in candidates[:MAX_NAME_CANDIDATES]:
        albums = (_get(f"artist/{cand['id']}/albums", {"limit": "100"}, transport) or {}).get("data") or []
        common = wanted & {_title(a.get("title")) for a in albums if isinstance(a, dict)}
        if len(common) >= min(2, len(wanted)):
            passed.append(str(cand["id"]))
    return passed[0] if len(passed) == 1 else None


def resolve(mb_artist: dict[str, Any], mbid: str, recordings: Callable[[], list[dict[str, Any]]],
            titles: Callable[[], list[str]], transport: Transport | None = None) -> dict[str, Any] | None:
    """Ficha verificada del artista en Deezer ({id, via, name, link, picture}) o None. Las grabaciones y los títulos
    se piden solo si hacen falta. Lanza Unavailable ante un fallo temporal."""
    hit = store.get(KIND, mbid)
    if hit is not None and hit.get("version") == VERSION:
        return hit.get("artist")
    get = transport or _default_transport
    names = _names(mb_artist)
    linked = linked_ids(mb_artist)
    artist = None
    if linked:
        # Varios enlaces: MusicBrainz dice que todos son este artista (Deezer duplica fichas, p. ej. «Daft Punk -
        # Stardust» junto a «Stardust»). Se elige la que tiene foto y, entre ellas, la de más seguidores.
        cards = [c for c in (_get(f"artist/{i}", None, get) for i in linked[:MAX_LINKED]) if c and c.get("id")]
        artist = max(cards, key=lambda c: (picture(c) is not None, c.get("nb_fan") or 0), default=None)
        via = "musicbrainz_link"
    else:
        found, via = _by_isrc(recording_isrcs(recordings(), mbid), names, get), "isrc"
        if not found:
            found, via = _by_name(str(mb_artist.get("name") or ""), names, titles(), get), "catalog_match"
        artist = _get(f"artist/{found}", None, get) if found else None
    record = ({"id": str(artist["id"]), "via": via, "name": artist.get("name"), "link": artist.get("link"),
               "picture": picture(artist)} if artist and artist.get("id") else None)
    store.put(KIND, mbid, {"version": VERSION, "artist": record}, TTL_S if record else EMPTY_TTL_S)
    return record


def artist_image(record: dict[str, Any] | None) -> schemas.ArtistImage | None:
    if not record or not record.get("picture"):
        return None
    link = record.get("link") if str(record.get("link") or "").startswith("https://") else (
        f"https://www.deezer.com/artist/{record['id']}")
    return schemas.ArtistImage(url=record["picture"], width=IMAGE_SIZE, height=IMAGE_SIZE, page_url=link, author=None,
                               license=LICENSE, license_url=TERMS_URL, source="deezer", via=f"deezer_{record['via']}")


# --- Canciones (V6.1): la misma grabación en Deezer, para el extracto de 30 s y el sello que MusicBrainz no tiene ---
TRACK_KIND = "deezer_track"
TRACK_VERSION = 1
LENGTH_TOLERANCE = 0.03
LENGTH_MIN_SLACK_MS = 1000  # Deezer redondea la duración a segundos
RELEASE_TYPES = {"single", "ep", "album"}  # nunca recopilatorios
LABEL_DETAIL = ("Sello de la edición en Deezer: la misma grabación (ISRC y duración) en un lanzamiento propio del "
                "artista y del mismo año que la original.")


def _same_length(seconds: Any, length_ms: int) -> bool:
    return isinstance(seconds, (int, float)) and abs(seconds * 1000 - length_ms) <= max(length_ms * LENGTH_TOLERANCE,
                                                                                         LENGTH_MIN_SLACK_MS)


def track_match(recording_mbid: str, isrcs: list[str], length_ms: int | None,
                transport: Transport | None = None) -> dict[str, Any] | None:
    """La grabación en Deezer ({id, link, isrc, album, label, release_date, own_release}) o None. Solo por ISRC de la
    grabación y con la misma duración (±3 %): otra versión con el ISRC mal asignado se descarta. Sin ISRC o sin duración
    no se pregunta (ni se guarda: pueden llegar después). Lanza Unavailable ante un fallo temporal."""
    hit = store.get(TRACK_KIND, recording_mbid)
    if hit is not None and hit.get("version") == TRACK_VERSION:
        return hit.get("track")
    ids = [i for i in dict.fromkeys(isrcs) if isinstance(i, str) and i.strip()][:MAX_ISRCS]
    if not ids or not length_ms:
        return None
    get = transport or _default_transport
    record = None
    for isrc in ids:
        found = _get(f"track/isrc:{urllib.parse.quote(isrc)}", None, get)
        if not found or found.get("isrc") != isrc or not _same_length(found.get("duration"), length_ms):
            continue
        album_id = (found.get("album") or {}).get("id")
        album = (_get(f"album/{album_id}", None, get) if album_id else None) or {}
        own = (album.get("record_type") in RELEASE_TYPES
               and (album.get("artist") or {}).get("id") == (found.get("artist") or {}).get("id"))
        record = {"id": str(found["id"]), "link": found.get("link"), "isrc": isrc, "album": album.get("title"),
                  "label": album.get("label"), "release_date": album.get("release_date"), "own_release": own}
        break
    store.put(TRACK_KIND, recording_mbid, {"version": TRACK_VERSION, "track": record}, TTL_S if record else EMPTY_TTL_S)
    return record


def track_url(record: dict[str, Any] | None) -> str | None:
    if not record:
        return None
    link = str(record.get("link") or "")
    return link if link.startswith("https://") else f"https://www.deezer.com/track/{record['id']}"


def preview(record: dict[str, Any] | None, transport: Transport | None = None) -> str | None:
    """URL del extracto de 30 s, pedida en el momento (Deezer la firma y caduca en minutos: nunca se guarda). El audio
    no pasa por el backend ni se almacena (guidelines de Deezer)."""
    if not record:
        return None
    found = _get(f"track/{record['id']}", None, transport or _default_transport) or {}
    url = found.get("preview")
    return url if isinstance(url, str) and url.startswith("https://") else None


def label_value(record: dict[str, Any] | None, first_release_date: str | None) -> str | None:
    """Sello de Deezer solo si es un lanzamiento propio del artista y del mismo año que la edición original (una
    reedición posterior trae el sello del reeditor: Villalobos figura en Deezer con «EAMS», de 2017)."""
    if not record or not record.get("own_release") or not first_release_date:
        return None
    label = str(record.get("label") or "").strip()
    same_year = str(record.get("release_date") or "")[:4] == first_release_date[:4]
    return label if label and same_year else None


def with_label(dna: schemas.TrackDna, record: dict[str, Any] | None, first_release_date: str | None) -> schemas.TrackDna:
    """Completa el sello solo si MusicBrainz no documenta ninguno (ni autoedición)."""
    label = label_value(record, first_release_date)
    if not label:
        return dna
    ref = schemas.SourceRef(label="Deezer", url=track_url(record) or BASE_URL, license=LICENSE)
    traits = [t.model_copy(update={"status": "verified", "scope": "release", "values": [label], "detail": LABEL_DETAIL,
                                   "sources": [ref]})
              if t.key == "label" and t.status == "unavailable" else t for t in dna.traits]
    return dna.model_copy(update={"traits": traits})


# --- Catálogo de reserva (V6.1): canciones que no están ni en MusicBrainz ni en Discogs ---------------------------
EXT_ID_RE = re.compile(r"^deezer:(\d{1,12})$")
SEARCH_LIMIT = 25
ATTRIBUTION = "Datos de Deezer"
RECORD_TYPES = {"single": "Single", "ep": "EP", "album": "Album"}


def ext_id(track_id: Any) -> str:
    return f"deezer:{track_id}"


def _https(url: Any) -> str | None:
    return url if isinstance(url, str) and url.startswith("https://") else None


def _length_ms(found: dict[str, Any]) -> int | None:
    return int(found["duration"]) * 1000 if isinstance(found.get("duration"), int) and found["duration"] > 0 else None


def _credit(found: dict[str, Any]) -> list[schemas.CreditedArtist]:
    """Artistas de la pista con su ID de Deezer (con espacio de nombres: no son MBID). Contribuidores si los hay."""
    people = [c for c in found.get("contributors") or [] if isinstance(c, dict)] or [found.get("artist") or {}]
    valid = [p for p in people if p.get("id") and str(p.get("name") or "").strip()]
    return [schemas.CreditedArtist(mbid=f"deezer:artist:{p['id']}", name=str(p["name"]).strip(),
                                   join_phrase=", " if i < len(valid) - 1 else "") for i, p in enumerate(valid)]


def search_tracks(query: str, limit: int, transport: Transport | None = None) -> list[schemas.TrackSearchResult]:
    """Pistas de Deezer con todas las palabras de la búsqueda (título + artista), como en MusicBrainz y Discogs. Nunca
    falla. Dos resultados con el mismo ISRC son la misma grabación; un remix o un edit, otra canción."""
    if len(tracks._tokens(query) - tracks.NEUTRAL_TOKENS) < 2:
        return []
    tokens = tracks._tokens(query)
    try:
        data = _get("search/track", {"q": query, "limit": str(SEARCH_LIMIT)}, transport or _default_transport) or {}
    except Unavailable:
        return []
    results, seen = [], set()
    for t in data.get("data") or []:
        if not isinstance(t, dict) or not t.get("id") or not str(t.get("title") or "").strip():
            continue
        artist = str((t.get("artist") or {}).get("name") or "")
        if not tracks.covers_query(tokens, t["title"], artist):
            continue
        key = t.get("isrc") or (tracks._fold(t["title"]), artist.casefold(), t.get("duration"))
        if key in seen:
            continue
        seen.add(key)
        album = t.get("album") or {}
        results.append(schemas.TrackSearchResult(
            mbid=ext_id(t["id"]), catalog="deezer", title=t["title"].strip(), artist_credit=_credit(t),
            artist_name=artist, length_ms=_length_ms(t), version=tracks.version_label(t["title"]),
            release_title=album.get("title"), cover_url=_https(album.get("cover_xl"))))
        if len(results) >= limit:
            break
    return results


def _linked_mbid(client: MusicBrainzClient, deezer_artist_id: str) -> str | None:
    """MBID del único artista de MusicBrainz que enlaza esa ficha de Deezer; ante la duda, ninguno."""
    try:
        fetched = client.get("https://musicbrainz.org/ws/2/url", {
            "resource": f"https://www.deezer.com/artist/{deezer_artist_id}", "inc": "artist-rels", "fmt": "json"})
    except ProviderError:
        return None
    ids = {(r.get("artist") or {}).get("id") for r in fetched.data.get("relations") or []
           if isinstance(r, dict) and r.get("target-type") == "artist"}
    ids.discard(None)
    return next(iter(ids)) if len(ids) == 1 else None


def track_profile(tid: str, client: MusicBrainzClient, transport: Transport | None = None) -> schemas.TrackResponse:
    """Ficha TrackDNA de una pista de Deezer (catalog = deezer) con el contrato de siempre. Solo lo que Deezer documenta:
    lanzamiento, sello, fecha, ISRC y portada; el tempo, el estimado por ReccoBeats para ese ISRC y duración. Sin
    género (Deezer solo da uno amplio del lanzamiento) ni interpretación con IA. Lanza Unavailable ante un fallo."""
    m = EXT_ID_RE.match(tid)
    if not m:
        raise NotFound("Identificador externo no válido")
    get = transport or _default_transport
    found = _get(f"track/{m.group(1)}", None, get)
    if not found or not str(found.get("title") or "").strip():
        raise NotFound("Esta pista no existe en Deezer")
    album_id = (found.get("album") or {}).get("id")
    album = (_get(f"album/{album_id}", None, get) if album_id else None) or {}
    page = track_url({"id": found["id"], "link": found.get("link")}) or BASE_URL
    ref = schemas.SourceRef(label=ATTRIBUTION, url=page, license=LICENSE)
    artists = _credit(found)
    for i, a in enumerate(artists[:3]):
        mbid = _linked_mbid(client, a.mbid.rsplit(":", 1)[1])
        if mbid:
            artists[i] = a.model_copy(update={"mbid": mbid})
    first = artists[0] if artists else None
    main = schemas.TrackArtist(mbid=first.mbid, name=first.name) if first and not first.mbid.startswith("deezer:") else None
    title, length_ms = found["title"].strip(), _length_ms(found)
    compilation = album.get("record_type") == "compile"
    label = str(album.get("label") or "").strip()
    date = str(album.get("release_date") or found.get("release_date") or "") or None
    cover = _https(album.get("cover_xl"))
    release = schemas.TrackRelease(
        mbid=f"deezer:album:{album_id or 0}", title=str(album.get("title") or ""),
        primary_type=RECORD_TYPES.get(str(album.get("record_type") or "")),
        secondary_types=["Compilation"] if compilation else [], date=date, labels=[label] if label else [],
        formats=["Digital Media"], own=not compilation, cover_url=cover, url=_https(album.get("link")) or page)
    version = tracks.version_label(title)
    traits = [schemas.DnaTrait(key="genre", group="classification", label="Género", status="unavailable",
                               detail="Deezer solo da un género amplio del lanzamiento («Dance», «Electro»): no se usa.")]
    if label and not compilation:
        traits.append(schemas.DnaTrait(key="label", group="context", label="Sello", status="verified", scope="release",
                                       values=[label], detail="Sello del lanzamiento en Deezer.", sources=[ref]))
    else:
        traits.append(schemas.DnaTrait(key="label", group="context", label="Sello", status="unavailable",
                                       detail="Sin sello atribuible en Deezer."))
    if version:
        traits.append(schemas.DnaTrait(key="version", group="context", label="Versión", status="verified",
                                       values=[version], detail="Según el título en Deezer.", sources=[ref]))
    for key, name in (("bpm", "BPM"), ("key", "Tonalidad"), ("energy", "Energía")):
        traits.append(schemas.DnaTrait(key=key, group="acoustic", label=name, status="unavailable",
                                       detail="Requiere análisis de audio autorizado. No se estima con IA."))
    isrc = found.get("isrc") if isinstance(found.get("isrc"), str) and found["isrc"].strip() else None
    dna = schemas.TrackDna(recording_mbid=tid, traits=traits)
    if isrc:
        dna = reccobeats.with_tempo(dna, reccobeats.lookup(tid, [isrc], length_ms))
    source = schemas.Source(provider="deezer", url=page, license=LICENSE,
                            fetched_at=datetime.now(timezone.utc).isoformat(timespec="seconds"))
    return schemas.TrackResponse(
        mbid=tid, catalog="deezer", title=title, artist_credit=artists,
        artist_name="".join(a.name + a.join_phrase for a in artists), main_artist=main, length_ms=length_ms,
        first_release_date=date, version=version, isrcs=[isrc] if isrc else [], cover_url=cover,
        original_release=release, releases=[release], release_count=1,
        releases_status=schemas.SectionStatus(status="ok", total=1, source=source), relations=schemas.TrackRelations(),
        links=[schemas.Link(url=page, label="Deezer", platform="Deezer", scope="recording", target="track")],
        dna=dna, deezer_url=page, sources=[ref], source=source)
