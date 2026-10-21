"""Clientes HTTP sin red: límite de ritmo, caché con TTL, copia caducada y un único reintento ante 503/429."""

import json

import pytest

from app import musicbrainz
from app.musicbrainz import MusicBrainzClient, NotFound, Unavailable


class Clock:
    def __init__(self):
        self.t = 1000.0
        self.sleeps: list[float] = []

    def __call__(self):
        return self.t

    def sleep(self, s):
        self.sleeps.append(round(s, 3))
        self.t += s


def client_with(responses, clock):
    calls = []

    def transport(url, headers, timeout):
        calls.append(url)
        status, body, *rest = responses.pop(0)
        if isinstance(status, Exception):
            raise status
        return status, json.dumps(body).encode(), rest[0] if rest else None

    return MusicBrainzClient("c@example.org", transport=transport, clock=clock, sleep=clock.sleep), calls


def test_rate_limit_spaces_consecutive_requests():
    clock = Clock()
    c, calls = client_with([(200, {"artists": []}), (200, {"artists": []})], clock)
    c.search_artists("a", 5)
    clock.t += 0.3
    c.search_artists("b", 5)
    assert len(calls) == 2 and clock.sleeps == [0.8]  # 1,1 s mínimos entre peticiones


def test_cache_hit_then_stale_on_failure():
    clock = Clock()
    c, calls = client_with([(200, {"id": "x", "name": "N"}), (503, None), (503, None)], clock)
    first = c.artist("x")
    assert c.artist("x") is first and len(calls) == 1  # dentro del TTL: sin red
    clock.t += musicbrainz.CACHE_TTL_S + 1
    stale = c.artist("x")
    assert stale.stale is True and stale.data == first.data and len(calls) == 3  # petición + 1 reintento


def test_single_polite_retry_on_503_honours_retry_after():
    clock = Clock()
    c, calls = client_with([(503, None, 2.0), (200, {"id": "x", "name": "N"})], clock)
    assert c.artist("x").data["name"] == "N"
    assert len(calls) == 2 and clock.sleeps[0] == 2.0
    clock = Clock()
    c, calls = client_with([(429, None, 60.0), (503, None)], clock)
    with pytest.raises(Unavailable):
        c.artist("y")
    assert len(calls) == 2 and clock.sleeps[0] == musicbrainz.RETRY_MAX_WAIT_S  # espera acotada, solo 1 reintento


def test_errors_without_cache_are_not_retried_except_503():
    clock = Clock()
    c, calls = client_with([(404, None), (OSError("down"), None), (500, None)], clock)
    with pytest.raises(NotFound):
        c.artist("b")
    with pytest.raises(Unavailable):
        c.artist("c")
    with pytest.raises(Unavailable):
        c.artist("d")
    assert len(calls) == 3  # 404, error de red y 500: una sola petición cada uno
