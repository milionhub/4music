from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api import ApiError, router
from app.musicbrainz import ProviderError

app = FastAPI(title="music-discovery backend")
app.include_router(router)

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
