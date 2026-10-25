"""Deezer (V6): identidad del artista solo por identificadores o por nombre exacto con discografía en común; foto solo si
no es la silueta genérica; nada con DATA_USE=commercial."""

import urllib.error

import pytest

from app import deezer, schemas, store
from tests.test_api import ROUTES, make_client
from tests.fixtures import mb

MBID = "11111111-1111-1111-1111-111111111111"
OTHER = "22222222-2222-2222-2222-222222222222"
PHOTO = "https://cdn-images.dzcdn.net/images/artist/6c2b7d033c6ffabdd5cc45a1929bad6e/1000x1000-000000-80-0-0.jpg"
SILHOUETTE = "https://cdn-images.dzcdn.net/images/artist//1000x1000-000000-80-0-0.jpg"
NO_DATA = {"error": {"type": "DataException", "message": "no data", "code": 800}}


class Fake:
    def __init__(self, routes):
        self.routes, self.urls = routes, []

    def __call__(self, url):
        self.urls.append(url)
        path = url.removeprefix(deezer.BASE_URL + "/")
        for key, value in self.routes.items():
            if path == key or path.startswith(key + "?"):
                if isinstance(value, Exception):
                    raise value
                return value
        return NO_DATA


def artist(id_=5359276, name="CHRIS STASSY", pic=PHOTO):
    return {"id": id_, "name": name, "link": f"https://www.deezer.com/artist/{id_}", "picture_xl": pic}


def mb_artist(name="Chris Stussy", relations=(), aliases=()):
    return {"id": MBID, "name": name, "relations": list(relations), "aliases": [{"name": a} for a in aliases]}


def rec(isrc, *credits):
    return {"isrcs": [isrc], "artist-credit": [{"artist": {"id": c}} for c in (credits or (MBID,))]}


def track(artist_id, name):
    return {"id": 1, "artist": {"id": artist_id, "name": name}}


def run(mb, routes, recordings=(), titles=()):
    fake = Fake(routes)
    found = deezer.resolve(mb, MBID, lambda: list(recordings), lambda: list(titles), fake)
    return found, fake


def test_musicbrainz_link_first_without_searching():
    link = {"type": "free streaming", "url": {"resource": "https://www.deezer.com/en/artist/5359276"}}
    found, fake = run(mb_artist(relations=[link]), {"artist/5359276": artist()})
    assert found["via"] == "musicbrainz_link" and found["picture"] == PHOTO
    assert fake.urls == [f"{deezer.BASE_URL}/artist/5359276"]


def test_two_matching_isrcs_survive_a_name_change():
    # Chris Stussy figura en Deezer como «CHRIS STASSY»: el nombre no coincide, pero dos ISRC sí.
    routes = {"track/isrc:QM4TW2437510": track(5359276, "CHRIS STASSY"), "track/isrc:QM4TW2437511": track(5359276, "CHRIS STASSY"),
              "artist/5359276": artist()}
    found, _ = run(mb_artist(), routes, [rec("QM4TW2437510"), rec("QM4TW2437511")])
    assert found["id"] == "5359276" and found["via"] == "isrc"


def test_one_isrc_needs_the_name_too_and_collaborations_are_ignored():
    routes = {"track/isrc:A": track(9, "Someone Else"), "artist/9": artist(9, "Someone Else")}
    assert run(mb_artist(), routes, [rec("A")])[0] is None, "un ISRC con otro nombre: no basta"
    store.put(deezer.KIND, MBID, {}, 1)  # sin caché entre casos
    routes = {"track/isrc:A": track(5, "Chris Stussy"), "artist/5": artist(5, "Chris Stussy")}
    assert run(mb_artist(), routes, [rec("A")])[0]["id"] == "5"
    assert deezer.recording_isrcs([rec("B", MBID, OTHER), rec("A")], MBID) == ["A"], "con colaboradores, no"


def test_name_alone_is_never_enough():
    routes = {"search/artist": {"data": [artist(606695, "Arapu")]}, "artist/606695/albums": {"data": [{"title": "Otro"}]}}
    assert run(mb_artist("Arapu"), routes, titles=["Just a Jam", "Tribal Nation"])[0] is None
    store.put(deezer.KIND, MBID, {}, 1)
    routes["artist/606695/albums"] = {"data": [{"title": "Just A Jam - EP"}, {"title": "Tribal Nation"}]}
    routes["artist/606695"] = artist(606695, "Arapu")
    found, _ = run(mb_artist("Arapu"), routes, titles=["Just a Jam", "Tribal Nation"])
    assert found["via"] == "catalog_match"


def test_two_candidates_that_pass_are_ambiguous():
    albums = {"data": [{"title": "A"}, {"title": "B"}]}
    routes = {"search/artist": {"data": [artist(1, "Arapu"), artist(2, "Arapu")]}, "artist/1/albums": albums,
              "artist/2/albums": albums}
    assert run(mb_artist("Arapu"), routes, titles=["A", "B"])[0] is None


def test_silhouette_is_not_a_photo_and_result_is_cached():
    link = {"url": {"resource": "https://www.deezer.com/artist/7"}}
    found, fake = run(mb_artist(relations=[link]), {"artist/7": artist(7, pic=SILHOUETTE)})
    assert found["picture"] is None and deezer.artist_image(found) is None
    again, fake2 = run(mb_artist(relations=[link]), {})
    assert again == found and fake2.urls == []


def test_temporary_failure_raises_and_is_not_cached():
    link = {"url": {"resource": "https://www.deezer.com/artist/7"}}
    with pytest.raises(deezer.Unavailable):
        run(mb_artist(relations=[link]), {"artist/7": urllib.error.URLError("down")})
    with pytest.raises(deezer.Unavailable):
        run(mb_artist(relations=[link]), {"artist/7": {"error": {"code": 4, "message": "Quota limit exceeded"}}})
    assert store.get(deezer.KIND, MBID) is None


def _api_with_deezer(monkeypatch, routes):
    fake = Fake(routes)
    monkeypatch.setattr(deezer, "_default_transport", fake)
    no_commons = dict(ROUTES)
    no_commons[f"wd:{mb.QID}"] = (200, mb.wikidata_entity(p18=()))
    no_commons[f"artist/{mb.SEED}"] = (200, {**mb.SEED_ARTIST, "relations": [
        *mb.SEED_ARTIST.get("relations", []), {"url": {"resource": "https://www.deezer.com/artist/42"}}]})
    return make_client(no_commons)[0], fake


def test_api_uses_deezer_only_when_there_is_no_free_photo(monkeypatch):
    client, _ = _api_with_deezer(monkeypatch, {"artist/42": artist(42, "Seed Artist")})
    body = client.get(f"/v1/artists/{mb.SEED}/image").json()
    assert body["image"]["source"] == "deezer" and body["image"]["via"] == "deezer_musicbrainz_link"
    assert body["image"]["page_url"] == "https://www.deezer.com/artist/42" and body["reason"] is None
    profile = client.get(f"/v1/artists/{mb.SEED}").json()
    assert profile["image"]["source"] == "deezer"
    assert any(s["label"] == "Foto (Deezer)" for s in profile["sources"])


def test_api_commercial_mode_never_calls_or_serves_deezer(monkeypatch):
    client, fake = _api_with_deezer(monkeypatch, {"artist/42": artist(42, "Seed Artist")})
    assert client.get(f"/v1/artists/{mb.SEED}/image").json()["image"]["source"] == "deezer"
    monkeypatch.setenv("DATA_USE", "commercial")
    calls = len(fake.urls)
    body = client.get(f"/v1/artists/{mb.SEED}/image").json()
    assert body["image"] is None and len(fake.urls) == calls  # la foto guardada no se sirve y no se pregunta a Deezer


# --- V6.1: canciones ---
REC = "9d619150-6b0f-4f14-b038-8503ae4c6c8f"  # Desire (Chris Stussy), single digital de 2:52


def dz_track(isrc="QM4TW2437510", duration=171, album=630, artist_id=5359276):
    return {"id": 2782517712, "isrc": isrc, "duration": duration, "link": "https://www.deezer.com/track/2782517712",
            "album": {"id": album}, "artist": {"id": artist_id}}


def dz_album(label="CSS", date="2024-02-09", record_type="single", artist_id=5359276):
    return {"title": "Desire", "label": label, "release_date": date, "record_type": record_type, "artist": {"id": artist_id}}


def test_track_only_the_same_recording_by_isrc_and_length():
    fake = Fake({"track/isrc:QM4TW2437510": dz_track(), "album/630": dz_album()})
    found = deezer.track_match(REC, ["QM4TW2437510"], 171953, fake)
    assert found["id"] == "2782517712" and found["own_release"] and deezer.label_value(found, "2024-02-09") == "CSS"
    store.put(deezer.TRACK_KIND, REC, {}, 1)
    other = Fake({"track/isrc:QM4TW2437510": dz_track(duration=374), "album/630": dz_album()})
    assert deezer.track_match(REC, ["QM4TW2437510"], 171953, other) is None, "la edición de 6:14: otra versión"
    assert deezer.track_match("x", [], 171953, fake) is None and deezer.track_match("y", ["A"], None, fake) is None


def test_label_only_from_own_release_of_the_same_year():
    base = {"id": "1", "label": "EAMS", "release_date": "2017-01-01", "own_release": True}
    assert deezer.label_value(base, "2004-05-01") is None, "reedición posterior: sello del reeditor"
    assert deezer.label_value({**base, "own_release": False}, "2017") is None, "recopilatorio o de otro artista"
    assert deezer.label_value(base, "2017-03-02") == "EAMS"
    unavailable = schemas.DnaTrait(key="label", group="context", label="Sello", status="unavailable")
    known = schemas.DnaTrait(key="label", group="context", label="Sello", status="verified", values=["Desolat"])
    dna = deezer.with_label(schemas.TrackDna(recording_mbid=REC, traits=[unavailable]), base, "2017")
    assert dna.traits[0].values == ["EAMS"] and dna.traits[0].sources[0].label == "Deezer"
    assert deezer.with_label(schemas.TrackDna(recording_mbid=REC, traits=[known]), base, "2017").traits[0].values == ["Desolat"]


def test_preview_is_requested_fresh_and_never_cached():
    record = {"id": "2782517712"}
    fake = Fake({"track/2782517712": {"preview": "https://cdnt-preview.dzcdn.net/a.mp3?hdnea=exp=1"}})
    assert deezer.preview(record, fake) == "https://cdnt-preview.dzcdn.net/a.mp3?hdnea=exp=1"
    assert deezer.preview(record, fake) and len(fake.urls) == 2
    assert deezer.preview(record, Fake({"track/2782517712": {"preview": ""}})) is None


# --- V6.1: catálogo de reserva ---
def hit(id_, title, artist="Arapu", isrc="GBKQU2654262", duration=402, album="Playground"):
    return {"id": id_, "title": title, "isrc": isrc, "duration": duration, "artist": {"id": 606695, "name": artist},
            "album": {"id": 7, "title": album, "cover_xl": "https://cdn-images.dzcdn.net/images/cover/x/1000x1000.jpg"}}


def test_search_only_tracks_with_every_word_and_no_duplicates():
    data = {"data": [hit(1, "Playground"), hit(2, "Playground"), hit(3, "Playground (Edit)", isrc="GBKQU2654263", duration=180),
                     hit(4, "Other song"), hit(5, "Playground", artist="Someone")]}
    results = deezer.search_tracks("arapu playground", 10, Fake({"search/track": data}))
    assert [r.mbid for r in results] == ["deezer:1", "deezer:3"], "mismo ISRC = una; el edit es otra canción"
    assert results[0].catalog == "deezer" and results[0].length_ms == 402000 and results[1].version
    assert deezer.search_tracks("playground", 10, Fake({"search/track": data})) == [], "una sola palabra: no"
    assert deezer.search_tracks("arapu playground", 10, Fake({"search/track": urllib.error.URLError("x")})) == []


def test_external_profile_from_deezer(monkeypatch):
    album = {"id": 7, "title": "Playground", "label": "Rawax", "release_date": "2026-03-06", "record_type": "single",
             "link": "https://www.deezer.com/album/7", "cover_xl": "https://cdn-images.dzcdn.net/images/cover/x/1000x1000.jpg"}
    fake = Fake({"track/1": {**hit(1, "Playground"), "link": "https://www.deezer.com/track/1"}, "album/7": album})
    monkeypatch.setattr(deezer, "_default_transport", fake)
    client, _ = make_client()
    body = client.get("/v1/tracks/ext/deezer:1").json()
    assert body["catalog"] == "deezer" and body["mbid"] == "deezer:1" and body["isrcs"] == ["GBKQU2654262"]
    assert body["deezer_url"] == "https://www.deezer.com/track/1" and body["main_artist"] is None  # sin enlace en MB
    label = next(t for t in body["dna"]["traits"] if t["key"] == "label")
    assert label["values"] == ["Rawax"] and label["sources"][0]["label"] == "Datos de Deezer"
    assert client.get("/v1/tracks/ext/deezer:abc").status_code == 404
    monkeypatch.setenv("DATA_USE", "commercial")
    assert client.get("/v1/tracks/ext/deezer:1").status_code == 404


def test_several_musicbrainz_links_pick_the_card_with_a_photo():
    links = [{"url": {"resource": "https://www.deezer.com/artist/1477045"}},
             {"url": {"resource": "https://www.deezer.com/artist/68540642"}}]
    routes = {"artist/1477045": {**artist(1477045, "Daft Punk - Stardust", SILHOUETTE), "nb_fan": 8617},
              "artist/68540642": {**artist(68540642, "Stardust"), "nb_fan": 22209}}
    found, _ = run(mb_artist("Stardust", relations=links), routes)
    assert found["id"] == "68540642" and found["via"] == "musicbrainz_link"
