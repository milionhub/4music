"""Ítem de Wikidata de un artista, verificado por MBID (P434). Lo comparten fotos, estilos y descripción factual.

1. Enlace a Wikidata documentado en MusicBrainz para ese MBID; si no hay,
2. búsqueda inversa `haswbstatement:P434=<MBID>` (cubre DJs cuyo MBID no enlaza con Wikidata, p. ej. PAWSA).
En ambos casos el ítem DEBE declarar ese mismo MBID; si no, se descarta (posible homónimo).
3. Si ningún ítem declara el MBID: el identificador de Discogs (P1953) que MusicBrainz documenta para ese MBID. El
   ítem debe declarar ese mismo ID de Discogs, ser el único resultado y no declarar OTRO MBID (p. ej. ANOTR, cuyo
   ítem existe pero sin P434). Es un cruce entre dos identificadores documentados, nunca por nombre.
Datos de Wikidata: CC0.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from app import store
from app.musicbrainz import ProviderError, WikimediaClient

QID_RE = re.compile(r"^Q[1-9][0-9]*$")
ISO_RE = re.compile(r"^[A-Z]{2}$")
COUNTRY_KIND = "country"
COUNTRY_TTL_S = 180 * 24 * 3600


@dataclass
class WikidataInfo:
    qid: str | None = None
    via: str | None = None             # "musicbrainz_link" | "p434_search" | "discogs_id"
    reason: str | None = None          # por qué no hay ítem verificado
    image_files: list[str] = field(default_factory=list)
    genre_ids: list[str] = field(default_factory=list)
    occupation_ids: list[str] = field(default_factory=list)
    wikipedia: dict[str, str] = field(default_factory=dict)  # {"enwiki": "PAWSA", …}
    other_wikipedia: dict[str, str] = field(default_factory=dict)  # {"dewiki": "ANOTR"} (ver OTHER_WIKIS)
    label_ids: list[str] = field(default_factory=list)        # P264 sello discográfico
    country_ids: list[str] = field(default_factory=list)      # P27 nacionalidad / P495 país de origen
    member_of_ids: list[str] = field(default_factory=list)    # P463/P361 miembro o parte de
    has_part_ids: list[str] = field(default_factory=list)     # P527 integrantes (dúos y grupos)
    award_ids: list[str] = field(default_factory=list)        # P166 premios
    active_since: str | None = None                           # P2031 inicio del periodo de actividad (año)
    descriptions: dict[str, str] = field(default_factory=dict)  # descripción corta del ítem {"es": …, "en": …}


def _link_qid(mb_artist: dict) -> str | None:
    for rel in mb_artist.get("relations") or []:
        url = ((rel.get("url") or {}).get("resource") or "").rstrip("/")
        if rel.get("type") == "wikidata" and "wikidata.org/wiki/" in url:
            qid = url.rsplit("/", 1)[-1]
            if QID_RE.match(qid):
                return qid
    return None


# Wikipedias de otros idiomas, por orden de preferencia, para artistas sin artículo en español ni en inglés (ANOTR
# solo tiene de/nl/sv). El selector reconoce en ellas lo esencial: fundaciones, sellos, residencias, inicios.
OTHER_WIKIS = ("dewiki", "frwiki", "nlwiki", "itwiki", "ptwiki")
DISCOGS_ARTIST_RE = re.compile(r"^https?://(www\.)?discogs\.com/artist/(\d+)")


def discogs_ids(mb_artist: dict) -> list[str]:
    """IDs de artista de Discogs que MusicBrainz enlaza para ese MBID (relación «discogs»)."""
    out = []
    for rel in mb_artist.get("relations") or []:
        m = DISCOGS_ARTIST_RE.match(((rel.get("url") or {}).get("resource") or ""))
        if rel.get("type") == "discogs" and m:
            out.append(m.group(2))
    return list(dict.fromkeys(out))


def _values(entity: dict, prop: str) -> list:
    out = []
    for claim in (entity.get("claims") or {}).get(prop) or []:
        if claim.get("rank") == "deprecated":
            continue
        value = ((claim.get("mainsnak") or {}).get("datavalue") or {}).get("value")
        if value is not None:
            out.append(value)
    return out


def _texts(entity: dict, key: str) -> dict[str, str]:
    """Etiquetas o descripciones en español e inglés del propio ítem."""
    out = {}
    for lang in ("es", "en"):
        value = ((entity.get(key) or {}).get(lang) or {}).get("value")
        if isinstance(value, str) and value.strip():
            out[lang] = value.strip()
    return out


def _ids(entity: dict, prop: str) -> list[str]:
    return [v["id"] for v in _values(entity, prop) if isinstance(v, dict) and isinstance(v.get("id"), str)]


def resolve(mb_artist: dict, mbid: str, wiki: WikimediaClient) -> WikidataInfo:
    """Nunca lanza: los fallos de Wikimedia se devuelven como reason='unavailable'."""
    discogs = discogs_ids(mb_artist)
    try:
        qid, via = _link_qid(mb_artist), "musicbrainz_link"
        if not qid:
            hits = (wiki.search_by_mbid(mbid).data.get("query") or {}).get("search") or []
            candidates = [h.get("title") for h in hits if QID_RE.match(str(h.get("title")))]
            qid, via = (candidates[0], "p434_search") if candidates else (None, None)
        if not qid and len(discogs) == 1:
            hits = (wiki.search_statement("P1953", discogs[0]).data.get("query") or {}).get("search") or []
            candidates = [h.get("title") for h in hits if QID_RE.match(str(h.get("title")))]
            if len(candidates) == 1:  # varios ítems con el mismo ID: ambiguo, no se usa
                qid, via = candidates[0], "discogs_id"
        if not qid:
            return WikidataInfo(reason="no_wikidata_item")
        entity = (wiki.entity_claims(qid).data.get("entities") or {}).get(qid) or {}
    except ProviderError:
        return WikidataInfo(reason="unavailable")
    mbids = [v for v in _values(entity, "P434") if isinstance(v, str)]
    if via == "discogs_id":
        if discogs[0] not in [v for v in _values(entity, "P1953") if isinstance(v, str)] or mbids:
            return WikidataInfo(reason="mbid_mismatch")  # no confirma el ID, o declara otro MBID: otro artista
    elif mbid not in mbids:
        return WikidataInfo(reason="mbid_mismatch")  # el ítem no confirma el mismo artista
    sitelinks = entity.get("sitelinks") or {}
    return WikidataInfo(
        qid=qid, via=via, descriptions=_texts(entity, "descriptions"),
        image_files=[v for v in _values(entity, "P18") if isinstance(v, str)],
        genre_ids=_ids(entity, "P136"), occupation_ids=_ids(entity, "P106"),
        label_ids=_ids(entity, "P264"), country_ids=_ids(entity, "P27") + _ids(entity, "P495"),
        member_of_ids=_ids(entity, "P463") + _ids(entity, "P361"), award_ids=_ids(entity, "P166"),
        has_part_ids=_ids(entity, "P527"),
        active_since=next((v["time"][1:5] for v in _values(entity, "P2031")
                           if isinstance(v, dict) and isinstance(v.get("time"), str) and len(v["time"]) > 5), None),
        wikipedia={k: v["title"] for k, v in sitelinks.items()
                   if k in ("eswiki", "enwiki") and isinstance(v, dict) and isinstance(v.get("title"), str)},
        other_wikipedia={k: sitelinks[k]["title"] for k in OTHER_WIKIS
                         if isinstance(sitelinks.get(k), dict) and isinstance(sitelinks[k].get("title"), str)})


def resolve_statement(wiki: WikimediaClient, prop: str, mbid: str) -> WikidataInfo:
    """Ítem de una canción (P4404) o de un lanzamiento (P436) que declara ese MBID. Mismo criterio que con los
    artistas: si el ítem no confirma el MBID, se descarta. Solo género y Wikipedia. Nunca lanza."""
    try:
        hits = (wiki.search_statement(prop, mbid).data.get("query") or {}).get("search") or []
        candidates = [h.get("title") for h in hits if QID_RE.match(str(h.get("title")))]
        if not candidates:
            return WikidataInfo(reason="no_wikidata_item")
        qid = candidates[0]
        entity = (wiki.entity_claims(qid).data.get("entities") or {}).get(qid) or {}
    except ProviderError:
        return WikidataInfo(reason="unavailable")
    if mbid not in [v for v in _values(entity, prop) if isinstance(v, str)]:
        return WikidataInfo(reason="mbid_mismatch")
    sitelinks = entity.get("sitelinks") or {}
    return WikidataInfo(qid=qid, via=f"{prop.lower()}_search", genre_ids=_ids(entity, "P136"),
                        wikipedia={k: v["title"] for k, v in sitelinks.items()
                                   if k in ("eswiki", "enwiki") and isinstance(v, dict) and isinstance(v.get("title"), str)})


def labels(wiki: WikimediaClient, qids: list[str]) -> dict[str, str]:
    """Etiquetas en español (o inglés) de una lista de ítems; {} si Wikimedia no responde."""
    if not qids:
        return {}
    try:
        entities = wiki.labels(qids).data.get("entities") or {}
    except ProviderError:
        return {}
    out = {}
    for qid, ent in entities.items():
        lab = (ent.get("labels") or {})
        value = (lab.get("es") or lab.get("en") or {}).get("value")
        if isinstance(value, str) and value.strip():
            out[qid] = value.strip()
    return out


def all_label_ids(wd: WikidataInfo) -> list[str]:
    """Ids cuyas etiquetas hacen falta para describir al artista (una sola petición de etiquetas)."""
    ids = (wd.occupation_ids[:3] + wd.genre_ids[:3] + wd.label_ids[:3] + wd.country_ids[:2]
           + wd.member_of_ids[:2] + wd.award_ids[:3] + wd.has_part_ids[:6])
    return list(dict.fromkeys(ids))[:50]


def country_name(wiki: WikimediaClient, iso: str | None) -> str | None:
    """Nombre legible (español o inglés) del país ISO 3166-1 que declara MusicBrainz, vía el ítem de Wikidata con
    ese código (P297, no disuelto: sin P576). Caché persistente por código; None si Wikimedia falla (no se guarda)."""
    code = (iso or "").strip().upper()
    if not ISO_RE.match(code):
        return None  # MusicBrainz usa también códigos propios (XW, XE) que no son países
    hit = store.get(COUNTRY_KIND, code)
    if hit is not None:
        return hit.get("name")
    name = None
    try:
        hits = (wiki.search_statement("P297", code).data.get("query") or {}).get("search") or []
        for qid in [h.get("title") for h in hits if QID_RE.match(str(h.get("title")))][:2]:
            entity = (wiki.entity_claims(qid).data.get("entities") or {}).get(qid) or {}
            if code in [v for v in _values(entity, "P297") if isinstance(v, str)] and not _values(entity, "P576"):
                labels_ = _texts(entity, "labels")
                name = labels_.get("es") or labels_.get("en")
                break
    except ProviderError:
        return None
    store.put(COUNTRY_KIND, code, {"name": name}, COUNTRY_TTL_S)
    return name
