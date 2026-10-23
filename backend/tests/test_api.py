"""Contrato /v1 sin red: clientes de MusicBrainz, Wikimedia y ListenBrainz con un transporte falso inyectado."""

import json
from urllib.parse import parse_qs, urlsplit

import pytest
from fastapi.testclient import TestClient

from app import config, store
from app.api import get_client, get_groq_client, get_labs_client, get_lb_client, get_wiki_client
from app.groq_client import GroqClient
from app.main import app
from app.musicbrainz import LabsClient, ListenBrainzClient, MusicBrainzClient, WikimediaClient
from tests.fixtures import mb


class FakeTransport:
    """Responde según la ruta pedida; registra las URL y cabeceras para comprobar qué se consulta."""

    def __init__(self, routes: dict[str, tuple[object, object]]):
        self.routes = routes
        self.urls: list[str] = []
        self.headers: list[dict] = []

    def __call__(self, url, headers, timeout):
        self.urls.append(url)
        self.headers.append(headers)
        assert headers["User-Agent"] == "music-discovery/0.1 ( test@example.org )"
        parts = urlsplit(url)
        q = {k: v[0] for k, v in parse_qs(parts.query).items()}
        if "wikidata.org" in parts.netloc:
            key = f"wdsearch:{q['srsearch'].rsplit('=', 1)[1]}" if "srsearch" in q else f"wd:{q['ids']}"
        elif "wikipedia.org" in parts.netloc:
            key = "wp:" + q.get("titles", "")
        elif "commons.wikimedia.org" in parts.netloc:
            key = (f"commons-search:{q['srsearch']}" if "srsearch" in q
                   else f"commons-mediainfo:{q['titles']}" if q.get("action") == "wbgetentities"
                   else f"commons:{q['titles']}")
        elif parts.netloc.startswith("labs."):
            key = f"labs:{q['artist_mbids']}"
        elif "listenbrainz.org" in parts.netloc:
            key = "lb:" + parts.path.rstrip("/").rsplit("/", 1)[1]
        else:
            path = parts.path.split("/ws/2/", 1)[1]
            if path == "release":
                key = f"release:{q.get('artist') or 'label=' + q['label']}"
            else:
                key = f"{path}:{q['artist']}" if path in ("recording", "release-group") else path
        status, body = self.routes.get(key, (404, None))
        if isinstance(status, Exception):
            raise status
        return status, json.dumps(body).encode() if body is not None else b"", None


COMMONS_KEY = "commons:File:Seed Artist 2022.jpg"
ROUTES = {
    "artist": (200, mb.SEARCH),
    f"artist/{mb.SEED}": (200, mb.SEED_ARTIST),
    f"artist/{mb.SEED_EMPTY}": (200, mb.EMPTY_ARTIST),
    f"recording:{mb.SEED}": (200, mb.SEED_RECORDINGS),
    f"recording:{mb.SEED_EMPTY}": (200, mb.EMPTY_RECORDINGS),
    f"release-group:{mb.SEED}": (200, mb.SEED_RELEASE_GROUPS),
    f"release-group:{mb.SEED_EMPTY}": (200, {"release-group-count": 0, "release-groups": []}),
    f"wd:{mb.QID}": (200, mb.wikidata_entity()),
    f"wd:{mb.OCCUPATION}|{mb.GENRE}": (200, mb.LABELS),
    f"wdsearch:{mb.SEED_EMPTY}": (200, {"query": {"search": []}}),
    "wdsearch:BE": (200, mb.COUNTRY_SEARCH),  # país ISO de MusicBrainz → ítem de Wikidata (P297)
    f"wd:{mb.COUNTRY_QID}": (200, mb.COUNTRY_ENTITY),
    COMMONS_KEY: (200, mb.commons_file()),
    f"lb:{mb.SEED}": (200, mb.LB_ITEMS),
    f"labs:{mb.SEED}": (200, [{"artist_mbid": mb.CO_B, "name": "Co B", "score": 80, "comment": "techno", "type": "Person"}]),
    f"release:{mb.SEED}": (200, {"releases": [
        {"title": "Joint 1", "date": "2024", "artist-credit": mb.credit((mb.SEED, "Seed Artist"), (mb.CO_A, "Co A")),
         "label-info": []},
        {"title": "Feat once", "date": "2024", "artist-credit": mb.credit((mb.SEED, "Seed Artist"), (mb.SPOUSE, "Guest")),
         "label-info": []},
        {"title": "Joint 2", "date": "2025", "artist-credit": mb.credit((mb.SEED, "Seed Artist"), (mb.CO_A, "Co A")),
         "label-info": []}]}),
    f"release:{mb.SEED_EMPTY}": (200, {"releases": []}),
}


def make_client(routes=None, contact="test@example.org", lb_token="tok"):
    transport = FakeTransport(dict(ROUTES if routes is None else routes))
    no_sleep = {"transport": transport, "sleep": lambda s: None}
    clients = (MusicBrainzClient(contact, **no_sleep), WikimediaClient(contact, **no_sleep),
               ListenBrainzClient(contact, lb_token, **no_sleep), LabsClient(contact, **no_sleep))
    app.dependency_overrides[get_client] = lambda: clients[0]
    app.dependency_overrides[get_wiki_client] = lambda: clients[1]
    app.dependency_overrides[get_lb_client] = lambda: clients[2]
    app.dependency_overrides[get_labs_client] = lambda: clients[3]
    app.dependency_overrides[get_groq_client] = lambda: GroqClient("", "")  # sin Groq salvo en test_biography
    return TestClient(app), transport


@pytest.fixture(autouse=True)
def _reset_overrides(monkeypatch):
    monkeypatch.delenv("COVER_ART", raising=False)
    yield
    app.dependency_overrides.clear()


def test_search_returns_disambiguated_candidates():
    client, transport = make_client()
    r = client.get("/v1/artists/search", params={"q": "traumer"})
    assert r.status_code == 200
    body = r.json()
    assert [x["disambiguation"] for x in body["results"]] == ["house/techno", "Brazilian Power Metal Band"]
    assert body["results"][1]["country"] is None  # ausente en la fuente: null, no inventado
    assert "query=traumer" in transport.urls[0]


def test_search_escapes_lucene_and_validates_query():
    client, transport = make_client()
    client.get("/v1/artists/search", params={"q": "C++ [A:RPIA:R]"})
    assert "C%5C%2B%5C%2B" in transport.urls[0]
    for bad in ({"q": ""}, {"q": "x" * 101}, {"q": "ok", "limit": "0"}, {"q": "ok", "limit": "abc"}):
        r = client.get("/v1/artists/search", params=bad)
        assert r.status_code == 422 and r.json()["error"]["code"] == "invalid_query"


def test_profile_contract_all_modules():
    client, transport = make_client()
    body = client.get(f"/v1/artists/{mb.SEED}").json()
    a = body["artist"]
    assert (a["name"], a["country"], a["area"]) == ("Seed Artist", "BE", "Belgium")
    # Identidad: país legible (Wikidata P297); el área es el propio país; nacimiento (1990) nunca como «desde».
    assert body["identity"] == {"country_name": "Bélgica", "area": None, "origin": None, "origin_kind": None,
                                "formed_year": None, "active_since": None, "founded_labels": [], "run_labels": [], "label_years": {}, "projects": ["The Band"],
                                "members": []}

    # Foto: relación de Wikidata verificada por P434, con licencia y autoría.
    assert body["image"]["license"] == "CC BY-SA 4.0" and body["image"]["via"] == "wikidata_p18"
    # Estilos: solo P136 de Wikidata (CC0), con etiqueta.
    assert body["styles"] == [{"label": "tech house", "qid": mb.GENRE, "source": "wikidata"}]
    # Biografía: sin entrada editorial → descripción factual breve con sus fuentes.
    # Sin biografía generada ni editorial: solo identidad verificada (Wikidata), nunca discografía.
    assert body["bio"] == {**body["bio"], "kind": "factual", "text": "Disc-jockey de tech house."}
    assert body["bio_pending"] is False  # sin Groq configurado en make_client
    assert "tech house" in body["bio"]["text"] and {s["license"] for s in body["bio"]["sources"]} == {"CC0"}

    # Más escuchadas: orden real de ListenBrainz; versiones equivalentes fusionadas; remix aparte; portada CAA.
    tracks = body["top_tracks"]
    assert [t["title"] for t in tracks] == ["Hit (Extended Mix)", "Hit (Co A Remix)", "Deep Cut"]
    assert [t["listen_count"] for t in tracks] == [900, 700, 50]
    assert tracks[0]["cover_url"].startswith("https://coverartarchive.org/release/") and tracks[1]["cover_url"] is None
    assert body["top_tracks_status"]["status"] == "ok"
    assert any(h.get("Authorization") == "Token tok" for h in transport.headers)

    # Lanzamientos recientes: propios, con fecha, sin recopilatorios/DJ-mix, por fecha de publicación.
    assert [r["title"] for r in body["recent_releases"]] == ["Joint Single", "Old EP"]
    assert body["recent_releases"][0]["with_artists"] == ["Co A"]
    assert body["recent_releases"][0]["url"].startswith("https://musicbrainz.org/release-group/")

    # Colaboraciones: lanzamiento conjunto primero; nunca «Various Artists» ni relaciones personales.
    assert body["highlights_title"] == "collaborations"
    assert [(h["artist"]["name"], h["kind"]) for h in body["highlights"]] == [("Co A", "joint_release"), ("Co B", "co_credit")]
    assert body["highlights"][0]["reason"] == "Lanzamiento conjunto: «Joint Single»"

    # Plataformas: solo enlaces musicales destacados, sin duplicados.
    assert [l["label"] for l in body["platforms"]] == ["Spotify", "SoundCloud", "Beatport", "Apple Music", "Qobuz"]
    assert {s["label"] for s in body["sources"]} >= {"MusicBrainz", f"Wikidata {mb.QID}", "Foto"}


def test_profile_summary_is_the_cached_wikipedia_intro_with_attribution():
    """Carteles 3.5B: introducción literal (párrafos incluidos) del ítem verificado, sin peticiones de más."""
    intro = "Seed Artist is a Belgian DJ and producer known for tech house.\nThe artist grew up in Antwerp and plays long sets."
    wiki = {"query": {"pages": {"1": {"title": "Seed Artist", "extract": intro}}}}
    client, transport = make_client({**ROUTES, "wp:Seed Artist": (200, wiki)})
    body = client.get(f"/v1/artists/{mb.SEED}").json()
    assert body["summary"] == {"text": intro, "language": "en", "source": {
        "label": "Wikipedia (en)", "url": "https://en.wikipedia.org/wiki/Seed_Artist", "license": "CC BY-SA 4.0"}}
    assert sum("exintro=1" in u for u in transport.urls) == 1  # la misma petición que los géneros (en caché)

    client, _ = make_client()  # sin artículo disponible: sin extracto
    assert client.get(f"/v1/artists/{mb.SEED}").json()["summary"] is None


def test_profile_degrades_per_module_without_blocking():
    routes = {**ROUTES, f"recording:{mb.SEED}": (503, None), f"release-group:{mb.SEED}": (503, None),
              f"wd:{mb.QID}": (503, None), f"lb:{mb.SEED}": (503, None)}
    client, _ = make_client(routes)
    r = client.get(f"/v1/artists/{mb.SEED}")
    assert r.status_code == 200  # solo la identidad es imprescindible
    body = r.json()
    assert body["artist"]["name"] == "Seed Artist"
    assert body["image"] is None and body["image_reason"] == "unavailable"
    assert body["bio"] is None and body["styles"] == []
    for key in ("top_tracks_status", "releases_status", "recordings_status"):
        assert body[key] == {**body[key], "status": "error", "error_code": "provider_unavailable"}
    assert body["highlights"] == [] or body["highlights_title"] == "connections"  # solo relaciones de la ficha


def test_profile_without_listenbrainz_token_makes_no_request():
    client, transport = make_client(lb_token="")
    body = client.get(f"/v1/artists/{mb.SEED}").json()
    assert body["top_tracks"] == []
    assert body["top_tracks_status"]["error_code"] == "listenbrainz_token_required"
    assert not any("listenbrainz.org" in u for u in transport.urls)


def test_profile_without_wikidata_item_and_empty_sources():
    client, _ = make_client()
    body = client.get(f"/v1/artists/{mb.SEED_EMPTY}").json()
    assert body["image"] is None and body["image_reason"] == "no_wikidata_item"
    assert (body["bio"], body["styles"], body["recent_releases"], body["highlights"]) == (None, [], [], [])
    assert body["releases_status"]["status"] == "empty" and body["platforms"] == []


def test_cover_art_can_be_disabled(monkeypatch):
    monkeypatch.setenv("COVER_ART", "off")
    assert config.cover_art_enabled() is False
    client, _ = make_client()
    body = client.get(f"/v1/artists/{mb.SEED}").json()
    assert all(r["cover_url"] is None for r in body["recent_releases"])
    assert all(t["cover_url"] is None for t in body["top_tracks"])


def test_artist_image_verified_by_mbid_with_attribution():
    client, _ = make_client()
    img = client.get(f"/v1/artists/{mb.SEED}/image").json()["image"]
    assert img["url"] == "https://upload.wikimedia.org/thumb/seed.jpg/640px-seed.jpg"
    assert (img["license"], img["author"], img["wikidata_id"]) == ("CC BY-SA 4.0", "Ph & Co", mb.QID)


def test_artist_image_prefers_musicbrainz_image_relation():
    artist = {**mb.SEED_ARTIST, "relations": mb.SEED_ARTIST["relations"] + [
        mb.url_rel("image", "https://commons.wikimedia.org/wiki/File:Seed_On_Stage.jpg")]}
    routes = {**ROUTES, f"artist/{mb.SEED}": (200, artist), "commons:File:Seed On Stage.jpg": (200, mb.commons_file())}
    client, _ = make_client(routes)
    assert client.get(f"/v1/artists/{mb.SEED}/image").json()["image"]["via"] == "musicbrainz_image"


def test_artist_image_found_by_reverse_p434_search():
    no_link = {**mb.SEED_ARTIST, "relations": [r for r in mb.SEED_ARTIST["relations"] if r.get("type") != "wikidata"]}
    routes = {**ROUTES, f"artist/{mb.SEED}": (200, no_link),
              f"wdsearch:{mb.SEED}": (200, {"query": {"search": [{"title": mb.QID}]}})}
    client, _ = make_client(routes)
    img = client.get(f"/v1/artists/{mb.SEED}/image").json()["image"]
    assert img["wikidata_id"] == mb.QID


@pytest.mark.parametrize("override, reason", [
    ({f"artist/{mb.SEED}": (200, {**mb.SEED_ARTIST, "relations": []})}, "no_wikidata_item"),
    ({f"wd:{mb.QID}": (200, mb.wikidata_entity(p434=(mb.CO_A,)))}, "mbid_mismatch"),  # homónimo: no hay foto
    ({f"wd:{mb.QID}": (200, mb.wikidata_entity(p18=()))}, "no_image"),
    ({COMMONS_KEY: (200, mb.commons_file(license_name="CC BY-NC 2.0"))}, "license_not_allowed"),
    ({COMMONS_KEY: (200, mb.commons_file(author=""))}, "license_not_allowed"),
    ({COMMONS_KEY: (503, None)}, "unavailable"),
])
def test_artist_image_rejections(override, reason):
    routes = {**ROUTES, f"wdsearch:{mb.SEED}": (200, {"query": {"search": []}}), **override}
    client, _ = make_client(routes)
    body = client.get(f"/v1/artists/{mb.SEED}/image").json()
    assert (body["image"], body["reason"]) == (None, reason)


def test_discovery_uses_affinity_and_repeated_collaboration_not_one_off_credits():
    client, _ = make_client()
    r = client.get("/v1/discovery", params={"seeds": f"{mb.SEED},{mb.SEED_EMPTY}"})
    assert r.status_code == 200
    body = r.json()
    got = [(c["artist"]["name"], c["kind"]) for c in body["cards"]]
    assert got == [("Co B", "affinity"), ("Co A", "collaboration")]  # «Guest» (1 crédito) no aparece
    assert body["cards"][0]["tag"] == "Afinidad de escucha"
    assert body["cards"][1]["headline"] == "Lanzamientos junto a Seed Artist"
    assert body["seeds_without_results"] == [mb.SEED_EMPTY] and body["seeds_failed"] == []
    assert any("Labs" in s["label"] for s in body["sources"])


def test_discovery_survives_one_source_failing():
    routes = {**ROUTES, f"release:{mb.SEED}": (503, None)}  # MusicBrainz cae: queda la afinidad de Labs
    client, _ = make_client(routes)
    body = client.get("/v1/discovery", params={"seeds": mb.SEED}).json()
    assert [c["artist"]["name"] for c in body["cards"]] == ["Co B"]
    assert body["cards"][0]["reasons"][0]["seed_name"] == "tu favorito"  # sin nombre verificado: texto neutro
    client, _ = make_client({f"release:{mb.SEED}": (503, None), f"labs:{mb.SEED}": (503, None)})
    r = client.get("/v1/discovery", params={"seeds": mb.SEED})
    assert r.status_code == 503 and r.json()["error"]["code"] == "provider_unavailable"


def test_validation_and_error_codes():
    client, _ = make_client()
    cases = [
        ("/v1/artists/not-a-uuid", 422, "invalid_mbid"),
        ("/v1/artists/not-a-uuid/image", 422, "invalid_mbid"),
        ("/v1/discovery?seeds=", 422, "invalid_query"),
        ("/v1/discovery?seeds=xyz", 422, "invalid_mbid"),
        (f"/v1/artists/{mb.CO_A}", 404, "not_found"),
        (f"/v1/artists/{mb.CO_A}/image", 404, "not_found"),
    ]
    for url, status, code in cases:
        r = client.get(url)
        assert (r.status_code, r.json()["error"]["code"]) == (status, code), url
    client, _ = make_client({f"artist/{mb.SEED}": (200, "not an object")})
    r = client.get(f"/v1/artists/{mb.SEED}")
    assert (r.status_code, r.json()["error"]["code"]) == (502, "provider_bad_response")


def test_not_configured_contact():
    client, transport = make_client(contact="")
    r = client.get("/v1/artists/search", params={"q": "x"})
    assert (r.status_code, r.json()["error"]["code"]) == (503, "provider_not_configured")
    assert transport.urls == []


def test_health_unchanged():
    assert TestClient(app).get("/health").json() == {"status": "ok"}


def test_profile_identity_places_by_artist_type():
    group = mb.artist(mb.CO_B, "Duo", type="Group", country="DE", area={"name": "Berlin", "type": "City"},
                      **{"begin-area": {"name": "Hamburg"}, "life-span": {"begin": "2004"}})
    routes = {**ROUTES, f"artist/{mb.CO_B}": (200, group), "wdsearch:DE": (503, None),
              f"wdsearch:{mb.CO_B}": (200, {"query": {"search": []}})}
    client, _ = make_client(routes)
    ident = client.get(f"/v1/artists/{mb.CO_B}").json()["identity"]
    # Área (ciudad) y origen (formación) se presentan por separado; sin nombre de país si Wikimedia falla.
    assert ident == {"country_name": None, "area": "Berlin", "origin": "Hamburg", "origin_kind": "formation",
                     "formed_year": "2004", "active_since": None, "founded_labels": [], "run_labels": [], "label_years": {}, "projects": [], "members": []}
    assert store.get("country", "DE") is None  # el fallo temporal no se guarda
    nobody = mb.artist(mb.CO_A, "Unknown type", type=None, **{"begin-area": {"name": "Leeds"}})
    client, _ = make_client({**ROUTES, f"artist/{mb.CO_A}": (200, nobody),
                             f"wdsearch:{mb.CO_A}": (200, {"query": {"search": []}})})
    ident = client.get(f"/v1/artists/{mb.CO_A}").json()["identity"]
    assert ident["origin"] is None and ident["country_name"] == "Bélgica"  # sin tipo: begin-area ambiguo, no se usa
