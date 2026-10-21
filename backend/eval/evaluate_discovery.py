"""Evaluación del motor de descubrimiento con datos reales (consulta MusicBrainz y ListenBrainz Labs).

    cd backend; .\\.venv\\Scripts\\python eval\\evaluate_discovery.py

Los objetivos son ejemplos de relevancia deseada definidos por producto, NO reglas del motor: aquí solo se mide
en qué posición aparecen (o si no aparecen). Los negativos son coincidencias incidentales que no deberían salir.
Las semillas se identifican por MBID verificado (nunca por nombre).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

SEEDS = {
    "PAWSA": "202ed573-bcb9-4686-bc98-6fc96b1f6ae9",
    "Cloonee": "b643c24d-4cd6-4531-88bc-62b39ce43ee1",
    "Paco Osuna": "bf6335a3-9dc3-46bf-844a-fdb432ddefd5",
    "Joseph Capriati": "b523b6b8-f2ea-4d6c-ba23-f25e02715727",
}
CASES = [
    {"seeds": ["PAWSA"], "targets": ["Michael Bibi"], "negatives": ["Nate Dogg", "Malachiii"]},
    {"seeds": ["Cloonee"], "targets": ["Josh Baker"], "negatives": ["Jomanda", "Changing Faces", "Funkdoobiest"]},
    {"seeds": ["Paco Osuna"], "targets": ["Ilario Alicante", "Marco Carola"], "negatives": []},
    {"seeds": ["Joseph Capriati"], "targets": ["Marco Carola", "Ilario Alicante"], "negatives": ["Arnold Jarvis"]},
    {"seeds": ["Paco Osuna", "Joseph Capriati"], "targets": ["Ilario Alicante", "Marco Carola"], "negatives": ["Arnold Jarvis"]},
]


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    client = TestClient(app)
    report = []
    for case in CASES:
        r = client.get("/v1/discovery", params={"seeds": ",".join(SEEDS[s] for s in case["seeds"]), "limit": "20"})
        if r.status_code != 200:
            print(f"{' + '.join(case['seeds'])}: HTTP {r.status_code} {r.json().get('error')}")
            report.append({**case, "status": r.status_code})
            continue
        cards = r.json()["cards"]
        names = [c["artist"]["name"] for c in cards]
        positions = {t: (names.index(t) + 1 if t in names else None) for t in case["targets"]}
        leaked = [n for n in case["negatives"] if n in names]
        print(f"\n== {' + '.join(case['seeds'])}: {len(cards)} recomendaciones")
        print("   objetivos:", positions, "| negativos presentes:", leaked or "ninguno")
        for i, c in enumerate(cards[:10], 1):
            print(f"   {i:>2}. {c['artist']['name']} — {c['tag']} · {c['headline']} (score {c['score']})")
        report.append({**case, "count": len(cards), "positions": positions, "negatives_present": leaked,
                       "top10": [(c["artist"]["name"], c["kind"], c["score"]) for c in cards[:10]]})
    out = Path(__file__).resolve().parent / "last_results.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
