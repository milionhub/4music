"""Discogs: perfiles de artista desde el índice local de los volcados oficiales CC0 (ver app/discogs_dump.py).

- Identidad: únicamente el ID de Discogs que MusicBrainz enlaza al MBID (`wikidata.discogs_ids`), y solo si el nombre
  del artista coincide con el de Discogs o con una de sus variantes. Nunca se busca por nombre.
- Campos: nombre, notas del perfil, integrantes y grupos (CC0). Sin nombre real, contactos, enlaces ni imágenes.
- Las referencias del perfil a otros artistas o sellos ([a123], [l123]) se resuelven con el mismo índice, sin red.
- Sin índice (no construido o ilegible), el pipeline sigue con las demás fuentes: aquí nada lanza excepciones.
"""

from __future__ import annotations

import json
import os
import re
import sqlite3
import unicodedata
import zlib
from pathlib import Path
from typing import Callable

from app.sources import SourceDoc

SITE = "https://www.discogs.com"
LICENSE = "CC0"
PROFILE_LABEL = "Discogs (perfil)"
RELATIONS_LABEL = "Discogs (relaciones)"
LABEL_LABEL = "Discogs (sello)"
DEFAULT_INDEX = Path(__file__).resolve().parent.parent / "data" / "discogs.sqlite3"
MAX_REF_LOOKUPS = 3  # referencias numéricas que se resuelven por perfil

# Marcado de presentación de Discogs: [a=Nombre], [l=Nombre], [a123], [l123], [r123], [m123], [url=…]texto[/url],
# [b]…[/b], [i]…[/i], [u]…[/u], [g…] (guías de estilo).
NAMED_REF_RE = re.compile(r"\[(?:a|l)=([^\]]+)\]")
ID_REF_RE = re.compile(r"\[(a|l|r|m)(\d+)\]")
URL_RE = re.compile(r"\[url=[^\]]*\](.*?)\[/url\]", re.IGNORECASE | re.DOTALL)
STYLE_RE = re.compile(r"\[/?(?:b|i|u)\]|\[g[^\]]*\]", re.IGNORECASE)
SUFFIX_RE = re.compile(r"\s+\(\d+\)$")  # «Hellbent Records (2)»: número de desambiguación de Discogs
SENTENCE_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9«\"“(])")


def clean_name(name: str) -> str:
    return SUFFIX_RE.sub("", name.strip())


def _key(name: str) -> str:
    plain = "".join(c for c in unicodedata.normalize("NFKD", clean_name(name)) if not unicodedata.combining(c))
    return re.sub(r"\W+", "", plain.casefold())


def normalize_profile(text: str, resolve: Callable[[str, str], str | None] | None = None) -> str:
    """Notas del perfil sin marcado de presentación. No se reescribe nada: «[l=Hellbent Records (2)]» → «Hellbent
    Records». Una referencia numérica se sustituye por su nombre si `resolve(tipo, id)` lo conoce; si no, la frase
    se descarta entera (quitar solo la referencia cambiaría lo que dice)."""
    text = URL_RE.sub(lambda m: m.group(1), text.replace("\r", " "))
    text = STYLE_RE.sub("", text)
    text = NAMED_REF_RE.sub(lambda m: clean_name(m.group(1)), text)
    kept, lookups = [], 0
    for sentence in SENTENCE_RE.split(re.sub(r"\s+", " ", text).strip()):
        unresolved = False

        def name_for(m: re.Match) -> str:
            nonlocal unresolved, lookups
            name = None
            if resolve and m.group(1) in ("a", "l") and lookups < MAX_REF_LOOKUPS:
                lookups += 1
                name = resolve(m.group(1), m.group(2))
            if not name:
                unresolved = True
                return ""
            return clean_name(name)

        sentence = ID_REF_RE.sub(name_for, sentence)
        if sentence and not unresolved:
            kept.append(sentence)
    return " ".join(kept).strip()


class DiscogsIndex:
    """Lector del índice local (solo lectura). `available` es False si no se ha construido."""

    def __init__(self, path: str | Path | None = None):
        self.path = Path(path or os.environ.get("DISCOGS_DB_PATH") or DEFAULT_INDEX)

    @property
    def available(self) -> bool:
        return self.path.is_file()

    def _row(self, sql: str, args: tuple) -> tuple | None:
        if not self.available:
            return None
        try:
            conn = sqlite3.connect(f"file:{self.path.as_posix()}?mode=ro", uri=True, timeout=5)
            try:
                return conn.execute(sql, args).fetchone()
            finally:
                conn.close()
        except sqlite3.Error:
            return None

    def artist(self, discogs_id: str) -> dict | None:
        # `sites` solo existe en índices construidos desde la v4: con uno anterior, la consulta básica.
        row = (self._row("SELECT id, name, variations, profile, members, groups, sites FROM artist WHERE id = ?",
                         (int(discogs_id),))
               or self._row("SELECT id, name, variations, profile, members, groups, NULL FROM artist WHERE id = ?",
                            (int(discogs_id),)))
        if not row:
            return None
        ident, name, variations, profile, members, groups, sites = row
        return {"id": str(ident), "name": clean_name(name), "variations": json.loads(variations or "[]"),
                "profile": zlib.decompress(profile).decode() if profile else "",
                "members": [clean_name(n) for _i, n in json.loads(members or "[]")],
                "groups": [clean_name(n) for _i, n in json.loads(groups or "[]")],
                "sites": json.loads(sites or "[]")}

    def label(self, label_id: str) -> dict | None:
        """Sello por ID: nombre y notas del perfil (CC0). Nunca datos de contacto (no están en el índice)."""
        row = self._row("SELECT id, name, profile FROM label WHERE id = ?", (int(label_id),))
        if not row:
            return None
        ident, name, profile = row
        return {"id": str(ident), "name": clean_name(name), "profile": zlib.decompress(profile).decode() if profile else ""}

    def label_by_name(self, name: str) -> dict | None:
        """Sello por nombre exacto de Discogs, solo si es único (con «(2)» Discogs distingue homónimos)."""
        if not self.available:
            return None
        try:
            conn = sqlite3.connect(f"file:{self.path.as_posix()}?mode=ro", uri=True, timeout=5)
            try:
                rows = conn.execute("SELECT id FROM label WHERE name = ? LIMIT 2", (name,)).fetchall()
            finally:
                conn.close()
        except sqlite3.Error:
            return None
        return self.label(str(rows[0][0])) if len(rows) == 1 else None

    def name(self, kind: str, ref_id: str) -> str | None:
        row = self._row(f"SELECT name FROM {'artist' if kind == 'a' else 'label'} WHERE id = ?", (int(ref_id),))
        return clean_name(row[0]) if row else None

    def meta(self) -> dict[str, str]:
        if not self.available:
            return {}
        try:
            conn = sqlite3.connect(f"file:{self.path.as_posix()}?mode=ro", uri=True, timeout=5)
            try:
                return dict(conn.execute("SELECT key, value FROM meta").fetchall())
            finally:
                conn.close()
        except sqlite3.Error:
            return {}


def same_artist(artist: dict, name: str) -> bool:
    """Comprobación de identidad: el enlace de MusicBrainz apunta a un registro con ese nombre o esa variante."""
    key = _key(name)
    return bool(key) and key in {_key(artist["name"]), *(_key(v) for v in artist["variations"])}


def artist_docs(index: DiscogsIndex, discogs_id: str, name: str, with_members: bool = True,
                with_groups: bool = True) -> list[SourceDoc]:
    """Perfil (texto descriptivo) y relaciones (campos) de un artista de Discogs, con procedencia y licencia CC0.
    Integrantes y grupos solo completan lo que MusicBrainz no tenga (`with_members`/`with_groups`): un grupo
    secundario repetido no debe ocupar el sitio de hechos más distintivos."""
    artist = index.artist(discogs_id)
    if not artist or not same_artist(artist, name):
        return []
    url = f"{SITE}/artist/{artist['id']}"
    docs = []
    profile = normalize_profile(artist["profile"], index.name)
    if profile:
        docs.append(SourceDoc("", PROFILE_LABEL, url, LICENSE, profile))
    fields = []
    if with_members and artist["members"]:
        fields.append(f"Integrantes: {', '.join(artist['members'][:6])}.")
    if with_groups and artist["groups"]:
        fields.append(f"Miembro de: {', '.join(artist['groups'][:4])}.")
    if fields:
        docs.append(SourceDoc("", RELATIONS_LABEL, url, LICENSE, " ".join(fields)))
    return docs


LABEL_REF_RE = re.compile(r"\[l(\d+)\]|\[l=([^\]]+)\]")
MAX_LABEL_PROFILES = 2


def linked_label_docs(index: DiscogsIndex, discogs_id: str, name: str) -> list[SourceDoc]:
    """Perfiles (CC0) de los sellos que el perfil del propio artista enlaza ([l123] o [l=Nombre]): identidad
    inequívoca, sin buscar sellos por coincidencia de nombre libre. «Atipic: Independent vinyl only romanian record
    label run by Adrian Niculae. Founded in Bucharest.» Cada sello, su propio documento con su URL."""
    artist = index.artist(discogs_id)
    if not artist or not same_artist(artist, name):
        return []
    docs = []
    for m in LABEL_REF_RE.finditer(artist["profile"]):
        label = index.label(m.group(1)) if m.group(1) else index.label_by_name(m.group(2).strip())
        if not label or not label["profile"] or any(d.url.endswith(f"/label/{label['id']}") for d in docs):
            continue
        text = normalize_profile(label["profile"], index.name)
        if text:
            docs.append(SourceDoc("", f"{LABEL_LABEL}: {label['name']}", f"{SITE}/label/{label['id']}", LICENSE,
                                  f"{label['name']}: {text}"))
        if len(docs) == MAX_LABEL_PROFILES:
            break
    return docs


def own_sites(index: DiscogsIndex, discogs_id: str, name: str) -> list[str]:
    """Webs propias del artista según Discogs (sin redes ni tiendas), tras comprobar la identidad."""
    artist = index.artist(discogs_id)
    return artist["sites"] if artist and same_artist(artist, name) else []
