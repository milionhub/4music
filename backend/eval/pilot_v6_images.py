"""Piloto V6: cobertura de fotos de artista antes y después de Deezer, a través de la propia API.

    cd backend; .\\.venv\\Scripts\\python eval\\pilot_v6_images.py

Artistas: todos los MBID distintos de la caché de fotos real (backend/data/artist_intel.sqlite3, abierta solo en
lectura). Cada uno se resuelve de nuevo en un almacén temporal (la caché real no se toca). Commons y el catálogo
editorial tienen prioridad, así que «antes» = foto que no es de Deezer y «después» = cualquier foto.
Salida en eval/pilot_v6_images_results.json (fuera de Git). Ver docs/v6-fuentes-no-comerciales.md.
"""

from __future__ import annotations

import json
import os
import sqlite3
import sys
import tempfile
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ["ARTIST_DB_PATH"] = str(Path(tempfile.mkdtemp()) / "pilot.sqlite3")
os.environ["DATA_USE"] = "noncommercial"

from fastapi.testclient import TestClient  # noqa: E402

from app import deezer, store  # noqa: E402
from app.api import get_client  # noqa: E402
from app.main import app  # noqa: E402

OUT = Path(__file__).resolve().parent / "pilot_v6_images_results.json"


def cached_mbids() -> list[str]:
    conn = sqlite3.connect(f"file:{ROOT / 'data' / 'artist_intel.sqlite3'}?mode=ro", uri=True)
    return sorted({row[0] for row in conn.execute("SELECT mbid FROM records WHERE kind = 'image'")})


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    client = TestClient(app)
    rows, seen = [], set()
    mbids = cached_mbids()
    for i, mbid in enumerate(mbids, 1):
        started = time.monotonic()
        body = client.get(f"/v1/artists/{mbid}/image").json()
        image = body.get("image") or {}
        record = (store.get(deezer.KIND, mbid) or {}).get("artist") or {}
        name = get_client().artist(mbid).data.get("name")  # ya en la caché en memoria del cliente
        if image.get("url") and image["url"] in seen:
            continue  # MBID fusionado: el mismo artista con otro identificador
        seen.add(image.get("url"))
        rows.append({"mbid": mbid, "name": name, "source": image.get("source"), "via": image.get("via"),
                     "reason": body.get("reason"), "deezer_id": record.get("id"), "deezer_name": record.get("name"),
                     "deezer_via": record.get("via"), "seconds": round(time.monotonic() - started, 1)})
        print(f"{i}/{len(mbids)} {name} → {image.get('source') or body.get('reason')} {record.get('name') or ''}")
    before = sum(1 for r in rows if r["source"] in ("wikimedia_commons", "editorial"))
    after = sum(1 for r in rows if r["source"])
    summary = {"artists": len(rows), "before": before, "after": after,
               "deezer_via": Counter(r["via"] for r in rows if r["source"] == "deezer"),
               "deezer_id_without_photo": sum(1 for r in rows if r["deezer_id"] and r["source"] != "deezer"
                                              and not r["source"]),
               "unavailable": sum(1 for r in rows if r["reason"] == "unavailable")}
    OUT.write_text(json.dumps({"summary": summary, "rows": rows}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
