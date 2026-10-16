"""Esquema de extracción de carteles, validación (sin dependencias) y prompt multimodal."""

from __future__ import annotations

import json
import re

# Ejemplo del esquema. Cada campo conserva el texto tal como se ve en el cartel.
SCHEMA_EXAMPLE = {
    "event_name": None,                 # str | null
    "dates": [                          # fechas visibles
        {"text": "SAT 12 JULY 2025", "iso": "2025-07-12"},  # iso solo si día, mes y año son visibles
    ],
    "location": None,                   # str | null: recinto/ciudad tal como aparece
    "stages": [],                       # nombres de escenarios visibles
    "artists": [
        {"name": "Nombre leído", "stage": None, "day": None, "time": None, "uncertain": False},
    ],
    "unreadable_text": [],              # descripciones de zonas con texto que existe pero no se puede leer
    # Opcional (Fase 1.4, carteles con programación): bloques que agrupan artistas por fecha/escenario/hora.
    "sessions": [
        {"date": {"text": "03.09", "iso": None}, "label": "THURSDAY NIGHTTIME", "stage": "1",
         "time": "22:00", "artists": ["Nombre leído"]},
    ],
    # Opcional: actuaciones conjuntas impresas (B2B). Cada miembro figura también en "artists" por separado.
    "b2b": [
        {"artists": ["Nombre A", "Nombre B"], "text": "NOMBRE A B2B NOMBRE B"},
    ],
}

PROMPT = """You are reading a music event poster (festival or club night). Extract ONLY text that is visible in the image.

Return a single JSON object with exactly these keys:
{
  "event_name": string or null,
  "dates": [{"text": string, "iso": "YYYY-MM-DD" or null}],
  "location": string or null,
  "stages": [string],
  "artists": [{"name": string, "stage": string or null, "day": string or null, "time": string or null, "uncertain": boolean}],
  "unreadable_text": [string],
  "sessions": [{"date": {"text": string, "iso": "YYYY-MM-DD" or null} or null, "label": string or null, "stage": string or null, "time": string or null, "artists": [string]}],
  "b2b": [{"artists": [string], "text": string or null}]
}

Rules:
- Use only information visible in the poster. Do not invent artists, times, dates, stages or places.
- Do not complete or correct names using your music knowledge. Keep the original spelling, capitalisation and symbols as printed.
- If a name is only partly visible or hard to read, write what you can read and set "uncertain": true. Never turn a partial name into a confident identification.
- "iso" only when day, month and year are all visible; otherwise null. Keep the printed date in "text".
- "stage", "day" and "time" only when the poster links them to that artist; otherwise null.
- Use null or [] when something is not present. Use "unreadable_text" only for text that exists but cannot be read (describe where it is, e.g. "small print at bottom").
- Do not infer music genres. Do not add confidence scores or any other keys.
- Logos of sponsors or promoters are not artists unless presented as performers.
- "sessions": only when the poster groups artists into blocks (by day, stage or time slot); otherwise []. Session "time" is the time printed for the block (start time or range). An artist's own "time" is null unless a time is printed next to that artist: never infer running order, set length or individual times.
- "b2b": when names are joined by "B2B" (also across two lines), list EACH person as a separate entry in "artists" (and in the session's "artists"), and add one "b2b" entry with their names in printed order and the printed text. Do not infer who plays first, set length or individual times. A collective with members in brackets is ONE artist, not a b2b. Otherwise [].
"""

DATE_ISO = re.compile(r"^\d{4}-\d{2}-\d{2}$")
KEYS = set(SCHEMA_EXAMPLE)
OPTIONAL_KEYS = {"sessions", "b2b"}  # ampliación compatible: salidas sin "sessions" siguen siendo válidas
ARTIST_KEYS = {"name", "stage", "day", "time", "uncertain"}
SESSION_KEYS = {"date", "label", "stage", "time", "artists"}
B2B_KEYS = {"artists", "text"}


def _str_or_null(v) -> bool:
    return v is None or isinstance(v, str)


def validate(obj) -> list[str]:
    """Devuelve la lista de errores de estructura (vacía si es válido)."""
    if not isinstance(obj, dict):
        return ["la raíz no es un objeto JSON"]
    errors = []
    missing, extra = KEYS - OPTIONAL_KEYS - set(obj), set(obj) - KEYS
    if missing:
        errors.append(f"faltan claves: {sorted(missing)}")
    if extra:
        errors.append(f"claves no previstas: {sorted(extra)}")
    if not _str_or_null(obj.get("event_name")):
        errors.append("event_name debe ser string o null")
    if not _str_or_null(obj.get("location")):
        errors.append("location debe ser string o null")
    for key in ("dates", "stages", "artists", "unreadable_text"):
        if key in obj and not isinstance(obj[key], list):
            errors.append(f"{key} debe ser una lista")
    for i, d in enumerate(obj.get("dates") or [] if isinstance(obj.get("dates"), list) else []):
        if not isinstance(d, dict) or not isinstance(d.get("text"), str):
            errors.append(f"dates[{i}] necesita 'text' string")
        elif d.get("iso") is not None and not (isinstance(d["iso"], str) and DATE_ISO.match(d["iso"])):
            errors.append(f"dates[{i}].iso debe ser YYYY-MM-DD o null")
    for key in ("stages", "unreadable_text"):
        if isinstance(obj.get(key), list) and not all(isinstance(x, str) for x in obj[key]):
            errors.append(f"{key} debe contener strings")
    for i, a in enumerate(obj.get("artists") or [] if isinstance(obj.get("artists"), list) else []):
        if not isinstance(a, dict):
            errors.append(f"artists[{i}] no es un objeto")
            continue
        if not isinstance(a.get("name"), str) or not a["name"].strip():
            errors.append(f"artists[{i}].name vacío o no string")
        for k in ("stage", "day", "time"):
            if not _str_or_null(a.get(k)):
                errors.append(f"artists[{i}].{k} debe ser string o null")
        if not isinstance(a.get("uncertain"), bool):
            errors.append(f"artists[{i}].uncertain debe ser booleano")
        if set(a) - ARTIST_KEYS:
            errors.append(f"artists[{i}] claves no previstas: {sorted(set(a) - ARTIST_KEYS)}")
    sessions = obj.get("sessions", [])
    if not isinstance(sessions, list):
        errors.append("sessions debe ser una lista")
        sessions = []
    for i, ses in enumerate(sessions):
        if not isinstance(ses, dict):
            errors.append(f"sessions[{i}] no es un objeto")
            continue
        d = ses.get("date")
        if d is not None and (not isinstance(d, dict) or not isinstance(d.get("text"), str)
                              or (d.get("iso") is not None
                                  and not (isinstance(d["iso"], str) and DATE_ISO.match(d["iso"])))):
            errors.append(f"sessions[{i}].date debe ser null o {{text, iso YYYY-MM-DD|null}}")
        for k in ("label", "stage", "time"):
            if not _str_or_null(ses.get(k)):
                errors.append(f"sessions[{i}].{k} debe ser string o null")
        if not isinstance(ses.get("artists"), list) or not all(isinstance(x, str) for x in ses["artists"]):
            errors.append(f"sessions[{i}].artists debe ser una lista de strings")
        if set(ses) - SESSION_KEYS:
            errors.append(f"sessions[{i}] claves no previstas: {sorted(set(ses) - SESSION_KEYS)}")
    b2b = obj.get("b2b", [])
    if not isinstance(b2b, list):
        errors.append("b2b debe ser una lista")
        b2b = []
    for i, b in enumerate(b2b):
        if not isinstance(b, dict):
            errors.append(f"b2b[{i}] no es un objeto")
            continue
        names = b.get("artists")
        if not isinstance(names, list) or len(names) < 2 or not all(isinstance(x, str) and x.strip() for x in names):
            errors.append(f"b2b[{i}].artists debe ser una lista de 2 o más nombres")
        if not _str_or_null(b.get("text")):
            errors.append(f"b2b[{i}].text debe ser string o null")
        if set(b) - B2B_KEYS:
            errors.append(f"b2b[{i}] claves no previstas: {sorted(set(b) - B2B_KEYS)}")
    return errors


def parse_and_validate(text: str) -> tuple[object | None, list[str]]:
    try:
        obj = json.loads(text)
    except (json.JSONDecodeError, TypeError) as exc:
        return None, [f"JSON inválido: {exc.__class__.__name__}"]
    return obj, validate(obj)


# --- Variante compacta (Fase 1.4, carteles grandes) -------------------------------------------------
# Cada nombre aparece UNA sola vez: dentro de su sesión si el cartel tiene bloques, o en "artists" si no.
# Las horas individuales van aparte y solo si están impresas junto al nombre. expand_compact() la convierte
# de forma determinista al esquema original para reutilizar el evaluador y las referencias.

COMPACT_PROMPT = """You are reading a music event poster (festival or club night). Extract ONLY text that is visible in the image.

Return a single compact JSON object with exactly these keys:
{
  "event_name": string or null,
  "dates": [{"text": string, "iso": "YYYY-MM-DD" or null}],
  "location": string or null,
  "stages": [string],
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
- Write each performer name ONCE. If the poster groups artists into blocks (by day, stage or time slot), put the names only inside "sessions" and leave "artists" as []. Otherwise leave "sessions" as [] and use "artists".
- Session "date.text" is the date exactly as printed for that block; session "time" is the time printed for the block (start time or range), or null.
- "individual_times": only when a time is printed next to that specific artist's name. A block start time is NOT an individual time. Usually this is [].
- "iso" only when day, month and year are printed in that same date text; a year printed elsewhere on the poster does not count. Otherwise null.
- "b2b": when names are joined by "B2B" (also across two lines), write each person as a separate name and add one "b2b" entry with their names in printed order and the printed text. A collective with members in brackets is ONE name, not a b2b.
- "uncertain": names that are only partly visible or hard to read (write what you can read). Never turn a partial name into a confident identification.
- Logos of sponsors or promoters are not artists unless presented as performers. Do not infer genres, running order or set length.
- Use null or [] when something is not present. "unreadable_text" only for text that exists but cannot be read.
"""

COMPACT_KEYS = {"event_name", "dates", "location", "stages", "sessions", "artists", "individual_times", "b2b",
                "uncertain", "unreadable_text"}
COMPACT_ARTIST_KEYS = {"name", "stage", "day"}


def validate_compact(obj) -> list[str]:
    """Errores de estructura de la variante compacta (vacía si es válida)."""
    if not isinstance(obj, dict):
        return ["la raíz no es un objeto JSON"]
    errors = []
    missing, extra = COMPACT_KEYS - set(obj), set(obj) - COMPACT_KEYS
    if missing:
        errors.append(f"faltan claves: {sorted(missing)}")
    if extra:
        errors.append(f"claves no previstas: {sorted(extra)}")
    for key in ("artists", "individual_times", "uncertain"):
        if key in obj and not isinstance(obj[key], list):
            errors.append(f"{key} debe ser una lista")
    for i, a in enumerate(obj.get("artists") if isinstance(obj.get("artists"), list) else []):
        if not isinstance(a, dict) or not isinstance(a.get("name"), str) or not a["name"].strip():
            errors.append(f"artists[{i}] necesita 'name' string no vacío")
            continue
        if not all(_str_or_null(a.get(k)) for k in ("stage", "day")):
            errors.append(f"artists[{i}].stage/day debe ser string o null")
        if set(a) - COMPACT_ARTIST_KEYS:
            errors.append(f"artists[{i}] claves no previstas: {sorted(set(a) - COMPACT_ARTIST_KEYS)}")
    for i, t in enumerate(obj.get("individual_times") if isinstance(obj.get("individual_times"), list) else []):
        if not isinstance(t, dict) or not isinstance(t.get("name"), str) or not isinstance(t.get("time"), str) \
                or set(t) - {"name", "time"}:
            errors.append(f"individual_times[{i}] debe ser {{name, time}} con strings")
    if isinstance(obj.get("uncertain"), list) and not all(isinstance(x, str) for x in obj["uncertain"]):
        errors.append("uncertain debe contener strings")
    # El resto de claves comparte formato con el esquema original: se reutiliza su validador.
    shared = {k: obj[k] for k in ("event_name", "dates", "location", "stages", "unreadable_text", "sessions", "b2b")
              if k in obj}
    errors += [e for e in validate({**shared, "artists": []}) if not e.startswith("faltan claves")]
    return errors


def _year_printed(date: dict) -> bool:
    return bool(date.get("iso")) and date["iso"][:4] in (date.get("text") or "")


def audit_extraction(ext: dict) -> tuple[dict, list[dict]]:
    """Validación determinista sobre el esquema original. Devuelve (extracción depurada, avisos para revisión).

    - Hora individual igual a la hora de inicio de su sesión, o repetida en varios artistas del mismo bloque:
      no hay evidencia de horario individual -> se descarta (time = null).
    - Fecha con iso cuyo año no está impreso en su propio texto -> iso = null.
    """
    ext = json.loads(json.dumps(ext))  # copia profunda; el original no se toca
    review = []
    sessions = [s for s in ext.get("sessions") or [] if isinstance(s, dict)]
    block_of = {}
    for i, s in enumerate(sessions):
        for name in s.get("artists") or []:
            if isinstance(name, str):
                block_of.setdefault(name.casefold(), i)
    artists = [a for a in ext.get("artists") or [] if isinstance(a, dict)]
    per_block: dict[tuple, int] = {}
    for a in artists:
        i = block_of.get(str(a.get("name", "")).casefold())
        if a.get("time") and i is not None:
            per_block[(i, a["time"])] = per_block.get((i, a["time"]), 0) + 1
    for a in artists:
        if not a.get("time"):
            continue
        i = block_of.get(str(a.get("name", "")).casefold())
        reason = None
        if i is not None and sessions[i].get("time") and a["time"].strip() == sessions[i]["time"].strip():
            reason = "igual a la hora de inicio de su sesión"
        elif i is not None and per_block[(i, a["time"])] > 1:
            reason = "misma hora repetida en varios artistas del bloque"
        if reason:
            review.append({"field": "artists.time", "artist": a.get("name"), "value": a["time"],
                           "action": "descartado", "reason": reason})
            a["time"] = None
    dates = list(ext.get("dates") or []) + [s["date"] for s in sessions if isinstance(s.get("date"), dict)]
    for d in dates:
        if isinstance(d, dict) and d.get("iso") and not _year_printed(d):
            review.append({"field": "iso", "text": d.get("text"), "value": d["iso"], "action": "descartado",
                           "reason": "año no impreso en esa fecha"})
            d["iso"] = None
    return ext, review


def expand_compact(obj: dict) -> dict:
    """Convierte la variante compacta al esquema original (sin inventar datos)."""
    uncertain = {str(x).casefold() for x in obj.get("uncertain") or []}
    times = {t["name"].casefold(): t["time"] for t in obj.get("individual_times") or []}
    artists = []
    for s in obj.get("sessions") or []:
        date_text = (s.get("date") or {}).get("text")
        day = " ".join(x for x in (date_text, s.get("label")) if x) or None
        for name in s.get("artists") or []:
            artists.append({"name": name, "stage": s.get("stage"), "day": day,
                            "time": times.get(name.casefold()), "uncertain": name.casefold() in uncertain})
    for a in obj.get("artists") or []:
        artists.append({"name": a["name"], "stage": a.get("stage"), "day": a.get("day"),
                        "time": times.get(a["name"].casefold()), "uncertain": a["name"].casefold() in uncertain})
    out = {k: obj.get(k) for k in ("event_name", "dates", "location", "stages", "unreadable_text", "sessions", "b2b")}
    out["artists"] = artists
    return out


def parse_compact(text: str) -> tuple[object | None, list[str], dict | None, list[dict]]:
    """Analiza, valida, expande y audita. Devuelve (compacto, errores, extracción expandida y depurada, avisos)."""
    try:
        obj = json.loads(text)
    except (json.JSONDecodeError, TypeError) as exc:
        return None, [f"JSON inválido: {exc.__class__.__name__}"], None, []
    errors = validate_compact(obj)
    if errors:
        return obj, errors, None, []
    expanded, review = audit_extraction(expand_compact(obj))
    return obj, validate(expanded), expanded, review
