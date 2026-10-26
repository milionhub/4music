"""Catálogo externo (V5.6): canciones de Discogs ausentes de MusicBrainz, sin red y sin coincidencias dudosas."""

import urllib.error
from urllib.parse import parse_qs, urlsplit

import pytest
from fastapi.testclient import TestClient

from app import discogs_tracks as dt, schemas
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
    # Una sola petición del lanzamiento (la búsqueda de contexto, V6.6, va aparte y sin el sello del recopilatorio).
    assert sum("/releases/" in u for u in discogs.urls) == 1 and dt.TTL_S == 6 * 3600
    assert not any("label=" in u for u in discogs.urls)


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


# --- V6.2: género de una pista de MusicBrainz o Deezer desde Discogs ------------------------------------------------
def test_genero_de_la_misma_pista_en_discogs_nunca_de_un_remix_ni_de_un_dj_mix(monkeypatch):
    from app import deezer, schemas
    fake = Discogs(search=[hit(300), hit(200, master=9)], releases={200: EP, 300: DJ_MIX})
    monkeypatch.setattr(dt, "_default_transport", fake)
    found = dt.genre_for("rec-1", "Arapu", "Night Groove (Original Mix)", 431000)
    trait = found[0]
    assert trait.scope == "release" and trait.values and "Discogs" in trait.detail
    # «Minimal, Tech House»: Minimal convive con el house (no mezcla familias) y queda como estilo.
    assert trait.values == ["House", "Minimal", "Tech House"]
    assert trait.sources[0].url.startswith("https://www.discogs.com/release/200")
    # Otro remix (no está en el EP), otra duración u otro artista: nada.
    assert dt.genre_for("rec-2", "Arapu", "Night Groove (Otro Remix)", None) == []
    assert dt.genre_for("rec-3", "Arapu", "Night Groove", 300000) == []
    assert dt.genre_for("rec-4", "Priku", "Night Groove", 431000) == []
    # Segunda vez: solo el lanzamiento guardado (sin volver a buscar).
    before = len(fake.urls)
    assert dt.genre_for("rec-1", "Arapu", "Night Groove", 431000) == found
    assert not any("/database/search" in u for u in fake.urls[before:])
    # Nunca pisa un género que ya existe; el BPM de Deezer, tampoco un tempo medido.
    dna = schemas.TrackDna(recording_mbid="rec-1", traits=[
        schemas.DnaTrait(key="genre", group="classification", label="Género", status="unavailable"),
        schemas.DnaTrait(key="bpm", group="acoustic", label="BPM", status="unavailable")])
    assert dt.with_genre(dna, found).traits[0] == trait
    # Un género concreto nunca se pisa; «Electrónica» sí cede ante uno concreto.
    concrete = dna.model_copy(update={"traits": [dna.traits[0].model_copy(update={"status": "community", "values": ["Techno"]})]})
    assert dt.with_genre(concrete, found) == concrete
    broad = dna.model_copy(update={"traits": [dna.traits[0].model_copy(update={"status": "community", "values": ["Electrónica"]})]})
    assert dt.with_genre(broad, found).traits[0] == trait and dt.needs_genre(broad) and not dt.needs_genre(concrete)
    assert [t.values for t in deezer.with_tempo(dna, 124.6).traits] == [[], ["125"]]
    assert deezer.with_tempo(dna, 0) == dna and deezer.with_tempo(dna, 240) == dna, "0 = sin calcular; 240, octava"
    measured = deezer.with_tempo(dna, 124)
    assert deezer.with_tempo(measured, 130) == measured



def test_ep_que_mezcla_familias_da_estilos_del_lanzamiento_no_de_la_pista():
    from app import tracks
    mixed_ep = {**EP, "styles": ["Techno", "House", "Tech House"],
                "tracklist": [{"position": "A1", "type_": "track", "title": "Night Groove", "duration": "7:10"},
                              {"position": "A2", "type_": "track", "title": "Otra", "duration": "6:00"}]}
    traits = dt.release_genre(mixed_ep)
    assert [t.key for t in traits] == ["genre", "release_styles"]
    assert traits[0].values == ["Electrónica"] and traits[1].values == ["Techno", "House", "Tech House"]
    assert tracks.genre_values(["minimal"]) == ["Minimal"]
    assert tracks.genre_values(["minimal", "deep house"]) == ["House", "Minimal", "Deep House"]


def test_v64_contexto_de_sello_y_artista_confirmado_en_cada_resultado(monkeypatch):
    results = ([{"id": i, "label": ["Solid Grooves Records"], "style": ["Tech House", "Minimal"], "title": "PAWSA - X"} for i in range(6)]
               + [{"id": 9, "label": ["Otro Sello"], "style": ["Trance"], "title": "Otro - Y"}] * 10)

    class Fake:
        def __call__(self, url):
            return {"results": results}
    monkeypatch.setattr(dt, "_default_transport", Fake())
    ctx = {t.key: t for t in dt.context_traits("Solid Grooves Records", "PAWSA")}
    assert ctx["label_styles"].values == ["Minimal", "Tech House"] or ctx["label_styles"].values == ["Tech House", "Minimal"]
    assert ctx["label_styles"].scope == "label" and "no una clasificación" in ctx["label_styles"].detail
    assert "Trance" not in ctx["artist_sound"].values, "solo los resultados del propio artista"
    assert dt.context_traits("Not On Label", None) == []
    # Sello homónimo: ningún lanzamiento del artista en él, sin contexto de sello.
    assert all(t.key != "label_styles" for t in dt.context_traits("Solid Grooves Records", "Chris Stassy"))


def _ctx(key, values, scope):
    ref = schemas.SourceRef(label="Discogs", url=f"https://www.discogs.com/{key}", license="CC0")
    return schemas.DnaTrait(key=key, group="context", label=key, status="community", scope=scope, values=values,
                            sources=[ref])


def test_v65_genero_deducido_de_artista_y_sello():
    none = schemas.DnaTrait(key="genre", group="classification", label="Género", status="unavailable")
    artist = _ctx("artist_sound", ["Tech House", "Techno", "Minimal"], "artist")
    label = _ctx("label_styles", ["Minimal", "Tech House"], "label")
    # Comparten estilos: esos, con una sola familia y el comodín como estilo.
    g = dt.with_inferred_genre(schemas.TrackDna(recording_mbid="x", traits=[none, artist, label])).traits[0]
    assert g.key == "genre" and g.values == ["House", "Tech House", "Minimal"] and g.scope == "label"
    assert "no clasifica esta pista" in g.detail and len(g.sources) == 2
    # Solo el artista: su estilo principal y los de su familia, nunca mezcla House y Techno.
    g = dt.with_inferred_genre(schemas.TrackDna(recording_mbid="x", traits=[none, artist])).traits[0]
    assert g.values == ["House", "Tech House", "Minimal"] and g.scope == "artist"
    # Wikidata del artista si Discogs no da nada; «Electrónica» sola no basta.
    wd = _ctx("artist_style", ["Deep House"], "artist")
    assert dt.with_inferred_genre(schemas.TrackDna(recording_mbid="x", traits=[wd])).traits[0].values == ["House", "Deep House"]
    broad = _ctx("artist_style", ["Electronic"], "artist")
    assert dt.with_inferred_genre(schemas.TrackDna(recording_mbid="x", traits=[none, broad])).traits[0] == none
    # Nunca pisa un género concreto.
    own = none.model_copy(update={"status": "community", "values": ["Techno"]})
    assert dt.with_inferred_genre(schemas.TrackDna(recording_mbid="x", traits=[own, artist])).traits[0] == own
