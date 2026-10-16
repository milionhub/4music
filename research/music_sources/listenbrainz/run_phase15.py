"""Fase 1.5: artistas similares de ListenBrainz Labs para artistas de música electrónica.

Investigación aislada (no la usan mobile/ ni backend/). Solo biblioteca estándar; reutiliza http_client.py.

    py -3.11 research/music_sources/listenbrainz/run_phase15.py identify   # MusicBrainz: búsqueda + url-rels
    py -3.11 research/music_sources/listenbrainz/run_phase15.py verify     # MusicBrainz: ficha de los MBID fijados
    py -3.11 research/music_sources/listenbrainz/run_phase15.py similar    # Labs: 1 consulta por artista
    py -3.11 research/music_sources/listenbrainz/run_phase15.py radio --ids L1   # 1.5B: LB Radio, sin token
    (--ids L2 limita la etapa a esos artistas y conserva el resto del resultado)

- Sin reintentos automáticos (max_attempts=1). Las respuestas se cachean: repetir no repite peticiones.
- Presupuesto persistente (cuenta las peticiones de red de todos los logs): MusicBrainz 14, Labs 4, LB Radio 4.
- LB Radio (1.5B) exige token de usuario; no se usa ninguno (sin cuentas ni claves nuevas).
- El MBID de cada artista lo fija una persona en artists.json tras revisar identify; el script no elige solo.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from urllib.parse import urlparse

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from http_client import HttpClient, SourcePolicy, now_iso  # noqa: E402

DATA = HERE / "data"
ARTISTS = HERE / "artists.json"
ENV_FILE = HERE.parent / ".env"

MB_BASE = "https://musicbrainz.org/ws/2"
LABS_URL = "https://labs.api.listenbrainz.org/similar-artists/json"
# Algoritmo que usa la página de artista de listenbrainz.org (entity_pages.py) y que Labs ofrece como opción.
ALGORITHM = "session_based_days_7500_session_300_contribution_3_threshold_10_limit_100_filter_True_skip_30"
BUDGET = {"musicbrainz": 14, "listenbrainz_labs": 4,  # MB: 4 búsquedas + url-rels + 1 repetición manual tras 503
          "listenbrainz_api": 4}                        # 1.5B: LB Radio, máximo 1 por artista
LB_RADIO_URL = "https://api.listenbrainz.org/1/explore/lb-radio"
LB_RADIO_MODE = "easy"  # parte más relevante de cada conjunto de datos (troi: easy/medium/hard)
TOP_N = 10


def load_contact() -> str:
    contact = os.environ.get("MUSIC_RESEARCH_CONTACT", "").strip()
    if not contact and ENV_FILE.exists():
        for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
            if line.startswith("MUSIC_RESEARCH_CONTACT="):
                contact = line.split("=", 1)[1].strip()
    return contact


def used_requests(source: str) -> int:
    """Peticiones de red ya hechas en ejecuciones anteriores (presupuesto acumulado, no por ejecución)."""
    n = 0
    for log in (DATA / "logs").glob("*.jsonl"):
        for line in log.read_text(encoding="utf-8").splitlines():
            e = json.loads(line)
            n += e.get("source") == source and not e.get("from_cache")
    return n


def make_client(stage: str) -> HttpClient:
    contact = load_contact()
    if not contact:
        raise SystemExit("Falta MUSIC_RESEARCH_CONTACT en research/music_sources/.env (User-Agent con contacto).")
    ua = {"User-Agent": f"music-discovery-research/0.5 ( {contact} )"}
    client = HttpClient(DATA / "raw", DATA / "logs" / f"{stage}-{now_iso().replace(':', '')}.jsonl")
    for name, interval in (("musicbrainz", 1.1), ("listenbrainz_labs", 1.1), ("listenbrainz_api", 1.1)):
        remaining = BUDGET[name] - used_requests(name)
        client.register(SourcePolicy(name, min_interval_s=interval, max_requests=max(remaining, 0), headers=ua,
                                     max_attempts=1, log_headers=("X-RateLimit-Limit", "X-RateLimit-Remaining",
                                                                  "X-RateLimit-Reset-In", "WWW-Authenticate")))
    return client


def norm(s: str | None) -> str:
    return " ".join((s or "").casefold().split())


def identify(client: HttpClient, artists: list[dict]) -> list[dict]:
    out = []
    for a in artists:
        url = client.build_url(f"{MB_BASE}/artist", {"query": f'artist:"{a["query"]}"', "fmt": "json", "limit": "5"})
        r = client.get_json("musicbrainz", url)
        cands = []
        for c in (r.data or {}).get("artists", []) if r.ok else []:
            cands.append({"mbid": c.get("id"), "name": c.get("name"), "sort_name": c.get("sort-name"),
                          "score": c.get("score"), "type": c.get("type"), "country": c.get("country"),
                          "area": (c.get("area") or {}).get("name"), "disambiguation": c.get("disambiguation"),
                          "begin": (c.get("life-span") or {}).get("begin"),
                          "aliases": sorted({x.get("name") for x in c.get("aliases") or []})[:8],
                          "exact_name": norm(c.get("name")) == norm(a["query"])})
        # Comprobación de identidad: enlaces externos de los candidatos con el nombre exacto (máx. 2).
        for c in [c for c in cands if c["exact_name"]][:2]:
            lr = client.get_json("musicbrainz", client.build_url(f"{MB_BASE}/artist/{c['mbid']}",
                                                                 {"inc": "url-rels", "fmt": "json"}))
            rels = (lr.data or {}).get("relations", []) if lr.ok else []
            c["url_rels"] = sorted({urlparse((x.get("url") or {}).get("resource", "")).netloc for x in rels} - {""})
            c["lookup"] = {"status": lr.status, "error": lr.error, "raw_file": lr.cache_file}
        out.append({"id": a["id"], "query": a["query"], "context_given": a["context_given"],
                    "request": {"url": r.url, "status": r.status, "error": r.error, "raw_file": r.cache_file},
                    "exact_name_candidates": sum(c["exact_name"] for c in cands), "candidates": cands})
    return out


def verify(client: HttpClient, artists: list[dict]) -> list[dict]:
    """Ficha de MusicBrainz (con enlaces externos) de cada MBID fijado en artists.json."""
    out = []
    for a in artists:
        if not a.get("mbid"):
            out.append({"id": a["id"], "query": a["query"], "skipped": "sin MBID en artists.json"})
            continue
        r = client.get_json("musicbrainz", client.build_url(f"{MB_BASE}/artist/{a['mbid']}",
                                                            {"inc": "url-rels", "fmt": "json"}))
        b = r.data if r.ok else {}
        out.append({"id": a["id"], "query": a["query"], "mbid": a["mbid"],
                    "request": {"url": r.url, "status": r.status, "error": r.error, "raw_file": r.cache_file},
                    "name": b.get("name"), "type": b.get("type"), "country": b.get("country"),
                    "area": (b.get("area") or {}).get("name"), "disambiguation": b.get("disambiguation"),
                    "url_rels": sorted({urlparse((x.get("url") or {}).get("resource", "")).netloc
                                        for x in b.get("relations", [])} - {""})})
    return out


def radio(client: HttpClient, artists: list[dict]) -> list[dict]:
    """LB Radio con prompt artist:(MBID) y modo easy. Sin cabecera Authorization: no se usa ningún token."""
    out = []
    for a in artists:
        if not a.get("mbid"):
            out.append({"id": a["id"], "query": a["query"], "skipped": "sin MBID en artists.json"})
            continue
        prompt = f"artist:({a['mbid']})"
        r = client.get_json("listenbrainz_api", client.build_url(LB_RADIO_URL, {"prompt": prompt,
                                                                               "mode": LB_RADIO_MODE}))
        body = r.data if isinstance(r.data, dict) else {}
        tracks = ((body.get("payload") or {}).get("jspf") or {}).get("playlist", {}).get("tracks", [])
        top = [{"rank": i + 1, "title": t.get("title"), "creator": t.get("creator"),
                "identifier": t.get("identifier")} for i, t in enumerate(tracks[:TOP_N])]
        out.append({"id": a["id"], "query": a["query"], "mbid": a["mbid"], "prompt": prompt, "mode": LB_RADIO_MODE,
                    "request": {"url": r.url, "status": r.status, "error": r.error, "raw_file": r.cache_file,
                                "from_cache": r.from_cache, "authorization": "ninguna"},
                    "api_error": body.get("error"), "total_tracks": len(tracks), "top": top})
    return out


def parse_similar(body) -> list[dict]:
    """La respuesta de Labs es una lista de filas; se aceptan filas con artist_mbid (formato no documentado)."""
    rows = body if isinstance(body, list) else (body or {}).get("data", []) if isinstance(body, dict) else []
    flat = []
    for row in rows:
        if isinstance(row, dict) and isinstance(row.get("data"), list):  # variante con bloques {type, data}
            flat += row["data"]
        else:
            flat.append(row)
    return [r for r in flat if isinstance(r, dict) and r.get("artist_mbid")]


def similar(client: HttpClient, artists: list[dict]) -> list[dict]:
    out = []
    for a in artists:
        if not a.get("mbid"):
            out.append({"id": a["id"], "query": a["query"], "skipped": "sin MBID verificado en artists.json"})
            continue
        url = client.build_url(LABS_URL, {"artist_mbids": a["mbid"], "algorithm": ALGORITHM})
        r = client.get_json("listenbrainz_labs", url)
        rows = parse_similar(r.data) if r.ok else []
        rows = [x for x in rows if x.get("artist_mbid") != a["mbid"]]
        keys = sorted({k for x in rows for k in x})
        top = [{"rank": i + 1, "name": x.get("name"), "mbid": x.get("artist_mbid"), "score": x.get("score"),
                **({"comment": x["comment"]} if x.get("comment") else {}),
                **({"type": x["type"]} if x.get("type") else {})} for i, x in enumerate(rows[:TOP_N])]
        out.append({"id": a["id"], "query": a["query"], "mbid": a["mbid"],
                    "request": {"url": r.url, "status": r.status, "error": r.error, "raw_file": r.cache_file,
                                "from_cache": r.from_cache},
                    "total_results": len(rows), "fields_observed": keys, "top": top,
                    "body_shape": type(r.data).__name__ if r.data is not None else None})
    return out


def main(argv: list[str] | None = None) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("stage", choices=("identify", "verify", "similar", "radio"))
    ap.add_argument("--ids", nargs="*", help="solo estos artistas (p. ej. L2); el resto del resultado se conserva")
    args = ap.parse_args(argv)
    artists = json.loads(ARTISTS.read_text(encoding="utf-8"))["artists"]
    if args.ids:
        artists = [a for a in artists if a["id"] in args.ids]
    client = make_client(args.stage)
    result = {"identify": identify, "verify": verify, "similar": similar, "radio": radio}[args.stage](client, artists)
    res_dir = DATA / "results"
    res_dir.mkdir(parents=True, exist_ok=True)
    previous = res_dir / f"{args.stage}.json"
    if args.ids and previous.exists():  # sustituye solo los artistas consultados
        done = {r["id"] for r in result}
        result = [r for r in json.loads(previous.read_text(encoding="utf-8"))["results"] if r["id"] not in done] + result
        result.sort(key=lambda r: r["id"])
    payload = {"generated_at": now_iso(), "stage": args.stage,
               "algorithm": ALGORITHM if args.stage == "similar" else None,
               "network_requests_this_run": client.network_requests,
               "network_requests_all_runs": {s: used_requests(s) for s in BUDGET}, "budget": BUDGET,
               "results": result}
    (res_dir / f"{args.stage}.json").write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: payload[k] for k in ("network_requests_this_run", "network_requests_all_runs")}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
