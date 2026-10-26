"""Tempo estimado por análisis de audio en ReccoBeats, por ISRC de la grabación (V5.5). Sin clave.

Condiciones (https://reccobeats.com/docs/documentation/terms-of-service, leídas el 2026-10-21): «entirely free to use
for both personal and commercial projects»; las métricas las genera su propio análisis («custom, homemade service») y
los metadatos vienen de Spotify (aquí no se usan). Sin garantía de exactitud ni de continuidad: es un complemento,
nunca bloquea la ficha y solo se consulta cuando AcousticBrainz no tiene el tempo.

Piloto (eval/pilot_v55.py, docs/v5-5-cobertura-musical.md): el tempo coincide con AcousticBrainz en 6 de 7 grabaciones
(±1 BPM) y la otra es un error de octava (196 frente a 98). La tonalidad solo coincide en 2 de 6 (el resto, a una quinta
o en el modo relativo): **no se publica**. Reglas para no mostrar un dato dudoso:
- Identidad: el ISRC devuelto debe ser uno de la grabación y la duración debe coincidir (±3 %); sin duración, nada.
- Si hay varias pistas válidas (el mismo ISRC en varias ediciones), deben concordar (±2 %).
- Solo tempos entre 70 y 180 BPM: fuera de ese margen suele ser un error de octava; no se corrige, se descarta.
Una respuesta sin datos se guarda (30 días); un fallo de red no, para reintentarlo en la próxima visita.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from typing import Any

from app import schemas, store

KIND = "reccobeats"
VERSION = 2  # v2: perfil sonoro (energía, bailabilidad, voz, ánimo, sonoridad)
TTL_S = 90 * 24 * 3600
EMPTY_TTL_S = 30 * 24 * 3600
BASE_URL = "https://api.reccobeats.com/v1"
TIMEOUT_S = 4  # dos peticiones como máximo, solo la primera vez: la ficha no espera más de ~8 s por esta fuente
MAX_IDS = 5
USER_AGENT = "music-discovery/0.1 (TrackDNA; ReccoBeats tempo lookup)"
LENGTH_TOLERANCE = 0.03
BPM_TOLERANCE = 0.02
BPM_RANGE = (70, 180)
SOURCE = schemas.SourceRef(label="ReccoBeats", url="https://reccobeats.com/")
DETAIL = "Tempo estimado por el análisis de audio de ReccoBeats; grabación identificada por ISRC y duración."
# Perfil sonoro (V6.3, piloto eval/pilot_v63_analysis.py): distingue bien los temas con voz de los instrumentales y su
# ánimo es coherente; se publica como estimación. La tonalidad sigue sin publicarse (coincidía en 2 de 6).
FEATURES = ("energy", "danceability", "instrumentalness", "valence")
FEATURE_TOLERANCE = 0.15  # varias ediciones del mismo ISRC deben concordar
PROFILE_DETAIL = "Estimado por el análisis de audio de ReccoBeats; grabación identificada por ISRC y duración."

Transport = Callable[[str], dict[str, Any]]


def _default_transport(url: str) -> dict[str, Any]:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
        return json.loads(resp.read().decode("utf-8"))


def summarize(tracks: list[dict[str, Any]], features: list[dict[str, Any]], isrcs: list[str], length_ms: int | None) -> dict[str, Any]:
    """{"bpm": 134, "energy": 0.79, …} si las pistas son esta grabación (ISRC y duración) y concuerdan; {} en cualquier
    otro caso. El tempo solo entre 70 y 180; cada rasgo del perfil, solo si todas sus ediciones concuerdan (±0,15)."""
    if not length_ms:
        return {}
    wanted = set(isrcs)
    valid = {t["id"] for t in tracks if isinstance(t, dict) and t.get("isrc") in wanted and isinstance(t.get("durationMs"), (int, float))
             and abs(t["durationMs"] - length_ms) <= length_ms * LENGTH_TOLERANCE}
    rows = [f for f in features if isinstance(f, dict) and f.get("id") in valid]
    tempos = [f["tempo"] for f in rows if isinstance(f.get("tempo"), (int, float))]
    if not tempos or max(tempos) - min(tempos) > min(tempos) * BPM_TOLERANCE:
        return {}  # ediciones que no concuerdan: la identificación es dudosa, no se publica nada
    out: dict[str, Any] = {}
    bpm = round(sum(tempos) / len(tempos))
    if BPM_RANGE[0] <= bpm <= BPM_RANGE[1]:
        out["bpm"] = bpm
    for key in FEATURES:
        vals = [f[key] for f in rows if isinstance(f.get(key), (int, float)) and 0 <= f[key] <= 1]
        if vals and len(vals) == len(rows) and max(vals) - min(vals) <= FEATURE_TOLERANCE:
            out[key] = round(sum(vals) / len(vals), 3)
    return out


def lookup(mbid: str, isrcs: list[str], length_ms: int | None, transport: Transport | None = None) -> dict[str, Any]:
    """Tempo publicable de la grabación (caché propia por MBID). Dos peticiones como máximo: pistas y audio-features."""
    hit = store.get(KIND, mbid)
    if hit is not None and hit.get("version") == VERSION:
        return hit.get("values") or {}
    ids = [i for i in dict.fromkeys(isrcs) if isinstance(i, str) and i.strip()][:MAX_IDS]
    if not ids or not length_ms:
        return {}  # sin ISRC o sin duración no hay identificación posible (no se guarda: puede llegar después)
    q = urllib.parse.quote(",".join(ids), safe=",")
    get = transport or _default_transport
    try:
        tracks = (get(f"{BASE_URL}/track?ids={q}") or {}).get("content") or []
        values: dict[str, Any] = {}
        if tracks:
            features = (get(f"{BASE_URL}/audio-features?ids={q}") or {}).get("content") or []
            values = summarize(tracks, features, ids, length_ms)
    except (urllib.error.URLError, TimeoutError, OSError, ValueError, AttributeError):
        return {}  # fallo temporal o respuesta inesperada: no se guarda
    store.put(KIND, mbid, {"version": VERSION, "values": values}, TTL_S if values else EMPTY_TTL_S)
    return values


def vocals(instrumentalness: float) -> str:
    """Voz o instrumental según la instrumentalidad estimada (umbrales prudentes; el medio, «voz puntual»)."""
    return "instrumental" if instrumentalness >= 0.6 else "vocal" if instrumentalness <= 0.2 else "partial"


def with_profile(dna: schemas.TrackDna, values: dict[str, Any]) -> schemas.TrackDna:
    """Perfil sonoro estimado: energía, bailabilidad y ánimo (0–100) y voz/instrumental. Sustituye los rasgos no
    disponibles con la misma clave y añade los que falten; nunca pisa uno medido por otra fuente."""
    found: dict[str, schemas.DnaTrait] = {}
    names = {"energy": "Energía", "danceability": "Bailabilidad", "valence": "Ánimo"}
    for key, label in names.items():
        if key in values:
            found[key] = schemas.DnaTrait(key=key, group="acoustic", label=label, status="measured",
                                          values=[str(round(values[key] * 100))], detail=PROFILE_DETAIL, sources=[SOURCE])
    if "instrumentalness" in values:
        found["vocals"] = schemas.DnaTrait(key="vocals", group="acoustic", label="Voz", status="measured",
                                           values=[vocals(values["instrumentalness"]), str(round(values["instrumentalness"] * 100))],
                                           detail=PROFILE_DETAIL, sources=[SOURCE])
    if not found:
        return dna
    traits = [found.pop(t.key) if t.key in found and t.status == "unavailable" else t for t in dna.traits]
    present = {t.key for t in traits}
    traits += [t for k, t in found.items() if k not in present]
    return dna.model_copy(update={"traits": traits})


def with_tempo(dna: schemas.TrackDna, values: dict[str, Any]) -> schemas.TrackDna:
    """Añade el tempo estimado solo si el ADN aún no lo tiene (AcousticBrainz manda); nunca la tonalidad."""
    if not values.get("bpm"):
        return dna
    traits = [t.model_copy(update={"status": "measured", "values": [str(values["bpm"])], "sources": [SOURCE], "detail": DETAIL})
              if t.key == "bpm" and t.status == "unavailable" else t for t in dna.traits]
    return dna.model_copy(update={"traits": traits})
