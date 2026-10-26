"""Carteles 3.4: identidad musical de los nombres leídos en un cartel (MusicBrainz) y canciones para la vista rápida.

Regla de enlace automático (plan 3.0, §7), sin excepciones:
- Solo se enlaza si hay UN único candidato cuyo nombre o alias coincide exactamente tras normalizar, con
  score ≥ 95, y ningún otro candidato con ese mismo nombre normalizado. Nunca por ser el primero de la lista.
- Homónimos → `ambiguous` con sus candidatos (elige el usuario). La desambiguación solo ordena y orienta.
- Sin coincidencia exacta → `none`. Los nombres casi iguales (posible errata del cartel, p. ej. PETER GROCE) se
  ofrecen como sugerencia con su evidencia; nunca se corrige el nombre impreso.

Sin catálogo paralelo: solo MBID y datos de la búsqueda. Caché: la del cliente (24 h, en memoria) y el almacén SQLite
existente (`store`), por nombre normalizado. Un fallo de MusicBrainz nunca se guarda.
"""

from __future__ import annotations

import re
import unicodedata
from difflib import SequenceMatcher
from typing import Any

from app import normalize, profile, renames, schemas, store
from app.musicbrainz import MusicBrainzClient, NotConfigured, ProviderError, Unavailable

MAX_NAMES = 20
MAX_NAME_LEN = 100
SEARCH_LIMIT = 10
AUTO_SCORE = 95
SIMILAR_MIN = 0.85
MAX_CANDIDATES = 5
TRACKS_LIMIT = 5
STORE_KIND = "poster_resolve_v3"  # v3 (V6.8): los nombres antiguos de app/renames.py cuentan como alias
TTL_FOUND_S = 7 * 24 * 3600
TTL_NONE_S = 24 * 3600  # «sin identidad» se revisa a diario (MusicBrainz puede añadir al artista)
# Desambiguaciones que sitúan al candidato en la escena electrónica: solo ordenan y se señalan, nunca enlazan.
SCENE_RE = re.compile(r"\b(dj|house|techno|electro\w*|producer|productor|disco|garage|ambient|trance|dubstep|"
                      r"drum (and|&) bass|minimal|club|rave|dance)\b", re.IGNORECASE)


_VARIANT = re.compile(r"\s*[\(\[][^()\[\]]*[\)\]]\s*$|\s+[-–—]\s+.+$")


class ResolveError(Exception):
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


def key(name: str | None) -> str:
    """Normalización prudente: sin acentos ni mayúsculas, «&» = «and», signos como espacios. «Future.666» y
    «FUTURE 666» coinciden; «Âme» y «Ame» también. No quita palabras («DJ», «The») ni corrige letras."""
    text = unicodedata.normalize("NFKD", name or "")
    text = "".join(ch for ch in text if not unicodedata.combining(ch)).casefold().replace("&", " and ")
    return " ".join(re.sub(r"[\W_]+", " ", text).split())


def _similar(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio() if a and b else 0.0


def _candidate(raw: dict[str, Any], k: str) -> schemas.PosterCandidate | None:
    names = [raw["name"]] + [a.get("name") for a in raw.get("aliases") or [] if isinstance(a, dict) and a.get("name")]
    alias = next((n for n in names[1:] if key(n) == k), None)
    if key(raw["name"]) == k:
        match = "name"
    elif alias:
        match = "alias"
    elif max(_similar(key(n), k) for n in names) >= SIMILAR_MIN:
        match = "similar"
    else:
        return None
    s = normalize.artist_summary(raw)
    score = raw.get("score")
    return schemas.PosterCandidate(
        mbid=s.mbid, name=s.name, disambiguation=s.disambiguation, type=s.type, country=s.country,
        score=score if isinstance(score, int) else None, match=match, alias=alias,
        scene=bool(s.disambiguation and SCENE_RE.search(s.disambiguation)))


def decide(name: str, artists: list[dict[str, Any]]) -> schemas.PosterResolution:
    """Decisión pura sobre una respuesta de búsqueda de MusicBrainz (probada sin red)."""
    k = key(name)
    raw = [a for a in artists if isinstance(a, dict) and isinstance(a.get("id"), str) and a.get("name")
           and a["id"] not in normalize.SPECIAL_ARTISTS]
    cands = [c for c in (_candidate(a, k) for a in raw) if c is not None]
    exact = [c for c in cands if c.match != "similar"]
    exact.sort(key=lambda c: (not c.scene, -(c.score or 0)))
    if len(exact) == 1 and (exact[0].score or 0) >= AUTO_SCORE:
        c = exact[0]
        former = c.match == "alias" and renames.is_former(c.mbid, c.alias)
        evidence = (f"Nombre anterior de {c.name}, sin homónimos" if former
                    else f"Alias «{c.alias}» de {c.name} en MusicBrainz, sin homónimos" if c.match == "alias"
                    else f"Nombre exacto en MusicBrainz (coincidencia {c.score}), sin homónimos")
        return schemas.PosterResolution(name=name, status="linked", mbid=c.mbid, canonical=c.name, candidates=[c],
                                        evidence=evidence)
    if exact:
        evidence = (f"{len(exact)} artistas de MusicBrainz se llaman así: elige el correcto" if len(exact) > 1
                    else "Coincidencia exacta poco segura en MusicBrainz: confírmala")
        return schemas.PosterResolution(name=name, status="ambiguous", candidates=exact[:MAX_CANDIDATES],
                                        evidence=evidence)
    similar = sorted(cands, key=lambda c: (-_similar(key(c.name), k), -(c.score or 0)))[:MAX_CANDIDATES]
    evidence = ("Ningún artista de MusicBrainz se llama exactamente así; hay nombres parecidos (¿errata del cartel?)"
                if similar else "Ningún artista de MusicBrainz se llama así")
    return schemas.PosterResolution(name=name, status="none", candidates=similar, evidence=evidence)


def _resolve_one(client: MusicBrainzClient, name: str) -> schemas.PosterResolution:
    k = key(name)
    if not k:
        return schemas.PosterResolution(name=name, status="none", evidence="Sin letras ni números que buscar")
    cached = store.get(STORE_KIND, k)
    if cached:
        try:
            return schemas.PosterResolution(**{**cached, "name": name})
        except ValueError:
            pass  # registro de otra versión: se vuelve a resolver
    fetched = client.search_artists(normalize.lucene_escape(name), SEARCH_LIMIT)
    result = decide(name, fetched.data.get("artists") or [])
    result.source = normalize.source(fetched).url
    if not fetched.stale:
        store.put(STORE_KIND, k, result.model_dump(exclude={"name"}),
                  TTL_NONE_S if result.status == "none" else TTL_FOUND_S)
    return result


def resolve(client: MusicBrainzClient, names: list[str]) -> list[schemas.PosterResolution]:
    """Resuelve en serie (el cliente ya espacia las peticiones a 1,1 s). Si MusicBrainz deja de responder, el resto
    queda en `error` sin más peticiones: el móvil lo reintentará después. Sin MUSICBRAINZ_CONTACT, lanza."""
    if not 1 <= len(names) <= MAX_NAMES or any(not isinstance(n, str) or not n.strip() or len(n) > MAX_NAME_LEN
                                               for n in names):
        raise ResolveError(f"Envía entre 1 y {MAX_NAMES} nombres de hasta {MAX_NAME_LEN} caracteres")
    out: list[schemas.PosterResolution] = []
    down = False
    for name in names:
        if down:
            out.append(schemas.PosterResolution(name=name, status="error", evidence="MusicBrainz no responde"))
            continue
        try:
            out.append(_resolve_one(client, name.strip()))
        except NotConfigured:
            raise
        except ProviderError as exc:
            down = isinstance(exc, Unavailable)
            out.append(schemas.PosterResolution(name=name, status="error", evidence="MusicBrainz no responde"))
    return out


def recent_tracks(recordings: list[dict[str, Any]], mbid: str, limit: int = TRACKS_LIMIT) -> list[schemas.PosterTrack]:
    """Grabaciones propias (el artista encabeza el crédito) con fecha documentada, de la más reciente a la más
    antigua y sin versiones repetidas. No es un ranking: la vista rápida lo dice. Nunca rellena hasta `limit`."""
    rows = []
    for raw in recordings:
        rec = normalize.recording(raw) if isinstance(raw, dict) else None
        if (rec is None or not rec.first_release_date or not rec.artist_credit or rec.artist_credit[0].mbid != mbid
                or raw.get("video")):
            continue
        rows.append(rec)
    rows.sort(key=lambda r: r.title.casefold())
    rows.sort(key=lambda r: r.first_release_date or "", reverse=True)
    seen: set[str] = set()
    out = []
    for r in rows:
        # Un tema, una canción: «X», «X (Live)», «X (Remix)» y «X - Edit» cuentan como «X» (la más reciente).
        k = _VARIANT.sub("", r.title).strip().casefold() or profile.base_title(r.title)
        if k in seen:
            continue
        seen.add(k)
        credit = "".join(c.name + c.join_phrase for c in r.artist_credit).strip()
        out.append(schemas.PosterTrack(recording_mbid=r.mbid, title=r.title, artist_credit=credit,
                                       first_release_date=r.first_release_date))
        if len(out) == limit:
            break
    return out
