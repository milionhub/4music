"""Reglas críticas de los módulos del perfil (funciones puras, sin red)."""

from app import editorial, profile, schemas
from app.wikidata import WikidataInfo
from tests.fixtures import mb


def rg(id_, title, date, ptype="Single", secondary=(), credit=None):
    return {"id": id_, "title": title, "first-release-date": date, "primary-type": ptype,
            "secondary-types": list(secondary), "artist-credit": credit or mb.credit((mb.SEED, "Seed Artist"))}


def test_recent_releases_rules():
    groups = [
        rg("r1", "Old Single", "2019-01-01"),
        rg("r2", "New EP", "2026-05-02", "EP"),
        rg("r3", "Comp", "2026-06-01", "Album", ["Compilation"]),
        rg("r4", "DJ Mix", "2026-06-02", "Album", ["DJ-mix"]),
        rg("r5", "No date", None),
        rg("r6", "Broadcast", "2026-07-01", "Broadcast"),
        rg("r7", "VA", "2026-08-01", credit=mb.credit((mb.SEED, "Seed Artist"), (mb.VARIOUS, "Various Artists"))),
        rg("r8", "Someone else", "2026-09-01", credit=mb.credit((mb.CO_A, "Co A"))),
        rg("r9", "Remixes", "2026-04-01", "EP", ["Remix"]),
    ]
    out = profile.recent_releases(groups, mb.SEED, covers=True)
    assert [r.title for r in out] == ["New EP", "Remixes", "Old Single"]
    assert out[0].primary_type == "EP" and out[0].cover_url.endswith("/release-group/r2/front-250")
    assert len(profile.recent_releases(groups * 3, mb.SEED, covers=False, limit=5)) == 5


def test_highlights_prefer_direct_collaborations_and_fall_back_to_connections():
    recs = [
        {"id": "x1", "title": "Song (Extended Mix)", "artist-credit": [
            {"name": "Seed Artist", "joinphrase": " feat. ", "artist": {"id": mb.SEED, "name": "Seed Artist"}},
            {"name": "Co B", "joinphrase": "", "artist": {"id": mb.CO_B, "name": "Co B"}}]},
        {"id": "x2", "title": "Song", "artist-credit": [
            {"name": "Seed Artist", "joinphrase": " feat. ", "artist": {"id": mb.SEED, "name": "Seed Artist"}},
            {"name": "Co B", "joinphrase": "", "artist": {"id": mb.CO_B, "name": "Co B"}}]},
    ]
    hl, title = profile.highlights(mb.SEED_ARTIST, recs, [], mb.SEED)
    assert title == "collaborations"
    assert [(h.artist.name, h.kind, h.evidence_count) for h in hl] == [("Co B", "featuring", 1)]  # versiones = 1
    assert hl[0].reason == "Colaboración en «Song (Extended Mix)»"
    # Sin colaboraciones directas: solo relaciones musicales (no la personal «married»), como «conexiones».
    hl, title = profile.highlights(mb.SEED_ARTIST, [], [], mb.SEED)
    assert title == "connections" and [h.artist.name for h in hl] == ["The Band"]
    assert profile.highlights(mb.EMPTY_ARTIST, [], [], mb.SEED_EMPTY) == ([], None)


def test_top_tracks_order_dedupe_and_limit():
    tracks = profile.top_tracks(mb.LB_ITEMS + [{"recording_mbid": "z", "recording_name": "Broken"}], covers=True, limit=2)
    assert [t.title for t in tracks] == ["Hit (Extended Mix)", "Hit (Co A Remix)"]
    assert tracks[0].search_query == "Hit (Extended Mix) Seed Artist"
    assert profile.top_tracks([], covers=True) == []


def _artist(**kw):
    base = dict(mbid=mb.SEED, name="Seed", type="Person", country="GB", area="London",
                source=schemas.Source(url="https://musicbrainz.org/artist/x", fetched_at="2026"))
    return schemas.Artist(**{**base, **kw})


def test_identity_bio_never_lists_discography():
    wd = WikidataInfo(qid="Q1", genre_ids=["G"], occupation_ids=["O1", "O2", "O3"])
    labels = {"G": "tech house", "O1": "disc-jockey", "O2": "productor discográfico", "O3": "compositor"}
    assert profile.identity_bio(_artist(), wd, labels).text == "Disc-jockey y productor discográfico de tech house."
    assert profile.identity_bio(_artist(), WikidataInfo(qid="Q1", genre_ids=["G"]), labels).text == "Artista de tech house."
    assert profile.identity_bio(_artist(), WikidataInfo(), {}) is None  # sin ítem verificado: estado vacío
    assert profile.identity_bio(_artist(), WikidataInfo(qid="Q1"), {}) is None  # sin ocupación ni estilo: vacío


def test_editorial_catalog_requires_sources_and_permission(tmp_path, monkeypatch):
    catalog = tmp_path / "editorial.json"
    catalog.write_text('{"version": 1, "artists": {"a": {"bio": {"text": "Texto", "sources": []},'
                       ' "photo": {"url": "https://x/p.jpg", "author": "Ana", "license": "CC BY 4.0"}},'
                       ' "b": {"bio": {"text": "Texto B", "sources": [{"label": "MB", "url": "https://mb"}]},'
                       ' "photo": {"url": "https://x/b.jpg", "author": "Ana", "license": "All rights reserved",'
                       ' "permission": "Cedida por la agencia X por email, 2026-10-16"}}}}', encoding="utf-8")
    original = editorial._load.__wrapped__  # función sin caché
    monkeypatch.setattr(editorial, "_load", lambda: original(str(catalog)))
    assert editorial.bio("a") is None and editorial.photo("a") is None  # sin fuentes / sin permiso: no se publica
    assert editorial.bio("b")["text"] == "Texto B" and editorial.photo("b")["permission"].startswith("Cedida")


def test_shipped_editorial_catalog_is_valid():
    for mbid in ("202ed573-bcb9-4686-bc98-6fc96b1f6ae9", "6f8d9d66-24a0-4faf-97c7-81cd22cb1c7e",
                 "b643c24d-4cd6-4531-88bc-62b39ce43ee1", "319c89bc-c7a3-4139-8386-a2a5b48b4ed7",
                 "4c3cffca-37b7-4ecd-9320-e6dcc2cb837a", "b523b6b8-f2ea-4d6c-ba23-f25e02715727"):
        b = editorial.bio(mbid)
        assert b and 40 <= len(b["text"].split()) <= 120 and b["sources"] and b["reviewed"] is False
        from app import biography
        assert biography.quality_issue(b["text"]) is None  # el catálogo cumple las reglas editoriales
        assert editorial.photo(mbid) is None  # no hay fotos con permiso documentado todavía


def test_highlights_two_by_default_third_only_if_strong():
    def rec(title, other_id, other):
        return {"id": title, "title": title, "artist-credit": mb.credit((mb.SEED, "Seed Artist"), (other_id, other))}
    ids = [f"eeeeeeee-0000-4000-8000-00000000000{i}" for i in range(4)]
    recs = [rec(f"T{i}", ids[i], f"Artist {i}") for i in range(4)]
    hl, _ = profile.highlights(mb.EMPTY_ARTIST, recs, [], mb.SEED)
    assert len(hl) == 2  # créditos sueltos: solo dos tarjetas
    groups = [rg(f"g{i}", f"Joint {i}", "2024", credit=mb.credit((mb.SEED, "Seed Artist"), (ids[2], "Artist 2")))
              for i in range(2)]
    groups += [rg(f"h{i}", f"Other {i}", "2024", credit=mb.credit((mb.SEED, "Seed Artist"), (ids[3], "Artist 3")))
               for i in range(2)]
    hl, _ = profile.highlights(mb.EMPTY_ARTIST, recs[:1], groups, mb.SEED)
    assert len(hl) == 2  # el tercero (Artist 0) solo tiene un crédito suelto: no entra
    groups += [rg(f"k{i}", f"More {i}", "2024", credit=mb.credit((mb.SEED, "Seed Artist"), (ids[1], "Artist 1")))
               for i in range(2)]
    hl, _ = profile.highlights(mb.EMPTY_ARTIST, recs[:1], groups, mb.SEED)
    assert len(hl) == 3 and hl[2].kind == "joint_release"  # tercera solo por ≥2 lanzamientos conjuntos


def test_identity_bio_prefers_wikidata_description_marked_with_its_language():
    labels = {"O": "productor discográfico"}
    en = WikidataInfo(qid="Q1", occupation_ids=["O"], descriptions={"en": "British DJ and producer"})
    bio = profile.identity_bio(_artist(), en, labels)
    assert (bio.kind, bio.text, bio.language) == ("factual", "British DJ and producer.", "en")
    assert [s.label for s in bio.sources] == ["Wikidata Q1"]  # solo Wikidata: nada procedente de Wikipedia
    es = WikidataInfo(qid="Q1", descriptions={"es": "DJ y productor británico", "en": "British DJ and producer"})
    assert (profile.identity_bio(_artist(), es, {}).text, profile.identity_bio(_artist(), es, {}).language) == (
        "DJ y productor británico.", "es")
    # Una descripción de una sola palabra no aporta más que la ocupación.
    short = WikidataInfo(qid="Q1", occupation_ids=["O"], descriptions={"en": "musician"})
    assert profile.identity_bio(_artist(), short, labels).text == "Productor discográfico."


def test_identity_never_mixes_birth_formation_and_area():
    person = {"area": {"name": "United Kingdom", "type": "Country"}, "begin-area": {"name": "Manchester"}}
    ident = profile.identity(person, _artist(area="United Kingdom", begin_date="1990-01-02"),
                             WikidataInfo(qid="Q1", active_since="2012"), None)
    assert (ident.country_name, ident.area, ident.origin, ident.origin_kind) == ("United Kingdom", None, "Manchester", "birth")
    assert ident.formed_year is None and ident.active_since == "2012"  # la fecha de nacimiento no es «desde»
    city = profile.identity({"area": {"name": "London", "type": "City"}}, _artist(), WikidataInfo(), "Reino Unido")
    assert (city.country_name, city.area, city.origin) == ("Reino Unido", "London", None)
