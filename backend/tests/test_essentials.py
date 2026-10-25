"""Tracks esenciales: solo canciones propias del ranking de Deezer, una por título, con TrackDNA completo si
MusicBrainz tiene el ISRC del artista con la misma duración; y reglas nuevas de «Más allá de la cabina» (v6)."""

from app import essentials, schemas, stories
from app.musicbrainz import MusicBrainzClient
from tests.test_deezer import Fake

ARTIST = "319c89bc-0000-4000-8000-000000000001"


def top(id_, title, version="", artist_id=384675, artist="Traumer", duration=414):
    return {"id": id_, "title": title, "title_short": title.split(" (")[0], "title_version": version, "duration": duration,
            "artist": {"id": artist_id, "name": artist}, "link": f"https://www.deezer.com/track/{id_}",
            "album": {"title": "Dedust EP", "cover_xl": "https://cdn-images.dzcdn.net/images/cover/x/1000x1000.jpg"}}


def test_pick_own_songs_once_without_remixes_by_others():
    ranking = [top(1, "Cyclo"), top(2, "We Do (Edit)", "(Edit)"), top(3, "Sunday Loop (Traumer Stripped Down)", artist_id=9,
               artist="DJ Deep"), top(4, "Express (DeWalta Remix)", "(DeWalta Remix)"), top(5, "We Do"), top(6, "Hoodlum"),
               top(7, "Drive"), top(8, "District")]
    picked = essentials.pick(ranking, "384675")
    assert [t["id"] for t in picked] == [1, 5, 6, 7], "sin el remix de DeWalta, sin el de DJ Deep, la original de We Do"


class MbFake:
    def __init__(self, recordings):
        self.recordings = recordings

    def __call__(self, url, headers, timeout):
        import json
        return 200, json.dumps({"recordings": self.recordings}).encode(), None


def test_build_links_trackdna_by_isrc_or_falls_back_to_deezer():
    rec = {"id": "98e34bc2-0e71-4205-8986-af891195ed4e", "length": 414000, "first-release-date": "2014-03-10",
           "artist-credit": [{"artist": {"id": ARTIST}}]}
    client = MusicBrainzClient("test@example.org", transport=MbFake([rec]), sleep=lambda s: None)
    routes = {"artist/384675/top": {"data": [top(6, "Hoodlum"), top(1, "Cyclo", duration=521)]},
              "track/6": {"isrc": "DEHE41400041"}, "track/1": {}}
    out = essentials.build(ARTIST, {"id": "384675"}, client, Fake(routes))
    assert [(t.catalog, t.id) for t in out.tracks] == [("musicbrainz", rec["id"]), ("deezer", "deezer:1")]
    assert out.tracks[0].year == "2014" and out.status == "ready" and "Deezer" in out.basis
    other = MusicBrainzClient("test@example.org", transport=MbFake([{**rec, "length": 300000}]), sleep=lambda s: None)
    assert essentials.build(ARTIST, {"id": "384675"}, other, Fake(routes)).tracks[0].catalog == "deezer", "otra duración"
    assert essentials.build(ARTIST, None, client, Fake(routes)).status == "unavailable"


def test_stories_reject_generic_titles_and_genre_only_texts():
    assert stories.GENERIC_TITLE_RE.match("Primer lanzamiento") and stories.GENERIC_TITLE_RE.match("Su propio universo")
    assert not stories.GENERIC_TITLE_RE.match("El nacimiento de Plus 8")
    assert not stories.GENERIC_TITLE_RE.match("Primeros pasos en Detroit"), "nombra un lugar: es concreto"
    assert stories.GENERIC_TITLE_RE.match("Primer lanzamiento 2014"), "un año no lo hace concreto"
    assert stories.GENRE_ONLY_RE.search("Traumer trabaja dentro del house y el techno.")


def test_structured_stories_skip_date_only_events_and_use_concrete_titles():
    identity = schemas.Identity(founded_labels=["Gettraum"])
    events = [{"target-type": "event", "type": "main performer", "event": {"name": n}}
              for n in ("1979‐09‐21", "Dour 2017", "Montreux Jazz Festival 2018")]
    refs = {"musicbrainz": schemas.SourceRef(label="MusicBrainz", url="https://musicbrainz.org/artist/x", license="CC0")}
    doc = stories.SourceDoc("", stories.TRAJECTORY_LABEL, "https://musicbrainz.org/artist/x", "CC0",
                            "Primer lanzamiento propio: «E-Bird» (single, 2009), publicado por el sello IRM Records.")
    out = {s.key: s for s in stories.structured_stories("Traumer", False, identity, {"relations": events}, "x", doc, refs)}
    assert out["inicios"].title == "Todo empezó con «E-Bird»"
    assert out["universo"].title == "El universo Gettraum"
    assert out["momento"].title == "En el cartel de Dour" and "1979" not in out["momento"].text


def test_trajectory_ignores_dj_mixes_as_first_release():
    groups = [{"title": "Amnesia Ibiza Underground #4", "first-release-date": "2004", "primary-type": "Album",
               "secondary-types": ["Compilation", "DJ-mix"], "artist-credit": [{"artist": {"id": "m"}}]},
              {"title": "Shake EP", "first-release-date": "2006", "primary-type": "EP", "artist-credit": [{"artist": {"id": "m"}}]}]
    doc = stories.trajectory_doc("m", groups, 2, [], {}, {})
    assert "Shake EP" in doc.text and "Amnesia" not in doc.text
