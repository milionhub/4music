"""Clientes HTTP mínimos (biblioteca estándar) para MusicBrainz y Wikimedia (Wikidata + Commons).

- Cada proveedor tiene su candado: una petición cada `min_interval_s` como mínimo, para todo el proceso.
- Caché en memoria con TTL; si el proveedor falla y hay una copia caducada, se sirve marcada como `stale`.
- MusicBrainz devuelve 503 de forma intermitente (Fase 1.5 y T1.1): ante 503/429 se repite UNA sola vez,
  esperando `Retry-After` (máx. 3 s) o 1,5 s. Nunca más de un reintento.
"""

from __future__ import annotations

import json
import socket
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import OrderedDict
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable

MB_BASE_URL = "https://musicbrainz.org/ws/2"
LISTENBRAINZ_API = "https://api.listenbrainz.org/1"
WIKIDATA_API = "https://www.wikidata.org/w/api.php"
COMMONS_API = "https://commons.wikimedia.org/w/api.php"
MIN_INTERVAL_S = 1.1
TIMEOUT_S = 10.0
CACHE_TTL_S = 24 * 3600
CACHE_MAX_ENTRIES = 500
RETRY_STATUSES = {429, 503}
RETRY_DEFAULT_S = 1.5
RETRY_MAX_WAIT_S = 3.0
USER_AGENT = "music-discovery/0.1 ( {contact} )"

# (status, cuerpo, Retry-After en segundos o None)
Transport = Callable[[str, dict[str, str], float], tuple[int, bytes, float | None]]


class ProviderError(Exception):
    code = "provider_unavailable"


class NotConfigured(ProviderError):
    code = "provider_not_configured"


class NotFound(ProviderError):
    code = "not_found"


class Unavailable(ProviderError):
    code = "provider_unavailable"


class BadResponse(ProviderError):
    code = "provider_bad_response"


@dataclass(frozen=True)
class Fetched:
    data: dict[str, Any]
    url: str
    fetched_at: str
    stale: bool


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _default_transport(url: str, headers: dict[str, str], timeout: float) -> tuple[int, bytes, float | None]:
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read(), None
    except urllib.error.HTTPError as exc:
        retry_after = exc.headers.get("Retry-After") if exc.headers else None
        return exc.code, b"", float(retry_after) if retry_after and retry_after.isdigit() else None


class CachedJsonClient:
    """GET JSON con límite de ritmo, caché con TTL, copia caducada ante fallos y como mucho un reintento."""

    provider = "provider"
    extra_headers: dict[str, str] = {}  # nunca se registran ni se devuelven

    def __init__(self, contact: str, transport: Transport | None = None, clock: Callable[[], float] = time.monotonic,
                 sleep: Callable[[float], None] = time.sleep, min_interval_s: float = MIN_INTERVAL_S):
        self.contact = contact
        self._transport = transport or _default_transport
        self._clock = clock
        self._sleep = sleep
        self._min_interval_s = min_interval_s
        self._lock = threading.Lock()
        self._last_request: float | None = None
        self._cache: OrderedDict[str, tuple[float, Fetched]] = OrderedDict()

    def get(self, base: str, params: dict[str, str]) -> Fetched:
        if not self.contact:
            raise NotConfigured("Falta MUSICBRAINZ_CONTACT en el backend")
        url = f"{base}?{urllib.parse.urlencode(sorted(params.items()), quote_via=urllib.parse.quote)}"
        cached = self._cache.get(url)
        if cached and self._clock() - cached[0] < CACHE_TTL_S:
            return cached[1]
        try:
            fetched = self._fetch(url)
        except (Unavailable, BadResponse):
            if cached:  # el proveedor falla: se sirve la copia caducada, marcada
                old = cached[1]
                return Fetched(old.data, old.url, old.fetched_at, stale=True)
            raise
        self._cache[url] = (self._clock(), fetched)
        self._cache.move_to_end(url)
        while len(self._cache) > CACHE_MAX_ENTRIES:
            self._cache.popitem(last=False)
        return fetched

    def _request(self, url: str) -> tuple[int, bytes, float | None]:
        headers = {"User-Agent": USER_AGENT.format(contact=self.contact), "Accept": "application/json",
                   **self.extra_headers}
        if self._last_request is not None:
            wait = self._min_interval_s - (self._clock() - self._last_request)
            if wait > 0:
                self._sleep(wait)
        self._last_request = self._clock()
        try:
            return self._transport(url, headers, TIMEOUT_S)
        except (urllib.error.URLError, socket.timeout, TimeoutError, ConnectionError, OSError) as exc:
            raise Unavailable(f"Sin respuesta de {self.provider}: {exc.__class__.__name__}") from exc

    def _fetch(self, url: str) -> Fetched:
        with self._lock:  # serializa y espacia todas las peticiones del proceso a este proveedor
            status, body, retry_after = self._request(url)
            if status in RETRY_STATUSES:  # un único reintento cortés
                self._sleep(min(retry_after if retry_after is not None else RETRY_DEFAULT_S, RETRY_MAX_WAIT_S))
                status, body, _ = self._request(url)
        if status == 404:
            raise NotFound(f"{self.provider} no tiene esa entidad")
        if status == 429 or status >= 500:
            raise Unavailable(f"{self.provider} respondió HTTP {status}")
        if status != 200:
            raise BadResponse(f"{self.provider} respondió HTTP {status}")
        try:
            data = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise BadResponse(f"La respuesta de {self.provider} no es JSON") from exc
        if isinstance(data, list):  # ListenBrainz responde con una lista: se envuelve para un contrato uniforme
            data = {"items": data}
        if not isinstance(data, dict):
            raise BadResponse(f"Respuesta de {self.provider} con forma inesperada")
        return Fetched(data, url, _now_iso(), stale=False)


class MusicBrainzClient(CachedJsonClient):
    provider = "MusicBrainz"

    def search_artists(self, query: str, limit: int) -> Fetched:
        return self.get(f"{MB_BASE_URL}/artist", {"query": query, "limit": str(limit), "fmt": "json"})

    def artist(self, mbid: str) -> Fetched:
        """Artista con alias, URL y relaciones (CC0): con otros artistas, con sellos («label founder»…) y con eventos
        (actuaciones documentadas). Todo en una sola petición."""
        return self.get(f"{MB_BASE_URL}/artist/{mbid}", {"inc": "aliases+url-rels+artist-rels+label-rels+event-rels",
                                                        "fmt": "json"})

    def recordings(self, mbid: str) -> Fetched:
        return self.get(f"{MB_BASE_URL}/recording", {"artist": mbid, "inc": "artist-credits", "limit": "100", "fmt": "json"})

    def release_groups(self, mbid: str) -> Fetched:
        """Grupos de lanzamientos acreditados al artista (álbum, EP, single…), con su primera fecha de publicación."""
        return self.get(f"{MB_BASE_URL}/release-group", {"artist": mbid, "inc": "artist-credits", "limit": "100",
                                                         "fmt": "json"})


    def releases_with_labels(self, mbid: str) -> Fetched:
        """Lanzamientos del artista con sello y créditos (para sello compartido y lanzamientos conjuntos)."""
        return self.get(f"{MB_BASE_URL}/release", {"artist": mbid, "inc": "labels+artist-credits", "limit": "100",
                                                   "fmt": "json"})

    def label_releases(self, label_mbid: str) -> Fetched:
        """Una página (100) de lanzamientos de un sello con sus créditos: nunca el catálogo completo."""
        return self.get(f"{MB_BASE_URL}/release", {"label": label_mbid, "inc": "artist-credits", "limit": "100",
                                                   "fmt": "json"})

    # --- Canciones (TrackDNA, T2.0) ---
    def search_recordings(self, query: str, limit: int) -> Fetched:
        return self.get(f"{MB_BASE_URL}/recording", {"query": query, "limit": str(limit), "fmt": "json"})

    def recording(self, mbid: str) -> Fetched:
        """Grabación con ISRC, créditos (producción, remezcla…), relaciones con otras grabaciones, obra, URL y
        géneros curados (V5.2; los géneros de MusicBrainz son CC BY-NC-SA: solo con atribución y uso no comercial)."""
        return self.get(f"{MB_BASE_URL}/recording/{mbid}", {
            "inc": "artist-credits+isrcs+artist-rels+recording-rels+work-rels+work-level-rels+url-rels+genres",
            "fmt": "json"})

    def release_group_genres(self, mbid: str) -> Fetched:
        """Géneros curados de un grupo de lanzamientos (el EP o single original de una canción)."""
        return self.get(f"{MB_BASE_URL}/release-group/{mbid}", {"inc": "genres", "fmt": "json"})

    def recording_releases(self, mbid: str) -> Fetched:
        """Lanzamientos que contienen la grabación (100 como máximo) con sello, tipo, formato, portada disponible,
        barcode y enlaces (url-rels: tiendas, streaming, Bandcamp, Discogs…), en la misma petición."""
        return self.get(f"{MB_BASE_URL}/release", {"recording": mbid,
                                                   "inc": "labels+release-groups+artist-credits+media+url-rels",
                                                   "limit": "100", "fmt": "json"})


class LabsClient(CachedJsonClient):
    """ListenBrainz Labs (experimental, sin token): artistas similares por sesiones de escucha (Fase 1.5A)."""

    provider = "ListenBrainz Labs"
    URL = "https://labs.api.listenbrainz.org/similar-artists/json"
    # Algoritmo de la página de artista de listenbrainz.org (histórico) y variante de los últimos 5 años.
    ALGORITHMS = (
        "session_based_days_7500_session_300_contribution_3_threshold_10_limit_100_filter_True_skip_30",
        "session_based_days_1825_session_300_contribution_3_threshold_10_limit_100_filter_True_skip_30",
    )

    def similar_artists(self, mbid: str, algorithm: str) -> Fetched:
        return self.get(self.URL, {"artist_mbids": mbid, "algorithm": algorithm})


class WikimediaClient(CachedJsonClient):
    provider = "Wikimedia"

    def entity_claims(self, qid: str) -> Fetched:
        return self.get(WIKIDATA_API, {"action": "wbgetentities", "ids": qid,
                                       "props": "claims|sitelinks|labels|descriptions", "languages": "es|en",
                                       "format": "json"})

    def search_by_mbid(self, mbid: str) -> Fetched:
        """Ítems de Wikidata que declaran este MBID de artista (P434). La identidad se vuelve a verificar después."""
        return self.get(WIKIDATA_API, {"action": "query", "list": "search", "srsearch": f"haswbstatement:P434={mbid}",
                                       "srlimit": "3", "format": "json"})

    def search_statement(self, prop: str, value: str) -> Fetched:
        """Ítems que declaran `prop=value` (p. ej. P4404 grabación o P436 grupo de lanzamientos de MusicBrainz)."""
        return self.get(WIKIDATA_API, {"action": "query", "list": "search", "srsearch": f"haswbstatement:{prop}={value}",
                                       "srlimit": "3", "format": "json"})

    def commons_depicting(self, qid: str) -> Fetched:
        """Archivos de Commons cuyos datos estructurados declaran «representa» (P180) = ese ítem de Wikidata."""
        return self.get(COMMONS_API, {"action": "query", "list": "search", "srnamespace": "6",
                                      "srsearch": f"haswbstatement:P180={qid}", "srlimit": "5", "format": "json"})

    def commons_depicts(self, file_title: str) -> Fetched:
        """Datos estructurados (MediaInfo) de un archivo de Commons: qué ítems representa."""
        return self.get(COMMONS_API, {"action": "wbgetentities", "sites": "commonswiki", "titles": file_title,
                                      "format": "json"})

    def labels(self, qids: list[str]) -> Fetched:
        return self.get(WIKIDATA_API, {"action": "wbgetentities", "ids": "|".join(sorted(set(qids))[:50]),
                                       "props": "labels", "languages": "es|en", "format": "json"})

    def commons_file(self, filename: str, width: int) -> Fetched:
        return self.get(COMMONS_API, {
            "action": "query", "titles": f"File:{filename}", "prop": "imageinfo", "iiprop": "url|extmetadata",
            "iiurlwidth": str(width), "format": "json",
            "iiextmetadatafilter": "LicenseShortName|Artist|LicenseUrl|AttributionRequired",
        })


class ListenBrainzClient(CachedJsonClient):
    """Popularidad de ListenBrainz. Desde 2026 el endpoint exige un token de usuario (401 sin él, comprobado en
    T1.2): sin LISTENBRAINZ_TOKEN en backend/.env no se hace ninguna petición."""

    provider = "ListenBrainz"

    def __init__(self, contact: str, token: str, **kwargs):
        super().__init__(contact, **kwargs)
        self.token = token
        self.extra_headers = {"Authorization": f"Token {token}"} if token else {}

    def top_recordings(self, artist_mbid: str) -> Fetched:
        if not self.token:
            raise NotConfigured("ListenBrainz exige token (LISTENBRAINZ_TOKEN) para la popularidad")
        return self.get(f"{LISTENBRAINZ_API}/popularity/top-recordings-for-artist/{artist_mbid}", {})
