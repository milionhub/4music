"""Canciones afines (Tu frecuencia): temas propios de artistas relacionados en Deezer, nunca otra versión de la
canción de partida, con TrackDNA completo si MusicBrainz tiene el ISRC del mismo artista y la misma duración."""

import json

from app import affinity
from app.musicbrainz import MusicBrainzClient
from tests.test_deezer import Fake
from tests.test_essentials import top

SEED = "98e34bc2-0e71-4205-8986-af891195ed4e"


class MbFake:
    def __init__(self, recordings):
        self.recordings = recordings

    def __call__(self, url, headers, timeout):
        return 200, json.dumps({"recordings": self.recordings}).encode(), None


def routes():
    return {
        "track/100": {"id": 100, "title": "Hoodlum", "title_short": "Hoodlum", "artist": {"id": 384675, "name": "Traumer"}},
        "artist/384675/related": {"data": [{"id": 384675}, {"id": 1, "name": "Chris Stussy"}, {"id": 2, "name": "Priku"},
                                           {"id": 3, "name": "Arapu"}]},
        # Chris Stussy: su remix de «Hoodlum» y la propia «Hoodlum» quedan fuera; entra «Desire».
        "artist/1/top": {"data": [top(11, "Hoodlum (Chris Stussy Remix)", "(Chris Stussy Remix)", 1, "Chris Stussy"),
                                  top(12, "Hoodlum", "", 1, "Chris Stussy"), top(13, "Desire", "", 1, "Chris Stussy", 400)]},
        # Priku: solo remixes de otros (artista principal distinto): sin propuesta.
        "artist/2/top": {"data": [top(21, "Sol (Priku Remix)", "(Priku Remix)", 9, "Otro")]},
        "artist/3/top": {"data": [top(30, "Lune (MK Dub)", "(MK Dub)", 3, "Arapu"), top(31, "Nouvelle", "", 3, "Arapu")]},
        "track/13": {"isrc": "NLA112300001"}, "track/31": {},
    }


def test_related_artists_own_top_track_never_a_version_of_the_seed():
    rec = {"id": "aaaaaaaa-0000-4000-8000-000000000013", "length": 400000, "first-release-date": "2023-05-01",
           "artist-credit": [{"artist": {"id": "x", "name": "Chris Stussy"}}]}
    client = MusicBrainzClient("test@example.org", transport=MbFake([rec]), sleep=lambda s: None)
    out = affinity.build(SEED, affinity.seed_from_track({"id": "100"}, Fake(routes())), client, Fake(routes()))
    assert out.status == "ready" and out.seed_artist == "Traumer"
    assert [(t.catalog, t.id, t.title) for t in out.tracks] == [
        ("musicbrainz", rec["id"], "Desire"), ("deezer", "deezer:31", "Nouvelle")]
    assert out.tracks[0].year == "2023"


def test_other_artist_name_or_length_falls_back_to_deezer_and_no_match_is_unavailable():
    rec = {"id": "aaaaaaaa-0000-4000-8000-000000000013", "length": 400000, "artist-credit": [{"artist": {"name": "Otro"}}]}
    client = MusicBrainzClient("test@example.org", transport=MbFake([rec]), sleep=lambda s: None)
    assert affinity.build(SEED, affinity.seed_from_track({"id": "100"}, Fake(routes())), client, Fake(routes())).tracks[0].catalog == "deezer"
    assert affinity.build(SEED, None, client, Fake(routes())).status == "unavailable"
    assert affinity.seed_from_track({"id": "100"}, Fake({"track/100": {}})) is None
    # Sin la grabación por ISRC: desde la ficha de Deezer del artista, con el título de MusicBrainz.
    seed = affinity.seed_from_artist({"id": "384675"}, "Traumer", "Hoodlum (Original Mix)")
    assert [t.title for t in affinity.build(SEED, seed, client, Fake(routes())).tracks] == ["Desire", "Nouvelle"]
