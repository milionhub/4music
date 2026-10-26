from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response

from app import renames
from app.api import ApiError, router
from app.musicbrainz import ProviderError

app = FastAPI(title="music-discovery backend")
app.include_router(router)


VERBATIM_PATHS = {"/v1/posters/analyze", "/v1/posters/resolve"}


@app.middleware("http")
async def current_artist_names(request: Request, call_next):
    """Nombres artísticos actuales (app/renames.py) también en lo ya compuesto o guardado: historias, biografías,
    títulos de remixes y respuestas en caché. Solo JSON."""
    response = await call_next(request)
    # Carteles: lo impreso manda («CHRIS STUSSY» sigue siendo lo que dice el cartel) y la app empareja cada resultado
    # por el nombre que envió; los datos de MusicBrainz ya llegan con el nombre actual (renames.apply).
    if "application/json" not in response.headers.get("content-type", "") or request.url.path in VERBATIM_PATHS:
        return response
    body = b"".join([chunk async for chunk in response.body_iterator])
    fixed = renames.text(body.decode("utf-8")).encode("utf-8")
    headers = {k: v for k, v in response.headers.items() if k.lower() != "content-length"}
    return Response(content=fixed, status_code=response.status_code, headers=headers, media_type=response.media_type)


_PROVIDER_STATUS = {"not_found": 404, "provider_bad_response": 502}


def _error(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": {"code": code, "message": message}})


@app.exception_handler(ApiError)
def api_error_handler(_: Request, exc: ApiError) -> JSONResponse:
    return _error(exc.status, exc.code, exc.message)


@app.exception_handler(ProviderError)
def provider_error_handler(_: Request, exc: ProviderError) -> JSONResponse:
    return _error(_PROVIDER_STATUS.get(exc.code, 503), exc.code, str(exc))


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
