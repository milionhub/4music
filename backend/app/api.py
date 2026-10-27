"""Endpoints /v1 de #4MUSIC (Explorar, Descubrir y TrackDNA). MusicBrainz y Wikimedia solo se
consultan aquí, a través de sus clientes."""

from __future__ import annotations

import re
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from functools import lru_cache

from fastapi import APIRouter, Depends, Request

from app import (acousticbrainz, affinity, biography, config, deezer, discogs, essentials, discogs_tracks, editorial, facts, images, normalize, poster_identity,
                 posters, profile, reccobeats, recommend, renames,
                 schemas, sources, stories, store, track_ai, tracks, wikidata)
from app.groq_client import GroqClient, GroqError
from app.musicbrainz import (BadResponse, Fetched, LabsClient, ListenBrainzClient, MusicBrainzClient, ProviderError,
                             WikimediaClient)

router = APIRouter(prefix="/v1")

SEARCH_MAX_LIMIT = 25
MAX_QUERY_LEN = 100
MAX_SEEDS = 5
MAX_EXCLUDE = 300
DISCOVERY_MAX_LIMIT = 50
WIKIMEDIA_INTERVAL_S = 0.5


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str):
        super().__init__(message)
        self.status, self.code, self.message = status, code, message


@lru_cache
def get_client() -> MusicBrainzClient:
    """Un único cliente por proceso: comparte caché y límite de ritmo entre peticiones."""
    return MusicBrainzClient(config.musicbrainz_contact())


@lru_cache
def get_lb_client() -> ListenBrainzClient:
    """Popularidad de ListenBrainz: solo activa con LISTENBRAINZ_TOKEN (opcional) en backend/.env."""
    return ListenBrainzClient(config.musicbrainz_contact(), config.listenbrainz_token())


@lru_cache
def get_groq_client() -> GroqClient:
    """Groq solo en el backend (GROQ_API_KEY / GROQ_MODEL en backend/.env)."""
    return GroqClient(config.groq_api_key(), config.groq_model())


IMAGE_KIND = "image"
IMAGE_TTL_OK_S = 14 * 24 * 3600
IMAGE_TTL_NONE_S = 24 * 3600  # «sin foto» se revisa a diario (Wikidata/Commons pueden añadirla)
# v2: Wikidata también por el ID de Discogs y fotos de Commons que representan (P180) al artista.
# v3: foto de Deezer (V6) cuando no hay ninguna con licencia libre. Los «sin foto» guardados con una versión anterior se
# resuelven de nuevo una vez; las fotos ya encontradas no se tocan.
IMAGE_RESOLVER_VERSION = 3


def _image_hit(mbid: str) -> dict | None:
    hit = store.get(IMAGE_KIND, mbid)
    if hit is not None and not hit.get("image") and hit.get("v", 1) < IMAGE_RESOLVER_VERSION:
        return None
    if hit is not None and (hit.get("image") or {}).get("source") == "deezer" and not config.noncommercial_sources():
        return None  # con DATA_USE=commercial no se sirve una foto de Deezer guardada antes
    return hit


def _canonical(fetched: Fetched, mbid: str) -> str:
    """MusicBrainz redirige los MBID fusionados: la identidad (y Wikidata P434) usa el MBID canónico."""
    real = fetched.data.get("id")
    return real if isinstance(real, str) and normalize.is_mbid(real) else mbid


def _deezer_record(client: MusicBrainzClient, fetched: Fetched, mbid: str) -> dict | None:
    """Ficha del artista en Deezer verificada por identificadores (app/deezer.py, caché propia). Las grabaciones y la
    discografía de MusicBrainz solo se piden si hacen falta. Lanza deezer.Unavailable ante un fallo temporal."""
    def recordings():
        rec, _ = _section(lambda: client.recordings(mbid))
        return [x for x in (rec.data.get("recordings") or []) if isinstance(x, dict)] if rec else []

    def titles():
        rg, _ = _section(lambda: client.release_groups(mbid))
        return [str(g.get("title") or "") for g in (rg.data.get("release-groups") or []) if isinstance(g, dict)] if rg else []

    return deezer.resolve(fetched.data, mbid, recordings, titles)


def _deezer_image(client: MusicBrainzClient, fetched: Fetched, mbid: str) -> tuple[schemas.ArtistImage | None, bool]:
    """Foto de la ficha de Deezer del artista. (imagen, fallo temporal)."""
    try:
        return deezer.artist_image(_deezer_record(client, fetched, mbid)), False
    except deezer.Unavailable:
        return None, True


@router.get("/artists/{mbid}/essentials", response_model=schemas.EssentialsResponse)
def artist_essentials(mbid: str, client: MusicBrainzClient = Depends(get_client)):
    """3–4 tracks esenciales con enlace a TrackDNA (app/essentials.py). Aparte del perfil, con caché propia; sin
    fuentes no comerciales o si Deezer no responde, `unavailable` (la app no muestra el bloque)."""
    mbid = _valid_mbid(mbid)
    if not config.noncommercial_sources():
        return schemas.EssentialsResponse(artist_mbid=mbid, status="unavailable")
    fetched = client.artist(mbid)
    canonical = _canonical(fetched, mbid)
    try:
        return essentials.cached_or_build(canonical, lambda: _deezer_record(client, fetched, canonical), client)
    except deezer.Unavailable:
        return schemas.EssentialsResponse(artist_mbid=canonical, status="unavailable")


def _image_for(fetched: Fetched, mbid: str, wiki: WikimediaClient, wd: wikidata.WikidataInfo | None = None,
               client: MusicBrainzClient | None = None):
    """Foto verificada con caché persistente por MBID (la comparten ficha, tarjetas y Carteles). Primero las de licencia
    libre o permiso documentado; si no hay, la de Deezer (solo con fuentes no comerciales activadas).
    Se guarda con el MBID pedido y con el canónico, para que todas las vistas encuentren la misma foto."""
    hit = _image_hit(mbid)
    if hit is not None:
        return (schemas.ArtistImage.model_validate(hit["image"]) if hit.get("image") else None), hit.get("reason")
    canonical = _canonical(fetched, mbid)
    wd = wd or wikidata.resolve(fetched.data, canonical, wiki)
    image, reason = images.resolve(fetched, canonical, wiki, wd)
    if image is None and reason != "unavailable" and client is not None and config.noncommercial_sources():
        image, failed = _deezer_image(client, fetched, canonical)
        reason = None if image else ("unavailable" if failed else reason)
    if reason != "unavailable":  # los fallos temporales no se guardan
        payload = {"image": image.model_dump() if image else None, "reason": reason, "v": IMAGE_RESOLVER_VERSION}
        for key in dict.fromkeys((mbid, canonical)):
            store.put(IMAGE_KIND, key, payload, IMAGE_TTL_OK_S if image else IMAGE_TTL_NONE_S)
    return image, reason


@lru_cache
def get_labs_client() -> LabsClient:
    """ListenBrainz Labs: sin token; servicio experimental (sin garantía de disponibilidad)."""
    return LabsClient(config.musicbrainz_contact(), min_interval_s=0.5)


@lru_cache
def get_wiki_client() -> WikimediaClient:
    """Wikidata + Commons: proveedor distinto, con su propio límite de ritmo y caché."""
    return WikimediaClient(config.musicbrainz_contact(), min_interval_s=WIKIMEDIA_INTERVAL_S)


def _valid_mbid(mbid: str) -> str:
    mbid = mbid.strip().lower()
    if not normalize.is_mbid(mbid):
        raise ApiError(422, "invalid_mbid", f"'{mbid}' no es un MBID válido")
    return mbid


def _mbid_list(raw: str, field: str, maximum: int) -> list[str]:
    values = [v.strip().lower() for v in raw.split(",") if v.strip()]
    bad = [v for v in values if not normalize.is_mbid(v)]
    if bad:
        raise ApiError(422, "invalid_mbid", f"{field}: '{bad[0]}' no es un MBID válido")
    if len(values) > maximum:
        raise ApiError(422, "invalid_query", f"{field}: máximo {maximum} MBID")
    return list(dict.fromkeys(values))


def _limit(raw: str, default: int, maximum: int) -> int:
    try:
        value = int(raw) if raw else default
    except ValueError:
        raise ApiError(422, "invalid_query", "limit debe ser un número entero") from None
    if not 1 <= value <= maximum:
        raise ApiError(422, "invalid_query", f"limit debe estar entre 1 y {maximum}")
    return value


def _section(fetch) -> tuple[Fetched | None, str | None]:
    """Una sección secundaria que falla no tumba la ficha: se devuelve su código de error."""
    try:
        return fetch(), None
    except ProviderError as exc:
        if exc.code == "provider_not_configured":
            raise
        return None, exc.code


def _status(fetched: Fetched | None, error: str | None, count: int, total: int | None,
            skipped: int = 0) -> schemas.SectionStatus:
    if fetched is None:
        return schemas.SectionStatus(status="error", error_code=error)
    if count == 0 and skipped:  # la fuente devolvió datos, pero ninguno con la forma esperada
        return schemas.SectionStatus(status="error", error_code="provider_bad_response", total=total,
                                     skipped=skipped, source=normalize.source(fetched))
    return schemas.SectionStatus(status="ok" if count else "empty", total=total, skipped=skipped,
                                 source=normalize.source(fetched))


@router.get("/artists/search", response_model=schemas.SearchResponse)
def search_artists(q: str = "", limit: str = "", client: MusicBrainzClient = Depends(get_client)):
    query = q.strip()
    if not query or len(query) > MAX_QUERY_LEN:
        raise ApiError(422, "invalid_query", f"q es obligatorio y admite hasta {MAX_QUERY_LEN} caracteres")
    fetched = client.search_artists(normalize.lucene_escape(query), _limit(limit, 10, SEARCH_MAX_LIMIT))
    return schemas.SearchResponse(query=query, results=normalize.search_results(fetched),
                                  source=normalize.source(fetched))


def _wikimedia_module(fetched: Fetched, mbid: str, wiki: WikimediaClient, country: str | None,
                      client: MusicBrainzClient):
    """Wikidata (identidad, estilos, ocupaciones, nombre del país) + foto. Nunca lanza."""
    wd = wikidata.resolve(fetched.data, _canonical(fetched, mbid), wiki)
    labels = wikidata.labels(wiki, wikidata.all_label_ids(wd)) if wd.qid else {}
    image, image_reason = _image_for(fetched, mbid, wiki, wd, client)
    # Introducción de Wikipedia (una petición, en caché): solo para contrastar y precisar los géneros.
    intro = sources.wikipedia_summary(wiki, wd) if wd.wikipedia else None
    # La introducción literal (misma petición, en caché) para presentar al artista en la vista rápida de Carteles.
    lead = sources.wikipedia_lead(wiki, wd) if wd.wikipedia else None
    summary = schemas.Excerpt(text=lead[1].text, language=lead[0], source=lead[1].ref()) if lead else None
    return wd, labels, image, image_reason, wikidata.country_name(wiki, country), intro, summary


def _musicbrainz_module(client: MusicBrainzClient, mbid: str):
    rec, rec_error = _section(lambda: client.recordings(mbid))
    rg, rg_error = _section(lambda: client.release_groups(mbid))
    return rec, rec_error, rg, rg_error


def _listenbrainz_module(lb: ListenBrainzClient, mbid: str):
    if not lb.token:
        return None, "listenbrainz_token_required"  # sin token no se hace la petición (respondería 401)
    return _section(lambda: lb.top_recordings(mbid))


@router.get("/artists/{mbid}", response_model=schemas.ArtistProfileResponse)
def artist_profile(mbid: str, client: MusicBrainzClient = Depends(get_client),
                   wiki: WikimediaClient = Depends(get_wiki_client), lb: ListenBrainzClient = Depends(get_lb_client),
                   groq: GroqClient = Depends(get_groq_client)):
    """Perfil modular. Si falla una fuente secundaria, su módulo queda vacío con su estado; la ficha no se bloquea."""
    mbid = _valid_mbid(mbid)
    fetched = client.artist(mbid)  # identidad: sin ella no hay ficha
    artist = normalize.artist(fetched)
    covers = config.cover_art_enabled()
    # Tres proveedores independientes en paralelo (cada cliente mantiene su propio límite de ritmo).
    with ThreadPoolExecutor(max_workers=3) as pool:
        f_mb = pool.submit(_musicbrainz_module, client, mbid)
        f_wiki = pool.submit(_wikimedia_module, fetched, mbid, wiki, artist.country, client)
        f_lb = pool.submit(_listenbrainz_module, lb, mbid)
        rec, rec_error, rg, rg_error = f_mb.result()
        wd, labels, image, image_reason, country_name, intro, summary = f_wiki.result()
        lb_fetched, lb_error = f_lb.result()

    recordings_raw = [x for x in (rec.data.get("recordings") or []) if isinstance(x, dict)] if rec else []
    groups_raw = [x for x in (rg.data.get("release-groups") or []) if isinstance(x, dict)] if rg else []
    recent = profile.recent_releases(groups_raw, mbid, covers)
    highlights, highlights_title = profile.highlights(fetched.data, recordings_raw, groups_raw, mbid)
    tracks = profile.top_tracks((lb_fetched.data.get("items") or []) if lb_fetched else [], covers)
    collaborators = [h.artist.name for h in highlights if h.kind != "relation"]
    bio, bio_pending = _choose_bio(mbid, artist, wd, labels, groups_raw, collaborators, groq)

    sources = [schemas.SourceRef(label="MusicBrainz", url=artist.source.url, license="CC0")]
    if wd.qid:
        sources.append(schemas.SourceRef(label=f"Wikidata {wd.qid}", url=f"https://www.wikidata.org/wiki/{wd.qid}",
                                         license="CC0"))
    styles = profile.styles(wd, labels, artist.disambiguation, intro.text if intro else None)
    if intro and any(s.source == "wikipedia" for s in styles):
        sources.append(schemas.SourceRef(label=f"{intro.label} (géneros)", url=intro.url, license=intro.license))
    if image:
        sources.append(schemas.SourceRef(label="Foto (Deezer)" if image.source == "deezer" else "Foto", url=image.page_url,
                                         license=image.license))
    identity, discogs_ref = _with_discogs(profile.identity(fetched.data, artist, wd, country_name), fetched.data,
                                          artist.name)
    if discogs_ref:
        sources.append(discogs_ref)
    if tracks:
        sources.append(schemas.SourceRef(label="ListenBrainz (popularidad)", url="https://listenbrainz.org"))
    if covers and (recent or any(t.cover_url for t in tracks)):
        sources.append(schemas.SourceRef(label="Cover Art Archive (portadas)", url="https://coverartarchive.org"))

    return schemas.ArtistProfileResponse(
        artist=artist, identity=identity,
        image=image, image_reason=image_reason,
        styles=styles, bio=bio, bio_pending=bio_pending, summary=summary,
        top_tracks=tracks,
        top_tracks_status=_status(lb_fetched, lb_error, len(tracks), None),
        recent_releases=recent,
        first_release=profile.first_release(groups_raw, mbid, rg.data.get("release-group-count") if rg else None),
        releases_status=_status(rg, rg_error, len(recent), rg.data.get("release-group-count") if rg else None),
        highlights=highlights, highlights_title=highlights_title,
        recordings_status=_status(rec, rec_error, len(recordings_raw), rec.data.get("recording-count") if rec else None),
        platforms=[link for link in artist.links if link.primary],
        sources=sources)


@router.get("/artists/{mbid}/image", response_model=schemas.ArtistImageResponse)
def artist_image(mbid: str, client: MusicBrainzClient = Depends(get_client),
                 wiki: WikimediaClient = Depends(get_wiki_client)):
    """Foto verificada por MBID (catálogo editorial, MusicBrainz, Wikidata o Deezer); image = null con motivo si no hay."""
    mbid = _valid_mbid(mbid)
    hit = _image_hit(mbid)
    if hit is not None:  # sin tocar MusicBrainz: la foto (o su ausencia) ya se resolvió
        image = schemas.ArtistImage.model_validate(hit["image"]) if hit.get("image") else None
        return schemas.ArtistImageResponse(mbid=mbid, image=image, reason=hit.get("reason"))
    fetched, error = _section(lambda: client.artist(mbid))
    if fetched is None:
        if error == "not_found":
            raise ApiError(404, "not_found", "MusicBrainz no tiene ese artista")
        return schemas.ArtistImageResponse(mbid=mbid, image=None, reason="unavailable")
    image, reason = _image_for(fetched, mbid, wiki, client=client)
    return schemas.ArtistImageResponse(mbid=mbid, image=image, reason=reason)


def _discogs_docs(mb_artist: dict, name: str, members: list[str], groups: list[str]) -> list[sources.SourceDoc]:
    """Perfil de Discogs (índice local CC0) del único ID que MusicBrainz enlaza; integrantes y grupos solo si
    MusicBrainz no los tiene. Sin índice o con varios IDs enlazados, nada."""
    ids = wikidata.discogs_ids(mb_artist)
    index = discogs.DiscogsIndex()
    if len(ids) != 1 or not index.available:
        return []
    return discogs.artist_docs(index, ids[0], name, with_members=not members, with_groups=not groups)


def _with_discogs(identity: schemas.Identity, mb_artist: dict, name: str
                  ) -> tuple[schemas.Identity, schemas.SourceRef | None]:
    """Sellos e integrantes que constan en las notas de Discogs (CC0, índice local) y que MusicBrainz no tiene, con el
    mismo criterio que el expediente: frase clasificada como sello propio o dirigido y el nombre que sigue a la
    expresión («founder of Hellbent Records», «runs the label Atipic»). Sin índice o sin datos, la identidad no cambia."""
    docs = _discogs_docs(mb_artist, name, identity.members, identity.projects)
    if not docs:
        return identity, None
    found = facts.extract(docs, name)

    def own(kind: str, known: list[str]) -> list[str]:
        seen = {k.casefold() for k in known}
        out = []
        for fact in found:
            if fact.kind == kind and fact.source.label == discogs.PROFILE_LABEL:
                for label in facts.own_names(fact, name):
                    if label.casefold() not in seen:
                        seen.add(label.casefold())
                        out.append(label)
        return out

    founded = identity.founded_labels + own("sello propio", identity.founded_labels)
    run = own("sello que dirige", founded)
    years = dict(identity.label_years)
    for fact in found:  # año solo si la frase del sello lo da y es uno («founded … NO ART in 2017»)
        if fact.kind in ("sello propio", "sello que dirige") and fact.period and fact.period.isdigit():
            for label in facts.own_names(fact, name):
                years.setdefault(label, fact.period)
    relations = next((d.text for d in docs if d.label == discogs.RELATIONS_LABEL), "")
    members = identity.members or [m.strip() for m in (re.search(r"Integrantes: ([^.]+)\.", relations) or [None, ""])[1]
                                   .split(",") if m.strip()]
    if (founded, run, members) == (identity.founded_labels, [], identity.members):
        return identity, None
    labels = set(founded[:4] + run[:3])
    updated = identity.model_copy(update={"founded_labels": founded[:4], "run_labels": run[:3], "members": members[:6],
                                          "label_years": {k: v for k, v in years.items() if k in labels}})
    return updated, schemas.SourceRef(label="Discogs (perfil)", url=docs[0].url, license="CC0")


def _generated_bio(record: biography.BiographyRecord | None) -> schemas.Bio | None:
    """Biografía válida del registro o, si la regeneración aún no ha dado una válida, la anterior (`previous`)."""
    if not record:
        return None
    if record.status == "ok" and record.biography and not biography.quality_issue(record.biography):
        legacy = record.prompt_version < biography.PROMPT_VERSION
        text, urls, labels, licenses = (record.biography, record.source_urls, record.source_labels,
                                        record.source_licenses)
    elif record.previous and record.previous.get("biography"):
        p, legacy = record.previous, record.previous.get("prompt_version", 0) < biography.PROMPT_VERSION
        text, urls, labels, licenses = (p["biography"], p.get("source_urls") or [], p.get("source_labels") or [],
                                        p.get("source_licenses") or [])
    else:
        return None
    refs = [schemas.SourceRef(label=label, url=url, license=lic) for label, url, lic in
            zip(labels, urls, licenses or [None] * len(urls))]
    return schemas.Bio(kind="generated", text=text, sources=refs, legacy=legacy)


def _needs_translation(bio: schemas.Bio | None, wd: wikidata.WikidataInfo) -> bool:
    return bool(bio and bio.kind == "factual" and bio.language != "es" and wd.qid)


def _localized(bio: schemas.Bio | None, wd: wikidata.WikidataInfo, groq: GroqClient | None = None) -> schemas.Bio | None:
    """Respaldo en otro idioma: traducción ya validada (o, con `groq`, se genera una vez). Si no, el original."""
    if not _needs_translation(bio, wd):
        return bio
    text = (biography.translate_description(wd.qid, bio.text, groq) if groq
            else biography.stored_translation(wd.qid, bio.text)[1])
    return bio.model_copy(update={"text": text, "language": "es", "translated_from": bio.language}) if text else bio


def _editorial_entry(mbid: str) -> dict | None:
    """Texto editorial del catálogo, solo si una persona lo ha revisado: los pendientes de revisión no se publican
    (su procedencia no está acreditada como la de una biografía verificada)."""
    entry = editorial.bio(mbid)
    return entry if entry and entry.get("reviewed") else None


def _choose_bio(mbid, artist, wd, labels, groups_raw, collaborators, groq: GroqClient):
    """Prioridad: editorial revisada > generada válida (o la anterior, heredada) > identidad verificada."""
    reviewed = profile.editorial_bio(_editorial_entry(mbid))
    if reviewed:
        return reviewed, False
    record = biography.cached(mbid)
    # Sin registro de la versión actual: la biografía válida anterior (heredada) mientras se renueva.
    generated = _generated_bio(record or biography.stored(mbid))
    if generated and record:
        return generated, False
    fallback = generated or _localized(profile.identity_bio(artist, wd, labels), wd)
    # Pendiente: falta la biografía de la versión actual o la traducción del respaldo (una sola vez cada una).
    untranslated = _needs_translation(fallback, wd) and not biography.stored_translation(wd.qid, fallback.text)[0]
    return fallback, (record is None or untranslated) and groq.configured and not biography.in_cooldown()


@dataclass
class _Context:
    """Lo que la biografía y las historias comparten de un artista (una sola recopilación por petición)."""
    mbid: str
    fetched: Fetched
    artist: schemas.Artist
    wd: wikidata.WikidataInfo
    labels: dict[str, str]
    groups_raw: list[dict]
    group_total: int | None
    joint_titles: dict[str, set[str]]
    names: dict[str, str]
    collaborators: list[str]
    identity: schemas.Identity
    members: list[str]
    groups: list[str]


def _artist_context(mbid: str, client: MusicBrainzClient, wiki: WikimediaClient) -> _Context:
    fetched = client.artist(mbid)
    artist = normalize.artist(fetched)
    wd = wikidata.resolve(fetched.data, _canonical(fetched, mbid), wiki)
    labels = wikidata.labels(wiki, wikidata.all_label_ids(wd)) if wd.qid else {}
    rg, _ = _section(lambda: client.release_groups(mbid))
    groups_raw = [x for x in (rg.data.get("release-groups") or []) if isinstance(x, dict)] if rg else []
    rec, _ = _section(lambda: client.recordings(mbid))
    recordings_raw = [x for x in (rec.data.get("recordings") or []) if isinstance(x, dict)] if rec else []
    highlights, _title = profile.highlights(fetched.data, recordings_raw, groups_raw, mbid)
    # Para la biografía solo colaboraciones repetidas: ≥2 lanzamientos conjuntos DISTINTOS (las versiones de una
    # misma pista no cuentan dos veces). Un crédito aislado suele ser un vocalista invitado o un sample acreditado
    # (p. ej. Arnold Jarvis con Joseph Capriati) y no define al artista.
    joint_titles: dict[str, set[str]] = {}
    names: dict[str, str] = {}
    for g in groups_raw:
        credit = [c.get("artist") or {} for c in g.get("artist-credit") or []]
        ids = {a.get("id") for a in credit}
        if mbid in ids and g.get("title"):
            for a in credit:
                if a.get("id") and a.get("id") != mbid:
                    names[a["id"]] = a.get("name") or ""
            for other in ids - {mbid, None}:
                joint_titles.setdefault(other, set()).add(profile.base_title(g["title"]))
    collaborators = [h.artist.name for h in highlights
                     if h.kind != "relation" and len(joint_titles.get(h.artist.mbid, set())) >= 2]
    identity = profile.identity(fetched.data, artist, wd, wikidata.country_name(wiki, artist.country))
    members, groups = profile.membership(fetched.data)
    return _Context(mbid, fetched, artist, wd, labels, groups_raw, rg.data.get("release-group-count") if rg else None,
                    joint_titles, names, collaborators, identity, members, groups)


def _releases_with_labels(client: MusicBrainzClient, mbid: str) -> list[dict]:
    rel, _ = _section(lambda: client.releases_with_labels(mbid))
    return [r for r in (rel.data.get("releases") or []) if isinstance(r, dict)] if rel else []


def _collect(ctx: _Context, wiki: WikimediaClient, releases: list[dict]) -> list[sources.SourceDoc]:
    """Documentos de la biografía: MusicBrainz, Wikidata, Discogs CC0, Wikipedia (es/en u otro idioma) y web oficial."""
    label_names = [name for _id, name, _y in recommend.seed_labels(recommend.SeedData(
        mbid=ctx.mbid, name=ctx.artist.name, releases=releases), limit=3)]
    docs = [sources.musicbrainz_facts(ctx.artist, profile.recent_releases(ctx.groups_raw, ctx.mbid, covers=False, limit=6),
                                      label_names, ctx.collaborators, ctx.identity, ctx.members, ctx.groups),
            sources.musicbrainz_relations(ctx.fetched.data, ctx.artist.name),
            sources.wikidata_facts(ctx.wd, ctx.labels),
            *_discogs_docs(ctx.fetched.data, ctx.artist.name, ctx.members, ctx.groups),
            *sources.wikipedia_articles(wiki, ctx.wd)]
    homepage = next((l.url for l in ctx.artist.links if "official homepage" in l.kinds), None)
    if homepage:
        text = sources.official_site_text(homepage, f"music-discovery/0.1 ( {config.musicbrainz_contact()} )")
        if text:
            docs.append(sources.SourceDoc("", "Web oficial", homepage, None, text))
    return docs


@router.get("/artists/{mbid}/biography", response_model=schemas.BiographyResponse)
def artist_biography(mbid: str, client: MusicBrainzClient = Depends(get_client),
                     wiki: WikimediaClient = Depends(get_wiki_client), groq: GroqClient = Depends(get_groq_client)):
    """Biografía editorial generada (o reutilizada) a partir de fuentes recopiladas. Si no es posible, devuelve
    la mejor alternativa verificada; nunca falla por Groq."""
    mbid = _valid_mbid(mbid)
    ctx = _artist_context(mbid, client, wiki)

    def collect() -> list[sources.SourceDoc]:
        return sources.number(_collect(ctx, wiki, _releases_with_labels(client, mbid)), sources.BIO_MAX_TOTAL_CHARS)

    reviewed = profile.editorial_bio(_editorial_entry(mbid))
    if reviewed:
        return schemas.BiographyResponse(artist_mbid=mbid, status="ready", bio=reviewed)
    record = biography.generate(mbid, ctx.artist.name, collect, groq)
    bio = _generated_bio(record) or _localized(profile.identity_bio(ctx.artist, ctx.wd, ctx.labels), ctx.wd, groq)
    return schemas.BiographyResponse(artist_mbid=mbid, status="ready" if bio else "unavailable", bio=bio)


@router.get("/artists/{mbid}/stories", response_model=schemas.StoriesResponse)
def artist_stories(mbid: str, client: MusicBrainzClient = Depends(get_client),
                   wiki: WikimediaClient = Depends(get_wiki_client), groq: GroqClient = Depends(get_groq_client)):
    """«Más allá de la cabina»: historias breves verificables (stories.py). Se piden aparte del perfil, con caché
    propia, para que la ficha nunca espere a la investigación. Nunca falla por Groq."""
    mbid = _valid_mbid(mbid)
    hit = stories.cached(mbid)
    if hit:
        return hit
    ctx = _artist_context(mbid, client, wiki)
    releases = _releases_with_labels(client, mbid)
    trajectory = stories.trajectory_doc(mbid, ctx.groups_raw, ctx.group_total, releases, ctx.joint_titles, ctx.names)
    identity, discogs_ref = _with_discogs(ctx.identity, ctx.fetched.data, ctx.artist.name)
    refs = {"musicbrainz": schemas.SourceRef(label="MusicBrainz", url=ctx.artist.source.url, license="CC0")}
    if discogs_ref:
        refs["discogs"] = discogs_ref
    plural = ctx.artist.type == "Group" or len(identity.members) >= 2
    has_homepage = any("official homepage" in link.kinds for link in ctx.artist.links)

    def collect() -> list[sources.SourceDoc]:
        docs = _collect(ctx, wiki, releases) + ([trajectory] if trajectory else [])
        docs += _discogs_extra(ctx.fetched.data, ctx.artist.name, has_homepage)
        return sources.number(docs, sources.BIO_MAX_TOTAL_CHARS)

    kind = "dúo" if plural and len(identity.members) == 2 else "grupo" if plural else "solista o proyecto"
    return stories.generate(mbid, ctx.artist.name, kind, collect,
                            lambda: stories.structured_stories(ctx.artist.name, plural, identity, ctx.fetched.data, mbid,
                                                               trajectory, refs), groq,
                            avoid=stories.civil_names(ctx.fetched.data, ctx.artist.name))


def _discogs_extra(mb_artist: dict, name: str, has_homepage: bool) -> list[sources.SourceDoc]:
    """Perfiles CC0 de los sellos que el perfil de Discogs enlaza y, si MusicBrainz no enlaza web oficial, la web
    propia que lista Discogs (respetando robots.txt). Sin índice o con varios IDs enlazados, nada."""
    ids = wikidata.discogs_ids(mb_artist)
    index = discogs.DiscogsIndex()
    if len(ids) != 1 or not index.available:
        return []
    docs = discogs.linked_label_docs(index, ids[0], name)
    if not has_homepage:
        for site in discogs.own_sites(index, ids[0], name)[:1]:
            text = sources.official_site_text(site, f"music-discovery/0.1 ( {config.musicbrainz_contact()} )")
            if text:
                docs.append(sources.SourceDoc("", "Web oficial", site, None, text))
    return docs


def _seed_musicbrainz(client: MusicBrainzClient, mbid: str) -> tuple[recommend.SeedData | None, list[schemas.SourceRef]]:
    """Lanzamientos de la semilla (sello + créditos) y una página del sello principal. None si MusicBrainz falla."""
    try:
        releases = [r for r in client.releases_with_labels(mbid).data.get("releases") or [] if isinstance(r, dict)]
    except ProviderError as exc:
        if exc.code == "provider_not_configured":
            raise
        return None, []
    name = next((c.get("name") or (c.get("artist") or {}).get("name") for r in releases for c in r.get("artist-credit") or []
                 if (c.get("artist") or {}).get("id") == mbid), None)
    seed = recommend.SeedData(mbid=mbid, name=name or "", releases=releases)
    sources = [schemas.SourceRef(label="MusicBrainz (lanzamientos)", url=f"https://musicbrainz.org/artist/{mbid}/releases",
                                 license="CC0")]
    for label_id, label_name, _year in recommend.seed_labels(seed):
        page, _err = _section(lambda: client.label_releases(label_id))
        if page:
            seed.label_pages[label_id] = page.data
            sources.append(schemas.SourceRef(label=f"MusicBrainz (sello {label_name})",
                                             url=f"https://musicbrainz.org/label/{label_id}", license="CC0"))
    return seed, sources


def _seed_labs(labs: LabsClient, mbid: str) -> list[dict]:
    """Filas de similitud de Labs etiquetadas con su algoritmo. [] si Labs no responde (servicio experimental)."""
    rows = []
    for algorithm in LabsClient.ALGORITHMS:
        try:
            items = labs.similar_artists(mbid, algorithm).data.get("items") or []
        except ProviderError:
            continue
        rows += [{**r, "_algorithm": algorithm} for r in items if isinstance(r, dict) and r.get("artist_mbid") != mbid]
    return rows


@router.get("/discovery", response_model=schemas.DiscoveryResponse)
def discover(seeds: str = "", exclude: str = "", limit: str = "",
             client: MusicBrainzClient = Depends(get_client), labs: LabsClient = Depends(get_labs_client)):
    seed_ids = _mbid_list(seeds, "seeds", MAX_SEEDS)
    if not seed_ids:
        raise ApiError(422, "invalid_query", "seeds es obligatorio (1 a 5 MBID)")
    excluded = set(_mbid_list(exclude, "exclude", MAX_EXCLUDE))
    max_cards = _limit(limit, 20, DISCOVERY_MAX_LIMIT)
    # MusicBrainz (1 petición/s) y Labs son proveedores distintos: se consultan en paralelo.
    with ThreadPoolExecutor(max_workers=2) as pool:
        f_labs = pool.submit(lambda: {m: _seed_labs(labs, m) for m in seed_ids})
        mb_results = {m: _seed_musicbrainz(client, m) for m in seed_ids}
        labs_rows = f_labs.result()
    loaded, failed, sources = [], [], []
    for mbid in seed_ids:
        seed, seed_sources = mb_results[mbid]
        if seed is None and not labs_rows[mbid]:
            failed.append(mbid)
            continue
        seed = seed or recommend.SeedData(mbid=mbid, name="")
        seed.similar = labs_rows[mbid]
        seed.name = seed.name or "tu favorito"  # MusicBrainz no respondió: sin nombre verificado, texto neutro
        loaded.append(seed)
        sources += seed_sources
    if not loaded:
        raise ApiError(503, "provider_unavailable", "MusicBrainz y ListenBrainz Labs no responden para ninguna semilla")
    if any(s.similar for s in loaded):
        sources.append(schemas.SourceRef(label="ListenBrainz Labs (artistas similares, experimental)",
                                         url="https://labs.api.listenbrainz.org/similar-artists"))
    cards = recommend.recommend(loaded, excluded, max_cards)
    without = [s.mbid for s in loaded if not recommend.recommend([s], excluded, 1)]
    return schemas.DiscoveryResponse(cards=cards, seeds_without_results=without, seeds_failed=failed, sources=sources)


# --- TrackDNA de canciones (T2.0) ---------------------------------------------------------------------------------
TRACK_KIND = "track"
TRACK_TTL_S = 7 * 24 * 3600      # ficha ensamblada: se reutiliza una semana (sobrevive a reinicios)
# Versión del contrato de la ficha guardada. Se sube cuando cambia el esquema o la semántica de lo guardado; las
# fichas de otra versión se reconstruyen al pedirlas (y se sobrescriben). El resto de la caché no se toca.
# v1 (sin campo): T2.0 · v2: autoedición, enlaces de lanzamientos, identificadores (T2.2A) ·
# v3: enlaces agrupados por destino, con `target`/`release_type` y sin los caducados conocidos.
TRACK_CONTRACT_VERSION = 8  # 6: sin géneros de bandas sonoras ni recopilatorios; familias mezcladas de un EP (V5.7) · 7: «Electrónica» cede ante el subgénero; estilos del lanzamiento; Wikidata normalizado (V6.3)
# 5  # 5: géneros de MusicBrainz (grabación y lanzamiento), samples, mashups y covers
# 4  # 4: formatos físicos del lanzamiento en sus enlaces (Discogs solo si es una edición física)
TRACK_SEARCH_DEFAULT = 15


@router.get("/tracks/search", response_model=schemas.TrackSearchResponse)
def search_tracks(q: str = "", limit: str = "", client: MusicBrainzClient = Depends(get_client)):
    """Canciones por título o «Artista - Canción». Grabaciones reales de MusicBrainz, agrupadas sin mezclar versiones."""
    query = q.strip()
    if not query or len(query) > MAX_QUERY_LEN:
        raise ApiError(422, "invalid_query", f"q es obligatorio y admite hasta {MAX_QUERY_LEN} caracteres")
    max_results = _limit(limit, TRACK_SEARCH_DEFAULT, SEARCH_MAX_LIMIT)
    fetched = client.search_recordings(tracks.build_query(query), tracks.SEARCH_FETCH)
    results, omitted = tracks.search_results(fetched.data, query, max_results, config.cover_art_enabled())
    if not results and len(tracks._tokens(query) - tracks.NEUTRAL_TOKENS) >= 2:
        # Una sola segunda consulta, difusa (erratas), con el mismo filtro estricto de palabras. Es opcional: si
        # MusicBrainz no responde, vale la primera respuesta (sin resultados), no un error.
        retry, _retry_error = _section(lambda: client.search_recordings(tracks.fuzzy_query(query), tracks.SEARCH_FETCH))
        if retry:
            results, omitted = tracks.search_results(retry.data, query, max_results, config.cover_art_enabled())
    if not results:
        # V5.6: canciones que MusicBrainz no tiene, documentadas en Discogs (catalog = discogs). Nunca un error.
        results = discogs_tracks.search(query, max_results)
    if not results and config.noncommercial_sources():
        results = deezer.search_tracks(query, max_results)  # V6.1: ni MusicBrainz ni Discogs la tienen
    return schemas.TrackSearchResponse(query=query, results=results, omitted_mix_fragments=omitted,
                                       source=normalize.source(fetched))


def _main_artist(raw: dict) -> tuple[str | None, str | None]:
    for credit in raw.get("artist-credit") or []:
        a = (credit or {}).get("artist") or {}
        if isinstance(a.get("id"), str) and a["id"] not in normalize.SPECIAL_ARTISTS:
            return a["id"], credit.get("name") or a.get("name")
    return None, None


def _track_bundle(mbid: str, client: MusicBrainzClient, wiki: WikimediaClient) -> tuple[schemas.TrackResponse, list[dict]]:
    """Ficha de canción sin interpretación + contexto de Wikipedia para la IA. Caché persistente por MBID.
    La identidad (grabación) es obligatoria; lanzamientos, artista y Wikidata son módulos que pueden faltar."""
    hit = store.get(TRACK_KIND, mbid)
    if hit is not None and hit.get("contract") == TRACK_CONTRACT_VERSION:
        try:
            return schemas.TrackResponse.model_validate(hit["track"]), list(hit.get("wiki") or [])
        except (KeyError, ValueError):
            pass  # registro dañado: se reconstruye
    # Sin registro, caducado o de otra versión del contrato: se reconstruye y se sobrescribe (solo esta ficha).
    fetched = client.recording(mbid)
    raw = fetched.data
    if not isinstance(raw.get("id"), str) or not tracks._str(raw.get("title")):
        raise BadResponse("Grabación sin id o título")
    canonical = _canonical(fetched, mbid)
    credit_ids = tracks._credit_ids(raw)
    artist_id, artist_name = _main_artist(raw)

    def mb_part():
        rel, rel_error = _section(lambda: client.recording_releases(canonical))
        art = _section(lambda: client.artist(artist_id))[0] if artist_id else None
        return rel, rel_error, art

    # MusicBrainz (1 petición/s) y Wikimedia son proveedores distintos: en paralelo.
    with ThreadPoolExecutor(max_workers=2) as pool:
        f_mb = pool.submit(mb_part)
        f_wd = pool.submit(wikidata.resolve_statement, wiki, "P4404", canonical)
        rel, rel_error, art = f_mb.result()
        track_wd = f_wd.result()
    covers = config.cover_art_enabled()
    raw_releases = [r for r in (rel.data.get("releases") or []) if isinstance(r, dict)] if rel else []
    groups, original, original_raw, group_count = tracks.releases(raw_releases, credit_ids, covers)
    cover_url, cover_release = tracks.hero_cover(raw_releases, original_raw, credit_ids, covers)
    release_wd = (wikidata.resolve_statement(wiki, "P436", original.mbid) if original
                  else wikidata.WikidataInfo(reason="no_release"))
    artist_wd = (wikidata.resolve(art.data, _canonical(art, artist_id), wiki) if art and artist_id
                 else wikidata.WikidataInfo(reason="unavailable" if artist_id else "no_artist"))
    label_ids = list(dict.fromkeys(track_wd.genre_ids[:3] + release_wd.genre_ids[:3] + artist_wd.genre_ids[:3]))
    wd_labels = wikidata.labels(wiki, label_ids) if label_ids else {}
    artist_styles = profile.styles(artist_wd, wd_labels)
    display_name = (art.data.get("name") if art else None) or artist_name
    version = tracks.version_label(raw["title"], tracks._str(raw.get("disambiguation")), bool(raw.get("video")))
    relations = tracks.relations(raw, groups)
    rg_genres: list[str] = []
    if original and not tracks.mb_genres(raw):  # solo si la grabación no tiene los suyos: una petición menos
        rg_fetched, _rg_error = _section(lambda: client.release_group_genres(original.mbid))
        rg_genres = tracks.mb_genres(rg_fetched.data) if rg_fetched else []
    dna = tracks.dna(canonical, raw["title"], track_wd, release_wd, original, display_name, artist_wd.qid,
                     artist_styles, groups, version, relations, wd_labels, tracks.mb_genres(raw), rg_genres)

    sources_list = [schemas.SourceRef(label="MusicBrainz", url=f"https://musicbrainz.org/recording/{canonical}",
                                      license="CC0")]
    used_qids = {s.label for t in dna.traits for s in t.sources if s.label.startswith("Wikidata")}
    for info in (track_wd, release_wd, artist_wd):
        label = f"Wikidata {info.qid}"
        if info.qid and label in used_qids and all(s.label != label for s in sources_list):
            sources_list.append(schemas.SourceRef(label=label, url=f"https://www.wikidata.org/wiki/{info.qid}",
                                                  license="CC0"))
    if cover_url and cover_release:
        sources_list.append(schemas.SourceRef(label="Cover Art Archive (portada; sin licencia de reutilización)",
                                              url=f"https://musicbrainz.org/release/{cover_release}/cover-art"))
    main = schemas.TrackArtist(mbid=artist_id, name=display_name or "", styles=artist_styles) if artist_id else None
    track = schemas.TrackResponse(
        mbid=canonical, title=raw["title"].strip(), artist_credit=normalize.credited_artists(raw),
        artist_name=tracks.credit_text(raw), main_artist=main,
        length_ms=tracks._length(raw), first_release_date=tracks._str(raw.get("first-release-date")),
        disambiguation=tracks._str(raw.get("disambiguation")), video=bool(raw.get("video")), version=version,
        isrcs=tracks.isrcs(raw), cover_url=cover_url, cover_release_mbid=cover_release, original_release=original,
        releases=groups[:tracks.RELEASES_LIMIT], release_count=group_count,
        releases_status=_status(rel, rel_error, len(groups), rel.data.get("release-count") if rel else None),
        credits=tracks.credits(raw), relations=relations, links=tracks.links(raw, raw_releases, credit_ids),
        identifiers=tracks.identifiers(raw, raw_releases, original, original_raw, credit_ids), dna=dna,
        sources=sources_list, source=normalize.source(fetched, f"https://musicbrainz.org/recording/{canonical}"))
    wiki_context = [{"scope": scope, "qid": info.qid, "sites": info.wikipedia}
                    for scope, info in (("track", track_wd), ("release", release_wd), ("artist", artist_wd))
                    if info.qid and info.wikipedia]
    complete = (rel_error is None and not fetched.stale and (art is not None or not artist_id)
                and "unavailable" not in (track_wd.reason, release_wd.reason, artist_wd.reason))
    if complete:  # los fallos temporales no se guardan: la próxima visita lo reintenta
        payload = {"contract": TRACK_CONTRACT_VERSION, "track": track.model_dump(), "wiki": wiki_context}
        for key in dict.fromkeys((mbid, canonical)):
            store.put(TRACK_KIND, key, payload, TRACK_TTL_S)
    return track, wiki_context


@router.get("/tracks/ext/{track_id}", response_model=schemas.TrackResponse)
def external_track(track_id: str, client: MusicBrainzClient = Depends(get_client)):
    """Ficha de una canción fuera de MusicBrainz (`discogs:<release>:<posición>` o `deezer:<id>`), con el mismo contrato
    que la de un MBID. Ruta aparte: /tracks/{mbid} sigue aceptando solo MBID."""
    if track_id.startswith("deezer:"):
        if not config.noncommercial_sources():
            raise ApiError(404, "not_found", "Las fuentes de uso no comercial están desactivadas")
        try:
            return deezer.track_profile(track_id, client)
        except deezer.Unavailable:
            raise ApiError(503, "provider_unavailable", "Deezer no responde") from None
    return _discogs_with_deezer(discogs_tracks.profile(track_id, client))


def _discogs_with_deezer(track: schemas.TrackResponse) -> schemas.TrackResponse:
    """V6.6: una pista de Discogs (a menudo sin duración) cruzada con la misma en Deezer (artista, título y lanzamiento;
    con duración, también ella): duración, ISRC, extracto, perfil sonoro y tempo. Si nadie la clasifica, el contexto de
    su sello y su artista y el género deducido. Un fallo de una fuente no bloquea la ficha."""
    first = next(iter(track.artist_credit), None)
    if not first:
        return track
    match = None
    if config.noncommercial_sources():
        try:
            match = deezer.track_match(track.mbid, [], track.length_ms, artist_name=first.name, title=track.title,
                                       release_title=track.original_release.title if track.original_release else None)
        except deezer.Unavailable:
            pass
    seconds = (match or {}).get("duration")
    length_ms = track.length_ms or (round(seconds * 1000) if isinstance(seconds, (int, float)) and seconds > 0 else None)
    isrcs = [match["isrc"]] if match and match.get("isrc") else []
    dna = track.dna
    if isrcs:
        rb = reccobeats.lookup(track.mbid, isrcs, length_ms)
        dna = reccobeats.with_profile(reccobeats.with_tempo(dna, rb), rb)
    dna = deezer.with_tempo(dna, (match or {}).get("bpm"))
    if discogs_tracks.needs_genre(dna):
        label = next((t.values[0] for t in dna.traits if t.key == "label" and t.status != "unavailable" and t.values), None)
        collection = bool(track.original_release and set(track.original_release.secondary_types) & tracks.NON_TRACK_RELEASES)
        try:  # el sello de un recopilatorio no dice nada del sonido de la pista
            dna = discogs_tracks.with_context(dna, discogs_tracks.context_traits(None if collection else label, first.name))
        except ProviderError:
            pass
    sources = track.sources + ([schemas.SourceRef(label="Deezer (duración y extracto)", url=deezer.track_url(match),
                                                  license=deezer.LICENSE)] if match else [])
    return track.model_copy(update={"length_ms": length_ms, "isrcs": isrcs or track.isrcs, "deezer_url": deezer.track_url(match),
                                    "dna": discogs_tracks.with_inferred_genre(dna), "sources": sources})


@router.get("/tracks/ext/{track_id}/preview", response_model=schemas.TrackPreviewResponse)
def external_track_preview(track_id: str):
    """Extracto de 30 s de una canción del catálogo de Deezer (`deezer:<id>`) o de una de Discogs ya cruzada con Deezer."""
    m = deezer.EXT_ID_RE.match(track_id)
    if not config.noncommercial_sources():
        return schemas.TrackPreviewResponse(recording_mbid=track_id, reason="disabled")
    # V6.6: una pista de Discogs, por la misma de Deezer ya cruzada en su ficha (caché de deezer.track_match).
    record = {"id": m.group(1)} if m else deezer.cached_match(track_id)
    if not record:
        raise ApiError(404, "not_found", "Esta canción no tiene extracto")
    try:
        url = deezer.preview(record)
    except deezer.Unavailable:
        return schemas.TrackPreviewResponse(recording_mbid=track_id, reason="unavailable")
    return schemas.TrackPreviewResponse(recording_mbid=track_id, url=url, deezer_url=deezer.track_url(record),
                                        reason=None if url else "no_preview")


@router.get("/tracks/{mbid}", response_model=schemas.TrackResponse)
def track_profile(mbid: str, client: MusicBrainzClient = Depends(get_client),
                  wiki: WikimediaClient = Depends(get_wiki_client), groq: GroqClient = Depends(get_groq_client)):
    """Ficha TrackDNA: identidad, lanzamientos, créditos, relaciones y ADN con procedencia. La interpretación con IA
    solo se incluye si ya existe; si se puede generar, interpretation_status = pending (la app pide /interpretation)."""
    track, _wiki = _track_bundle(_valid_mbid(mbid), client, wiki)
    interpretation, status = track_ai.status_for(track.mbid, groq)
    match = _deezer_track(track)
    sources_list = track.sources + ([schemas.SourceRef(label="Deezer (extracto y sello)", url=deezer.track_url(match),
                                                       license=deezer.LICENSE)] if match else [])
    return track.model_copy(update={"interpretation": interpretation, "interpretation_status": status,
                                    "dna": _measured_dna(track, match), "deezer_url": deezer.track_url(match),
                                    "sources": sources_list})


@router.get("/tracks/ext/{track_id}/affinity", response_model=schemas.AffinityResponse)
def track_ext_affinity(track_id: str, client: MusicBrainzClient = Depends(get_client)):
    """Afines de una canción de Deezer guardada (Tu frecuencia). Las de Discogs no tienen: `unavailable`."""
    m = deezer.EXT_ID_RE.match(track_id)
    if not m or not config.noncommercial_sources():
        return schemas.AffinityResponse(recording_mbid=track_id, status="unavailable")
    try:
        return affinity.cached_or_build(track_id, lambda: affinity.seed_from_track({"id": m.group(1)}), client)
    except deezer.Unavailable:
        return schemas.AffinityResponse(recording_mbid=track_id, status="unavailable")


@router.get("/tracks/{mbid}/affinity", response_model=schemas.AffinityResponse)
def track_affinity(mbid: str, client: MusicBrainzClient = Depends(get_client),
                   wiki: WikimediaClient = Depends(get_wiki_client)):
    """Canciones afines (app/affinity.py) para «Tu frecuencia». Sin fuentes no comerciales, sin la grabación en Deezer
    o si Deezer no responde, `unavailable` (la app sigue con sus otros motivos). Si la grabación no está en Deezer por
    ISRC, se parte de la ficha de Deezer de su artista principal."""
    track, _wiki = _track_bundle(_valid_mbid(mbid), client, wiki)
    if not config.noncommercial_sources():
        return schemas.AffinityResponse(recording_mbid=track.mbid, status="unavailable")
    def seed():
        found = affinity.seed_from_track(_deezer_track(track))
        main = next((a for a in track.artist_credit if normalize.is_mbid(a.mbid)), None)
        if found or not main:
            return found
        fetched = client.artist(main.mbid)
        canonical = _canonical(fetched, main.mbid)
        label = next((t.values[0] for t in track.dna.traits if t.key == "label" and t.status != "unavailable"
                      and t.values), None)
        return affinity.seed_from_artist(_deezer_record(client, fetched, canonical), main.name, track.title, label)

    try:
        return affinity.cached_or_build(track.mbid, seed, client)
    except (deezer.Unavailable, ProviderError):
        return schemas.AffinityResponse(recording_mbid=track.mbid, status="unavailable")


def _deezer_track(track: schemas.TrackResponse) -> dict | None:
    """La grabación en Deezer (V6.1, caché propia). None sin fuentes no comerciales o si Deezer no responde."""
    if not config.noncommercial_sources():
        return None
    main = next(iter(getattr(track, "artist_credit", None) or []), None)
    try:
        return deezer.track_match(track.mbid, track.isrcs, track.length_ms, artist_name=main.name if main else None,
                                  title=getattr(track, "title", None))
    except deezer.Unavailable:
        return None


@router.get("/tracks/{mbid}/preview", response_model=schemas.TrackPreviewResponse)
def track_preview(mbid: str, client: MusicBrainzClient = Depends(get_client),
                  wiki: WikimediaClient = Depends(get_wiki_client)):
    """Extracto de 30 s de Deezer para la grabación exacta. La URL se pide en el momento porque caduca en minutos."""
    track, _wiki = _track_bundle(_valid_mbid(mbid), client, wiki)
    if not config.noncommercial_sources():
        return schemas.TrackPreviewResponse(recording_mbid=track.mbid, reason="disabled")
    try:
        match = _deezer_track(track)
        url = deezer.preview(match)
    except deezer.Unavailable:
        return schemas.TrackPreviewResponse(recording_mbid=track.mbid, reason="unavailable")
    reason = None if url else ("no_preview" if match else "no_match")
    return schemas.TrackPreviewResponse(recording_mbid=track.mbid, url=url, deezer_url=deezer.track_url(match),
                                        reason=reason)


def _measured_dna(track: schemas.TrackResponse, match: dict | None = None) -> schemas.TrackDna:
    """ADN con BPM y tonalidad medidos en AcousticBrainz si los hay; perfil sonoro de ReccoBeats (V6.3); si falta el
    tempo, el estimado por ReccoBeats
    (por ISRC y duración) y, si tampoco, el de Deezer; si falta el sello, el de Deezer (V6.1, misma grabación y año);
    si falta el género o solo es «Electrónica», el del lanzamiento propio en Discogs que contiene la misma pista y, si
    tampoco, el deducido de su artista o su sello (V6.5). Cada fuente con su
    caché propia, aparte de la ficha; un fallo no bloquea nada."""
    dna = deezer.with_label(track.dna, match, track.first_release_date)
    dna = acousticbrainz.with_measurements(dna, acousticbrainz.lookup(track.mbid, track.length_ms))
    # Sin ISRC en MusicBrainz, el de la misma grabación en Deezer (búsqueda verificada, V6.4).
    isrcs = track.isrcs or ([match["isrc"]] if match and match.get("isrc") else [])
    rb = reccobeats.lookup(track.mbid, isrcs, track.length_ms)  # caché propia; tempo y perfil sonoro
    dna = reccobeats.with_profile(reccobeats.with_tempo(dna, rb), rb)
    dna = deezer.with_tempo(dna, (match or {}).get("bpm"))
    main = getattr(track, "main_artist", None) or next(iter(getattr(track, "artist_credit", None) or []), None)
    if main and discogs_tracks.needs_genre(dna):
        try:
            dna = discogs_tracks.with_genre(dna, discogs_tracks.genre_for(track.mbid, main.name, track.title,
                                                                          track.length_ms))
        except ProviderError:
            pass  # Discogs no responde: sin género, como antes
    if main and discogs_tracks.needs_genre(dna):  # nadie la clasifica: contexto de su sello y de su artista
        label = next((t.values[0] for t in dna.traits if t.key == "label" and t.status != "unavailable" and t.values), None)
        try:
            dna = discogs_tracks.with_context(dna, discogs_tracks.context_traits(label, main.name))
        except ProviderError:
            pass
    return discogs_tracks.with_inferred_genre(dna)  # V6.5: sin clasificación propia, el de su artista o su sello


@router.get("/tracks/{mbid}/dna", response_model=schemas.TrackDna)
def track_dna(mbid: str, client: MusicBrainzClient = Depends(get_client), wiki: WikimediaClient = Depends(get_wiki_client)):
    """Solo el ADN (base para comparar canciones o SetLab en el futuro). Comparte caché con la ficha."""
    track = _track_bundle(_valid_mbid(mbid), client, wiki)[0]
    return _measured_dna(track, _deezer_track(track))


@router.get("/tracks/{mbid}/interpretation", response_model=schemas.TrackInterpretationResponse)
def track_interpretation(mbid: str, client: MusicBrainzClient = Depends(get_client),
                         wiki: WikimediaClient = Depends(get_wiki_client), groq: GroqClient = Depends(get_groq_client)):
    """Interpretación con IA generada (o reutilizada) a partir de fuentes. Nunca falla por Groq: sin texto válido
    responde insufficient_sources o unavailable y la ficha se queda con los datos verificados."""
    track, wiki_context = _track_bundle(_valid_mbid(mbid), client, wiki)
    record = track_ai.generate(track, lambda: track_ai.collect(track, wiki_context, wiki), groq)
    interpretation = track_ai.public(record)
    status = ("ready" if interpretation else
              "insufficient_sources" if record.status == "insufficient_sources" else "unavailable")
    return schemas.TrackInterpretationResponse(recording_mbid=track.mbid, status=status, interpretation=interpretation)


_POSTER_GROQ_ERRORS = {
    "not_configured": (503, "poster_ai_not_configured", "El análisis de carteles no está configurado en el servidor"),
    "rate_limited": (429, "poster_ai_rate_limited", "La IA ha alcanzado su límite. Espera un minuto y vuelve a intentarlo"),
    "unavailable": (503, "poster_ai_unavailable", "La IA no responde ahora mismo"),
    "image_too_large": (413, "image_too_large", "La IA rechazó el tamaño de la imagen"),
}


@router.post("/posters/analyze", response_model=schemas.PosterExtraction)
def analyze_poster(req: schemas.PosterAnalyzeRequest, request: Request, groq: GroqClient = Depends(get_groq_client)):
    """Carteles: una llamada a Groq Vision por petición, sin reintentos automáticos ni imagen guardada. Devuelve la
    extracción auditada (propuesta para revisar); complete=False si la respuesta se cortó."""
    try:
        posters.decode_image(req.image)  # valida antes de gastar cupo
        posters.take_quota(request.client.host if request.client else "local", config.poster_daily_limit())
        return posters.analyze(req, groq, config.groq_vision_model())
    except posters.PosterError as exc:
        raise ApiError(exc.status, exc.code, exc.message) from None
    except GroqError as exc:
        status, code, message = _POSTER_GROQ_ERRORS.get(exc.code, (502, "poster_ai_bad_response",
                                                                    "La IA devolvió una respuesta inesperada"))
        raise ApiError(status, code, message) from None


@router.post("/posters/resolve", response_model=schemas.PosterResolveResponse)
def resolve_poster_artists(req: schemas.PosterResolveRequest, client: MusicBrainzClient = Depends(get_client)):
    """Carteles 3.4: identidad de hasta 20 nombres (en serie, al ritmo de MusicBrainz). Solo enlaza lo inequívoco."""
    try:
        return schemas.PosterResolveResponse(results=poster_identity.resolve(client, req.names))
    except poster_identity.ResolveError as exc:
        raise ApiError(422, "invalid_names", exc.message) from None


SOUND_KIND = "poster_sound"
SOUND_VERSION = 2  # v2: Discogs también con el nombre anterior (app/renames.py)
SOUND_TTL_S = 6 * 3600          # el contenido de Discogs no se guarda más de 6 h (condiciones de su API)
SOUND_RELATED = 20


@router.get("/posters/artists/{mbid}/sound", response_model=schemas.PosterArtistSound)
def poster_artist_sound(mbid: str, client: MusicBrainzClient = Depends(get_client)):
    """Estilos y sellos habituales del artista en Discogs y artistas que Deezer relaciona con él (uso no comercial).
    Se guarda 6 h solo si todo respondió; un fallo deja `partial` y la app puede reintentar."""
    mbid = _valid_mbid(mbid)
    hit = store.get(SOUND_KIND, mbid)
    if hit is not None and hit.get("version") == SOUND_VERSION:
        return schemas.PosterArtistSound.model_validate(hit["sound"])
    fetched, error = _section(lambda: client.artist(mbid))
    if fetched is None:
        if error == "not_found":
            raise ApiError(404, "not_found", "MusicBrainz no tiene ese artista")
        raise ApiError(503, "provider_unavailable", "MusicBrainz no responde")
    name = str(fetched.data.get("name") or "")
    partial = False
    styles: list[str] = []
    labels: list[str] = []
    releases = 0
    sources: list[schemas.SourceRef] = []
    try:
        # Con el nombre actual y, si no da nada, con el anterior (app/renames.py): Discogs puede seguir con el antiguo.
        for query in dict.fromkeys([name, *([renames.RENAMES[mbid][0]] if mbid in renames.RENAMES else [])]):
            styles, labels, releases = discogs_tracks.artist_sound(query)
            if releases:
                break
        if releases:
            sources.append(schemas.SourceRef(label=discogs_tracks.ATTRIBUTION, license=discogs_tracks.LICENSE,
                                             url=f"{discogs_tracks.SITE}/search/?type=artist&q={urllib.parse.quote(name)}"))
    except ProviderError:
        partial = True
    related: list[schemas.PosterRelated] = []
    if config.noncommercial_sources():
        try:
            record = _deezer_record(client, fetched, mbid)
            if record:
                data = (deezer._get(f"artist/{record['id']}/related", {"limit": str(SOUND_RELATED)}, deezer._default_transport) or {}).get("data") or []
                related = [schemas.PosterRelated(name=a["name"], url=a.get("link")) for a in data
                           if isinstance(a, dict) and isinstance(a.get("name"), str) and a["name"].strip()][:SOUND_RELATED]
                if related:
                    sources.append(schemas.SourceRef(label="Deezer (artistas relacionados)", url=record.get("link") or deezer.TERMS_URL,
                                                     license=deezer.LICENSE))
        except deezer.Unavailable:
            partial = True
    sound = schemas.PosterArtistSound(artist_mbid=mbid, name=name, genre=tracks.single_family(styles), styles=styles,
                                      labels=labels, related=related, releases=releases,
                                      status="partial" if partial else "ok", sources=sources)
    if not partial:
        store.put(SOUND_KIND, mbid, {"version": SOUND_VERSION, "sound": sound.model_dump()}, SOUND_TTL_S)
    return sound


@router.get("/posters/artists/{mbid}/tracks", response_model=schemas.PosterTracksResponse)
def poster_artist_tracks(mbid: str, client: MusicBrainzClient = Depends(get_client)):
    """Canciones propias documentadas (con MBID de grabación para TrackDNA). Reutiliza la consulta del perfil."""
    mbid = _valid_mbid(mbid)
    fetched = client.recordings(mbid)
    raw = [x for x in fetched.data.get("recordings") or [] if isinstance(x, dict)]
    return schemas.PosterTracksResponse(artist_mbid=mbid, tracks=poster_identity.recent_tracks(raw, mbid),
                                        source=normalize.source(fetched))
