"""Discogs CC0 local: importador en streaming (sin nombre real, contactos, enlaces ni imágenes), lector del índice,
identidad por ID enlazado y nombre, normalización, hechos en el expediente, evidencia de fundación y umbral de texto.
Volcados diminutos escritos a mano (no son datos de producción); sin red."""

import gzip
import sqlite3

from app import biography, discogs, discogs_dump, facts, sources
from app.api import _discogs_docs
from app.sources import SourceDoc

DATE = "20990101"
ARTISTS = """<artists>
<artist><images><image type="primary" uri="https://i.discogs.com/x.jpg"/></images><id>42</id>
<name>Seed Artist (2)</name><realname>Private Person</realname>
<profile>[b]Dutch[/b] DJ based in Amsterdam. Founder of [l=Deep Records (3)] in 2017. Runs the label [l7]. Signed to [r99].</profile>
<urls><url>https://example.com</url></urls><namevariations><name>Seed</name></namevariations>
<members><name id="5">Member One</name><name id="6">Member Two (4)</name></members>
<groups><name id="8">Side Group</name></groups></artist>
<artist><id>43</id><name>Nameless Extra</name><realname>Someone</realname></artist>
</artists>"""
LABELS = """<labels>
<label><id>7</id><name>Night Label (2)</name><contactinfo>Phone +1 555 0100</contactinfo><profile>x</profile>
<parentLabel id="9">Parent</parentLabel></label>
</labels>"""


def built_index(tmp_path):
    for name, xml in (("artists", ARTISTS), ("labels", LABELS)):
        with gzip.open(tmp_path / f"discogs_{DATE}_{name}.xml.gz", "wt", encoding="utf-8") as fh:
            fh.write(xml)
    path = tmp_path / "discogs.sqlite3"
    discogs_dump.build(DATE, tmp_path, path)
    return path


def test_normalizes_presentation_markup_without_rewriting():
    text = ("[b]Founder[/b] of [l=Hellbent Records (2)], see [url=https://x.y]his page[/url]. Runs [l99]. "
            "Signed to [l123].")
    resolved = discogs.normalize_profile(text, lambda kind, ref: "Atipic" if (kind, ref) == ("l", "99") else None)
    # La referencia sin resolver hace descartar su frase entera, en lugar de dejarla sin el nombre.
    assert resolved == "Founder of Hellbent Records, see his page. Runs Atipic."


def test_import_keeps_only_profile_fields_never_personal_data_or_images(tmp_path):
    path = built_index(tmp_path)
    conn = sqlite3.connect(path)
    columns = {t: [c[1] for c in conn.execute(f"PRAGMA table_info({t})")] for t in ("artist", "label")}
    assert columns == {"artist": ["id", "name", "variations", "profile", "members", "groups", "sites"],
                       "label": ["id", "name", "parent_id", "profile"]}  # sin realname, contactinfo ni imágenes
    dump = b"".join(bytes(str(row), "utf-8") for t in ("artist", "label") for row in conn.execute(f"SELECT * FROM {t}"))
    assert b"Private Person" not in dump and b"555" not in dump and b"i.discogs.com" not in dump
    # Un artista sin perfil ni relaciones solo conserva el nombre (para resolver referencias de otros perfiles).
    assert conn.execute("SELECT name, variations, profile FROM artist WHERE id = 43").fetchone() == ("Nameless Extra",
                                                                                                     None, None)
    meta = dict(conn.execute("SELECT key, value FROM meta"))
    assert meta["license"] == "CC0" and meta["dump_date"] == DATE and '"artist": 2' in meta["counts"]


def test_profile_docs_come_from_the_linked_id_with_identity_check_and_local_references(tmp_path):
    index = discogs.DiscogsIndex(built_index(tmp_path))
    docs = discogs.artist_docs(index, "42", "Seed Artist")
    assert [(d.label, d.license, d.url) for d in docs] == [
        ("Discogs (perfil)", "CC0", "https://www.discogs.com/artist/42"),
        ("Discogs (relaciones)", "CC0", "https://www.discogs.com/artist/42")]
    # [l7] se resuelve con el índice; [r99] (lanzamiento) no se indexa: su frase se descarta.
    assert docs[0].text == "Dutch DJ based in Amsterdam. Founder of Deep Records in 2017. Runs the label Night Label."
    assert docs[1].text == "Integrantes: Member One, Member Two. Miembro de: Side Group."
    assert discogs.artist_docs(index, "42", "Seed")[0].text == docs[0].text  # variante del nombre
    assert discogs.artist_docs(index, "42", "Another Artist") == []  # el enlace apunta a otro artista: no se usa
    # MusicBrainz ya tiene los grupos: Discogs no los repite.
    assert discogs.artist_docs(index, "42", "Seed Artist", with_groups=False)[1].text == (
        "Integrantes: Member One, Member Two.")


def test_without_index_the_pipeline_continues_with_the_other_sources(tmp_path):
    assert not discogs.DiscogsIndex(tmp_path / "missing.sqlite3").available
    linked = {"relations": [{"type": "discogs", "url": {"resource": "https://www.discogs.com/artist/42"}}]}
    assert _discogs_docs(linked, "Seed Artist", [], []) == []  # conftest: DISCOGS_DB_PATH sin índice


def test_discogs_notes_feed_the_dossier_keeping_found_run_and_owner_apart():
    notes = SourceDoc("", "Discogs (perfil)", "https://www.discogs.com/artist/1", "CC0",
                      "French DJ and producer based in Paris. Owner of record label Night Label. "
                      "DJ and producer from the UK, founder of Hellbent Records.")
    found = {f.text: f for f in facts.extract([notes], "Seed Artist")}
    assert found["Owner of record label Night Label."].kind == "sello que dirige"  # ser dueño no es fundar
    assert found["DJ and producer from the UK, founder of Hellbent Records."].kind == "sello propio"
    assert facts.descriptive_count(list(found.values())) == 3
    # Ante el mismo hecho, la frase de Wikipedia (con fecha y contexto) va antes que la nota de Discogs.
    wiki = SourceDoc("", "Wikipedia (es): Seed Artist", "https://wp", "CC BY-SA 4.0",
                     "Seed Artist es un DJ francés. En 2014 Seed Artist fundó su propio sello, Night Label, en París.")
    chosen = facts.select(facts.extract([wiki, notes], "Seed Artist"), limit=2)
    assert [f.source.label for f in chosen] == ["Wikipedia (es): Seed Artist", "Wikipedia (es): Seed Artist"]


def test_discogs_supports_founding_claims_only_and_does_not_lower_the_text_threshold():
    notes = [SourceDoc("S1", "Discogs (perfil)", "https://www.discogs.com/artist/1", "CC0",
                       "DJ & Producer duo from Amsterdam, Netherlands. They founded their own label NO ART in 2017.")]
    assert biography.claim_issue("ANOTR fundaron el sello NO ART en 2017.", "ANOTR", notes) is None
    assert "residencia" in biography.claim_issue("ANOTR son residentes en Amnesia.", "ANOTR", notes)
    assert "sello o proyecto fundado" in biography.claim_issue("ANOTR fundaron el sello Other Label.", "ANOTR", notes)
    # Las notas cuentan como texto descriptivo, pero una sola frase breve no basta para llamar al modelo.
    assert sources.descriptive_chars(notes) == len(notes[0].text) < sources.DESCRIPTIVE_MIN_CHARS == 150
    assert not sources.sufficient(notes)


def test_label_profiles_only_for_labels_the_artist_profile_links_and_own_sites(tmp_path):
    index = discogs.DiscogsIndex(built_index(tmp_path))
    docs = discogs.linked_label_docs(index, "42", "Seed Artist")  # el perfil enlaza [l7]
    assert [(d.label, d.url, d.text) for d in docs] == [("Discogs (sello): Night Label", "https://www.discogs.com/label/7", "Night Label: x")]
    assert discogs.linked_label_docs(index, "42", "Another Artist") == []  # identidad no confirmada
    assert discogs.own_sites(index, "42", "Seed Artist") == ["https://example.com"]  # web propia, no redes
