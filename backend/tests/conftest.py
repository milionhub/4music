"""Aislamiento: cada prueba usa su propio almacén SQLite y nunca la web oficial real de un artista."""

import pytest

from app import acousticbrainz, biography, reccobeats, sources


@pytest.fixture(autouse=True)
def _isolated_store(tmp_path, monkeypatch):
    monkeypatch.setenv("ARTIST_DB_PATH", str(tmp_path / "artist_intel.sqlite3"))
    monkeypatch.setenv("DISCOGS_DB_PATH", str(tmp_path / "discogs.sqlite3"))  # sin índice salvo que la prueba lo cree
    monkeypatch.setattr(sources, "official_site_text", lambda url, ua: None)
    monkeypatch.setattr(acousticbrainz, "_default_transport", lambda url: {})  # nunca la API real en las pruebas
    monkeypatch.setattr(reccobeats, "_default_transport", lambda url: {})
    monkeypatch.setattr(biography, "_cooldown_until", 0.0)  # la pausa tras un 429 no pasa de una prueba a otra
