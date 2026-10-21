"""BPM y tonalidad de AcousticBrainz: solo con acuerdo entre envíos y audio de la misma duración; caché propia."""

import urllib.error

from app import acousticbrainz as ab
from app import schemas, store

MBID = "11111111-1111-4111-8111-111111111111"


def sub(bpm, key="A", scale="minor", strength=0.75, length=240.0):
    return {"rhythm": {"bpm": bpm}, "tonal": {"key_key": key, "key_scale": scale, "key_strength": strength},
            "metadata": {"audio_properties": {"length": length}}}


def test_key_names_in_spanish_and_camelot():
    assert ab.key_label("A", "minor") == ("La menor", "8A")
    assert ab.key_label("G#", "minor") == ("Sol# menor", "1A")
    assert ab.key_label("Ab", "major") == ("Lab mayor", "4B")
    assert ab.key_label("C", "major") == ("Do mayor", "8B")
    assert ab.key_label("H", "minor") is None


def test_only_agreeing_submissions_of_the_same_audio_are_published():
    assert ab.summarize([sub(123.97)], 240000) == {"bpm": 124, "key": "La menor", "camelot": "8A"}
    # Tonalidad distinta entre envíos (caso real): el BPM coincide, la tonalidad no se publica.
    assert ab.summarize([sub(128.35), sub(128.46, key="F", strength=0.53)], 240000) == {"bpm": 128}
    assert ab.summarize([sub(124, strength=0.4)], 240000) == {"bpm": 124}  # tonalidad poco clara
    assert ab.summarize([sub(124), sub(140)], 240000) == {}  # tempos distintos: no es el mismo audio, nada
    assert ab.summarize([sub(124, length=420.0)], 240000) == {}  # otro edit (otra duración) con el mismo MBID
    assert ab.summarize([], 240000) == {}


def test_lookup_caches_answers_but_not_failures():
    calls = []

    def ok(url):
        calls.append(url)
        return {MBID: {"0": sub(124)}}

    assert ab.lookup(MBID, 240000, ok) == {"bpm": 124, "key": "La menor", "camelot": "8A"}
    assert ab.lookup(MBID, 240000, ok) == {"bpm": 124, "key": "La menor", "camelot": "8A"} and len(calls) == 1
    other = "22222222-2222-4222-8222-222222222222"

    def down(url):
        raise urllib.error.URLError("sin red")

    assert ab.lookup(other, None, down) == {}
    assert store.get(ab.KIND, other) is None  # se reintentará


def test_measurements_replace_only_unavailable_acoustic_traits():
    dna = schemas.TrackDna(recording_mbid=MBID, traits=[
        schemas.DnaTrait(key="bpm", group="acoustic", label="BPM", status="unavailable"),
        schemas.DnaTrait(key="key", group="acoustic", label="Tonalidad", status="unavailable"),
        schemas.DnaTrait(key="energy", group="acoustic", label="Energía", status="unavailable")])
    out = ab.with_measurements(dna, {"bpm": 124})
    assert [(t.key, t.status, t.values) for t in out.traits] == [
        ("bpm", "measured", ["124"]), ("key", "unavailable", []), ("energy", "unavailable", [])]
    assert out.traits[0].sources[0].license == "CC0"
    assert ab.with_measurements(dna, {}) is dna
