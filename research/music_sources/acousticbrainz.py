"""Acceso a la API histórica de AcousticBrainz (Fase 1.3), solo lectura por MBID de grabación.

AcousticBrainz dejó de recoger datos en 2022. Sus valores son **estimaciones algorítmicas**
(Essentia y clasificadores SVM de alto nivel) y nunca se tratan como datos verificados.
Documentación: https://acousticbrainz.readthedocs.io/api.html (búsqueda masiva de hasta 25 MBID;
límite típico de 10 peticiones cada 10 s por IP, comunicado en las cabeceras X-RateLimit-*).
"""

from __future__ import annotations

from http_client import FetchResult, HttpClient, SourcePolicy

API = "https://acousticbrainz.org/api/v1/"
MAX_BULK = 25

# Solo se piden estos descriptores de bajo nivel, no el documento completo.
LOW_LEVEL_FEATURES = "rhythm.bpm;tonal.key_key;tonal.key_scale;tonal.key_strength;metadata.audio_properties.length"


def policy(user_agent: str, max_requests: int) -> SourcePolicy:
    return SourcePolicy(
        "acousticbrainz", min_interval_s=1.0, max_requests=max_requests, headers={"User-Agent": user_agent},
        log_headers=("X-RateLimit-Limit", "X-RateLimit-Remaining", "X-RateLimit-Reset-In"),
        remaining_header="X-RateLimit-Remaining", remaining_threshold=1, cooldown_s=10.0,
    )


def _ids(mbids: list[str]) -> str:
    if not 0 < len(mbids) <= MAX_BULK:
        raise ValueError(f"entre 1 y {MAX_BULK} MBID por petición masiva")
    return ";".join(sorted(mbids))


def count(client: HttpClient, mbids: list[str]) -> FetchResult:
    return client.get_json("acousticbrainz", client.build_url(API + "count", {"recording_ids": _ids(mbids)}))


def low_level(client: HttpClient, mbids: list[str]) -> FetchResult:
    return client.get_json("acousticbrainz", client.build_url(
        API + "low-level", {"recording_ids": _ids(mbids), "features": LOW_LEVEL_FEATURES}))


def high_level(client: HttpClient, mbids: list[str]) -> FetchResult:
    return client.get_json("acousticbrainz", client.build_url(
        API + "high-level", {"recording_ids": _ids(mbids), "map_classes": "true"}))


GENRE_MODELS = ("genre_electronic", "genre_dortmund", "genre_rosamerica", "genre_tzanetakis")


def summarize_low(doc: dict) -> dict:
    rhythm, tonal = doc.get("rhythm", {}), doc.get("tonal", {})
    return {"bpm": rhythm.get("bpm"), "key": tonal.get("key_key"), "scale": tonal.get("key_scale"),
            "key_strength": tonal.get("key_strength"),
            "length_s": doc.get("metadata", {}).get("audio_properties", {}).get("length")}


def summarize_high(doc: dict) -> dict:
    hl = doc.get("highlevel", {})
    models = {m: {"value": hl[m].get("value"), "probability": hl[m].get("probability")}
              for m in GENRE_MODELS if m in hl}
    versions = doc.get("metadata", {}).get("version", {})
    return {"genre_models": models,
            "essentia_version": versions.get("highlevel", {}).get("essentia")
            or versions.get("essentia"),
            "model_version": versions.get("highlevel", {}).get("models_essentia_git_sha")}
