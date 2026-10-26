"""Piloto V6.1: extracto de 30 s, sello de Deezer y catálogo de reserva sobre las canciones fijadas en V5.5, a través
de la propia API y en un almacén temporal (la caché real no se toca).

    cd backend; .\\.venv\\Scripts\\python eval\\pilot_v61_tracks.py

Salida en eval/pilot_v61_tracks_results.json (fuera de Git). Ver docs/v6-fuentes-no-comerciales.md.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ["ARTIST_DB_PATH"] = str(Path(tempfile.mkdtemp()) / "pilot.sqlite3")
os.environ["DATA_USE"] = "noncommercial"

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

OUT = Path(__file__).resolve().parent / "pilot_v61_tracks_results.json"
CASES = [  # identidades de V5.5 (docs/v5-5-cobertura-musical.md)
    ("Desire — Chris Stassy", "9d619150-6b0f-4f14-b038-8503ae4c6c8f"),
    ("Double C — PAWSA", "df73a61d-f713-4611-8715-5e4ac6c820d6"),
    ("Hoodlum — Traumer", "98e34bc2-0e71-4205-8986-af891195ed4e"),
    ("Lovelee Dae — Blaze", "8edae321-48fc-4ae6-add1-bc976cb1a823"),
    ("Music Sounds Better With You — Stardust", "6e8b1a97-9b49-4898-9aa3-68db185b3653"),
    ("Dirty Cash (Money Talks) — PAWSA", "f2399817-454b-4c24-8af4-b7c1b17dc00a"),
    ("Crazy — ANOTR", "4358ddcc-119a-48ae-9401-5413b8514441"),
    ("Breather — Chris Stassy", "e0ee17b8-17d3-4514-8579-9a1fd127b57f"),
]
SEARCHES = ["arapu playground", "luciano vinotinto"]


def trait(body: dict, key: str) -> str:
    t = next((t for t in (body.get("dna") or {}).get("traits") or [] if t["key"] == key), None)
    if not t or t["status"] == "unavailable":
        return "—"
    return f"{', '.join(t['values'])} ({t['sources'][0]['label'] if t.get('sources') else '?'})"


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    client = TestClient(app)
    rows = []
    for name, mbid in CASES:
        body = client.get(f"/v1/tracks/{mbid}").json()
        if "dna" not in body:
            rows.append({"case": name, "error": body})
            print(name, "ERROR", body)
            continue
        preview = client.get(f"/v1/tracks/{mbid}/preview").json()
        row = {"case": name, "mbid": body.get("mbid"), "isrcs": body.get("isrcs"), "deezer_url": body.get("deezer_url"),
               "preview": bool(preview.get("url")), "preview_reason": preview.get("reason"),
               "label": trait(body, "label"), "bpm": trait(body, "bpm")}
        rows.append(row)
        print(json.dumps(row, ensure_ascii=False))
    searches = {}
    for q in SEARCHES:
        results = client.get("/v1/tracks/search", params={"q": q}).json().get("results") or []
        searches[q] = [{"id": r["mbid"], "catalog": r.get("catalog"), "title": r["title"], "artist": r["artist_name"],
                        "length_ms": r.get("length_ms")} for r in results[:5]]
        print(q, "→", json.dumps(searches[q], ensure_ascii=False))
        ext = next((r for r in results if r.get("catalog") == "deezer"), None)
        if ext:
            body = client.get(f"/v1/tracks/ext/{ext['mbid']}").json()
            prev = client.get(f"/v1/tracks/ext/{ext['mbid']}/preview").json()
            searches[q + " (ficha)"] = {"label": trait(body, "label"), "bpm": trait(body, "bpm"), "isrcs": body.get("isrcs"),
                                        "date": body.get("first_release_date"), "preview": bool(prev.get("url"))}
            print("  ficha:", json.dumps(searches[q + " (ficha)"], ensure_ascii=False))
    OUT.write_text(json.dumps({"tracks": rows, "searches": searches}, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
