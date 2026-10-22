"""Carteles 3.4: identidad de los nombres del cartel (MusicBrainz simulado) y canciones de la vista rápida."""

import json
from urllib.parse import parse_qs, urlsplit

import pytest
from fastapi.testclient import TestClient

from app import poster_identity
from app.api import get_client
from app.main import app
from app.musicbrainz import MusicBrainzClient

PACO = "11111111-1111-1111-1111-111111111111"
CARL = "22222222-2222-2222-2222-222222222222"
CAJ = "33333333-3333-3333-3333-333333333333"
COL_A = "44444444-4444-4444-4444-444444444444"
COL_B = "55555555-5555-5555-5555-555555555555"
STING = "66666666-6666-6666-6666-666666666666"
CROCE = "77777777-7777-7777-7777-777777777777"
FUT = "88888888-8888-8888-8888-888888888888"
VARIOUS = "89ad4ac3-39f7-470e-963a-56509c546377"


def a(mbid, name, score=100, disambiguation=None, aliases=()):
    return {"id": mbid, "name": name, "score": score, "disambiguation": disambiguation,
            "aliases": [{"name": x} for x in aliases]}


SEARCH = {
    "Paco Osuna": [a(PACO, "Paco Osuna", disambiguation="Spanish techno DJ"), a(FUT, "Paco", 60)],
    "Carl Craig": [a(CARL, "Carl Craig", disambiguation="Detroit techno producer")],
    "Cajmere": [a(CAJ, "Cajmere", aliases=["Green Velvet"])],
    "Colette": [a(COL_A, "Colette", disambiguation="French singer"),
                a(COL_B, "Colette", 98, disambiguation="Chicago house DJ and vocalist")],
    "DJ Stingray 313": [a(STING, "DJ Stingray", 97, aliases=["DJ Stingray 313"])],
    "PETER GROCE": [a(CROCE, "Peter Croce", 72)],
    "Future\\.666": [a(FUT, "Future", 100), a(CROCE, "Future Sound of London", 90)],
    "Nadie Conocido": [],
    "Various": [a(VARIOUS, "Various Artists")],
    "Low Score": [a(PACO, "Low Score", 80)],
}


class Transport:
    def __init__(self, fail=False):
        self.urls: list[str] = []
        self.fail = fail

    def __call__(self, url, headers, timeout):
        self.urls.append(url)
        if self.fail:
            return 503, b"", None
        q = {k: v[0] for k, v in parse_qs(urlsplit(url).query).items()}
        if "/recording" in url:
            return 200, json.dumps({"recordings": RECORDINGS, "recording-count": len(RECORDINGS)}).encode(), None
        return 200, json.dumps({"artists": SEARCH.get(q["query"], [])}).encode(), None


def rec(mbid, title, date, credit=CARL, video=False):
    return {"id": mbid, "title": title, "first-release-date": date, "video": video,
            "artist-credit": [{"name": "Carl Craig", "joinphrase": "", "artist": {"id": credit, "name": "x"}}]}


RECORDINGS = [
    rec("r1", "At Les", "1997-05-01"), rec("r2", "At Les (Original Mix)", "1999"), rec("r3", "Sandstorms", "2004"),
    rec("r4", "Remix for other", "2020", credit=CAJ), rec("r5", "Video", "2021", video=True),
    rec("r6", "No date", ""), rec("r7", "Darkness", "2008"),
]


@pytest.fixture
def api():
    transport = Transport()
    client = MusicBrainzClient("test@example.org", transport=transport, sleep=lambda s: None)
    app.dependency_overrides[get_client] = lambda: client
    yield TestClient(app), transport
    app.dependency_overrides.clear()


def resolve(http, *names):
    r = http.post("/v1/posters/resolve", json={"names": list(names)})
    assert r.status_code == 200, r.text
    return {x["name"]: x for x in r.json()["results"]}


def test_coincidencia_exacta_unica_se_enlaza_con_evidencia(api):
    http, _ = api
    r = resolve(http, "Paco Osuna")["Paco Osuna"]
    assert r["status"] == "linked" and r["mbid"] == PACO and r["canonical"] == "Paco Osuna"
    assert "sin homónimos" in r["evidence"]


def test_homonimos_quedan_ambiguos_aunque_uno_parezca_de_la_escena(api):
    http, _ = api
    r = resolve(http, "Colette")["Colette"]
    assert r["status"] == "ambiguous" and r["mbid"] is None
    assert [c["mbid"] for c in r["candidates"]] == [COL_B, COL_A]  # la escena ordena, no decide
    assert r["candidates"][0]["scene"] is True


def test_alias_exacto_se_enlaza_y_lo_explica(api):
    http, _ = api
    r = resolve(http, "DJ Stingray 313")["DJ Stingray 313"]
    assert r["status"] == "linked" and r["mbid"] == STING and r["canonical"] == "DJ Stingray"
    assert "Alias «DJ Stingray 313»" in r["evidence"]


def test_sin_resultados_y_entidades_especiales_no_enlazan(api):
    http, _ = api
    out = resolve(http, "Nadie Conocido", "Various")
    assert out["Nadie Conocido"]["status"] == "none" and out["Nadie Conocido"]["candidates"] == []
    assert out["Various"]["status"] == "none"


def test_errata_probable_es_sugerencia_y_no_corrige_el_nombre(api):
    http, _ = api
    r = resolve(http, "PETER GROCE")["PETER GROCE"]
    assert r["status"] == "none" and r["mbid"] is None and r["name"] == "PETER GROCE"
    assert r["candidates"][0]["name"] == "Peter Croce" and r["candidates"][0]["match"] == "similar"


def test_no_enlaza_al_primero_si_no_coincide_exactamente(api):
    http, _ = api
    r = resolve(http, "Future.666")["Future.666"]
    assert r["status"] == "none" and r["mbid"] is None  # «Future» (score 100) no es «Future.666»


def test_exacta_con_puntuacion_baja_pide_confirmacion(api):
    http, _ = api
    r = resolve(http, "Low Score")["Low Score"]
    assert r["status"] == "ambiguous" and len(r["candidates"]) == 1


def test_b2b_cada_artista_se_resuelve_por_separado(api):
    http, transport = api
    out = resolve(http, "Carl Craig", "Cajmere")
    assert out["Carl Craig"]["mbid"] == CARL and out["Cajmere"]["mbid"] == CAJ
    assert len(transport.urls) == 2  # una búsqueda por persona, nunca «Carl Craig B2B Cajmere»


def test_cache_persistente_evita_repetir_busquedas(api):
    http, transport = api
    resolve(http, "Paco Osuna")
    client = MusicBrainzClient("test@example.org", transport=transport, sleep=lambda s: None)  # sin caché en memoria
    app.dependency_overrides[get_client] = lambda: client
    r = resolve(http, "PACO OSUNA")["PACO OSUNA"]
    assert r["status"] == "linked" and r["name"] == "PACO OSUNA"
    assert len(transport.urls) == 1


def test_musicbrainz_caido_marca_error_sin_seguir_consultando():
    transport = Transport(fail=True)
    client = MusicBrainzClient("test@example.org", transport=transport, sleep=lambda s: None)
    app.dependency_overrides[get_client] = lambda: client
    try:
        out = resolve(TestClient(app), "Paco Osuna", "Carl Craig", "Cajmere")
    finally:
        app.dependency_overrides.clear()
    assert {x["status"] for x in out.values()} == {"error"}
    assert len(transport.urls) == 2  # una petición y su único reintento; el resto no se pide
    again = MusicBrainzClient("test@example.org", transport=Transport(), sleep=lambda s: None)
    assert poster_identity.resolve(again, ["Paco Osuna"])[0].status == "linked"  # el error no se guardó


@pytest.mark.parametrize("body", [{"names": []}, {"names": ["x"] * 21}, {"names": ["  "]}, {"names": ["x" * 101]}])
def test_peticion_invalida(api, body):
    http, _ = api
    r = http.post("/v1/posters/resolve", json=body)
    assert r.status_code == 422


def test_sin_contacto_de_musicbrainz():
    app.dependency_overrides[get_client] = lambda: MusicBrainzClient("", transport=Transport())
    try:
        r = TestClient(app).post("/v1/posters/resolve", json={"names": ["Paco Osuna"]})
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 503 and r.json()["error"]["code"] == "provider_not_configured"


def test_key_normaliza_con_prudencia():
    assert poster_identity.key("Future.666") == poster_identity.key("FUTURE 666")
    assert poster_identity.key("Âme") == "ame"
    assert poster_identity.key("Simon & Garfunkel") == poster_identity.key("simon and garfunkel")
    assert poster_identity.key("DJ Stingray") != poster_identity.key("Stingray")


def test_canciones_propias_por_fecha_sin_rellenar(api):
    http, _ = api
    r = http.get(f"/v1/posters/artists/{CARL}/tracks")
    assert r.status_code == 200
    titles = [t["title"] for t in r.json()["tracks"]]
    assert titles == ["Darkness", "Sandstorms", "At Les (Original Mix)"]  # versión más reciente, sin duplicar el tema
    assert all(t["recording_mbid"].startswith("r") for t in r.json()["tracks"])
    assert http.get("/v1/posters/artists/no-es-mbid/tracks").status_code == 422
