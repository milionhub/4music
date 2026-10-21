"""Catálogo externo (V5.6): canciones de Discogs ausentes de MusicBrainz, sin red y sin coincidencias dudosas."""

import urllib.error
from urllib.parse import parse_qs, urlsplit

import pytest
from fastapi.testclient import TestClient

from app import discogs_tracks as dt
from app.api import get_client
from app.main import app
from app.musicbrainz import MusicBrainzClient

LUCIANO_MB = "6f8d9d66-24a0-4faf-97c7-81cd22cb1c7e"
REC = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"


def artist(id_, name, join=""):
    return {"id": id_, "name": name, "anv": "", "join": join}


# Forma real de la API (release 29565955, consultada el 2026-10-21), recortada.
VINOTINTO = {
    "id": 29565955, "title": "Vinotinto", "released": "2022-11-18", "year": 2022, "uri": "https://www.discogs.com/release/29565955-Vinotinto",
    "artists": [artist(6362, "Luciano", ","), artist(6126490, "Carloh", ","), artist(7319854, "Bastidas", ","), artist(14066743, "Carlos Corté$")],
    "labels": [{"name": "From The South", "catno": "FTSR001", "id": 1}], "formats": [{"name": "File", "descriptions": ["WAV"]}],
    "genres": ["Electronic"], "styles": ["Tech House"], "images": [{"uri": "https://i.discogs.com/x.jpg"}],
    "tracklist": [{"position": "1", "type_": "track", "title": "Vinotinto", "duration": "9:19"}],
}
EP = {
    "id": 200, "title": "Night EP", "released": "2024-00-00", "uri": "https://www.discogs.com/release/200-Night-EP",
    "artists": [artist(10, "Arapu (2)")], "labels": [{"name": "Satya (2)", "catno": "SATYA016"}],
    "formats": [{"name": "Vinyl", "descriptions": ['12"', "EP"]}], "genres": ["Electronic"], "styles": ["Minimal", "Tech House"],
    "tracklist": [
        {"position": "", "type_": "heading", "title": "Side A"},
        {"position": "A1", "type_": "track", "title": "Night Groove", "duration": "7:10"},
        {"position": "A2", "type_": "track", "title": "Night Groove (Extended Mix)", "duration": "9:40"},
        {"position": "B1", "type_": "track", "title": "Night Groove (Rossi Remix)", "duration": "",
         "extraartists": [{"id": 77, "name": "Rossi", "role": "Remix"}]},
    ],
}
EP_DIGITAL = {**EP, "id": 201, "formats": [{"name": "File", "descriptions": ["EP"]}],
              "tracklist": [{"position": "1", "type_": "track", "title": "Night Groove", "duration": "7:12"},
                            {"position": "2", "type_": "track", "title": "Night Groove", "duration": "6:02"}]}  # otra edición: 6:02 ≠ 7:10
DJ_MIX = {"id": 300, "title": "Live Session", "artists": [artist(10, "Arapu")], "formats": [{"name": "File", "descriptions": ["Mixed"]}],
          "tracklist": [{"position": "1", "type_": "track", "title": "Night Groove", "duration": "3:01"}]}
OTHER = {"id": 400, "title": "Playground", "artists": [artist(55, "Ivory")], "formats": [{"name": "Vinyl"}],
         "tracklist": [{"position": "A", "type_": "track", "title": "Playground", "duration": "6:00"}]}


class Discogs:
    def __init__(self, search=None, releases=None, fail=None):
        self.search, self.releases, self.fail, self.urls = search or [], releases or {}, fail, []

    def __call__(self, url):
        self.urls.append(url)
        if self.fail:
            raise self.fail
        path = urlsplit(url).path
        if path == "/database/search":
            return {"results": self.search}
        rid = int(path.rsplit("/", 1)[1])
        if rid not in self.releases:
            raise urllib.error.HTTPError(url, 404, "Not Found", {}, None)
        return self.releases[rid]


class MB:
    """MusicBrainz: búsqueda de grabaciones (vacía salvo `recordings`) y búsqueda de URL de Discogs → artista."""
    def __init__(self, recordings=None, links=None):
        self.recordings, self.links, self.urls = recordings or [], links or {}, []

    def __call__(self, url, headers, timeout):
        import json
        self.urls.append(url)
        parts = urlsplit(url)
        q = {k: v[0] for k, v in parse_qs(parts.query).items()}
        if parts.path.endswith("/url"):
            mbids = self.links.get(q["resource"])
            if mbids is None:
                return 404, b"", None
            rels = [{"target-type": "artist", "artist": {"id": m}} for m in mbids]
            return 200, json.dumps({"resource": q["resource"], "relations": rels}).encode(), None
        return 200, json.dumps({"recordings": self.recordings}).encode(), None


def make(monkeypatch, discogs, mb=None):
    mb = mb or MB()
    monkeypatch.setattr(dt, "_default_transport", discogs)
    mbc = MusicBrainzClient("test@example.org", transport=mb, sleep=lambda s: None)
    app.dependency_overrides[get_client] = lambda: mbc
    return TestClient(app), mb


@pytest.fixture(autouse=True)
def _reset():
    yield
    app.dependency_overrides.clear()


def hit(id_, master=None):
    return {"id": id_, "type": "release", "master_id": master, "title": "x"}


# --- Búsqueda -----------------------------------------------------------------------------------------------------
def test_cancion_ausente_de_musicbrainz_se_encuentra_y_se_abre(monkeypatch):
    discogs = Discogs([hit(29565955, 3614923)], {29565955: VINOTINTO})
    client, mb = make(monkeypatch, discogs, MB(links={"https://www.discogs.com/artist/6362": [LUCIANO_MB]}))
    r = client.get("/v1/tracks/search", params={"q": "Luciano Vinotinto"})
    assert r.status_code == 200
    [res] = r.json()["results"]
    assert res["mbid"] == "discogs:29565955:1" and res["catalog"] == "discogs"
    assert res["artist_name"] == "Luciano, Carloh, Bastidas, Carlos Corté$" and res["length_ms"] == 559000
    assert res["first_release_date"] == "2022-11-18" and res["cover_url"] is None

    d = client.get(f"/v1/tracks/ext/{res['mbid']}").json()
    assert d["catalog"] == "discogs" and d["mbid"] == "discogs:29565955:1" and d["source"]["provider"] == "discogs"
    # Solo el artista que MusicBrainz enlaza a ese ID de Discogs tiene MBID; los demás, sin enlace (nunca uno inventado).
    assert d["main_artist"]["mbid"] == LUCIANO_MB
    assert [a["mbid"] for a in d["artist_credit"]][1:] == ["discogs:artist:6126490", "discogs:artist:7319854", "discogs:artist:14066743"]
    rel = d["original_release"]
    assert (rel["labels"], rel["catalog_number"], rel["formats"]) == (["From The South"], "FTSR001", ["Digital Media"])
    traits = {t["key"]: t for t in d["dna"]["traits"]}
    assert traits["genre"]["scope"] == "release" and traits["genre"]["values"] == ["House", "Tech House"], "familia y estilo, no «Electronic»"
    assert all(traits[k]["status"] == "unavailable" for k in ("bpm", "key")), "sin BPM ni tonalidad inventados"
    assert d["sources"][0]["label"] == "Data provided by Discogs" and d["sources"][0]["url"].startswith("https://www.discogs.com/release/29565955")
    assert "images" not in str(d) and d["cover_url"] is None, "las imágenes son Restricted Data"
    assert d["interpretation_status"] == "unavailable"


def test_versiones_separadas_y_ediciones_identicas_unidas(monkeypatch):
    discogs = Discogs([hit(200, 9), hit(201, 10), hit(300)], {200: EP, 201: EP_DIGITAL, 300: DJ_MIX})
    client, _ = make(monkeypatch, discogs)
    results = client.get("/v1/tracks/search", params={"q": "Arapu Night Groove"}).json()["results"]
    got = [(r["mbid"], r["version"], r["length_ms"]) for r in results]
    # Original, extended y remix: tres canciones. La digital de 7:12 es la misma que la A1 de 7:10 (±3 %): no se repite;
    # la de 6:02 es otra grabación aunque se titule igual. El DJ mix (fragmento) no entra nunca.
    assert got == [("discogs:200:A1", None, 430000), ("discogs:200:A2", "Extended Mix", 580000),
                   ("discogs:200:B1", "Rossi Remix", None), ("discogs:201:2", None, 362000)]
    assert results[0]["artist_name"] == "Arapu" and results[0]["release_type"] == "EP"


def test_sin_todas_las_palabras_no_hay_resultado(monkeypatch):
    # «Arapu Playground» no debe devolver «Playground» de Ivory (V5.2): mismo filtro estricto que en MusicBrainz.
    discogs = Discogs([hit(400)], {400: OTHER})
    client, _ = make(monkeypatch, discogs)
    assert client.get("/v1/tracks/search", params={"q": "Arapu Playground"}).json()["results"] == []
    # Una sola palabra: no se consulta Discogs (los homónimos sobran).
    discogs.urls.clear()
    assert client.get("/v1/tracks/search", params={"q": "Playground"}).json()["results"] == []
    assert discogs.urls == []


def test_si_musicbrainz_encuentra_la_cancion_discogs_no_se_consulta(monkeypatch):
    rec = {"id": REC, "title": "Vinotinto", "score": 100, "length": 559000,
           "artist-credit": [{"name": "Luciano", "joinphrase": "", "artist": {"id": LUCIANO_MB, "name": "Luciano"}}]}
    discogs = Discogs([hit(29565955)], {29565955: VINOTINTO})
    client, _ = make(monkeypatch, discogs, MB(recordings=[rec]))
    [res] = client.get("/v1/tracks/search", params={"q": "Luciano Vinotinto"}).json()["results"]
    assert res["mbid"] == REC and res["catalog"] == "musicbrainz" and discogs.urls == []


def test_fallo_del_proveedor_no_rompe_la_busqueda_y_la_ficha_responde_503(monkeypatch):
    client, _ = make(monkeypatch, Discogs(fail=urllib.error.URLError("down")))
    r = client.get("/v1/tracks/search", params={"q": "Luciano Vinotinto"})
    assert r.status_code == 200 and r.json()["results"] == []
    r = client.get("/v1/tracks/ext/discogs:29565955:1")
    assert r.status_code == 503 and r.json()["error"]["code"] == "provider_unavailable"


# --- Ficha e identidad --------------------------------------------------------------------------------------------
def test_identidad_externa_validada_y_rutas_mbid_intactas(monkeypatch):
    client, mb = make(monkeypatch, Discogs(releases={29565955: VINOTINTO}))
    assert client.get("/v1/tracks/ext/discogs:29565955:9").status_code == 404, "posición inexistente"
    assert client.get("/v1/tracks/ext/discogs:1:1").status_code == 404, "lanzamiento inexistente"
    for bad in ("29565955", "isrc:QM4TW2437510", "discogs:abc:1", f"discogs:{REC}"):
        assert client.get(f"/v1/tracks/ext/{bad}").status_code == 404
    # /tracks/{mbid} sigue aceptando solo MBID: un ID externo no se cuela en la ruta de MusicBrainz.
    assert client.get("/v1/tracks/discogs:29565955:1").status_code == 422
    assert mb.urls == []


def test_artista_homonimo_o_ambiguo_queda_sin_enlace(monkeypatch):
    links = {"https://www.discogs.com/artist/6362": [LUCIANO_MB, "22222222-2222-4222-8222-222222222222"]}
    client, _ = make(monkeypatch, Discogs(releases={29565955: VINOTINTO}), MB(links=links))
    d = client.get("/v1/tracks/ext/discogs:29565955:1").json()
    assert d["main_artist"] is None and d["artist_credit"][0]["mbid"] == "discogs:artist:6362"


def test_recopilatorio_no_presta_su_genero_y_cache_de_seis_horas(monkeypatch):
    comp = {**EP, "id": 500, "formats": [{"name": "File", "descriptions": ["Compilation"]}]}
    discogs = Discogs(releases={500: comp})
    client, _ = make(monkeypatch, discogs)
    d = client.get("/v1/tracks/ext/discogs:500:A1").json()
    traits = {t["key"]: t for t in d["dna"]["traits"]}
    assert traits["genre"]["status"] == "unavailable" and d["original_release"]["secondary_types"] == ["Compilation"]
    assert traits["label"]["values"] == ["Satya"], "sin el número de desambiguación de Discogs"
    client.get("/v1/tracks/ext/discogs:500:A1")
    assert len(discogs.urls) == 1 and dt.TTL_S == 6 * 3600


def test_ep_de_varias_canciones_no_reparte_estilos_de_familias_distintas(monkeypatch):
    # Caso real: Dedust EP (Traumer, Desolat, release 5925531): 8 canciones, «Techno, House, Tech House» y sin duraciones.
    dedust = {**EP, "id": 600, "title": "Dedust EP", "genres": ["Electronic"], "styles": ["Techno", "House", "Tech House"],
              "tracklist": [{"position": "A1", "type_": "track", "title": "Hoodlum", "duration": ""},
                            {"position": "A2", "type_": "track", "title": "Insola", "duration": ""}]}
    single_song = {**dedust, "id": 601, "tracklist": [{"position": "A1", "type_": "track", "title": "Hoodlum", "duration": ""},
                                                      {"position": "B1", "type_": "track", "title": "Hoodlum (Dub)", "duration": ""}]}
    client, _ = make(monkeypatch, Discogs(releases={600: dedust, 601: single_song}))
    genre = lambda tid: next(t for t in client.get(f"/v1/tracks/ext/{tid}").json()["dna"]["traits"] if t["key"] == "genre")  # noqa: E731
    assert genre("discogs:600:A1")["values"] == ["Electrónica"], "solo el género amplio del lanzamiento"
    assert genre("discogs:601:A1")["values"] == ["Techno", "House", "Tech House"], "una sola canción (y su dub): sus estilos"


def test_funciones_puras():
    assert dt.parse_duration("9:19") == 559000 and dt.parse_duration("1:02:03") == 3723000
    assert dt.parse_duration("") is None and dt.parse_duration(None) is None
    assert dt.release_date({"released": "2024-00-00"}) == "2024" and dt.release_date({"year": 2019}) == "2019"
    assert dt.track_id(1, "A1") == "discogs:1:A1" and dt.track_id(1, "A 1") is None
