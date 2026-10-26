"""TrackDNA V5.2: géneros por grabación o lanzamiento (nunca del artista), samples/mashups/covers documentados y
búsqueda que no devuelve coincidencias vagas. Datos escritos a mano a partir del piloto real."""

from app import schemas, tracks
from app.wikidata import WikidataInfo

REC = "98e34bc2-0000-4000-8000-000000000000"


def credit(name, mbid):
    return [{"artist": {"id": mbid, "name": name}, "name": name, "joinphrase": ""}]


def test_genre_family_and_style_without_broad_tags():
    assert tracks.genre_values(["deep house", "electronic", "house"]) == ["House", "Deep House"]
    assert tracks.genre_values(["house"]) == ["House"]
    assert tracks.genre_values(["techno"]) == ["Techno"]
    assert tracks.genre_values(["electronic"]) == ["Electrónica"]
    assert tracks.genre_values(["minimal techno", "dub techno"]) == ["Techno", "Minimal Techno", "Dub Techno"]
    assert tracks.genre_values([]) == []
    assert tracks.mb_genres({"genres": [{"name": "House", "count": 1}, {"name": "deep house", "count": 3}], "tags": [{"name": "x"}]}) \
        == ["deep house", "house"]  # por votos; las etiquetas libres no cuentan


def _dna(recording_genres, release_genres, artist_styles=()):
    release = schemas.TrackRelease(mbid="rg1", title="Dedust", url="https://musicbrainz.org/release-group/rg1")
    return tracks.dna(REC, "Hoodlum", WikidataInfo(), WikidataInfo(), release, "Traumer", None,
                      [schemas.Style(label=s, qid=None, source="wikidata") for s in artist_styles], [release], None,
                      schemas.TrackRelations(), {}, recording_genres, release_genres)


def test_genre_priority_recording_then_release_never_artist():
    rec = next(t for t in _dna(["house"], ["techno"]).traits if t.key == "genre")
    assert (rec.scope, rec.values, rec.sources[0].license) == ("track", ["House"], "CC BY-NC-SA")
    rel = next(t for t in _dna([], ["techno"]).traits if t.key == "genre")
    assert (rel.scope, rel.values) == ("release", ["Techno"]) and "release-group/rg1" in rel.sources[0].url
    none = next(t for t in _dna([], [], artist_styles=["Minimal"]).traits if t.key == "genre")
    assert none.status == "unavailable"  # el estilo del artista no se convierte en género de la canción


def test_samples_mashups_and_covers_only_when_documented():
    other = {"id": "o1", "title": "Original Song", "artist-credit": credit("Someone", "a2")}
    raw = {"title": "Lovelee Dae", "relations": [
        {"target-type": "recording", "type": "samples material", "direction": "forward", "recording": other},
        {"target-type": "recording", "type": "samples material", "direction": "backward",
         "recording": {"id": "s2", "title": "Sampler", "artist-credit": credit("DJ X", "a3")}},
        {"target-type": "recording", "type": "mashes up", "direction": "backward",
         "recording": {"id": "m1", "title": "Mash", "artist-credit": credit("DJ Y", "a4")}},
        {"target-type": "work", "type": "performance", "attributes": ["cover"],
         "work": {"title": "Old Tune", "relations": [{"target-type": "artist", "type": "writer", "artist": {"id": "w", "name": "Ana"}}]}},
    ]}
    rel = tracks.relations(raw, [])
    assert [x.title for x in rel.samples] == ["Original Song"] and [x.title for x in rel.sampled_by] == ["Sampler"]
    assert [x.title for x in rel.mashups] == ["Mash"]
    assert (rel.cover_of, rel.cover_writers) == ("Old Tune", ["Ana"])
    plain = tracks.relations({"relations": [{"target-type": "work", "type": "performance", "attributes": [], "work": {"title": "Old Tune"}}]}, [])
    assert plain.cover_of is None  # interpretar una obra no es ser un cover


def _search(query, recordings):
    data = {"recordings": [{"id": f"r{i}", "title": t, "artist-credit": credit(a, f"a{i}"), "score": 100}
                           for i, (t, a) in enumerate(recordings)]}
    return [f"{r.title} | {r.artist_name}" for r in tracks.search_results(data, query, 10, False)[0]]


def test_search_never_returns_vague_matches_for_artist_plus_title():
    # Caso real del piloto: MusicBrainz no tiene «Playground» de Arapu; antes salía «Ivory Playground».
    vague = [("Ivory Playground", "Ivory Playground"), ("Who Are You (Arapu Remix)", "YokoO & Arapu")]
    assert _search("Arapu Playground", vague) == []
    assert _search("Playground - Arapu", vague) == []
    good = vague + [("Playground", "Arapu")]
    assert _search("Arapu Playground", good) == ["Playground | Arapu"]
    # Orden invertido, erratas de una letra y palabras de versión no impiden encontrarla.
    assert _search("Playgrund Arapu", good) == ["Playground | Arapu"]
    assert _search("Lovelee Dae Blaze extended", [("Lovelee Dae", "Blaze")]) == ["Lovelee Dae | Blaze"]
    # Un remix no se fusiona con el original.
    assert _search("Blaze Lovelee Dae", [("Lovelee Dae", "Blaze"), ("Lovelee Dae (radio edit)", "Blaze")]) \
        == ["Lovelee Dae | Blaze", "Lovelee Dae (radio edit) | Blaze"]


def test_typo_tolerance_is_narrow():
    assert tracks._near("playground", "playgrund") and tracks._near("stussy", "stassy")
    assert not tracks._near("arapu", "arupa") and not tracks._near("dae", "day")  # palabras cortas: exactas
    fuzzy = tracks.fuzzy_query("Playground - Arapu").lower()
    assert "playground~1" in fuzzy and "arapu~1" in fuzzy


def test_v63_broad_recording_genre_yields_to_a_concrete_release_and_mixed_eps_give_release_styles():
    g = next(t for t in _dna(["electronic"], ["detroit techno"]).traits if t.key == "genre")
    assert (g.scope, g.values) == ("release", ["Techno", "Detroit Techno"]), "«Electrónica» cede ante el subgénero"
    broad = _dna(["electronic"], ["electronic"])
    assert next(t for t in broad.traits if t.key == "genre").values == ["Electrónica"]
    mixed = _dna([], ["techno", "house", "tech house"])  # EP (primary_type distinto de Single) con varias familias
    by = {t.key: t for t in mixed.traits}
    assert by["genre"].values == ["Electrónica"] or by["genre"].status == "unavailable"
    assert by["release_styles"].values == ["Techno", "House", "Tech House"]
