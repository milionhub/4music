"""Carteles (Fase 3.1): extracción con Groq Vision, saneado y auditoría determinista. Biblioteca estándar.

Trasladado de research/poster_ai/poster_schema.py (variante compacta de Fase 1.4, la única que completó SW38):
- El modelo solo propone. Aquí no se corrige ningún nombre ni se deduce nada; lo dudoso se anota en `review`.
- Una respuesta cortada (finish_reason length) se repara conservando solo los objetos completos (`complete=False`).
- La imagen no se guarda ni se registra: solo viaja a Groq dentro de la petición.
"""

from __future__ import annotations

import base64
import binascii
import json
import re
import threading
from datetime import date

from app import schemas
from app.groq_client import GroqClient

MAX_IMAGE_BYTES = 4 * 1024 * 1024  # tope prudente de Fase 1.4 (el límite real en base64 no está publicado)
MAX_KNOWN = 300
MAX_TEXT = 200
MAX_COLORS = 5

PROMPT = """You are reading a music event poster (festival or club night). Extract ONLY text that is visible in the image.

Return a single compact JSON object with exactly these keys, in this order:
{
  "event_name": string or null,
  "dates": [{"text": string, "iso": "YYYY-MM-DD" or null}],
  "location": string or null,
  "stages": [string],
  "colors": [string],
  "sessions": [{"date": {"text": string, "iso": "YYYY-MM-DD" or null} or null, "label": string or null, "stage": string or null, "time": string or null, "artists": [string]}],
  "artists": [{"name": string, "stage": string or null, "day": string or null}],
  "individual_times": [{"name": string, "time": string}],
  "b2b": [{"artists": [string], "text": string or null}],
  "uncertain": [string],
  "unreadable_text": [string]
}

Rules:
- Use only information visible in the poster. Do not invent artists, times, dates, stages or places.
- Do not complete or correct names using your music knowledge. Keep the original spelling, capitalisation and symbols as printed.
- Write each performer name ONCE per block, in the order printed. If the poster groups artists into blocks (by day, stage or time slot), put the names only inside "sessions" and leave "artists" as []. Otherwise leave "sessions" as [] and use "artists".
- Session "date.text" is the date exactly as printed for that block; session "time" is the time printed for the block (start time or range), or null.
- "individual_times": only when a time is printed next to that specific artist's name. A block start time is NOT an individual time. Usually this is [].
- "iso" only when day, month and year are printed in that same date text; a year printed elsewhere on the poster does not count. Otherwise null.
- "b2b": when names are joined by "B2B" (also across two lines), write each person as a separate name and add one "b2b" entry with their names in printed order and the printed text. A collective with members in brackets is ONE name, not a b2b.
- "uncertain": names that are only partly visible or hard to read (write what you can read). Never turn a partial name into a confident identification.
- "colors": 2 to 5 dominant colours of the poster artwork as "#RRGGBB".
- Logos of sponsors or promoters, venue logos and slogans are not artists unless presented as performers. Do not infer genres, running order or set length.
- Use null or [] when something is not present. "unreadable_text" only for text that exists but cannot be read.
"""

CONTINUE_PROMPT = """
This poster was already PARTLY read; the previous answer was cut off. Already extracted blocks: {sessions}.
Already extracted names: {names}.
Return the same JSON format, but in "sessions" and "artists" include ONLY blocks and names that are NOT listed above.
Still return every "b2b" and "uncertain" entry of the whole poster. Keep the answer short.
"""

REGION_PROMPT = """
This image is a CROPPED FRAGMENT of a larger poster. Extract only what is visible in this fragment.
Names cut by the edge of the fragment go to "uncertain" with the visible part only. Event name, dates and place only if visible here.
"""

_HEX = re.compile(r"^#[0-9a-fA-F]{6}$")
_ISO = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_NUM_DATE = re.compile(r"(?<!\d)(\d{1,2})[./-](\d{1,2})[./-](\d{2}|\d{4})(?!\d)")

_limit_lock = threading.Lock()
_daily: dict[str, int] = {}
_daily_day = ""


class PosterError(Exception):
    def __init__(self, status: int, code: str, message: str):
        super().__init__(message)
        self.status, self.code, self.message = status, code, message


def decode_image(data: str) -> tuple[bytes, str]:
    """base64 (con o sin prefijo data:) → (bytes, mime). Solo JPEG, PNG y WebP por sus bytes mágicos."""
    if data.startswith("data:"):
        data = data.split(",", 1)[-1]
    if len(data) > MAX_IMAGE_BYTES * 4 // 3 + 16:
        raise PosterError(413, "image_too_large", "La imagen supera 4 MB")
    try:
        raw = base64.b64decode(data, validate=True)
    except (binascii.Error, ValueError):
        raise PosterError(422, "invalid_image", "La imagen no es base64 válido") from None
    if not raw:
        raise PosterError(422, "invalid_image", "Imagen vacía")
    if len(raw) > MAX_IMAGE_BYTES:
        raise PosterError(413, "image_too_large", "La imagen supera 4 MB")
    if raw[:3] == b"\xff\xd8\xff":
        return raw, "image/jpeg"
    if raw[:8] == b"\x89PNG\r\n\x1a\n":
        return raw, "image/png"
    if raw[:4] == b"RIFF" and raw[8:12] == b"WEBP":
        return raw, "image/webp"
    raise PosterError(422, "unsupported_image", "Formato no admitido: usa JPEG, PNG o WebP")


def take_quota(client_id: str, limit: int) -> None:
    """Límite diario en memoria por cliente (se reinicia con el proceso o al cambiar de día)."""
    global _daily_day
    today = date.today().isoformat()
    with _limit_lock:
        if today != _daily_day:
            _daily.clear()
            _daily_day = today
        if _daily.get(client_id, 0) >= limit:
            raise PosterError(429, "poster_daily_limit", f"Has alcanzado el límite de {limit} análisis por hoy")
        _daily[client_id] = _daily.get(client_id, 0) + 1


def repair_json(text: str) -> object | None:
    """JSON completo, o el prefijo más largo que termina en un objeto/lista cerrados, con sus cierres añadidos."""
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        pass
    stack: list[str] = []
    safe: list[tuple[int, str]] = []
    in_str = esc = False
    for i, ch in enumerate(text):
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch in "{[":
            stack.append("}" if ch == "{" else "]")
        elif ch in "}]":
            if not stack:
                return None
            stack.pop()
            if stack:
                safe.append((i + 1, "".join(reversed(stack))))
    for end, closers in reversed(safe[-200:]):
        try:
            return json.loads(text[:end] + closers)
        except json.JSONDecodeError:
            continue
    return None


def _text(v: object) -> str | None:
    if not isinstance(v, str):
        return None
    v = " ".join(v.split())[:MAX_TEXT]
    return v or None


def _names(v: object) -> list[str]:
    out: list[str] = []
    for x in v if isinstance(v, list) else []:
        t = _text(x)
        if t and t not in out:
            out.append(t)
    return out


def _date(v: object) -> schemas.PosterDate | None:
    if not isinstance(v, dict) or not _text(v.get("text")):
        return None
    iso = v.get("iso") if isinstance(v.get("iso"), str) and _ISO.match(v["iso"]) else None
    return schemas.PosterDate(text=_text(v["text"]), iso=iso)


def sanitize(obj: object, mode: str, complete: bool, model: str) -> schemas.PosterExtraction:
    """Convierte la salida del modelo (posiblemente reparada) en el contrato. Descarta lo mal formado sin inventar."""
    if not isinstance(obj, dict):
        raise PosterError(502, "poster_ai_bad_response", "La IA no devolvió un objeto JSON")
    review: list[schemas.PosterReview] = []
    sessions = []
    for i, s in enumerate(obj.get("sessions") if isinstance(obj.get("sessions"), list) else []):
        if not isinstance(s, dict) or not isinstance(s.get("artists"), list):
            review.append(schemas.PosterReview(field="sessions", value=str(i), action="descartado",
                                               reason="bloque incompleto o mal formado"))
            continue
        names = _names(s["artists"])
        if names:
            sessions.append(schemas.PosterSession(date=_date(s.get("date")), label=_text(s.get("label")),
                                                  stage=_text(s.get("stage")), time=_text(s.get("time")), artists=names))
    artists = []
    for a in obj.get("artists") if isinstance(obj.get("artists"), list) else []:
        name = _text(a.get("name")) if isinstance(a, dict) else _text(a)
        if name:
            artists.append(schemas.PosterArtistRow(name=name, stage=_text(a.get("stage")) if isinstance(a, dict) else None,
                                                   day=_text(a.get("day")) if isinstance(a, dict) else None))
    times = [schemas.PosterTime(name=_text(t["name"]), time=_text(t["time"]))
             for t in (obj.get("individual_times") if isinstance(obj.get("individual_times"), list) else [])
             if isinstance(t, dict) and _text(t.get("name")) and _text(t.get("time"))]
    b2b = []
    for b in obj.get("b2b") if isinstance(obj.get("b2b"), list) else []:
        names = _names(b.get("artists")) if isinstance(b, dict) else []
        if len(names) >= 2:
            b2b.append(schemas.PosterB2B(artists=names, text=_text(b.get("text"))))
    colors = [c.upper() for c in _names(obj.get("colors")) if _HEX.match(c)][:MAX_COLORS]
    ext = schemas.PosterExtraction(
        mode=mode, complete=complete, model=model, event_name=_text(obj.get("event_name")),
        dates=[d for d in (_date(x) for x in (obj.get("dates") if isinstance(obj.get("dates"), list) else [])) if d],
        location=_text(obj.get("location")), stages=_names(obj.get("stages")), colors=colors, sessions=sessions,
        artists=artists, individual_times=times, b2b=b2b, uncertain=_names(obj.get("uncertain")),
        unreadable_text=_names(obj.get("unreadable_text")), review=review)
    return audit(ext)


def year_printed(text: str, iso: str) -> bool:
    """El año de `iso` está impreso en esa misma fecha: «2026» suelto, o «10.09.26» con el mismo día y mes. Una fecha
    imposible (31 de febrero) no cuenta. Un año de otra parte del cartel (cabecera, «IBIZA26») tampoco."""
    try:
        d = date.fromisoformat(iso)
    except ValueError:
        return False
    if re.search(rf"(?<!\d){d.year}(?!\d)", text):
        return True
    return any(y[-2:] == iso[2:4] and {int(a), int(b)} == {d.day, d.month} for a, b, y in _NUM_DATE.findall(text))


def audit(ext: schemas.PosterExtraction) -> schemas.PosterExtraction:
    """Auditoría de Fase 1.4 sobre el esquema compacto:
    - Hora individual igual a la de su bloque o repetida en varios artistas del bloque → se descarta. Los miembros de
      un mismo B2B comparten su hora: cuentan como uno.
    - Fecha ISO cuyo año no está impreso en su propio texto → iso = null.
    """
    block_of: dict[str, int] = {}
    for i, s in enumerate(ext.sessions):
        for name in s.artists:
            block_of.setdefault(name.casefold(), i)
    pair_of = {n.casefold(): j for j, b in enumerate(ext.b2b) for n in b.artists}

    def unit(name: str) -> object:
        return pair_of.get(name.casefold(), name.casefold())

    per_block: dict[tuple[int, str], set[object]] = {}
    for t in ext.individual_times:
        i = block_of.get(t.name.casefold())
        if i is not None:
            per_block.setdefault((i, t.time), set()).add(unit(t.name))
    kept = []
    for t in ext.individual_times:
        i = block_of.get(t.name.casefold())
        reason = None
        if i is not None and ext.sessions[i].time and t.time.strip() == ext.sessions[i].time.strip():
            reason = "igual a la hora de inicio de su bloque"
        elif i is not None and len(per_block[(i, t.time)]) > 1:
            reason = "misma hora repetida en varios artistas del bloque"
        if reason:
            ext.review.append(schemas.PosterReview(field="individual_times", value=f"{t.name} {t.time}",
                                                   action="descartado", reason=reason))
        else:
            kept.append(t)
    ext.individual_times = kept
    for d in list(ext.dates) + [s.date for s in ext.sessions if s.date]:
        if d.iso and not year_printed(d.text, d.iso):
            ext.review.append(schemas.PosterReview(field="iso", value=f"{d.text} → {d.iso}", action="descartado",
                                                   reason="año no impreso en esa fecha"))
            d.iso = None
    if not ext.complete:
        ext.review.append(schemas.PosterReview(field="respuesta", action="reparado",
                                               reason="respuesta cortada: solo se conservan los bloques completos"))
    return ext


def build_prompt(req: schemas.PosterAnalyzeRequest) -> str:
    if req.mode == "continue":
        sessions = json.dumps([_text(s) for s in req.known_sessions[:MAX_KNOWN] if _text(s)], ensure_ascii=False)
        names = json.dumps([_text(n) for n in req.known_names[:MAX_KNOWN] if _text(n)], ensure_ascii=False)
        return PROMPT + CONTINUE_PROMPT.format(sessions=sessions, names=names)
    if req.mode == "region":
        return PROMPT + REGION_PROMPT
    return PROMPT


def analyze(req: schemas.PosterAnalyzeRequest, groq: GroqClient, model: str) -> schemas.PosterExtraction:
    """Una única llamada a Groq (sin reintentos). Lanza PosterError o GroqError."""
    raw, mime = decode_image(req.image)
    text, complete, usage = groq.vision(model, build_prompt(req), base64.b64encode(raw).decode("ascii"), mime)
    obj = repair_json(text)
    if obj is None:
        raise PosterError(502, "poster_ai_bad_response", "La IA devolvió una respuesta ilegible")
    ext = sanitize(obj, req.mode, complete, model)
    ext.usage = schemas.PosterUsage(**usage) if usage else None
    return ext
