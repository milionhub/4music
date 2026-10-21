"""Selección editorial de hechos (sesión 2, capa 1): fundar ≠ dirigir, alias ambiguos fuera, frases sobre un proyecto
propio, sonido por géneros y evolución (no por comparaciones), sin elogios ni frases que dependen de la anterior y
sin que los datos secundarios desplacen proyectos. Datos escritos a mano para pruebas (no son datos de producción)."""

from app import facts
from app.sources import SourceDoc

NAME = "Seed Artist"


def wiki(*sentences: str) -> SourceDoc:
    return SourceDoc("", "Wikipedia (en): Seed Artist", "https://wp", "CC BY-SA 4.0", " ".join(sentences))


def mb(text: str, label: str = "MusicBrainz") -> SourceDoc:
    return SourceDoc("", label, "https://mb", "CC0", text)


def kinds(*docs: SourceDoc) -> dict[str, str]:
    return {f.text: f.kind for f in facts.extract(list(docs), NAME)}


def chosen(*docs: SourceDoc, limit: int = facts.MAX_FACTS) -> list[str]:
    return [f.text for f in facts.select(facts.extract(list(docs), NAME), limit)]


def test_directing_a_label_is_not_founding_it():
    found = kinds(wiki("Seed Artist is a Belgian DJ.",
                       "He is the head of the record label Hot Records, as well as its sub-labels.",
                       "In 2010 Seed Artist founded his own label, Deep Records.",
                       "Publica en Big Label y en Sub Label, un subsello que dirige el propio Seed Artist."))
    assert found["He is the head of the record label Hot Records, as well as its sub-labels."] == "sello que dirige"
    assert found["In 2010 Seed Artist founded his own label, Deep Records."] == "sello propio"
    assert found["Publica en Big Label y en Sub Label, un subsello que dirige el propio Seed Artist."] == "sello que dirige"


def test_ambiguous_aliases_are_left_out_and_confirmed_ones_count():
    aliases = mb("Otros alias del mismo artista: Night Shift, Other Name.", "MusicBrainz (relaciones)")
    # Una fuente descriptiva nombra «Other Name» como otra persona: la relación es ambigua y no se usa.
    friend = wiki("Seed Artist is a Belgian DJ.", "He began playing techno in 1993 with friends such as Other Name.")
    found = facts.extract([friend, aliases], NAME)
    alias = next(f for f in found if f.kind == "alias")
    assert facts.alias_status(alias, [f.text for f in found if f.basis == "frase de la fuente"]) == "ambiguo"
    assert alias.text not in chosen(friend, aliases)
    # Presentado como alias por la fuente: confirmado.
    named = wiki("Seed Artist is a Belgian DJ.", "He also records under the alias Night Shift.")
    found = facts.extract([named, mb("Otros alias del mismo artista: Night Shift.", "MusicBrainz (relaciones)")], NAME)
    alias = next(f for f in found if f.kind == "alias")
    assert facts.alias_status(alias, [f.text for f in found if f.basis == "frase de la fuente"]) == "confirmado"


def test_sentences_about_an_own_project_belong_to_it():
    found = kinds(wiki("Seed Artist is a Belgian DJ.",
                       "In 2012 Seed Artist launched his own party series, Night Shift, at Club One.",
                       "In 2020 the Night Shift party moved to Club Two.",
                       "Club One closed its doors in 2015."))
    assert found["In 2020 the Night Shift party moved to Club Two."] == "fiesta propia"
    assert found["Club One closed its doors in 2015."] != "fiesta propia"  # el club donde se celebraba no es suyo


def test_sound_is_told_with_genres_and_dated_evolution_not_with_references():
    doc = wiki("Seed Artist is a Belgian DJ.",
               "Critics saw his sound as a crossroads between the Track One of Artist A, the Track Two of Artist B "
               "and the Track Three of Artist C.",
               "In 2004 Seed Artist left harder rhythms behind to focus on minimal techno.")
    found = facts.extract([doc], NAME)
    assert {f.kind for f in found[1:]} == {"estilo"}
    selected = chosen(doc, limit=2)
    assert "In 2004 Seed Artist left harder rhythms behind to focus on minimal techno." in selected
    assert not any("crossroads" in t for t in selected)


def test_praise_and_context_dependent_sentences_lose_to_plain_facts():
    doc = wiki("Seed Artist is a Belgian DJ.",
               "Seed Artist is without doubt one of the best techno DJs in the world.",
               "From that point on, Seed Artist played regularly at techno clubs in Antwerp.",
               "In 2008 Seed Artist moved from house to techno.")
    assert chosen(doc, limit=2)[1] == "In 2008 Seed Artist moved from house to techno."


def test_label_lists_and_secondary_data_do_not_displace_projects():
    docs = [wiki("Seed Artist is a Belgian DJ.",
                 "In 2011 Seed Artist launched his own party, Night Shift, at Club One.",
                 "In 2009 Seed Artist founded his own label, Deep Records."),
            mb("País: Bélgica. Activo desde: 2003. Sellos que han publicado su música (no implica que los haya "
               "fundado): Label A, Label B, Label C, Label D.")]
    selected = chosen(*docs, limit=3)
    assert selected == ["Seed Artist is a Belgian DJ.", "In 2009 Seed Artist founded his own label, Deep Records.",
                        "In 2011 Seed Artist launched his own party, Night Shift, at Club One."]


def test_sound_is_found_in_descriptions_and_specialisation_not_in_passing_mentions():
    doc = wiki("Seed Artist is a British DJ from Leeds.",
               "Seed Artist is from Leeds and specialises in house music.",
               "When the Italian house scene was at its peak, Seed Artist bought his first turntables in 1990.",
               "In 2012 his single reached number 31 in the UK Singles Chart.")
    found = {f.text: f.kind for f in facts.extract([doc, mb("Descripción breve: UK techno/house DJ.")], NAME)}
    assert found["Seed Artist is from Leeds and specialises in house music."] == "estilo"  # no «origen»
    assert found["Descripción breve: UK techno/house DJ."] == "estilo"
    assert found["When the Italian house scene was at its peak, Seed Artist bought his first turntables in 1990."] != "estilo"
    # «UK» y «Leeds» aparecen en otros hechos: en un hecho de sonido cuenta el género, no esos nombres.
    selected = chosen(doc, mb("Descripción breve: UK techno/house DJ."))
    assert "Descripción breve: UK techno/house DJ." in selected
    assert "Seed Artist is from Leeds and specialises in house music." in selected
    # El mismo género en dos campos no se envía dos veces.
    same = [mb("Descripción breve: tech house."), SourceDoc("", "Wikidata Q1", "https://wd", "CC0", "Géneros: tech house.")]
    assert sum(t.endswith("tech house.") for t in chosen(wiki("Seed Artist is a British DJ."), *same)) == 1


def test_specific_sentences_survive_enumerations_and_repeated_events_do_not():
    doc = wiki("Seed Artist is a British DJ.",
               "He is a co-founder of Night Shift, Day Shift, Late Shift and Early Shift.",
               "Seed Artist co-founded Night Shift in 2015, initially as a student club night in Leeds.",
               "In 2024 he was named Breakthrough Producer at the Big Awards, and his singles charted in the UK Chart.",
               "Several of his singles have entered the UK Chart, among them Song One, which reached number 48.")
    selected = chosen(doc)
    assert "Seed Artist co-founded Night Shift in 2015, initially as a student club night in Leeds." in selected
    assert sum("UK Chart" in t for t in selected) == 1  # el mismo hecho contado dos veces


def test_filler_fields_never_take_reserved_places_and_little_data_is_not_padded():
    docs = [wiki("Seed Artist is a British DJ.", "In 2010 Seed Artist founded his own label, Deep Records.",
                 "In 2014 Seed Artist launched his own party series, Night Shift, at Club One."),
            mb("País: Reino Unido. Colaboradores habituales: Other DJ, Third DJ.")]
    assert chosen(*docs, limit=3) == ["Seed Artist is a British DJ.",
                                      "In 2010 Seed Artist founded his own label, Deep Records.",
                                      "In 2014 Seed Artist launched his own party series, Night Shift, at Club One."]
    # Solo datos estructurados débiles: no se rellena con eventos ni con sellos donde publica.
    thin = mb("Descripción breve: house/techno. País: Francia. Sellos que han publicado su música (no implica que los "
              "haya fundado): Label A, Label B, Label C.")
    assert chosen(thin) == ["Descripción breve: house/techno."]
