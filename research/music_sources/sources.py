"""Acceso a MusicBrainz y Wikidata (endpoints oficiales) y estado de Discogs.

Solo extrae y copia valores tal como vienen de la fuente ("observed").
Las decisiones de correspondencia viven en run_experiment.py ("interpretation").
"""

from __future__ import annotations

import re
import unicodedata

from http_client import FetchResult, HttpClient

MB_BASE = "https://musicbrainz.org/ws/2/"
WD_API = "https://www.wikidata.org/w/api.php"

# ---------------------------------------------------------------- normalización
# Solo para COMPARAR; los nombres originales se conservan siempre.


def norm(s: str | None) -> str:
    return " ".join((s or "").casefold().split())


def fold(s: str | None) -> str:
    decomposed = unicodedata.normalize("NFKD", s or "")
    return norm("".join(c for c in decomposed if not unicodedata.combining(c)))


def lucene_phrase(s: str) -> str:
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


# ---------------------------------------------------------------- MusicBrainz

def mb_get(client: HttpClient, entity: str, params: dict[str, str]) -> FetchResult:
    return client.get_json("musicbrainz", client.build_url(MB_BASE + entity, {**params, "fmt": "json"}))


def mb_search_recordings(client: HttpClient, title: str, artist: str | None, limit: int = 25) -> FetchResult:
    query = f"recording:{lucene_phrase(title)}"
    if artist:
        query += f" AND artist:{lucene_phrase(artist)}"
    return mb_get(client, "recording", {"query": query, "limit": str(limit)})


def mb_search_artists(client: HttpClient, name: str, limit: int = 10) -> FetchResult:
    return mb_get(client, "artist", {"query": f"artist:{lucene_phrase(name)}", "limit": str(limit)})


RECORDING_INC = "artist-credits+releases+release-groups+isrcs+url-rels+genres+tags+artist-rels+work-rels"
RECORDING_INC_FALLBACK = "artist-credits+releases+isrcs+url-rels+genres+tags+artist-rels+work-rels"


def mb_lookup_recording(client: HttpClient, mbid: str) -> FetchResult:
    res = mb_get(client, f"recording/{mbid}", {"inc": RECORDING_INC})
    if res.status == 400:  # inc no aceptado: se repite sin release-groups
        res = mb_get(client, f"recording/{mbid}", {"inc": RECORDING_INC_FALLBACK})
    return res


def mb_lookup_release(client: HttpClient, mbid: str) -> FetchResult:
    return mb_get(client, f"release/{mbid}", {"inc": "labels+release-groups+url-rels+genres+tags+artist-credits"})


def mb_lookup_release_group(client: HttpClient, mbid: str) -> FetchResult:
    return mb_get(client, f"release-group/{mbid}", {"inc": "genres+tags+url-rels+artist-credits"})


def mb_lookup_artist(client: HttpClient, mbid: str) -> FetchResult:
    return mb_get(client, f"artist/{mbid}", {"inc": "aliases+genres+tags+url-rels+label-rels+artist-rels"})


def mb_browse_artist_releases(client: HttpClient, mbid: str) -> FetchResult:
    return mb_get(client, "release", {"artist": mbid, "inc": "labels+release-groups", "limit": "100"})


def credit_text(artist_credit: list[dict] | None) -> str:
    return "".join(c.get("name", "") + c.get("joinphrase", "") for c in artist_credit or [])


def credit_people(artist_credit: list[dict] | None) -> list[dict]:
    return [{"credited_as": c.get("name"), "artist_name": c.get("artist", {}).get("name"),
             "artist_mbid": c.get("artist", {}).get("id"),
             "disambiguation": c.get("artist", {}).get("disambiguation") or None}
            for c in artist_credit or []]


def url_rels(entity: dict) -> list[dict]:
    return [{"type": r.get("type"), "url": r.get("url", {}).get("resource")}
            for r in entity.get("relations", []) if r.get("target-type") == "url"]


def non_url_rels(entity: dict) -> list[dict]:
    out = []
    for r in entity.get("relations", []):
        tt = r.get("target-type")
        if tt == "url":
            continue
        target = r.get(tt.replace("-", "_"), r.get(tt, {})) if tt else {}
        out.append({"type": r.get("type"), "direction": r.get("direction"), "target_type": tt,
                    "target_name": target.get("name") or target.get("title"), "target_mbid": target.get("id"),
                    "begin": r.get("begin"), "end": r.get("end"), "attributes": r.get("attributes") or []})
    return out


def genres_and_tags(entity: dict) -> dict:
    return {"genres": [{"name": g["name"], "votes": g.get("count")} for g in entity.get("genres", [])],
            "tags": [{"name": t["name"], "votes": t.get("count")} for t in entity.get("tags", [])]}


QID_RE = re.compile(r"wikidata\.org/wiki/(Q\d+)$")
DISCOGS_RE = re.compile(r"discogs\.com/(artist|release|master|label)/(\d+)")


def wikidata_qids(rels: list[dict]) -> list[str]:
    return sorted({m.group(1) for r in rels if (m := QID_RE.search(r["url"] or ""))})


def discogs_ids(rels: list[dict]) -> list[dict]:
    return [{"kind": m.group(1), "id": m.group(2), "url": r["url"]}
            for r in rels if (m := DISCOGS_RE.search(r["url"] or ""))]


# ---------------------------------------------------------------- Wikidata

def wd_get(client: HttpClient, params: dict[str, str]) -> FetchResult:
    res = client.get_json("wikidata", client.build_url(WD_API, {**params, "format": "json", "maxlag": "5"}))
    if res.ok and isinstance(res.data, dict) and "error" in res.data:
        res.ok = False
        res.error = f"API error: {res.data['error'].get('code')}"
    return res


def wd_search(client: HttpClient, text: str, limit: int = 5) -> FetchResult:
    return wd_get(client, {"action": "wbsearchentities", "search": text, "language": "en",
                           "type": "item", "limit": str(limit)})


def wd_entities(client: HttpClient, qids: list[str], props: str) -> FetchResult:
    return wd_get(client, {"action": "wbgetentities", "ids": "|".join(sorted(qids)), "props": props,
                           "languages": "en|es"})


# Propiedades consultadas (artistas y obras musicales).
WD_PROPS = {
    "P31": "instancia de", "P106": "ocupación", "P27": "ciudadanía", "P495": "país de origen",
    "P740": "lugar de formación", "P19": "lugar de nacimiento", "P569": "fecha de nacimiento",
    "P571": "fecha de fundación/creación", "P2031": "inicio de actividad", "P1477": "nombre de nacimiento",
    "P742": "seudónimo", "P136": "género", "P264": "sello discográfico", "P463": "miembro de",
    "P527": "tiene parte(s)", "P3373": "hermano/a", "P434": "MusicBrainz artist ID",
    "P1953": "Discogs artist ID", "P1902": "Spotify artist ID", "P2850": "Apple Music artist ID",
    "P2002": "X/Twitter", "P2003": "Instagram", "P3040": "SoundCloud ID", "P175": "intérprete",
    "P577": "fecha de publicación", "P435": "MusicBrainz work ID", "P4404": "MusicBrainz recording ID",
    "P436": "MusicBrainz release group ID",
}
WIKIMEDIA_IMPORT_PROPS = {"P143", "P4656", "P887", "P3452"}  # importado de proyecto Wikimedia / heurística


def _snak_value(snak: dict):
    if snak.get("snaktype") != "value":
        return {"special": snak.get("snaktype")}
    dv = snak["datavalue"]
    t, v = dv["type"], dv["value"]
    if t == "wikibase-entityid":
        return {"item": v.get("id")}
    if t == "time":
        return {"time": v["time"], "precision": v["precision"]}
    if t == "monolingualtext":
        return {"text": v["text"], "lang": v["language"]}
    if t == "quantity":
        return {"quantity": v["amount"]}
    return {"string": v}


def classify_references(refs: list[dict]) -> tuple[str, list[dict]]:
    """referenced | wikimedia_import_only | unreferenced, y las fuentes citadas."""
    if not refs:
        return "unreferenced", []
    cited, external = [], False
    for ref in refs:
        props = set(ref.get("snaks", {}))
        if props - WIKIMEDIA_IMPORT_PROPS:
            external = True
        entry = {}
        for p in ("P248", "P143", "P854", "P813"):
            for snak in ref.get("snaks", {}).get(p, []):
                entry.setdefault(p, []).append(_snak_value(snak))
        cited.append(entry)
    return ("referenced" if external else "wikimedia_import_only"), cited


def extract_claims(entity: dict) -> dict:
    out = {}
    for pid, label in WD_PROPS.items():
        stmts = [s for s in entity.get("claims", {}).get(pid, []) if s.get("rank") != "deprecated"]
        if not stmts:
            continue
        values = []
        for s in stmts:
            ref_status, cited = classify_references(s.get("references", []))
            values.append({"value": _snak_value(s["mainsnak"]), "rank": s.get("rank"),
                           "reference_status": ref_status, "references": cited})
        out[pid] = {"label": label, "values": values}
    return out


def format_time(v: dict) -> str:
    t, p = v["time"].lstrip("+"), v["precision"]
    return t[:10] if p >= 11 else t[:7] if p == 10 else t[:4] if p == 9 else f"{t[:4]} (precisión {p})"


# ---------------------------------------------------------------- Discogs

DISCOGS_STATUS = {
    "evaluated": False,
    "reason": (
        "No se realizan llamadas en esta fase. (1) La documentación y las condiciones "
        "(discogs.com/developers y support.discogs.com/.../API-Terms-of-Use) devuelven HTTP 403 a "
        "clientes automatizados, por lo que no se han podido leer completas de primera mano. "
        "(2) Lo verificable por fuentes secundarias indica restricciones relevantes para el "
        "producto: contenido mostrado con antigüedad máxima de 6 horas respecto a Discogs, "
        "almacenamiento limitado a lo necesario, atribución obligatoria 'Data provided by Discogs' "
        "y licencia separada para 'Restricted Data'. (3) Según la documentación conocida (no "
        "re-verificada hoy por el 403), /database/search requiere autenticación, y no se dispone "
        "(ni se solicita) de token."
    ),
    "token_env_var": "DISCOGS_TOKEN",
}
