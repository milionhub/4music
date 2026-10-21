"""ReccoBeats (V5.5): tempo estimado solo para la grabación exacta (ISRC + duración), nunca tonalidad, con caché."""

import urllib.error

from app import acousticbrainz, api, reccobeats as rb
from app import schemas, store

DESIRE = "9d619150-6b0f-4f14-b038-8503ae4c6c8f"
ISRC = "QM4TW2437510"
LENGTH = 171953  # MusicBrainz: Desire (single digital de 2024)


def pista(id_="t1", isrc=ISRC, duration=171953):
    return {"id": id_, "isrc": isrc, "durationMs": duration, "trackTitle": "Desire"}


def rasgo(id_="t1", tempo=133.971, key=6, mode=0):
    return {"id": id_, "tempo": tempo, "key": key, "mode": mode}


def test_solo_la_grabacion_exacta_por_isrc_y_duracion():
    assert rb.summarize([pista()], [rasgo()], [ISRC], LENGTH) == {"bpm": 134}
    assert rb.summarize([pista(isrc="OTRO0000001")], [rasgo()], [ISRC], LENGTH) == {}, "ISRC de otra grabación"
    # Otra versión con el mismo ISRC mal asignado (p. ej. la edición de 6:14 frente al single de 2:52): fuera.
    assert rb.summarize([pista(duration=374000)], [rasgo()], [ISRC], LENGTH) == {}
    assert rb.summarize([pista(duration=LENGTH + 4000)], [rasgo()], [ISRC], LENGTH) == {"bpm": 134}, "±3 %"
    assert rb.summarize([pista()], [rasgo()], [ISRC], None) == {}, "sin duración no hay identificación"


def test_tempos_dudosos_no_se_publican():
    # Error de octava (Nabi: 196 frente a 98 de AcousticBrainz): se descarta, no se divide entre dos.
    assert rb.summarize([pista()], [rasgo(tempo=196.0)], [ISRC], LENGTH) == {}
    # Dos ediciones del mismo ISRC que no concuerdan: nada.
    assert rb.summarize([pista("a"), pista("b")], [rasgo("a", 124.0), rasgo("b", 131.0)], [ISRC], LENGTH) == {}
    assert rb.summarize([pista("a"), pista("b")], [rasgo("a", 122.99), rasgo("b", 122.993)], [ISRC], LENGTH) == {"bpm": 123}


def test_la_tonalidad_nunca_se_publica():
    assert "key" not in rb.summarize([pista()], [rasgo()], [ISRC], LENGTH)


def test_cache_de_respuestas_pero_no_de_fallos():
    calls = []

    def ok(url):
        calls.append(url)
        return {"content": [pista()]} if "/track?" in url else {"content": [rasgo()]}

    assert rb.lookup(DESIRE, [ISRC], LENGTH, transport=ok) == {"bpm": 134}
    assert rb.lookup(DESIRE, [ISRC], LENGTH, transport=lambda url: (_ for _ in ()).throw(AssertionError)) == {"bpm": 134}
    assert len(calls) == 2 and f"ids={ISRC}" in calls[0]

    def down(url):
        raise urllib.error.URLError("sin red")

    other = "11111111-1111-4111-8111-111111111111"
    assert rb.lookup(other, [ISRC], LENGTH, transport=down) == {}
    assert store.get(rb.KIND, other) is None, "un fallo temporal no se guarda"
    # Pista desconocida: una sola petición y la respuesta vacía sí se guarda.
    empty = []
    assert rb.lookup(other, [ISRC], LENGTH, transport=lambda url: empty.append(url) or {"content": []}) == {}
    assert len(empty) == 1 and store.get(rb.KIND, other) == {"version": rb.VERSION, "values": {}}
    assert rb.lookup(other, [], LENGTH, transport=down) == {}, "sin ISRC no se consulta"


def _dna():
    return schemas.TrackDna(recording_mbid=DESIRE, traits=[
        schemas.DnaTrait(key=k, group="acoustic", label=k, status="unavailable") for k in ("bpm", "key", "energy")])


def test_acousticbrainz_manda_y_reccobeats_solo_completa_el_tempo(monkeypatch):
    dna = rb.with_tempo(_dna(), {"bpm": 134})
    bpm = next(t for t in dna.traits if t.key == "bpm")
    assert (bpm.status, bpm.values, bpm.sources[0].label) == ("measured", ["134"], "ReccoBeats")
    assert next(t for t in dna.traits if t.key == "key").status == "unavailable"
    measured = acousticbrainz.with_measurements(_dna(), {"bpm": 123, "key": "Sol# menor", "camelot": "1A"})
    assert rb.with_tempo(measured, {"bpm": 999}) == measured, "nunca sustituye un tempo ya medido"

    # En la API: con tempo de AcousticBrainz no se consulta ReccoBeats.
    track = schemas.TrackResponse.model_construct(mbid=DESIRE, isrcs=[ISRC], length_ms=LENGTH, dna=_dna())
    asked = []
    monkeypatch.setattr(rb, "lookup", lambda *a, **k: asked.append(a) or {"bpm": 134})
    monkeypatch.setattr(acousticbrainz, "lookup", lambda mbid, length: {"bpm": 123})
    assert next(t for t in api._measured_dna(track).traits if t.key == "bpm").values == ["123"] and not asked
    monkeypatch.setattr(acousticbrainz, "lookup", lambda mbid, length: {})
    out = next(t for t in api._measured_dna(track).traits if t.key == "bpm")
    assert out.values == ["134"] and out.sources[0].label == "ReccoBeats" and len(asked) == 1
