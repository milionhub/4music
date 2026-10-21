"""Regresión (sesión 2, capa 1): borrador real de Marco Carola rechazado por el validador v5 con cuatro falsos
positivos (frase partida en «Do.Mi.No.», nacimiento en la convención «Nombre (Lugar, fecha)», «ganó el apoyo» como
premio y 176 palabras). Hechos y borrador copiados de SQLite (tests/fixtures/carola_bio_v8_rejected.json)."""

import json
from pathlib import Path

from app import biography
from app.sources import SourceDoc

CASE = json.loads((Path(__file__).parent / "fixtures" / "carola_bio_v8_rejected.json").read_text(encoding="utf-8"))
NAME = CASE["artist"]
DOCS = [SourceDoc(f["id"], f["source"], f["url"], f["license"], f["text"]) for f in CASE["facts"]]
DRAFT = biography.paragraphs(CASE["draft"])


def validate(paras):
    return biography.validate(paras, NAME, DOCS)


COPIED = ("descrito como un cruce de caminos entre el Dynamic Syncopation de Surgeon, el Cavernous Walls de Lost y el "
          "I‑Fidelity de Blueprint")


def test_real_carola_draft_only_fails_for_its_literal_copy():
    assert CASE["error_code"] == "afirmación sin respaldo (sello o proyecto fundado: Music)"  # el rechazo original
    assert len(CASE["facts"]) == 9 and COPIED in DRAFT[0]
    # Los falsos positivos desaparecen; queda un rechazo legítimo: copia 19 palabras seguidas de H2 (Wikipedia).
    assert validate(DRAFT) == "copia literal de una fuente"
    assert validate([DRAFT[0].replace(COPIED, "comparado con el de Surgeon, Lost y Blueprint"), DRAFT[1]]) is None


def test_sentences_are_not_split_inside_abbreviations():
    h5 = next(d.text for d in DOCS if d.id == "H5")
    assert len(biography.SENTENCE_RE.split(h5)) == 1  # «Do.Mi.No. and Music On…» es la misma frase
    assert biography.SENTENCE_RE.split("Fue DJ. En 1996 fundó Design. «Man Train» salió; luego vino Zenit.\nFin") == [
        "Fue DJ.", "En 1996 fundó Design.", "«Man Train» salió;", "luego vino Zenit.", "Fin"]


def test_birth_needs_explicit_evidence():
    assert "nacimiento" not in (validate(DRAFT) or "")  # «(Nápoles el 7 de febrero de 1975)» es su nacimiento
    # Fráncfort es su ciudad de residencia en las fuentes, no la natal.
    frankfurt = [SourceDoc("X", "Wikipedia (es): Marco Carola", "https://wp", "CC BY-SA 4.0",
                           "Actualmente tiene su residencia en la ciudad alemana de Frankfurt.")]
    assert "nacimiento" in biography.claim_issue("Carola nació en Frankfurt.", NAME, DOCS + frankfurt)
    # Ciudad asociada fuera del paréntesis, o mencionada tras la cláusula de nacimiento: no es la natal.
    for source, city in (("Marco Carola (7 de febrero de 1975) es un DJ de Nápoles.", "Nápoles"),
                         ("Carola was born in 1975, and he later moved to Berlin.", "Berlín"),
                         ("Carola (born 1975) is a DJ based in Berlin.", "Berlín")):
        doc = [SourceDoc("X", "Wikipedia (en): Marco Carola", "https://wp", "CC BY-SA 4.0", source)]
        assert "nacimiento" in (biography.claim_issue(f"Carola nació en {city}.", NAME, doc) or ""), source
    explicit = [SourceDoc("X", "Wikipedia (en): Marco Carola", "https://wp", "CC BY-SA 4.0",
                          "Marco Carola (born February 7 of 1975, Naples, Italy) is an Italian DJ.")]
    assert biography.claim_issue("Carola nació en Nápoles.", NAME, explicit) is None


def test_won_support_is_not_an_award_but_invented_awards_are_rejected():
    assert biography.claim_issue("Su sonido le ganó el apoyo de DJs de todo el mundo.", NAME, DOCS) is None
    for text in ("En 2011 ganó el premio DJ Awards.", "Ganó dos Grammy.", "Fue galardonado en 2011."):
        assert "premio o reconocimiento" in (biography.claim_issue(text, NAME, DOCS) or ""), text


def test_false_labels_and_residencies_are_still_rejected():
    first, second = DRAFT
    # Minus publica su música (H9), no es un sello fundado por él.
    assert "sello o proyecto fundado: Minus" in validate([first, second.replace("Do.Mi.No. y Music On",
                                                                                "Do.Mi.No., Music On y Minus")])
    assert "residencia en club o fiesta" in validate([first, second.replace("Amnesia Ibiza y Cocoon",
                                                                            "Amnesia Ibiza y Fabric")])


def test_length_has_a_reasonable_margin_but_a_ceiling():
    assert biography.MAX_WORDS == 190
    padding = " Siguió publicando y actuando durante muchos años en distintas ciudades."
    assert "longitud" in (validate([DRAFT[0], DRAFT[1] + padding * 3]) or "")  # 176 + 30 > 190
