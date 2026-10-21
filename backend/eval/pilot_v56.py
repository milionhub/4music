"""Piloto V5.6: canciones fuera de MusicBrainz encontradas y abiertas por la API real (búsqueda + ficha de Discogs).

    cd backend; .\\.venv\\Scripts\\python eval\\pilot_v56.py

Usa los proveedores reales a través de la propia API (sin atajos): primero MusicBrainz y, solo si no encuentra nada,
Discogs. Las respuestas de Discogs quedan en la caché del backend (6 h, condiciones de su API). El resumen se escribe
en eval/pilot_v56_results.json (salida generada, fuera de Git). Ver docs/v5-6-catalogo-externo.md.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

# (búsqueda, qué se espera): el piloto comprueba también los rechazos.
CASES = [
    ("Luciano Vinotinto", "discogs:29565955:1"),     # 9:19 en Discogs; el ISRC de Deezer (2:23) es otra versión
    ("Arapu Playground", None),                      # solo en Deezer (uso no comercial): sin resultado
    ("Arapu You Got The Groove", "discogs"),
    ("Arapu Tribal Nation", "discogs"),
    ("Arapu Unexpected", "discogs"),
    ("Arapu Deep Down", "discogs"),
    ("Fired Up Arapu Remix", "discogs"),             # versión: remix, nunca fusionado con la original
    ("Chris Stussy Desire", "musicbrainz"),          # control: MusicBrainz lo tiene y Discogs no se consulta
]


def main() -> None:
    client = TestClient(app)
    out = []
    for query, expected in CASES:
        t0 = time.monotonic()
        r = client.get("/v1/tracks/search", params={"q": query, "limit": "5"})
        body = r.json() if r.status_code == 200 else {"results": []}
        results = body.get("results", [])
        row = {"query": query, "expected": expected, "status": r.status_code, "search_s": round(time.monotonic() - t0, 2),
               "results": [{k: x.get(k) for k in ("mbid", "catalog", "title", "artist_name", "length_ms", "version",
                                                    "release_title", "first_release_date")} for x in results]}
        ext = next((x for x in results if x.get("catalog") == "discogs"), None)
        if ext:
            t1 = time.monotonic()
            p = client.get(f"/v1/tracks/ext/{ext['mbid']}")
            row["profile_s"] = round(time.monotonic() - t1, 2)
            if p.status_code == 200:
                d = p.json()
                row["profile"] = {
                    "main_artist": d["main_artist"], "length_ms": d["length_ms"], "version": d["version"],
                    "release": {k: d["original_release"][k] for k in ("title", "primary_type", "date", "labels",
                                                                       "catalog_number", "formats", "secondary_types")},
                    "traits": {t["key"]: (t["status"], t["scope"], t["values"]) for t in d["dna"]["traits"]},
                    "sources": d["sources"]}
            else:
                row["profile"] = {"status": p.status_code, "error": p.json()}
        out.append(row)
        first = results[0] if results else {}
        print(f"{query:28} → {first.get('catalog', '—'):11} {first.get('mbid', '')} {first.get('title', '')} "
              f"[{first.get('version') or ''}] {row['search_s']} s")
    Path(__file__).with_name("pilot_v56_results.json").write_text(json.dumps(out, ensure_ascii=False, indent=1),
                                                                 encoding="utf-8")


if __name__ == "__main__":
    main()
