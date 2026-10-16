from fastapi import FastAPI

app = FastAPI(title="music-discovery backend")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
