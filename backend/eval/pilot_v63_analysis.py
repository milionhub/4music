"""Piloto V6.3: ¿qué datos de análisis del track son publicables? (no se usa en la app)

Para clásicos (con AcousticBrainz) y temas underground actuales:
- ReccoBeats audio-features completos por ISRC (energía, bailabilidad, instrumental, valencia, volumen, tonalidad).
- AcousticBrainz high-level (clasificadores entrenados): bailable, voz/instrumental, timbre, ánimo; como referencia.
- Etiquetas de MusicBrainz (tags) de la grabación y su release-group: ¿cuántos géneros/subgéneros más aparecen?
Uso: con el backend en marcha, `python eval/pilot_v63_analysis.py`.
"""

import json
import sys
import time
import urllib.parse
import urllib.request

API = "http://127.0.0.1:8000"
UA = {"User-Agent": "music-discovery/0.1 (pilot v6.3)", "Accept": "application/json"}


def get(url, timeout=180):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def safe(url, timeout=60):
    try:
        return get(url, timeout)
    except Exception as e:  # noqa: BLE001 - piloto
        return {"_error": str(e)}


def tracks_to_test():
    out = []
    catalog = open("../mobile/src/lib/home-catalog.ts", encoding="utf-8").read()
    import re
    for m in re.findall(r"mbid: '([0-9a-f-]{36})', title: '([^']*)'", catalog)[:10]:
        out.append(("clásico", m[0], m[1]))
    for name in ["Traumer", "PAWSA", "Chris Stassy", "Kerri Chandler", "Dam Swindle", "Mall Grab", "Rossi."]:
        a = (safe(f"{API}/v1/artists/search?q=" + urllib.parse.quote(name)).get("results") or [{}])[0]
        if not a.get("mbid"):
            continue
        for t in (safe(f"{API}/v1/artists/{a['mbid']}/essentials", 180).get("tracks") or [])[:3]:
            if t["catalog"] == "musicbrainz":
                out.append(("underground", t["id"], t["title"]))
    return out


def main():
    rows = []
    for kind, mbid, title in tracks_to_test():
        d = safe(f"{API}/v1/tracks/{mbid}", 180)
        if "_error" in d:
            continue
        isrcs = d.get("isrcs") or []
        rb = {}
        if isrcs:
            q = urllib.parse.quote(",".join(isrcs[:5]), safe=",")
            feats = (safe(f"https://api.reccobeats.com/v1/audio-features?ids={q}").get("content") or [])
            rb = feats[0] if feats else {}
        hl = safe(f"https://acousticbrainz.org/api/v1/{mbid}/high-level")
        h = (hl.get("highlevel") or {}) if "_error" not in hl else {}
        rec = safe(f"https://musicbrainz.org/ws/2/recording/{mbid}?inc=tags+genres+release-groups&fmt=json")
        time.sleep(1.1)
        tags = sorted({t["name"] for t in rec.get("tags") or []})
        genre = next((t for t in d["dna"]["traits"] if t["key"] == "genre"), {})
        rows.append({
            "kind": kind, "title": title[:26], "genre_now": genre.get("values") if genre.get("status") != "unavailable" else None,
            "mb_tags": tags[:6],
            "rb": {k: rb.get(k) for k in ("energy", "danceability", "instrumentalness", "valence", "loudness", "key", "mode", "tempo")} if rb else None,
            "ab": {k: (h.get(k) or {}).get("value") for k in ("danceability", "voice_instrumental", "timbre", "mood_party", "mood_relaxed", "genre_electronic")} if h else None,
        })
        print(json.dumps(rows[-1], ensure_ascii=False))
    n = len(rows)
    print(f"\n{n} temas · ReccoBeats con rasgos: {sum(1 for r in rows if r['rb'])} · AcousticBrainz high-level: "
          f"{sum(1 for r in rows if r['ab'])} · género hoy: {sum(1 for r in rows if r['genre_now'])} · con tags MB: "
          f"{sum(1 for r in rows if r['mb_tags'])}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
