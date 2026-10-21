"""Cliente mínimo de Groq (API compatible con OpenAI), solo en el backend. Biblioteca estándar.

- La clave se lee del entorno (GROQ_API_KEY en backend/.env); nunca se registra, devuelve ni guarda.
- Salida estructurada estricta (json_schema) para gpt-oss; timeout corto y como mucho un reintento ante 429/503.
- Un semáforo limita las generaciones simultáneas para respetar los límites del plan gratuito.
"""

from __future__ import annotations

import json
import socket
import threading
import time
import urllib.error
import urllib.request
from typing import Any, Callable

API_URL = "https://api.groq.com/openai/v1/chat/completions"
TIMEOUT_S = 25.0
MAX_WAIT_RETRY_S = 5.0
MAX_CONCURRENT = 2


class GroqError(Exception):
    def __init__(self, code: str, message: str, retry_after: float | None = None):
        super().__init__(message)
        self.code = code  # not_configured | rate_limited | unavailable | bad_response | incomplete
        self.retry_after = retry_after  # segundos indicados por Groq (Retry-After), si los hay


Transport = Callable[[str, dict[str, str], bytes, float], tuple[int, bytes, float | None]]


def _default_transport(url: str, headers: dict[str, str], body: bytes, timeout: float) -> tuple[int, bytes, float | None]:
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read(), None
    except urllib.error.HTTPError as exc:
        ra = exc.headers.get("retry-after") if exc.headers else None
        try:
            wait = float(ra) if ra else None
        except ValueError:
            wait = None
        try:
            detail = exc.read(2000)  # cuerpo del error de Groq (no contiene la clave): permite distinguir causas
        except OSError:
            detail = b""
        return exc.code, detail, wait


def _json_failure(raw: bytes) -> bool:
    """Groq no pudo producir o validar el JSON (json_validate_failed / «Failed to generate JSON»)."""
    return b"json_validate_failed" in raw or b"Failed to generate JSON" in raw or b"Failed to validate JSON" in raw


class GroqClient:
    def __init__(self, api_key: str, model: str, transport: Transport | None = None,
                 sleep: Callable[[float], None] = time.sleep):
        self._key = api_key
        self.model = model
        self._transport = transport or _default_transport
        self._sleep = sleep
        self._slots = threading.BoundedSemaphore(MAX_CONCURRENT)

    @property
    def configured(self) -> bool:
        return bool(self._key and self.model)

    def structured(self, system: str, user: str, schema_name: str, schema: dict[str, Any],
                   max_tokens: int = 3000) -> dict[str, Any]:
        """Devuelve el objeto JSON validado por el esquema estricto. Lanza GroqError (nunca con la clave)."""
        if not self.configured:
            raise GroqError("not_configured", "Groq no está configurado (GROQ_API_KEY / GROQ_MODEL)")
        def payload(response_format: dict[str, Any], prompt: str) -> bytes:
            return json.dumps({
                "model": self.model,
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
                "temperature": 0.4,
                "max_completion_tokens": max_tokens,
                "response_format": response_format,
                # gpt-oss razona antes de responder: con esfuerzo bajo no agota el presupuesto antes de escribir
                # el JSON (generación vacía observada en T1.5); el razonamiento no se devuelve.
                "reasoning_effort": "low",
                "include_reasoning": False,
            }).encode("utf-8")

        body = payload({"type": "json_schema", "json_schema": {"name": schema_name, "strict": True, "schema": schema}},
                       user)
        headers = {"Authorization": f"Bearer {self._key}", "Content-Type": "application/json",
                   "User-Agent": "music-discovery/0.1"}
        if not self._slots.acquire(timeout=TIMEOUT_S):
            raise GroqError("rate_limited", "Demasiadas generaciones simultáneas")
        try:
            status, raw, retry_after = self._call(headers, body)
            if status in (429, 503) and (retry_after is None or retry_after <= MAX_WAIT_RETRY_S):
                self._sleep(min(retry_after if retry_after is not None else 2.0, MAX_WAIT_RETRY_S))
                status, raw, retry_after = self._call(headers, body)
            if status == 400 and _json_failure(raw):
                # La decodificación estricta falló (observado en T1.5 con Dom Dolla): un único reintento en modo
                # json_object. El resultado se valida igual después (Pydantic + reglas editoriales).
                keys = ", ".join(f"'{k}'" for k in schema.get("properties", {}))
                fallback = payload({"type": "json_object"},
                                   f"{user}\n\nResponde SOLO con un objeto JSON con las claves {keys}.")
                status, raw, retry_after = self._call(headers, fallback)
                if status == 400 and _json_failure(raw):
                    raise GroqError("json_generation_failed", "Groq no pudo generar JSON válido")
        finally:
            self._slots.release()
        if status == 429:
            raise GroqError("rate_limited", "Límite de Groq alcanzado", retry_after)
        if status == 503:
            raise GroqError("unavailable", "Groq no disponible", retry_after)
        if status in (401, 403):
            raise GroqError("not_configured", "Groq rechazó la autenticación")
        if status != 200:
            raise GroqError(f"http_{status}", f"Groq respondió HTTP {status}")  # código exacto para diagnosticar
        try:
            choice = json.loads(raw.decode("utf-8"))["choices"][0]
            if choice.get("finish_reason") == "length":
                raise GroqError("incomplete", "Respuesta cortada por longitud")
            content = choice["message"]["content"]
            data = json.loads(content)
        except GroqError:
            raise
        except (KeyError, IndexError, TypeError, ValueError, UnicodeDecodeError) as exc:
            raise GroqError("bad_response", "Respuesta de Groq con formato inesperado") from exc
        if not isinstance(data, dict):
            raise GroqError("bad_response", "Respuesta de Groq con formato inesperado")
        return data

    def _call(self, headers: dict[str, str], body: bytes) -> tuple[int, bytes, float | None]:
        try:
            return self._transport(API_URL, headers, body, TIMEOUT_S)
        except (urllib.error.URLError, socket.timeout, TimeoutError, ConnectionError, OSError) as exc:
            raise GroqError("unavailable", f"Sin respuesta de Groq: {exc.__class__.__name__}") from exc
