"""Cliente HTTP mínimo (solo biblioteca estándar) para el experimento de cobertura.

- Límite de ritmo por host (intervalo mínimo entre peticiones).
- Presupuesto máximo de peticiones de red por fuente.
- Caché en disco: cada respuesta original se guarda tal cual (datos originales),
  de modo que repetir el experimento no repite peticiones.
- Reintentos acotados ante 429/503/5xx/timeouts, respetando Retry-After.
- El registro de peticiones nunca incluye cabeceras (User-Agent con contacto,
  tokens): solo URL, estado, tiempos y errores.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import socket
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

RETRY_STATUSES = {429, 500, 502, 503, 504}


class BudgetExceeded(RuntimeError):
    pass


@dataclass
class SourcePolicy:
    name: str
    min_interval_s: float
    max_requests: int
    headers: dict[str, str] = field(default_factory=dict)  # nunca se registran
    timeout_s: float = 20.0
    max_attempts: int = 3


@dataclass
class FetchResult:
    url: str
    ok: bool
    status: int | None
    data: object | None
    error: str | None
    from_cache: bool
    cache_file: str | None


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class HttpClient:
    def __init__(self, cache_dir: Path, log_path: Path, refresh: bool = False):
        self.cache_dir = cache_dir
        self.log_path = log_path
        self.refresh = refresh
        self.policies: dict[str, SourcePolicy] = {}
        self.network_requests: dict[str, int] = {}
        self.last_request_at: dict[str, float] = {}
        self.session_seen: set[str] = set()
        log_path.parent.mkdir(parents=True, exist_ok=True)

    def register(self, policy: SourcePolicy) -> None:
        self.policies[policy.name] = policy
        self.network_requests.setdefault(policy.name, 0)

    @staticmethod
    def build_url(base: str, params: dict[str, str] | None = None) -> str:
        if not params:
            return base
        # Orden estable para que la misma consulta produzca la misma clave de caché.
        return base + "?" + urllib.parse.urlencode(sorted(params.items()), quote_via=urllib.parse.quote)

    def _cache_file(self, source: str, url: str) -> Path:
        digest = hashlib.sha256(url.encode("utf-8")).hexdigest()[:24]
        return self.cache_dir / source / f"{digest}.json"

    def _log(self, entry: dict) -> None:
        with self.log_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def _wait_turn(self, source: str, policy: SourcePolicy) -> None:
        last = self.last_request_at.get(source)
        if last is not None:
            delay = policy.min_interval_s - (time.monotonic() - last)
            if delay > 0:
                time.sleep(delay)
        self.last_request_at[source] = time.monotonic()

    def get_json(self, source: str, url: str) -> FetchResult:
        policy = self.policies[source]
        cache_file = self._cache_file(source, url)
        rel_cache = cache_file.relative_to(self.cache_dir.parent).as_posix()

        if cache_file.exists() and not (self.refresh and url not in self.session_seen):
            stored = json.loads(cache_file.read_text(encoding="utf-8"))
            self.session_seen.add(url)
            self._log({"at": now_iso(), "source": source, "url": url, "from_cache": True,
                       "status": stored.get("status")})
            return FetchResult(url, stored["status"] == 200, stored["status"], stored.get("body"),
                               stored.get("error"), True, rel_cache)

        status: int | None = None
        error: str | None = None
        body: object | None = None
        for attempt in range(1, policy.max_attempts + 1):
            if self.network_requests[source] >= policy.max_requests:
                raise BudgetExceeded(f"{source}: presupuesto de {policy.max_requests} peticiones agotado")
            self._wait_turn(source, policy)
            self.network_requests[source] += 1
            started_at = datetime.now(timezone.utc).isoformat(timespec="milliseconds")
            started = time.monotonic()
            retry_after: float | None = None
            try:
                req = urllib.request.Request(url, headers={"Accept": "application/json",
                                                           "Accept-Encoding": "gzip", **policy.headers})
                with urllib.request.urlopen(req, timeout=policy.timeout_s) as resp:
                    status = resp.status
                    raw = resp.read()
                    if resp.headers.get("Content-Encoding") == "gzip":
                        raw = gzip.decompress(raw)
                try:
                    body = json.loads(raw.decode("utf-8"))
                    error = None
                except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                    error = f"respuesta no JSON: {exc.__class__.__name__}"
                    body = None
            except urllib.error.HTTPError as exc:
                status = exc.code
                error = f"HTTP {exc.code}"
                ra = exc.headers.get("Retry-After") if exc.headers else None
                if ra and ra.isdigit():
                    retry_after = float(ra)
                try:
                    body = json.loads(exc.read().decode("utf-8"))
                except Exception:
                    body = None
            except (urllib.error.URLError, socket.timeout, TimeoutError, ConnectionError) as exc:
                status = None
                error = f"error de red: {exc.__class__.__name__}: {getattr(exc, 'reason', exc)}"
            elapsed = round(time.monotonic() - started, 3)
            self._log({"at": now_iso(), "source": source, "url": url, "from_cache": False,
                       "started_at": started_at, "started_mono": round(started, 3),
                       "attempt": attempt, "status": status, "elapsed_s": elapsed, "error": error})

            retryable = status in RETRY_STATUSES or status is None
            if not retryable or attempt == policy.max_attempts:
                break
            time.sleep(min(retry_after if retry_after is not None else 2.0 * attempt, 30.0))

        # Se cachean éxitos y errores definitivos de cliente (p. ej. 404, 400),
        # no los fallos transitorios, para que una repetición los reintente.
        if status is not None and (status == 200 or 400 <= status < 500 and status != 429):
            cache_file.parent.mkdir(parents=True, exist_ok=True)
            cache_file.write_text(json.dumps({"url": url, "fetched_at": now_iso(), "status": status,
                                              "error": error, "body": body}, ensure_ascii=False, indent=1),
                                  encoding="utf-8")
        else:
            rel_cache = None
        self.session_seen.add(url)
        return FetchResult(url, status == 200 and error is None, status, body, error, False, rel_cache)
