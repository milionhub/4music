"""Motor de recomendación de Descubrir (T1.3). Determinista, sin IA generativa, sin datos simulados.

Etapas:
  A. Candidatos por semilla (favorito): afinidad de escucha (ListenBrainz Labs), sello compartido en la misma
     época (MusicBrainz) y lanzamientos conjuntos (MusicBrainz).
  B. Normalización por MBID: se excluyen semillas, excluidos, «Various Artists»/[unknown].
  C. Ranking interpretable: cada señal tiene una fuerza en [0, 1] y se combinan como evidencias independientes
     («noisy-OR»: 1 − Π(1 − fᵢ)). Así, varias evidencias y varios favoritos suman sin superar 1, y una señal
     débil sola no alcanza el umbral.
  D. Explicación: etiqueta y frase según la evidencia más fuerte; se conservan todas las señales y la puntuación.
  E. Diversidad: penalización geométrica por favorito de origen ya representado (reproducible, sin azar).

Fuerzas (justificación):
  - Afinidad Labs 0,50–1,00: la única señal basada en escuchas reales; 0,5 por aparecer en la lista y hasta +0,5
    según su puntuación relativa a la mejor de esa semilla.
  - Sello compartido (2 sellos principales de la semilla; no cuentan los lanzamientos en los que figura la propia
    semilla): ≥2 lanzamientos del candidato en el sello y la época de la semilla → 0,55 (sello pequeño,
    ≤300 lanzamientos en MusicBrainz) o 0,45 (sello grande), +0,05 por cada lanzamiento adicional (máx. +0,15);
    1 lanzamiento en sello pequeño → 0,30. Repetición y
    sellos pequeños indican escena; un sello grande o una aparición aislada, mucho menos.
  - Lanzamientos conjuntos: 1 → 0,30; ≥2 → 0,50. Un solo crédito suele ser un vocalista o invitado puntual
    (caso Arnold Jarvis con Joseph Capriati): no basta por sí solo para recomendar.
  Umbral de publicación: 0,45. Si no hay candidatos que lo superen, se devuelven menos (o ninguno).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app import schemas
from app.normalize import SPECIAL_ARTISTS
from app.profile import base_title

NO_LABEL = "157afde4-4bf5-4039-8ad2-5a15acc85176"  # «[no label]» en MusicBrainz
THRESHOLD = 0.45
DIVERSITY_PENALTY = 0.85
SMALL_LABEL_MAX_RELEASES = 300
ERA_MARGIN_YEARS = 2
LABELS_PER_SEED = 2  # el sello principal suele ser el propio (p. ej. PAWZ); el segundo aporta escena


@dataclass
class SeedData:
    mbid: str
    name: str
    similar: list[dict[str, Any]] = field(default_factory=list)       # filas de Labs (todas las variantes)
    releases: list[dict[str, Any]] = field(default_factory=list)      # lanzamientos de la semilla (labels+credits)
    label_pages: dict[str, dict[str, Any]] = field(default_factory=dict)  # label_mbid → página de lanzamientos


@dataclass
class _Signal:
    kind: str           # affinity | shared_label | collaboration
    seed_mbid: str
    seed_name: str
    strength: float
    detail: str | None = None


def noisy_or(values: list[float]) -> float:
    p = 1.0
    for v in values:
        p *= 1.0 - max(0.0, min(1.0, v))
    return 1.0 - p


def _year(date: Any) -> int | None:
    return int(date[:4]) if isinstance(date, str) and len(date) >= 4 and date[:4].isdigit() else None


def seed_labels(seed: SeedData, limit: int = LABELS_PER_SEED) -> list[tuple[str, str, int]]:
    """Sellos principales de la semilla: (mbid, nombre, primer año de la semilla en el sello). Mínimo 2 lanzamientos."""
    counts: dict[str, list] = {}
    for rel in seed.releases:
        for li in rel.get("label-info") or []:
            label = li.get("label") or {}
            if not isinstance(label.get("id"), str) or label["id"] == NO_LABEL:
                continue
            entry = counts.setdefault(label["id"], [label.get("name") or "", 0, None])
            entry[1] += 1
            y = _year(rel.get("date"))
            if y and (entry[2] is None or y < entry[2]):
                entry[2] = y
    ranked = sorted(((k, v) for k, v in counts.items() if v[1] >= 2), key=lambda kv: (-kv[1][1], kv[1][0]))
    return [(k, v[0], v[2] or 0) for k, v in ranked[:limit]]


def _signals(seed: SeedData) -> dict[str, tuple[dict[str, Any], list[_Signal]]]:
    out: dict[str, tuple[dict[str, Any], list[_Signal]]] = {}

    def add(raw: dict[str, Any], signal: _Signal):
        mbid = raw.get("id")
        if not isinstance(mbid, str) or mbid == seed.mbid or mbid in SPECIAL_ARTISTS or not raw.get("name"):
            return
        out.setdefault(mbid, (raw, []))[1].append(signal)

    # 1. Afinidad de escucha (Labs). Puntuación relativa a la mejor de la semilla, por variante; se queda la mayor.
    by_artist: dict[str, tuple[dict[str, Any], float]] = {}
    for rows in _group_by_algorithm(seed.similar):
        top = max((r["score"] for r in rows), default=0) or 1
        for r in rows:
            strength = 0.5 + 0.5 * (r["score"] / top)
            prev = by_artist.get(r["artist_mbid"])
            if not prev or strength > prev[1]:
                by_artist[r["artist_mbid"]] = ({"id": r["artist_mbid"], "name": r.get("name"),
                                                "disambiguation": r.get("comment") or None, "type": r.get("type")},
                                               strength)
    for raw, strength in by_artist.values():
        add(raw, _Signal("affinity", seed.mbid, seed.name, round(strength, 3)))

    # 2. Lanzamientos conjuntos (créditos del propio lanzamiento, no recopilatorios de terceros).
    joint: dict[str, tuple[dict[str, Any], set[str]]] = {}
    for rel in seed.releases:
        credit = [c.get("artist") or {} for c in rel.get("artist-credit") or []]
        if seed.mbid not in {a.get("id") for a in credit} or not rel.get("title"):
            continue
        for a in credit:
            if isinstance(a.get("id"), str) and a["id"] != seed.mbid:
                joint.setdefault(a["id"], (a, set()))[1].add(base_title(rel["title"]))  # versiones = 1
    for raw, titles in joint.values():
        add(raw, _Signal("collaboration", seed.mbid, seed.name, 0.5 if len(titles) >= 2 else 0.3,
                         detail=sorted(titles)[0]))

    # 3. Sello compartido en la misma época.
    for label_id, label_name, first_year in seed_labels(seed):
        page = seed.label_pages.get(label_id) or {}
        size = page.get("release-count") if isinstance(page.get("release-count"), int) else 10**6
        small = size <= SMALL_LABEL_MAX_RELEASES
        per_artist: dict[str, tuple[dict[str, Any], int]] = {}
        for rel in page.get("releases") or []:
            y = _year(rel.get("date"))
            if y is None or y < first_year - ERA_MARGIN_YEARS:
                continue  # otra época del sello: no es la misma escena
            if seed.mbid in {(c.get("artist") or {}).get("id") for c in rel.get("artist-credit") or []}:
                continue  # lanzamiento de la propia semilla: eso es colaboración, no compañero de sello
            for c in {(c.get("artist") or {}).get("id"): c.get("artist") or {} for c in rel.get("artist-credit") or []}.values():
                if isinstance(c.get("id"), str):
                    raw, n = per_artist.get(c["id"], (c, 0))
                    per_artist[c["id"]] = (raw, n + 1)
        for raw, n in per_artist.values():
            # ≥2 lanzamientos: base 0,55 (sello pequeño) o 0,45 (grande), +0,05 por lanzamiento adicional (máx. +0,15).
            strength = ((0.55 if small else 0.45) + 0.05 * min(n - 2, 3)) if n >= 2 else (0.3 if small else 0.0)
            if strength:
                add(raw, _Signal("shared_label", seed.mbid, seed.name, strength, detail=label_name))
    return out


def _group_by_algorithm(rows: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for r in rows:
        if isinstance(r, dict) and isinstance(r.get("artist_mbid"), str) and isinstance(r.get("score"), (int, float)):
            groups.setdefault(str(r.get("_algorithm", "")), []).append(r)
    return list(groups.values())


TAGS = {"affinity": "Afinidad de escucha", "shared_label": "Sello compartido", "collaboration": "Colaboración",
        "multiple_favorites": "Varios de tus favoritos"}


def _headline(kind: str, s: _Signal, seeds: list[str]) -> str:
    if kind == "multiple_favorites":
        return f"Conecta con {' y '.join(seeds[:2])}" + (f" y {len(seeds) - 2} más" if len(seeds) > 2 else "")
    if s.kind == "affinity":
        return f"Afín a {s.seed_name} según ListenBrainz"
    if s.kind == "shared_label":
        return f"Publica en {s.detail}, como {s.seed_name}"
    return f"Lanzamientos junto a {s.seed_name}"


def _reason_text(s: _Signal) -> str:
    if s.kind == "affinity":
        return f"Quienes escuchan a {s.seed_name} también lo escuchan (ListenBrainz)"
    if s.kind == "shared_label":
        return f"Mismo sello y época que {s.seed_name}: {s.detail}"
    return f"Lanzamiento conjunto con {s.seed_name}"


def recommend(seeds: list[SeedData], exclude: set[str], limit: int) -> list[schemas.Recommendation]:
    blocked = {s.mbid for s in seeds} | exclude | SPECIAL_ARTISTS
    merged: dict[str, tuple[dict[str, Any], list[_Signal]]] = {}
    for seed in seeds:
        for mbid, (raw, sigs) in _signals(seed).items():
            if mbid in blocked:
                continue
            prev = merged.get(mbid)
            merged[mbid] = (prev[0] if prev and prev[0].get("disambiguation") else raw, (prev[1] if prev else []) + sigs)

    scored = []
    for mbid, (raw, sigs) in merged.items():
        per_seed: dict[str, list[float]] = {}
        for s in sigs:
            per_seed.setdefault(s.seed_mbid, []).append(s.strength)
        seed_scores = {k: noisy_or(v) for k, v in per_seed.items()}
        total = noisy_or(list(seed_scores.values()))
        if total < THRESHOLD:
            continue
        strongest = max(sigs, key=lambda s: (s.strength, s.kind == "affinity"))
        primary_seed = max(seed_scores, key=lambda k: (seed_scores[k], k))
        scored.append((total, raw, sigs, strongest, primary_seed, seed_scores))

    # E. Diversidad: greedy con penalización por favorito de origen ya representado.
    scored.sort(key=lambda x: (-x[0], (x[1].get("name") or "").casefold(), x[1]["id"]))
    picked, used = [], {}
    pool = list(scored)
    while pool and len(picked) < limit:
        pool.sort(key=lambda x: (-(x[0] * DIVERSITY_PENALTY ** used.get(x[4], 0)),
                                 (x[1].get("name") or "").casefold(), x[1]["id"]))
        best = pool.pop(0)
        used[best[4]] = used.get(best[4], 0) + 1
        picked.append(best)

    out = []
    for total, raw, sigs, strongest, _primary, seed_scores in picked:
        names = sorted({s.seed_name for s in sigs}, key=lambda n: -max(x.strength for x in sigs if x.seed_name == n))
        kind = "multiple_favorites" if len(seed_scores) >= 2 else strongest.kind
        reasons = sorted(sigs, key=lambda s: -s.strength)
        out.append(schemas.Recommendation(
            artist=schemas.ArtistSummary(mbid=raw["id"], name=raw["name"], disambiguation=raw.get("disambiguation") or None,
                                         type=raw.get("type") or None),
            score=round(total, 3), tag=TAGS[kind], kind=kind, headline=_headline(kind, strongest, names),
            reasons=[schemas.RecommendationReason(kind=s.kind, seed_mbid=s.seed_mbid, seed_name=s.seed_name,
                                                  strength=s.strength, detail=s.detail, text=_reason_text(s))
                     for s in reasons[:4]]))
    return out
