"""Acceso a la API oficial de Discogs (Fase 1.3).

- Autenticación con token personal por cabecera `Authorization: Discogs token=...`.
  El token solo se lee del entorno; nunca va en la URL, en logs ni en resultados.
- Antes de cachear se eliminan los campos de "Restricted Data" según las API Terms of Use
  (imágenes, datos de usuarios/comunidad y de Marketplace).
- Ritmo: 60 peticiones/min autenticado (ventana móvil de 60 s); se usa 1,2 s entre peticiones
  y una pausa si X-Discogs-Ratelimit-Remaining baja del umbral.
"""

from __future__ import annotations

from http_client import FetchResult, HttpClient, SourcePolicy

API = "https://api.discogs.com/"
WEB = "https://www.discogs.com/"

# Claves de Restricted Data o no necesarias que se descartan antes de guardar nada.
RESTRICTED_KEYS = {
    "images", "image", "thumb", "cover_image", "thumbnail_url",  # imágenes (Restricted Data)
    "community", "user_data", "stats", "submitter",               # datos de usuarios / comunidad
    "lowest_price", "num_for_sale", "blocked_from_sale",          # Marketplace Data
}


def strip_restricted(obj):
    if isinstance(obj, dict):
        return {k: strip_restricted(v) for k, v in obj.items() if k not in RESTRICTED_KEYS}
    if isinstance(obj, list):
        return [strip_restricted(v) for v in obj]
    return obj


def policy(token: str, user_agent: str, max_requests: int) -> SourcePolicy:
    return SourcePolicy(
        "discogs", min_interval_s=1.2, max_requests=max_requests,
        headers={"User-Agent": user_agent, "Authorization": f"Discogs token={token}"},
        sanitize=strip_restricted,
        log_headers=("X-Discogs-Ratelimit", "X-Discogs-Ratelimit-Used", "X-Discogs-Ratelimit-Remaining"),
        remaining_header="X-Discogs-Ratelimit-Remaining", remaining_threshold=3, cooldown_s=20.0,
    )


def get(client: HttpClient, path: str, params: dict[str, str] | None = None) -> FetchResult:
    return client.get_json("discogs", client.build_url(API + path, params))


def search(client: HttpClient, **params: str) -> FetchResult:
    return get(client, "database/search", {**params, "per_page": params.get("per_page", "25")})


def release(client: HttpClient, rid: str | int) -> FetchResult:
    return get(client, f"releases/{rid}")


def master(client: HttpClient, mid: str | int) -> FetchResult:
    return get(client, f"masters/{mid}")


def master_versions(client: HttpClient, mid: str | int) -> FetchResult:
    return get(client, f"masters/{mid}/versions", {"per_page": "100"})


def artist(client: HttpClient, aid: str | int) -> FetchResult:
    return get(client, f"artists/{aid}")


def artist_releases(client: HttpClient, aid: str | int) -> FetchResult:
    return get(client, f"artists/{aid}/releases", {"sort": "year", "sort_order": "desc", "per_page": "100"})


def web_url(kind: str, did: str | int) -> str:
    return f"{WEB}{kind}/{did}"


# ---------------------------------------------------------------- extracción (valores tal cual)

def summarize_release(r: dict) -> dict:
    return {
        "id": r.get("id"), "title": r.get("title"), "uri": r.get("uri"),
        "artists": [{"name": a.get("name"), "anv": a.get("anv") or None, "id": a.get("id"), "join": a.get("join") or None}
                    for a in r.get("artists", [])],
        "extraartists": [{"name": a.get("name"), "role": a.get("role"), "id": a.get("id"), "tracks": a.get("tracks") or None}
                         for a in r.get("extraartists", [])],
        "year": r.get("year"), "released": r.get("released"), "country": r.get("country"),
        "labels": [{"name": l.get("name"), "catno": l.get("catno"), "id": l.get("id")} for l in r.get("labels", [])],
        "formats": [{"name": f.get("name"), "qty": f.get("qty"), "descriptions": f.get("descriptions", [])}
                    for f in r.get("formats", [])],
        "genres": r.get("genres", []), "styles": r.get("styles", []),
        "master_id": r.get("master_id"), "data_quality": r.get("data_quality"),
        "tracklist": [{"position": t.get("position"), "title": t.get("title"), "duration": t.get("duration") or None,
                       "type": t.get("type_"),
                       "extraartists": [{"name": a.get("name"), "role": a.get("role")} for a in t.get("extraartists", [])]}
                      for t in r.get("tracklist", [])],
        "identifiers": [{"type": i.get("type"), "value": i.get("value"), "description": i.get("description")}
                        for i in r.get("identifiers", [])],
    }


def summarize_master(m: dict) -> dict:
    return {"id": m.get("id"), "title": m.get("title"), "uri": m.get("uri"), "year": m.get("year"),
            "artists": [a.get("name") for a in m.get("artists", [])], "genres": m.get("genres", []),
            "styles": m.get("styles", []), "main_release": m.get("main_release"),
            "data_quality": m.get("data_quality")}


def summarize_search_hit(h: dict) -> dict:
    return {"id": h.get("id"), "type": h.get("type"), "title": h.get("title"), "uri": h.get("uri"),
            "master_id": h.get("master_id") or None, "year": h.get("year"), "country": h.get("country"),
            "label": h.get("label", []), "catno": h.get("catno"), "format": h.get("format", []),
            "genre": h.get("genre", []), "style": h.get("style", [])}
