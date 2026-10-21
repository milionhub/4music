"""BPM y tonalidad medidos por análisis de audio (Essentia) en AcousticBrainz: CC0, por MBID de grabación, sin clave.

El proyecto está congelado desde 2022: solo hay datos de grabaciones analizadas hasta entonces. Por eso es un
complemento histórico, nunca una estimación propia. Reglas para no mostrar un dato dudoso:
- Solo envíos cuyo audio dura lo mismo que la grabación (±5 %): otro edit con el mismo MBID no cuenta.
- BPM: todos los envíos deben coincidir (±2 %); se muestra redondeado. Si no coinciden, no se publica nada.
- Tonalidad: todos los envíos deben dar la misma tonalidad y modo, con fuerza ≥ 0,6 en cada uno.
Una respuesta vacía se guarda (no hay datos); un fallo de red no, para reintentarlo en la próxima visita.
"""

import json
import urllib.error
import urllib.request
from collections.abc import Callable
from typing import Any

from app import schemas, store

KIND = "acoustic"
VERSION = 1
TTL_S = 180 * 24 * 3600
BASE_URL = "https://acousticbrainz.org/api/v1/low-level"
FEATURES = "rhythm.bpm;tonal.key_key;tonal.key_scale;tonal.key_strength;metadata.audio_properties.length"
SUBMISSIONS = 3
TIMEOUT_S = 6
USER_AGENT = "music-discovery/0.1 (TrackDNA; AcousticBrainz CC0 lookup)"
LENGTH_TOLERANCE = 0.05
BPM_TOLERANCE = 0.02
KEY_STRENGTH = 0.6

Transport = Callable[[str], dict[str, Any]]

PITCH = {"C": 0, "C#": 1, "Db": 1, "D": 2, "D#": 3, "Eb": 3, "E": 4, "F": 5, "F#": 6, "Gb": 6, "G": 7, "G#": 8,
         "Ab": 8, "A": 9, "A#": 10, "Bb": 10, "B": 11}
# Grafía habitual en cada modo (Sol# menor, pero Lab mayor), como en las tiendas y el software de DJ.
SPANISH_MINOR = ["Do", "Do#", "Re", "Mib", "Mi", "Fa", "Fa#", "Sol", "Sol#", "La", "Sib", "Si"]
SPANISH_MAJOR = ["Do", "Reb", "Re", "Mib", "Mi", "Fa", "Fa#", "Sol", "Lab", "La", "Sib", "Si"]
# Rueda Camelot (la notación de mezcla armónica que usan los DJ): número por clase de altura y modo.
CAMELOT_MINOR = {8: 1, 3: 2, 10: 3, 5: 4, 0: 5, 7: 6, 2: 7, 9: 8, 4: 9, 11: 10, 6: 11, 1: 12}
CAMELOT_MAJOR = {11: 1, 6: 2, 1: 3, 8: 4, 3: 5, 10: 6, 5: 7, 0: 8, 7: 9, 2: 10, 9: 11, 4: 12}
SOURCE = schemas.SourceRef(label="AcousticBrainz", url="https://acousticbrainz.org/", license="CC0")


def _default_transport(url: str) -> dict[str, Any]:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
        return json.loads(resp.read().decode("utf-8"))


def key_label(key: str, scale: str) -> tuple[str, str] | None:
    """«La menor» y «8A» a partir de la notación de Essentia («A», «minor»)."""
    pc = PITCH.get(key)
    if pc is None or scale not in ("major", "minor"):
        return None
    camelot = f"{CAMELOT_MINOR[pc]}A" if scale == "minor" else f"{CAMELOT_MAJOR[pc]}B"
    return (f"{SPANISH_MINOR[pc]} menor" if scale == "minor" else f"{SPANISH_MAJOR[pc]} mayor"), camelot


def summarize(submissions: list[dict[str, Any]], length_ms: int | None) -> dict[str, Any]:
    """Valores publicables a partir de los envíos (vacío si no hay acuerdo o no corresponden a esta grabación)."""
    valid = []
    for s in submissions:
        length = ((s.get("metadata") or {}).get("audio_properties") or {}).get("length")
        if length_ms and isinstance(length, (int, float)) and abs(length * 1000 - length_ms) > length_ms * LENGTH_TOLERANCE:
            continue
        valid.append(s)
    out: dict[str, Any] = {}
    bpms = [b for b in ((s.get("rhythm") or {}).get("bpm") for s in valid) if isinstance(b, (int, float)) and 60 <= b <= 200]
    if bpms and max(bpms) - min(bpms) > min(bpms) * BPM_TOLERANCE:
        return {}  # envíos que no concuerdan en el tempo: probablemente no es el mismo audio; no se publica nada
    if bpms and len(bpms) == len(valid):
        out["bpm"] = round(sum(bpms) / len(bpms))
    keys = {((s.get("tonal") or {}).get("key_key"), (s.get("tonal") or {}).get("key_scale")) for s in valid}
    strengths = [(s.get("tonal") or {}).get("key_strength") for s in valid]
    if valid and len(keys) == 1 and all(isinstance(x, (int, float)) and x >= KEY_STRENGTH for x in strengths):
        label = key_label(*next(iter(keys)))
        if label:
            out["key"], out["camelot"] = label
    return out


def lookup(mbid: str, length_ms: int | None, transport: Transport | None = None) -> dict[str, Any]:
    """{"bpm": 124, "key": "La menor", "camelot": "8A"} con lo que haya; {} sin datos o si la fuente falla."""
    hit = store.get(KIND, mbid)
    if hit is not None and hit.get("version") == VERSION:
        return hit.get("values") or {}
    ids = ";".join(f"{mbid}:{n}" for n in range(SUBMISSIONS))
    try:
        data = (transport or _default_transport)(f"{BASE_URL}?recording_ids={ids}&features={FEATURES}")
    except (urllib.error.URLError, TimeoutError, OSError, ValueError):
        return {}  # fallo temporal: no se guarda
    entries = (data.get(mbid) or {}) if isinstance(data, dict) else {}
    submissions = [v for _, v in sorted(entries.items()) if isinstance(v, dict)] if isinstance(entries, dict) else []
    values = summarize(submissions, length_ms)
    store.put(KIND, mbid, {"version": VERSION, "values": values}, TTL_S)
    return values


def with_measurements(dna: schemas.TrackDna, values: dict[str, Any]) -> schemas.TrackDna:
    """Sustituye los rasgos acústicos sin datos por los medidos (estado «measured»), sin tocar el resto."""
    measured: dict[str, list[str]] = {}
    if values.get("bpm"):
        measured["bpm"] = [str(values["bpm"])]
    if values.get("key"):
        measured["key"] = [values["key"], values["camelot"]]
    if not measured:
        return dna
    traits = [t.model_copy(update={"status": "measured", "values": measured[t.key], "sources": [SOURCE],
                                   "detail": "Análisis de audio de AcousticBrainz (estimación, datos hasta 2022)."})
              if t.key in measured and t.status == "unavailable" else t for t in dna.traits]
    return dna.model_copy(update={"traits": traits})
