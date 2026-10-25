"""Piloto del perfil de artista: tracks esenciales, «Más allá de la cabina» (v6) y biografía para la vista rápida de
Carteles, con fuentes reales (MusicBrainz, Deezer, Groq) y en un almacén temporal (la caché real no se toca).

    cd backend; .\\.venv\\Scripts\\python eval\\pilot_profiles.py

Salida en eval/pilot_profiles_results.json (fuera de Git).
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

OUT = Path(__file__).resolve().parent / "pilot_profiles_results.json"
NAMES = ["Traumer", "PAWSA", "Chris Stussy", "Priku", "Arapu"]


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    client = TestClient(app)
    rows = []
    for name in NAMES:
        hit = (client.get("/v1/artists/search", params={"q": name}).json().get("results") or [{}])[0]
        mbid = hit.get("mbid")
        if not mbid:
            print(name, "sin resultado")
            continue
        ess = client.get(f"/v1/artists/{mbid}/essentials").json()
        sto = client.get(f"/v1/artists/{mbid}/stories").json()
        bio = client.get(f"/v1/artists/{mbid}/biography").json().get("bio") or {}
        row = {"name": name, "mbid": mbid,
               "essentials": [f"{t['title']} ({t['year']}) → {t['catalog']}" for t in ess.get("tracks") or []],
               "stories_mode": sto.get("mode"), "stories": [f"[{s['key']}] {s['title']}: {s['text']}" for s in sto.get("stories") or []],
               "bio": (bio.get("kind"), len((bio.get("text") or "").split()))}
        rows.append(row)
        print(json.dumps(row, ensure_ascii=False, indent=1))
    OUT.write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
