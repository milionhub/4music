"""Catálogo editorial local (app/data/editorial.json), indexado por MBID: biografías originales verificadas
y fotografías con permiso documentado. Sin administración: se edita a mano y se revisa en Git."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

CATALOG = Path(__file__).resolve().parent / "data" / "editorial.json"


@lru_cache
def _load(path: str = str(CATALOG)) -> dict[str, Any]:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data.get("artists", {}) if isinstance(data, dict) and data.get("version") == 1 else {}


def entry(mbid: str) -> dict[str, Any]:
    value = _load().get(mbid)
    return value if isinstance(value, dict) else {}


def bio(mbid: str) -> dict[str, Any] | None:
    b = entry(mbid).get("bio")
    if isinstance(b, dict) and isinstance(b.get("text"), str) and b["text"].strip() and b.get("sources"):
        return b
    return None  # sin fuentes no se publica una biografía editorial


def photo(mbid: str) -> dict[str, Any] | None:
    p = entry(mbid).get("photo")
    required = ("url", "author", "license", "permission")
    if isinstance(p, dict) and all(isinstance(p.get(k), str) and p[k].strip() for k in required) \
            and p["url"].startswith("https://"):
        return p
    return None  # una foto sin permiso documentado no se muestra
