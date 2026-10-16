"""Pruebas offline del cliente HTTP (servidor local, sin tocar APIs externas).

    py -3.11 -m unittest research/music_sources/test_http_client.py
"""

import json
import sys
import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from http_client import BudgetExceeded, HttpClient, SourcePolicy  # noqa: E402

CALLS: dict[str, int] = {}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        CALLS[self.path] = CALLS.get(self.path, 0) + 1
        if self.path.startswith("/ok"):
            self._send(200, json.dumps({"ok": True}).encode())
        elif self.path == "/notjson":
            self._send(200, b"<html>no</html>")
        elif self.path == "/404":
            self._send(404, b'{"error": "not found"}')
        elif self.path == "/flaky":  # 503 con Retry-After la primera vez
            if CALLS[self.path] == 1:
                self._send(503, b"", {"Retry-After": "0"})
            else:
                self._send(200, b'{"recovered": true}')
        elif self.path == "/slow":
            time.sleep(1.5)
            self._send(200, b"{}")

    def _send(self, code, body, headers=None):
        self.send_response(code)
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        try:
            self.wfile.write(body)
        except ConnectionError:  # el cliente ya cortó por timeout (esperado en /slow)
            pass


class HttpClientTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        cls.base = f"http://127.0.0.1:{cls.server.server_port}"
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.client = HttpClient(self.tmp / "raw", self.tmp / "log.jsonl")
        self.client.register(SourcePolicy("t", min_interval_s=0.3, max_requests=10, timeout_s=0.5,
                                          headers={"Authorization": "Token SECRETO"}))

    def test_ok_cached_and_not_repeated(self):
        first = self.client.get_json("t", self.base + "/ok1")
        second = self.client.get_json("t", self.base + "/ok1")
        self.assertTrue(first.ok and not first.from_cache)
        self.assertTrue(second.ok and second.from_cache)
        self.assertEqual(CALLS["/ok1"], 1)

    def test_invalid_json_and_http_error(self):
        bad = self.client.get_json("t", self.base + "/notjson")
        self.assertFalse(bad.ok)
        self.assertIn("no JSON", bad.error)
        missing = self.client.get_json("t", self.base + "/404")
        self.assertEqual((missing.ok, missing.status), (False, 404))

    def test_retry_after_503(self):
        res = self.client.get_json("t", self.base + "/flaky")
        self.assertTrue(res.ok)
        self.assertEqual(res.data, {"recovered": True})

    def test_timeout_is_reported_not_raised(self):
        res = self.client.get_json("t", self.base + "/slow")
        self.assertFalse(res.ok)
        self.assertIsNone(res.status)
        self.assertIn("red", res.error)

    def test_rate_limit_and_budget(self):
        self.client.policies["t"].max_requests = 3
        started = time.monotonic()
        for i in range(3):
            self.client.get_json("t", self.base + f"/ok-rate{i}")
        self.assertGreaterEqual(time.monotonic() - started, 0.6)  # 2 esperas de 0.3 s
        with self.assertRaises(BudgetExceeded):
            self.client.get_json("t", self.base + "/ok-rate-extra")

    def test_log_never_contains_headers(self):
        self.client.get_json("t", self.base + "/ok-log")
        self.assertNotIn("SECRETO", (self.tmp / "log.jsonl").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
