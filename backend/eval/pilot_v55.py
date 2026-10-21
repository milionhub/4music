"""Piloto V5.5: cobertura real de género, estilo, BPM, tonalidad, sello y catálogo en 10 canciones de referencia.

    cd backend; .\\.venv\\Scripts\\python eval\\pilot_v55.py            # usa la caché de eval/pilot_v55_cache.json
    cd backend; .\\.venv\\Scripts\\python eval\\pilot_v55.py --refresh  # vuelve a consultar las fuentes externas

Identidad: cada canción se fija por MBID verificado a mano (título, crédito, versión y duración), nunca por la primera
coincidencia de una búsqueda. Fuentes candidatas, siempre cruzadas por identificadores que documenta MusicBrainz
(URL de la grabación o de sus ediciones propias), nunca por nombre:
- MusicBrainz: géneros curados de la grabación y del release-group original + enlace a Discogs (master) del grupo.
- Discogs (API pública sin token, 25 peticiones/min): estilos del lanzamiento y de su master. Solo para medir: los
  datos de la API están sujetos a sus API Terms of Use; en producción se usaría el volcado CC0 (ver docs/v5-5-...).
- ReccoBeats (sin clave; «free for personal and commercial projects»): tempo y tonalidad estimados por su propio
  análisis, por ID de pista de Spotify enlazado en MusicBrainz.
- Deezer (solo evidencia; sus condiciones lo limitan a uso no comercial): BPM por ISRC y existencia del catálogo.
Las respuestas se guardan en eval/pilot_v55_cache.json para repetir el piloto sin volver a consultar a nadie.
"""

from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient  # noqa: E402

from app import acousticbrainz, tracks  # noqa: E402
from app.main import app  # noqa: E402

HERE = Path(__file__).resolve().parent
CACHE = HERE / "pilot_v55_cache.json"
RESULTS = HERE / "pilot_v55_results.json"
UA = "music-discovery/0.1 (TrackDNA V5.5 coverage pilot; portfolio project)"

# (nombre, MBID verificado o None si no existe en MusicBrainz, búsqueda de comprobación de catálogo)
PILOT = [
    ("Desire — Chris Stussy", "9d619150-6b0f-4f14-b038-8503ae4c6c8f", "Chris Stussy Desire"),
    ("Double C — PAWSA", "df73a61d-f713-4611-8715-5e4ac6c820d6", "PAWSA Double C"),
    ("Hoodlum — Traumer", "98e34bc2-0e71-4205-8986-af891195ed4e", "Traumer Hoodlum"),
    ("Lovelee Dae — Blaze", "8edae321-48fc-4ae6-add1-bc976cb1a823", "Blaze Lovelee Dae"),
    # Varias versiones en MusicBrainz (radio edit, 12" club mix, remixes): se fija la 12" club mix de 1998.
    ("Music Sounds Better With You — Stardust", "6e8b1a97-9b49-4898-9aa3-68db185b3653", "Stardust Music Sounds Better With You"),
    # Original (no la extended mix 89fbe5e3…).
    ("Dirty Cash (Money Talks) — PAWSA", "f2399817-454b-4c24-8af4-b7c1b17dc00a", "PAWSA Dirty Cash Money Talks"),
    # Original (no la extended mix a0fe0116…).
    ("Crazy — ANOTR", "4358ddcc-119a-48ae-9401-5413b8514441", "ANOTR Crazy"),
    ("Breather — Chris Stussy", "e0ee17b8-17d3-4514-8579-9a1fd127b57f", "Chris Stussy Breather"),
    ("Playground — Arapu", None, "Arapu Playground"),
    ("Vinotinto — Luciano", None, "Luciano Vinotinto"),
]


class Http:
    """GET JSON con caché en disco, pausa por proveedor y medición de peticiones y latencia."""

    PAUSE = {"api.discogs.com": 2.6, "musicbrainz.org": 1.1, "api.reccobeats.com": 0.5, "api.deezer.com": 0.3}

    def __init__(self, refresh: bool):
        self.refresh = refresh
        self.cache: dict = json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.exists() else {}
        self.calls: dict[str, list[float]] = {}
        self.last: dict[str, float] = {}

    def get(self, url: str):
        if not self.refresh and url in self.cache:
            return self.cache[url]
        host = urllib.parse.urlparse(url).hostname or ""
        wait = self.PAUSE.get(host, 0.5) - (time.monotonic() - self.last.get(host, 0))
        if wait > 0:
            time.sleep(wait)
        started = time.monotonic()
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=20) as r:
                body = {"status": r.status, "json": json.loads(r.read().decode("utf-8"))}
        except urllib.error.HTTPError as e:
            body = {"status": e.code, "json": None}
        except (urllib.error.URLError, TimeoutError, ValueError) as e:
            body = {"status": 0, "json": None, "error": str(e)}
        self.last[host] = time.monotonic()
        self.calls.setdefault(host, []).append(round(time.monotonic() - started, 2))
        if body["status"] in (200, 404):
            self.cache[url] = body
        return body

    def save(self):
        CACHE.write_text(json.dumps(self.cache, ensure_ascii=False, indent=1), encoding="utf-8")


def ext(t: dict, provider: str, kind: str) -> list[str]:
    return [e["id"] for e in (t.get("identifiers") or {}).get("external", []) if e["provider"] == provider and e["kind"] == kind]


def trait(t: dict, key: str) -> dict | None:
    return next((x for x in t["dna"]["traits"] if x["key"] == key and x["status"] != "unavailable" and x["values"]), None)


def discogs_styles(http: Http, kind: str, ids: list[str], limit: int = 2) -> list[dict]:
    out = []
    for i in ids[:limit]:
        r = http.get(f"https://api.discogs.com/{kind}s/{i}")
        j = r["json"] or {}
        if j:
            out.append({"id": i, "genres": j.get("genres") or [], "styles": j.get("styles") or [],
                        "year": j.get("year") or j.get("released"), "master_id": j.get("master_id"),
                        "labels": [lab.get("name") for lab in j.get("labels") or []][:2]})
    return out


def reccobeats(http: Http, ids: list[str], length_ms: int | None, isrcs: list[str]) -> dict:
    """Pistas de ReccoBeats por ISRC o ID de Spotify, aceptadas solo si el ISRC es de la grabación y la duración casa."""
    ids = list(dict.fromkeys(ids))[:5]
    if not ids:
        return {"ids": [], "tracks": [], "features": []}
    q = ",".join(ids)
    tr = (http.get(f"https://api.reccobeats.com/v1/track?ids={q}")["json"] or {}).get("content", [])
    ft = {f["id"]: f for f in (http.get(f"https://api.reccobeats.com/v1/audio-features?ids={q}")["json"] or {}).get("content", [])}
    out = []
    for x in tr:
        ok_isrc = not isrcs or x.get("isrc") in isrcs
        ok_len = length_ms is None or (x.get("durationMs") and abs(x["durationMs"] - length_ms) <= 0.03 * length_ms)
        f = ft.get(x["id"], {})
        out.append({"title": x.get("trackTitle"), "artists": [a["name"] for a in x.get("artists", [])], "isrc": x.get("isrc"),
                    "duration": x.get("durationMs"), "match": bool(ok_isrc and ok_len), "tempo": f.get("tempo"), "key": f.get("key"), "mode": f.get("mode")})
    return {"ids": ids, "features": out}


def run(refresh: bool) -> list[dict]:
    http = Http(refresh)
    client = TestClient(app)
    rows = []
    for name, mbid, query in PILOT:
        row: dict = {"name": name, "mbid": mbid}
        if not mbid:
            found = client.get("/v1/tracks/search", params={"q": query, "limit": 5}).json().get("results", [])
            dz = http.get(f"https://api.deezer.com/search?q={urllib.parse.quote(query)}&limit=5")
            hits = [(d["title"], d["artist"]["name"], d.get("isrc")) for d in (dz["json"] or {}).get("data", [])]
            row.update(catalog="ausente en MusicBrainz", mb_search=[r["title"] for r in found], deezer=hits[:3])
            # El ISRC de Deezer solo sirve aquí como pista de investigación (no se integraría Deezer).
            exact = [h for h in hits if h[2] and query.lower().split()[-1] in h[0].lower()]
            row["reccobeats"] = reccobeats(http, [h[2] for h in exact[:1]], None, [h[2] for h in exact[:1]])
            rows.append(row)
            continue
        started = time.monotonic()
        t = client.get(f"/v1/tracks/{mbid}").json()
        row["ficha_s"] = round(time.monotonic() - started, 2)
        g = trait(t, "genre")
        o = t.get("original_release") or {}
        label = trait(t, "label")
        bpm, key = trait(t, "bpm"), trait(t, "key")
        row["before"] = {
            "title": t["title"], "version": t["version"], "length": t["length_ms"], "isrc": t["isrcs"],
            "genre": g and {"values": g["values"], "scope": g["scope"]}, "release": [o.get("title"), o.get("primary_type"), o.get("secondary_types")],
            "label": label and label["values"][:2], "year": (t.get("first_release_date") or "")[:4] or None,
            "bpm": bpm and bpm["values"], "key": key and key["values"],
        }
        # MusicBrainz: grupo de lanzamientos original con géneros y enlaces (una petición).
        rg_id = (t.get("identifiers") or {}).get("release_group_mbid")
        rg = http.get(f"https://musicbrainz.org/ws/2/release-group/{rg_id}?inc=genres+url-rels&fmt=json")["json"] if rg_id else None
        masters = [u["url"]["resource"].rstrip("/").split("/")[-1] for u in (rg or {}).get("relations", [])
                   if "discogs.com/master/" in (u.get("url") or {}).get("resource", "")]
        row["mb_release_group"] = {"genres": tracks.mb_genres(rg or {}), "discogs_masters": masters}
        # Discogs: estilos de las ediciones propias enlazadas y de su master.
        releases = discogs_styles(http, "release", ext(t, "discogs", "release"))
        masters_ids = masters or list(dict.fromkeys(str(r["master_id"]) for r in releases if r.get("master_id")))
        row["discogs"] = {"releases": releases, "masters": discogs_styles(http, "master", masters_ids, 1)}
        # ReccoBeats: por ISRC de la grabación (o pista de Spotify enlazada); la duración debe coincidir (±3 %).
        row["reccobeats"] = reccobeats(http, t["isrcs"] + ext(t, "spotify", "track"), t["length_ms"], t["isrcs"])
        # Deezer (evidencia): BPM por ISRC.
        dz = [http.get(f"https://api.deezer.com/track/isrc:{i}")["json"] or {} for i in t["isrcs"][:1]]
        row["deezer"] = [{"bpm": d.get("bpm"), "duration": d.get("duration"), "label": (d.get("album") or {}).get("label")} for d in dz if d.get("id")]
        rows.append(row)
    http.save()
    for host, times in http.calls.items():
        print(f"[peticiones] {host}: {len(times)}, media {sum(times) / len(times):.2f} s")
    return rows


def key_name(pitch: int | None, mode: int | None) -> tuple[str, str] | None:
    """Tonalidad (notación de Spotify: 0 = Do…11 = Si, mode 1 mayor / 0 menor) en español y Camelot."""
    if pitch is None or pitch < 0 or mode not in (0, 1):
        return None
    if mode == 0:
        return f"{acousticbrainz.SPANISH_MINOR[pitch]} menor", f"{acousticbrainz.CAMELOT_MINOR[pitch]}A"
    return f"{acousticbrainz.SPANISH_MAJOR[pitch]} mayor", f"{acousticbrainz.CAMELOT_MAJOR[pitch]}B"


if __name__ == "__main__":
    out = run("--refresh" in sys.argv)
    for r in out:
        for f in (r.get("reccobeats") or {}).get("features", []) or []:
            f["key_es"] = key_name(f.get("key"), f.get("mode"))
    RESULTS.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=1))
