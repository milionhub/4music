"""Evaluador offline: compara las salidas del modelo con referencias manuales. No llama a ninguna API.

    py -3.11 research/poster_ai/evaluate.py                     # salidas de data/outputs/
    py -3.11 research/poster_ai/evaluate.py --variant compact   # salidas de data/outputs/compact/

Referencias: data/references/<nombre>.json (mismo nombre base que la imagen). Formato: ver _template.json.
Se normalizan espacios, mayúsculas y acentos solo para comparar; los textos originales se conservan.
Además se informa de la grafía estricta (exact_spelling / spelling_diffs), sin sustituir a la normalizada.
Una salida con finish_reason "length" no se evalúa (incompleta).
Las coincidencias aproximadas se listan para revisión humana y NO cuentan como acierto.
"""

from __future__ import annotations

import argparse
import difflib
import json
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REFS = ROOT / "data" / "references"
OUTPUTS = ROOT / "data" / "outputs"
NEAR = 0.85  # similitud a partir de la cual se pide revisión humana


def norm(s: str | None) -> str:
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c))
    return " ".join(s.casefold().split())


def strict(s: str | None) -> str:
    """Solo colapsa espacios y unifica la forma Unicode (NFC); no toca mayúsculas ni diacríticos."""
    return " ".join(unicodedata.normalize("NFC", s or "").split())


def similar(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, norm(a), norm(b)).ratio()


def compare_text(pred: str | None, ref: str | None, variants: list[str] | None = None) -> str:
    if pred is None and ref is None:
        return "both_null"
    if pred is None:
        return "omitted"
    if ref is None:
        return "not_in_reference"
    if norm(pred) in {norm(ref)} | {norm(v) for v in variants or []}:
        return "match"
    return "needs_review" if similar(pred, ref) >= NEAR else "mismatch"


def match_artists(pred: list[dict], ref: list[dict]) -> dict:
    ref_keys = []
    for r in ref:  # variantes aceptadas por una persona en la referencia
        ref_keys.append({norm(r["name"])} | {norm(v) for v in r.get("accepted_variants", [])})
    used, pairs, unmatched = set(), [], []
    for p in pred:
        idx = next((i for i, keys in enumerate(ref_keys) if i not in used and norm(p["name"]) in keys), None)
        if idx is None:
            unmatched.append(p)
        else:
            used.add(idx)
            pairs.append((p, ref[idx]))
    near, invented = [], []
    for p in unmatched:
        best = max(((similar(p["name"], r["name"]), i) for i, r in enumerate(ref) if i not in used), default=(0, None))
        (near if best[0] >= NEAR else invented).append(
            {"predicted": p["name"], "closest_reference": ref[best[1]]["name"] if best[1] is not None else None,
             "similarity": round(best[0], 3), "uncertain_flag": p.get("uncertain")})
    omitted = [r["name"] for i, r in enumerate(ref) if i not in used]
    tp = len(pairs)
    detail = {f: {"correct": 0, "wrong": [], "evaluated": 0, "invented": []} for f in ("stage", "time")}
    for p, r in pairs:
        for field in ("stage", "time"):
            if r.get(field) is None and p.get(field) is not None:  # p. ej. horario individual no impreso
                detail[field]["invented"].append({"artist": r["name"], "predicted": p[field]})
            if r.get(field) is not None:
                detail[field]["evaluated"] += 1
                res = compare_text(p.get(field), r[field])
                if res == "match":
                    detail[field]["correct"] += 1
                else:
                    detail[field]["wrong"].append({"artist": r["name"], "predicted": p.get(field),
                                                   "reference": r[field], "result": res})
    # Grafía estricta (complementa a la normalizada): mayúsculas, acentos y símbolos deben coincidir tal cual.
    spelling_diffs = [{"predicted": p["name"], "reference": r["name"]} for p, r in pairs
                      if strict(p["name"]) not in {strict(r["name"])} | {strict(v) for v in r.get("accepted_variants", [])}]
    return {
        "reference_count": len(ref), "predicted_count": len(pred), "correct": tp,
        "exact_spelling": tp - len(spelling_diffs), "spelling_diffs": spelling_diffs,
        "omitted": omitted, "invented": invented, "needs_review": near,
        "precision": round(tp / len(pred), 3) if pred else None,
        "recall": round(tp / len(ref), 3) if ref else None,
        "flagged_uncertain": sum(1 for p in pred if p.get("uncertain")),
        "stage": detail["stage"], "time": detail["time"],
    }


def compare_dates(pred: list[dict], ref: list[dict]) -> dict:
    """Coincide si ambos tienen iso y es igual o, si la referencia no tiene iso (p. ej. un rango), por texto."""
    def same(p, r):
        if r.get("iso") and p.get("iso"):
            return p["iso"] == r["iso"]
        return norm(p.get("text")) == norm(r.get("text"))
    used, missing = set(), []
    for r in ref:
        i = next((i for i, p in enumerate(pred) if i not in used and same(p, r)), None)
        if i is None:
            missing.append(r.get("text"))
        else:
            used.add(i)
    extra = [p.get("text") for i, p in enumerate(pred) if i not in used]
    return {"reference": [r.get("text") for r in ref], "predicted": [p.get("text") for p in pred],
            "correct": len(used), "missing": missing, "extra": extra, "exact": not missing and not extra}


def _date_matches(pred: dict | None, ref: dict | None) -> bool:
    if not ref:
        return not pred
    if not pred:
        return False
    if pred.get("iso") and ref.get("iso"):
        return pred["iso"] == ref["iso"]
    return norm(ref.get("text")) in norm(pred.get("text"))


def _label_matches(pred: str | None, ref: str | None) -> bool:
    a, b = norm(pred), norm(ref)
    return a == b or (bool(a) and bool(b) and (a in b or b in a))


def compare_sessions(pred: list[dict], ref: list[dict]) -> dict:
    """Empareja bloques por fecha + escenario (y etiqueta si hay varios); compara hora y artistas asignados."""
    used, matched, missing = set(), [], []
    for r in ref:
        cands = [i for i, p in enumerate(pred) if i not in used and _date_matches(p.get("date"), r.get("date"))
                 and norm(p.get("stage")) == norm(r.get("stage"))]
        # Si ambos tienen etiqueta (p. ej. DAYTIME/NIGHTTIME del mismo día), deben ser compatibles.
        cands = [i for i in cands if not (r.get("label") and pred[i].get("label"))
                 or _label_matches(pred[i].get("label"), r.get("label"))]
        if not cands:
            missing.append({"date": r.get("date"), "label": r.get("label"), "stage": r.get("stage")})
            continue
        i = cands[0]
        used.add(i)
        p = pred[i]
        pa, ra = {norm(x) for x in p.get("artists", [])}, {norm(x) for x in r.get("artists", [])}
        matched.append({"date": r.get("date"), "label": r.get("label"), "stage": r.get("stage"),
                        "time": compare_text(p.get("time"), r.get("time")),
                        "artists_correct": len(pa & ra), "artists_reference": len(ra),
                        "artists_missing": sorted(x for x in r.get("artists", []) if norm(x) not in pa),
                        "artists_extra": sorted(x for x in p.get("artists", []) if norm(x) not in ra)})
    ref_pairs = sum(len(r.get("artists", [])) for r in ref)
    ok_pairs = sum(m["artists_correct"] for m in matched)
    return {"reference": len(ref), "predicted": len(pred), "matched": len(matched), "missing": missing,
            "extra": len(pred) - len(used),
            "time_correct": sum(1 for m in matched if m["time"] in ("match", "both_null")),
            "artist_assignment_recall": round(ok_pairs / ref_pairs, 3) if ref_pairs else None, "detail": matched}


def compare_b2b(pred: list[dict], ref: list[dict]) -> dict:
    """Compara las relaciones B2B como conjuntos de nombres (el orden impreso no se evalúa)."""
    def key(b):
        return frozenset(norm(x) for x in b.get("artists", []))
    pk, rk = [key(b) for b in pred], [key(b) for b in ref]
    return {"reference": len(ref), "predicted": len(pred), "correct": len(set(pk) & set(rk)),
            "missing": [b.get("text") or " B2B ".join(b["artists"]) for b, k in zip(ref, rk) if k not in pk],
            "extra": [b.get("text") or " B2B ".join(b.get("artists", [])) for b, k in zip(pred, pk) if k not in rk]}


def evaluate_one(output: dict, ref: dict) -> dict:
    complete = output.get("finish_reason") != "length"  # salida cortada: incompleta aunque el JSON se lea
    ext = output.get("extraction") if (output.get("json_valid") and not output.get("schema_errors")
                                       and complete) else None
    res = {"image": output.get("image"), "variant": output.get("variant", "original"),
           "json_valid": output.get("json_valid"), "complete": complete,
           "schema_errors": output.get("schema_errors"), "latency_s": output.get("latency_s"),
           "usage": output.get("usage"), "finish_reason": output.get("finish_reason"),
           "review": output.get("review", [])}
    if ext is None:
        res["evaluated"] = False
        return res
    res.update({
        "evaluated": True,
        "event_name": compare_text(ext.get("event_name"), ref.get("event_name"), ref.get("event_name_variants")),
        "location": compare_text(ext.get("location"), ref.get("location"), ref.get("location_variants")),
        "dates": compare_dates(ext.get("dates", []), ref.get("dates", [])),
        "artists": match_artists(ext.get("artists", []), ref.get("artists", [])),
        "stages_predicted": ext.get("stages", []), "stages_reference": ref.get("stages", []),
        "unreadable_text": ext.get("unreadable_text", []),
    })
    if ref.get("sessions"):
        res["sessions"] = compare_sessions(ext.get("sessions", []), ref["sessions"])
    if ref.get("b2b") or ext.get("b2b"):
        res["b2b"] = compare_b2b(ext.get("b2b", []), ref.get("b2b", []))
    return res


def aggregate(results: list[dict]) -> dict:
    ev = [r for r in results if r.get("evaluated")]
    tp = sum(r["artists"]["correct"] for r in ev)
    pred = sum(r["artists"]["predicted_count"] for r in ev)
    ref = sum(r["artists"]["reference_count"] for r in ev)
    tokens = [r["usage"] for r in results if r.get("usage")]
    return {
        "posters": len(results), "evaluated": len(ev),
        "json_valid": sum(1 for r in results if r.get("json_valid") and not r.get("schema_errors")),
        "complete": sum(1 for r in results if r.get("complete", True)),
        "artists_correct": tp, "artists_predicted": pred, "artists_reference": ref,
        "artists_exact_spelling": sum(r["artists"]["exact_spelling"] for r in ev),
        "artists_omitted": sum(len(r["artists"]["omitted"]) for r in ev),
        "artists_invented": sum(len(r["artists"]["invented"]) for r in ev),
        "artists_needs_review": sum(len(r["artists"]["needs_review"]) for r in ev),
        "precision": round(tp / pred, 3) if pred else None, "recall": round(tp / ref, 3) if ref else None,
        "event_name_match": sum(1 for r in ev if r["event_name"] == "match"),
        "dates_exact": sum(1 for r in ev if r["dates"]["exact"]),
        "invented_individual_times": sum(len(r["artists"]["time"]["invented"]) for r in ev),
        "sessions_matched": sum(r["sessions"]["matched"] for r in ev if "sessions" in r),
        "sessions_reference": sum(r["sessions"]["reference"] for r in ev if "sessions" in r),
        "b2b_correct": sum(r["b2b"]["correct"] for r in ev if "b2b" in r),
        "b2b_reference": sum(r["b2b"]["reference"] for r in ev if "b2b" in r),
        "latency_s": [r["latency_s"] for r in results],
        "prompt_tokens": sum(t.get("prompt_tokens") or 0 for t in tokens),
        "completion_tokens": sum(t.get("completion_tokens") or 0 for t in tokens),
    }


def main(argv: list[str] | None = None) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--variant", default="original", help="original (data/outputs/) o compact (data/outputs/compact/)")
    args = ap.parse_args(argv)
    outputs = OUTPUTS if args.variant == "original" else OUTPUTS / args.variant
    refs = {p.stem: p for p in sorted(REFS.glob("*.json")) if not p.name.startswith("_")}
    results, missing = [], []
    for stem, ref_path in refs.items():
        out_path = outputs / f"{stem}.json"
        if not out_path.exists():
            missing.append(stem)
            continue
        results.append(evaluate_one(json.loads(out_path.read_text(encoding="utf-8")),
                                    json.loads(ref_path.read_text(encoding="utf-8"))))
    report = {"results": results, "aggregate": aggregate(results), "references_without_output": missing}
    outputs.mkdir(parents=True, exist_ok=True)
    (outputs / "_evaluation.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(report["aggregate"], ensure_ascii=False))
    if missing:
        print(f"Referencias sin salida del modelo: {missing}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
