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


def test_v68_el_nombre_antiguo_queda_como_alias():
    mbid = next(iter(renames.RENAMES))
    old, new, _src = renames.RENAMES[mbid]
    out = renames.apply({"id": mbid, "name": old, "aliases": [{"name": "Otro"}]})
    assert out["name"] == new and [a["name"] for a in out["aliases"]] == ["Otro", old]
    assert renames.apply(out)["aliases"] == out["aliases"], "no se duplica"


def test_v68_nombre_anterior():
    mbid = next(iter(renames.RENAMES))
    old, new, _src = renames.RENAMES[mbid]
    assert renames.is_former(mbid, old.upper()) and not renames.is_former(mbid, new) and not renames.is_former("x", old)


def test_v68_carteles_sin_reescribir_lo_impreso(monkeypatch):
    from fastapi.testclient import TestClient
    from app import api, poster_identity, schemas
    old, new = next(iter(renames.RENAMES.values()))[:2]
    monkeypatch.setattr(poster_identity, "resolve", lambda client, names: [
        schemas.PosterResolution(name=n, status="none", evidence=None) for n in names])
    body = TestClient(app).post("/v1/posters/resolve", json={"names": [old.upper()]}).json()
    assert body["results"][0]["name"] == old.upper(), "la app empareja por el nombre enviado"
