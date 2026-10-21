"""Mantenimiento selectivo (sin endpoints públicos que consuman cuota).

    cd backend; .\\.venv\\Scripts\\python -m app.admin invalidate-bio <MBID>   # se regenerará en la próxima visita
    cd backend; .\\.venv\\Scripts\\python -m app.admin show-bio <MBID>         # estado, fuentes y código de error
"""

from __future__ import annotations

import json
import sys

from app import biography, normalize


def main(argv: list[str]) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    if len(argv) != 2 or argv[0] not in ("invalidate-bio", "show-bio") or not normalize.is_mbid(argv[1].lower()):
        print(__doc__)
        return 2
    mbid = argv[1].lower()
    if argv[0] == "invalidate-bio":
        print("borrada" if biography.invalidate(mbid) else "no había biografía guardada para ese MBID")
        return 0
    record = biography.cached(mbid)
    print(json.dumps(record.model_dump() if record else None, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
