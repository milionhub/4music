"""Carteles 3.1: validación de imagen, saneado, auditoría, JSON cortado y errores de Groq (transporte simulado)."""

import base64
import json

import pytest
from fastapi.testclient import TestClient

from app import posters
from app.api import get_groq_client
from app.groq_client import GroqClient
from app.main import app

JPEG = base64.b64encode(b"\xff\xd8\xff\xe0" + b"0" * 64).decode()
PNG = base64.b64encode(b"\x89PNG\r\n\x1a\n" + b"0" * 64).decode()
WEBP = base64.b64encode(b"RIFF\x00\x00\x00\x00WEBPVP8 " + b"0" * 64).decode()
GIF = base64.b64encode(b"GIF89a" + b"0" * 64).decode()

SW38_LIKE = {
    "event_name": "SW38", "dates": [{"text": "3-7 SEPTEMBER 2026", "iso": None}], "location": "ROQUETAS DE MAR",
    "stages": ["1", "2"], "colors": ["#ff2e88", "red", "#07060B"],
    "sessions": [
        {"date": {"text": "03.09", "iso": "2026-09-03"}, "label": "THURSDAY NIGHTTIME", "stage": "1", "time": "22:00",
         "artists": ["CUKY", "PERSIC", "MIHIGH"]},
        {"date": {"text": "04.09", "iso": None}, "label": "FRIDAY DAYTIME", "stage": "2", "time": None,
         "artists": ["JAMIE JONES", "JOSEPH CAPRIATI"]},
    ],
    "artists": [], "individual_times": [{"name": "MIHIGH", "time": "22:00"}],
    "b2b": [{"artists": ["CUKY", "PERSIC"], "text": "CUKY B2B PERSIC"},
            {"artists": ["JAMIE JONES", "JOSEPH CAPRIATI"], "text": "B2B JOSEPH CAPRIATI"}],
    "uncertain": [], "unreadable_text": [],
}


class Transport:
    def __init__(self, status=200, content="", finish="stop"):
        self.status, self.content, self.finish, self.calls = status, content, finish, []

    def __call__(self, url, headers, body, timeout):
        self.calls.append(json.loads(body))
        if self.status != 200:
            return self.status, b'{"error": {}}', 7.0
        payload = {"choices": [{"message": {"content": self.content}, "finish_reason": self.finish}],
                   "usage": {"prompt_tokens": 2390, "completion_tokens": 1540}}
        return 200, json.dumps(payload).encode(), None


@pytest.fixture(autouse=True)
def _reset_quota(monkeypatch):
    posters._daily.clear()
    monkeypatch.setenv("POSTER_DAILY_LIMIT", "30")
    yield
    app.dependency_overrides.clear()


def call(transport, image=JPEG, **body):
    app.dependency_overrides[get_groq_client] = lambda: GroqClient("test-key", "openai/gpt-oss-20b", transport=transport,
                                                                   sleep=lambda s: None)
    return TestClient(app).post("/v1/posters/analyze", json={"image": image, **body})


def test_acepta_jpeg_png_webp_y_rechaza_otros_formatos():
    for img, mime in ((JPEG, "image/jpeg"), (PNG, "image/png"), (WEBP, "image/webp")):
        assert posters.decode_image(img)[1] == mime
    t = Transport(content=json.dumps(SW38_LIKE))
    assert call(t, image=GIF).json()["error"]["code"] == "unsupported_image"
    assert call(t, image="no-es-base64!!").status_code == 422
    big = base64.b64encode(b"\xff\xd8\xff" + b"0" * (posters.MAX_IMAGE_BYTES + 1)).decode()
    assert call(t, image=big).status_code == 413
    assert t.calls == []  # ninguna imagen inválida llega a Groq


def test_extraccion_completa_auditada_sin_inventar():
    t = Transport(content=json.dumps(SW38_LIKE))
    r = call(t)
    assert r.status_code == 200
    d = r.json()
    assert d["complete"] is True and d["mode"] == "full"
    assert d["colors"] == ["#FF2E88", "#07060B"]  # colores no hex descartados
    assert d["sessions"][0]["date"]["iso"] is None  # año no impreso en «03.09»
    assert d["individual_times"] == []  # hora igual a la del bloque: no es hora de DJ
    assert {r["field"] for r in d["review"]} == {"iso", "individual_times"}
    assert [b["artists"] for b in d["b2b"]] == [["CUKY", "PERSIC"], ["JAMIE JONES", "JOSEPH CAPRIATI"]]
    assert d["usage"] == {"input": 2390, "output": 1540}
    sent = t.calls[0]
    assert sent["model"] == "qwen/qwen3.8-27b" and sent["response_format"] == {"type": "json_object"}
    assert sent["messages"][0]["content"][1]["image_url"]["url"].startswith("data:image/jpeg;base64,")


def test_respuesta_cortada_conserva_solo_bloques_completos():
    text = json.dumps(SW38_LIKE)
    cut = text[: text.index('"JOSEPH CAPRIATI"]') + 8]  # se corta dentro de los artistas del segundo bloque
    d = call(Transport(content=cut, finish="length")).json()
    assert d["complete"] is False
    assert [s["artists"] for s in d["sessions"]] == [["CUKY", "PERSIC", "MIHIGH"]]
    assert d["event_name"] == "SW38" and d["b2b"] == []
    assert any(r["action"] == "reparado" for r in d["review"])


def test_repair_json_no_inventa_estructura():
    assert posters.repair_json('{"a": [1, 2], "b": {"c": "x') == {"a": [1, 2]}
    assert posters.repair_json("basura") is None
    assert posters.repair_json('{"a": 1}') == {"a": 1}


@pytest.mark.parametrize("status,code", [(401, "poster_ai_not_configured"), (429, "poster_ai_rate_limited"),
                                         (503, "poster_ai_unavailable"), (500, "poster_ai_bad_response")])
def test_errores_de_groq_sin_reintentos_que_gasten_cuota(status, code):
    t = Transport(status=status)
    r = call(t)
    assert r.json()["error"]["code"] == code
    # Una sola llamada, salvo el 429 por minuto: no gasta cuota y se espera una vez lo que pide Groq (7 s).
    assert len(t.calls) == (2 if status == 429 else 1)


def test_limite_por_minuto_espera_una_vez_y_sigue():
    class Once(Transport):
        def __call__(self, url, headers, body, timeout):
            self.status = 429 if not self.calls else 200
            return super().__call__(url, headers, body, timeout)
    t = Once(content=json.dumps(SW38_LIKE))
    assert call(t).status_code == 200
    assert len(t.calls) == 2


def test_respuesta_ilegible_y_sin_clave():
    assert call(Transport(content="no json")).json()["error"]["code"] == "poster_ai_bad_response"
    app.dependency_overrides[get_groq_client] = lambda: GroqClient("", "")
    r = TestClient(app).post("/v1/posters/analyze", json={"image": JPEG})
    assert r.status_code == 503 and r.json()["error"]["code"] == "poster_ai_not_configured"
    assert "test-key" not in r.text


def test_limite_diario_por_cliente(monkeypatch):
    monkeypatch.setenv("POSTER_DAILY_LIMIT", "2")
    t = Transport(content=json.dumps(SW38_LIKE))
    assert [call(t).status_code for _ in range(3)] == [200, 200, 429]
    assert len(t.calls) == 2


def test_continuacion_y_region_envian_contexto():
    t = Transport(content=json.dumps({**SW38_LIKE, "sessions": [], "artists": [{"name": "GEOUSHY"}]}))
    d = call(t, mode="continue", known_sessions=["03.09 THURSDAY NIGHTTIME 1"], known_names=["CUKY"]).json()
    assert d["mode"] == "continue" and d["artists"] == [{"name": "GEOUSHY", "stage": None, "day": None}]
    prompt = t.calls[0]["messages"][0]["content"][0]["text"]
    assert "THURSDAY NIGHTTIME" in prompt and '"CUKY"' in prompt
    call(t, mode="region")
    assert "CROPPED FRAGMENT" in t.calls[1]["messages"][0]["content"][0]["text"]


# --- 3.6A: casos reproducidos con los pilotos (sin llamadas reales) ---------------------------------------------------

def extract(over):
    return posters.sanitize({**SW38_LIKE, **over}, "full", True, "m")


def test_b2b_con_hora_propia_la_conserva_y_una_hora_repetida_entre_solistas_no():
    times = [{"name": "CUKY", "time": "23:00 - 01:00"}, {"name": "PERSIC", "time": "23:00 - 01:00"}]
    d = extract({"individual_times": times})
    assert [t.name for t in d.individual_times] == ["CUKY", "PERSIC"]  # misma hora: es la de su B2B, no del bloque
    d = extract({"individual_times": times, "b2b": []})
    assert d.individual_times == []  # sin B2B, dos solistas con la misma hora sigue siendo la del bloque


def test_anio_impreso_se_conserva_y_el_de_la_cabecera_no_se_atribuye():
    dates = [{"text": "10.09.26", "iso": "2026-09-10"}, {"text": "SEPTEMBER 10 2026", "iso": "2026-09-10"},
             {"text": "10.09", "iso": "2026-09-10"}, {"text": "10.09.25", "iso": "2026-09-10"},
             {"text": "31.02.2026", "iso": "2026-02-31"}, {"text": "IBIZA26", "iso": "2026-01-01"}]
    d = extract({"dates": dates})
    assert [x.iso for x in d.dates] == ["2026-09-10", "2026-09-10", None, None, None, None]
    assert d.sessions[0].date.iso is None  # «03.09» bajo «3-7 SEPTEMBER 2026»: el año no es suyo


def test_piloto_sw38_cortado_dentro_de_los_b2b():
    # Forma real del piloto compacto de Fase 1.4: el día y la franja en el mismo texto, «B2B X» en dos líneas.
    real = {**SW38_LIKE, "sessions": [
        {"date": {"text": "05.09 SATURDAY NIGHTTIME", "iso": None}, "label": None, "stage": "1", "time": "22:00",
         "artists": ["JOE VANDITTI", "MAHONY", "JAMIE JONES", "JOSEPH CAPRIATI"]}]}
    text = json.dumps(real)
    cut = text[: text.index('"B2B JOSEPH CAPRIATI"') - 30]
    d = call(Transport(content=cut, finish="length")).json()
    assert d["complete"] is False and len(d["sessions"]) == 1 and d["sessions"][0]["artists"][-1] == "JOSEPH CAPRIATI"
    assert [b["artists"] for b in d["b2b"]] == [["CUKY", "PERSIC"]]  # el B2B cortado no se rellena
