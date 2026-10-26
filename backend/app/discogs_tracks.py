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


# --- Género de una pista (V6.2) -------------------------------------------------------------------------------------
GENRE_KIND = "discogs_genre"
GENRE_VERSION = 2  # v2: estilos del lanzamiento cuando mezcla familias
GENRE_TTL_S = 30 * 24 * 3600   # solo se guarda el número del lanzamiento: su contenido, 6 h como mucho (_get)
GENRE_EMPTY_TTL_S = 7 * 24 * 3600
ORIGINAL_MIX_RE = re.compile(r"\s*[(\[]\s*original(?: mix| version)?\s*[)\]]\s*$", re.IGNORECASE)


def release_genre(release: dict[str, Any]) -> list[schemas.DnaTrait]:
    """Género y estilos de un lanzamiento propio aplicados a una de sus pistas. Misma regla que en MusicBrainz
    (tracks.release_genre_values): estilos antes que el género amplio, nunca los de un recopilatorio y, en un
    lanzamiento de varias canciones, nada concreto si sus estilos son de familias distintas."""
    summary = release_summary(release)
    names = [n.strip().lower() for n in (release.get("styles") or []) + (release.get("genres") or [])
             if isinstance(n, str) and n.strip()]
    songs = {tracks._fold(tracks._core_title(t["title"])) for t in release_tracks(release)}
    if not summary.own:
        return []
    values = tracks.release_genre_values(names, summary.secondary_types, len(songs) > 1)
    if not values:
        return []
    ref = schemas.SourceRef(label=ATTRIBUTION, url=summary.url, license=LICENSE)
    out = [schemas.DnaTrait(key="genre", group="classification", label="Género", status="community", scope="release",
                            values=values,
                            detail=f"Género y estilos de «{summary.title}» en Discogs: describen el lanzamiento.",
                            sources=[ref])]
    styles = tracks.release_styles(names, summary.secondary_types) if len(songs) > 1 else []
    if tracks.is_broad(values) and styles:
        out.append(tracks.styles_trait(styles, summary.title, ref))
    return out


def _plain(title: str) -> str:
    return tracks._fold(ORIGINAL_MIX_RE.sub("", title or ""))


def _same_track(t: dict[str, Any], title: str, artist_name: str, length_ms: int | None) -> bool:
    """La misma pista: título igual (sin «(Original Mix)»), el artista entre sus créditos y, si las dos fuentes dan
    duración, la misma (±3 %). Un remix o un edit tiene otro título: nunca coincide con la original."""
    if _plain(t["title"]) != _plain(title):
        return False
    if tracks._fold(artist_name) not in {tracks._fold(discogs.clean_name(a.name)) for a in t["artists"]}:
        return False
    la = t["length_ms"]
    return not (la and length_ms) or abs(la - length_ms) <= max(la, length_ms) * LENGTH_TOLERANCE


def genre_for(key: str, artist_name: str, title: str, length_ms: int | None,
              transport: Transport | None = None) -> list[schemas.DnaTrait]:
    """Género de una pista de MusicBrainz o Deezer sin clasificar: el de su lanzamiento propio en Discogs, si la misma
    pista está en él. `key`: identificador de la grabación (caché del número de lanzamiento). Lanza Unavailable ante un
    fallo temporal (no se guarda nada)."""
    hit = store.get(GENRE_KIND, key)
    if hit is not None and hit.get("version") == GENRE_VERSION:
        rid = hit.get("release_id")
        release = _get(f"/releases/{rid}", transport) if rid else None
        return release_genre(release) if release else []
    query = f"{artist_name} {ORIGINAL_MIX_RE.sub('', title)}".strip()
    found: tuple[int, list[schemas.DnaTrait]] | None = None
    if artist_name and eligible(query):
        data = _get("/database/search?" + urllib.parse.urlencode(
            {"q": query, "type": "release", "per_page": SEARCH_PER_PAGE}), transport) or {}
        seen: set[Any] = set()
        opened = 0
        for r in data.get("results") or []:
            if not isinstance(r, dict) or not isinstance(r.get("id"), int):
                continue
            master = r.get("master_id") or r["id"]
            if master in seen:
                continue
            seen.add(master)
            opened += 1
            if opened > MAX_RELEASES:
                break
            release = _get(f"/releases/{r['id']}", transport) or {}
            if any(_same_track(t, title, artist_name, length_ms) for t in release_tracks(release)):
                traits = release_genre(release)
                if traits:
                    found = (r["id"], traits)
                    break
    store.put(GENRE_KIND, key, {"version": GENRE_VERSION, "release_id": found[0] if found else None},
              GENRE_TTL_S if found else GENRE_EMPTY_TTL_S)
    return found[1] if found else []


CONTEXT_PER_PAGE = 50
CONTEXT_MIN_RELEASES = 5      # con menos, no hay «estilos habituales» que valgan
CONTEXT_MIN_SHARE = 0.2       # un estilo cuenta si está en al menos el 20 % de sus lanzamientos
CONTEXT_MAX_STYLES = 3


def _usual_styles(results: list[dict[str, Any]]) -> tuple[list[str], int]:
    counts: dict[str, int] = {}
    for r in results:
        for style in dict.fromkeys(x for x in r.get("style") or [] if isinstance(x, str) and x.strip()):
            counts[style] = counts.get(style, 0) + 1
    n = len(results)
    if n < CONTEXT_MIN_RELEASES:
        return [], n
    ranked = sorted((c, s) for s, c in counts.items() if c / n >= CONTEXT_MIN_SHARE)
    return [s for _c, s in sorted(ranked, key=lambda x: -x[0])][:CONTEXT_MAX_STYLES], n


def _artist_releases(artist_name: str, transport: Transport | None = None) -> list[dict[str, Any]]:
    """Lanzamientos del propio artista en la búsqueda de Discogs (el título empieza por su nombre: no los de otros que
    lo acreditan). Lanza Unavailable ante un fallo temporal."""
    data = _get("/database/search?" + urllib.parse.urlencode(
        {"artist": artist_name, "type": "release", "per_page": CONTEXT_PER_PAGE}), transport) or {}
    key = tracks._fold(artist_name)
    return [r for r in data.get("results") or [] if isinstance(r, dict)
            and tracks._fold(discogs.clean_name(str(r.get("title") or "").split(" - ")[0])) == key]


SOUND_MAX_LABELS = 5


def artist_sound(artist_name: str, transport: Transport | None = None) -> tuple[list[str], list[str], int]:
    """Carteles 4 (V6.8): (estilos habituales, sellos habituales, lanzamientos contados) del artista en Discogs, con la
    misma búsqueda que el contexto del sonido. Un sello cuenta si tiene al menos dos lanzamientos suyos; sin el
    «Not On Label» de las autoediciones."""
    found = _artist_releases(artist_name, transport)
    styles, n = _usual_styles(found)
    counts: dict[str, list[Any]] = {}
    for r in found:
        for raw in dict.fromkeys(x for x in r.get("label") or [] if isinstance(x, str) and x.strip()):
            if NOT_ON_LABEL_RE.search(raw):
                continue
            name = discogs.clean_name(raw)
            hit = counts.setdefault(tracks._fold(name), [name, 0])
            hit[1] += 1
    labels = [name for name, c in sorted(counts.values(), key=lambda x: -x[1]) if c >= 2][:SOUND_MAX_LABELS]
    return styles, labels, n


def context_traits(label: str | None, artist_name: str | None, transport: Transport | None = None) -> list[schemas.DnaTrait]:
    """Estilos habituales del sello y del artista en Discogs (V6.4): contexto para las canciones que ninguna fuente
    clasifica. Nunca se presentan como el género de la pista. Cada búsqueda confirma el sello (o el artista) en cada
    resultado, y el sello solo cuenta si el artista ha publicado en él (sellos homónimos). Lanza Unavailable ante un
    fallo temporal."""
    out: list[schemas.DnaTrait] = []
    if label and not NOT_ON_LABEL_RE.search(label):
        data = _get("/database/search?" + urllib.parse.urlencode(
            {"label": label, "type": "release", "per_page": CONTEXT_PER_PAGE}), transport) or {}
        key = tracks._fold(discogs.clean_name(label))
        same = [r for r in data.get("results") or [] if isinstance(r, dict)
                and key in {tracks._fold(discogs.clean_name(x)) for x in r.get("label") or [] if isinstance(x, str)}]
        # Sellos homónimos («CSS»): solo si entre sus lanzamientos hay alguno del propio artista.
        own = not artist_name or any(tracks._fold(discogs.clean_name(str(r.get("title") or "").split(" - ")[0]))
                                     == tracks._fold(artist_name) for r in same)
        styles, n = _usual_styles(same) if own else ([], 0)
        if styles:
            out.append(schemas.DnaTrait(
                key="label_styles", group="context", label="Estilos del sello", status="community", scope="label",
                values=styles, detail=f"Estilos más frecuentes en {n} lanzamientos de {label} en Discogs: contexto del "
                                      "sello, no una clasificación de esta pista.",
                sources=[schemas.SourceRef(label=ATTRIBUTION, url=f"{SITE}/search/?type=label&q={urllib.parse.quote(label)}",
                                           license=LICENSE)]))
    if artist_name:
        styles, n = _usual_styles(_artist_releases(artist_name, transport))
        if styles:
            out.append(schemas.DnaTrait(
                key="artist_sound", group="context", label="Estilos del artista", status="community", scope="artist",
                values=styles, detail=f"Estilos más frecuentes en {n} lanzamientos de {artist_name} en Discogs: "
                                      "contexto del artista, no una clasificación de esta pista.",
                sources=[schemas.SourceRef(label=ATTRIBUTION, url=f"{SITE}/search/?type=artist&q={urllib.parse.quote(artist_name)}",
                                           license=LICENSE)]))
    return out


def with_context(dna: schemas.TrackDna, found: list[schemas.DnaTrait]) -> schemas.TrackDna:
    present = {t.key for t in dna.traits}
    extra = [t for t in found if t.key not in present]
    return dna.model_copy(update={"traits": [*dna.traits, *extra]}) if extra else dna


def with_inferred_genre(dna: schemas.TrackDna) -> schemas.TrackDna:
    """Último recurso (V6.5): si nadie clasifica la pista, su género se deduce de los estilos habituales de su artista y
    de su sello, con scope «artist» o «label» para que nunca se lea como una clasificación propia. Primero los estilos
    que comparten artista y sello; si no, los del artista (Discogs, luego Wikidata); si no, los del sello. Solo una
    familia: el estilo principal y los de su familia (o comodín). Nunca pisa un género concreto."""
    if not needs_genre(dna):
        return dna
    by_key = {t.key: t for t in dna.traits if t.status != "unavailable" and t.values}
    artist = by_key.get("artist_sound") or by_key.get("artist_style")
    label = by_key.get("label_styles")
    candidates: list[tuple[list[str], str, list[schemas.SourceRef], str]] = []
    if artist and label:
        shared = [v for v in artist.values if tracks._fold(v) in {tracks._fold(x) for x in label.values}]
        if shared:
            candidates.append((shared, "label", [*artist.sources, *label.sources],
                               "Deducido de los estilos que comparten su artista y su sello: no clasifica esta pista."))
    if artist:
        candidates.append((artist.values, "artist", artist.sources,
                           "Deducido de los estilos habituales de su artista: no clasifica esta pista."))
    if label:
        candidates.append((label.values, "label", label.sources,
                           "Deducido de los estilos habituales de su sello: no clasifica esta pista."))
    for names, scope, sources, detail in candidates:
        values = tracks.single_family(names)
        if not values:
            continue
        genre = schemas.DnaTrait(key="genre", group="classification", label="Género", status="community", scope=scope,
                                 values=values, detail=detail, sources=sources)
        has = any(t.key == "genre" for t in dna.traits)
        traits = [genre if t.key == "genre" else t for t in dna.traits] if has else [genre, *dna.traits]
        return dna.model_copy(update={"traits": traits})
    return dna


def needs_genre(dna: schemas.TrackDna) -> bool:
    """Sin género o solo con el amplio («Electrónica»): Discogs puede concretarlo."""
    g = next((t for t in dna.traits if t.key == "genre"), None)
    return g is None or g.status == "unavailable" or tracks.is_broad(g.values)


def with_genre(dna: schemas.TrackDna, found: list[schemas.DnaTrait]) -> schemas.TrackDna:
    """Género de Discogs donde no había o solo era «Electrónica» (nunca pisa uno concreto); sus estilos del lanzamiento
    solo si la ficha no los tiene ya."""
    genre = next((t for t in found if t.key == "genre"), None)
    traits = list(dna.traits)
    current = next((t for t in traits if t.key == "genre"), None)
    if genre and (current is None or current.status == "unavailable"
                  or (tracks.is_broad(current.values) and not tracks.is_broad(genre.values))):
        traits = [genre if t.key == "genre" else t for t in traits] if current else [genre, *traits]
        if not tracks.is_broad(genre.values):  # con un género concreto, los estilos de un EP mezclado sobran
            traits = [t for t in traits if t.key != "release_styles"]
    if not any(t.key == "release_styles" for t in traits):
        current = next((t for t in traits if t.key == "genre"), None)
        styles = next((t for t in found if t.key == "release_styles"), None)
        if styles and (current is None or tracks.is_broad(current.values) or current.status == "unavailable"):
            traits.append(styles)
    return dna.model_copy(update={"traits": traits})


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
    genre = release_genre(release)
    if genre:
        traits += genre
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
