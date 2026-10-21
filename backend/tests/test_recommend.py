"""Regresiones del motor de recomendación (T1.3): señales fuertes antes que créditos incidentales, exclusiones,
varios favoritos, diversidad y determinismo. Datos de prueba escritos a mano (no son datos de producción)."""

from app import recommend
from app.recommend import SeedData

A, B = "aaaaaaaa-0000-4000-8000-00000000000a", "bbbbbbbb-0000-4000-8000-00000000000b"
SIM1, SIM2, VOCAL, LABELMATE, OLDLABEL, DOUBLE, ONEOFF = (f"cccccccc-0000-4000-8000-00000000000{i}" for i in range(1, 8))
LABEL, BIG_LABEL = "11111111-0000-4000-8000-000000000001", "11111111-0000-4000-8000-000000000002"
VA = "89ad4ac3-39f7-470e-963a-56509c546377"


def credit(*artists):
    return [{"name": n, "artist": {"id": m, "name": n}} for m, n in artists]


def release(title, date, label=LABEL, *artists):
    return {"title": title, "date": date, "artist-credit": credit(*artists),
            "label-info": [{"label": {"id": label, "name": "Scene Records"}}] if label else []}


def seed_a():
    return SeedData(
        mbid=A, name="Seed A",
        similar=[{"artist_mbid": SIM1, "name": "Similar Uno", "score": 100, "_algorithm": "x"},
                 {"artist_mbid": SIM2, "name": "Similar Dos", "score": 20, "_algorithm": "x"}],
        releases=[
            release("Own 1", "2019", LABEL, (A, "Seed A")),
            release("Own 2", "2021", LABEL, (A, "Seed A")),
            release("Feat Vocalist", "2022", LABEL, (A, "Seed A"), (VOCAL, "Vocalista Invitado")),  # 1 crédito suelto
            release("Twice 1", "2020", None, (A, "Seed A"), (DOUBLE, "Socio Habitual")),
            release("Twice 2", "2023", None, (A, "Seed A"), (DOUBLE, "Socio Habitual")),
            release("Comp", "2022", None, (VA, "Various Artists"), (A, "Seed A")),
        ],
        label_pages={LABEL: {"release-count": 40, "releases": [
            release("L1", "2020", LABEL, (LABELMATE, "Compañero de Sello")),
            release("L2", "2022", LABEL, (LABELMATE, "Compañero de Sello")),
            release("Old 1", "1995", LABEL, (OLDLABEL, "Otra Época")),
            release("Old 2", "1996", LABEL, (OLDLABEL, "Otra Época")),
            release("L3", "2021", LABEL, (ONEOFF, "Una Vez")),
        ]}})


def names(cards):
    return [c.artist.name for c in cards]


def test_strong_signals_rank_and_incidental_credits_are_excluded():
    cards = recommend.recommend([seed_a()], exclude=set(), limit=10)
    got = names(cards)
    assert got[0] == "Similar Uno" and cards[0].kind == "affinity"
    assert cards[0].headline == "Afín a Seed A según ListenBrainz"
    assert "Compañero de Sello" in got and "Socio Habitual" in got
    # Negativos: vocalista de un solo lanzamiento, mismo sello en otra época, una sola aparición, recopilatorio.
    for bad in ("Vocalista Invitado", "Otra Época", "Una Vez", "Various Artists", "Seed A"):
        assert bad not in got
    label_card = next(c for c in cards if c.artist.name == "Compañero de Sello")
    assert label_card.tag == "Sello compartido" and label_card.headline == "Publica en Scene Records, como Seed A"
    assert all(0 < c.score <= 1 for c in cards)


def test_affinity_beats_weak_documentary_coincidence():
    seed = seed_a()
    seed.label_pages = {}
    cards = recommend.recommend([seed], exclude=set(), limit=10)
    weak = [c for c in cards if c.kind == "collaboration"]
    assert names(cards).index("Similar Dos") < names(cards).index(weak[0].artist.name)


def test_exclusions_and_reproducibility():
    seed = seed_a()
    cards = recommend.recommend([seed], exclude={SIM1, LABELMATE}, limit=10)
    assert "Similar Uno" not in names(cards) and "Compañero de Sello" not in names(cards)
    assert names(recommend.recommend([seed_a()], set(), 10)) == names(recommend.recommend([seed_a()], set(), 10))


def test_multiple_favorites_strengthen_and_are_explained():
    seed_b = SeedData(mbid=B, name="Seed B", similar=[{"artist_mbid": SIM2, "name": "Similar Dos", "score": 50, "_algorithm": "x"}])
    single = {c.artist.mbid: c.score for c in recommend.recommend([seed_a()], set(), 10)}
    both = {c.artist.mbid: c for c in recommend.recommend([seed_a(), seed_b], set(), 10)}
    assert both[SIM2].score > single[SIM2] and both[SIM2].kind == "multiple_favorites"
    assert both[SIM2].tag == "Varios de tus favoritos" and both[SIM2].headline.startswith("Conecta con Seed")


def test_diversity_interleaves_seeds_and_limit_returns_fewer():
    seed_b = SeedData(mbid=B, name="Seed B", similar=[{"artist_mbid": f"dddddddd-0000-4000-8000-00000000000{i}",
                                                      "name": f"B{i}", "score": 60 - i, "_algorithm": "x"} for i in range(5)])
    cards = recommend.recommend([seed_a(), seed_b], set(), 4)
    seeds = [c.reasons[0].seed_mbid for c in cards]
    assert A in seeds and B in seeds  # ninguna semilla acapara la lista
    lonely = SeedData(mbid=B, name="Seed B", releases=[release("Solo", "2020", None, (B, "Seed B"))])
    assert recommend.recommend([lonely], set(), 10) == []  # sin señales de calidad: ninguna recomendación
