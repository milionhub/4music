"""Extrae datos de un cartel con un modelo multimodal de Groq (una llamada por cartel).

Uso (desde la raíz del repo):
    py -3.11 research/poster_ai/extract_poster.py research/poster_ai/data/posters/01_sencillo.jpg
    py -3.11 research/poster_ai/extract_poster.py <imagen> --dry-run   # valida la imagen; no llama a Groq
    py -3.11 research/poster_ai/extract_poster.py <imagen> --variant compact   # esquema compacto -> outputs/compact/

- La clave se lee de GROQ_API_KEY (entorno) o de research/music_sources/.env; nunca se imprime ni se guarda.
- No hay reintentos automáticos: cada llamada consume cuota. Si ya existe la salida, no se repite (--force).
- Presupuesto: como máximo MAX_CALLS llamadas registradas en data/outputs/_calls.jsonl (--budget para cambiarlo),
  compartido por todas las variantes.
- finish_reason "length" se trata como respuesta incompleta (error_kind "incomplete") aunque el JSON se pueda leer.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import socket
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from poster_schema import COMPACT_PROMPT, PROMPT, audit_extraction, parse_and_validate, parse_compact

ROOT = Path(__file__).resolve().parent
OUTPUTS = ROOT / "data" / "outputs"
ENV_FILE = ROOT.parent / "music_sources" / ".env"

API_URL = os.environ.get("POSTER_AI_API_URL", "https://api.groq.com/openai/v1/chat/completions")
MODEL = "qwen/qwen3.8-27b"          # preview; ver docs/fase-1-ia-carteles.md
MAX_CALLS = 5
TIMEOUT_S = 90
MAX_IMAGE_BYTES = 4 * 1024 * 1024   # prudente: la documentación solo fija 20 MB para imágenes por URL
FORMATS = {b"\xff\xd8\xff": "image/jpeg", b"\x89PNG\r\n\x1a\n": "image/png", b"RIFF": "image/webp"}
RATE_HEADERS = ("x-ratelimit-limit-requests", "x-ratelimit-remaining-requests", "x-ratelimit-reset-requests",
                "x-ratelimit-limit-tokens", "x-ratelimit-remaining-tokens", "x-ratelimit-reset-tokens",
                "retry-after")


class ImageError(ValueError):
    pass


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def check_image(path: Path) -> tuple[str, bytes]:
    if not path.is_file():
        raise ImageError(f"no existe el archivo: {path.name}")
    data = path.read_bytes()
    if not data:
        raise ImageError("archivo vacío")
    if len(data) > MAX_IMAGE_BYTES:
        raise ImageError(f"imagen de {len(data) / 1e6:.1f} MB; máximo {MAX_IMAGE_BYTES / 1e6:.1f} MB (redúcela antes)")
    for magic, mime in FORMATS.items():
        if data.startswith(magic) and (mime != "image/webp" or data[8:12] == b"WEBP"):
            return mime, data
    raise ImageError("formato no admitido (solo JPEG, PNG o WebP)")


def read_key() -> str:
    key = os.environ.get("GROQ_API_KEY", "").strip()
    if not key and ENV_FILE.exists():
        for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
            if line.startswith("GROQ_API_KEY="):
                key = line.split("=", 1)[1].strip()
    return key


VARIANTS = {"original": PROMPT, "compact": COMPACT_PROMPT}


def build_request(mime: str, data: bytes, variant: str = "original") -> dict:
    return {
        "model": MODEL,
        "messages": [{"role": "user", "content": [
            {"type": "text", "text": VARIANTS[variant]},
            {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{base64.b64encode(data).decode('ascii')}"}},
        ]}],
        "response_format": {"type": "json_object"},
        "temperature": 0,
        "reasoning_effort": "none",   # modo instruct: sin razonamiento oculto (menos tokens y latencia)
        "max_completion_tokens": 4096,
    }


def call_groq(payload: dict, key: str) -> dict:
    """Una sola petición. Devuelve un registro con estado, tiempos, consumo y contenido; nunca la clave."""
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(API_URL, data=body, method="POST", headers={
        "Authorization": f"Bearer {key}", "Content-Type": "application/json",
        "User-Agent": "music-discovery-research/0.4"})
    rec = {"status": None, "error_kind": None, "error": None, "rate_limit": {}, "latency_s": None}
    started = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
            rec["status"] = resp.status
            rec["rate_limit"] = {h: resp.headers.get(h) for h in RATE_HEADERS if resp.headers.get(h)}
            raw = resp.read()
        try:
            rec["response"] = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            rec["error_kind"], rec["error"] = "invalid_response", "la API no devolvió JSON"
    except urllib.error.HTTPError as exc:
        rec["status"] = exc.code
        rec["rate_limit"] = {h: exc.headers.get(h) for h in RATE_HEADERS if exc.headers and exc.headers.get(h)}
        rec["error_kind"] = {401: "auth", 403: "auth", 429: "rate_limit", 413: "too_large", 400: "bad_request"}.get(
            exc.code, "server_error" if exc.code >= 500 else "http_error")
        try:
            msg = json.loads(exc.read().decode("utf-8")).get("error", {}).get("message")
        except Exception:
            msg = None
        rec["error"] = f"HTTP {exc.code}" + (f": {msg[:300]}" if msg else "")
    except (socket.timeout, TimeoutError):
        rec["error_kind"], rec["error"] = "timeout", f"sin respuesta en {TIMEOUT_S} s"
    except (urllib.error.URLError, ConnectionError) as exc:
        rec["error_kind"], rec["error"] = "network", f"{exc.__class__.__name__}: {getattr(exc, 'reason', exc)}"
    rec["latency_s"] = round(time.monotonic() - started, 3)
    if key and key in json.dumps(rec):  # defensa: la clave nunca debe acabar en el registro
        raise RuntimeError("la clave aparece en el registro; se aborta sin guardar")
    return rec


def summarize(rec: dict, variant: str = "original") -> dict:
    out = {k: rec[k] for k in ("status", "error_kind", "error", "latency_s", "rate_limit")}
    resp = rec.get("response") or {}
    choice = (resp.get("choices") or [{}])[0]
    content = (choice.get("message") or {}).get("content")
    out.update({"variant": variant, "model_reported": resp.get("model"),
                "request_id": (resp.get("x_groq") or {}).get("id"),
                "finish_reason": choice.get("finish_reason"), "usage": resp.get("usage"), "raw_content": content})
    out["complete"] = out["finish_reason"] == "stop"
    if out["finish_reason"] == "length" and not out["error_kind"]:
        out["error_kind"] = "incomplete"
        out["error"] = "finish_reason=length: salida cortada por max_completion_tokens"
    if content is None:
        out.update({"extraction": None, "schema_errors": [], "json_valid": False, "review": []})
    elif variant == "compact":
        compact, errors, expanded, review = parse_compact(content)
        out.update({"compact_extraction": compact, "extraction": expanded, "schema_errors": errors,
                    "json_valid": compact is not None, "review": review})
    else:  # la extracción original se conserva tal cual; la auditoría solo informa
        parsed, errors = parse_and_validate(content)
        review = audit_extraction(parsed)[1] if isinstance(parsed, dict) and not errors else []
        out.update({"extraction": parsed, "schema_errors": errors, "json_valid": parsed is not None,
                    "review": review})
    return out


def calls_used() -> int:
    log = OUTPUTS / "_calls.jsonl"
    return len(log.read_text(encoding="utf-8").splitlines()) if log.exists() else 0


def main(argv: list[str] | None = None) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("image", type=Path)
    ap.add_argument("--dry-run", action="store_true", help="valida la imagen y la petición sin llamar a Groq")
    ap.add_argument("--force", action="store_true", help="repite aunque ya exista la salida")
    ap.add_argument("--budget", type=int, default=MAX_CALLS)
    ap.add_argument("--variant", choices=sorted(VARIANTS), default="original")
    args = ap.parse_args(argv)

    try:
        mime, data = check_image(args.image)
    except ImageError as exc:
        print(f"Imagen rechazada: {exc}", file=sys.stderr)
        return 2
    payload = build_request(mime, data, args.variant)
    out_dir = OUTPUTS if args.variant == "original" else OUTPUTS / args.variant
    out_file = out_dir / f"{args.image.stem}.json"
    print(f"{args.image.name}: {mime}, {len(data) / 1e6:.2f} MB; modelo {MODEL}; variante {args.variant}")
    if args.dry_run:
        print("dry-run: petición preparada, no se ha llamado a Groq")
        return 0
    if out_file.exists() and not args.force:
        print(f"Ya existe {out_file.relative_to(OUTPUTS.parent).as_posix()}; no se repite la llamada (usa --force)")
        return 0
    if calls_used() >= args.budget:
        print(f"Presupuesto agotado: {calls_used()} llamadas registradas (máximo {args.budget})", file=sys.stderr)
        return 3
    key = read_key()
    if not key:
        print("Falta GROQ_API_KEY (entorno o research/music_sources/.env)", file=sys.stderr)
        return 2

    rec = call_groq(payload, key)
    del key
    result = {"image": args.image.name, "image_bytes": len(data), "mime": mime, "model_requested": MODEL,
              "called_at": now_iso(), **summarize(rec, args.variant)}
    out_dir.mkdir(parents=True, exist_ok=True)
    with (OUTPUTS / "_calls.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({k: result[k] for k in ("called_at", "image", "variant", "status", "error_kind",
                                                    "latency_s", "usage")}, ensure_ascii=False) + "\n")
    if result["status"] == 200:
        out_file.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    else:
        (out_dir / f"{args.image.stem}.error.json").write_text(json.dumps(result, ensure_ascii=False, indent=1),
                                                                encoding="utf-8")
    usage = result.get("usage") or {}
    print(f"estado {result['status']} {result['error_kind'] or ''} | {result['latency_s']} s | "
          f"tokens {usage.get('prompt_tokens')}+{usage.get('completion_tokens')} | "
          f"JSON válido: {result['json_valid']} | completa: {result['complete']} | "
          f"errores de esquema: {len(result['schema_errors'])} | avisos de revisión: {len(result['review'])}")
    if result["error_kind"] == "incomplete":
        print(f"Respuesta incompleta: {result['error']}. No se reintenta.", file=sys.stderr)
        return 5
    if result["error_kind"] in ("auth", "rate_limit"):
        print(f"Detenido: {result['error']}. No se reintenta.", file=sys.stderr)
        return 4
    return 0 if result["status"] == 200 else 1


if __name__ == "__main__":
    sys.exit(main())
