"""Nombres artísticos nuevos que MusicBrainz aún no recoge (corrección editorial, por MBID, nunca por parecido).

Se aplican a toda respuesta de MusicBrainz antes de usarla (fichas, créditos, búsquedas): la app muestra el nombre
actual. En las búsquedas, el nombre nuevo se traduce al que MusicBrainz conoce para que el artista se encuentre.
Cada entrada lleva su procedencia; cuando MusicBrainz lo actualice, sobra y se borra.
"""

from __future__ import annotations

import re
from typing import Any

# MBID → (nombre que tiene en MusicBrainz, nombre actual, procedencia)
RENAMES: dict[str, tuple[str, str, str]] = {
    "5b7f4511-1764-4d80-83b5-8c150f4636c5": (
        "Chris Stussy", "Chris Stassy",
        "Nombre actual del artista (así figura ya en Deezer: «CHRIS STASSY»); indicado por el usuario el 2026-10-25."),
}
_BY_ID = {mbid: new for mbid, (_old, new, _src) in RENAMES.items()}
_QUERY = [(re.compile(rf"\b{re.escape(new)}\b", re.IGNORECASE), old) for old, new, _src in RENAMES.values()]


def apply(data: Any) -> Any:
    """Copia de la respuesta con los nombres actuales: entidades {id, name} y créditos {name, artist: {id}}."""
    if isinstance(data, list):
        return [apply(x) for x in data]
    if not isinstance(data, dict):
        return data
    out = {k: apply(v) for k, v in data.items()}
    new = _BY_ID.get(out.get("id")) if isinstance(out.get("id"), str) else None
    if new and isinstance(out.get("name"), str):
        old_name = out["name"]
        out["name"] = new
        if isinstance(out.get("sort-name"), str):
            out["sort-name"] = new
        # El nombre antiguo sigue siendo suyo: como alias, un cartel o un crédito que lo imprime se reconoce (V6.8).
        aliases = out.get("aliases") if isinstance(out.get("aliases"), list) else []
        if old_name.casefold() != new.casefold() and not any(
                isinstance(x, dict) and str(x.get("name", "")).casefold() == old_name.casefold() for x in aliases):
            out["aliases"] = [*aliases, {"name": old_name, "sort-name": old_name, "type": "Artist name", "primary": None}]
    artist = out.get("artist")
    credited = _BY_ID.get(artist.get("id")) if isinstance(artist, dict) and isinstance(artist.get("id"), str) else None
    if credited and isinstance(out.get("name"), str):
        old = RENAMES[artist["id"]][0]
        if out["name"].casefold() == old.casefold():  # el nombre acreditado es el antiguo (no un alias distinto)
            out["name"] = credited
    if isinstance(out.get("artist-credit-phrase"), str):
        for mbid, (old, new_name, _src) in RENAMES.items():
            out["artist-credit-phrase"] = re.sub(re.escape(old), new_name, out["artist-credit-phrase"], flags=re.IGNORECASE)
    return out


def is_former(mbid: str | None, name: str | None) -> bool:
    """`name` es el nombre anterior del artista `mbid` (para decirlo así y no como un alias cualquiera)."""
    entry = RENAMES.get(mbid or "")
    return bool(entry and name and entry[0].casefold() == name.casefold())


def query(text: str) -> str:
    """Búsqueda con el nombre nuevo → con el que MusicBrainz conoce («Chris Stassy Desire» → «Chris Stussy Desire»)."""
    for pattern, old in _QUERY:
        text = pattern.sub(old, text)
    return text


_TEXT = [(re.compile(rf"\b{re.escape(old)}\b", re.IGNORECASE), new) for old, new, _src in RENAMES.values()]


def text(body: str) -> str:
    """Nombre antiguo → actual en un texto ya compuesto (historias, biografías, títulos como «X (Chris Stussy Remix)»
    y lo guardado en caché antes del cambio). Respeta las mayúsculas: «CHRIS STUSSY» → «CHRIS STASSY»."""
    for pattern, new in _TEXT:
        body = pattern.sub(lambda m: new.upper() if m.group(0).isupper() else new, body)
    return body
