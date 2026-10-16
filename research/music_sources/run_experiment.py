"""Experimento de cobertura de fuentes musicales (Fase 1.2).

Uso (desde la raíz del repo):
    py -3.11 research/music_sources/run_experiment.py            # usa caché si existe
    py -3.11 research/music_sources/run_experiment.py --refresh  # vuelve a pedir todo

Salidas en research/music_sources/data/:
    raw/<fuente>/*.json   respuesta original de cada petición (datos originales)
    logs/run-*.jsonl      registro de peticiones (sin cabeceras ni credenciales)
    results/*.json        valores observados + interpretación, separados por clave
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import re
import sys
from pathlib import Path

from http_client import BudgetExceeded, HttpClient, SourcePolicy, now_iso
import sources as S

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"

ELECTRONIC_TERMS = {
    "electronic", "house", "deep house", "tech house", "minimal", "minimal techno", "minimal house",
    "techno", "progressive house", "microhouse", "afro house", "electronica", "dance", "garage house",
    "uk garage", "soulful house", "disco", "nu-disco", "acid house", "trance", "electro",
}

# Presupuesto de peticiones de red por ejecución (techo duro; ver README).
MB_BUDGET = 130
WD_BUDGET = 30
MB_INTERVAL_S = 1.5  # oficial: ~1 petición/s de media por IP; margen ante 503
WD_INTERVAL_S = 1.0
MAX_RECORDING_LOOKUPS_PER_SONG = 3
MAX_RELEASE_LOOKUPS_PER_SONG = 3
MAX_RG_LOOKUPS_PER_SONG = 2
MAX_ARTIST_LOOKUPS_PER_CASE = 2
MAX_FUZZY_ARTISTS = 3


def load_env(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip())


def ref(res) -> dict:
    return {"url": res.url, "status": res.status, "error": res.error, "raw_file": res.cache_file,
            "from_cache": res.from_cache}


# ---------------------------------------------------------------- canciones

def title_match(found: str, wanted: str) -> str:
    if S.norm(found) == S.norm(wanted):
        return "exact"
    if S.fold(found) == S.fold(wanted):
        return "exact_ignoring_diacritics"
    f, w = S.fold(found), S.fold(wanted)
    if f.startswith(w + " (") or f.startswith(w + " - ") or f.startswith(w + " ["):
        return "base_title_plus_version"
    return "different"


def artist_match(artist_credit: list[dict], wanted: str) -> str:
    names = [c.get("name") for c in artist_credit] + [c.get("artist", {}).get("name") for c in artist_credit]
    if any(S.norm(n) == S.norm(wanted) for n in names):
        return "exact"
    if any(S.fold(n) == S.fold(wanted) for n in names):
        return "exact_ignoring_diacritics"
    if S.fold(wanted) in S.fold(S.credit_text(artist_credit)):
        return "contained_in_credit"
    return "none"


def summarize_search_recording(rec: dict, wanted_title: str, wanted_artist: str | None) -> dict:
    releases = rec.get("releases", [])
    return {
        "observed": {
            "mbid": rec["id"], "title": rec.get("title"), "disambiguation": rec.get("disambiguation") or None,
            "length_ms": rec.get("length"), "first_release_date": rec.get("first-release-date"),
            "artist_credit": S.credit_text(rec.get("artist-credit")), "isrcs": rec.get("isrcs", []),
            "release_count": len(releases),
            "release_titles": sorted({r.get("title") for r in releases})[:10],
        },
        "search_score": rec.get("score"),
        "interpretation": {
            "title_match": title_match(rec.get("title", ""), wanted_title),
            "artist_match": artist_match(rec.get("artist-credit", []), wanted_artist) if wanted_artist else None,
        },
    }


def release_sort_key(rel: dict):
    rg = rel.get("release-group", {})
    secondary = set(rg.get("secondary-types", []) or [])
    is_comp = bool(secondary & {"Compilation", "DJ-mix", "Mixtape/Street"})
    return (is_comp, rel.get("date") or "9999", rel.get("id"))


def process_song(client: HttpClient, case: dict) -> dict:
    out = {"case": case, "searches": [], "candidates": [], "recordings": [], "releases": [],
           "release_groups": [], "wikidata_search": None, "interpretation": {}}

    # 1) búsquedas: entrada original, correcciones candidatas, y solo título (homónimos)
    queries = [("original_input", case["artist"])] + \
              [(f"candidate_correction:{c}", c) for c in case["candidate_corrections"]] + \
              [("title_only", None)]
    matched: dict[str, dict] = {}
    for via, artist in queries:
        res = S.mb_search_recordings(client, case["title"], artist)
        recs = res.data.get("recordings", []) if res.ok and isinstance(res.data, dict) else []
        summ = [summarize_search_recording(r, case["title"], artist or case["artist"]) for r in recs]
        out["searches"].append({"via": via, "artist_query": artist, "request": ref(res),
                                "total_hits": res.data.get("count") if res.ok else None,
                                "results_returned": len(recs)})
        for s in summ:
            s["via"] = via
            out["candidates"].append(s)
            it = s["interpretation"]
            if via != "title_only" and it["title_match"] != "different" and it["artist_match"] != "none":
                matched.setdefault(s["observed"]["mbid"], s)

    # 1b) diagnóstico: homónimos del artista y, si no hay coincidencia, búsqueda difusa
    #     (solo informativa: nunca cuenta como coincidencia).
    res = S.mb_search_artists(client, case["artist"])
    out["artist_search"] = {"request": ref(res), "observed": [
        {"mbid": a["id"], "name": a.get("name"), "disambiguation": a.get("disambiguation") or None,
         "country": a.get("country"), "score": a.get("score")}
        for a in (res.data.get("artists", []) if res.ok else []) if S.fold(a.get("name")) == S.fold(case["artist"])]}
    out["fuzzy_diagnostic"] = None
    if not matched:
        # Por MBID de cada artista homónimo (arid), para no mezclar artistas con el mismo nombre.
        terms = " OR ".join(f"recording:{t}~ OR recording:{t[:max(4, len(t) // 2)]}*"
                            for t in S.fold(case["title"]).split() if t.isalnum())
        out["fuzzy_diagnostic"] = []
        for a in out["artist_search"]["observed"][:MAX_FUZZY_ARTISTS]:
            res = S.mb_get(client, "recording", {"query": f"arid:{a['mbid']} AND ({terms})", "limit": "10"})
            out["fuzzy_diagnostic"].append({
                "artist_mbid": a["mbid"], "artist_disambiguation": a["disambiguation"], "request": ref(res),
                "note": "búsqueda aproximada; no es correspondencia",
                "observed": [{"mbid": r["id"], "title": r.get("title"), "score": r.get("score"),
                              "artist_credit": S.credit_text(r.get("artist-credit")),
                              "first_release_date": r.get("first-release-date")}
                             for r in (res.data.get("recordings", []) if res.ok else [])]})

    # 2) lookups de las grabaciones que coinciden (título + artista), las más fiables primero:
    #    entrada original, título exacto, no extraída de un DJ-mix, más antigua, con más lanzamientos.
    order = {"exact": 0, "exact_ignoring_diacritics": 1, "base_title_plus_version": 2}
    chosen = sorted(matched.values(), key=lambda s: (s["via"] != "original_input",
                                                     order[s["interpretation"]["title_match"]],
                                                     "dj-mix" in S.fold(s["observed"]["disambiguation"]),
                                                     s["observed"]["first_release_date"] or "9999",
                                                     -s["observed"]["release_count"]))
    chosen = chosen[:MAX_RECORDING_LOOKUPS_PER_SONG]
    release_pool: dict[str, dict] = {}
    for s in chosen:
        res = S.mb_lookup_recording(client, s["observed"]["mbid"])
        entry = {"request": ref(res), "via": s["via"], "interpretation": s["interpretation"]}
        if res.ok:
            rec = res.data
            rels = S.url_rels(rec)
            entry["observed"] = {
                "mbid": rec["id"], "title": rec.get("title"), "disambiguation": rec.get("disambiguation") or None,
                "length_ms": rec.get("length"), "first_release_date": rec.get("first-release-date"),
                "artist_credit": S.credit_text(rec.get("artist-credit")),
                "artists": S.credit_people(rec.get("artist-credit")), "isrcs": rec.get("isrcs", []),
                "url_relations": rels, "other_relations": S.non_url_rels(rec), **S.genres_and_tags(rec),
                "releases": [{"mbid": r["id"], "title": r.get("title"), "date": r.get("date"),
                              "country": r.get("country"), "status": r.get("status"),
                              "release_group_type": r.get("release-group", {}).get("primary-type"),
                              "release_group_secondary": r.get("release-group", {}).get("secondary-types", []),
                              "release_group_mbid": r.get("release-group", {}).get("id")}
                             for r in rec.get("releases", [])],
            }
            for r in sorted(rec.get("releases", []), key=release_sort_key)[:MAX_RELEASE_LOOKUPS_PER_SONG]:
                release_pool.setdefault(r["id"], r)
        out["recordings"].append(entry)

    # 3) lanzamientos (sello, tipo, enlaces) y release groups (géneros)
    rg_ids: list[str] = []
    for rid in sorted(release_pool, key=lambda k: release_sort_key(release_pool[k]))[:MAX_RELEASE_LOOKUPS_PER_SONG]:
        res = S.mb_lookup_release(client, rid)
        entry = {"request": ref(res)}
        if res.ok:
            rel = res.data
            rg = rel.get("release-group", {})
            entry["observed"] = {
                "mbid": rel["id"], "title": rel.get("title"), "date": rel.get("date"), "country": rel.get("country"),
                "status": rel.get("status"), "barcode": rel.get("barcode") or None,
                "artist_credit": S.credit_text(rel.get("artist-credit")),
                "labels": [{"name": li.get("label", {}).get("name") if li.get("label") else None,
                            "label_mbid": li.get("label", {}).get("id") if li.get("label") else None,
                            "catalog_number": li.get("catalog-number")} for li in rel.get("label-info", [])],
                "formats": [m.get("format") for m in rel.get("media", [])],
                "release_group": {"mbid": rg.get("id"), "title": rg.get("title"), "primary_type": rg.get("primary-type"),
                                  "secondary_types": rg.get("secondary-types", [])},
                "url_relations": S.url_rels(rel), **S.genres_and_tags(rel),
            }
            if rg.get("id") and rg["id"] not in rg_ids:
                rg_ids.append(rg["id"])
        out["releases"].append(entry)
    for rgid in rg_ids[:MAX_RG_LOOKUPS_PER_SONG]:
        res = S.mb_lookup_release_group(client, rgid)
        entry = {"request": ref(res)}
        if res.ok:
            rg = res.data
            entry["observed"] = {"mbid": rg["id"], "title": rg.get("title"), "primary_type": rg.get("primary-type"),
                                 "secondary_types": rg.get("secondary-types", []),
                                 "first_release_date": rg.get("first-release-date"),
                                 "url_relations": S.url_rels(rg), **S.genres_and_tags(rg)}
        out["release_groups"].append(entry)

    # 4) Wikidata: búsqueda de texto del título (candidatos sin vincular, nunca correspondencia automática)
    res = S.wd_search(client, case["title"])
    out["wikidata_search"] = {"request": ref(res), "observed": [
        {"qid": h.get("id"), "label": h.get("label"), "description": h.get("description")}
        for h in (res.data.get("search", []) if res.ok else [])]}

    # 5) interpretación resumida
    found = [r for r in out["recordings"] if r.get("observed")]
    exact_orig = [r for r in found if r["via"] == "original_input" and r["interpretation"]["title_match"] == "exact"
                  and r["interpretation"]["artist_match"] == "exact"]
    via_corr = [r for r in found if r["via"].startswith("candidate_correction")]
    all_genres = {g["name"] for x in out["recordings"] + out["releases"] + out["release_groups"]
                  for g in x.get("observed", {}).get("genres", [])}
    all_tags = {t["name"] for x in out["recordings"] + out["releases"] + out["release_groups"]
                for t in x.get("observed", {}).get("tags", [])}
    out["interpretation"] = {
        "status": ("found_exact_input" if exact_orig else
                   "found_only_via_candidate_correction" if via_corr and not any(r["via"] == "original_input" for r in found) else
                   "found_title_variant_only" if found else "not_found_in_musicbrainz"),
        "matching_recordings_in_search": len(matched),
        "recordings_looked_up": len(found),
        "artist_mbids_in_matches": sorted({p["artist_mbid"] for r in found for p in r["observed"]["artists"]}),
        "same_name_artists_in_mb": len(out["artist_search"]["observed"]),
        "distinct_lengths_ms": sorted({r["observed"]["length_ms"] for r in found if r["observed"]["length_ms"]}),
        "title_only_hits_other_artists": sorted({c["observed"]["artist_credit"] for c in out["candidates"]
                                                 if c["via"] == "title_only"
                                                 and c["interpretation"]["title_match"] == "exact"
                                                 and c["interpretation"]["artist_match"] == "none"})[:15],
        "genres_mb": sorted(all_genres), "tags_mb": sorted(all_tags),
        "electronic_specific_terms": sorted((all_genres | all_tags) & ELECTRONIC_TERMS),
        "wikidata_linked_from_mb": sorted({q for x in out["recordings"] + out["release_groups"]
                                           for q in S.wikidata_qids(x.get("observed", {}).get("url_relations", []))}),
        "discogs_ids_from_mb": [d for x in out["recordings"] + out["releases"] + out["release_groups"]
                                for d in S.discogs_ids(x.get("observed", {}).get("url_relations", []))],
    }
    return out


# ---------------------------------------------------------------- artistas

def name_match(artist: dict, wanted: str) -> str:
    if S.norm(artist.get("name")) == S.norm(wanted):
        return "exact"
    if S.fold(artist.get("name")) == S.fold(wanted):
        return "exact_ignoring_diacritics"
    aliases = [a.get("name") for a in artist.get("aliases", []) or []]
    if any(S.norm(a) == S.norm(wanted) for a in aliases):
        return "alias"
    if any(S.fold(a) == S.fold(wanted) for a in aliases):
        return "alias_ignoring_diacritics"
    return "none"


def process_artist(client: HttpClient, case: dict) -> dict:
    out = {"case": case, "searches": [], "candidates": [], "lookups": [], "interpretation": {}}
    matched: dict[str, dict] = {}
    for via, name in [("original_input", case["name"])] + \
                     [(f"candidate_correction:{c}", c) for c in case["candidate_corrections"]]:
        res = S.mb_search_artists(client, name)
        arts = res.data.get("artists", []) if res.ok and isinstance(res.data, dict) else []
        out["searches"].append({"via": via, "query": name, "request": ref(res),
                                "total_hits": res.data.get("count") if res.ok else None})
        for a in arts:
            c = {"via": via, "search_score": a.get("score"),
                 "observed": {"mbid": a["id"], "name": a.get("name"), "sort_name": a.get("sort-name"),
                              "disambiguation": a.get("disambiguation") or None, "type": a.get("type"),
                              "country": a.get("country"), "area": a.get("area", {}).get("name"),
                              "life_span": a.get("life-span"), "tags": [t["name"] for t in a.get("tags", [])]},
                 "interpretation": {"name_match": name_match(a, name)}}
            out["candidates"].append(c)
            if c["interpretation"]["name_match"] != "none":
                matched.setdefault(a["id"], c)

    order = {"exact": 0, "exact_ignoring_diacritics": 1, "alias": 2, "alias_ignoring_diacritics": 3}
    chosen = sorted(matched.values(), key=lambda c: (c["via"] != "original_input",
                                                     order[c["interpretation"]["name_match"]],
                                                     -(c["search_score"] or 0)))
    chosen = chosen[:MAX_ARTIST_LOOKUPS_PER_CASE]
    for c in chosen:
        res = S.mb_lookup_artist(client, c["observed"]["mbid"])
        entry = {"request": ref(res), "via": c["via"], "interpretation": dict(c["interpretation"])}
        if res.ok:
            a = res.data
            rels = S.url_rels(a)
            entry["observed"] = {
                "mbid": a["id"], "name": a.get("name"), "sort_name": a.get("sort-name"),
                "disambiguation": a.get("disambiguation") or None, "type": a.get("type"), "gender": a.get("gender"),
                "country": a.get("country"), "area": (a.get("area") or {}).get("name"),
                "begin_area": (a.get("begin-area") or {}).get("name"), "life_span": a.get("life-span"),
                "ipis": a.get("ipis", []), "isnis": a.get("isnis", []),
                "aliases": [{"name": x.get("name"), "type": x.get("type"), "locale": x.get("locale")}
                            for x in a.get("aliases", [])],
                "url_relations": rels, "other_relations": S.non_url_rels(a), **S.genres_and_tags(a),
            }
            tags = {g["name"] for g in entry["observed"]["genres"]} | {t["name"] for t in entry["observed"]["tags"]}
            entry["interpretation"]["electronic_signal_genres_tags"] = sorted(tags & ELECTRONIC_TERMS)
            dis = S.fold(entry["observed"]["disambiguation"])
            entry["interpretation"]["electronic_signal_disambiguation"] = sorted(
                t for t in ELECTRONIC_TERMS | {"dj", "producer"} if re.search(rf"(?<![a-z]){re.escape(t)}(?![a-z])", dis))
        out["lookups"].append(entry)

    for entry in out["lookups"]:
        if entry.get("observed"):
            entry["release_browse"] = browse_releases(client, entry["observed"]["mbid"])

    primary = next((x for x in out["lookups"] if x.get("observed")), None)
    homonyms = [c for c in out["candidates"] if c["interpretation"]["name_match"] != "none"]
    distinct = sorted({(c["observed"]["name"], c["observed"]["disambiguation"] or "", c["observed"]["mbid"])
                       for c in homonyms})
    out["interpretation"] = {
        "status": "not_found_in_musicbrainz" if not primary else
                  ("found_exact_input" if primary["via"] == "original_input" and primary["interpretation"]["name_match"] == "exact"
                   else f"found_via_{primary['interpretation']['name_match']}" + ("" if primary["via"] == "original_input"
                                                                                  else "_of_candidate_correction")),
        "rule_ranked_first_mbid": primary["observed"]["mbid"] if primary else None,
        "ambiguous_homonyms": len(distinct) > 1,
        "name_matching_candidates": len(distinct),
        "homonyms": distinct,
        "wikidata_qids_from_mb": sorted({q for x in out["lookups"] if x.get("observed")
                                         for q in S.wikidata_qids(x["observed"]["url_relations"])}),
        "discogs_ids_from_mb": [d | {"artist_mbid": x["observed"]["mbid"]} for x in out["lookups"] if x.get("observed")
                                for d in S.discogs_ids(x["observed"]["url_relations"])],
    }
    return out


def browse_releases(client: HttpClient, mbid: str) -> dict:
    """Sellos y tipos derivados de los lanzamientos del artista (primera página, 100)."""
    res = S.mb_browse_artist_releases(client, mbid)
    browse = {"request": ref(res)}
    if res.ok:
        labels: dict[str, int] = {}
        rg_types: dict[str, int] = {}
        for rel in res.data.get("releases", []):
            for li in rel.get("label-info", []):
                if li.get("label"):
                    labels[li["label"]["name"]] = labels.get(li["label"]["name"], 0) + 1
            t = rel.get("release-group", {}).get("primary-type") or "sin tipo"
            rg_types[t] = rg_types.get(t, 0) + 1
        browse["observed"] = {"release_count_total": res.data.get("release-count"),
                              "releases_returned": len(res.data.get("releases", [])),
                              "labels_by_release_count": dict(sorted(labels.items(), key=lambda kv: -kv[1])),
                              "release_group_types": rg_types}
    return browse


# ---------------------------------------------------------------- Wikidata (enriquecimiento)

MAX_UNLINKED_WD_CANDIDATES = 3


def _item_ids_in(entity: dict) -> set[str]:
    """Ítems citados como valor o como fuente de referencia en las propiedades consultadas."""
    found = set()
    for pid in S.WD_PROPS:
        for s in entity.get("claims", {}).get(pid, []):
            v = S._snak_value(s["mainsnak"])
            if "item" in v:
                found.add(v["item"])
            for r in s.get("references", []):
                for p in ("P248", "P143"):
                    for sn in r.get("snaks", {}).get(p, []):
                        rv = S._snak_value(sn)
                        if "item" in rv:
                            found.add(rv["item"])
    return found


def _describe_item(qid: str, e: dict | None, labels: dict, mb_mbids: list[str], link: str) -> dict:
    if not e or "missing" in e:
        return {"qid": qid, "link": link, "observed": None, "interpretation": {"status": "missing_in_wikidata"}}
    claims = S.extract_claims(e)
    for prop in claims.values():
        for v in prop["values"]:
            if "item" in v["value"]:
                v["value"]["label"] = labels.get(v["value"]["item"])
            if "time" in v["value"]:
                v["value"]["formatted"] = S.format_time(v["value"])
            for r in v["references"]:
                for p in ("P248", "P143"):
                    for rv in r.get(p, []):
                        if "item" in rv:
                            rv["label"] = labels.get(rv["item"])
    back = [v["value"].get("string") for v in claims.get("P434", {}).get("values", [])]
    matches = sorted(set(back) & set(mb_mbids))
    if link == "from_musicbrainz":
        status = "validated_bidirectional" if matches else "linked_from_mb_only" if not back else "mbid_mismatch"
    else:  # candidato por texto: solo se acepta si Wikidata apunta a un MBID que ya revisamos
        status = "validated_reverse_link_only" if matches else "unvalidated_text_candidate"
    return {
        "qid": qid, "link": link, "source_url": f"https://www.wikidata.org/wiki/{qid}",
        "observed": {"label_en": e.get("labels", {}).get("en", {}).get("value"),
                     "label_es": e.get("labels", {}).get("es", {}).get("value"),
                     "description_en": e.get("descriptions", {}).get("en", {}).get("value"),
                     "description_es": e.get("descriptions", {}).get("es", {}).get("value"),
                     "sitelinks": sorted(e.get("sitelinks", {})), "claims": claims},
        "interpretation": {"status": status, "wikidata_mbids": back, "matches_mb_mbids_reviewed": matches},
    }


def enrich_with_wikidata(client: HttpClient, artists: list[dict]) -> dict:
    linked = {a["case"]["id"]: a["interpretation"]["wikidata_qids_from_mb"] for a in artists}
    reviewed_mbids = {a["case"]["id"]: [x["observed"]["mbid"] for x in a["lookups"] if x.get("observed")]
                      for a in artists}
    unlinked_search, unlinked_qids = {}, {}
    for a in artists:
        cid = a["case"]["id"]
        if linked[cid]:
            continue
        # Sin enlace desde MusicBrainz: búsqueda por texto del nombre tal cual se proporcionó.
        name = a["case"]["name"]
        res = S.wd_search(client, name)
        hits = res.data.get("search", []) if res.ok else []
        unlinked_search[cid] = {"request": ref(res), "query": name, "observed": [
            {"qid": h.get("id"), "label": h.get("label"), "description": h.get("description")} for h in hits]}
        unlinked_qids[cid] = [h["id"] for h in hits[:MAX_UNLINKED_WD_CANDIDATES]]

    all_qids = sorted({q for v in linked.values() for q in v} | {q for v in unlinked_qids.values() for q in v})
    entities, labels, requests = {}, {}, []
    for i in range(0, len(all_qids), 50):
        res = S.wd_entities(client, all_qids[i:i + 50], "labels|descriptions|claims|sitelinks")
        requests.append(ref(res))
        if res.ok:
            entities.update(res.data.get("entities", {}))
    ref_items = sorted(set().union(*(_item_ids_in(e) for e in entities.values())) if entities else set())
    for i in range(0, len(ref_items), 50):
        res = S.wd_entities(client, ref_items[i:i + 50], "labels")
        requests.append(ref(res))
        if res.ok:
            for qid, e in res.data.get("entities", {}).items():
                lab = e.get("labels", {})
                labels[qid] = (lab.get("es") or lab.get("en") or lab.get("mul") or {}).get("value")

    per_artist = {}
    for a in artists:
        cid = a["case"]["id"]
        items = [_describe_item(q, entities.get(q), labels, reviewed_mbids[cid], "from_musicbrainz") for q in linked[cid]]
        items += [_describe_item(q, entities.get(q), labels, reviewed_mbids[cid], "text_search_candidate")
                  for q in unlinked_qids.get(cid, [])]
        per_artist[cid] = {"items": items, "unlinked_text_search": unlinked_search.get(cid)}
    return {"requests": requests, "per_artist": per_artist}



# ---------------------------------------------------------------- main

def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--refresh", action="store_true", help="ignora la caché y vuelve a pedir")
    args = parser.parse_args()

    load_env(ROOT / ".env")
    contact = os.environ.get("MUSIC_RESEARCH_CONTACT", "").strip()
    if not contact:
        print("Falta MUSIC_RESEARCH_CONTACT (email o URL de contacto) en research/music_sources/.env; "
              "ver .env.example. MusicBrainz y Wikimedia exigen un User-Agent con contacto.", file=sys.stderr)
        return 2
    user_agent = f"music-discovery-coverage-research/0.1 ( {contact} )"

    run_id = now_iso().replace(":", "").replace("+0000", "Z")
    log_path = DATA / "logs" / f"run-{run_id}.jsonl"
    client = HttpClient(DATA / "raw", log_path, refresh=args.refresh)
    client.register(SourcePolicy("musicbrainz", min_interval_s=MB_INTERVAL_S, max_requests=MB_BUDGET,
                                 headers={"User-Agent": user_agent}))
    client.register(SourcePolicy("wikidata", min_interval_s=WD_INTERVAL_S, max_requests=WD_BUDGET,
                                 headers={"User-Agent": user_agent}))

    cases = json.loads((ROOT / "cases.json").read_text(encoding="utf-8"))
    songs, artists, aborted = [], [], None
    try:
        for c in cases["songs"]:
            print(f"[canción] {c['id']} {c['title']} — {c['artist']}", flush=True)
            songs.append(process_song(client, c))
        for c in cases["artists"]:
            print(f"[artista] {c['id']} {c['name']}", flush=True)
            artists.append(process_artist(client, c))
        print("[wikidata] enriquecimiento de artistas", flush=True)
        wikidata = enrich_with_wikidata(client, artists)
    except BudgetExceeded as exc:
        aborted, wikidata = str(exc), None
        print(f"ABORTADO: {exc}", file=sys.stderr)

    log_entries = [json.loads(l) for l in log_path.read_text(encoding="utf-8").splitlines()] if log_path.exists() else []
    net = [e for e in log_entries if not e["from_cache"]]
    summary = {
        "run_id": run_id, "executed_at": now_iso(), "aborted": aborted,
        "python": sys.version.split()[0], "platform": platform.platform(),
        "user_agent_format": "music-discovery-coverage-research/0.1 ( <contacto en .env, no se registra> )",
        "endpoints": {"musicbrainz": S.MB_BASE, "wikidata": S.WD_API},
        "budgets": {"musicbrainz": MB_BUDGET, "wikidata": WD_BUDGET, "discogs": 0},
        "rate_policy_min_interval_s": {"musicbrainz": MB_INTERVAL_S, "wikidata": WD_INTERVAL_S},
        "network_requests": dict(client.network_requests),
        "cache_hits": sum(1 for e in log_entries if e["from_cache"]),
        "network_errors_or_non_200": [e for e in net if e.get("status") != 200 or e.get("error")],
        "rate_check": {},
        "discogs": S.DISCOGS_STATUS | {"token_present_in_env": bool(os.environ.get("DISCOGS_TOKEN"))},
        "log_file": log_path.relative_to(ROOT).as_posix(),
    }
    for src in client.policies:
        starts = sorted(e["started_mono"] for e in net if e["source"] == src)
        gaps = [b - a for a, b in zip(starts, starts[1:])]
        summary["rate_check"][src] = {
            "network_requests": len(starts),
            "min_gap_between_starts_s": round(min(gaps), 3) if gaps else None,
            "mean_rate_per_s": round((len(starts) - 1) / (starts[-1] - starts[0]), 3) if len(starts) > 1 else None,
        }

    all_net = [json.loads(l) for f in sorted((DATA / "logs").glob("run-*.jsonl"))
               for l in f.read_text(encoding="utf-8").splitlines()]
    all_net = [e for e in all_net if not e["from_cache"]]
    summary["all_runs"] = {
        "log_files": len(list((DATA / "logs").glob("run-*.jsonl"))),
        "network_requests": {src: sum(1 for e in all_net if e["source"] == src) for src in client.policies},
        "retried_or_non_200": sum(1 for e in all_net if e.get("status") != 200 or e.get("error")),
        "unique_urls": len({e["url"] for e in all_net}),
    }

    out_dir = DATA / "results"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "songs.json").write_text(json.dumps(songs, ensure_ascii=False, indent=1), encoding="utf-8")
    (out_dir / "artists.json").write_text(json.dumps({"musicbrainz": artists, "wikidata": wikidata},
                                                     ensure_ascii=False, indent=1), encoding="utf-8")
    (out_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: summary[k] for k in ("network_requests", "cache_hits", "aborted")}, ensure_ascii=False))
    print(f"errores/no-200: {len(summary['network_errors_or_non_200'])}")
    return 1 if aborted else 0


if __name__ == "__main__":
    sys.exit(main())
