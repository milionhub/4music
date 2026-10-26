"""TrackDNA de canciones (T2.0). Funciones puras sobre respuestas de MusicBrainz y Wikidata ya obtenidas.

Reglas de honestidad:
- Nada se rellena por aproximación: lo que falta queda en null, [] o como rasgo «unavailable».
- BPM, tonalidad y energía no tienen fuente autorizada (AcousticBrainz congelado desde 2022 y descartado en la
  Fase 1): siempre «unavailable». Nunca se estiman con IA.
- Los géneros y tags de MusicBrainz no se usan (CC BY-NC-SA, excluidos en docs/t0). El género sale solo de
  Wikidata (CC0) y siempre indica a qué se refiere: la grabación, el lanzamiento o el artista.
- Sello: «[no label]» es una autoedición documentada; un `label-info` vacío es solo falta de datos (nunca se
  deduce autoedición de él).
- Identificadores para cruces futuros (T2.1 §F): solo MBID, ISRC, barcode y URL documentadas en MusicBrainz.
  Nunca por nombre: los artistas cambian de nombre y las plataformas tardan en recogerlo (Chris Stussy → Chris Stassy).
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any

from app import schemas
from app.links import external_id, is_dead, normalize_links
from app.normalize import SPECIAL_ARTISTS, artist_summary, credited_artists, lucene_escape
from app.wikidata import WikidataInfo

SEARCH_FETCH = 100               # candidatos que se piden a MusicBrainz para agrupar y ordenar aquí
LENGTH_TOLERANCE_MS = 3000       # misma canción en dos grabaciones: duraciones casi idénticas
RELEASES_LIMIT = 10
LABELS_LIMIT = 4
RELATED_LIMIT = 5
LINK_RELEASES = 5                # lanzamientos propios cuyos enlaces se muestran (los mejor situados)
BARCODES_LIMIT = 5
NO_LABEL = "157afde4-4bf5-4039-8ad2-5a15acc85176"  # «[no label]» en MusicBrainz: autoedición documentada
SELF_RELEASED = "Autoedición"
COMPILATION_TYPES = {"Compilation", "DJ-mix"}
COVER_RG = "https://coverartarchive.org/release-group/{mbid}/front-250"
COVER_RELEASE = "https://coverartarchive.org/release/{mbid}/front-{size}"

SEPARATOR_RE = re.compile(r"\s+[-–—]\s+")
OPERATOR_RE = re.compile(r"\b(AND|OR|NOT)\b")
TOKEN_RE = re.compile(r"[^\W_]+", re.UNICODE)
# Fragmentos de grabación que solo existen dentro de un DJ mix («part of “X” DJ‐mix»): no son la canción en sí.
MIX_FRAGMENT_RE = re.compile(r"\bDJ[\s\-‐‑]?mix\b", re.IGNORECASE)
LIVE_RE = re.compile(r"^live\b", re.IGNORECASE)
MIX_NAME_RE = re.compile(r"part of [“\"«](.+?)[”\"»]", re.IGNORECASE)
# Sufijo de versión al final del título: «(Layton Giordani remix)», «[Extended Mix]», « - Radio Edit».
SUFFIX_RE = re.compile(r"\s*(?:[\(\[]([^\(\)\[\]]+)[\)\]]|\s-\s([^-]+))\s*$")
VERSION_WORD_RE = re.compile(
    r"\b(mix|edit|remix|rmx|rework|re-?edit|version|dub|bootleg|vip|live|instrumental|a ?capp?ella|remaster(ed)?|flip)\b",
    re.IGNORECASE)
ORIGINAL_VERSIONS = {"original mix", "original", "original version"}
OWN_PRIMARY_TYPES = {"Single", "EP", "Album"}
NON_ORIGINAL_SECONDARY = {"Compilation", "DJ-mix", "Live", "Mixtape/Street", "Remix", "Soundtrack", "Demo"}

ROLE_LABELS = {
    "producer": "Producción", "remixer": "Remezcla", "composer": "Composición", "writer": "Autoría",
    "lyricist": "Letra", "vocal": "Voz", "instrument": "Instrumentos", "performer": "Interpretación",
    "programming": "Programación", "arranger": "Arreglos", "mix": "Mezcla", "engineer": "Ingeniería",
    "audio": "Ingeniería", "mastering": "Masterización",
}
WORK_ROLES = {"composer", "writer", "lyricist"}


def _str(value: Any) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def _fold(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text or "")
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch)).casefold()


def _tokens(text: str) -> set[str]:
    return set(TOKEN_RE.findall(_fold(text)))


def credit_text(raw: dict[str, Any]) -> str:
    """Crédito tal como lo escribe MusicBrainz: «A feat. B», «A & B»."""
    return "".join((c.get("name") or (c.get("artist") or {}).get("name") or "") + (c.get("joinphrase") or "")
                   for c in raw.get("artist-credit") or [] if isinstance(c, dict)).strip()


def _credit_ids(raw: dict[str, Any]) -> frozenset[str]:
    return frozenset((c.get("artist") or {}).get("id") for c in raw.get("artist-credit") or []
                     if isinstance(c, dict) and isinstance((c.get("artist") or {}).get("id"), str))


def _length(raw: dict[str, Any]) -> int | None:
    value = raw.get("length")
    return value if isinstance(value, int) and value > 0 else None


# Palabras que no identifican una canción: versiones y nexos. No cuentan para exigir que un resultado las contenga.
NEUTRAL_TOKENS = {"remix", "mix", "edit", "extended", "original", "radio", "version", "feat", "ft", "featuring", "vs",
                  "and", "the", "a", "de", "el", "la", "y", "dub", "club", "rework"}


def _near(a: str, b: str) -> bool:
    """Misma palabra o una errata (una letra cambiada, sobrante o que falta) en palabras de 5 letras o más."""
    if a == b:
        return True
    if min(len(a), len(b)) < 5 or abs(len(a) - len(b)) > 1:
        return False
    if len(a) == len(b):
        return sum(x != y for x, y in zip(a, b)) == 1
    short, long_ = sorted((a, b), key=len)
    return any(long_[:i] + long_[i + 1:] == short for i in range(len(long_)))


def covers_query(query_tokens: set[str], title: str, credit: str) -> bool:
    """Un resultado responde a la búsqueda si contiene todas sus palabras significativas (tolerando una errata)."""
    words = _tokens(title) | _tokens(credit)
    required = query_tokens - NEUTRAL_TOKENS
    return all(any(_near(q, w) for w in words) for q in required)


def fuzzy_query(q: str) -> str:
    """Segunda oportunidad cuando la búsqueda exacta no encuentra nada: términos difusos (una errata) en título y
    artista. Los resultados siguen pasando el filtro de `covers_query`: nunca una coincidencia vaga."""
    words = [lucene_escape(w) for w in re.split(r"\s+[-–—]\s+|\s+", OPERATOR_RE.sub(lambda m: m.group(1).lower(), q.strip())) if w]
    terms = " ".join(f"{w}~1" if len(w) >= 5 else w for w in words)
    return f"recording:({terms}) OR (recording:({terms}) AND artist:({terms}))"


def build_query(q: str) -> str:
    """«Artista - Canción» (o al revés) busca por campos; sin separador, título exacto o palabras en título+artista."""
    q = OPERATOR_RE.sub(lambda m: m.group(1).lower(), q.strip())
    parts = SEPARATOR_RE.split(q, maxsplit=1)
    if len(parts) == 2 and parts[0].strip() and parts[1].strip():
        a, b = (lucene_escape(p.strip()) for p in parts)
        return f"(recording:({b}) AND artist:({a}))^2 OR (recording:({a}) AND artist:({b}))"
    t = lucene_escape(q)
    return f'recording:"{t}"^3 OR (recording:({t}) AND artist:({t}))'


def version_label(title: str, disambiguation: str | None = None, video: bool = False) -> str | None:
    """Versión según el título (sufijo con «remix», «edit», «extended mix»…) o la desambiguación de MusicBrainz."""
    m = SUFFIX_RE.search(title or "")
    suffix = (m.group(1) or m.group(2) or "").strip() if m else ""
    if suffix and VERSION_WORD_RE.search(suffix):
        return suffix[0].upper() + suffix[1:]
    if disambiguation and LIVE_RE.match(disambiguation):
        return "Directo"
    if video:
        return "Vídeo"
    return None


def _core_title(title: str) -> str:
    m = SUFFIX_RE.search(title or "")
    if m and VERSION_WORD_RE.search(m.group(1) or m.group(2) or ""):
        return title[:m.start()]
    return title


# --- Lanzamientos -------------------------------------------------------------------------------------------------
def _release_rank(r: dict[str, Any], credit_ids: frozenset[str]) -> tuple:
    """Orden para elegir el lanzamiento original: propio, sin tipo secundario de recopilatorio/directo, oficial,
    single/EP/álbum y, entre esos, el de fecha más antigua."""
    rg = r.get("release-group") or {}
    secondary = set(rg.get("secondary-types") or [])
    return (not (credit_ids & _credit_ids(r)), bool(secondary & NON_ORIGINAL_SECONDARY),
            r.get("status") not in (None, "Official"), rg.get("primary-type") not in OWN_PRIMARY_TYPES,
            _str(r.get("date")) or "9999", r.get("id") or "")


def choose_release(releases: list[dict[str, Any]], credit_ids: frozenset[str]) -> dict[str, Any] | None:
    valid = [r for r in releases if isinstance(r, dict) and isinstance(r.get("id"), str) and r.get("title")]
    return min(valid, key=lambda r: _release_rank(r, credit_ids)) if valid else None


def _label_names(r: dict[str, Any]) -> list[str]:
    out = []
    for info in r.get("label-info") or []:
        name = _str(((info or {}).get("label") or {}).get("name"))
        if name and not name.startswith("[") and name not in out:  # «[no label]» no es un sello
            out.append(name)
    return out


def _self_released(r: dict[str, Any]) -> bool:
    """La edición declara expresamente «[no label]» (por MBID o, si falta, por nombre)."""
    for info in r.get("label-info") or []:
        label = (info or {}).get("label") or {}
        if label.get("id") == NO_LABEL or (not label.get("id") and _str(label.get("name")) == "[no label]"):
            return True
    return False


def _own_original(r: dict[str, Any], credit_ids: frozenset[str]) -> bool:
    """Lanzamiento del artista de la canción que no es un recopilatorio ni un DJ mix."""
    rg = r.get("release-group") or {}
    return bool(credit_ids & _credit_ids(r)) and not set(rg.get("secondary-types") or []) & COMPILATION_TYPES


def earliest_date(dates: list[str]) -> str | None:
    """Fecha más antigua; si otra edición precisa más esa misma fecha («2009» → «2009-09-22»), se usa la precisa."""
    ordered = sorted(d for d in dates if d)
    if not ordered:
        return None
    best = ordered[0]
    for d in ordered:
        if d.startswith(best) and len(d) > len(best):
            best = d
    return best


def _has_front(r: dict[str, Any]) -> bool:
    return bool((r.get("cover-art-archive") or {}).get("front"))


def releases(raw_releases: list[dict[str, Any]], credit_ids: frozenset[str], covers: bool
             ) -> tuple[list[schemas.TrackRelease], schemas.TrackRelease | None, dict[str, Any] | None, int]:
    """Agrupa las ediciones por grupo de lanzamientos. Devuelve (grupos ordenados, original, edición original,
    número total de grupos). La portada solo se enlaza si Cover Art Archive declara una portada frontal."""
    valid = [r for r in raw_releases if isinstance(r, dict) and isinstance(r.get("id"), str) and r.get("title")]
    by_group: dict[str, list[dict[str, Any]]] = {}
    for r in sorted(valid, key=lambda r: _release_rank(r, credit_ids)):
        rg_id = (r.get("release-group") or {}).get("id")
        by_group.setdefault(rg_id if isinstance(rg_id, str) else r["id"], []).append(r)
    original_raw = choose_release(valid, credit_ids)
    groups: list[schemas.TrackRelease] = []
    original: schemas.TrackRelease | None = None
    for rg_id, items in by_group.items():
        first = items[0]  # la mejor edición del grupo según el mismo criterio
        rg = first.get("release-group") or {}
        date = earliest_date([d for d in (_str(r.get("date")) for r in items) if d])
        labels: list[str] = []
        formats: list[str] = []
        for r in items:
            labels += [n for n in _label_names(r) if n not in labels]
            for medium in r.get("media") or []:
                fmt = _str((medium or {}).get("format"))
                if fmt and fmt not in formats:
                    formats.append(fmt)
        catalog = next((_str(i.get("catalog-number")) for i in first.get("label-info") or [] if _str((i or {}).get("catalog-number"))), None)
        cover_release = next((r for r in items if _has_front(r)), None)
        group = schemas.TrackRelease(
            mbid=rg_id, title=_str(rg.get("title")) or first["title"], primary_type=_str(rg.get("primary-type")),
            secondary_types=[t for t in rg.get("secondary-types") or [] if isinstance(t, str)],
            date=date, labels=labels[:LABELS_LIMIT], catalog_number=catalog, formats=formats[:4],
            self_released=not labels and any(_self_released(r) for r in items),
            own=any(credit_ids & _credit_ids(r) for r in items),
            cover_url=COVER_RELEASE.format(mbid=cover_release["id"], size=250) if covers and cover_release else None,
            url=f"https://musicbrainz.org/release-group/{rg_id}" if isinstance(rg.get("id"), str)
            else f"https://musicbrainz.org/release/{rg_id}")
        groups.append(group)
        if original_raw is not None and any(r["id"] == original_raw["id"] for r in items):
            original = group
    groups.sort(key=lambda g: (not g.own, bool(set(g.secondary_types) & NON_ORIGINAL_SECONDARY), g.date or "9999"))
    return groups, original, original_raw, len(groups)


def hero_cover(raw_releases: list[dict[str, Any]], original_raw: dict[str, Any] | None,
               credit_ids: frozenset[str], covers: bool) -> tuple[str | None, str | None]:
    """Portada grande: la de la edición original si existe; si no, la de la mejor edición que tenga portada."""
    if not covers:
        return None, None
    candidates = ([original_raw] if original_raw else []) + sorted(
        (r for r in raw_releases if isinstance(r, dict) and isinstance(r.get("id"), str)),
        key=lambda r: _release_rank(r, credit_ids))
    chosen = next((r for r in candidates if _has_front(r)), None)
    return (COVER_RELEASE.format(mbid=chosen["id"], size=500), chosen["id"]) if chosen else (None, None)


# --- Búsqueda -----------------------------------------------------------------------------------------------------
@dataclass
class _Candidate:
    raw: dict[str, Any]
    title: str
    ids: frozenset[str]
    credit: str
    length: int | None
    disambiguation: str
    video: bool
    score: int
    releases: dict[str, dict[str, Any]] = field(default_factory=dict)
    isrcs: frozenset[str] = frozenset()

    @property
    def date(self) -> str:
        return _str(self.raw.get("first-release-date")) or "9999"


def version_kind(title: str, disambiguation: str | None = None, video: bool = False) -> str | None:
    """Tipo de versión comparable: «Original mix» equivale a no indicar versión; el resto se compara tal cual."""
    label = version_label(title, disambiguation, video)
    folded = " ".join(_fold(label).split()) if label else None
    return None if folded in ORIGINAL_VERSIONS else folded


def _merge_by_isrc(groups: list[list[_Candidate]]) -> list[list[_Candidate]]:
    """Une grupos que comparten ISRC solo si además coinciden los artistas (MBID), el tipo de versión, el vídeo y
    la duración (±3 s). Así «Hoodlum» y «Hoodlum (original mix)» se unen, pero un remix, un edit o un directo
    con el ISRC mal asignado siguen aparte."""
    def compatible(a: list[_Candidate], b: list[_Candidate]) -> bool:
        x, y = a[0], b[0]
        if x.ids != y.ids or x.video != y.video:
            return False
        if version_kind(x.title, x.disambiguation, x.video) != version_kind(y.title, y.disambiguation, y.video):
            return False
        if not (frozenset().union(*(c.isrcs for c in a)) & frozenset().union(*(c.isrcs for c in b))):
            return False
        la, lb = [c.length for c in a if c.length], [c.length for c in b if c.length]
        return bool(la and lb) and all(abs(p - q) <= LENGTH_TOLERANCE_MS for p in la for q in lb)

    out: list[list[_Candidate]] = []
    for group in groups:
        target = next((g for g in out if compatible(g, group)), None)
        if target is None:
            out.append(group)
        else:
            target.extend(group)
    return out


def search_results(data: dict[str, Any], query: str, limit: int, covers: bool
                   ) -> tuple[list[schemas.TrackSearchResult], int]:
    """Ordena y agrupa candidatos de MusicBrainz. Devuelve (resultados, fragmentos de DJ mix omitidos).

    - Se omiten los fragmentos de DJ mix (desambiguación «part of … DJ-mix»).
    - Se fusionan solo grabaciones con el mismo título exacto, los mismos artistas (por MBID), la misma
      desambiguación y duraciones casi idénticas: remixes, edits, directos y vídeos nunca se mezclan.
    - Después se unen las que comparten ISRC con los mismos artistas, el mismo tipo de versión y la misma
      duración (p. ej. «Hoodlum» y «Hoodlum (original mix)»).
    - Orden: cubre todas las palabras de la búsqueda > título exacto > no directo/vídeo > más lanzamientos.
    """
    query_tokens = _tokens(query)
    candidates: list[_Candidate] = []
    omitted = 0
    for raw in data.get("recordings") or []:
        if not isinstance(raw, dict) or not isinstance(raw.get("id"), str) or not _str(raw.get("title")):
            continue
        disambiguation = _str(raw.get("disambiguation")) or ""
        if MIX_FRAGMENT_RE.search(disambiguation):
            omitted += 1
            continue
        score = raw.get("score")
        candidates.append(_Candidate(
            raw=raw, title=raw["title"].strip(), ids=_credit_ids(raw), credit=credit_text(raw), length=_length(raw),
            disambiguation=disambiguation, video=bool(raw.get("video")), score=score if isinstance(score, int) else 0,
            releases={r["id"]: r for r in raw.get("releases") or [] if isinstance(r, dict) and isinstance(r.get("id"), str)},
            isrcs=frozenset(i for i in raw.get("isrcs") or [] if isinstance(i, str))))

    def coverage(c: _Candidate) -> float:
        return len(query_tokens & (_tokens(c.title) | _tokens(c.credit))) / len(query_tokens) if query_tokens else 0.0

    best = max((coverage(c) for c in candidates), default=0.0)
    if len(query_tokens - NEUTRAL_TOKENS) >= 2:
        # Varias palabras (artista + título): solo resultados que las contienen todas. Si ninguno, no hay resultados:
        # «Arapu Playground» no debe devolver «Ivory Playground» (V5.2).
        candidates = [c for c in candidates if covers_query(query_tokens, c.title, c.credit)]
    elif best >= 0.5:  # si nada cubre la mitad de la búsqueda, se respeta el orden de MusicBrainz (alias, grafías)
        candidates = [c for c in candidates if coverage(c) >= best - 1e-9]

    # Peso de cada artista en el conjunto: agrupa primero las versiones del artista con más presencia (homónimos).
    artist_mass: dict[frozenset[str], int] = {}
    for c in candidates:
        artist_mass[c.ids] = artist_mass.get(c.ids, 0) + len(c.releases)

    groups: list[list[_Candidate]] = []
    by_key: dict[tuple, list[list[_Candidate]]] = {}
    for c in sorted(candidates, key=lambda c: c.length is None):  # las que no tienen duración se unen al final
        key = (" ".join(_fold(c.title).split()), c.ids, _fold(c.disambiguation), c.video)
        for group in by_key.get(key, []):
            lengths = [x.length for x in group if x.length]
            if c.length is None or not lengths or any(abs(c.length - n) <= LENGTH_TOLERANCE_MS for n in lengths):
                group.append(c)
                break
        else:
            group = [c]
            groups.append(group)
            by_key.setdefault(key, []).append(group)
    groups = _merge_by_isrc(groups)

    def summary(group: list[_Candidate]) -> tuple[tuple, schemas.TrackSearchResult]:
        rep = sorted(group, key=lambda c: (-len(c.releases), c.length is None, c.date, c.raw["id"]))[0]
        all_releases = {rid: r for c in group for rid, r in c.releases.items()}
        rest = query_tokens - _tokens(rep.credit)
        core, full = _tokens(_core_title(rep.title)), _tokens(rep.title)
        title_class = 0 if rest and core == rest else 1 if rest and rest <= full else 2
        penalty = int(bool(LIVE_RE.match(rep.disambiguation))) + int(rep.video)
        release = choose_release(list(all_releases.values()), rep.ids)
        rg = (release or {}).get("release-group") or {}
        rank = (-max(coverage(c) for c in group), title_class, penalty, -artist_mass.get(rep.ids, 0), -len(all_releases),
                -max(c.score for c in group), rep.date, rep.raw["id"])
        return rank, schemas.TrackSearchResult(
            mbid=rep.raw["id"], title=rep.title, artist_credit=credited_artists(rep.raw), artist_name=rep.credit,
            artist_disambiguation=next((_str((c.get("artist") or {}).get("disambiguation"))
                                        for c in rep.raw.get("artist-credit") or [] if isinstance(c, dict)), None),
            length_ms=rep.length or next((c.length for c in group if c.length), None),
            first_release_date=min((c.date for c in group), default="9999").replace("9999", "") or None,
            disambiguation=rep.disambiguation or None,
            version=version_label(rep.title, rep.disambiguation, rep.video),
            release_title=_str((release or {}).get("title")), release_type=_str(rg.get("primary-type")),
            cover_url=COVER_RG.format(mbid=rg["id"]) if covers and isinstance(rg.get("id"), str) else None,
            merged_count=len(group), release_count=len(all_releases))

    ranked = sorted((summary(g) for g in groups), key=lambda x: x[0])
    return [result for _, result in ranked[:limit]], omitted


# --- Ficha --------------------------------------------------------------------------------------------------------
def credits(raw: dict[str, Any]) -> list[schemas.TrackCredit]:
    """Créditos documentados en MusicBrainz: relaciones artista→grabación y autoría de la obra interpretada."""
    by_role: dict[str, list[schemas.ArtistSummary]] = {}

    def add(role: str, artist: dict[str, Any]):
        if role not in ROLE_LABELS or not isinstance(artist.get("id"), str) or not artist.get("name") \
                or artist["id"] in SPECIAL_ARTISTS:
            return
        people = by_role.setdefault(role, [])
        if all(p.mbid != artist["id"] for p in people):
            people.append(artist_summary(artist))

    for rel in raw.get("relations") or []:
        if not isinstance(rel, dict):
            continue
        if rel.get("target-type") == "artist" and rel.get("direction") == "backward":
            add(rel.get("type") or "", rel.get("artist") or {})
        elif rel.get("target-type") == "work" and rel.get("type") == "performance":
            for wrel in (rel.get("work") or {}).get("relations") or []:
                if isinstance(wrel, dict) and wrel.get("target-type") == "artist" and wrel.get("type") in WORK_ROLES:
                    add(wrel["type"], wrel.get("artist") or {})
    merged: dict[str, list[schemas.ArtistSummary]] = {}
    for role in ROLE_LABELS:  # orden fijo; «engineer» y «audio» comparten etiqueta
        for person in by_role.get(role, []):
            people = merged.setdefault(ROLE_LABELS[role], [])
            if all(p.mbid != person.mbid for p in people):
                people.append(person)
    return [schemas.TrackCredit(role=role, artists=people) for role, people in merged.items()]


def _link(rec: dict[str, Any]) -> schemas.TrackLink | None:
    if not isinstance(rec.get("id"), str) or not _str(rec.get("title")):
        return None
    return schemas.TrackLink(mbid=rec["id"], title=rec["title"].strip(), artist_name=credit_text(rec),
                             length_ms=_length(rec))


def relations(raw: dict[str, Any], groups: list[schemas.TrackRelease]) -> schemas.TrackRelations:
    """Remezclas/edits en ambos sentidos, samples, mashups, cover de una obra y DJ mixes que la incluyen.
    En MusicBrainz, el sentido «forward» parte de esta grabación: «remix» forward = esta es la versión;
    «samples material» forward = esta toma samples de la otra; backward, al revés."""
    remix_of: dict[str, schemas.TrackLink] = {}
    remixes: dict[str, schemas.TrackLink] = {}
    samples: dict[str, schemas.TrackLink] = {}
    sampled_by: dict[str, schemas.TrackLink] = {}
    mashups: dict[str, schemas.TrackLink] = {}
    cover_of: str | None = None
    cover_writers: list[str] = []
    mixes: dict[str, str] = {}
    for rel in raw.get("relations") or []:
        # Cover: la interpretación de la obra lleva el atributo «cover» (dato de MusicBrainz, no una deducción).
        if isinstance(rel, dict) and rel.get("target-type") == "work" and rel.get("type") == "performance" \
                and "cover" in (rel.get("attributes") or []) and cover_of is None:
            work = rel.get("work") or {}
            cover_of = _str(work.get("title"))
            for wrel in work.get("relations") or []:
                name = _str(((wrel or {}).get("artist") or {}).get("name")) if isinstance(wrel, dict) else None
                if name and wrel.get("type") in WORK_ROLES and name not in cover_writers:
                    cover_writers.append(name)
    for rel in raw.get("relations") or []:
        if not isinstance(rel, dict) or rel.get("target-type") != "recording":
            continue
        link = _link(rel.get("recording") or {})
        if not link:
            continue
        kind, direction = rel.get("type"), rel.get("direction")
        if kind in ("remix", "edit"):
            (remix_of if direction == "forward" else remixes).setdefault(link.mbid, link)
        elif kind == "samples material":
            (samples if direction == "forward" else sampled_by).setdefault(link.mbid, link)
        elif kind == "mashes up":
            mashups.setdefault(link.mbid, link)
        elif kind == "DJ-mix" and direction == "backward":
            # Suele apuntar a la versión mezclada (título de la canción, «part of “Mix” DJ-mix»): se usa el mix.
            m = MIX_NAME_RE.search((rel.get("recording") or {}).get("disambiguation") or "")
            if m:
                mixes.setdefault(_fold(m.group(1).strip()), m.group(1).strip())
            elif _fold(link.title) != _fold(raw.get("title") or ""):
                mixes.setdefault(_fold(link.title), link.title)
            else:  # sin nombre identificable: cuenta, pero no se muestra
                mixes.setdefault(f"#{link.mbid}", "")
    for g in groups:
        if "DJ-mix" in g.secondary_types:
            mixes.setdefault(_fold(g.title), g.title)
    return schemas.TrackRelations(
        remix_of=list(remix_of.values())[:RELATED_LIMIT], remixes=list(remixes.values())[:RELATED_LIMIT],
        remix_count=len(remixes), dj_mix_count=len(mixes), dj_mixes=[n for n in mixes.values() if n][:RELATED_LIMIT],
        samples=list(samples.values())[:RELATED_LIMIT], sampled_by=list(sampled_by.values())[:RELATED_LIMIT],
        mashups=list(mashups.values())[:RELATED_LIMIT], cover_of=cover_of, cover_writers=cover_writers[:4])


def _link_releases(raw_releases: list[dict[str, Any]], credit_ids: frozenset[str]) -> list[dict[str, Any]]:
    """Ediciones propias (no recopilatorios ni DJ mixes) en el orden del lanzamiento original, hasta LINK_RELEASES."""
    own = [r for r in raw_releases if isinstance(r, dict) and isinstance(r.get("id"), str) and _own_original(r, credit_ids)]
    return sorted(own, key=lambda r: _release_rank(r, credit_ids))[:LINK_RELEASES]


def links(raw: dict[str, Any], raw_releases: list[dict[str, Any]] | None = None,
          credit_ids: frozenset[str] = frozenset()) -> list[schemas.Link]:
    """Enlaces que MusicBrainz documenta para esta grabación y, después, para sus lanzamientos propios (tiendas,
    streaming, Bandcamp…). Los de la grabación prevalecen si la URL coincide. Nunca búsquedas construidas."""
    rels = [dict(r, _scope="recording") for r in raw.get("relations") or [] if isinstance(r, dict)]
    for release in _link_releases(raw_releases or [], credit_ids):
        release_type = (release.get("release-group") or {}).get("primary-type")
        formats = list(dict.fromkeys(f for f in (_str((m or {}).get("format")) for m in release.get("media") or []) if f))
        rels += [dict(r, _scope="release", _release_type=release_type, _formats=formats)
                 for r in release.get("relations") or [] if isinstance(r, dict)]
    return normalize_links(rels)


def isrcs(raw: dict[str, Any]) -> list[str]:
    return [i for i in dict.fromkeys(raw.get("isrcs") or []) if isinstance(i, str)][:5]


def identifiers(raw: dict[str, Any], raw_releases: list[dict[str, Any]], original: schemas.TrackRelease | None,
                original_raw: dict[str, Any] | None, credit_ids: frozenset[str]) -> schemas.TrackIdentifiers:
    """Identificadores fiables para cruzar con otros proveedores: MBID, ISRC, barcode de las ediciones propias e IDs
    extraídos de las URL que documenta MusicBrainz. Ningún identificador sale de una búsqueda por nombre."""
    own = _link_releases(raw_releases, credit_ids)
    barcodes = [b for b in dict.fromkeys(_str(r.get("barcode")) for r in own) if b][:BARCODES_LIMIT]
    external: dict[tuple[str, str, str], schemas.ExternalId] = {}
    sources = [("recording", None, raw)] + [("release", r["id"], r) for r in own]
    for scope, release_mbid, entity in sources:
        for rel in entity.get("relations") or []:
            url = ((rel or {}).get("url") or {}).get("resource") if isinstance(rel, dict) else None
            parsed = external_id(url) if isinstance(url, str) and not is_dead(url) else None
            if parsed:
                provider, kind, value = parsed
                external.setdefault((provider, kind, value), schemas.ExternalId(
                    provider=provider, kind=kind, id=value, url=url, scope=scope, release_mbid=release_mbid))
    return schemas.TrackIdentifiers(
        recording_mbid=raw["id"], isrcs=isrcs(raw), release_group_mbid=original.mbid if original else None,
        release_mbid=(original_raw or {}).get("id"), barcodes=barcodes, external=list(external.values()))


def _wd_ref(qid: str) -> schemas.SourceRef:
    return schemas.SourceRef(label=f"Wikidata {qid}", url=f"https://www.wikidata.org/wiki/{qid}", license="CC0")


def _plural(n: int, one: str, many: str) -> str:
    return f"{n} {one if n == 1 else many}"


# Géneros curados de MusicBrainz → (familia, estilo). Lo que no está aquí se muestra tal cual, como estilo.
GENRE_FAMILY = {
    "house": "House", "deep house": "House", "tech house": "House", "minimal house": "House", "microhouse": "House",
    "afro house": "House", "progressive house": "House", "acid house": "House", "garage house": "House",
    "chicago house": "House", "jackin house": "House", "lo-fi house": "House", "soulful house": "House",
    "electro house": "House", "funky house": "House", "french house": "House", "disco house": "House",
    "techno": "Techno", "minimal techno": "Techno", "dub techno": "Techno", "acid techno": "Techno",
    "detroit techno": "Techno", "hard techno": "Techno", "melodic techno": "Techno", "hypnotic techno": "Techno",
    "minimal": "Minimal", "deep tech": "House", "uk garage": "UK garage", "speed garage": "UK garage",
    "trance": "Trance", "progressive trance": "Trance", "breakbeat": "Breakbeat", "breaks": "Breakbeat",
    "drum and bass": "Drum and bass", "electro": "Electro", "disco": "Disco", "nu-disco": "Disco",
    "ambient": "Ambient", "downtempo": "Downtempo", "dance-pop": "Pop",
    # V6.3: estilos habituales de Discogs y MusicBrainz en la electrónica de club.
    "tribal house": "House", "tribal": "House", "hard house": "House", "italo house": "House", "euro house": "House", "hip-house": "House",
    "piano house": "House", "vocal house": "House", "latin house": "House", "amapiano": "House", "organic house": "House",
    "deep techno": "Techno", "industrial techno": "Techno", "peak time techno": "Techno", "raw techno": "Techno",
    "ambient techno": "Techno", "minimal techno ": "Techno", "electro techno": "Techno",
    "drum n bass": "Drum and bass", "jungle": "Drum and bass", "liquid funk": "Drum and bass",
    "dubstep": "Bass", "bassline": "Bass", "uk bass": "Bass", "grime": "Bass", "future garage": "UK garage",
    "2-step": "UK garage", "italo-disco": "Disco", "italo disco": "Disco", "disco polo": "Disco", "balearic": "Disco",
    "psy-trance": "Trance", "psytrance": "Trance", "hard trance": "Trance", "uplifting trance": "Trance",
    "broken beat": "Breakbeat", "big beat": "Breakbeat", "electroclash": "Electro", "electro house ": "House",
    "chillout": "Downtempo", "trip hop": "Downtempo", "lo-fi": "Downtempo",
}
# Estilos que conviven con varias familias: «Minimal» lo mismo es minimal techno que minimal house. No cuentan para
# decidir si un EP mezcla familias y, si hay otra familia, son un estilo de ella.
WILDCARD_FAMILIES = {"Minimal"}
BROAD = {"electronic", "dance", "electronic dance music", "edm", "club"}
MB_GENRES_LICENSE = "CC BY-NC-SA"


def _title(name: str) -> str:
    return " ".join(w[:1].upper() + w[1:] for w in name.split(" "))


def mb_genres(entity: dict[str, Any]) -> list[str]:
    """Géneros curados de una entidad de MusicBrainz (no las etiquetas libres), por votos."""
    items = [g for g in entity.get("genres") or [] if isinstance(g, dict) and _str(g.get("name"))]
    items.sort(key=lambda g: -(g.get("count") or 0))
    return [g["name"].strip().lower() for g in items]


# Lanzamientos cuyo género no describe cada pista que contienen (V5.7: también en la API, no solo en la app).
NON_TRACK_RELEASES = {"Compilation", "DJ-mix", "Mixtape/Street", "Soundtrack"}


def release_genre_values(names: list[str], secondary_types: list[str], multi_song: bool) -> list[str]:
    """Género de un lanzamiento aplicado a una de sus pistas (scope = release), para MusicBrainz y Discogs por igual.
    - Nunca el de un recopilatorio, DJ mix, mixtape o banda sonora (Double C: el «Pop» de la banda sonora de F1).
    - Si el lanzamiento tiene varias canciones y sus géneros son de familias distintas («Techno, House, Tech House»
      del Dedust EP), no se atribuye ninguno concreto a la pista: solo el género amplio, si consta.
    """
    if set(secondary_types) & NON_TRACK_RELEASES:
        return []
    specific = [n for n in names if n not in BROAD]
    if multi_song and len(families(specific)) > 1:
        return genre_values([n for n in names if n in BROAD])
    return genre_values(names)


def families(names: list[str]) -> set[str]:
    """Familias distintas de unos géneros concretos (sin las comodín, como Minimal)."""
    return {GENRE_FAMILY.get(n, _title(n)) for n in names} - WILDCARD_FAMILIES


def release_styles(names: list[str], secondary_types: list[str]) -> list[str]:
    """Estilos de un lanzamiento de varias canciones que mezcla familias: se muestran como estilos del lanzamiento,
    nunca como el género de la pista. Vacío si es un recopilatorio o no mezcla familias."""
    if set(secondary_types) & NON_TRACK_RELEASES:
        return []
    specific = [n for n in names if n not in BROAD]
    return [_title(n) for n in dict.fromkeys(specific)][:4] if len(families(specific)) > 1 else []


def styles_trait(values: list[str], title: str, source: schemas.SourceRef) -> schemas.DnaTrait:
    return schemas.DnaTrait(key="release_styles", group="classification", label="Estilos del lanzamiento",
                            status="community", scope="release", values=values,
                            detail=f"«{title}» mezcla estilos de varias familias: describen el lanzamiento, no esta pista.",
                            sources=[source])


def is_broad(values: list[str] | None) -> bool:
    """Solo el género amplio («Electrónica»): no dice qué tipo de electrónica es."""
    return not values or values == ["Electrónica"]


def genre_values(names: list[str]) -> list[str]:
    """[familia, estilo…]: «deep house» + «house» → ["House", "Deep House"]. Solo «electronic» → ["Electrónica"]."""
    specific = [n for n in names if n not in BROAD]
    if not specific:
        return ["Electrónica"] if names else []
    mapped = [GENRE_FAMILY.get(n, _title(n)) for n in specific]
    family = next((f for f in mapped if f not in WILDCARD_FAMILIES), None) or mapped[0]
    styles = [_title(n) for n in specific if _title(n) != family]
    return [family, *dict.fromkeys(styles)][:3]


def single_family(names: list[str]) -> list[str]:
    """[familia, estilo…] de una lista de estilos (de un artista o un sello), quedándose con una sola familia: la del
    primer estilo no comodín, más los de esa familia y los comodín. [] si solo hay géneros amplios."""
    specific = [n for n in (x.strip().lower() for x in names if x.strip()) if n not in BROAD]
    if not specific:
        return []
    fams = [GENRE_FAMILY.get(n, _title(n)) for n in specific]
    main = next((f for f in fams if f not in WILDCARD_FAMILIES), fams[0])
    values = genre_values([n for n, f in zip(specific, fams) if f in {main, *WILDCARD_FAMILIES}])
    return [] if is_broad(values) else values


def dna(recording_mbid: str, title: str, track_wd: WikidataInfo, release_wd: WikidataInfo,
        release: schemas.TrackRelease | None, artist_name: str | None, artist_qid: str | None,
        artist_styles: list[schemas.Style],
        groups: list[schemas.TrackRelease], version: str | None, rel: schemas.TrackRelations,
        wd_labels: dict[str, str], recording_genres: list[str] | None = None,
        release_genres_mb: list[str] | None = None) -> schemas.TrackDna:
    """Rasgos del ADN con procedencia explícita. Sin cifras inventadas: los recuentos son mínimos documentados."""
    mb = schemas.SourceRef(label="MusicBrainz", url=f"https://musicbrainz.org/recording/{recording_mbid}", license="CC0")
    traits: list[schemas.DnaTrait] = []

    # Etiquetas de Wikidata con la misma forma que las demás (familia y estilos, en mayúscula inicial: V6.3).
    track_genres = genre_values([wd_labels[q].lower() for q in track_wd.genre_ids if q in wd_labels][:3])
    release_genres = genre_values([wd_labels[q].lower() for q in release_wd.genre_ids if q in wd_labels][:3])
    mb_rec = genre_values(recording_genres or [])
    mb_rg = (release_genre_values(release_genres_mb or [], release.secondary_types, release.primary_type != "Single")
             if release else [])
    mb_genre_ref = schemas.SourceRef(label="MusicBrainz (géneros)", url=f"https://musicbrainz.org/recording/{recording_mbid}",
                                     license=MB_GENRES_LICENSE)
    # Prioridad: la propia grabación (MusicBrainz, luego Wikidata) > su lanzamiento original. Nunca el artista. V6.3:
    # una fuente que solo dice «Electrónica» cede ante la siguiente que concreta (subgénero).
    rg_ref = mb_genre_ref.model_copy(update={"url": f"https://musicbrainz.org/release-group/{release.mbid}"}) if release else None
    options: list[tuple[list[str], str, str, schemas.SourceRef]] = []
    if mb_rec:
        options.append((mb_rec, "track", "Géneros votados por la comunidad de MusicBrainz para esta grabación.", mb_genre_ref))
    if track_genres and track_wd.qid:
        options.append((track_genres, "track", "Clasificación de Wikidata para esta canción.", _wd_ref(track_wd.qid)))
    if mb_rg and release and rg_ref:
        options.append((mb_rg, "release", f"Géneros de «{release.title}» en MusicBrainz: describen el lanzamiento.", rg_ref))
    if release_genres and release_wd.qid and release and not set(release.secondary_types) & NON_TRACK_RELEASES:
        options.append((release_genres, "release",
                        f"Género de «{release.title}» en Wikidata: describe el lanzamiento, no solo esta pista.",
                        _wd_ref(release_wd.qid)))
    chosen = next((o for o in options if not is_broad(o[0])), options[0] if options else None)
    if chosen:
        traits.append(schemas.DnaTrait(key="genre", group="classification", label="Género", status="community",
                                       scope=chosen[1], values=chosen[0], detail=chosen[2], sources=[chosen[3]]))
    else:
        traits.append(schemas.DnaTrait(key="genre", group="classification", label="Género", status="unavailable",
                                       detail="Ninguna fuente con licencia compatible clasifica esta canción."))
    rg_styles = release_styles(release_genres_mb or [], release.secondary_types) if release else []
    if (not chosen or is_broad(chosen[0])) and rg_styles and release and rg_ref:
        traits.append(styles_trait(rg_styles, release.title, rg_ref))
    if artist_styles and artist_name:
        traits.append(schemas.DnaTrait(
            key="artist_style", group="classification", label="Estilo del artista", status="community", scope="artist",
            values=[s.label for s in artist_styles],
            detail=f"Estilos declarados para {artist_name} en Wikidata: contexto del artista, no de esta pista.",
            sources=[_wd_ref(artist_qid)] if artist_qid else []))

    own_groups = [g for g in groups if g.own and not set(g.secondary_types) & COMPILATION_TYPES]
    own_labels: list[str] = []
    for g in own_groups:
        own_labels += [n for n in g.labels if n not in own_labels]
    if own_labels:
        traits.append(schemas.DnaTrait(key="label", group="context", label="Sello", status="verified",
                                       values=own_labels[:LABELS_LIMIT],
                                       detail="Sellos de sus lanzamientos propios; primero, los de la edición original.",
                                       sources=[mb]))
    elif any(g.self_released for g in own_groups):
        traits.append(schemas.DnaTrait(key="label", group="context", label="Sello", status="verified",
                                       values=[SELF_RELEASED],
                                       detail="Publicada sin sello discográfico, según MusicBrainz.", sources=[mb]))
    else:
        traits.append(schemas.DnaTrait(key="label", group="context", label="Sello", status="unavailable",
                                       detail="Sin sello documentado en MusicBrainz."))
    if rel.remix_of:
        original = rel.remix_of[0]
        traits.append(schemas.DnaTrait(key="version", group="context", label="Versión", status="verified",
                                       values=[version or "Remezcla o edit"],
                                       detail=f"Versión de «{original.title}» ({original.artist_name}).", sources=[mb]))
    elif version:
        traits.append(schemas.DnaTrait(key="version", group="context", label="Versión", status="verified",
                                       values=[version], detail="Según el título y los datos de MusicBrainz.",
                                       sources=[mb]))
    if rel.remix_count:
        traits.append(schemas.DnaTrait(key="remixes", group="context", label="Remezclas", status="verified",
                                       values=[_plural(rel.remix_count, "documentada", "documentadas")],
                                       detail="Remezclas y edits enlazados en MusicBrainz (mínimo, no un total).",
                                       sources=[mb]))
    if rel.dj_mix_count:
        traits.append(schemas.DnaTrait(key="dj_mixes", group="context", label="En DJ mixes", status="verified",
                                       values=[_plural(rel.dj_mix_count, "DJ mix", "DJ mixes")],
                                       detail="DJ mixes publicados que la incluyen según MusicBrainz (mínimo documentado).",
                                       sources=[mb]))
    for key, label in (("bpm", "BPM"), ("key", "Tonalidad"), ("energy", "Energía")):
        traits.append(schemas.DnaTrait(key=key, group="acoustic", label=label, status="unavailable",
                                       detail="Requiere análisis de audio autorizado. No se estima con IA."))
    return schemas.TrackDna(recording_mbid=recording_mbid, traits=traits)
