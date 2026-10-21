"""Enlaces externos de MusicBrainz: deduplicados por URL y con etiquetas comprensibles.

Solo se usan las URL que documenta MusicBrainz para ese MBID; nunca se construyen perfiles a partir del nombre.
Las plataformas musicales conocidas (por dominio) van primero y en este orden; el resto, a «Más enlaces».
"""

from __future__ import annotations

import re
from urllib.parse import parse_qs, urlsplit

from app import schemas

# (fragmento de dominio, etiqueta, categoría) en orden de prioridad visual.
MUSIC_PLATFORMS: list[tuple[str, str, str]] = [
    ("open.spotify.com", "Spotify", "listen"),
    ("soundcloud.com", "SoundCloud", "listen"),
    ("beatport.com", "Beatport", "buy"),
    ("music.apple.com", "Apple Music", "listen"),
    ("itunes.apple.com", "Apple Music", "listen"),
    ("bandcamp.com", "Bandcamp", "buy"),
    ("traxsource.com", "Traxsource", "buy"),
    ("juno.co.uk", "Juno Download", "buy"),
    ("deezer.com", "Deezer", "listen"),
    ("tidal.com", "TIDAL", "listen"),
    ("qobuz.com", "Qobuz", "listen"),
    ("music.youtube.com", "YouTube Music", "listen"),
    ("youtube.com", "YouTube", "listen"),
    ("mixcloud.com", "Mixcloud", "listen"),
    ("audiomack.com", "Audiomack", "listen"),
]
OTHER_HOSTS: list[tuple[str, str]] = [
    ("ra.co", "Resident Advisor"),
    ("residentadvisor.net", "Resident Advisor"),
    ("discogs.com", "Discogs"),
    ("instagram.com", "Instagram"),
    ("facebook.com", "Facebook"),
    ("twitter.com", "X / Twitter"),
    ("x.com", "X / Twitter"),
    ("last.fm", "Last.fm"),
    ("wikidata.org", "Wikidata"),
    ("wikipedia.org", "Wikipedia"),
    ("allmusic.com", "AllMusic"),
    ("songkick.com", "Songkick"),
    ("bandsintown.com", "Bandsintown"),
    ("setlist.fm", "setlist.fm"),
    ("rateyourmusic.com", "Rate Your Music"),
]
# IDs de proveedor que se pueden leer de una URL documentada (para cruces futuros por identificador, T2.1 §F).
# (proveedor, patrón con grupos «kind» e «id»). Bandcamp no expone un ID numérico: el ID es la propia URL canónica.
EXTERNAL_ID_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("spotify", re.compile(r"^open\.spotify\.com/(?:intl-[a-z-]+/)?(?P<kind>album|track)/(?P<id>[A-Za-z0-9]{22})$")),
    ("deezer", re.compile(r"^deezer\.com/(?:[a-z]{2}/)?(?P<kind>album|track)/(?P<id>\d+)$")),
    ("apple_music", re.compile(r"^(?:music|itunes)\.apple\.com/(?:[a-z]{2}/)?(?P<kind>album|song)/(?:[^/]+/)?(?:id)?(?P<id>\d+)$")),
    ("tidal", re.compile(r"^tidal\.com/(?:browse/)?(?P<kind>album|track)/(?P<id>\d+)$")),
    ("discogs", re.compile(r"^discogs\.com/(?:[a-z]{2}/)?(?P<kind>release|master)/(?P<id>\d+)(?:-[^/]*)?$")),
    ("beatport", re.compile(r"^beatport\.com/(?P<kind>release|track)/[^/]+/(?P<id>\d+)$")),
]
# Destinos documentados en MusicBrainz que el proveedor ya no sirve, comprobados a mano (no hay validación en red).
# (proveedor, id) → evidencia. Se ocultan en la app; la relación sigue en MusicBrainz y conviene corregirla allí.
DEAD_LINKS: dict[tuple[str, str], str] = {
    ("apple_music", "1726980894"): "2026-10-18: 404 en /gb, /es y /us; iTunes Lookup sin resultados (Chris Stussy — Desire)",
}
TRACK_KINDS = {"track", "song"}
BANDCAMP_RE = re.compile(r"^[a-z0-9-]+\.bandcamp\.com/(?P<kind>album|track)/[^/]+$")
AMAZON_RE = re.compile(r"^(?:music\.)?amazon\.(?:com|ca|de|fr|es|it|nl|se|pl|in|co\.uk|co\.jp|com\.au|com\.br|com\.mx)$")
KIND_LABELS = {
    "official homepage": "Web oficial",
    "free streaming": "Streaming gratuito",
    "streaming": "Streaming",
    "purchase for download": "Compra digital",
    "purchase for mail-order": "Compra física",
    "download for free": "Descarga gratuita",
    "social network": "Red social",
    "fanpage": "Página de fans",
    "blog": "Blog",
    "biography": "Biografía",
    "lyrics": "Letras",
    "image": "Imagen",
    "other databases": "Otra base de datos",
}
PRIMARY_MAX = 6


def _host(url: str) -> str:
    host = urlsplit(url).netloc.lower()
    return host[4:] if host.startswith("www.") else host


def _canonical(url: str) -> str:
    parts = urlsplit(url.strip())
    return f"{parts.netloc.lower().removeprefix('www.')}{parts.path.rstrip('/')}" + (f"?{parts.query}" if parts.query else "")


def _match(host: str, fragment: str) -> bool:
    return host == fragment or host.endswith("." + fragment)


def classify(url: str, kinds: list[str]) -> tuple[str, str | None, int]:
    """Devuelve (etiqueta, plataforma musical o None, prioridad)."""
    host = _host(url)
    for i, (fragment, label, _category) in enumerate(MUSIC_PLATFORMS):
        if _match(host, fragment):
            return label, label, i
    for fragment, label in OTHER_HOSTS:
        if _match(host, fragment):
            return label, None, 1000
    if AMAZON_RE.match(host):  # amazon.de, amazon.co.uk…: un solo nombre para todas las tiendas
        return "Amazon", None, 1000
    if "official homepage" in kinds:
        return "Web oficial", None, 999
    kind_label = next((KIND_LABELS[k] for k in kinds if k in KIND_LABELS), None)
    return kind_label or host or "Enlace", None, 1001


def external_id(url: str) -> tuple[str, str, str] | None:
    """(proveedor, tipo, id) si la URL es de un proveedor conocido con un identificador estable; si no, None."""
    canonical = _canonical(url).split("?", 1)[0]
    for provider, pattern in EXTERNAL_ID_PATTERNS:
        m = pattern.match(canonical)
        if m:
            return provider, m.group("kind"), m.group("id")
    m = BANDCAMP_RE.match(canonical)
    return ("bandcamp", m.group("kind"), canonical) if m else None


def is_dead(url: str) -> bool:
    parsed = external_id(url)
    return parsed is not None and (parsed[0], parsed[2]) in DEAD_LINKS


def destination(url: str) -> tuple[str, str | None]:
    """Clave del destino musical y si es una pista («track») o un lanzamiento («release»). Con un ID de proveedor,
    la clave ignora la tienda de país (music.apple.com/gb y /us del mismo álbum son un destino); si no, es la URL."""
    parsed = external_id(url)
    if not parsed:
        return _canonical(url), None
    provider, kind, value = parsed
    if provider == "apple_music" and kind == "album":
        song = parse_qs(urlsplit(url).query).get("i")  # …/album/x/123?i=456 abre la pista 456 dentro del álbum
        if song:
            return f"apple_music:song:{song[0]}", "track"
    return f"{provider}:{kind}:{value}", "track" if kind in TRACK_KINDS else "release"


def normalize_links(relations: list[dict]) -> list[schemas.Link]:
    """Relaciones URL de MusicBrainz → enlaces únicos por destino, con todos sus tipos fusionados.
    Si la relación trae `_scope` (grabación o lanzamiento, en TrackDNA), se conserva el de la primera aparición, y con
    él a qué lleva el enlace (`target`: la pista o el lanzamiento que la contiene) y el tipo de ese lanzamiento."""
    merged: dict[str, tuple[str, list[str], dict]] = {}
    for rel in relations:
        url = ((rel.get("url") or {}).get("resource") or "").strip()
        if rel.get("target-type") != "url" or not url.startswith(("https://", "http://")) or is_dead(url):
            continue
        key, _target = destination(url)
        first_url, kinds, _first = merged.setdefault(key, (url, [], rel))
        kind = rel.get("type") or "link"
        if kind not in kinds:
            kinds.append(kind)
    links = []
    for first_url, kinds, rel in merged.values():
        label, platform, priority = classify(first_url, kinds)
        detail = next((KIND_LABELS[k] for k in kinds if k in KIND_LABELS), None)
        scope = rel.get("_scope")
        target = None
        if scope:  # sin ID reconocible, el ámbito de MusicBrainz decide: grabación → pista; lanzamiento → lanzamiento
            target = destination(first_url)[1] or ("track" if scope == "recording" else "release")
        release_type = rel.get("_release_type") if target == "release" and scope == "release" else None
        formats = list(rel.get("_formats") or []) if scope == "release" else []
        links.append((priority, label, target != "track", schemas.Link(
            url=first_url, label=label, platform=platform, kinds=kinds, detail=detail if detail != label else None,
            primary=False, scope=scope, target=target, release_type=release_type, formats=formats)))
    links.sort(key=lambda x: (x[0], x[1].casefold(), x[2], x[3].url))  # en cada plataforma, la pista antes que el álbum
    out = [link for *_, link in links]
    seen_platforms: set[str] = set()
    for link in out:  # destacado: la primera URL de cada plataforma musical, hasta PRIMARY_MAX
        if link.platform and link.platform not in seen_platforms and len(seen_platforms) < PRIMARY_MAX:
            seen_platforms.add(link.platform)
            link.primary = True
    return out
