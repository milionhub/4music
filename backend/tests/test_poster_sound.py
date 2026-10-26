"""Carteles 4 (V6.8): el sonido de un artista del cartel (estilos y sellos de Discogs, afines de Deezer)."""
import json
from urllib.parse import urlsplit

import pytest
from fastapi.testclient import TestClient

from app import api, deezer, discogs_tracks as dt, tracks
from app.api import get_client
from app.main import app
from app.musicbrainz import MusicBrainzClient

PAWSA = "11111111-1111-4111-8111-111111111111"


def release(title, labels, styles):
    return {"id": hash(title) % 10_000, "type": "release", "title": title, "label": labels, "style": styles}


RELEASES = ([release(f"PAWSA - EP {i}", ["Solid Grooves Records"], ["Tech House", "Minimal"]) for i in range(4)]
            + [release("PAWSA - Dirty Cash", ["Solid Grooves Records", "Not On Label"], ["Tech House"]),
               release("PAWSA - Edit", ["Not On Label (PAWSA Self-released)"], ["House"]),
               release("PAWSA - Other", ["Hot Creations"], ["Tech House"]),
               release("Otro - Y", ["Hot Creations"], ["Trance"])] * 1)


class Discogs:
    def __init__(self, fail=None):
        self.fail, self.urls = fail, []

    def __call__(self, url):
        self.urls.append(url)
        if self.fail:
            raise self.fail
        assert urlsplit(url).path == "/database/search"
        return {"results": RELEASES}


class MB:
    def __call__(self, url, headers, timeout):
        return 200, json.dumps({"id": PAWSA, "name": "PAWSA", "relations": []}).encode(), None


@pytest.fixture(autouse=True)
def _reset():
    yield
    app.dependency_overrides.clear()


def client_with(monkeypatch, discogs, related=None, deezer_fail=False):
    monkeypatch.setattr(dt, "_default_transport", discogs)
    monkeypatch.setattr(api, "_deezer_record", lambda c, f, m: {"id": "7", "link": "https://www.deezer.com/artist/7"})

    def fake_get(path, params, transport):
        if deezer_fail:
            raise deezer.Unavailable("x")
        assert path == "artist/7/related" and callable(transport)
        return {"data": related or []}
    monkeypatch.setattr(deezer, "_get", fake_get)
    mbc = MusicBrainzClient("test@example.org", transport=MB(), sleep=lambda s: None)
    app.dependency_overrides[get_client] = lambda: mbc
    return TestClient(app)


def test_single_family():
    assert tracks.single_family(["Minimal", "Tech House", "Techno"]) == ["House", "Minimal", "Tech House"]
    assert tracks.single_family(["Electronic"]) == []


def test_artist_sound_estilos_y_sellos_del_propio_artista():
    styles, labels, n = dt.artist_sound("PAWSA", Discogs())
    assert n == 7, "solo los lanzamientos cuyo título empieza por el artista"
    assert styles[0] == "Tech House" and "Trance" not in styles
    assert labels == ["Solid Grooves Records"], "un sello cuenta con dos o más lanzamientos; nunca «Not On Label»"


def test_endpoint_sonido_con_afines_y_cache(monkeypatch):
    discogs = Discogs()
    client = client_with(monkeypatch, discogs, related=[{"name": "Dennis Cruz", "link": "https://www.deezer.com/artist/9"}, {"x": 1}])
    body = client.get(f"/v1/posters/artists/{PAWSA}/sound").json()
    assert body["name"] == "PAWSA" and body["status"] == "ok"
    assert body["genre"][0] == "House" and "Tech House" in body["genre"]
    assert body["labels"] == ["Solid Grooves Records"]
    assert [r["name"] for r in body["related"]] == ["Dennis Cruz"]
    assert {s["label"] for s in body["sources"]} == {dt.ATTRIBUTION, "Deezer (artistas relacionados)"}
    client.get(f"/v1/posters/artists/{PAWSA}/sound")
    assert len(discogs.urls) == 1, "la respuesta completa se guarda"


def test_endpoint_parcial_no_se_guarda(monkeypatch):
    client = client_with(monkeypatch, Discogs(), deezer_fail=True)
    assert client.get(f"/v1/posters/artists/{PAWSA}/sound").json()["status"] == "partial"
    client = client_with(monkeypatch, Discogs(), related=[{"name": "Dennis Cruz"}])
    assert client.get(f"/v1/posters/artists/{PAWSA}/sound").json()["status"] == "ok"
    assert client.get("/v1/posters/artists/no-mbid/sound").status_code in (400, 404, 422)
