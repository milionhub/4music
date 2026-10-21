"""TrackDNA de canciones (T2.0) sin red: búsqueda, ficha, ADN sin métricas inventadas, IA con validación y caché."""

import json
from urllib.parse import parse_qs, urlsplit

import pytest
from fastapi.testclient import TestClient

from app import track_ai, tracks
from app.api import get_client, get_groq_client, get_wiki_client
from app.groq_client import GroqClient
from app.main import app
from app.musicbrainz import MusicBrainzClient, WikimediaClient
from app.wikidata import WikidataInfo

ART = "11111111-1111-4111-8111-111111111111"
HOMONYM = "22222222-2222-4222-8222-222222222222"
REMIXER = "33333333-3333-4333-8333-333333333333"
REC = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
REC_DUP = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
REC_REMIX = "cccccccc-cccc-4ccc-8ccc-cccccccccccc"
REC_LIVE = "dddddddd-dddd-4ddd-8ddd-dddddddddddd"
REC_FRAGMENT = "eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee"
REC_HOMONYM = "ffffffff-ffff-4fff-8fff-ffffffffffff"
RG_ALBUM = "a1a1a1a1-a1a1-4a1a-8a1a-a1a1a1a1a1a1"
RG_COMP = "c2c2c2c2-c2c2-4c2c-8c2c-c2c2c2c2c2c2"
GENRE = "Q20502"


def credit(*artists):
    return [{"name": n, "joinphrase": "", "artist": {"id": i, "name": n, "disambiguation": d}} for i, n, d in artists]


ME = (ART, "Seed Artist", "house producer")
release_album = {"id": "r-album-1", "title": "First Album", "status": "Official", "date": "2019",
                 "artist-credit": credit(ME), "release-group": {"id": RG_ALBUM, "title": "First Album", "primary-type": "Album"},
                 "label-info": [{"label": {"name": "Deep Label"}, "catalog-number": "DL001"}],
                 "cover-art-archive": {"front": False}, "media": [{"format": "Vinyl"}], "barcode": "5054288375188",
                 "relations": [
                     {"target-type": "url", "type": "purchase for download",
                      "url": {"resource": "https://seedartist.bandcamp.com/album/first-album"}},
                     {"target-type": "url", "type": "discogs", "url": {"resource": "https://www.discogs.com/release/818516"}},
                     {"target-type": "url", "type": "streaming", "url": {"resource": "https://open.spotify.com/track/abc"}}]}
release_album_digital = {**release_album, "id": "r-album-2", "date": "2019-05-03", "cover-art-archive": {"front": True},
                         "media": [{"format": "Digital Media"}], "label-info": [{"label": {"name": "[no label]"}}]}
release_comp = {"id": "r-comp", "title": "Club Hits", "status": "Official", "date": "2018",
                "artist-credit": credit(("89ad4ac3-39f7-470e-963a-56509c546377", "Various Artists", "")),
                "release-group": {"id": RG_COMP, "title": "Club Hits", "primary-type": "Album",
                                  "secondary-types": ["Compilation", "DJ-mix"]},
                "label-info": [{"label": {"name": "Big Comp"}}], "cover-art-archive": {"front": True}, "barcode": "999",
                "relations": [{"target-type": "url", "type": "purchase for download",
                               "url": {"resource": "https://www.beatport.com/release/club-hits/123"}}]}
NO_LABEL_INFO = [{"label": {"id": tracks.NO_LABEL, "name": "[no label]"}}]

SEARCH = {"count": 6, "recordings": [
    {"id": REC_FRAGMENT, "score": 100, "title": "Night Drive", "artist-credit": credit(ME), "length": 90000,
     "disambiguation": "part of “Club Hits” DJ‐mix", "releases": [release_comp]},
    {"id": REC_DUP, "score": 100, "title": "Night Drive", "artist-credit": credit(ME), "length": 361500,
     "releases": [release_comp]},
    {"id": REC, "score": 95, "title": "Night Drive", "artist-credit": credit(ME), "length": 360000,
     "first-release-date": "2019", "releases": [release_album, release_album_digital]},
    {"id": REC_REMIX, "score": 90, "title": "Night Drive (Other remix)", "artist-credit": credit(ME), "length": 400000,
     "releases": [release_album]},
    {"id": REC_LIVE, "score": 90, "title": "Night Drive", "artist-credit": credit(ME), "length": 420000,
     "disambiguation": "live, 2021-01-01: Club", "releases": [release_album]},
    {"id": REC_HOMONYM, "score": 99, "title": "Night Drive", "artist-credit": credit((HOMONYM, "Seed Artist", "rock band")),
     "length": 200000, "releases": []},
    {"id": "99999999-9999-4999-8999-999999999999", "score": 80, "title": "Unrelated", "artist-credit": credit(ME),
     "releases": []},
]}

RECORDING = {
    "id": REC, "title": "Night Drive", "length": 360000, "first-release-date": "2019-05-03", "video": False,
    "artist-credit": credit(ME), "isrcs": ["GBXXX1900001", "GBXXX1900001"],
    "relations": [
        {"target-type": "artist", "type": "producer", "direction": "backward", "artist": {"id": ART, "name": "Seed Artist"}},
        {"target-type": "artist", "type": "engineer", "direction": "backward", "artist": {"id": ART, "name": "Seed Artist"}},
        {"target-type": "work", "type": "performance", "direction": "forward", "work": {"title": "Night Drive", "relations": [
            {"target-type": "artist", "type": "composer", "direction": "backward", "artist": {"id": REMIXER, "name": "Real Name"}}]}},
        {"target-type": "recording", "type": "remix", "direction": "backward",
         "recording": {"id": REC_REMIX, "title": "Night Drive (Other remix)", "artist-credit": credit(ME), "length": 400000}},
        {"target-type": "recording", "type": "DJ-mix", "direction": "backward",
         "recording": {"id": REC_FRAGMENT, "title": "Night Drive", "disambiguation": "part of “Club Hits” DJ‐mix",
                       "artist-credit": credit(ME)}},
        {"target-type": "recording", "type": "DJ-mix", "direction": "backward",
         "recording": {"id": "12121212-1212-4212-8212-121212121212", "title": "Radio Show 100", "artist-credit": credit(ME)}},
        {"target-type": "url", "type": "streaming", "url": {"resource": "https://open.spotify.com/track/abc"}},
    ]}
REMIX_RECORDING = {
    "id": REC_REMIX, "title": "Night Drive (Other remix)", "length": 400000, "artist-credit": credit(ME),
    "relations": [
        {"target-type": "artist", "type": "remixer", "direction": "backward", "artist": {"id": REMIXER, "name": "Other"}},
        {"target-type": "recording", "type": "remix", "direction": "forward",
         "recording": {"id": REC, "title": "Night Drive", "artist-credit": credit(ME), "length": 360000}}]}
ARTIST = {"id": ART, "name": "Seed Artist", "relations": [
    {"target-type": "url", "type": "wikidata", "url": {"resource": "https://www.wikidata.org/wiki/Q500"}}]}
ALBUM_ENTITY = {"entities": {"Q100": {"claims": {
    "P436": [{"mainsnak": {"datavalue": {"value": RG_ALBUM}}}],
    "P136": [{"mainsnak": {"datavalue": {"value": {"id": GENRE}}}}]},
    "sitelinks": {"enwiki": {"title": "First Album"}}}}}
ARTIST_ENTITY = {"entities": {"Q500": {"claims": {"P434": [{"mainsnak": {"datavalue": {"value": ART}}}]}, "sitelinks": {}}}}
WIKIPEDIA = {"query": {"pages": {"1": {"extract": "First Album is the debut studio album by Seed Artist, released in 2019 "
                                                  "on Deep Label. It is described as a dark, hypnotic deep house record "
                                                  "built around long club tracks and was well received by DJs."}}}}

ROUTES = {
    "search": (200, SEARCH),
    f"recording/{REC}": (200, RECORDING),
    f"recording/{REC_REMIX}": (200, REMIX_RECORDING),
    f"release?recording={REC}": (200, {"release-count": 3, "releases": [release_album, release_album_digital, release_comp]}),
    f"release?recording={REC_REMIX}": (200, {"release-count": 1, "releases": [release_album]}),
    f"artist/{ART}": (200, ARTIST),
    f"wdsearch:P4404={REC}": (200, {"query": {"search": []}}),
    f"wdsearch:P4404={REC_REMIX}": (200, {"query": {"search": []}}),
    f"wdsearch:P436={RG_ALBUM}": (200, {"query": {"search": [{"title": "Q100"}]}}),
    "wd:Q100": (200, ALBUM_ENTITY),
    "wd:Q500": (200, ARTIST_ENTITY),
    f"wd:{GENRE}": (200, {"entities": {GENRE: {"labels": {"es": {"value": "deep house"}}}}}),
    "wp:First Album": (200, WIKIPEDIA),
}


class Transport:
    def __init__(self, routes):
        self.routes, self.urls = routes, []

    def __call__(self, url, headers, timeout):
        self.urls.append(url)
        parts = urlsplit(url)
        q = {k: v[0] for k, v in parse_qs(parts.query).items()}
        if "wikidata.org" in parts.netloc:
            key = f"wdsearch:{q['srsearch'].split(':', 1)[1]}" if "srsearch" in q else f"wd:{q['ids']}"
        elif "wikipedia.org" in parts.netloc:
            key = "wp:" + q.get("titles", "")
        else:
            path = parts.path.split("/ws/2/", 1)[1]
            key = "search" if path == "recording" else f"release?recording={q['recording']}" if path == "release" else path
        status, body = self.routes.get(key, (404, None))
        if isinstance(status, Exception):
            raise status
        return status, json.dumps(body).encode() if body is not None else b"", None


GOOD = ("«Night Drive» es una pista de Seed Artist incluida en su álbum debut «First Album» (2019), publicado en Deep "
        "Label. Ese álbum se describe como un disco de deep house oscuro e hipnótico, centrado en temas largos para club, "
        "y la canción encaja en esa línea dentro del catálogo del productor, sin que eso implique más detalles sonoros.")


class FakeGroq:
    def __init__(self, responses=None):
        self.responses, self.calls = list(responses or []), 0

    def __call__(self, url, headers, body, timeout):
        self.calls += 1
        status, payload = self.responses.pop(0) if self.responses else (200, {"interpretation": GOOD, "source_ids": ["S1", "S3"]})
        if status != 200:
            return status, b"", None
        return 200, json.dumps({"choices": [{"finish_reason": "stop", "message": {"content": json.dumps(payload)}}]}).encode(), None


def make(routes=None, groq=None):
    transport = Transport(dict(ROUTES if routes is None else routes))
    kw = {"transport": transport, "sleep": lambda s: None}
    mbc, wiki = MusicBrainzClient("test@example.org", **kw), WikimediaClient("test@example.org", **kw)
    app.dependency_overrides[get_client] = lambda: mbc
    app.dependency_overrides[get_wiki_client] = lambda: wiki
    g = GroqClient("test-key", "m", transport=groq, sleep=lambda s: None) if groq else GroqClient("", "")
    app.dependency_overrides[get_groq_client] = lambda: g
    return TestClient(app), transport


@pytest.fixture(autouse=True)
def _reset(monkeypatch):
    monkeypatch.delenv("COVER_ART", raising=False)
    yield
    app.dependency_overrides.clear()


# --- Funciones puras ----------------------------------------------------------------------------------------------
def test_query_supports_artist_dash_title_in_both_orders_and_escapes():
    q = tracks.build_query("Seed Artist - Night Drive")
    assert q == "(recording:(Night Drive) AND artist:(Seed Artist))^2 OR (recording:(Seed Artist) AND artist:(Night Drive))"
    assert tracks.build_query("AC/DC OR x") == 'recording:"AC\\/DC or x"^3 OR (recording:(AC\\/DC or x) AND artist:(AC\\/DC or x))'


def test_search_groups_identical_recordings_but_never_versions_or_homonyms():
    results, omitted = tracks.search_results(SEARCH, "night drive", 10, covers=True)
    assert omitted == 1  # fragmento de DJ mix: no es la canción
    by_id = {r.mbid: r for r in results}
    assert REC_DUP not in by_id and by_id[REC].merged_count == 2  # misma canción, 1,5 s de diferencia
    assert {REC, REC_REMIX, REC_LIVE, REC_HOMONYM} <= set(by_id)
    assert by_id[REC_REMIX].version == "Other remix" and by_id[REC_LIVE].version == "Directo"
    assert results[0].mbid == REC  # título exacto, no directo y con más lanzamientos
    assert results[-1].mbid == REC_LIVE  # el directo, al final
    assert by_id[REC_HOMONYM].artist_disambiguation == "rock band"  # homónimo distinguible
    assert by_id[REC].release_title == "First Album" and by_id[REC].release_type == "Album"
    assert by_id[REC].cover_url == f"https://coverartarchive.org/release-group/{RG_ALBUM}/front-250"
    assert "99999999-9999-4999-8999-999999999999" not in by_id  # no cubre la búsqueda
    assert tracks.search_results(SEARCH, "night drive", 10, covers=False)[0][0].cover_url is None


def test_releases_original_cover_and_precise_date():
    groups, original, original_raw, count = tracks.releases([release_comp, release_album, release_album_digital],
                                                            frozenset({ART}), covers=True)
    assert count == 2 and original.mbid == RG_ALBUM and groups[0].mbid == RG_ALBUM
    assert original.date == "2019-05-03" and original.labels == ["Deep Label"]  # «[no label]» no es un sello
    assert original.formats == ["Vinyl", "Digital Media"] and original.catalog_number == "DL001"
    assert groups[1].own is False
    cover, release_id = tracks.hero_cover([release_comp, release_album, release_album_digital], original_raw,
                                          frozenset({ART}), covers=True)
    assert release_id == "r-album-2" and cover.endswith("/release/r-album-2/front-500")  # solo con portada declarada
    assert tracks.hero_cover([release_album], release_album, frozenset({ART}), covers=True) == (None, None)


def test_label_documented_self_released_or_unknown():
    """«[no label]» = autoedición documentada; label-info vacío = sin datos (nunca se deduce autoedición)."""
    rel = tracks.relations(RECORDING, [])

    def label_trait(release):
        groups, original, *_ = tracks.releases([release], frozenset({ART}), covers=False)
        dna = tracks.dna(REC, "Night Drive", WikidataInfo(), WikidataInfo(), original, "Seed Artist", None, [],
                         groups, None, rel, {})
        return groups[0], next(t for t in dna.traits if t.key == "label")

    group, trait = label_trait(release_album)
    assert not group.self_released and (trait.status, trait.values) == ("verified", ["Deep Label"])
    group, trait = label_trait({**release_album, "label-info": NO_LABEL_INFO})
    assert group.self_released and group.labels == []
    assert (trait.status, trait.values) == ("verified", [tracks.SELF_RELEASED]) and "sin sello" in trait.detail
    group, trait = label_trait({**release_album, "label-info": []})
    assert not group.self_released and trait.status == "unavailable" and trait.values == []
    # Un sello documentado en otra edición del mismo grupo prevalece sobre «[no label]».
    groups, *_ = tracks.releases([release_album, {**release_album_digital, "label-info": NO_LABEL_INFO}],
                                 frozenset({ART}), covers=False)
    assert groups[0].labels == ["Deep Label"] and not groups[0].self_released
    # La autoedición de un recopilatorio de terceros no cuenta para la canción.
    comp_only = {**release_comp, "label-info": NO_LABEL_INFO}
    groups, original, *_ = tracks.releases([comp_only], frozenset({ART}), covers=False)
    dna = tracks.dna(REC, "Night Drive", WikidataInfo(), WikidataInfo(), original, "Seed Artist", None, [], groups,
                     None, rel, {})
    assert next(t for t in dna.traits if t.key == "label").status == "unavailable"


def test_release_links_and_identifiers_come_only_from_documented_urls():
    raw_releases = [release_album, release_album_digital, release_comp]
    links = tracks.links(RECORDING, raw_releases, frozenset({ART}))
    by_label = {l.label: l for l in links}
    assert by_label["Spotify"].scope == "recording"  # misma URL en grabación y lanzamiento: gana la grabación
    assert by_label["Bandcamp"].scope == "release" and by_label["Bandcamp"].primary
    assert "Discogs" in by_label and not by_label["Discogs"].primary
    assert "Beatport" not in by_label  # enlace de un recopilatorio de terceros: no es de esta canción
    assert [l.url for l in links].count("https://open.spotify.com/track/abc") == 1

    _groups, original, original_raw, _n = tracks.releases(raw_releases, frozenset({ART}), covers=False)
    ids = tracks.identifiers(RECORDING, raw_releases, original, original_raw, frozenset({ART}))
    assert ids.recording_mbid == REC and ids.isrcs == ["GBXXX1900001"] and ids.release_group_mbid == RG_ALBUM
    assert ids.barcodes == ["5054288375188"]  # sin el del recopilatorio
    ext = {(e.provider, e.kind): e for e in ids.external}
    assert ext[("discogs", "release")].id == "818516" and ext[("discogs", "release")].scope == "release"
    assert ext[("bandcamp", "album")].id == "seedartist.bandcamp.com/album/first-album"
    assert ("spotify", "track") not in ext  # «abc» no es un ID de Spotify válido: no se inventa
    assert ("beatport", "release") not in ext


def test_external_ids_from_real_url_shapes():
    from app.links import external_id
    assert external_id("https://open.spotify.com/album/0pCLaw5HAkjxcxq4ebcdrY") == ("spotify", "album", "0pCLaw5HAkjxcxq4ebcdrY")
    assert external_id("https://www.deezer.com/album/538277652") == ("deezer", "album", "538277652")
    assert external_id("https://music.apple.com/gb/album/1726980894") == ("apple_music", "album", "1726980894")
    assert external_id("https://itunes.apple.com/us/album/id1197253063") == ("apple_music", "album", "1197253063")
    assert external_id("https://tidal.com/album/168577975") == ("tidal", "album", "168577975")
    assert external_id("https://www.beatport.com/release/dedust/1331472") == ("beatport", "release", "1331472")
    assert external_id("https://arapu.bandcamp.com/track/just-a-jam") == ("bandcamp", "track", "arapu.bandcamp.com/track/just-a-jam")
    assert external_id("https://rateyourmusic.com/release/single/michael-bibi/hanging-tree/") is None
    from app.links import classify
    assert classify("https://www.amazon.de/gp/product/B000JSDO3S", ["purchase for mail-order"])[0] == "Amazon"
    assert classify("https://rateyourmusic.com/release/x/", ["other databases"])[0] == "Rate Your Music"


def test_links_grouped_by_destination_with_target_and_known_dead_hidden():
    from app.links import normalize_links

    def rel(url, kind, scope, release_type=None):
        out = {"target-type": "url", "type": kind, "url": {"resource": url}, "_scope": scope}
        return {**out, "_release_type": release_type} if release_type else out
    links = normalize_links([
        rel("https://open.spotify.com/track/1A2b3C4d5E6f7G8h9I0jKl", "free streaming", "recording"),
        # CRAZY → «Withness»: el mismo álbum de Apple en dos tiendas de país es un solo destino (BUG-04)
        rel("https://music.apple.com/gb/album/6770259408", "purchase for download", "release", "Album"),
        rel("https://music.apple.com/gb/album/6770259408", "streaming", "release", "Album"),
        rel("https://music.apple.com/us/album/6770259408", "streaming", "release", "Album"),
        rel("https://open.spotify.com/album/4q72fmveNOwffTj4hJ07Zo", "free streaming", "release", "Album"),
        rel("https://music.apple.com/gb/album/1726980894", "streaming", "release", "Single"),  # caducado (BUG-01)
    ])
    apple = [l for l in links if l.platform == "Apple Music"]
    assert len(apple) == 1 and apple[0].target == "release" and apple[0].release_type == "Album"
    assert set(apple[0].kinds) == {"purchase for download", "streaming"}
    assert not any("1726980894" in l.url for l in links)
    spotify = [l for l in links if l.platform == "Spotify"]  # dos destinos reales: la pista destacada, el álbum aparte
    assert [(l.target, l.primary) for l in spotify] == [("track", True), ("release", False)]
    assert spotify[0].release_type is None
    # Apple con ?i= abre la pista dentro del álbum: no se fusiona con el álbum
    song = normalize_links([rel("https://music.apple.com/gb/album/x/6770259408?i=6770259410", "streaming", "release", "Album"),
                            rel("https://music.apple.com/gb/album/6770259408", "streaming", "release", "Album")])
    assert sorted(l.target for l in song) == ["release", "track"]
    # Ficha de artista (sin ámbito): sin target
    assert normalize_links([{"target-type": "url", "type": "streaming",
                             "url": {"resource": "https://open.spotify.com/artist/x"}}])[0].target is None


def test_search_merges_same_isrc_only_when_artist_version_and_length_match():
    def rec(mbid, title, length, isrcs, artists=(ME,), disambiguation=None):
        out = {"id": mbid, "score": 100, "title": title, "artist-credit": credit(*artists), "length": length,
               "isrcs": isrcs, "releases": [{**release_album, "id": f"r-{mbid}"}]}
        return {**out, "disambiguation": disambiguation} if disambiguation else out
    ids = [f"{n}0000000-0000-4000-8000-000000000000" for n in "1234567"]
    data = {"recordings": [
        rec(ids[0], "Hoodlum", 414000, ["DEHE41400041"]),
        rec(ids[1], "Hoodlum (original mix)", 414584, ["DEHE41400041"]),       # misma pista: se une
        rec(ids[2], "Hoodlum (extended mix)", 414300, ["DEHE41400041"]),       # otra versión: aparte
        rec(ids[3], "Hoodlum (original mix)", 380000, ["DEHE41400041"]),       # otra duración: aparte
        rec(ids[4], "Hoodlum", 414000, ["DEHE41400041"], artists=((HOMONYM, "Seed Artist", "rock band"),)),
        rec(ids[5], "Hoodlum", 414100, ["DEHE41400041"], disambiguation="live, 2015: Club"),  # directo: aparte
        rec(ids[6], "Hoodlum (Original)", 414000, ["OTHER0000001"]),            # otro título sin ISRC común: aparte
    ]}
    results, _ = tracks.search_results(data, "hoodlum", 20, covers=False)
    merged = [r for r in results if r.merged_count > 1]
    assert len(merged) == 1 and merged[0].merged_count == 2
    assert len(results) == 6
    assert tracks.version_kind("Hoodlum (Original Mix)") is None and tracks.version_kind("Hoodlum (Extended Mix)") == "extended mix"


def test_relations_remix_direction_and_named_dj_mixes():
    groups, *_ = tracks.releases([release_album, release_comp], frozenset({ART}), covers=False)
    rel = tracks.relations(RECORDING, groups)
    assert [r.mbid for r in rel.remixes] == [REC_REMIX] and rel.remix_of == []
    assert rel.dj_mix_count == 2 and rel.dj_mixes == ["Club Hits", "Radio Show 100"]  # nombre del mix, sin duplicar
    assert [r.mbid for r in tracks.relations(REMIX_RECORDING, []).remix_of] == [REC]


def test_dna_has_no_invented_metrics():
    rel = tracks.relations(RECORDING, [])
    dna = tracks.dna(REC, "Night Drive", WikidataInfo(), WikidataInfo(), None, "Seed Artist", None, [], [], None, rel, {})
    by_key = {t.key: t for t in dna.traits}
    for key in ("bpm", "key", "energy"):
        assert by_key[key].status == "unavailable" and by_key[key].values == [] and by_key[key].group == "acoustic"
    assert by_key["genre"].status == "unavailable"
    assert all(t.status != "measured" for t in dna.traits)
    assert not any(any(ch.isdigit() for ch in v) and "%" in v for t in dna.traits for v in t.values)


def test_interpretation_validator_rejects_acoustic_claims_and_unsupported_sound():
    track = type("T", (), {"title": "Night Drive"})()
    doc = type("D", (), {"text": "Night Drive by Seed Artist, 2019, Deep Label. Dark hypnotic deep house album."})()
    base = "«Night Drive» es una pista de Seed Artist publicada en 2019 en Deep Label, un sello de deep house. " * 2
    assert track_ai.validate(base, track, [doc]) is None
    assert track_ai.validate(base + "Va a 124 BPM.", track, [doc]) == "menciona mediciones acústicas"
    assert track_ai.validate(base + "Está en La menor.", track, [doc]) == "menciona mediciones acústicas"
    assert track_ai.validate(base + "La mayor parte del disco es instrumental.", track, [doc]) is None
    assert track_ai.validate(base + "Al escuchar se nota.", track, [doc]) == "finge haber escuchado la canción"
    assert track_ai.validate(base + "Tiene un aire eufórico.", track, [doc]).startswith("rasgo sonoro sin respaldo")
    assert track_ai.validate(base + "Es oscuro.", track, [doc]) is None  # «dark» en la fuente
    assert track_ai.validate(base.replace("2019", "2015"), track, [doc]).startswith("año sin respaldo")
    # Relleno observado con datos reales: continuidad de estilo sin evidencia y comentarios sobre las fuentes.
    assert track_ai.validate(base + "Mantiene la coherencia con su estilo habitual.", track, [doc]) == "relleno sin respaldo"
    assert track_ai.validate(base + "Aunque la fuente no detalla su carácter.", track, [doc]) == "relleno sin respaldo"


# --- API ----------------------------------------------------------------------------------------------------------
def test_search_endpoint_contract_and_validation():
    client, transport = make()
    r = client.get("/v1/tracks/search", params={"q": "night drive", "limit": "3"})
    assert r.status_code == 200
    body = r.json()
    assert len(body["results"]) == 3 and body["omitted_mix_fragments"] == 1
    assert body["results"][0]["mbid"] == REC and body["source"]["license"].startswith("CC0")
    assert "limit=100" in transport.urls[0]
    for bad in ({"q": ""}, {"q": "x" * 101}, {"q": "ok", "limit": "99"}):
        assert client.get("/v1/tracks/search", params=bad).status_code == 422


def test_track_profile_identity_dna_and_cache():
    client, transport = make()
    body = client.get(f"/v1/tracks/{REC}").json()
    assert (body["title"], body["artist_name"], body["length_ms"]) == ("Night Drive", "Seed Artist", 360000)
    assert body["isrcs"] == ["GBXXX1900001"] and body["original_release"]["title"] == "First Album"
    assert body["cover_url"].endswith("/release/r-album-2/front-500")
    assert [c["role"] for c in body["credits"]] == ["Producción", "Composición", "Ingeniería"]
    assert body["links"][0]["label"] == "Spotify"
    traits = {t["key"]: t for t in body["dna"]["traits"]}
    assert traits["genre"] == {**traits["genre"], "status": "community", "scope": "release", "values": ["deep house"]}
    assert traits["label"]["values"] == ["Deep Label"] and traits["label"]["status"] == "verified"
    assert traits["dj_mixes"]["values"] == ["2 DJ mixes"] and traits["remixes"]["values"] == ["1 documentada"]
    assert all(traits[k]["status"] == "unavailable" for k in ("bpm", "key", "energy"))
    assert body["interpretation"] is None and body["interpretation_status"] == "unavailable"  # sin Groq
    assert {s["label"] for s in body["sources"]} >= {"MusicBrainz", "Wikidata Q100"}
    calls = len(transport.urls)
    assert client.get(f"/v1/tracks/{REC}/dna").json()["traits"] == body["dna"]["traits"]
    assert len(transport.urls) == calls  # ficha en caché persistente: sin nuevas peticiones


def test_track_cache_is_versioned_and_only_incompatible_records_are_rebuilt():
    from app import store
    from app.api import TRACK_CONTRACT_VERSION, TRACK_KIND
    client, transport = make()
    body = client.get(f"/v1/tracks/{REC}").json()
    assert body["identifiers"]["barcodes"] == ["5054288375188"]
    assert store.get(TRACK_KIND, REC)["contract"] == TRACK_CONTRACT_VERSION
    calls = len(transport.urls)
    client.get(f"/v1/tracks/{REC}")
    assert len(transport.urls) == calls  # versión vigente: se reutiliza sin peticiones
    # Registro de T2.0 (sin versión) con la semántica antigua: se reconstruye y se sobrescribe.
    old = {**body, "identifiers": None, "links": []}
    store.put(TRACK_KIND, REC, {"track": old, "wiki": []}, 3600)
    other = {"contract": TRACK_CONTRACT_VERSION, "keep": True}
    store.put("image", ART, other, 3600)
    rebuilt = client.get(f"/v1/tracks/{REC}").json()  # (las respuestas HTTP siguen en la caché en memoria)
    assert rebuilt["identifiers"] == body["identifiers"] and rebuilt["links"] == body["links"]
    assert store.get(TRACK_KIND, REC)["contract"] == TRACK_CONTRACT_VERSION
    assert store.get("image", ART) == other  # el resto de la caché no se toca


def test_track_profile_errors():
    client, _ = make()
    assert client.get("/v1/tracks/not-a-mbid").json()["error"]["code"] == "invalid_mbid"
    r = client.get("/v1/tracks/12345678-1234-4234-8234-123456789012")
    assert r.status_code == 404 and r.json()["error"]["code"] == "not_found"


def test_releases_failure_is_a_section_error_and_not_cached():
    routes = {**ROUTES, f"release?recording={REC}": (503, None)}
    client, transport = make(routes)
    body = client.get(f"/v1/tracks/{REC}").json()
    assert body["releases_status"]["status"] == "error" and body["releases"] == [] and body["cover_url"] is None
    assert body["title"] == "Night Drive"  # la identidad sigue disponible
    calls = len(transport.urls)
    client.get(f"/v1/tracks/{REC}")
    assert len(transport.urls) > calls  # fallo temporal: se reintenta en la siguiente visita


def test_interpretation_generated_once_validated_and_cached():
    groq = FakeGroq()
    client, _ = make(groq=groq)
    assert client.get(f"/v1/tracks/{REC}").json()["interpretation_status"] == "pending"
    r = client.get(f"/v1/tracks/{REC}/interpretation").json()
    assert r["status"] == "ready" and r["interpretation"]["text"] == GOOD
    assert [s["label"] for s in r["interpretation"]["sources"]] == ["MusicBrainz", "Wikipedia (en): First Album"]
    client.get(f"/v1/tracks/{REC}/interpretation")
    profile = client.get(f"/v1/tracks/{REC}").json()
    assert groq.calls == 1 and profile["interpretation_status"] == "ready"
    assert profile["interpretation"]["text"] == GOOD
    # La IA nunca se convierte en rasgos del ADN.
    assert all(t["status"] != "ai" for t in profile["dna"]["traits"])


def test_interpretation_rejected_or_failing_falls_back_to_facts():
    bad = {"interpretation": GOOD + " Va a 124 BPM.", "source_ids": ["S1"]}
    groq = FakeGroq([(200, bad)])
    client, _ = make(groq=groq)
    r = client.get(f"/v1/tracks/{REC}/interpretation").json()
    assert r == {"recording_mbid": REC, "status": "unavailable", "interpretation": None}
    assert track_ai.cached(REC).error_code == "menciona mediciones acústicas"

    groq429 = FakeGroq([(429, None), (429, None)])
    client, _ = make(groq=groq429)
    r = client.get(f"/v1/tracks/{REC_REMIX}/interpretation").json()
    assert r["status"] in ("unavailable", "insufficient_sources") and r["interpretation"] is None


def test_interpretation_without_descriptive_sources_never_calls_groq():
    routes = {k: v for k, v in ROUTES.items() if k != "wp:First Album"}
    groq = FakeGroq()
    client, _ = make(routes, groq=groq)
    r = client.get(f"/v1/tracks/{REC}/interpretation").json()
    assert r["status"] == "insufficient_sources" and groq.calls == 0
    assert client.get(f"/v1/tracks/{REC}").json()["interpretation_status"] == "insufficient_sources"


def test_artist_wikipedia_alone_is_not_enough_for_an_interpretation():
    """Caso real (Breather, remix de Strobe): solo la Wikipedia del artista → el modelo rellenaba. Ahora no se llama."""
    artist_with_wiki = {"entities": {"Q500": {"claims": {"P434": [{"mainsnak": {"datavalue": {"value": ART}}}]},
                                              "sitelinks": {"enwiki": {"title": "Seed Artist"}}}}}
    routes = {**{k: v for k, v in ROUTES.items() if k != "wp:First Album"}, "wd:Q500": (200, artist_with_wiki),
              "wp:Seed Artist": (200, WIKIPEDIA)}
    groq = FakeGroq()
    client, _ = make(routes, groq=groq)
    r = client.get(f"/v1/tracks/{REC}/interpretation").json()
    assert r["status"] == "insufficient_sources" and groq.calls == 0


def test_release_links_carry_the_formats_of_their_edition():
    """V5.1: la app solo muestra Discogs si el enlace sale de una edición física documentada (vinilo, CD…)."""
    from app import tracks as t
    credit = [{"artist": {"id": "a1", "name": "A"}}]
    releases = [{"id": "r1", "artist-credit": credit, "status": "Official", "release-group": {"primary-type": "EP"},
                 "media": [{"format": "12\" Vinyl"}, {"format": "12\" Vinyl"}],
                 "relations": [{"target-type": "url", "type": "discogs", "url": {"resource": "https://www.discogs.com/release/1"}}]}]
    links = t.links({"relations": []}, releases, frozenset({"a1"}))
    discogs = next(l for l in links if "discogs.com" in l.url)
    assert discogs.formats == ['12" Vinyl'] and discogs.scope == "release"
