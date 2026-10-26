"""Pruebas offline (servidor local simulado; no llaman a Groq).

    py -3.11 -m unittest research/poster_ai/test_poster_ai.py
"""

import json
import os
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
SERVER = ThreadingHTTPServer(("127.0.0.1", 0), BaseHTTPRequestHandler)  # se sustituye el handler abajo
os.environ["POSTER_AI_API_URL"] = f"http://127.0.0.1:{SERVER.server_port}/v1/chat/completions"

import evaluate as EV  # noqa: E402
import extract_poster as XP  # noqa: E402
from poster_schema import (audit_extraction, parse_and_validate, parse_compact, validate,  # noqa: E402
                           validate_compact)

FAKE_KEY = "gsk_FAKE_0123456789"
CALLS: dict[str, int] = {"n": 0}
GOOD = {"event_name": "Night A", "dates": [{"text": "12.07.2025", "iso": "2025-07-12"}], "location": "Club X",
        "stages": ["Main"], "artists": [{"name": "Sven Väth", "stage": "Main", "day": None, "time": "23:00",
                                         "uncertain": False}], "unreadable_text": []}
JPEG = b"\xff\xd8\xff\xe0" + b"0" * 100
# Variante compacta: cada nombre una sola vez, dentro de su sesión.
COMPACT = {"event_name": "SW38", "dates": [{"text": "3-7 SEPTEMBER 2026", "iso": None}],
           "location": "ROQUETAS DE MAR, SPAIN", "stages": ["1", "2"],
           "sessions": [{"date": {"text": "03.09", "iso": "2026-09-03"}, "label": "THURSDAY NIGHTTIME", "stage": "1",
                         "time": "22:00", "artists": ["CUKY", "PERSIC", "PACO OSUNA"]},
                        {"date": {"text": "04.09", "iso": None}, "label": "FRIDAY DAYTIME", "stage": "2",
                         "time": None, "artists": ["COSMINA", "5UNIVERSOS"]}],
           "artists": [], "individual_times": [{"name": "PACO OSUNA", "time": "22:00"}],
           "b2b": [{"artists": ["CUKY", "PERSIC"], "text": "CUKY B2B PERSIC"}],
           "uncertain": ["5UNIVERSOS"], "unreadable_text": []}


class Handler(BaseHTTPRequestHandler):
    mode = "ok"

    def log_message(self, *a):
        pass

    def do_POST(self):
        CALLS["n"] += 1
        self.rfile.read(int(self.headers["Content-Length"]))
        m = Handler.mode
        if m == "slow":
            import time
            time.sleep(1.5)
        content = {"compact": COMPACT}.get(m, GOOD)
        finish = "length" if m == "length" else "stop"
        code, body, hdr = 200, json.dumps({"model": XP.MODEL, "x_groq": {"id": "req_1"}, "usage": {
            "prompt_tokens": 2100, "completion_tokens": 120},
            "choices": [{"finish_reason": finish, "message": {"content": json.dumps(content)}}]}).encode(), {
            "x-ratelimit-remaining-requests": "999"}
        if m == "429":
            code, body, hdr = 429, b'{"error":{"message":"Rate limit reached"}}', {"retry-after": "7"}
        elif m == "401":
            code, body, hdr = 401, b'{"error":{"message":"Invalid API Key"}}', {}
        elif m == "notjson":
            body = b"<html>"
        self.send_response(code)
        for k, v in hdr.items():
            self.send_header(k, v)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        try:
            self.wfile.write(body)
        except ConnectionError:
            pass


SERVER.RequestHandlerClass = Handler
threading.Thread(target=SERVER.serve_forever, daemon=True).start()


class SchemaTest(unittest.TestCase):
    def test_valid_and_invalid(self):
        self.assertEqual(validate(GOOD), [])
        bad = dict(GOOD, artists=[{"name": "", "stage": 3, "uncertain": "no", "genre": "techno"}], extra=1)
        errs = " ".join(validate(bad))
        for frag in ("claves no previstas", "name vacío", "stage", "uncertain", "genre"):
            self.assertIn(frag, errs)
        self.assertIn("iso", " ".join(validate(dict(GOOD, dates=[{"text": "x", "iso": "12/07/25"}]))))
        obj, errs = parse_and_validate("{no json")
        self.assertIsNone(obj)
        self.assertIn("JSON inválido", errs[0])


class ImageTest(unittest.TestCase):
    def test_check_image(self):
        tmp = Path(tempfile.mkdtemp())
        (tmp / "a.jpg").write_bytes(JPEG)
        (tmp / "b.gif").write_bytes(b"GIF89a....")
        (tmp / "c.png").write_bytes(b"\x89PNG\r\n\x1a\n" + b"0" * (XP.MAX_IMAGE_BYTES + 1))
        (tmp / "d.jpg").write_bytes(b"")
        self.assertEqual(XP.check_image(tmp / "a.jpg")[0], "image/jpeg")
        for name in ("b.gif", "c.png", "d.jpg", "missing.jpg"):
            with self.assertRaises(XP.ImageError):
                XP.check_image(tmp / name)


class CallTest(unittest.TestCase):
    def setUp(self):
        CALLS["n"] = 0
        XP.TIMEOUT_S = 1
        self.payload = XP.build_request("image/jpeg", JPEG)

    def run_mode(self, mode):
        Handler.mode = mode
        return XP.call_groq(self.payload, FAKE_KEY)

    def test_ok_records_usage_and_no_key(self):
        rec = self.run_mode("ok")
        s = XP.summarize(rec)
        self.assertEqual((s["status"], s["json_valid"], s["schema_errors"]), (200, True, []))
        self.assertEqual(s["usage"]["prompt_tokens"], 2100)
        self.assertEqual(s["rate_limit"]["x-ratelimit-remaining-requests"], "999")
        self.assertNotIn(FAKE_KEY, json.dumps(s))

    def test_errors_are_classified_without_retry(self):
        for mode, kind in (("429", "rate_limit"), ("401", "auth"), ("slow", "timeout")):
            CALLS["n"] = 0
            rec = self.run_mode(mode)
            self.assertEqual(rec["error_kind"], kind, mode)
            self.assertEqual(CALLS["n"], 1, f"{mode}: no debe reintentar")
        self.assertEqual(self.run_mode("429")["rate_limit"].get("retry-after"), "7")
        self.assertEqual(self.run_mode("notjson")["error_kind"], "invalid_response")

    def test_main_dry_run_budget_and_no_repeat(self):
        tmp = Path(tempfile.mkdtemp())
        img = tmp / "p1.jpg"
        img.write_bytes(JPEG)
        XP.OUTPUTS = tmp / "out"
        os.environ["GROQ_API_KEY"] = FAKE_KEY
        Handler.mode = "ok"
        self.assertEqual(XP.main([str(img), "--dry-run"]), 0)
        self.assertEqual(CALLS["n"], 0)
        self.assertEqual(XP.main([str(img)]), 0)
        self.assertEqual(XP.main([str(img)]), 0)  # ya existe la salida: no repite
        self.assertEqual(CALLS["n"], 1)
        self.assertEqual(XP.main([str(img), "--force", "--budget", "1"]), 3)  # presupuesto agotado
        self.assertEqual(CALLS["n"], 1)
        stored = "".join(p.read_text(encoding="utf-8") for p in XP.OUTPUTS.iterdir())
        self.assertNotIn(FAKE_KEY, stored)
        del os.environ["GROQ_API_KEY"]

    def test_length_is_incomplete_and_compact_variant_is_separate(self):
        tmp = Path(tempfile.mkdtemp())
        img = tmp / "p2.jpg"
        img.write_bytes(JPEG)
        XP.OUTPUTS = tmp / "out"
        os.environ["GROQ_API_KEY"] = FAKE_KEY
        Handler.mode = "length"
        self.assertEqual(XP.main([str(img)]), 5)  # JSON legible pero cortado: incompleto, sin reintento
        self.assertEqual(CALLS["n"], 1)
        orig = json.loads((XP.OUTPUTS / "p2.json").read_text(encoding="utf-8"))
        self.assertEqual((orig["error_kind"], orig["complete"], orig["json_valid"]), ("incomplete", False, True))
        Handler.mode = "compact"
        self.assertEqual(XP.main([str(img), "--variant", "compact", "--budget", "2"]), 0)
        comp = json.loads((XP.OUTPUTS / "compact" / "p2.json").read_text(encoding="utf-8"))
        self.assertEqual((comp["variant"], comp["complete"], comp["schema_errors"]), ("compact", True, []))
        self.assertEqual(json.loads((XP.OUTPUTS / "p2.json").read_text(encoding="utf-8")), orig)  # intacto
        self.assertEqual(XP.main([str(img), "--variant", "compact", "--force", "--budget", "2"]), 3)  # presupuesto común
        self.assertEqual(CALLS["n"], 2)
        del os.environ["GROQ_API_KEY"]


class EvaluatorTest(unittest.TestCase):
    def test_metrics(self):
        ref = {"event_name": "Night A", "location": "Club X", "dates": [{"text": "12.07.2025", "iso": "2025-07-12"}],
               "artists": [{"name": "Sven Väth", "stage": "Main", "time": "23:00"},
                           {"name": "Mochakk"}, {"name": "Chris Stassy", "accepted_variants": ["CHRIS STASSY"]},
                           {"name": "Ilario Alicante"}]}
        pred = dict(GOOD, artists=[
            {"name": "SVEN VATH", "stage": "Main", "time": "22:00", "uncertain": False},  # acento normalizado
            {"name": "chris stassy", "stage": None, "time": None, "uncertain": False},
            {"name": "Ilario Alicant", "stage": None, "time": None, "uncertain": True},   # aproximado: revisión
            {"name": "Daft Punk", "stage": None, "time": None, "uncertain": False}])      # inventado
        r = EV.evaluate_one({"image": "x", "json_valid": True, "schema_errors": [], "extraction": pred,
                             "latency_s": 1.0, "usage": {"prompt_tokens": 10, "completion_tokens": 5}}, ref)
        a = r["artists"]
        self.assertEqual(a["correct"], 2)
        self.assertEqual(a["omitted"], ["Mochakk", "Ilario Alicante"])
        self.assertEqual([x["predicted"] for x in a["invented"]], ["Daft Punk"])
        self.assertEqual([x["predicted"] for x in a["needs_review"]], ["Ilario Alicant"])
        self.assertEqual((a["precision"], a["recall"]), (0.5, 0.5))
        self.assertEqual((a["stage"]["correct"], a["time"]["correct"]), (1, 0))
        self.assertEqual(r["event_name"], "match")
        self.assertTrue(r["dates"]["exact"])
        agg = EV.aggregate([r, {"image": "y", "json_valid": False, "evaluated": False, "latency_s": 2.0}])
        self.assertEqual((agg["posters"], agg["evaluated"], agg["json_valid"]), (2, 1, 1))
        self.assertEqual(EV.compare_text("Club Xs", "Club X"), "needs_review")
        self.assertEqual(EV.compare_text("NOW HERE", "NOW HERE BY PACO OSUNA", ["NOW HERE"]), "match")
        rng = EV.compare_dates([{"text": "3-7 September 2026", "iso": "2026-09-03"}],
                               [{"text": "3-7 SEPTEMBER 2026", "iso": None}])
        self.assertTrue(rng["exact"])  # sin iso en la referencia se compara el texto

    def test_sessions_and_invented_individual_times(self):
        ref_s = [{"date": {"text": "03.09", "iso": "2026-09-03"}, "label": "THURSDAY NIGHTTIME", "stage": "1",
                  "time": "22:00", "artists": ["CUKY B2B PERSIC", "PACO OSUNA"]},
                 {"date": {"text": "04.09", "iso": "2026-09-04"}, "label": "FRIDAY DAYTIME", "stage": "2",
                  "time": None, "artists": ["COSMINA"]},
                 {"date": {"text": "04.09", "iso": "2026-09-04"}, "label": "FRIDAY NIGHTTIME", "stage": "2",
                  "time": None, "artists": ["PRIKU"]}]
        pred_s = [{"date": {"text": "03.09 THURSDAY", "iso": None}, "label": "Nighttime", "stage": "1",
                   "time": "22:00", "artists": ["Cuky B2B Persic", "Manda Moor"]},
                  {"date": {"text": "04.09", "iso": "2026-09-04"}, "label": "FRIDAY NIGHTTIME", "stage": "2",
                   "time": "22:00", "artists": ["PRIKU"]}]
        s = EV.compare_sessions(pred_s, ref_s)
        self.assertEqual((s["matched"], s["extra"], s["time_correct"]), (2, 0, 1))
        self.assertEqual(s["missing"][0]["label"], "FRIDAY DAYTIME")
        self.assertEqual(s["detail"][0]["artists_missing"], ["PACO OSUNA"])
        self.assertEqual(s["detail"][0]["artists_extra"], ["Manda Moor"])
        self.assertEqual(s["detail"][1]["time"], "not_in_reference")  # hora de bloque inventada
        self.assertAlmostEqual(s["artist_assignment_recall"], 0.5)
        m = EV.match_artists([{"name": "PRIKU", "stage": "2", "time": "23:00", "uncertain": False}],
                             [{"name": "PRIKU", "stage": "2", "time": None}])
        self.assertEqual(m["time"]["invented"], [{"artist": "PRIKU", "predicted": "23:00"}])
        self.assertEqual(m["stage"]["correct"], 1)

    def test_sessions_schema_is_optional_and_validated(self):
        self.assertEqual(validate(GOOD), [])  # sin "sessions": compatible
        ok = dict(GOOD, sessions=[{"date": {"text": "03.09", "iso": None}, "label": None, "stage": "1",
                                   "time": "22:00", "artists": ["A"]}])
        self.assertEqual(validate(ok), [])
        bad = dict(GOOD, sessions=[{"date": "03.09", "stage": 1, "artists": "A", "dj_times": []}])
        errs = " ".join(validate(bad))
        for frag in ("sessions[0].date", "sessions[0].stage", "sessions[0].artists", "dj_times"):
            self.assertIn(frag, errs)

    def test_references_are_consistent(self):
        for ref_path in sorted(EV.REFS.glob("0*.json")):
            ref = json.loads(ref_path.read_text(encoding="utf-8"))
            names = {EV.norm(a["name"]) for a in ref["artists"]}
            self.assertEqual(len(names), len(ref["artists"]), f"{ref_path.name}: artistas duplicados")
            self.assertTrue(all(a["time"] is None for a in ref["artists"]), ref_path.name)
            in_sessions = [EV.norm(x) for s in ref.get("sessions", []) for x in s["artists"]]
            if in_sessions:
                self.assertEqual(sorted(in_sessions), sorted(names), f"{ref_path.name}: sesiones ≠ artistas")
            self.assertTrue(all(" b2b " not in n for n in names), f"{ref_path.name}: B2B sin separar")
            for b in ref.get("b2b", []):  # cada miembro de un B2B es también un artista
                self.assertTrue({EV.norm(x) for x in b["artists"]} <= names, f"{ref_path.name}: {b}")
            dates = ref["dates"] + [s["date"] for s in ref.get("sessions", []) if s.get("date")]
            for d in dates:  # iso solo si el año está impreso en ese mismo texto: no se deducen años
                if d.get("iso"):
                    self.assertIn(d["iso"][:4], d["text"], f"{ref_path.name}: año deducido en {d}")
            self.assertEqual(validate({k: v for k, v in ref.items() if k in {"dates", "b2b"}}
                                      | {"event_name": None, "location": None, "stages": [], "artists": [],
                                         "unreadable_text": []}), [], ref_path.name)
        self.assertEqual(EV.compare_text(None, None), "both_null")

    def test_compact_schema_expansion_and_audit(self):
        self.assertEqual(validate_compact(COMPACT), [])
        errs = " ".join(validate_compact(dict(COMPACT, artists=[{"name": "X", "time": "23:00"}],
                                              individual_times=[{"name": "X"}], extra=1)))
        for frag in ("claves no previstas", "artists[0]", "individual_times[0]"):
            self.assertIn(frag, errs)
        compact, errors, ext, review = parse_compact(json.dumps(COMPACT))
        self.assertEqual(errors, [])
        self.assertEqual([a["name"] for a in ext["artists"]], ["CUKY", "PERSIC", "PACO OSUNA", "COSMINA", "5UNIVERSOS"])
        self.assertEqual({a["stage"] for a in ext["artists"][:3]}, {"1"})
        self.assertTrue(ext["artists"][4]["uncertain"])
        self.assertIsNone(ext["artists"][2]["time"])  # 22:00 = inicio de su sesión: descartado
        self.assertIsNone(ext["sessions"][0]["date"]["iso"])  # año no impreso en "03.09"
        self.assertEqual(COMPACT["sessions"][0]["date"]["iso"], "2026-09-03")  # el original no se modifica
        self.assertEqual(sorted(r["field"] for r in review), ["artists.time", "iso"])
        # Esquema original: hora repetida en el bloque sin hora de sesión -> descartada; hora propia -> se conserva.
        orig = {"dates": [{"text": "SAT 12 JULY 2025", "iso": "2025-07-12"}],
                "sessions": [{"date": None, "label": None, "stage": "2", "time": None, "artists": ["A", "B", "C"]}],
                "artists": [{"name": "A", "time": "23:00"}, {"name": "B", "time": "23:00"}, {"name": "C", "time": "01:00"}]}
        cleaned, review = audit_extraction(orig)
        self.assertEqual([a["time"] for a in cleaned["artists"]], [None, None, "01:00"])
        self.assertEqual(len(review), 2)
        self.assertEqual(cleaned["dates"][0]["iso"], "2025-07-12")  # año impreso: se conserva

    def test_incomplete_output_is_not_evaluated_and_strict_spelling(self):
        out = {"image": "x", "json_valid": True, "schema_errors": [], "finish_reason": "length", "extraction": GOOD}
        r = EV.evaluate_one(out, {"artists": [{"name": "Sven Väth"}]})
        self.assertEqual((r["evaluated"], r["complete"]), (False, False))
        m = EV.match_artists([{"name": "SEDEF ADAŞI"}, {"name": "REELow"}, {"name": "ROSSI"}, {"name": "JNJS"}],
                             [{"name": "SEDEF ADASÏ"}, {"name": "REELOW"}, {"name": "ROSSI.", "accepted_variants": ["ROSSI"]},
                              {"name": "JNJS"}])
        self.assertEqual(m["correct"], 4)  # la comparación normalizada no cambia
        self.assertEqual(m["exact_spelling"], 2)
        self.assertEqual([d["predicted"] for d in m["spelling_diffs"]], ["SEDEF ADAŞI", "REELow"])

    def test_b2b_schema_and_evaluation(self):
        ok = dict(GOOD, b2b=[{"artists": ["JAMIE JONES", "JOSEPH CAPRIATI"], "text": "JAMIE JONES B2B JOSEPH CAPRIATI"}])
        self.assertEqual(validate(ok), [])
        errs = " ".join(validate(dict(GOOD, b2b=[{"artists": ["SOLO"], "order": 1}])))
        for frag in ("b2b[0].artists", "order"):
            self.assertIn(frag, errs)
        ref = [{"artists": ["CUKY", "PERSIC"], "text": "CUKY B2B PERSIC"},
               {"artists": ["ROBER PEINADO", "GABI"], "text": "ROBER PEINADO B2B GABI"}]
        pred = [{"artists": ["Persic", "Cuky"], "text": None},          # el orden no se evalúa
                {"artists": ["MAHONY", "KIDOO"], "text": "MAHONY B2B KIDOO"}]
        r = EV.compare_b2b(pred, ref)
        self.assertEqual((r["correct"], r["missing"], r["extra"]), (1, ["ROBER PEINADO B2B GABI"], ["MAHONY B2B KIDOO"]))
        # un B2B sin separar en artists cuenta como inventado y sus miembros como omitidos
        m = EV.match_artists([{"name": "CUKY B2B PERSIC", "uncertain": False}], [{"name": "CUKY"}, {"name": "PERSIC"}])
        self.assertEqual((m["correct"], len(m["invented"]), m["omitted"]), (0, 1, ["CUKY", "PERSIC"]))


if __name__ == "__main__":
    unittest.main()
