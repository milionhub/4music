"""Convierte respuestas de MusicBrainz al contrato propio. Nunca rellena: lo que falta queda en null o []."""

from __future__ import annotations

import re
from typing import Any

from app import schemas
from app.links import normalize_links
from app.musicbrainz import BadResponse, Fetched

MBID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
LUCENE_SPECIAL = re.compile(r'([+\-&|!(){}\[\]^"~*?:\\/])')
MAX_ALIASES = 5


def is_mbid(value: str) -> bool:
    return bool(MBID_RE.match(value))


def lucene_escape(text: str) -> str:
    return LUCENE_SPECIAL.sub(r"\\\1", text)


def _str(value: Any) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def source(fetched: Fetched, page_url: str | None = None) -> schemas.Source:
    return schemas.Source(url=page_url or fetched.url, fetched_at=fetched.fetched_at, stale=fetched.stale)


def artist_summary(raw: dict[str, Any]) -> schemas.ArtistSummary:
    return schemas.ArtistSummary(
        mbid=raw["id"], name=raw.get("name") or "", sort_name=_str(raw.get("sort-name")),
        disambiguation=_str(raw.get("disambiguation")), type=_str(raw.get("type")),
        country=_str(raw.get("country")), area=_str((raw.get("area") or {}).get("name")),
        begin_date=_str((raw.get("life-span") or {}).get("begin")))


def artist(fetched: Fetched) -> schemas.Artist:
    raw = fetched.data
    if not isinstance(raw.get("id"), str) or not raw.get("name"):
        raise BadResponse("Ficha de artista sin id o nombre")
    aliases: list[str] = []
    for a in raw.get("aliases") or []:
        name = _str(a.get("name"))
        if name and name != raw.get("name") and name not in aliases:
            aliases.append(name)
    summary = artist_summary(raw)
    links = normalize_links([r for r in raw.get("relations") or [] if isinstance(r, dict)])
    return schemas.Artist(**summary.model_dump(), aliases=aliases[:MAX_ALIASES], links=links,
                          source=source(fetched, f"https://musicbrainz.org/artist/{raw['id']}"))


def search_results(fetched: Fetched) -> list[schemas.SearchResult]:
    out = []
    for raw in fetched.data.get("artists") or []:
        if not isinstance(raw.get("id"), str) or not raw.get("name"):
            continue
        s = artist_summary(raw)
        score = raw.get("score")
        out.append(schemas.SearchResult(mbid=s.mbid, name=s.name, disambiguation=s.disambiguation, type=s.type,
                                        country=s.country, area=s.area,
                                        score=score if isinstance(score, int) else None))
    return out


def credited_artists(raw_recording: dict[str, Any]) -> list[schemas.CreditedArtist]:
    out = []
    for credit in raw_recording.get("artist-credit") or []:
        a = credit.get("artist") or {}
        if isinstance(a.get("id"), str):
            out.append(schemas.CreditedArtist(mbid=a["id"], name=credit.get("name") or a.get("name") or "",
                                              join_phrase=credit.get("joinphrase") or ""))
    return out


def recording(raw: dict[str, Any]) -> schemas.Recording | None:
    if not isinstance(raw.get("id"), str) or not raw.get("title"):
        return None
    length = raw.get("length")
    return schemas.Recording(mbid=raw["id"], title=raw["title"], artist_credit=credited_artists(raw),
                             length_ms=length if isinstance(length, int) and length > 0 else None,
                             first_release_date=_str(raw.get("first-release-date")),
                             disambiguation=_str(raw.get("disambiguation")))


def recordings(fetched: Fetched) -> tuple[list[schemas.Recording], int | None, int]:
    """Devuelve (grabaciones válidas, total declarado, descartadas por forma inesperada)."""
    raw = [x for x in fetched.data.get("recordings") or []]
    items = [r for r in (recording(x) if isinstance(x, dict) else None for x in raw) if r is not None]
    total = fetched.data.get("recording-count")
    return items, total if isinstance(total, int) else None, len(raw) - len(items)


# Entidades especiales de MusicBrainz que no son artistas descubribles: Various Artists y [unknown].
SPECIAL_ARTISTS = {"89ad4ac3-39f7-470e-963a-56509c546377", "125ec42a-7229-4250-afc5-e057484327fe"}
