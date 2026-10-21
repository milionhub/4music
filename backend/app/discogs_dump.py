"""Índice local de los volcados oficiales de Discogs (artistas y sellos), publicados bajo CC0 en data.discogs.com.

Uso (desde backend/, con el entorno virtual):
    python -m app.discogs_dump fetch 20261001   # descarga artistas y sellos a data/discogs/ y verifica el SHA-256
    python -m app.discogs_dump build 20261001   # construye data/discogs.sqlite3 en streaming y lo sustituye

- Licencia: «This data is made available under the CC0 No Rights Reserved license» (https://data.discogs.com/).
  Los términos de la API (6 horas, caché, avisos) se refieren al contenido servido por la API, no a los volcados.
- Solo se guarda lo que usan los perfiles: nombre, variantes del nombre (para comprobar la identidad), notas del
  perfil (comprimidas, sin normalizar), integrantes y grupos; de los sellos, nombre y sello matriz. Nunca el nombre
  real, los datos de contacto, los enlaces ni imágenes (los volcados no las incluyen).
- Memoria constante: `iterparse` registro a registro y limpieza del árbol tras cada uno; escritura por lotes.
- El índice nuevo se construye en un archivo temporal y sustituye al anterior de forma atómica: el backend, que lo
  abre en solo lectura en cada consulta, no necesita reiniciarse.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import shutil
import sqlite3
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
import zlib
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DUMP_DIR = DATA_DIR / "discogs"
INDEX_PATH = DATA_DIR / "discogs.sqlite3"
DOWNLOAD_URL = "https://data.discogs.com/?download=data%2F{year}%2F{name}"
FILES = ("artists", "labels")
USER_AGENT = "music-discovery/0.1 (Discogs CC0 data dump import; portfolio project)"
MIN_FREE_BYTES = 5 * 1024 ** 3   # descarga (~0,6 GB) + índice (~1 GB) con margen
BATCH = 10_000
MAX_VARIATIONS, MAX_RELATIONS = 20, 20
# Dominios que no son la web propia de un artista: redes, tiendas, plataformas y bases de datos.
NOT_OWN_SITES = ("facebook.com", "instagram.com", "twitter.com", "x.com", "soundcloud.com", "youtube.com", "youtu.be",
                 "bandcamp.com", "residentadvisor.net", "ra.co", "spotify.com", "discogs.com", "myspace.com",
                 "tiktok.com", "linktr.ee", "beatport.com", "apple.com", "deezer.com", "mixcloud.com", "wikipedia.org",
                 "last.fm", "tidal.com", "traxsource.com", "juno.co.uk", "threads.net", "allmusic.com", "songkick.com",
                 "bit.ly", "vk.com", "twitch.tv", "patreon.com", "boomkat.com", "decks.de", "hardwax.com")
SCHEMA = """
CREATE TABLE artist (id INTEGER PRIMARY KEY, name TEXT NOT NULL, variations TEXT, profile BLOB, members TEXT,
                     groups TEXT, sites TEXT);
CREATE TABLE label (id INTEGER PRIMARY KEY, name TEXT NOT NULL, parent_id INTEGER, profile BLOB);
CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
"""


def _file(date: str, name: str) -> str:
    return f"discogs_{date}_{name}" + (".txt" if name == "CHECKSUM" else ".xml.gz")


def _get(url: str):
    return urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": USER_AGENT}), timeout=60)


def checksums(date: str) -> dict[str, str]:
    """SHA-256 oficiales del mes (archivo CHECKSUM.txt publicado junto a los volcados)."""
    with _get(DOWNLOAD_URL.format(year=date[:4], name=_file(date, "CHECKSUM"))) as resp:
        lines = resp.read().decode().split("\n")
    return {parts[1]: parts[0] for parts in (line.split() for line in lines) if len(parts) == 2}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def fetch(date: str, dump_dir: Path = DUMP_DIR) -> None:
    """Descarga artistas y sellos una sola vez: si el archivo ya existe con el SHA-256 oficial, no se repite."""
    dump_dir.mkdir(parents=True, exist_ok=True)
    if shutil.disk_usage(dump_dir).free < MIN_FREE_BYTES:
        raise SystemExit(f"Espacio libre insuficiente en {dump_dir} (mínimo {MIN_FREE_BYTES // 1024 ** 3} GB)")
    expected = checksums(date)
    for name in FILES:
        filename = _file(date, name)
        target = dump_dir / filename
        if filename not in expected:
            raise SystemExit(f"{filename} no aparece en el CHECKSUM oficial de {date}")
        if target.exists() and _sha256(target) == expected[filename]:
            print(f"{filename}: ya descargado y verificado")
            continue
        part, digest, size, started = target.with_suffix(".part"), hashlib.sha256(), 0, time.time()
        with _get(DOWNLOAD_URL.format(year=date[:4], name=filename)) as resp, open(part, "wb") as out:
            for chunk in iter(lambda: resp.read(1 << 20), b""):
                out.write(chunk)
                digest.update(chunk)
                size += len(chunk)
        if digest.hexdigest() != expected[filename]:
            part.unlink()
            raise SystemExit(f"{filename}: el SHA-256 no coincide con el oficial; descarga descartada")
        os.replace(part, target)
        print(f"{filename}: {size / 1024 ** 2:.1f} MB en {time.time() - started:.0f} s, SHA-256 verificado")


def _records(path: Path, tag: str):
    """Elementos `tag` de primer nivel, uno a uno, liberando cada registro tras leerlo."""
    with gzip.open(path, "rb") as fh:
        context = ET.iterparse(fh, events=("start", "end"))
        _event, root = next(context)
        for event, elem in context:
            if event == "end" and elem.tag == tag and len(elem):
                yield elem
                root.clear()


def _names(elem: ET.Element, path: str, limit: int) -> list:
    return [[int(n.get("id")), n.text.strip()] for n in elem.findall(path)[:limit] if n.get("id") and n.text]


def _artist_row(elem: ET.Element) -> tuple | None:
    ident, name = elem.findtext("id"), (elem.findtext("name") or "").strip()
    if not ident or not name:
        return None
    profile = (elem.findtext("profile") or "").strip()
    variations = [n.text.strip() for n in elem.findall("namevariations/name")[:MAX_VARIATIONS] if n.text]
    members, groups = _names(elem, "members/name", MAX_RELATIONS), _names(elem, "groups/name", MAX_RELATIONS)
    sites = [u for u in (n.text.strip() for n in elem.findall("urls/url") if n.text) if _own_site(u)][:3]
    useful = bool(profile or members or groups)
    # Todos los artistas conservan su nombre (resuelve referencias [a123] de otros perfiles); el resto solo si aporta.
    return (int(ident), name, json.dumps(variations, ensure_ascii=False) if useful and variations else None,
            zlib.compress(profile.encode(), 6) if profile else None,
            json.dumps(members, ensure_ascii=False) if members else None,
            json.dumps(groups, ensure_ascii=False) if groups else None,
            json.dumps(sites) if useful and sites else None)


def _own_site(url: str) -> bool:
    """Web propia del artista (no redes, tiendas ni plataformas), para el texto descriptivo de su web oficial."""
    try:
        host = urllib.parse.urlsplit(url).netloc.lower().removeprefix("www.")
    except ValueError:  # URL malformada en el volcado
        return False
    return url.startswith(("http://", "https://")) and bool(host) and not any(
        host == d or host.endswith("." + d) for d in NOT_OWN_SITES)


def _label_row(elem: ET.Element) -> tuple | None:
    ident, name = elem.findtext("id"), (elem.findtext("name") or "").strip()
    parent = elem.find("parentLabel")
    if not ident or not name:
        return None
    profile = (elem.findtext("profile") or "").strip()  # notas del sello (CC0); los datos de contacto, nunca
    return (int(ident), name, int(parent.get("id")) if parent is not None and parent.get("id") else None,
            zlib.compress(profile.encode(), 6) if profile else None)


def build(date: str, dump_dir: Path = DUMP_DIR, index_path: Path = INDEX_PATH) -> None:
    sources = {name: dump_dir / _file(date, name) for name in FILES}
    missing = [str(p) for p in sources.values() if not p.exists()]
    if missing:
        raise SystemExit(f"Faltan volcados: {missing}. Ejecuta antes «fetch {date}».")
    tmp = index_path.with_suffix(".building")
    tmp.unlink(missing_ok=True)
    conn = sqlite3.connect(tmp)
    conn.executescript("PRAGMA journal_mode=OFF; PRAGMA synchronous=OFF;" + SCHEMA)
    started, counts = time.time(), {}
    for name, table, tag, row_of in (("labels", "label", "label", _label_row), ("artists", "artist", "artist", _artist_row)):
        placeholders = ",".join("?" * (4 if table == "label" else 7))
        batch, total = [], 0
        for elem in _records(sources[name], tag):
            row = row_of(elem)
            if row:
                batch.append(row)
            if len(batch) >= BATCH:
                conn.executemany(f"INSERT OR REPLACE INTO {table} VALUES ({placeholders})", batch)
                total += len(batch)
                batch = []
                if total % 1_000_000 == 0:
                    print(f"  {table}: {total:,} filas ({time.time() - started:.0f} s)", flush=True)
        conn.executemany(f"INSERT OR REPLACE INTO {table} VALUES ({placeholders})", batch)
        counts[table] = total + len(batch)
    meta = {"dump_date": date, "license": "CC0", "source": "https://data.discogs.com/",
            "files": json.dumps({n: p.name for n, p in sources.items()}),
            "sha256": json.dumps({n: _sha256(p) for n, p in sources.items()}),
            "counts": json.dumps(counts), "built_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "build_seconds": str(round(time.time() - started))}
    conn.executemany("INSERT INTO meta VALUES (?, ?)", meta.items())
    conn.commit()
    if not counts.get("artist") or not counts.get("label"):
        conn.close()
        tmp.unlink()
        raise SystemExit(f"Índice vacío ({counts}): no se sustituye el anterior")
    conn.close()
    os.replace(tmp, index_path)
    print(f"Índice {index_path}: {index_path.stat().st_size / 1024 ** 2:.0f} MB, {counts}, {meta['build_seconds']} s")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("command", choices=("fetch", "build"))
    parser.add_argument("date", help="fecha del volcado mensual, p. ej. 20261001")
    args = parser.parse_args(argv)
    sys.stdout.reconfigure(encoding="utf-8")
    (fetch if args.command == "fetch" else build)(args.date)


if __name__ == "__main__":
    main()
