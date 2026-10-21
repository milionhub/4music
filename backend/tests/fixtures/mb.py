"""Respuestas mínimas con la forma de MusicBrainz y Wikimedia, escritas a mano SOLO para pruebas (no son datos de producción)."""

SEED = "11111111-1111-4111-8111-111111111111"
SEED_EMPTY = "22222222-2222-4222-8222-222222222222"
CO_A = "33333333-3333-4333-8333-333333333333"
CO_B = "44444444-4444-4444-8444-444444444444"
BAND = "55555555-5555-4555-8555-555555555555"
SPOUSE = "66666666-6666-4666-8666-666666666666"
VARIOUS = "89ad4ac3-39f7-470e-963a-56509c546377"
QID = "Q42424242"


def artist(mbid=SEED, name="Seed Artist", relations=None, **extra):
    return {"id": mbid, "name": name, "sort-name": name, "type": "Person", "country": "BE", "disambiguation": "",
            "area": {"name": "Belgium", "type": "Country", "iso-3166-1-codes": ["BE"]}, "life-span": {"begin": "1990-05"}, "aliases": [{"name": "Seed Alias"}],
            "relations": relations if relations is not None else [], **extra}


def url_rel(kind, url):
    return {"target-type": "url", "type": kind, "url": {"resource": url}}


SEED_ARTIST = artist(relations=[
    url_rel("official homepage", "https://seed.example"),
    # Misma URL con dos tipos (caso real de Cloonee con Qobuz) y variante con barra final.
    url_rel("purchase for download", "https://open.qobuz.com/artist/1"),
    url_rel("streaming", "https://open.qobuz.com/artist/1"),
    url_rel("free streaming", "https://open.spotify.com/artist/abc"),
    url_rel("free streaming", "https://open.spotify.com/artist/abc/"),
    url_rel("purchase for download", "https://www.beatport.com/artist/seed/1"),
    url_rel("soundcloud", "https://soundcloud.com/seed"),
    url_rel("streaming", "https://music.apple.com/gb/artist/1"),
    url_rel("streaming", "https://music.apple.com/us/artist/1"),
    url_rel("social network", "https://www.instagram.com/seed/"),
    url_rel("wikidata", f"https://www.wikidata.org/wiki/{QID}"),
    {"target-type": "artist", "type": "married", "direction": "forward",
     "artist": {"id": SPOUSE, "name": "Spouse"}},
    {"target-type": "artist", "type": "member of band", "direction": "forward",
     "artist": {"id": BAND, "name": "The Band", "type": "Group", "disambiguation": "duo"}},
])
EMPTY_ARTIST = artist(SEED_EMPTY, "Lonely Artist", relations=[], country=None, area=None, **{"life-span": {}})


def credit(*artists):
    return [{"name": n, "joinphrase": " & " if i < len(artists) - 1 else "", "artist": {"id": m, "name": n}}
            for i, (m, n) in enumerate(artists)]


SEED_RECORDINGS = {"recording-count": 5, "recordings": [
    {"id": "aaaaaaaa-0000-4000-8000-000000000001", "title": "Track One", "length": 300000,
     "first-release-date": "2020", "artist-credit": credit((SEED, "Seed Artist"), (CO_A, "Co A"))},
    # Otra versión de la misma pista: no debe contar como evidencia nueva ni repetirse en colaboraciones.
    {"id": "aaaaaaaa-0000-4000-8000-000000000005", "title": "Track One", "disambiguation": "extended mix",
     "first-release-date": "2020-02", "artist-credit": credit((SEED, "Seed Artist"), (CO_A, "Co A"))},
    {"id": "aaaaaaaa-0000-4000-8000-000000000002", "title": "Track Two", "length": None,
     "first-release-date": "2023-06-01",
     "artist-credit": credit((SEED, "Seed Artist"), (CO_A, "Co A"), (CO_B, "Co B"))},
    {"id": "aaaaaaaa-0000-4000-8000-000000000003", "title": "Solo", "artist-credit": credit((SEED, "Seed Artist"))},
    {"id": "aaaaaaaa-0000-4000-8000-000000000004", "title": "Compilation",
     "artist-credit": credit((SEED, "Seed Artist"), (VARIOUS, "Various Artists"))},
]}
EMPTY_RECORDINGS = {"recording-count": 1, "recordings": [
    {"id": "bbbbbbbb-0000-4000-8000-000000000001", "title": "Alone", "artist-credit": credit((SEED_EMPTY, "Lonely Artist"))},
]}
SEED_RELEASE_GROUPS = {"release-group-count": 5, "release-groups": [
    {"id": "cccccccc-0000-4000-8000-000000000004", "title": "Mix Compilation", "primary-type": "Album",
     "secondary-types": ["Compilation", "DJ-mix"], "first-release-date": "2025-01-01",
     "artist-credit": credit((SEED, "Seed Artist"))},
    {"id": "cccccccc-0000-4000-8000-000000000001", "title": "Old EP", "primary-type": "EP", "secondary-types": [],
     "first-release-date": "2018-03", "artist-credit": credit((SEED, "Seed Artist"))},
    {"id": "cccccccc-0000-4000-8000-000000000002", "title": "Joint Single", "primary-type": "Single",
     "secondary-types": ["Remix"], "first-release-date": "2024-11-15",
     "artist-credit": credit((SEED, "Seed Artist"), (CO_A, "Co A"))},
    {"id": "cccccccc-0000-4000-8000-000000000003", "title": "Undated", "primary-type": None,
     "artist-credit": credit((SEED, "Seed Artist"))},
    {"title": "sin id: forma inesperada"},
]}
SEARCH = {"count": 2, "artists": [
    {"id": SEED, "name": "Traumer", "type": "Person", "country": "FR", "area": {"name": "Paris"},
     "disambiguation": "house/techno", "score": 100},
    {"id": BAND, "name": "TraumeR", "type": "Group", "area": {"name": "São Paulo"},
     "disambiguation": "Brazilian Power Metal Band", "score": 92},
]}


GENRE = "Q598593"
OCCUPATION = "Q130857"


def wikidata_entity(p434=(SEED,), p18=("Seed Artist 2022.jpg",), genres=(GENRE,), occupations=(OCCUPATION,), qid=QID,
                    descriptions=None):
    def claims(values):
        return [{"mainsnak": {"datavalue": {"value": v}}, "rank": "normal"} for v in values]
    return {"entities": {qid: {"id": qid, "claims": {
        "P434": claims(p434), "P18": claims(p18), "P136": claims([{"id": g} for g in genres]),
        "P106": claims([{"id": o} for o in occupations])}, "sitelinks": {"enwiki": {"title": "Seed Artist"}},
        "descriptions": {lang: {"value": v} for lang, v in (descriptions or {}).items()}}}}


COUNTRY_QID = "Q31"
COUNTRY_SEARCH = {"query": {"search": [{"title": COUNTRY_QID}]}}
COUNTRY_ENTITY = {"entities": {COUNTRY_QID: {"id": COUNTRY_QID, "labels": {"es": {"value": "Bélgica"}},
                                             "claims": {"P297": [{"mainsnak": {"datavalue": {"value": "BE"}}, "rank": "normal"}]}}}}


LABELS = {"entities": {GENRE: {"labels": {"en": {"value": "tech house"}}},
                       OCCUPATION: {"labels": {"es": {"value": "disc-jockey"}}}}}
LB_TOP = {"items": None}  # se sustituye en las pruebas por la lista real de ListenBrainz
LB_ITEMS = [
    {"recording_mbid": "dddddddd-0000-4000-8000-000000000001", "recording_name": "Hit (Extended Mix)",
     "artist_name": "Seed Artist", "total_listen_count": 900, "total_user_count": 300,
     "caa_id": 123, "caa_release_mbid": "eeeeeeee-0000-4000-8000-000000000001", "release_name": "Hit"},
    {"recording_mbid": "dddddddd-0000-4000-8000-000000000002", "recording_name": "Hit",
     "artist_name": "Seed Artist", "total_listen_count": 500, "total_user_count": 200},
    {"recording_mbid": "dddddddd-0000-4000-8000-000000000003", "recording_name": "Hit (Co A Remix)",
     "artist_name": "Seed Artist", "total_listen_count": 700, "total_user_count": 250},
    {"recording_mbid": "dddddddd-0000-4000-8000-000000000004", "recording_name": "Deep Cut",
     "artist_name": "Seed Artist", "total_listen_count": 50},
]


def commons_file(license_name="CC BY-SA 4.0", author='<a href="//commons.wikimedia.org/wiki/User:Ph">Ph &amp; Co</a>'):
    return {"query": {"pages": {"1": {"imageinfo": [{
        "thumburl": "https://upload.wikimedia.org/thumb/seed.jpg/640px-seed.jpg?utm_source=commons",
        "thumbwidth": 640, "thumbheight": 427,
        "descriptionurl": "https://commons.wikimedia.org/wiki/File:Seed_Artist_2022.jpg",
        "extmetadata": {"LicenseShortName": {"value": license_name}, "Artist": {"value": author},
                        "LicenseUrl": {"value": "https://creativecommons.org/licenses/by-sa/4.0"},
                        "AttributionRequired": {"value": "true"}}}]}}}}
