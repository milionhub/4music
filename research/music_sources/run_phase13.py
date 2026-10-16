"""Fase 1.3: géneros electrónicos en Discogs y AcousticBrainz.

Reutiliza los casos y los identificadores de la Fase 1.2 (data/results/, solo lectura) y no vuelve a
consultar MusicBrainz ni Wikidata.

Uso (desde la raíz del repo):
    py -3.11 research/music_sources/run_phase13.py              # usa la caché si existe
    py -3.11 research/music_sources/run_phase13.py --refresh

Salidas en research/music_sources/data/:
    raw/discogs/, raw/acousticbrainz/   respuestas originales (Discogs sin campos restringidos)
    logs/phase13-*.jsonl                registro de peticiones (sin cabeceras de petición ni token)
    results_phase13/*.json              valores observados + interpretación
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import sys
from pathlib import Path

import acousticbrainz as AB
import discogs as DG
import sources as S
from http_client import BudgetExceeded, HttpClient, now_iso
from run_experiment import DATA, ROOT, load_env, ref

RESULTS_12 = DATA / "results"
OUT = DATA / "results_phase13"

DISCOGS_BUDGET = 150
AB_BUDGET = 10
MAX_RELEASES_PER_SONG = 4
MAX_MASTERS_PER_SONG = 2
MAX_ARTISTS_PER_CASE = 2
MAX_SAMPLED_PUBLICATIONS = 5
GENERIC = {"electronic", "pop", "hip hop", "rock", "funk / soul", "jazz", "latin", "reggae", "stage & screen"}


def _base_name(name: str | None) -> str:
    """Discogs desambigua homónimos con un sufijo « (2)»; se ignora solo para comparar."""
    n = (name or "").strip()
    if n.endswith(")") and " (" in n and n[n.rfind(" (") + 2:-1].isdigit():
        n = n[:n.rfind(" (")]
    return S.fold(n)


def track_match(found: str, wanted: str) -> str:
    f, w = S.fold(found), S.fold(wanted)
    if f == w:
        return "exact"
    if f.startswith(w + " (") or f.startswith(w + " - ") or f.startswith(w + " ["):
        return "base_title_plus_version"
    return "different"


def hit_artist_part(hit_title: str) -> str:
    return hit_title.split(" - ", 1)[0] if " - " in hit_title else ""


def artist_in(text: str, wanted: str) -> bool:
    t, w = S.fold(text), S.fold(wanted)
    return any(_base_name(p) == w for p in t.replace(" & ", "|").replace(", ", "|").replace(" vs. ", "|")
               .replace(" vs ", "|").replace(" feat. ", "|").replace(" x ", "|").split("|"))


# ---------------------------------------------------------------- canciones

def process_song(client: HttpClient, case: dict, mb: dict) -> dict:
    out = {"case": case, "mb_reference": {
        "status": mb["interpretation"]["status"],
        "recordings": [r["observed"]["mbid"] for r in mb["recordings"] if r.get("observed")],
        "genres_mb": mb["interpretation"]["genres_mb"],
        "discogs_ids_from_mb": mb["interpretation"]["discogs_ids_from_mb"]},
        "searches": [], "releases": [], "masters": [], "master_versions": None, "interpretation": {}}

    # 1) IDs compartidos desde MusicBrainz (sin búsqueda)
    shared_releases = [d["id"] for d in mb["interpretation"]["discogs_ids_from_mb"] if d["kind"] == "release"]
    shared_masters = [d["id"] for d in mb["interpretation"]["discogs_ids_from_mb"] if d["kind"] == "master"]

    # 2) búsqueda propia de Discogs: entrada original y correcciones candidatas, por separado
    search_candidates: list[tuple[str, dict]] = []
    for via, artist_q in [("original_input", case["artist"])] + \
                         [(f"candidate_correction:{c}", c) for c in case["candidate_corrections"]]:
        res = DG.search(client, type="release", artist=artist_q, track=case["title"])
        hits = res.data.get("results", []) if res.ok else []
        summ = []
        for h in hits:
            s = DG.summarize_search_hit(h)
            s["uri"] = DG.WEB.rstrip("/") + s["uri"] if s.get("uri", "").startswith("/") else s.get("uri")
            s["interpretation"] = {"artist_in_title": artist_in(hit_artist_part(s["title"] or ""), artist_q)}
            summ.append(s)
            if s["interpretation"]["artist_in_title"]:
                search_candidates.append((via, s))
        out["searches"].append({"via": via, "artist_query": artist_q, "request": ref(res),
                                "total": res.data.get("pagination", {}).get("items") if res.ok else None,
                                "observed": summ})

    # 3) detalle de lanzamientos: primero los compartidos con MB, luego uno por master de la búsqueda
    to_fetch: list[tuple[str, str]] = [("shared_id_from_musicbrainz", r) for r in shared_releases]
    seen_masters = set()
    for via, s in sorted(search_candidates, key=lambda vs: (vs[0] != "original_input", vs[1].get("year") or "9999")):
        key = s.get("master_id") or f"r{s['id']}"
        if key in seen_masters or any(str(s["id"]) == str(r) for _, r in to_fetch):
            continue
        seen_masters.add(key)
        to_fetch.append((f"search:{via}", str(s["id"])))
    for via, rid in to_fetch[:MAX_RELEASES_PER_SONG]:
        res = DG.release(client, rid)
        entry = {"via": via, "request": ref(res), "discogs_url": DG.web_url("release", rid)}
        if res.ok:
            obs = DG.summarize_release(res.data)
            matches = [t for t in obs["tracklist"] if track_match(t["title"] or "", case["title"]) != "different"]
            artists_text = ", ".join(a["name"] for a in obs["artists"])
            entry["observed"] = obs
            entry["interpretation"] = {
                "tracks_matching_title": [{"position": t["position"], "title": t["title"], "duration": t["duration"],
                                           "match": track_match(t["title"], case["title"]),
                                           "track_credits": t["extraartists"]} for t in matches],
                "release_artist_matches_input": artist_in(artists_text, case["artist"]),
                "release_artist_matches_correction": [c for c in case["candidate_corrections"] if artist_in(artists_text, c)],
                "is_compilation": any("Compilation" in f["descriptions"] for f in obs["formats"])
                                  or S.fold(artists_text) in {"various"},
            }
        out["releases"].append(entry)

    # 4) masters (estilos agregados por Discogs) y ediciones del master principal
    master_ids = list(dict.fromkeys(shared_masters + [str(r["observed"]["master_id"]) for r in out["releases"]
                                                      if r.get("observed") and r["observed"]["master_id"]
                                                      and r["interpretation"]["tracks_matching_title"]]))
    names = [case["artist"]] + case["candidate_corrections"]
    for mid in master_ids[:MAX_MASTERS_PER_SONG]:
        res = DG.master(client, mid)
        entry = {"request": ref(res), "discogs_url": DG.web_url("master", mid),
                 "observed": DG.summarize_master(res.data) if res.ok else None}
        if entry["observed"]:
            # Discogs puede agrupar una versión nueva bajo el master de la obra original de otro artista.
            same = any(artist_in(", ".join(entry["observed"]["artists"]), n) for n in names)
            entry["interpretation"] = {"master_artists_include_input": same,
                                       "styles_applicable_to_case": same}
        out["masters"].append(entry)
    if master_ids:
        res = DG.master_versions(client, master_ids[0])
        versions = res.data.get("versions", []) if res.ok else []
        out["master_versions"] = {"master_id": master_ids[0], "request": ref(res),
                                  "total": res.data.get("pagination", {}).get("items") if res.ok else None,
                                  "observed": [{"id": v.get("id"), "title": v.get("title"), "format": v.get("format"),
                                                "label": v.get("label"), "catno": v.get("catno"),
                                                "country": v.get("country"), "released": v.get("released")}
                                               for v in versions]}

    # 5) interpretación
    confirmed = [r for r in out["releases"] if r.get("interpretation", {}).get("tracks_matching_title")
                 and (r["interpretation"]["release_artist_matches_input"]
                      or r["interpretation"]["release_artist_matches_correction"]
                      or any(artist_in(c["name"], case["artist"]) for t in r["interpretation"]["tracks_matching_title"]
                             for c in t["track_credits"]))]
    via_shared = [r for r in confirmed if r["via"] == "shared_id_from_musicbrainz"]
    via_orig = [r for r in confirmed if r["via"] == "search:original_input"]
    via_corr = [r for r in confirmed if r["via"].startswith("search:candidate_correction")]
    non_comp = [r for r in confirmed if not r["interpretation"]["is_compilation"]]
    styles_by_release = [{"release_id": r["observed"]["id"], "title": r["observed"]["title"], "year": r["observed"]["year"],
                          "is_compilation": r["interpretation"]["is_compilation"],
                          "genres": r["observed"]["genres"], "styles": r["observed"]["styles"]} for r in confirmed]
    styles_by_master = [{"master_id": m["observed"]["id"], "genres": m["observed"]["genres"],
                         "styles": m["observed"]["styles"], "master_artists": m["observed"]["artists"],
                         "applicable_to_case": m["interpretation"]["styles_applicable_to_case"]}
                        for m in out["masters"] if m.get("observed")]
    all_styles = sorted({s for x in styles_by_release if not x["is_compilation"] for s in x["styles"]} |
                        {s for x in styles_by_master if x["applicable_to_case"] for s in x["styles"]})

    # Identidad del artista en Discogs (homónimos): perfil del artista acreditado que coincide con la entrada.
    credited = []
    for r in confirmed:
        for a in r["observed"]["artists"]:
            if any(artist_in(a["name"] or "", n) for n in names) and a["id"] not in [c["id"] for c in credited]:
                credited.append({"id": a["id"], "name": a["name"]})
    out["artist_identity"] = []
    for c in credited[:1]:
        res = DG.artist(client, c["id"])
        a = res.data if res.ok else {}
        out["artist_identity"].append({"request": ref(res), "discogs_url": DG.web_url("artist", c["id"]),
                                       "observed": {"id": c["id"], "name": a.get("name"), "realname": a.get("realname"),
                                                    "profile": (a.get("profile") or "")[:400] or None,
                                                    "data_quality": a.get("data_quality")} if res.ok else None})
    statuses = []
    if via_shared:
        statuses.append("confirmed_via_shared_id_from_musicbrainz")
    if via_orig:
        statuses.append("found_by_discogs_search_with_input")
    if via_corr and not via_orig and not via_shared:
        statuses.append("found_only_via_candidate_correction")
    out["interpretation"] = {
        "status": statuses or (["not_found"] if all(s["request"]["status"] == 200 for s in out["searches"])
                               else ["query_error"]),
        "confirmed_releases": len(confirmed), "non_compilation_releases": len(non_comp),
        "distinct_masters": sorted({str(r["observed"]["master_id"]) for r in confirmed if r["observed"]["master_id"]}),
        "styles_by_release": styles_by_release, "styles_by_master": styles_by_master,
        "specific_styles": all_styles,
        "style_level_note": "Discogs asigna géneros/estilos al lanzamiento o master, no a la pista concreta.",
    }
    return out


# ---------------------------------------------------------------- artistas

def process_artist(client: HttpClient, case: dict, mb: dict) -> dict:
    out = {"case": case, "mb_reference": {
        "status": mb["interpretation"]["status"], "homonyms_mb": mb["interpretation"]["homonyms"],
        "discogs_ids_from_mb": mb["interpretation"]["discogs_ids_from_mb"],
        "genres_mb": sorted({g["name"] for l in mb["lookups"] if l.get("observed") for g in l["observed"]["genres"]}),
        "mb_release_count": {l["observed"]["name"]: l["release_browse"]["observed"]["release_count_total"]
                             for l in mb["lookups"] if l.get("observed") and l.get("release_browse", {}).get("observed")}},
        "searches": [], "artists": [], "interpretation": {}}

    name_hits: list[tuple[str, dict]] = []
    for via, q in [("original_input", case["name"])] + [(f"candidate_correction:{c}", c) for c in case["candidate_corrections"]]:
        res = DG.search(client, type="artist", q=q, per_page="10")
        hits = res.data.get("results", []) if res.ok else []
        obs = [{"id": h.get("id"), "title": h.get("title"), "uri": DG.WEB.rstrip("/") + h["uri"] if h.get("uri", "").startswith("/") else h.get("uri"),
                "name_match": ("exact" if S.norm(h.get("title")) == S.norm(q) else
                               "exact_ignoring_diacritics" if S.fold(h.get("title")) == S.fold(q) else
                               "homonym_suffix" if _base_name(h.get("title")) == S.fold(q) else "none")} for h in hits]
        out["searches"].append({"via": via, "query": q, "request": ref(res), "observed": obs})
        name_hits += [(via, o) for o in obs if o["name_match"] != "none"]

    # Candidatos: los ID enlazados desde MusicBrainz y, después, coincidencias de nombre en Discogs.
    cands: list[tuple[str, str]] = [("shared_id_from_musicbrainz", d["id"]) for d in mb["interpretation"]["discogs_ids_from_mb"]]
    for via, o in sorted(name_hits, key=lambda vo: ({"exact": 0, "exact_ignoring_diacritics": 1, "homonym_suffix": 2}[vo[1]["name_match"]],
                                                    vo[0] != "original_input")):
        if all(str(o["id"]) != c for _, c in cands):
            cands.append((f"search:{via}:{o['name_match']}", str(o["id"])))
    for via, aid in cands[:MAX_ARTISTS_PER_CASE]:
        res = DG.artist(client, aid)
        entry = {"via": via, "request": ref(res), "discogs_url": DG.web_url("artist", aid)}
        if res.ok:
            a = res.data
            entry["observed"] = {"id": a.get("id"), "name": a.get("name"), "realname": a.get("realname"),
                                 "profile": a.get("profile"), "urls": a.get("urls", []),
                                 "namevariations": a.get("namevariations", []),
                                 "aliases": [x.get("name") for x in a.get("aliases", [])],
                                 "members": [x.get("name") for x in a.get("members", [])],
                                 "groups": [x.get("name") for x in a.get("groups", [])],
                                 "data_quality": a.get("data_quality")}
            rr = DG.artist_releases(client, aid)
            items = rr.data.get("releases", []) if rr.ok else []
            roles: dict[str, int] = {}
            for it in items:
                roles[it.get("role") or "?"] = roles.get(it.get("role") or "?", 0) + 1
            main = [it for it in items if it.get("role") == "Main"]
            entry["discography"] = {"request": ref(rr),
                                    "total_items": rr.data.get("pagination", {}).get("items") if rr.ok else None,
                                    "items_in_first_page": len(items), "roles_in_first_page": roles,
                                    "main_in_first_page": len(main)}
            # Muestra de publicaciones propias (rol Main, más recientes primero): estilos por publicación.
            sample = []
            for it in main[:MAX_SAMPLED_PUBLICATIONS]:
                kind = "master" if it.get("type") == "master" else "release"
                res2 = DG.master(client, it["id"]) if kind == "master" else DG.release(client, it["id"])
                pub = {"kind": kind, "id": it["id"], "title": it.get("title"), "year": it.get("year"),
                       "label": it.get("label"), "request": ref(res2), "discogs_url": DG.web_url(kind, it["id"])}
                if res2.ok:
                    pub["genres"], pub["styles"] = res2.data.get("genres", []), res2.data.get("styles", [])
                sample.append(pub)
            entry["sampled_publications"] = sample
            freq: dict[str, int] = {}
            for p in sample:
                for s in p.get("styles", []):
                    freq[s] = freq.get(s, 0) + 1
            entry["interpretation"] = {
                "styles_in_sampled_publications": dict(sorted(freq.items(), key=lambda kv: -kv[1])),
                "sample_size": len(sample),
                "note": "Frecuencia de estilos en publicaciones concretas; no es un atributo del artista.",
            }
        out["artists"].append(entry)

    fetched = [a for a in out["artists"] if a.get("observed")]
    out["interpretation"] = {
        "discogs_name_matches": sorted({(o["title"], o["id"]) for _, o in name_hits}),
        "ambiguous_homonyms": len({o["id"] for _, o in name_hits}) > 1,
        "fetched": [{"id": a["observed"]["id"], "name": a["observed"]["name"], "via": a["via"]} for a in fetched],
    }
    return out


# ---------------------------------------------------------------- AcousticBrainz

def run_acousticbrainz(client: HttpClient, songs_12: list[dict]) -> dict:
    mbids = {r["observed"]["mbid"]: s["case"]["id"] for s in songs_12 for r in s["recordings"] if r.get("observed")}
    ids = sorted(mbids)
    out = {"mbids_queried": [{"mbid": m, "case": mbids[m]} for m in ids], "service_status": None,
           "count": None, "low_level": None, "high_level": None, "per_recording": {}}
    res = AB.count(client, ids)
    out["count"] = {"request": ref(res), "observed": res.data if res.ok else None}
    if not res.ok:
        out["service_status"] = f"no_disponible ({res.error})"
        return out
    out["service_status"] = "operativo"
    counts = {m: (res.data.get(m) or {}).get("count", 0) for m in ids}
    covered = [m for m in ids if counts[m] > 0]
    for m in ids:
        out["per_recording"][m] = {"case": mbids[m], "submissions": counts[m],
                                   "status": "covered" if counts[m] else "not_found"}
    if covered:
        lo = AB.low_level(client, covered)
        hi = AB.high_level(client, covered)
        out["low_level"], out["high_level"] = {"request": ref(lo)}, {"request": ref(hi)}
        for m in covered:
            if lo.ok and m in lo.data:
                out["per_recording"][m]["low_level_estimate"] = AB.summarize_low(lo.data[m].get("0", {}))
            if hi.ok and m in hi.data:
                out["per_recording"][m]["high_level_estimate"] = AB.summarize_high(hi.data[m].get("0", {}))
    out["interpretation_note"] = ("Valores estimados por algoritmo (Essentia/SVM) sobre envíos de usuarios hasta 2022; "
                                  "no son datos verificados. MetaBrainz cerró la recogida por la baja calidad de BPM, "
                                  "tonalidad y modelos de género.")
    return out


# ---------------------------------------------------------------- main

def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--skip-discogs", action="store_true")
    args = parser.parse_args()

    load_env(ROOT / ".env")
    contact = os.environ.get("MUSIC_RESEARCH_CONTACT", "").strip()
    token = os.environ.get("DISCOGS_TOKEN", "").strip()
    if not contact:
        print("Falta MUSIC_RESEARCH_CONTACT en research/music_sources/.env", file=sys.stderr)
        return 2
    user_agent = f"music-discovery-coverage-research/0.2 ( {contact} )"

    songs_12 = json.loads((RESULTS_12 / "songs.json").read_text(encoding="utf-8"))
    artists_12 = json.loads((RESULTS_12 / "artists.json").read_text(encoding="utf-8"))["musicbrainz"]

    run_id = now_iso().replace(":", "").replace("+0000", "Z")
    log_path = DATA / "logs" / f"phase13-{run_id}.jsonl"
    client = HttpClient(DATA / "raw", log_path, refresh=args.refresh)
    client.register(AB.policy(user_agent, AB_BUDGET))
    discogs_state = {"evaluated": False, "reason": None}
    if args.skip_discogs:
        discogs_state["reason"] = "no_consultado (--skip-discogs)"
    elif not token:
        discogs_state["reason"] = "no_consultado (falta DISCOGS_TOKEN)"
    else:
        client.register(DG.policy(token, user_agent, DISCOGS_BUDGET))
        discogs_state["evaluated"] = True
    del token

    songs, artists, ab, aborted = [], [], None, None
    try:
        if discogs_state["evaluated"]:
            for c, mb in zip(json.loads((ROOT / "cases.json").read_text(encoding="utf-8"))["songs"], songs_12):
                assert c["id"] == mb["case"]["id"]
                print(f"[discogs canción] {c['id']} {c['title']} — {c['artist']}", flush=True)
                songs.append(process_song(client, c, mb))
            for mb in artists_12:
                print(f"[discogs artista] {mb['case']['id']} {mb['case']['name']}", flush=True)
                artists.append(process_artist(client, mb["case"], mb))
        print("[acousticbrainz]", flush=True)
        ab = run_acousticbrainz(client, songs_12)
    except BudgetExceeded as exc:
        aborted = str(exc)
        print(f"ABORTADO: {exc}", file=sys.stderr)

    entries = [json.loads(l) for l in log_path.read_text(encoding="utf-8").splitlines()] if log_path.exists() else []
    net = [e for e in entries if not e["from_cache"]]
    rate = {}
    for src in client.policies:
        st = sorted(e["started_mono"] for e in net if e["source"] == src)
        gaps = [b - a for a, b in zip(st, st[1:])]
        rate[src] = {"network_requests": len(st), "min_gap_between_starts_s": round(min(gaps), 3) if gaps else None,
                     "min_ratelimit_remaining_seen": min((int(v) for e in net if e["source"] == src
                                                          for k, v in e.get("headers", {}).items()
                                                          if k.lower().endswith("remaining") and str(v).isdigit()),
                                                         default=None)}
    summary = {
        "run_id": run_id, "executed_at": now_iso(), "aborted": aborted, "python": sys.version.split()[0],
        "platform": platform.platform(),
        "user_agent_format": "music-discovery-coverage-research/0.2 ( <contacto en .env, no se registra> )",
        "auth": "Discogs: cabecera Authorization con token personal leído de .env (no se registra)",
        "budgets": {"discogs": DISCOGS_BUDGET if discogs_state["evaluated"] else 0, "acousticbrainz": AB_BUDGET},
        "discogs": discogs_state, "network_requests": dict(client.network_requests),
        "cache_hits": sum(1 for e in entries if e["from_cache"]),
        "network_errors_or_non_200": [e for e in net if e.get("status") != 200 or e.get("error")],
        "rate_check": rate, "restricted_keys_removed_before_storage": sorted(DG.RESTRICTED_KEYS),
        "log_file": log_path.relative_to(ROOT).as_posix(),
    }
    OUT.mkdir(parents=True, exist_ok=True)
    for name, data in (("discogs_songs", songs), ("discogs_artists", artists), ("acousticbrainz", ab), ("summary", summary)):
        (OUT / f"{name}.json").write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: summary[k] for k in ("network_requests", "cache_hits", "aborted")}, ensure_ascii=False))
    print(f"errores/no-200: {len(summary['network_errors_or_non_200'])}")
    return 1 if aborted else 0


if __name__ == "__main__":
    sys.exit(main())
