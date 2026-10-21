"""Fotografías de artistas: solo con identidad verificada por MBID y derechos comprobados. Nunca por nombre.

Orden de prioridad (reutilizable por Carteles a partir de un MBID):
1. Catálogo editorial (app/data/editorial.json): fotos aportadas con permiso documentado.
2. Relación «image» de MusicBrainz para ese MBID que apunte a un archivo de Wikimedia Commons.
3. Imagen P18 del ítem de Wikidata verificado (por P434 o por el ID de Discogs documentado; app/wikidata.py).
4. Sin P18: archivo de Commons cuyos datos estructurados declaran que representa (P180) ese mismo ítem. Solo si
   representa únicamente a ese ítem (no fotos de grupo ni carteles con varios artistas).
En Commons solo se aceptan CC0, dominio público, CC BY y CC BY-SA (no NC/ND) y con autor para atribuir.
"""

from __future__ import annotations

import re
from html import unescape
from urllib.parse import unquote, urlsplit

from app import editorial, schemas
from app.musicbrainz import Fetched, ProviderError, WikimediaClient
from app.wikidata import WikidataInfo

THUMB_WIDTH = 720
ALLOWED_LICENSE = re.compile(r"^(CC0|CC[ -]BY(-SA)?( \d(\.\d)?)?|Public domain|PD\b)", re.IGNORECASE)
TAG_RE = re.compile(r"<[^>]+>")


def _plain(html: str | None) -> str | None:
    text = unescape(TAG_RE.sub("", html or "")).strip()
    return re.sub(r"\s+", " ", text) or None


def license_allowed(short_name: str | None) -> bool:
    name = (short_name or "").strip()
    return bool(ALLOWED_LICENSE.match(name)) and not re.search(r"\b(NC|ND)\b", name, re.IGNORECASE)


def musicbrainz_image_files(mb_artist: dict) -> list[str]:
    """Archivos de Commons enlazados por la relación «image» de MusicBrainz (otras webs no se usan)."""
    out = []
    for rel in mb_artist.get("relations") or []:
        url = ((rel.get("url") or {}).get("resource") or "")
        parts = urlsplit(url)
        if rel.get("type") == "image" and parts.netloc.endswith("commons.wikimedia.org") and "/wiki/File:" in parts.path:
            out.append(unquote(parts.path.split("/wiki/File:", 1)[1]).replace("_", " "))
    return out


PHOTO_EXT = re.compile(r"\.(jpe?g|png|webp)$", re.IGNORECASE)


def depicting_files(wiki: WikimediaClient, qid: str) -> list[str]:
    """Fotos de Commons que representan (P180) ese ítem y solo ese: se comprueban los datos estructurados de cada
    archivo, no basta con que la búsqueda lo devuelva. [] si Commons no responde."""
    try:
        hits = (wiki.commons_depicting(qid).data.get("query") or {}).get("search") or []
    except ProviderError:
        return []
    out = []
    for hit in hits[:3]:
        title = str(hit.get("title") or "")
        if not title.startswith("File:") or not PHOTO_EXT.search(title):
            continue
        try:
            entities = (wiki.commons_depicts(title).data.get("entities") or {})
        except ProviderError:
            continue
        for ent in entities.values():
            statements = (ent.get("statements") or {}) if isinstance(ent, dict) else {}
            depicted = [((s.get("mainsnak") or {}).get("datavalue") or {}).get("value", {}).get("id")
                        for s in statements.get("P180") or [] if isinstance(s, dict)]
            if depicted == [qid]:
                out.append(title.split(":", 1)[1])
    return out


def commons_image(wiki: WikimediaClient, filename: str, via: str, wikidata_id: str | None
                  ) -> tuple[schemas.ArtistImage | None, str | None]:
    try:
        pages = (wiki.commons_file(filename, THUMB_WIDTH).data.get("query") or {}).get("pages") or {}
    except ProviderError:
        return None, "unavailable"
    page = next(iter(pages.values()), {}) if isinstance(pages, dict) else {}
    info = (page.get("imageinfo") or [{}])[0]
    meta = info.get("extmetadata") or {}
    license_name = _plain((meta.get("LicenseShortName") or {}).get("value"))
    if not license_allowed(license_name):
        return None, "license_not_allowed"
    url = (info.get("thumburl") or info.get("url") or "").split("?", 1)[0]  # sin parámetros de seguimiento
    page_url = info.get("descriptionurl")
    if not url.startswith("https://") or not isinstance(page_url, str):
        return None, "no_image"
    author = _plain((meta.get("Artist") or {}).get("value"))
    if ((meta.get("AttributionRequired") or {}).get("value") or "").lower() == "true" and not author:
        return None, "license_not_allowed"  # sin autor no podemos cumplir la atribución
    return schemas.ArtistImage(
        url=url, width=info.get("thumbwidth"), height=info.get("thumbheight"), page_url=page_url, author=author,
        license=license_name or "", license_url=_plain((meta.get("LicenseUrl") or {}).get("value")),
        source="wikimedia_commons", via=via, wikidata_id=wikidata_id), None


def resolve(mb_artist: Fetched, mbid: str, wiki: WikimediaClient, wd: WikidataInfo
            ) -> tuple[schemas.ArtistImage | None, str | None]:
    """Devuelve (imagen, motivo si no hay). Nunca lanza."""
    own = editorial.photo(mbid)
    if own:
        return schemas.ArtistImage(url=own["url"], width=own.get("width"), height=own.get("height"),
                                   page_url=own.get("source_url") or own["url"], author=own["author"],
                                   license=own["license"], license_url=own.get("license_url"),
                                   source="editorial", via="editorial_catalog", wikidata_id=None), None
    reasons = []
    for filename in musicbrainz_image_files(mb_artist.data)[:1]:
        image, reason = commons_image(wiki, filename, "musicbrainz_image", wd.qid)
        if image:
            return image, None
        reasons.append(reason)
    for filename in wd.image_files[:1]:
        image, reason = commons_image(wiki, filename, "wikidata_p18", wd.qid)
        if image:
            return image, None
        reasons.append(reason)
    if wd.qid and not wd.image_files:
        for filename in depicting_files(wiki, wd.qid)[:2]:
            image, reason = commons_image(wiki, filename, "commons_depicts", wd.qid)
            if image:
                return image, None
            reasons.append(reason)
    if reasons:
        return None, reasons[-1]
    return None, wd.reason or "no_image"
