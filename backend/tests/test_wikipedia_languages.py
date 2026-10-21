"""Wikipedia en otros idiomas (capa 1.2): solo sin artículo en español ni en inglés, por el sitelink del ítem
verificado y confirmando que la página enlaza al mismo ítem; reglas de clasificación aparte para esos idiomas y la
misma exigencia de evidencia en el validador. Datos escritos a mano (no son de producción); sin red."""

from app import biography, facts, sources, wikidata
from app.musicbrainz import Fetched
from app.sources import SourceDoc
from app.wikidata import WikidataInfo

DE_TEXT = ("ANOTR ist ein niederländisches House-Duo.\n== Geschichte ==\nSie gründeten das Eigenlabel No Art 2017 "
           "und ihr eigenes Festival in Amsterdam. Von 2017 an wurden sie Resident DJs auf dem ANTS.\n"
           "== Diskografie ==\nOn a Trip (2025)")


class FakeWiki:
    """Respuestas por idioma: {lang: (extract, pageprops)}; registra los idiomas consultados."""

    def __init__(self, pages):
        self.pages, self.langs = pages, []

    def get(self, url, params):
        lang = url.split("//")[1].split(".")[0]
        self.langs.append(lang)
        extract, props = self.pages[lang]
        page = {"extract": extract, **({"pageprops": props} if props is not None else {})}
        return Fetched({"query": {"pages": {"1": page}}}, url, "2026", stale=False)


def test_resolve_keeps_only_the_supported_other_language_sitelinks():
    entity = {"entities": {"Q9": {"claims": {"P434": [{"mainsnak": {"datavalue": {"value": "mbid-1"}}}]},
                                  "sitelinks": {"dewiki": {"title": "ANOTR"}, "svwiki": {"title": "ANOTR"},
                                                "commonswiki": {"title": "Category:ANOTR"}}}}}

    class Wiki:
        def search_by_mbid(self, mbid):
            return Fetched({"query": {"search": [{"title": "Q9"}]}}, "u", "2026", False)

        def entity_claims(self, qid):
            return Fetched(entity, "u", "2026", False)

    info = wikidata.resolve({"relations": []}, "mbid-1", Wiki())
    assert info.wikipedia == {} and info.other_wikipedia == {"dewiki": "ANOTR"}


def test_other_language_article_only_without_spanish_or_english_and_only_for_the_same_item():
    wd = WikidataInfo(qid="Q9", other_wikipedia={"dewiki": "ANOTR", "nlwiki": "ANOTR"})
    wiki = FakeWiki({"de": (DE_TEXT, {"wikibase_item": "Q9"}), "nl": ("ANOTR is een Nederlands duo. " * 5, {})})
    docs = sources.wikipedia_articles(wiki, wd)
    assert [(d.label, d.license, d.url) for d in docs] == [
        ("Wikipedia (de): ANOTR", "CC BY-SA 4.0", "https://de.wikipedia.org/wiki/ANOTR")]
    assert "Diskografie" not in docs[0].text and "On a Trip" not in docs[0].text  # secciones no narrativas fuera
    assert wiki.langs == ["de"]  # un único artículo: no se suman traducciones
    # Otro ítem (homónimo o redirección) o desambiguación: se descarta y se prueba el siguiente idioma.
    other = FakeWiki({"de": (DE_TEXT, {"wikibase_item": "Q77"}),
                      "nl": ("ANOTR is een Nederlands dj-duo uit Amsterdam. " * 3, {"wikibase_item": "Q9"})})
    assert [d.label for d in sources.wikipedia_articles(other, wd)] == ["Wikipedia (nl): ANOTR"]
    ambiguous = FakeWiki({"de": (DE_TEXT, {"wikibase_item": "Q9", "disambiguation": ""}), "nl": ("", {})})
    assert sources.wikipedia_articles(ambiguous, wd) == []
    # Con artículo en inglés, el de otro idioma no se consulta (evita duplicar).
    english = FakeWiki({"en": ("ANOTR are a Dutch house duo from Amsterdam. " * 3, None), "de": (DE_TEXT, {})})
    assert [d.label for d in sources.wikipedia_articles(english, WikidataInfo(
        qid="Q9", wikipedia={"enwiki": "ANOTR"}, other_wikipedia={"dewiki": "ANOTR"}))] == ["Wikipedia (en): ANOTR"]
    assert english.langs == ["en"]


def test_other_language_sentences_get_only_the_essential_relations():
    doc = SourceDoc("", "Wikipedia (de): ANOTR", "https://de.wikipedia.org/wiki/ANOTR", "CC BY-SA 4.0",
                    sources._narrative(DE_TEXT))
    kinds = {f.text: f.kind for f in facts.extract([doc], "ANOTR")}
    assert kinds == {"ANOTR ist ein niederländisches House-Duo.": "identidad",
                     "Sie gründeten das Eigenlabel No Art 2017 und ihr eigenes Festival in Amsterdam.": "sello propio",
                     "Von 2017 an wurden sie Resident DJs auf dem ANTS.": "residencia"}
    assert facts.descriptive_count(facts.extract([doc], "ANOTR")) == 3


def test_validator_accepts_founding_in_other_languages_with_the_same_name_requirement():
    docs = [SourceDoc("H1", "Wikipedia (de): ANOTR", "https://de.wikipedia.org/wiki/ANOTR", "CC BY-SA 4.0",
                      "Sie gründeten das Eigenlabel No Art 2017. Von 2017 an wurden sie Resident DJs auf dem ANTS.")]
    assert biography.claim_issue("ANOTR fundaron el sello No Art en 2017.", "ANOTR", docs) is None
    assert biography.claim_issue("ANOTR son residentes de ANTS.", "ANOTR", docs) is None
    assert "sello o proyecto fundado: Other" in biography.claim_issue("ANOTR fundaron Other Art.", "ANOTR", docs)
    assert "residencia en club o fiesta: Amnesia" in biography.claim_issue("ANOTR son residentes de Amnesia.",
                                                                          "ANOTR", docs)
