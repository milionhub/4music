"""Piloto V5.7: ADN musical de 8 canciones (6 de MusicBrainz y 2 de Discogs) a través de la propia API.

    cd backend; .\\.venv\\Scripts\\python eval\\pilot_v57.py baseline   # antes del cambio
    cd backend; .\\.venv\\Scripts\\python eval\\pilot_v57.py             # después: compara con la línea base

Identidades fijadas en V5.5/V5.6 (sin volver a buscarlas). Salidas generadas en eval/pilot_v57_*.json (fuera de Git).
Ver docs/v5-5-cobertura-musical.md, sección V5.7.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

HERE = Path(__file__).resolve().parent
CASES = [
    ("Desire — Chris Stassy", "9d619150-6b0f-4f14-b038-8503ae4c6c8f"),
    ("Double C — PAWSA", "df73a61d-f713-4611-8715-5e4ac6c820d6"),
    ("Dirty Cash (Money Talks) — PAWSA", "f2399817-454b-4c24-8af4-b7c1b17dc00a"),
    ("Crazy — ANOTR", "4358ddcc-119a-48ae-9401-5413b8514441"),
    ("Hoodlum — Traumer", "98e34bc2-0e71-4205-8986-af891195ed4e"),
    ("Lovelee Dae — Blaze", "8edae321-48fc-4ae6-add1-bc976cb1a823"),
    ("Vinotinto — Luciano", "discogs:29565955:1"),
    ("You Got The Groove — Arapu", "discogs:36998067:1"),
]


def row(d: dict) -> dict:
    traits = {t["key"]: t for t in d["dna"]["traits"]}
    show = lambda k: (traits[k]["values"], traits[k]["scope"], [s["label"] for s in traits[k]["sources"]]) \
        if k in traits and traits[k]["status"] != "unavailable" else None  # noqa: E731
    rel = d.get("original_release") or {}
    return {"catalog": d.get("catalog", "musicbrainz"), "genre": show("genre"), "bpm": show("bpm"), "key": show("key"),
            "label": show("label"), "version": d.get("version"), "length_ms": d.get("length_ms"),
            "release": [rel.get("title"), rel.get("primary_type"), rel.get("secondary_types"), rel.get("catalog_number"),
                        rel.get("date")]}


def main() -> None:
    client = TestClient(app)
    out = {}
    for name, tid in CASES:
        t0 = time.monotonic()
        path = f"/v1/tracks/ext/{tid}" if tid.startswith("discogs:") else f"/v1/tracks/{tid}"
        r = client.get(path)
        out[name] = {"id": tid, "status": r.status_code, "s": round(time.monotonic() - t0, 2),
                     **(row(r.json()) if r.status_code == 200 else {})}
    out = json.loads(json.dumps(out, ensure_ascii=False))  # mismas listas que la línea base leída del JSON
    name = "pilot_v57_baseline.json" if sys.argv[1:] == ["baseline"] else "pilot_v57_results.json"
    (HERE / name).write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    base = json.loads((HERE / "pilot_v57_baseline.json").read_text(encoding="utf-8")) if name != "pilot_v57_baseline.json" else {}
    for k, v in out.items():
        b = base.get(k, {})
        changed = [f for f in ("genre", "bpm", "key", "label", "version", "release") if b and b.get(f) != v.get(f)]
        print(f"{k:34} {v['status']} {v['s']:>5}s genre={v.get('genre') and v['genre'][:2]} bpm={v.get('bpm') and v['bpm'][0]} "
              f"key={v.get('key') and v['key'][0]} label={v.get('label') and v['label'][0]}" + (f"  CAMBIA: {changed}" if changed else ""))


if __name__ == "__main__":
    main()
