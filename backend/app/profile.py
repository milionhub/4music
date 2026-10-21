"""Módulos del perfil de artista (T1.2). Funciones puras sobre datos ya obtenidos: sin red, fáciles de probar.

Reglas de honestidad: nada se rellena por aproximación; un módulo sin datos fiables se devuelve vacío.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any

from app import schemas
from app.discovery import MUSICAL_RELATIONS
from app.normalize import SPECIAL_ARTISTS, artist_summary
from app.sources import founded_labels
from app.wikidata import WikidataInfo

RECENT_LIMIT = 5
TOP_TRACKS_LIMIT = 5
HIGHLIGHTS_DEFAULT = 2   # dos por defecto…
HIGHLIGHTS_STRONG_EXTRA = 2  # …y un tercero solo con ≥2 lanzamientos conjuntos
OWN_PRIMARY_TYPES = {"Single", "EP", "Album"}
# Recopilatorios, reediciones en directo, DJ mixes y similares no son «lanzamientos recientes» del artista.
EXCLUDED_SECONDARY = {"Compilation", "DJ-mix", "Live", "Mixtape/Street", "Interview", "Audiobook", "Audio drama",
                      "Spokenword", "Demo", "Field recording", "Soundtrack"}
COVER_RG = "https://coverartarchive.org/release-group/{mbid}/front-250"
COVER_RELEASE = "https://coverartarchive.org/release/{release}/{caa_id}-250.jpg"
FEAT_RE = re.compile(r"\b(feat\.?|ft\.?|featuring|with|con)\b", re.IGNORECASE)
# Sufijos de versión equivalentes (mismo tema). Los remixes de otros artistas NO se fusionan.
VERSION_RE = re.compile(
    r"\s*([\(\[]\s*((original|extended|radio|club|dub|instrumental|album|single)\s+)?(mix|edit|version|remaster(ed)?)"
    r"(\s+\d{4})?\s*[\)\]]|\s+-\s+((original|extended|radio|club)\s+)?(mix|edit|version))\s*$",
    re.IGNORECASE)
RELATION_LABELS = {
    "member of band": "pertenencia a un grupo", "collaboration": "colaboración",
    "is person": "alias o proyecto de la misma persona", "subgroup": "subgrupo",
    "supporting musician": "músico de apoyo", "vocal supporting musician": "voz de apoyo",
    "instrumental supporting musician": "músico de apoyo", "founder": "fundación del grupo", "tribute": "tributo",
}


def base_title(title: str) -> str:
    return VERSION_RE.sub("", title or "").strip().casefold()


# --- Lanzamientos recientes -------------------------------------------------------------------------------------
def recent_releases(release_groups: list[dict[str, Any]], artist_mbid: str, covers: bool,
                    limit: int = RECENT_LIMIT) -> list[schemas.RecentRelease]:
    out = []
    for rg in release_groups:
        date = rg.get("first-release-date")
        credit = [c.get("artist") or {} for c in rg.get("artist-credit") or []]
        ids = {a.get("id") for a in credit}
        if (not isinstance(rg.get("id"), str) or not rg.get("title") or not date
                or rg.get("primary-type") not in OWN_PRIMARY_TYPES
                or set(rg.get("secondary-types") or []) & EXCLUDED_SECONDARY
                or artist_mbid not in ids or ids & SPECIAL_ARTISTS):
            continue  # solo lanzamientos propios, con fecha de publicación documentada
        out.append(schemas.RecentRelease(
            mbid=rg["id"], title=rg["title"], primary_type=rg.get("primary-type"),
            secondary_types=[t for t in rg.get("secondary-types") or [] if isinstance(t, str)],
            first_release_date=date,
            with_artists=[a.get("name") for a in credit if a.get("id") != artist_mbid and a.get("name")],
            cover_url=COVER_RG.format(mbid=rg["id"]) if covers else None,
            url=f"https://musicbrainz.org/release-group/{rg['id']}"))
    out.sort(key=lambda r: r.title.casefold())
    out.sort(key=lambda r: r.first_release_date, reverse=True)  # fecha de primera publicación, no de alta en MB
    return out[:limit]


def first_release(release_groups: list[dict[str, Any]], artist_mbid: str, total: int | None
                  ) -> schemas.RecentRelease | None:
    """Primer lanzamiento propio documentado. Solo con la discografía completa: si MusicBrainz devolvió una página
    parcial (`total` mayor que lo recibido), el más antiguo de la página no tiene por qué ser el primero."""
    if total is None or total > len(release_groups):
        return None
    own = recent_releases(release_groups, artist_mbid, covers=False, limit=len(release_groups))
    return own[-1] if own else None


# --- Colaboraciones destacadas ------------------------------------------------------------------------------------
def highlights(mb_artist: dict[str, Any], recordings: list[dict[str, Any]], release_groups: list[dict[str, Any]],
               artist_mbid: str, limit: int = HIGHLIGHTS_DEFAULT + 1
               ) -> tuple[list[schemas.Highlight], str | None]:
    """Colaboraciones directas verificables (lanzamiento conjunto, feat., coautoría); si no hay ninguna,
    relaciones musicales documentadas, tituladas como «conexiones» (nunca como colaboraciones)."""
    cands: dict[str, dict[str, Any]] = {}

    def add(raw: dict, kind: str, detail: str):
        mbid = raw.get("id")
        if not isinstance(mbid, str) or mbid == artist_mbid or mbid in SPECIAL_ARTISTS or not raw.get("name"):
            return
        c = cands.setdefault(mbid, {"raw": raw, "joint_release": [], "featuring": [], "co_credit": [], "relation": []})
        key = base_title(detail) if kind != "relation" else detail
        if key not in {base_title(d) if kind != "relation" else d for d in c[kind]}:
            c[kind].append(detail)

    for rg in release_groups:
        credit = rg.get("artist-credit") or []
        if any((c.get("artist") or {}).get("id") == artist_mbid for c in credit) and rg.get("title") \
                and not set(rg.get("secondary-types") or []) & {"Compilation", "DJ-mix"}:
            for c in credit:
                add(c.get("artist") or {}, "joint_release", rg["title"])
    for rec in recordings:
        credit = rec.get("artist-credit") or []
        if not rec.get("title") or not any((c.get("artist") or {}).get("id") == artist_mbid for c in credit):
            continue
        for i, c in enumerate(credit):
            previous_join = credit[i - 1].get("joinphrase", "") if i > 0 else ""
            add(c.get("artist") or {}, "featuring" if FEAT_RE.search(previous_join) else "co_credit", rec["title"])
    for rel in mb_artist.get("relations") or []:
        if rel.get("target-type") == "artist" and rel.get("type") in MUSICAL_RELATIONS:
            add(rel.get("artist") or {}, "relation", rel["type"])

    def build(c: dict[str, Any], kinds: tuple[str, ...]) -> schemas.Highlight | None:
        for kind in kinds:
            if c[kind]:
                items = c[kind]
                if kind == "relation":
                    reason = "Relación documentada: " + ", ".join(RELATION_LABELS.get(t, t) for t in items)
                else:
                    prefix = {"joint_release": "Lanzamiento conjunto", "featuring": "Colaboración en",
                              "co_credit": "Comparten crédito en"}[kind]
                    reason = f"{prefix}{':' if kind == 'joint_release' else ''} «{items[0]}»" + (
                        f" y {len(items) - 1} más" if len(items) > 1 else "")
                count = sum(len(c[k]) for k in kinds)
                return schemas.Highlight(artist=artist_summary(c["raw"]), kind=kind, reason=reason, evidence_count=count)
        return None

    def score(c: dict[str, Any]) -> int:
        return 3 * len(c["joint_release"]) + 2 * len(c["featuring"]) + len(c["co_credit"])

    collab_kinds = ("joint_release", "featuring", "co_credit")
    collabs = sorted((c for c in cands.values() if score(c)), key=lambda c: (-score(c), c["raw"]["name"].casefold()))
    if collabs:
        built = [h for h in (build(c, collab_kinds) for c in collabs[:limit]) if h]
        default = min(HIGHLIGHTS_DEFAULT, limit)
        # El tercero solo si es especialmente relevante: al menos dos lanzamientos conjuntos con el artista.
        extra = [h for c, h in zip(collabs[default:limit], built[default:]) if len(c["joint_release"]) >= HIGHLIGHTS_STRONG_EXTRA]
        return built[:default] + extra, "collaborations"
    rels = sorted((c for c in cands.values() if c["relation"]), key=lambda c: c["raw"]["name"].casefold())
    if rels:
        return [h for h in (build(c, ("relation",)) for c in rels[:min(HIGHLIGHTS_DEFAULT, limit)]) if h], "connections"
    return [], None


# --- Más escuchadas (ListenBrainz) -------------------------------------------------------------------------------
def top_tracks(items: list[dict[str, Any]], covers: bool, limit: int = TOP_TRACKS_LIMIT) -> list[schemas.TopTrack]:
    """Orden por recuento real de escuchas; las versiones equivalentes (extended, radio edit…) se fusionan
    quedándose con la más escuchada. Los remixes de otros artistas son temas distintos."""
    valid = [x for x in items if isinstance(x, dict) and isinstance(x.get("recording_mbid"), str)
             and x.get("recording_name") and isinstance(x.get("total_listen_count"), int)]
    valid.sort(key=lambda x: -x["total_listen_count"])
    seen: set[str] = set()
    out = []
    for x in valid:
        key = base_title(x["recording_name"]) + "|" + (x.get("artist_name") or "").casefold()
        if key in seen:
            continue
        seen.add(key)
        cover = None
        if covers and x.get("caa_id") and isinstance(x.get("caa_release_mbid"), str):
            cover = COVER_RELEASE.format(release=x["caa_release_mbid"], caa_id=x["caa_id"])
        artist_name = x.get("artist_name") or ""
        out.append(schemas.TopTrack(
            recording_mbid=x["recording_mbid"], title=x["recording_name"], artist_name=artist_name,
            listen_count=x["total_listen_count"],
            user_count=x.get("total_user_count") if isinstance(x.get("total_user_count"), int) else None,
            release_name=x.get("release_name"), cover_url=cover,
            search_query=f"{x['recording_name']} {artist_name}".strip()))
        if len(out) == limit:
            break
    return out


# --- Estilos y biografía ------------------------------------------------------------------------------------------
# Géneros que no describen el estilo de un artista de electrónica (todos lo son) o que suelen ser una clasificación
# discutible de Wikidata para un DJ de club («pop» en Jamie Jones). Se comparan sin tildes ni mayúsculas.
GENERIC_GENRES = {"musica electronica", "electronic music", "electronica", "electronic", "musica dance",
                  "dance music", "dance", "electronic dance music", "musica electronica de baile"}
OUTSIDE_GENRES = {"pop", "musica pop", "pop music", "rock", "musica rock", "hip hop", "rap", "r&b",
                  "contemporary r&b", "soul", "funk", "jazz", "musica clasica", "dance-pop", "synth-pop"}
# Vocabulario cerrado de estilos de club que se reconocen en el texto que describe al artista (descripción de
# MusicBrainz, CC0, y frase de presentación de Wikipedia). Nunca se deducen subgéneros: solo lo que está escrito.
SCENE_GENRES = ("minimal techno", "melodic techno", "hard techno", "dub techno", "industrial techno", "acid techno",
                "deep house", "tech house", "progressive house", "afro house", "acid house", "jazz house",
                "lo-fi house", "melodic house", "minimal house", "microhouse", "uk garage", "drum and bass",
                "breakbeat", "electro", "nu-disco", "disco", "trance", "idm", "ambient", "dubstep", "downtempo",
                "minimal", "techno", "house")
SCENE_EXTRA = ("funk", "soul")  # solo si el texto lo dice expresamente («house, funk y soul»)


def _fold(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c)).casefold()


def text_genres(text: str | None) -> list[str]:
    """Estilos del vocabulario escritos en el texto, en orden de aparición; los compuestos («tech house») se
    reconocen antes y no cuentan también como «house»."""
    folded = " " + _fold(text or "").replace("/", " / ").replace("-house", " house") + " "
    found: list[tuple[int, str]] = []
    for genre in SCENE_GENRES + SCENE_EXTRA:
        for m in re.finditer(rf"(?<![\w-]){re.escape(genre)}(?![\w-])", folded):
            found.append((m.start(), genre))
            folded = folded[:m.start()] + " " * len(genre) + folded[m.end():]
    return list(dict.fromkeys(g for _pos, g in sorted(found)))


def _lead(text: str | None) -> str:
    """La primera frase de Wikipedia, donde se presenta al artista: más allá aparecen influencias y géneros de otros
    («acid house» en la historia de Marco Carola)."""
    return re.split(r"(?<=[.!?])\s+(?=[A-ZÁÉÍÓÚ])", (text or "").strip())[0]


def styles(wd: WikidataInfo, labels: dict[str, str], disambiguation: str | None = None,
           wiki_intro: str | None = None) -> list[schemas.Style]:
    """Hasta tres géneros representativos con su fuente:
    1. Géneros específicos de Wikidata (P136). Los de fuera de la escena («pop») solo si el texto los confirma.
    2. Estilos escritos en la descripción de MusicBrainz («techno/house DJ») y en la presentación de Wikipedia.
    3. Los genéricos («música electrónica») solo si no hay nada más preciso.
    Nunca etiquetas (tags) de MusicBrainz, que no son CC0."""
    lead = _lead(wiki_intro)
    corroborating = _fold(f"{disambiguation or ''} {lead}")
    out: list[schemas.Style] = []
    generic: list[schemas.Style] = []
    for q in wd.genre_ids:
        if q not in labels:
            continue
        key = _fold(labels[q])
        if key in GENERIC_GENRES:
            generic.append(schemas.Style(label=labels[q], qid=q))
        elif key not in OUTSIDE_GENRES or re.search(rf"\b{re.escape(key)}\b", corroborating):
            out.append(schemas.Style(label=labels[q], qid=q))
    for text, source in ((disambiguation, "musicbrainz"), (lead, "wikipedia")):
        for genre in text_genres(text):
            if all(_fold(s.label) != genre for s in out):
                out.append(schemas.Style(label=genre, qid=None, source=source))
    return (out or generic)[:3]


def _join(items: list[str]) -> str:
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " y " + items[-1]


GROUP_TYPES = {"Group", "Orchestra", "Choir"}


def membership(mb_artist: dict[str, Any]) -> tuple[list[str], list[str]]:
    """(integrantes del grupo, grupos de los que es miembro) según la relación «member of band» de MusicBrainz."""
    members, groups = [], []
    for rel in mb_artist.get("relations") or []:
        name = (rel.get("artist") or {}).get("name")
        if rel.get("target-type") == "artist" and rel.get("type") == "member of band" and name:
            (members if rel.get("direction") == "backward" else groups).append(name)
    return list(dict.fromkeys(members)), list(dict.fromkeys(groups))


def identity(mb_artist: dict[str, Any], artist: schemas.Artist, wd: WikidataInfo,
             country_name: str | None) -> schemas.Identity:
    """Solo datos documentados para ese MBID; ningún lugar se deduce de otro."""
    area = mb_artist.get("area") if isinstance(mb_artist.get("area"), dict) else {}
    area_is_country = area.get("type") == "Country" or bool(area.get("iso-3166-1-codes"))
    if not country_name and area_is_country:
        country_name = artist.area  # nombre que da MusicBrainz al área-país (en inglés)
    begin_area = (mb_artist.get("begin-area") or {}).get("name") if isinstance(mb_artist.get("begin-area"), dict) else None
    kind = "birth" if artist.type == "Person" else "formation" if artist.type in GROUP_TYPES else None
    begin_year = (artist.begin_date or "")[:4]
    members, projects = membership(mb_artist)
    return schemas.Identity(
        country_name=country_name, area=None if area_is_country else artist.area,
        origin=begin_area.strip() if kind and isinstance(begin_area, str) and begin_area.strip() else None,
        origin_kind=kind if kind and isinstance(begin_area, str) and begin_area.strip() else None,
        formed_year=begin_year if artist.type in GROUP_TYPES and begin_year.isdigit() else None,
        active_since=wd.active_since if (wd.active_since or "").isdigit() else None,
        founded_labels=[name for name, _year in founded_labels(mb_artist)][:4],
        label_years={name: year for name, year in founded_labels(mb_artist)[:4] if year},
        projects=projects[:3], members=members[:6])


def identity_bio(artist: schemas.Artist, wd: WikidataInfo, labels: dict[str, str]) -> schemas.Bio | None:
    """Descripción mínima de identidad con datos verificados de Wikidata (CC0), nunca una biografía editorial:
    1. la descripción corta del ítem (español; si no, inglés, marcada con su idioma);
    2. si no hay, ocupación y estilo. Nunca fechas, títulos ni listas de lanzamientos (T1.5). Sin datos: None."""
    if not wd.qid:
        return None
    sources = [schemas.SourceRef(label=f"Wikidata {wd.qid}", url=f"https://www.wikidata.org/wiki/{wd.qid}", license="CC0")]
    for lang in ("es", "en"):
        desc = wd.descriptions.get(lang)
        if desc and len(desc.split()) >= 2:  # «DJ» o «músico» a secas no describen más que la ocupación
            text = desc[0].upper() + desc[1:]
            return schemas.Bio(kind="factual", text=text if text.endswith(".") else text + ".", language=lang,
                               reviewed=None, sources=sources)
    roles = [labels[q] for q in wd.occupation_ids if q in labels][:2]
    genres = [labels[q] for q in wd.genre_ids if q in labels][:2]
    if not (roles or genres):
        return None
    if roles:
        text = _join(roles)
        text = text[0].upper() + text[1:] + (f" de {_join(genres)}" if genres else "") + "."
    else:
        text = f"Artista de {_join(genres)}."
    return schemas.Bio(kind="factual", text=text, reviewed=None, sources=sources)


def editorial_bio(entry: dict[str, Any] | None) -> schemas.Bio | None:
    if not entry:
        return None
    sources = [schemas.SourceRef(label=s["label"], url=s["url"], license=s.get("license"))
               for s in entry.get("sources") or [] if isinstance(s, dict) and s.get("label") and s.get("url")]
    if not sources:
        return None
    return schemas.Bio(kind="editorial", text=entry["text"].strip(), language=entry.get("language", "es"),
                       sources=sources, reviewed=bool(entry.get("reviewed")))
