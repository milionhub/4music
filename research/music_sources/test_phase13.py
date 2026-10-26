"""Pruebas offline de los módulos de la Fase 1.3 (sin red externa).

    py -3.11 -m unittest research/music_sources/test_phase13.py
"""

import json
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import acousticbrainz as AB  # noqa: E402
import discogs as DG  # noqa: E402
from http_client import HttpClient  # noqa: E402
from run_phase13 import _base_name, artist_in, track_match  # noqa: E402

FAKE_TOKEN = "FAKE-TOKEN-0123456789abcdef"
SEEN_AUTH: list[str] = []


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        SEEN_AUTH.append(self.headers.get("Authorization", ""))
        remaining = "2" if self.path.startswith("/low") else "50"
        body = json.dumps({"id": 1, "title": "X", "images": [{"uri": "img"}], "lowest_price": 9.5,
                           "community": {"have": 3}, "tracklist": [{"title": "A", "extraartists": []}],
                           "styles": ["Deep House"]}).encode()
        self.send_response(200)
        self.send_header("X-Discogs-Ratelimit-Remaining", remaining)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class Phase13Test(unittest.TestCase):
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
        pol = DG.policy(FAKE_TOKEN, "test-agent/0", max_requests=5)
        pol.min_interval_s, pol.cooldown_s = 0.0, 0.2
        self.client.register(pol)

    def test_token_sent_in_header_only_and_never_stored(self):
        res = self.client.get_json("discogs", self.base + "/release")
        self.assertTrue(res.ok)
        self.assertIn(f"Discogs token={FAKE_TOKEN}", SEEN_AUTH[-1])
        self.assertNotIn(FAKE_TOKEN, res.url)
        stored = "".join(p.read_text(encoding="utf-8") for p in self.tmp.rglob("*") if p.is_file())
        self.assertNotIn(FAKE_TOKEN, stored)
        self.assertNotIn(FAKE_TOKEN, repr(self.client.policies["discogs"]))

    def test_restricted_fields_removed_before_cache(self):
        res = self.client.get_json("discogs", self.base + "/release2")
        cached = json.loads((self.tmp / res.cache_file).read_text(encoding="utf-8"))["body"]
        for key in ("images", "lowest_price", "community"):
            self.assertNotIn(key, cached)
            self.assertNotIn(key, res.data)
        self.assertEqual(cached["styles"], ["Deep House"])

    def test_ratelimit_header_logged_and_cooldown(self):
        self.client.get_json("discogs", self.base + "/low1")
        self.assertIn("discogs", self.client.cooldown_until)  # quedan <= 3: pausa antes de la siguiente
        log = (self.tmp / "log.jsonl").read_text(encoding="utf-8")
        self.assertIn("X-Discogs-Ratelimit-Remaining", log)
        self.assertNotIn("Authorization", log)

    def test_matching_helpers(self):
        self.assertEqual(track_match("Breather", "breather"), "exact")
        self.assertEqual(track_match("On 2nite (Extended Mix)", "On 2nite"), "base_title_plus_version")
        self.assertEqual(track_match("Breathe", "Breather"), "different")
        self.assertEqual(_base_name("Blaze (2)"), "blaze")
        self.assertTrue(artist_in("Chris Stassy & S.A.M.", "Chris Stassy"))
        self.assertTrue(artist_in("Mochakk (2)", "Mochakk"))
        self.assertFalse(artist_in("Chris Stassy", "Chris Stassy"))

    def test_acousticbrainz_bulk_limit(self):
        with self.assertRaises(ValueError):
            AB._ids([])
        with self.assertRaises(ValueError):
            AB._ids([f"id{i}" for i in range(AB.MAX_BULK + 1)])
        self.assertEqual(AB._ids(["b", "a"]), "a;b")

    def test_acousticbrainz_summaries(self):
        low = AB.summarize_low({"rhythm": {"bpm": 124.2}, "tonal": {"key_key": "A", "key_scale": "minor"}})
        self.assertEqual((low["bpm"], low["key"], low["scale"]), (124.2, "A", "minor"))
        high = AB.summarize_high({"highlevel": {"genre_electronic": {"value": "house", "probability": 0.6}}})
        self.assertEqual(high["genre_models"]["genre_electronic"]["value"], "house")


if __name__ == "__main__":
    unittest.main()
