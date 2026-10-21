"""Almacén persistente ligero (SQLite de la biblioteca estándar) para biografías y fotos resueltas por MBID.

Archivo: backend/data/artist_intel.sqlite3 (fuera de Git; ARTIST_DB_PATH lo cambia, p. ej. en pruebas).
Cada registro guarda su caducidad: así no se regenera en cada visita y los fallos no se reintentan en bucle.
"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any

DEFAULT_PATH = Path(__file__).resolve().parent.parent / "data" / "artist_intel.sqlite3"
_lock = threading.Lock()


def _path() -> Path:
    return Path(os.environ.get("ARTIST_DB_PATH") or DEFAULT_PATH)


def _connect() -> sqlite3.Connection:
    path = _path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=5)
    conn.execute("CREATE TABLE IF NOT EXISTS records (kind TEXT NOT NULL, mbid TEXT NOT NULL, payload TEXT NOT NULL,"
                 " stored_at REAL NOT NULL, expires_at REAL NOT NULL, PRIMARY KEY (kind, mbid))")
    return conn


def get(kind: str, mbid: str) -> dict[str, Any] | None:
    """Registro vigente o None (caducado o inexistente)."""
    with _lock:
        try:
            conn = _connect()
            try:
                row = conn.execute("SELECT payload, expires_at FROM records WHERE kind = ? AND mbid = ?",
                                   (kind, mbid)).fetchone()
            finally:
                conn.close()
        except sqlite3.Error:
            return None
    if not row or row[1] < time.time():
        return None
    try:
        value = json.loads(row[0])
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, dict) else None


def delete(kind: str, mbid: str) -> bool:
    """Borra un registro concreto (regeneración selectiva). Nunca vacía la caché completa."""
    with _lock:
        try:
            conn = _connect()
            try:
                cur = conn.execute("DELETE FROM records WHERE kind = ? AND mbid = ?", (kind, mbid))
                conn.commit()
                return cur.rowcount > 0
            finally:
                conn.close()
        except sqlite3.Error:
            return False


def put(kind: str, mbid: str, payload: dict[str, Any], ttl_s: float) -> None:
    now = time.time()
    with _lock:
        try:
            conn = _connect()
            try:
                conn.execute("INSERT OR REPLACE INTO records (kind, mbid, payload, stored_at, expires_at)"
                             " VALUES (?, ?, ?, ?, ?)", (kind, mbid, json.dumps(payload, ensure_ascii=False), now, now + ttl_s))
                conn.commit()
            finally:
                conn.close()
        except sqlite3.Error:
            pass  # sin almacén persistente la app sigue funcionando (solo se pierde la reutilización)
