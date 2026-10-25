"""Biografías con Groq (T1.4) sin red: transporte falso de Groq, fuentes de prueba escritas a mano."""

import json
import threading
import time

from fastapi.testclient import TestClient

from app import api, biography, facts, sources, store
from app.api import get_groq_client
from app.groq_client import GroqClient
from app.main import app
from tests.fixtures import mb
from tests.test_api import ROUTES, make_client

WIKI_KEY = "wp:Seed Artist"
WIKI_TEXT = ("Seed Artist is a Belgian DJ and producer known for tech house and long club sets. The artist grew up "
             "in Antwerp and started playing records in local clubs before releasing on Scene Records. Seed Artist's "
             "sound mixes rolling basslines, percussive grooves and vocal samples, and is often described as warm and "
             "hypnotic. Old EP became an underground favourite and led to tours across Europe and residencies in Ibiza, "
             "where the artist became known for extended sets.")
WIKI = {"query": {"pages": {"1": {"title": "Seed Artist", "extract": WIKI_TEXT}}}}
GOOD_TEXT = ("Seed Artist es un DJ y productor belga que ha hecho del tech house su territorio, con sesiones largas "
             "pensadas para la pista y un pulso constante de club. Su música combina groove y energía, y en su "
             "recorrido destacan lanzamientos como «Old EP», que le abrió las puertas de los clubes de fuera. "
             "Sus giras por Europa y sus noches en Ibiza han afianzado un estilo de club directo y con "
             "personalidad.")


class FakeGroq:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = 0
        self.bodies = []

    def __call__(self, url, headers, body, timeout):
        self.calls += 1
        self.bodies.append(json.loads(body))
        assert headers["Authorization"] == "Bearer test-key" and url.endswith("/chat/completions")
        status, payload = self.responses.pop(0) if self.responses else (200, {"paragraphs": [GOOD_TEXT], "fact_ids": ["H1"]})
        if status != 200:
            return status, b"", None
        return 200, json.dumps({"choices": [{"finish_reason": "stop", "message": {"content": json.dumps(payload)}}]}).encode(), None


def client_with(groq_responses, routes=None):
    routes = {**ROUTES, WIKI_KEY: (200, WIKI), **(routes or {})}
    client, transport = make_client(routes)
    fake = FakeGroq(groq_responses)
    groq = GroqClient("test-key", "test-model", transport=fake, sleep=lambda s: None)
    app.dependency_overrides[get_groq_client] = lambda: groq
    return client, fake


def test_generates_validates_stores_and_reuses():
    client, fake = client_with([(200, {"paragraphs": [GOOD_TEXT], "fact_ids": ["H1", "H4", "H99"]})])
    r = client.get(f"/v1/artists/{mb.SEED}/biography")
    assert r.status_code == 200
    # H99 no existe: la salida se rechaza (no se aceptan fuentes inventadas) y se usa la alternativa verificada.
    assert r.json()["bio"] == {**r.json()["bio"], "kind": "factual", "text": "Disc-jockey de tech house."}
    assert store.get(biography.KIND, mb.SEED)["status"] == "rejected"
    assert store.get(biography.KIND, mb.SEED)["error_code"] == "unknown_source"

    client, fake = client_with([(200, {"paragraphs": [GOOD_TEXT], "fact_ids": ["H1", "H3"]})])
    assert biography.invalidate(mb.SEED)  # regeneración selectiva de ese MBID
    body = client.get(f"/v1/artists/{mb.SEED}/biography").json()
    assert body["status"] == "ready" and body["bio"]["kind"] == "generated" and body["bio"]["text"] == GOOD_TEXT
    urls = [s["url"] for s in body["bio"]["sources"]]  # las fuentes de los hechos citados (H1 y H3)
    assert urls == ["https://en.wikipedia.org/wiki/Seed_Artist", f"https://www.wikidata.org/wiki/{mb.QID}"]
    assert "model" not in json.dumps(body) and "test-key" not in json.dumps(body)  # nada técnico ni secreto
    # El prompt solo lleva hechos seleccionados, con su tipo y su fuente; nunca la lista de lanzamientos recientes.
    prompt = fake.bodies[0]["messages"][1]["content"]
    assert "[H1] (identidad; frase de la fuente; fuente: Wikipedia (en): Seed Artist) Seed Artist is a Belgian DJ" in prompt
    assert "(proyecto paralelo; relación estructurada; fuente: MusicBrainz) Miembro de: The Band." in prompt
    assert prompt.count("(origen;") == 1  # un solo dato de origen
    assert "lanzamientos recientes" not in prompt and "«New EP»" not in prompt and "solista" in prompt
    assert len(prompt) < 2500
    # Segunda visita (y el perfil): desde la caché persistente, sin llamar a Groq.
    client.get(f"/v1/artists/{mb.SEED}/biography")
    profile = client.get(f"/v1/artists/{mb.SEED}").json()
    assert fake.calls == 1 and profile["bio"]["kind"] == "generated" and profile["bio_pending"] is False


def test_rejects_banned_phrases_lists_invented_years_and_titles():
    docs = [sources.SourceDoc("S1", "MusicBrainz", "https://mb", "CC0", "Seed Artist publicó «Old EP» en 2018, 2019 y 2020. Colaboradores habituales: Co A."),
            sources.SourceDoc("S2", "Wikipedia (en): Seed Artist", "https://wp", "CC BY-SA 4.0", WIKI_TEXT)]
    ok = GOOD_TEXT.replace("como «Old EP»", "como «Old EP» en 2018")
    assert biography.validate(ok, "Seed Artist", docs) is None
    assert "fuentes" in biography.validate(ok + " MusicBrainz documenta 12 lanzamientos.", "Seed Artist", docs)
    assert "fuentes" in biography.validate(ok.replace("Sus giras", "Publica desde 2018. Sus giras"), "Seed Artist", docs)
    assert "año" in biography.validate(ok.replace("2018", "2015"), "Seed Artist", docs)
    # El contenido se comprueba antes que la forma: dos títulos, uno inventado → rechazo de contenido.
    assert "sin respaldo" in biography.validate(ok.replace("«Old EP»", "«Old EP» y «Inventado»"), "Seed Artist", docs)
    assert "título" in biography.validate(ok.replace("«Old EP»", "«Inventado»"), "Seed Artist", docs)
    assert "enumera títulos" in biography.validate(ok.replace("«Old EP»", "«Old EP», «Old EP» y «Old EP»"), "Seed Artist", docs)
    assert "enumera años" in biography.validate(ok.replace("en 2018", "en 2018, 2019 y 2020"), "Seed Artist", docs)
    assert "longitud" in biography.validate("Seed Artist es un DJ.", "Seed Artist", docs)


def test_insufficient_sources_never_call_groq():
    client, fake = client_with([], routes={f"wd:{mb.QID}": (503, None), WIKI_KEY: (404, None)})
    body = client.get(f"/v1/artists/{mb.SEED_EMPTY}/biography").json()
    assert fake.calls == 0 and body["status"] == "unavailable" and body["bio"] is None  # estado vacío discreto
    assert store.get(biography.KIND, mb.SEED_EMPTY)["status"] == "insufficient_sources"
    # Discografía + metadatos de Wikidata sin texto descriptivo: tampoco se llama a Groq (solo identidad).
    client, fake = client_with([], routes={WIKI_KEY: (404, None)})
    body = client.get(f"/v1/artists/{mb.SEED}/biography").json()
    assert fake.calls == 0 and body["bio"]["text"] == "Disc-jockey de tech house."


def test_groq_errors_do_not_break_the_profile_and_are_not_retried_in_a_loop():
    client, fake = client_with([(429, None), (429, None)])
    r = client.get(f"/v1/artists/{mb.SEED}/biography")
    assert r.status_code == 200 and r.json()["bio"]["text"] == "Disc-jockey de tech house."  # nunca discografía
    assert fake.calls == 2  # una petición + un único reintento
    saved = store.get(biography.KIND, mb.SEED)
    assert saved["status"] == "error" and saved["error_code"] == "rate_limited"
    client.get(f"/v1/artists/{mb.SEED}/biography")
    assert fake.calls == 2  # el error queda en caché: no se reintenta en cada visita
    profile = client.get(f"/v1/artists/{mb.SEED}").json()
    assert profile["bio_pending"] is False  # pausa global tras el 429: la app no vuelve a pedirla
    # Otro artista durante la pausa: no se llama a Groq (no se gasta cuota) ni se guarda el fallo.
    rec = biography.generate(mb.CO_A, "Co A", lambda: [sources.SourceDoc("S1", "Wikipedia (en): Co A", "https://x", None, WIKI_TEXT)],
                             GroqClient("test-key", "m", transport=fake, sleep=lambda s: None))
    assert rec.error_code == "cooldown" and fake.calls == 2 and store.get(biography.KIND, mb.CO_A) is None


def test_concurrent_requests_generate_once():
    slow = threading.Event()

    class SlowFake(FakeGroq):
        def __call__(self, *a):
            slow.wait(0.3)
            return super().__call__(*a)

    client, _ = client_with([])
    fake = SlowFake([(200, {"paragraphs": [GOOD_TEXT], "fact_ids": ["H1"]})])
    groq = GroqClient("test-key", "test-model", transport=fake, sleep=lambda s: None)
    app.dependency_overrides[get_groq_client] = lambda: groq
    results = []
    threads = [threading.Thread(target=lambda: results.append(client.get(f"/v1/artists/{mb.SEED}/biography").json()))
               for _ in range(3)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert fake.calls == 1 and all(r["bio"]["kind"] == "generated" for r in results)


def test_profile_marks_bio_pending_only_when_groq_is_configured():
    client, _ = make_client()  # sin Groq configurado en make_client
    body = client.get(f"/v1/artists/{mb.SEED}").json()
    assert body["bio_pending"] is False and body["bio"]["kind"] == "factual"
    client, _ = client_with([])
    assert client.get(f"/v1/artists/{mb.SEED}").json()["bio_pending"] is True


def test_image_result_is_persisted_and_reused_without_musicbrainz():
    client, transport = make_client()
    first = client.get(f"/v1/artists/{mb.SEED}/image").json()
    calls = len(transport.urls)
    second = client.get(f"/v1/artists/{mb.SEED}/image").json()
    assert first == second and first["image"] is not None and len(transport.urls) == calls  # caché persistente


def test_previous_valid_biography_is_kept_while_the_new_format_is_not_valid():
    old_ok = biography.BiographyRecord(artist_mbid=mb.SEED, biography=GOOD_TEXT, source_urls=["https://wp"],
                                       source_labels=["Wikipedia"], generated_at="2026", model="m", status="ok",
                                       prompt_version=5)
    store.put(biography.KIND, mb.SEED, old_ok.model_dump(), 3600)
    assert biography.cached(mb.SEED) is None  # el formato cambió: se regenera una vez
    client, fake = client_with([(200, {"paragraphs": [GOOD_TEXT.replace("«Old EP»", "«Inventado»")],
                                       "fact_ids": ["H1"]})] * 2)
    body = client.get(f"/v1/artists/{mb.SEED}/biography").json()
    # La nueva no es válida (contenido): se sigue mostrando la anterior, y no se regenera en cada visita.
    # Petición + un único intento de reparación.
    assert fake.calls == 2 and body["bio"]["kind"] == "generated" and body["bio"]["text"] == GOOD_TEXT
    saved = store.get(biography.KIND, mb.SEED)
    assert saved["status"] == "rejected" and saved["previous"]["biography"] == GOOD_TEXT
    profile = client.get(f"/v1/artists/{mb.SEED}").json()
    assert profile["bio"]["text"] == GOOD_TEXT and profile["bio_pending"] is False and fake.calls == 2
    # Una antigua con lista de títulos/años no se conserva.
    listy = old_ok.model_copy(update={"biography": GOOD_TEXT.replace("«Old EP»", "«A» (2019), «B» (2020) y «C» (2021)")})
    assert biography._previous_of(listy) is None


def test_admin_invalidates_only_one_artist(capsys):
    from app import admin
    store.put(biography.KIND, mb.SEED, {"x": 1}, 3600)
    store.put(biography.KIND, mb.CO_A, {"x": 1}, 3600)
    assert admin.main(["invalidate-bio", mb.SEED]) == 0
    assert store.get(biography.KIND, mb.SEED) is None and store.get(biography.KIND, mb.CO_A) == {"x": 1}
    assert admin.main(["invalidate-bio", "no-es-un-mbid"]) == 2


def test_redirected_mbid_resolves_and_shares_photo():
    old = "99999999-9999-4999-8999-999999999999"  # MBID fusionado: MusicBrainz devuelve el canónico
    client, _ = make_client({**ROUTES, f"artist/{old}": (200, mb.SEED_ARTIST)})
    img = client.get(f"/v1/artists/{old}/image").json()["image"]
    assert img is not None and img["wikidata_id"] == mb.QID  # P434 se comprueba con el MBID canónico
    assert store.get("image", mb.SEED)["image"]["url"] == img["url"]  # misma foto para el MBID canónico


def test_strict_json_failure_retries_once_in_json_object_mode():
    calls = []

    def transport(url, headers, body, timeout):
        calls.append(json.loads(body)["response_format"]["type"])
        if len(calls) == 1:
            return 400, b'{"error":{"message":"Failed to generate JSON. Please adjust your prompt."}}', None
        return 200, json.dumps({"choices": [{"finish_reason": "stop", "message": {"content": json.dumps(
            {"paragraphs": ["x"], "source_ids": ["S1"]})}}]}).encode(), None

    out = GroqClient("test-key", "m", transport=transport, sleep=lambda s: None).structured("s", "u", "n", biography.SCHEMA)
    assert out["source_ids"] == ["S1"] and calls == ["json_schema", "json_object"]


TITLE_LIST = GOOD_TEXT.replace("como «Old EP»", "como «Old EP», «Scene Records» y «Old EP»")  # respaldados, pero en lista


def _expires_in(mbid):
    with store._lock:
        conn = store._connect()
        try:
            (expires,) = conn.execute("SELECT expires_at FROM records WHERE kind = ? AND mbid = ?",
                                      (biography.KIND, mbid)).fetchone()
        finally:
            conn.close()
    return expires - time.time()


def test_format_only_rejection_is_retried_once_with_feedback():
    client, fake = client_with([(200, {"paragraphs": [TITLE_LIST], "fact_ids": ["H1"]}),
                                (200, {"paragraphs": [GOOD_TEXT], "fact_ids": ["H1"]})])
    body = client.get(f"/v1/artists/{mb.SEED}/biography").json()
    assert fake.calls == 2 and body["bio"]["kind"] == "generated" and body["bio"]["text"] == GOOD_TEXT
    retry = fake.bodies[1]["messages"][1]["content"]
    assert "se rechazó (enumera títulos de lanzamientos)" in retry and TITLE_LIST in retry
    assert fake.bodies[1]["messages"][0] == fake.bodies[0]["messages"][0]  # mismas reglas, sin relajar nada


def test_format_rejected_twice_retries_next_day_not_on_every_visit():
    client, fake = client_with([(200, {"paragraphs": [TITLE_LIST], "fact_ids": ["H1"]})] * 2)
    body = client.get(f"/v1/artists/{mb.SEED}/biography").json()
    assert fake.calls == 2 and body["bio"]["kind"] == "factual"  # nunca más de una petición y un reintento
    saved = store.get(biography.KIND, mb.SEED)
    assert saved["status"] == "rejected" and saved["error_code"].startswith("enumera títulos")
    assert 0 < _expires_in(mb.SEED) <= biography.TTL_FORMAT_S
    client.get(f"/v1/artists/{mb.SEED}/biography")
    assert fake.calls == 2 and client.get(f"/v1/artists/{mb.SEED}").json()["bio_pending"] is False


def test_content_rejection_gets_one_repair_and_is_never_published():
    invented = GOOD_TEXT.replace("«Old EP»", "«Inventado»")
    client, fake = client_with([(200, {"paragraphs": [invented], "fact_ids": ["H1"]})] * 2)
    body = client.get(f"/v1/artists/{mb.SEED}/biography").json()
    saved = store.get(biography.KIND, mb.SEED)
    assert fake.calls == 2 and saved["status"] == "rejected" and "sin respaldo" in saved["error_code"]
    assert body["bio"]["kind"] == "factual" and "Inventado" not in json.dumps(body)
    assert _expires_in(mb.SEED) > biography.TTL_FORMAT_S  # una semana: no se reintenta en cada visita
    retry = fake.bodies[1]["messages"][1]["content"]
    assert "título entre comillas sin respaldo" in retry and "elimínala" in retry
    # Si la reparación omite lo que no tenía respaldo, se publica.
    biography.invalidate(mb.SEED)
    client, fake = client_with([(200, {"paragraphs": [invented], "fact_ids": ["H1"]}),
                                (200, {"paragraphs": [GOOD_TEXT], "fact_ids": ["H1"]})])
    body = client.get(f"/v1/artists/{mb.SEED}/biography").json()
    assert fake.calls == 2 and body["bio"]["text"] == GOOD_TEXT


def test_rejections_from_previous_prompt_versions_are_retried():
    old = biography.BiographyRecord(artist_mbid=mb.SEED, biography=None, source_urls=[], generated_at="2026",
                                    model=None, status="rejected", error_code="enumera títulos de lanzamientos",
                                    prompt_version=4)
    store.put(biography.KIND, mb.SEED, old.model_dump(), biography.TTL_REJECTED_S)
    assert biography.cached(mb.SEED) is None
    client, _ = client_with([])
    assert client.get(f"/v1/artists/{mb.SEED}").json()["bio_pending"] is True  # la app pedirá una nueva


# --- v6: párrafos y afirmaciones ---------------------------------------------------------------------------------
LONG_WIKI = WIKI_TEXT + (" The artist co-founded the label Night Shift Records in 2015 and has held a residency at the "
                         "club Fuse in Brussels since 2017. Their single Late Bloom reached the Belgian charts. "
                         "In 2020 Seed Artist relocated to Berlin, where the artist now runs a monthly studio "
                         "session for young producers and keeps touring clubs across Europe and South America. Critics have "
                         "praised the patience of the long sets, which build slowly from deep grooves to peak-time "
                         "percussion, and the warmth of the vocal edits that mark most of the catalogue in recent years.")
PARA_1 = ("Seed Artist ha hecho del tech house belga un asunto de sesiones largas y pulso de club, con raíces en Amberes "
          "y en las cabinas locales donde empezó a pinchar. Su sonido mezcla bajos rodantes, percusión y voces "
          "sampleadas, y se ha descrito como cálido e hipnótico.")
PARA_2 = ("Además de publicar en Scene Records, cofundó el sello Night Shift Records y mantiene una residencia en el "
          "club Fuse de Bruselas. Su paso a Berlín en 2020 abrió una etapa nueva, y sus giras por Europa y sus noches en "
          "Ibiza han afianzado un estilo de club directo y con personalidad.")


FLOW_PARA_2 = PARA_2.replace("Su paso a Berlín en 2020 abrió una etapa nueva, y sus giras", "Sus giras")


def _docs(wiki=LONG_WIKI):
    return [sources.SourceDoc("S1", "MusicBrainz", "https://mb", "CC0",
                              "Nombre artístico: Seed Artist. Sellos que han publicado su música (no implica que los "
                              "haya fundado): Scene Records, Label Two. Colaboradores habituales: Co A."),
            sources.SourceDoc("S2", "Wikipedia (en): Seed Artist", "https://wp", "CC BY-SA 4.0", wiki)]


def test_one_or_two_paragraphs_depending_on_descriptive_sources():
    docs = _docs()
    plan = lambda d: biography._plan(facts.select(facts.extract(d, "Seed Artist")))  # noqa: E731
    assert plan(docs) == "full" and biography.validate([PARA_1, PARA_2], "Seed Artist", docs) is None
    assert biography.validate([PARA_1], "Seed Artist", docs) is None  # uno basta si es lo que dan los hechos
    assert plan(_docs("Seed Artist is a Belgian DJ and producer known for tech house and long club sets.")) == "brief"
    short = _docs(WIKI_TEXT)
    assert biography.validate([GOOD_TEXT, GOOD_TEXT], "Seed Artist", short) is None  # 1 o 2, según el modelo
    assert "párrafos" in biography.validate([PARA_1, PARA_2, PARA_1], "Seed Artist", docs)
    assert biography.validate([PARA_1 + " " + PARA_2, "Seed Artist volvió a Berlín en 2020."], "Seed Artist",
                              docs) is None  # sin cuotas por párrafo
    assert "lista" in biography.validate(["Origen: " + PARA_1, PARA_2], "Seed Artist", docs)
    assert "lista" in biography.validate([PARA_1 + " ¿Qué le depara el futuro?", PARA_2], "Seed Artist", docs)
    assert "cliché" in biography.validate([PARA_1 + " Un nombre a seguir.", PARA_2], "Seed Artist", docs)
    copied = PARA_1 + " Old EP became an underground favourite and led to tours across Europe."
    assert "copia literal" in biography.validate([copied, PARA_2], "Seed Artist", docs)


def test_claims_need_supporting_sources():
    docs, short = _docs(), _docs(WIKI_TEXT)
    v = lambda text, d=docs: biography.validate([PARA_1, text], "Seed Artist", d)  # noqa: E731
    # Un sello que publica su música no es un sello fundado.
    assert "sello o proyecto fundado: Scene" in v(PARA_2.replace("Night Shift Records", "Scene Records"))
    assert "sello o proyecto fundado" in biography.validate([PARA_1 + " Fundó su propio sello."], "Seed Artist", short)
    # Residencia: el club debe aparecer en una frase de las fuentes que hable de residencia.
    assert "residencia en club o fiesta: Berghain" in v(PARA_2.replace("club Fuse de Bruselas", "club Berghain"))
    # Éxitos: solo si una fuente lo dice; una canción sin respaldo de listas no es «su mayor éxito».
    assert "éxito o listas" in biography.validate([PARA_1 + " «Old EP» fue su mayor éxito."], "Seed Artist", short)
    assert "integrantes" in biography.validate([PARA_1 + " El proyecto está integrado por Ana y Leo."],
                                               "Seed Artist", short)
    assert "nacimiento" in biography.validate([PARA_1 + " Nació en Gante."], "Seed Artist", short)
    # Exónimos: «Bruselas» y «Berlín» se reconocen como Brussels y Berlin.
    assert v(PARA_2) is None
    assert biography.content_problem("afirmación sin respaldo (residencia en club o fiesta: Berghain)")


def test_unsupported_claim_is_retried_once_and_then_kept_for_a_day():
    claim = GOOD_TEXT.replace("Sus giras", "Tiene una residencia en Berghain. Sus giras")
    client, fake = client_with([(200, {"paragraphs": [claim], "fact_ids": ["H1"]}),
                                (200, {"paragraphs": [GOOD_TEXT], "fact_ids": ["H1"]})])
    body = client.get(f"/v1/artists/{mb.SEED}/biography").json()
    assert fake.calls == 2 and body["bio"]["text"] == GOOD_TEXT
    assert "elimínala" in fake.bodies[1]["messages"][1]["content"]


def test_paragraphs_are_stored_with_a_blank_line_between_them():
    long_wiki = {"query": {"pages": {"1": {"title": "Seed Artist", "extract": LONG_WIKI}}}}
    client, fake = client_with([(200, {"paragraphs": [PARA_1, FLOW_PARA_2], "fact_ids": ["H1", "H2"]})],
                               routes={WIKI_KEY: (200, long_wiki)})
    body = client.get(f"/v1/artists/{mb.SEED}/biography").json()
    assert fake.calls == 1, store.get(biography.KIND, mb.SEED)
    assert body["bio"]["text"] == PARA_1 + "\n\n" + FLOW_PARA_2
    assert "Escribe DOS párrafos" in fake.bodies[0]["messages"][1]["content"]


def test_english_fallback_description_is_translated_once_without_adding_information():
    entity = mb.wikidata_entity(descriptions={"en": "Belgian DJ and producer"})
    routes = {f"wd:{mb.QID}": (200, entity), WIKI_KEY: (404, None)}  # sin texto descriptivo: respaldo
    client, fake = client_with([(200, {"translation": "DJ y productor belga"})], routes=routes)
    profile = client.get(f"/v1/artists/{mb.SEED}").json()
    assert profile["bio"]["text"] == "Belgian DJ and producer." and profile["bio_pending"] is True
    body = client.get(f"/v1/artists/{mb.SEED}/biography").json()
    assert body["bio"] == {**body["bio"], "kind": "factual", "text": "DJ y productor belga.", "language": "es",
                           "translated_from": "en"}
    assert [s["label"] for s in body["bio"]["sources"]] == [f"Wikidata {mb.QID}"]
    profile = client.get(f"/v1/artists/{mb.SEED}").json()
    assert profile["bio"]["text"] == "DJ y productor belga." and profile["bio_pending"] is False and fake.calls == 1


def test_translation_that_adds_information_is_rejected():
    issue = biography.translation_issue
    assert issue("Belgian DJ and producer", "DJ y productor belga") is None
    assert issue("British electronic music duo", "Dúo británico de música electrónica") is None
    assert issue("Belgian DJ and producer", "DJ y productor belga de Amberes") == "nombre nuevo (Antwerp)"  # «Amberes» = Antwerp
    assert issue("Belgian DJ and producer", "DJ y productor belga nacido en 1990") == "cifras nuevas"
    assert issue("Belgian DJ", "DJ belga. Muy famoso") == "más de una frase"


def test_paragraphs_returned_as_a_single_string_are_split_not_iterated():
    client, fake = client_with([(200, {"paragraphs": GOOD_TEXT, "fact_ids": ["H1"]})])
    body = client.get(f"/v1/artists/{mb.SEED}/biography").json()
    assert fake.calls == 1 and body["bio"]["kind"] == "generated" and body["bio"]["text"] == GOOD_TEXT


def test_claim_window_stops_at_the_next_clause_and_ignores_titles():
    # Casos reales (Josh Baker): la residencia no arrastra el EP de la oración siguiente ni el premio el sencillo.
    docs = _docs(LONG_WIKI + " In 2024 Seed Artist was named Breakthrough Producer at the Club Awards.")
    claim = PARA_2.replace("Su paso a Berlín en 2020 abrió una etapa nueva,",
                           "Fue nombrado Breakthrough Producer en los Club Awards, y su sencillo «Old EP» sonó en Berlín,")
    assert biography.validate([PARA_1, claim], "Seed Artist", docs) is None
    tail = PARA_2.replace("club Fuse de Bruselas.", "club Fuse de Bruselas, y publicó «Old EP» en Scene Records.")
    assert biography.validate([PARA_1, tail], "Seed Artist", docs) is None
    assert "éxito o listas" in biography.validate([PARA_1 + " Llegó al puesto 48 de una lista."], "Seed Artist",
                                                  _docs(WIKI_TEXT))


def test_paragraphs_separated_by_a_single_line_break_are_two_paragraphs():
    long_wiki = {"query": {"pages": {"1": {"title": "Seed Artist", "extract": LONG_WIKI}}}}
    client, fake = client_with([(200, {"paragraphs": [PARA_1 + "\n" + FLOW_PARA_2], "fact_ids": ["H1"]})],
                               routes={WIKI_KEY: (200, long_wiki)})
    body = client.get(f"/v1/artists/{mb.SEED}/biography").json()
    assert fake.calls == 1 and body["bio"]["text"] == PARA_1 + "\n\n" + FLOW_PARA_2


def test_literal_backslash_n_between_paragraphs_is_a_paragraph_break():
    long_wiki = {"query": {"pages": {"1": {"title": "Seed Artist", "extract": LONG_WIKI}}}}
    client, fake = client_with([(200, {"paragraphs": [PARA_1 + "\n" + FLOW_PARA_2], "fact_ids": ["H1"]})],
                               routes={WIKI_KEY: (200, long_wiki)})
    body = client.get(f"/v1/artists/{mb.SEED}/biography").json()
    assert fake.calls == 1 and body["bio"]["text"] == PARA_1 + "\n\n" + FLOW_PARA_2


# --- Validador v2: falsos rechazos reales (Bicep, Josh Baker) con extractos de sus fuentes -----------------------
BICEP_DOCS = [
    sources.SourceDoc("S1", "MusicBrainz", "https://mb", "CC0",
                      "Nombre artístico: Bicep. Tipo: grupo. País: Reino Unido. Área asociada (no indica residencia ni "
                      "nacimiento): Belfast. Lugar de formación: London. Año de formación: 2009. Integrantes: BDB, "
                      "Andrew Ferguson, Matthew McBriar. Sellos que han publicado su música (no implica que los haya "
                      "fundado): Ninja Tune, Feel My Bicep, CHROMA."),
    sources.SourceDoc("S3", "Wikipedia (en): Bicep (duo)", "https://wp", "CC BY-SA 4.0",
                      "Bicep are an electronic music production and DJ duo from Belfast, Northern Ireland, consisting of "
                      "Andrew Ferguson and Matthew McBriar. History Bicep was formed in 2009 as a production and DJing pair "
                      "in London. The duo, childhood friends, created a blog called \"Feel My Bicep\", which was used to "
                      "post lost and forgotten disco, Chicago house, Detroit techno and Italo disco edits. They released "
                      "tracks on labels Throne of Blood, Traveller Records and Mystery Meat before joining Will Saul's Aus "
                      "Music and setting up their own label Feel My Bicep in September 2012. That year the pair were "
                      "awarded DJ Mag's 'Best of British Breakthrough DJ' award. After signing to Ninja Tune in 2017, Bicep "
                      "released their debut album Bicep, which went in at number 20 on the UK Albums Chart. The lead "
                      "single, \"Glue\", was voted by the public as DJ Mag's (Best of British) Track of the Year. It also "
                      "reached number 1 on Amazon's Best Electronic of 2017. Bicep released their second album Isles on "
                      "Ninja Tune on 22 January 2021."),
]
BICEP = [
    "Bicep son Andrew Ferguson y Matthew McBriar, amigos de la infancia procedentes de Belfast, Irlanda del Norte, que "
    "en 2009 formaron en Londres un dúo de producción y DJ. Todo empezó con el blog «Feel My Bicep», donde rescataban "
    "edits de disco, house de Chicago, techno de Detroit e italo disco, y que en septiembre de 2012 acabó dando nombre "
    "a su propio sello.",
    "Ese mismo año recibieron el premio a DJ revelación de los Best of British de DJ Mag. Tras fichar por Ninja Tune en "
    "2017 publicaron su álbum de debut, «Bicep», que llegó al puesto 20 de la lista británica de álbumes y cuyo sencillo "
    "«Glue» fue elegido tema del año por el público de DJ Mag. En 2021 llegó su segundo álbum, «Isles».",
]
JOSH_DOCS = [
    sources.SourceDoc("S1", "MusicBrainz", "https://mb", "CC0",
                      "Nombre artístico: Josh Baker. País: Reino Unido. Sellos que han publicado su música (no implica "
                      "que los haya fundado): Three Six Zero Recordings, Baker's Dozen. Contexto secundario (no "
                      "enumerar): algunos lanzamientos recientes son «Breaking Point EP» (2026); «My Place» (2026); "
                      "«Down To The Bone» (2026)."),
    sources.SourceDoc("S3", "Wikipedia (en): Josh Baker (musician)", "https://wp", "CC BY-SA 4.0",
                      "Josh Baker is a British musician, DJ and record producer from Manchester, England. In 2024, he was "
                      "named Breakthrough Producer at the DJ Mag Best of British awards, and several of his singles have "
                      "charted on the UK Singles Chart. He is a co-founder of the record label and events series You&Me "
                      "and of the Hide & Seek festival, and the founder of the electronic music-production education "
                      "platform Syntho. Career Baker is from Manchester and specialises in house music. Baker has "
                      "presented on BBC Radio 1 Dance on several occasions, and in August 2025 he stood in for Pete "
                      "Tong. Several of his singles have entered the UK Singles Chart, among them \"Come "
                      "Closer\" (with Sienna Sophia), which reached number 48, and \"Back It Up\", which reached number "
                      "58. He has performed at festivals including Parklife, and in April 2026 appeared at the Coachella "
                      "Valley Music and Arts Festival in California in a back-to-back set with Kettama and Prospa. In "
                      "2026, Baker headlined a season-long residency at Amnesia, Ibiza, under his You&Me brand."),
]
JOSH = [
    "Josh Baker es un DJ y productor de Manchester, Inglaterra, especializado en house. En 2024 fue nombrado "
    "Breakthrough Producer en los premios Best of British de DJ Mag, y varios de sus sencillos han entrado en la lista "
    "británica, como «Come Closer», junto a Sienna Sophia, y «Back It Up».",
    "Es cofundador del sello y serie de eventos «You&Me» y del festival «Hide & Seek», y fundó la plataforma educativa "
    "Syntho. Ha actuado en Parklife y en abril de 2026 pasó por Coachella junto a Kettama y Prospa; ese mismo año "
    "encabezó una residencia de temporada en Amnesia, Ibiza, con su marca You&Me.",
]


def _bicep(p1=BICEP[0], p2=BICEP[1]):
    return biography.validate([p1, p2], "Bicep", BICEP_DOCS)


def _josh(p1=JOSH[0], p2=JOSH[1]):
    return biography.validate([p1, p2], "Josh Baker", JOSH_DOCS)


def test_real_false_rejections_are_now_valid():
    # Antes: «enumera títulos» (blog, sello y festival entre comillas) y, en Bicep, «enumera años» (4 años).
    assert _bicep() is None and _josh() is None
    assert biography.quality_issue("\n\n".join(BICEP)) is None and biography.quality_issue("\n\n".join(JOSH)) is None


def test_quoted_projects_are_not_release_titles_but_lists_still_are():
    assert biography._release_titles(BICEP[0]) == []                          # blog
    assert biography._release_titles(JOSH[1]) == []                           # sello y festival
    assert biography._release_titles(BICEP[1]) == ["Bicep", "Glue", "Isles"]  # álbum, sencillo, álbum
    assert biography._release_titles("Publicó «Old EP» con el sello Scene Records y su tema «Late Bloom».") == [
        "Old EP", "Late Bloom"]  # el contexto más cercano decide
    listed = BICEP[1].replace("«Isles»", "«Isles», «Glue» y «Bicep»")
    assert "enumera títulos" in _bicep(p2=listed)
    assert "enumera títulos" in biography.quality_issue("Seed Artist publicó «A» (2019), «B» (2020) y «C» (2021).")
    # Dentro de una afirmación, un nombre entre comillas que no es un lanzamiento se comprueba como los demás.
    assert "sello o proyecto fundado: Ninja" in _bicep(p2=BICEP[1].replace("Tras fichar", "Fundaron el sello "
                                                                            "«Ninja Tune» y tras fichar"))
    assert "título entre comillas sin respaldo" in _bicep(p2=BICEP[1].replace("«Isles»", "«Opal»"))


def test_documented_years_are_judged_by_readability():
    assert len(biography._years("\n\n".join(BICEP))) == 4 and _bicep() is None
    assert "año sin respaldo" in _bicep(p2=BICEP[1].replace("En 2021", "En 2019"))  # inventado
    assert "enumera años" in _bicep(p2=BICEP[1].replace("En 2021", "En 2017, 2021 y 2012"))  # lista
    prose = "Bicep: 2009 en Londres, 2012 con sello, 2017 con Ninja Tune y álbum, 2021 con «Isles» y gira larga."
    assert biography.quality_issue(prose) is None  # años documentados en prosa, sin cuota


def test_geographic_equivalences_do_not_mix_origin_birth_and_formation():
    assert _bicep(BICEP[0].replace("Belfast, Irlanda del Norte", "Belfast (Reino Unido)")) is None  # región → país
    assert _josh(JOSH[0].replace("de Manchester, Inglaterra,", "originario de Manchester (Reino Unido),")) is None
    assert "origen: Ireland" in _bicep(BICEP[0].replace("Irlanda del Norte", "Irlanda"))  # no es lo mismo
    assert "origen: Scotland" in _josh(JOSH[0].replace("de Manchester, Inglaterra,", "originario de Manchester, Escocia,"))
    assert "origen: London" in _bicep(BICEP[0].replace("Belfast, Irlanda del Norte", "Londres"))  # se formó allí
    # Salida real de Groq (Bicep): invertía origen y formación con un traslado que ninguna fuente menciona.
    assert "residencia geográfica" in _bicep(BICEP[0].replace("que en 2009 formaron en Londres",
                                                              "que comenzaron en Londres y se trasladaron a Belfast, y "
                                                              "en 2009 formaron"))
    # «Área asociada (no indica… nacimiento): Belfast» no respalda un nacimiento.
    assert "nacimiento" in _bicep(BICEP[0].replace("amigos de la infancia procedentes de", "amigos nacidos en"))


def test_invented_claims_are_still_rejected():
    # El título va delante de la afirmación: «Isles» no consta en ninguna lista. «Glue» sí, aunque la fuente lo
    # nombre en la frase anterior («"Glue" was voted… It also reached number 1…»).
    assert "éxito o listas: Isles" in _bicep(p2=BICEP[1].replace("«Isles».", "«Isles», su mayor éxito en las listas."))
    assert _bicep(p2=BICEP[1].replace("«Glue» fue elegido tema del año por el público de DJ Mag.",
                                      "«Glue» llegó al número 1 de una lista de Amazon.")) is None
    # Varios títulos documentados en prosa se admiten; una lista seguida, no (también con comillas rectas).
    assert _josh(p2=JOSH[1].replace("con su marca You&Me.", 'con su marca You&Me, y lanzó el EP "Breaking Point EP" '
                                    'y, después, el sencillo "My Place" y "Down To The Bone".')) is None
    assert "enumera títulos" in _josh(p2=JOSH[1].replace("con su marca You&Me.", 'con su marca You&Me, y lanzó '
                                                         '"Breaking Point EP", "Down To The Bone" y "My Place".'))
    assert "premio o reconocimiento: Grammy" in _bicep(p2=BICEP[1].replace("«Isles».", "«Isles», que ganó un Grammy."))
    assert "residencia en club o fiesta" in _bicep(p2=BICEP[1] + " Mantienen una residencia en Fabric.")
    assert "sello o proyecto fundado: Ninja" in _bicep(BICEP[0].replace("su propio sello", "su propio sello, antes "
                                                                        "de fundar también Ninja Tune"))
    assert "sello o proyecto fundado: Parklife" in _josh(p2=JOSH[1].replace("«Hide & Seek»", "«Parklife»"))
    assert "residencia en club o fiesta: Pacha" in _josh(p2=JOSH[1].replace("Amnesia", "Pacha"))
    assert "integrantes" in _josh(p2=JOSH[1] + " El proyecto está integrado por Josh Baker y Kettama.")


def test_word_limits_only_stop_excessive_texts():
    assert _bicep(p2="Ese mismo año recibieron el premio a DJ revelación de los Best of British de DJ Mag, antes de "
                     "fichar por Ninja Tune en 2017.") is None  # segundo párrafo breve pero no una frase suelta
    assert "longitud" in _bicep(p2=BICEP[1] + " Su música avanza con calma y crece poco a poco en la pista." * 8)


def test_old_validator_rejections_are_retried_once_and_valid_bios_are_kept():
    old = biography.BiographyRecord(artist_mbid=mb.SEED, biography=None, source_urls=[], generated_at="2026",
                                    model=None, status="rejected", error_code="enumera títulos de lanzamientos")
    assert old.validator_version == 1
    store.put(biography.KIND, mb.SEED, old.model_dump(), biography.TTL_FORMAT_S)
    assert biography.cached(mb.SEED) is None  # se reintenta sin esperar a que caduque
    client, fake = client_with([])
    assert client.get(f"/v1/artists/{mb.SEED}/biography").json()["bio"]["kind"] == "generated" and fake.calls == 1
    assert store.get(biography.KIND, mb.SEED)["validator_version"] == biography.VALIDATOR_VERSION
    client.get(f"/v1/artists/{mb.SEED}/biography")
    assert fake.calls == 1  # una sola vez
    # Una biografía válida anterior y un rechazo por fuente inventada no se regeneran por el cambio de validador.
    for rec in (old.model_copy(update={"status": "ok", "biography": GOOD_TEXT}),
                old.model_copy(update={"error_code": "unknown_source"})):
        store.put(biography.KIND, mb.CO_A, rec.model_dump(), 3600)
        assert biography.cached(mb.CO_A) is not None


def test_wikipedia_narrative_skips_discography_and_clips_at_a_sentence():
    article = ("Paco Osuna (Barcelona, 1974) es un disc jockey español.​\n\n\n== Biografía ==\n"
               "En 1999 inició una residencia en Amnesia. En los últimos años destaca su residencia en Hï Ibiza.\n\n\n"
               "== Discografía ==\nLPs\n\n2008 - Orbeat (Plus 8 Records)\n=== Sencillos ===\n2010 - Amigos\n\n\n"
               "== Reconocimientos ==\nMejor DJ de Techno en los Vicious Awards 2011.\n\n\n== Referencias ==\n\n\n"
               "== Enlaces externos ==\nWeb oficial")
    text = sources._narrative(article)
    assert "Hï Ibiza" in text and "Vicious Awards" in text and "​" not in text
    assert "Orbeat" not in text and "Amigos" not in text and "Web oficial" not in text and "==" not in text
    clipped = sources._clip("Primera frase completa. " * 3 + "Una frase que no cabe entera en el recorte", 80)
    assert clipped.endswith("completa.") and "…" not in clipped


def test_real_cases_paco_osuna_and_jamie_jones():
    paco = [sources.SourceDoc("S1", "Wikipedia (es): Paco Osuna", "https://wp", "CC BY-SA 4.0",
                              "Francisco Osuna Pérez nació en Barcelona el 8 de junio de 1974. Se inició en Valencia, "
                              "ciudad por aquél entonces conocida por el Bakalao, y allí pinchó en varias salas. En 1999 "
                              "inició una residencia en Amnesia, en Ibiza. En 2003 fundó su propio sello discográfico, "
                              "Shake Records.")]
    text = ("Paco Osuna, nacido en Barcelona el 8 de junio de 1974, inició su carrera en Valencia durante el Bakalao. "
            "En 1999 empezó una residencia en Amnesia que lo unió a Ibiza, y en 2003 fundó Shake Records.")
    # La fecha y el lugar coinciden palabra por palabra con la fuente (no es copia) y Valencia no es su nacimiento.
    assert biography.validate(text, "Paco Osuna", paco) is None
    assert "nacimiento: Valencia" in biography.validate(text.replace("nacido en Barcelona el 8 de junio de 1974, inició",
                                                                     "nacido en Valencia, inició"), "Paco Osuna", paco)
    jamie = [sources.SourceDoc("S1", "Wikipedia (en): Jamie Jones (DJ)", "https://wp", "CC BY-SA 4.0",
                               "Jamie Jones is a Welsh DJ and producer. He is a member of the electronic music group Hot "
                               "Natured and the head of the record label Hot Creations, as well as its sub-labels Emerald "
                               "City and Hottrax. In early 2016 Jones launched The House of Hot, an online shop.")]
    text = ("Jamie Jones es un DJ y productor galés, miembro de Hot Natured, que dirige el sello Hot Creations y sus "
            "subsellos Emerald City y Hottrax, y que en 2016 puso en marcha la tienda The House of Hot.")
    assert biography.validate(text, "Jamie Jones", jamie) is None
    # «head of» no es fundar, y «Hot Creations» no contiene el verbo «create».
    assert "sello o proyecto fundado: Creations" in biography.validate(
        text.replace("que dirige el sello", "que fundó el sello"), "Jamie Jones", jamie)


# --- v7: hechos verificados ----------------------------------------------------------------------------------------
JONES_MB = sources.SourceDoc("S1", "MusicBrainz", "https://mb", "CC0",
                             "Nombre artístico: Jamie Jones. Tipo: persona. País: Reino Unido. Lugar de nacimiento: "
                             "Caernarfon. Miembro de: Hot Natured. Sellos que han publicado su música (no implica que "
                             "los haya fundado): Crosstown Rebels, Hot Creations. Contexto secundario (no enumerar): "
                             "algunos lanzamientos recientes son «State of Mind» (2026); «Murder Mystery» (2025).")
JONES_WD = sources.SourceDoc("S2", "Wikidata Q13581065", "https://wd", "CC0",
                             "Descripción breve: DJ, producer. Géneros: música electrónica, pop. Activo desde: 2003.")
JONES_WP = sources.SourceDoc("S3", "Wikipedia (en): Jamie Jones (DJ)", "https://wp", "CC BY-SA 4.0",
                             "Jamie Jones is a Welsh DJ and producer. He is a member of the electronic music group Hot "
                             "Natured and the head of the record label Hot Creations, as well as its sub-labels Emerald "
                             "City and Hottrax. Jones was voted the top DJ of 2011 by the online dance music magazine "
                             "Resident Advisor. Jones hosted his own Paradise party at Ibiza's DC10 nightclub for 8 "
                             "seasons since 2012. In 2022 the Paradise party moved to Amnesia. 2006 - Amazon EP (2006) "
                             "Panic (2006) The Capsule EP (2006).")
JONES = [JONES_MB, JONES_WD, JONES_WP]


def test_facts_keep_their_relation_and_skip_recent_releases_and_lists():
    found = facts.extract(JONES, "Jamie Jones")
    kinds = {f.text: f.kind for f in found}
    assert kinds["Jones hosted his own Paradise party at Ibiza's DC10 nightclub for 8 seasons since 2012."] == "fiesta propia"
    assert kinds[next(t for t in kinds if "Resident Advisor" in t)] == "hito"  # la revista no es una residencia
    assert kinds["Lugar de nacimiento: Caernarfon."] == "origen"
    assert kinds[next(t for t in kinds if t.startswith("Sellos que han publicado"))] == "publica en"  # no «fundó»
    assert not any(t.startswith("Géneros:") for t in kinds)  # «pop» sin respaldo; «música electrónica», genérico
    assert not any("State of Mind" in t or "Panic" in t for t in kinds)  # ni lanzamientos recientes ni discografía
    chosen = facts.select(found)
    assert 3 <= len(chosen) <= facts.MAX_FACTS and chosen[0].kind == "identidad"
    assert not any(f.kind == "publica en" for f in chosen)  # hay hechos de sobra: dónde publica no entra
    assert [f.id for f in chosen] == [f"H{i}" for i in range(1, len(chosen) + 1)]
    duo = [sources.SourceDoc("S1", "MusicBrainz", "https://mb", "CC0", "Tipo: grupo. Integrantes: Andrew, Matthew.")]
    assert facts.artist_kind(duo) == "dúo" and facts.artist_kind(JONES) == "solista"


def test_text_is_checked_against_the_selected_facts():
    docs = facts.as_docs(facts.select(facts.extract(JONES, "Jamie Jones")))
    good = ("Jamie Jones es un DJ y productor galés nacido en Caernarfon. Miembro de Hot Natured, dirige el sello Hot "
            "Creations y sus subsellos Emerald City y Hottrax, y durante años organizó su propia fiesta, Paradise, en "
            "el club DC10 de Ibiza.")
    assert biography.validate(good, "Jamie Jones", docs) is None, biography.validate(good, "Jamie Jones", docs)
    assert "sello o proyecto fundado" in biography.validate(good.replace("dirige el sello", "fundó el sello"),
                                                          "Jamie Jones", docs)  # dirigir no es fundar
    assert "nombre sin respaldo (Fabric)" in biography.validate(good + " También actuó en Fabric.", "Jamie Jones", docs)
    assert "año sin respaldo" in biography.validate(good.replace("durante años", "hasta 2020"), "Jamie Jones", docs)
    assert "temporal" in biography.validate(good + " Próximamente publicará un álbum.", "Jamie Jones", docs)


def test_old_biographies_are_renewed_on_visit_and_kept_as_legacy_meanwhile():
    store.put("image", mb.SEED, {"image": None, "reason": "no_image", "v": api.IMAGE_RESOLVER_VERSION}, 3600)  # otros datos cacheados: intactos
    old = biography.BiographyRecord(artist_mbid=mb.SEED, biography=GOOD_TEXT, source_urls=["https://wp"],
                                    source_labels=["Wikipedia"], generated_at="2026", model="m", status="ok",
                                    prompt_version=6)
    store.put(biography.KIND, mb.SEED, old.model_dump(), biography.TTL_OK_S)
    assert biography.cached(mb.SEED) is None  # una biografía válida de v6 no es definitiva para v7
    client, fake = client_with([(200, {"paragraphs": [GOOD_TEXT.replace("«Old EP»", "«Inventado»")],
                                       "fact_ids": ["H1"]})] * 2)
    profile = client.get(f"/v1/artists/{mb.SEED}").json()
    assert profile["bio"]["text"] == GOOD_TEXT and profile["bio"]["legacy"] is True and profile["bio_pending"] is True
    assert fake.calls == 0  # la ficha no llama a Groq: la renovación es la visita a /biography
    body = client.get(f"/v1/artists/{mb.SEED}/biography").json()  # la nueva no es válida: sigue la anterior
    assert fake.calls == 2 and body["bio"]["text"] == GOOD_TEXT and body["bio"]["legacy"] is True
    assert client.get(f"/v1/artists/{mb.SEED}").json()["bio_pending"] is False and fake.calls == 2  # sin bucles
    # Una nueva válida sustituye a la anterior (y ya no arrastra la heredada).
    biography.invalidate(mb.SEED)
    store.put(biography.KIND, mb.SEED, old.model_dump(), biography.TTL_OK_S)
    client, fake = client_with([(200, {"paragraphs": [GOOD_TEXT], "fact_ids": ["H1"]})])
    body = client.get(f"/v1/artists/{mb.SEED}/biography").json()
    saved = store.get(biography.KIND, mb.SEED)
    assert fake.calls == 1 and body["bio"]["legacy"] is False and saved["prompt_version"] == biography.PROMPT_VERSION
    assert saved["previous"] is None and store.get("image", mb.SEED) == {"image": None, "reason": "no_image", "v": api.IMAGE_RESOLVER_VERSION}
    # Un rechazo de una versión anterior no bloquea la nueva generación.
    old_rejected = old.model_copy(update={"status": "rejected", "biography": None, "error_code": "enumera años"})
    store.put(biography.KIND, mb.CO_A, old_rejected.model_dump(), biography.TTL_REJECTED_S)
    assert biography.cached(mb.CO_A) is None


def test_pending_editorial_texts_are_not_published(monkeypatch):
    from app import api
    entry = {"text": "Texto editorial sin revisar.", "reviewed": False, "language": "es",
             "sources": [{"label": "MusicBrainz", "url": "https://mb"}]}
    monkeypatch.setattr(api.editorial, "bio", lambda mbid: entry)
    client, _ = client_with([], routes={WIKI_KEY: (404, None)})  # sin texto descriptivo
    profile = client.get(f"/v1/artists/{mb.SEED}").json()
    body = client.get(f"/v1/artists/{mb.SEED}/biography").json()
    assert profile["bio"]["kind"] == "factual" and body["bio"]["kind"] == "factual"
    assert "sin revisar" not in json.dumps(profile) + json.dumps(body)
    monkeypatch.setattr(api.editorial, "bio", lambda mbid: {**entry, "reviewed": True})
    assert client.get(f"/v1/artists/{mb.SEED}").json()["bio"]["kind"] == "editorial"  # revisado: sí


def test_artistic_name_and_rejected_draft_is_kept_only_for_diagnosis():
    docs = [sources.SourceDoc("H1", "Wikipedia (en): Joseph Capriati", "https://wp", None,
                              "Joseph Capriati started Djing in 1998 at the age of 11 in his hometown of Caserta. Years "
                              "later, he began performing regularly as a DJ resident at Disco Seven Club under the "
                              "artistic name \"Prince J\".")]
    text = ("Joseph Capriati empezó a pinchar en 1998, con once años, en Caserta, y años después fue DJ residente del "
            "Disco Seven Club bajo el alias de «Prince J».")
    assert biography.validate(text, "Joseph Capriati", docs) is None  # «artistic name» respalda el alias
    invented = GOOD_TEXT.replace("«Old EP»", "«Inventado»")
    client, _ = client_with([(200, {"paragraphs": [invented], "fact_ids": ["H1"]})] * 2)
    body = client.get(f"/v1/artists/{mb.SEED}/biography").json()
    assert store.get(biography.KIND, mb.SEED)["rejected_draft"] == invented and "Inventado" not in json.dumps(body)
