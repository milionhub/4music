"""«Más allá de la cabina» (Artist Intelligence v4): trayectoria estructurada, historias validadas contra los hechos que
citan (sin relleno, sin nombres civiles), respaldo determinista y caché. Datos escritos a mano; Groq simulado."""

import json

from app import biography, schemas, stories, store
from app.groq_client import GroqClient
from app.sources import SourceDoc

MBID = "11111111-1111-4111-8111-111111111111"
OTHER = "22222222-2222-4222-8222-222222222222"


def credit(*ids):
    return [{"artist": {"id": i, "name": "Seed Artist" if i == MBID else "Other DJ"}, "joinphrase": ""} for i in ids]


GROUPS = [
    {"id": "g1", "title": "First Steps EP", "primary-type": "EP", "first-release-date": "2012-03", "artist-credit": credit(MBID)},
    {"id": "g2", "title": "Joint One", "primary-type": "Single", "first-release-date": "2015-01-01", "artist-credit": credit(MBID, OTHER)},
    {"id": "g3", "title": "Joint Two", "primary-type": "Single", "first-release-date": "2016-01-01", "artist-credit": credit(MBID, OTHER)},
]
RELEASES = [
    {"title": "First Steps EP", "date": "2012-03-01", "artist-credit": credit(MBID), "label-info": [{"label": {"name": "Night Label"}}]},
    {"title": "Joint One", "date": "2015-01-01", "artist-credit": credit(MBID, OTHER), "label-info": [{"label": {"name": "Night Label"}}]},
    {"title": "Other", "date": "2018-01-01", "artist-credit": credit(MBID), "label-info": [{"label": {"name": "[no label]"}}]},
]
JOINT = {OTHER: {"joint one", "joint two"}}


def test_trajectory_from_musicbrainz_only_claims_what_is_complete():
    doc = stories.trajectory_doc(MBID, GROUPS, 3, RELEASES, JOINT, {OTHER: "Other DJ"})
    assert doc.label == "MusicBrainz (trayectoria)" and doc.license == "CC0"
    assert doc.text == ("Primer lanzamiento propio: «First Steps EP» (EP, 2012), publicado por el sello Night Label. "
                        "Sellos con más lanzamientos suyos (no implica que los fundara): Night Label. "
                        "Lanzamientos conjuntos con: Other DJ.")
    partial = stories.trajectory_doc(MBID, GROUPS, 40, RELEASES, {}, {})  # página parcial: el más antiguo no es «el primero»
    assert "Primer lanzamiento" not in partial.text


def test_civil_names_of_soloists_are_never_used_but_group_members_are():
    assert stories.civil_names({"disambiguation": "Adrian Niculae, Techno Producer"}, "Priku") == ["Adrian Niculae"]
    assert stories.civil_names({"disambiguation": "house/techno"}, "Traumer") == []
    assert stories.civil_names({"type": "Group", "disambiguation": "Chris Martinez and Steve Martinez"}, "TMB") == []


DOCS = [SourceDoc("H1", "Discogs (perfil)", "u", "CC0", "French DJ and producer based in Paris. Owner of record label Night Label.")]


def test_story_validation_rejects_fluff_and_inference_but_accepts_plain_facts():
    ok = "Desde París, Seed Artist está al frente de Night Label, el sello discográfico del que es propietario."
    assert biography.story_issue("Un sello propio", ok, "Seed Artist", DOCS) is None
    for text, problem in (
            ("Seed Artist es propietario de Night Label, consolidando su presencia en la escena electrónica.", "consolidando"),
            ("En París su estilo toma forma y se inspira en la cultura local, con su sello Night Label.", "toma forma"),
            ("Seed Artist fundó Night Label en 2015 en París para publicar su música.", "año sin respaldo"),
            ("Seed Artist dirige Night Label y también Day Label desde la ciudad de París.", "nombre sin respaldo (Day)")):
        assert problem in (biography.story_issue("Un sello propio", text, "Seed Artist", DOCS) or ""), text


class FakeGroq:
    def __init__(self, payloads):
        self.payloads, self.calls = list(payloads), 0

    def __call__(self, url, headers, body, timeout):
        self.calls += 1
        content = json.dumps(self.payloads.pop(0) if self.payloads else {"stories": []})
        return 200, json.dumps({"choices": [{"finish_reason": "stop", "message": {"content": content}}]}).encode(), None


def groq_with(payloads):
    fake = FakeGroq(payloads)
    return GroqClient("test-key", "test-model", transport=fake, sleep=lambda s: None), fake


EVIDENCE = [SourceDoc("", "Discogs (perfil)", "https://www.discogs.com/artist/1", "CC0",
                      "French DJ and producer based in Paris. Owner of record label Night Label. "
                      "Seed Artist started DJing in 2009 at small clubs in Lyon."),
            SourceDoc("", "MusicBrainz (trayectoria)", "https://musicbrainz.org/artist/x", "CC0",
                      "Primer lanzamiento propio: «First Steps EP» (EP, 2012), publicado por el sello Night Label.")]
REFS = {"musicbrainz": schemas.SourceRef(label="MusicBrainz", url="https://mb", license="CC0")}
STRUCTURED = [schemas.Story(key="momento", title="Sobre el escenario", text="Su nombre figura entre los artistas de A 2020 y B 2021.",
                            sources=[REFS["musicbrainz"]])]


def test_generated_stories_are_validated_one_by_one_merged_and_cached():
    groq, fake = groq_with([{"stories": [
        {"key": "inicios", "title": "Primeras sesiones", "fact_ids": ["H1"],
         "text": "Seed Artist empezó a pinchar en 2009 en pequeños clubes de Lyon."},
        # Inventa un sello que no consta: se descarta esta historia, no las demás.
        {"key": "universo", "title": "Dos sellos", "fact_ids": ["H2"], "text": "Seed Artist dirige Night Label y Day Label desde París."},
    ]}])
    out = stories.generate(MBID, "Seed Artist", "solista", lambda: [d.model_copy() if hasattr(d, "model_copy") else d for d in EVIDENCE],
                           lambda: STRUCTURED, groq)
    assert [s.key for s in out.stories] == ["inicios", "momento"] and out.mode == "mixed"
    assert out.stories[0].text.startswith("Seed Artist empezó a pinchar en 2009")
    assert [s.label for s in out.stories[0].sources] == ["Discogs (perfil)"]
    again = stories.generate(MBID, "Seed Artist", "solista", lambda: [], lambda: [], groq)
    assert again == out and fake.calls == 1  # desde la caché, sin volver a llamar al modelo


def test_without_valid_generation_structured_stories_with_short_ttl_and_never_civil_names():
    groq, fake = groq_with([{"stories": [{"key": "inicios", "title": "Su nombre real", "fact_ids": ["H1"],
                                         "text": "Adrian Niculae empezó a pinchar en 2009 en pequeños clubes de Lyon."}]}] * 2)
    out = stories.generate(OTHER, "Seed Artist", "solista", lambda: [SourceDoc(d.id, d.label, d.url, d.license, d.text) for d in EVIDENCE],
                           lambda: STRUCTURED, groq, avoid=["Adrian Niculae"])
    assert out.mode == "structured" and out.stories == STRUCTURED and fake.calls == 2  # un reintento, nada más
    assert store.get(stories.KIND, OTHER)["version"] == stories.VERSION
    offline = stories.generate("33333333-3333-4333-8333-333333333333", "Seed Artist", "solista", lambda: [], lambda: [],
                               GroqClient("", "none"))
    assert offline.status == "unavailable" and offline.stories == []  # sin datos: la app no muestra la sección


def test_structured_stories_use_verified_data_and_skip_poor_events():
    identity = schemas.Identity(founded_labels=["NO ART"], label_years={"NO ART": "2017"}, members=["Ana", "Bea"])
    mb = {"relations": [{"target-type": "event", "type": "main performer", "event": {"name": n}}
                        for n in ("Big Festival 2024, Day 1: Main", "#RAVETAG", "Seed Artist presents", "Other Fest 2025")]}
    traj = stories.trajectory_doc(MBID, GROUPS, 3, RELEASES, JOINT, {OTHER: "Other DJ"})
    out = stories.structured_stories("Seed Artist", True, identity, mb, MBID, traj, REFS)
    assert [s.key for s in out] == ["inicios", "universo", "momento"]
    assert out[0].text == ("Su primer lanzamiento propio conocido es «First Steps EP», un EP de 2012 que salió en el sello "
                           "Night Label. Desde entonces han firmado varios trabajos junto a Other DJ.")
    assert out[1].text == "Fundaron el sello NO ART (2017). El proyecto lo forman Ana y Bea."
    assert out[2].text == "Su nombre figura entre los artistas de Big Festival 2024 y Other Fest 2025."
