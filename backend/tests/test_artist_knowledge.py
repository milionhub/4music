"""Sesión 2: expediente de hechos (relaciones de MusicBrainz, Wikipedia completa), identidad por ID de Discogs,
fotos de Commons por «representa» (P180), géneros representativos y validación de sonido, géneros y gentilicios.
Datos escritos a mano para pruebas (no son datos de producción)."""

from app import biography, facts, images, profile, schemas, sources, wikidata
from app.musicbrainz import Fetched
from app.wikidata import WikidataInfo

MBID = "11111111-1111-4111-8111-111111111111"


def fetched(data: dict) -> Fetched:
    return Fetched(data, "https://test", "2026", stale=False)


class FakeWiki:
    """Respuestas de Wikimedia por método; registra las llamadas."""

    def __init__(self, **responses):
        self.responses, self.calls = responses, []

    def __getattr__(self, method):
        def call(*args):
            self.calls.append((method, args))
            value = self.responses.get(method, {})
            return fetched(value(*args) if callable(value) else value)
        return call


MB_ARTIST = {"id": MBID, "relations": [
    {"target-type": "label", "type": "label founder", "direction": "forward", "begin": "2011",
     "label": {"name": "Hot Label"}},
    {"target-type": "label", "type": "recording contract", "direction": "forward", "label": {"name": "Big Label"}},
    {"target-type": "artist", "type": "is person", "direction": "forward", "artist": {"name": "Alias One"}},
    {"target-type": "event", "type": "main performer", "direction": "forward",
     "event": {"name": "Seed Artist b2b Other DJ"}},
    {"target-type": "event", "type": "main performer", "direction": "forward",
     "event": {"name": "Big Festival 2019, Friday: Main Stage"}},
    {"target-type": "url", "type": "discogs", "url": {"resource": "https://www.discogs.com/artist/123-Seed"}},
]}


def test_musicbrainz_relations_keep_their_exact_meaning():
    doc = sources.musicbrainz_relations(MB_ARTIST, "Seed Artist")
    assert doc.text == ("Sello fundado por el artista: Hot Label (desde 2011). Otros alias del mismo artista: Alias One. "
                        "B2B documentado: Seed Artist b2b Other DJ. Actuaciones documentadas en eventos (no implica "
                        "cabeza de cartel ni residencia): Big Festival 2019.")
    assert "Big Label" not in doc.text  # un contrato discográfico no es una fundación
    kinds = {f.text.split(":")[0]: (f.kind, f.basis) for f in facts.extract([doc], "Seed Artist")}
    assert kinds["Sello fundado por el artista"] == ("sello propio", "relación estructurada")
    assert kinds["B2B documentado"][0] == "colaboración" and kinds["Otros alias del mismo artista"][0] == "alias"
    # «fundó» queda respaldado por la relación explícita; «residencia», no.
    docs = facts.as_docs(facts.select(facts.extract([doc], "Seed Artist")))
    assert biography.claim_issue("Seed Artist fundó Hot Label en 2011.", "Seed Artist", docs) is None
    assert "residencia" in biography.claim_issue("Seed Artist es residente en Big Festival.", "Seed Artist", docs)


def test_wikidata_by_discogs_id_only_when_the_item_confirms_it():
    entity = {"entities": {"Q9": {"claims": {"P1953": [{"mainsnak": {"datavalue": {"value": "123"}}}]},
                                  "sitelinks": {}}}}
    wiki = FakeWiki(search_by_mbid={"query": {"search": []}}, search_statement={"query": {"search": [{"title": "Q9"}]}},
                    entity_claims=entity)
    info = wikidata.resolve(MB_ARTIST, MBID, wiki)
    assert (info.qid, info.via) == ("Q9", "discogs_id")
    assert ("search_statement", ("P1953", "123")) in wiki.calls
    # El ítem declara OTRO MBID: es otro artista con el mismo ID de Discogs (dato erróneo) → no se usa.
    other = {"entities": {"Q9": {"claims": {"P1953": [{"mainsnak": {"datavalue": {"value": "123"}}}],
                                            "P434": [{"mainsnak": {"datavalue": {"value": "other-mbid"}}}]}}}}
    wiki = FakeWiki(search_by_mbid={"query": {"search": []}}, search_statement={"query": {"search": [{"title": "Q9"}]}},
                    entity_claims=other)
    assert wikidata.resolve(MB_ARTIST, MBID, wiki).reason == "mbid_mismatch"
    # Dos ítems con el mismo ID: ambiguo.
    wiki = FakeWiki(search_by_mbid={"query": {"search": []}},
                    search_statement={"query": {"search": [{"title": "Q9"}, {"title": "Q10"}]}})
    assert wikidata.resolve(MB_ARTIST, MBID, wiki).reason == "no_wikidata_item"


def _mediainfo(depicts):
    return {"entities": {"M1": {"statements": {"P180": [
        {"mainsnak": {"datavalue": {"value": {"id": q}}}} for q in depicts]}}}}


def test_commons_photo_by_depicts_only_if_it_shows_only_that_artist():
    commons = {"query": {"pages": {"1": {"imageinfo": [{
        "thumburl": "https://upload.wikimedia.org/a.jpg", "descriptionurl": "https://commons.wikimedia.org/wiki/File:A.jpg",
        "extmetadata": {"LicenseShortName": {"value": "CC BY 4.0"}, "Artist": {"value": "Ph"}}}]}}}}
    search = {"query": {"search": [{"title": "File:A.jpg"}, {"title": "File:Poster.pdf"}]}}
    wd = WikidataInfo(qid="Q9")
    wiki = FakeWiki(commons_depicting=search, commons_depicts=_mediainfo(["Q9"]), commons_file=commons)
    image, reason = images.resolve(fetched({"relations": []}), MBID, wiki, wd)
    assert reason is None and image.via == "commons_depicts" and image.license == "CC BY 4.0"
    assert all(args != ("File:Poster.pdf",) for _m, args in wiki.calls)  # solo fotos
    group = FakeWiki(commons_depicting=search, commons_depicts=_mediainfo(["Q9", "Q77"]), commons_file=commons)
    assert images.resolve(fetched({"relations": []}), MBID, group, wd) == (None, "no_image")  # foto de grupo: no


def test_styles_prefer_specific_documented_genres():
    labels = {"Q1": "música electrónica", "Q2": "pop", "Q3": "tech house"}
    jones = WikidataInfo(qid="Q", genre_ids=["Q1", "Q2"])
    # «pop» sin confirmar y «música electrónica» genérico ceden ante lo que dice la descripción de MusicBrainz.
    assert [(s.label, s.source) for s in profile.styles(jones, labels, "UK techno/house DJ & producer")] == [
        ("techno", "musicbrainz"), ("house", "musicbrainz")]
    assert [s.label for s in profile.styles(jones, labels)] == ["música electrónica"]  # sin nada mejor, el genérico
    assert [s.label for s in profile.styles(WikidataInfo(qid="Q", genre_ids=["Q3"]), labels, "house/techno",
                                            "X is a DJ. He also loves acid house.")] == ["tech house", "house", "techno"]
    assert profile.text_genres("a deep-house and tech house DJ") == ["deep house", "tech house"]  # no «house» suelto


def test_validator_rejects_invented_sound_genres_nationality_and_influence():
    docs = [sources.SourceDoc("H1", "Wikipedia (en): X", "https://wp", "CC BY-SA 4.0",
                              "Jamie Jones is a Welsh DJ and producer. Jones hosted his own Paradise party at Ibiza's "
                              "DC10 nightclub. In 2012 he released an EP in collaboration with Adam Beyer.")]
    base = ("Jamie Jones es un DJ y productor galés que durante varias temporadas organizó su propia fiesta, "
            "Paradise, en el DC10 de Ibiza.")
    assert biography.validate(base, "Jamie Jones", docs) is None
    for extra, problem in (
            (" Su sonido fusiona deep house con techno.", "descripción del sonido"),
            (" Es un DJ de deep house.", "género sin respaldo (deep house)"),
            (" En 2012 colaboró con el sueco Adam Beyer.", "nacionalidad sin respaldo"),
            (" Ha consolidado su influencia en la escena.", "relevancia o influencia"),
            (" Es uno de los DJs más influyentes.", "relevancia o influencia")):
        assert problem in (biography.validate(base + extra, "Jamie Jones", docs) or ""), extra
    club = base.replace("su propia fiesta, Paradise, en el DC10", "su propio club, Paradise, en Ibiza")
    assert "club propio" in biography.validate(club, "Jamie Jones", docs)


def test_full_articles_are_not_clipped_to_the_old_limit():
    long_text = "Intro sentence about the artist. " * 80 + "In 2020 he launched his own party series, Metamorfosi."
    wiki = FakeWiki(get=lambda url, params: {"query": {"pages": {"1": {"extract": long_text}}}})
    docs = sources.wikipedia_articles(wiki, WikidataInfo(qid="Q", wikipedia={"eswiki": "X", "enwiki": "X"}))
    assert [d.label for d in docs] == ["Wikipedia (es): X", "Wikipedia (en): X"]
    assert all("Metamorfosi" in d.text for d in docs)  # antes se cortaba a 1800 caracteres
    found = facts.extract(docs[1:], "X")
    assert any(f.kind == "fiesta propia" and "Metamorfosi" in f.entities for f in found)


def test_identity_lists_founded_labels_and_projects_from_explicit_relations():
    artist = schemas.Artist.model_validate({
        "mbid": MBID, "name": "Seed", "type": "Person", "links": [],
        "source": {"provider": "musicbrainz", "url": "https://mb", "fetched_at": "2026", "stale": False}})
    data = {**MB_ARTIST, "relations": MB_ARTIST["relations"] + [
        {"target-type": "artist", "type": "member of band", "direction": "forward", "artist": {"name": "The Band"}}]}
    ident = profile.identity(data, artist, WikidataInfo(), None)
    assert ident.founded_labels == ["Hot Label"] and ident.projects == ["The Band"] and ident.members == []
