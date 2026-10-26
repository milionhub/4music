"""Nombres artísticos actuales que MusicBrainz aún no recoge: por MBID en los datos, por texto en lo ya compuesto."""

from fastapi.testclient import TestClient

from app import renames
from app.main import app

STASSY = "5b7f4511-1764-4d80-83b5-8c150f4636c5"


def test_mb_data_names_by_mbid_only_and_queries_translated():
    raw = {"id": STASSY, "name": "Chris Stussy", "sort-name": "Stussy, Chris",
           "artist-credit": [{"name": "Chris Stussy", "artist": {"id": STASSY, "name": "Chris Stussy"}},
                             {"name": "Chris Stussy", "artist": {"id": "otro", "name": "Chris Stussy"}}]}
    out = renames.apply(raw)
    assert out["name"] == "Chris Stassy" and out["artist-credit"][0]["name"] == "Chris Stassy"
    assert out["artist-credit"][1]["artist"]["name"] == "Chris Stussy", "otro MBID homónimo: no se toca"
    assert renames.query("chris stassy desire") == "Chris Stussy desire"


def test_api_json_uses_current_name_also_in_composed_text():
    assert renames.text("Hoodlum (Chris Stussy Remix) · CHRIS STUSSY") == "Hoodlum (Chris Stassy Remix) · CHRIS STASSY"
    assert TestClient(app).get("/health").json() == {"status": "ok"}
