"""Contrato de respuesta /v1 (docs/t0-contrato-datos.md). Campos ausentes en la fuente: null o []."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class Source(BaseModel):
    provider: Literal["musicbrainz", "discogs", "deezer"] = "musicbrainz"  # canción fuera de MusicBrainz (V5.6, V6.1)
    url: str
    fetched_at: str
    license: str = "CC0 (MusicBrainz core data)"
    stale: bool = False


class Link(BaseModel):
    url: str
    label: str
    platform: str | None = None   # plataforma musical reconocida por dominio (Spotify, Beatport…)
    kinds: list[str] = []         # tipos de relación de MusicBrainz fusionados para esta URL
    detail: str | None = None     # tipo legible («Compra digital», «Streaming»…) si aporta algo a la etiqueta
    primary: bool = False         # se muestra destacado; el resto va a «Más enlaces»
    scope: Literal["recording", "release"] | None = None  # TrackDNA: enlace de la grabación o de un lanzamiento suyo
    target: Literal["track", "release"] | None = None    # TrackDNA: abre la pista o el lanzamiento que la contiene
    release_type: str | None = None  # tipo principal del lanzamiento (Album, EP, Single) si target = release
    formats: list[str] = []          # formatos del lanzamiento de origen («12\" Vinyl», «Digital Media») si scope = release


class ArtistSummary(BaseModel):
    mbid: str
    name: str
    sort_name: str | None = None
    disambiguation: str | None = None
    type: str | None = None
    country: str | None = None
    area: str | None = None
    begin_date: str | None = None


class Artist(ArtistSummary):
    aliases: list[str] = []
    links: list[Link] = []
    source: Source


class SearchResult(BaseModel):
    mbid: str
    name: str
    disambiguation: str | None = None
    type: str | None = None
    country: str | None = None
    area: str | None = None
    score: int | None = None


class SearchResponse(BaseModel):
    query: str
    results: list[SearchResult]
    source: Source


class CreditedArtist(BaseModel):
    mbid: str
    name: str
    join_phrase: str = ""


class Recording(BaseModel):
    mbid: str
    title: str
    artist_credit: list[CreditedArtist]
    length_ms: int | None = None
    first_release_date: str | None = None
    disambiguation: str | None = None


class SectionStatus(BaseModel):
    """Estado de una sección de la ficha: ok, empty (la fuente no tiene datos) o error (temporal o de formato)."""
    status: Literal["ok", "empty", "error"]
    error_code: str | None = None
    total: int | None = None      # total que declara la fuente (puede superar lo devuelto)
    skipped: int = 0              # elementos descartados por no tener la forma esperada
    source: Source | None = None


class SourceRef(BaseModel):
    label: str
    url: str
    license: str | None = None


class Bio(BaseModel):
    """editorial: texto original del catálogo (con fuentes); factual: frase generada solo con datos CC0 verificados."""
    kind: Literal["editorial", "generated", "factual"]
    text: str
    language: str = "es"
    sources: list[SourceRef]
    reviewed: bool | None = None
    translated_from: str | None = None  # factual: descripción breve traducida (p. ej. del inglés), sin añadir nada
    legacy: bool = False  # generated: biografía válida de una versión anterior, a la espera de la nueva


class Excerpt(BaseModel):
    """Texto literal de una fuente con licencia (introducción de Wikipedia del ítem verificado por MBID)."""
    text: str
    language: str
    source: SourceRef


class Identity(BaseModel):
    """Identidad documentada (MusicBrainz + Wikidata verificado por MBID). Lugares con su significado exacto:
    `area` es el área asociada en MusicBrainz (no se presenta como residencia); `origin` es el begin-area:
    lugar de nacimiento si es una persona, de formación si es un grupo (sin tipo conocido no se usa)."""
    country_name: str | None = None   # país de MusicBrainz (ISO) con su nombre legible (Wikidata P297)
    area: str | None = None           # área asociada cuando no es el propio país (ciudad o región)
    origin: str | None = None
    origin_kind: Literal["birth", "formation"] | None = None
    formed_year: str | None = None    # grupos: año de inicio en MusicBrainz (en personas es el nacimiento: no se usa)
    active_since: str | None = None   # Wikidata P2031
    # Relaciones explícitas de MusicBrainz (CC0): «label founder» y «member of band». Publicar en un sello no basta.
    founded_labels: list[str] = []
    run_labels: list[str] = []        # sellos que dirige o posee (no consta que los fundara): notas de Discogs
    label_years: dict[str, str] = {}  # año de fundación o inicio de un sello, solo si consta (MusicBrainz o Discogs)
    projects: list[str] = []          # grupos o proyectos de los que es miembro
    members: list[str] = []           # integrantes (dúos y grupos)


class Style(BaseModel):
    """Género con su fuente: Wikidata (P136, CC0) para un ítem verificado, o estilo escrito en la descripción de
    MusicBrainz (CC0) o en la presentación de Wikipedia (CC BY-SA). Nunca tags de MusicBrainz (no son CC0)."""
    label: str
    qid: str | None = None
    source: Literal["wikidata", "musicbrainz", "wikipedia"] = "wikidata"


class TopTrack(BaseModel):
    recording_mbid: str
    title: str
    artist_name: str
    listen_count: int
    user_count: int | None = None
    release_name: str | None = None
    cover_url: str | None = None
    search_query: str            # para «Buscar en…»: nunca se presenta como enlace exacto


class RecentRelease(BaseModel):
    mbid: str
    title: str
    primary_type: str | None = None
    secondary_types: list[str] = []
    first_release_date: str
    with_artists: list[str] = []
    cover_url: str | None = None
    url: str                     # registro de origen en MusicBrainz


class Highlight(BaseModel):
    artist: ArtistSummary
    kind: Literal["joint_release", "featuring", "co_credit", "relation"]
    reason: str
    evidence_count: int


class ArtistImage(BaseModel):
    url: str
    width: int | None = None
    height: int | None = None
    page_url: str
    author: str | None = None
    license: str
    license_url: str | None = None
    source: Literal["wikimedia_commons", "editorial", "deezer"] = "wikimedia_commons"
    # editorial_catalog | musicbrainz_image | wikidata_p18 | commons_depicts | deezer_musicbrainz_link | deezer_isrc |
    # deezer_catalog_match
    via: str | None = None
    wikidata_id: str | None = None


class ArtistImageResponse(BaseModel):
    mbid: str
    image: ArtistImage | None
    reason: str | None = None     # no_wikidata_item, mbid_mismatch, no_image, license_not_allowed, unavailable


class Story(BaseModel):
    """Historia de «Más allá de la cabina»: breve, en español y con las fuentes de los hechos que cita."""
    key: Literal["inicios", "universo", "momento"]
    title: str
    text: str
    sources: list[SourceRef]


class EssentialTrack(BaseModel):
    """Una canción esencial del artista con su TrackDNA: MBID si MusicBrainz la tiene (por ISRC), si no `deezer:<id>`."""
    id: str
    catalog: Literal["musicbrainz", "deezer"]
    title: str
    artist_name: str
    length_ms: int | None = None
    year: str | None = None
    cover_url: str | None = None
    release_title: str | None = None
    deezer_url: str | None = None


class EssentialsResponse(BaseModel):
    """Tracks esenciales (3–4) para «Más allá de la cabina». `basis` explica el criterio (popularidad en Deezer)."""
    artist_mbid: str
    status: Literal["ready", "unavailable"]
    tracks: list[EssentialTrack] = []
    basis: str | None = None
    sources: list[SourceRef] = []


class AffinityResponse(BaseModel):
    """Canciones afines a una grabación (Inicio, «Tu frecuencia»): temas de artistas relacionados en Deezer.
    `seed_artist` es el artista de la canción de partida en Deezer. Sin Deezer o sin afines, `unavailable`."""
    recording_mbid: str
    status: Literal["ready", "unavailable"]
    seed_artist: str | None = None
    tracks: list[EssentialTrack] = []
    basis: str | None = None


class StoriesResponse(BaseModel):
    """generated: redactadas y validadas contra los hechos citados; structured: plantillas con datos verificados;
    mixed: ambas. Sin historias posibles, `unavailable` (la app no muestra la sección)."""
    artist_mbid: str
    status: Literal["ready", "unavailable"]
    mode: Literal["generated", "structured", "mixed"] | None = None
    stories: list[Story] = []
    generated_at: str | None = None


class BiographyResponse(BaseModel):
    """Biografía final de la ficha. No incluye datos técnicos del modelo (solo texto y fuentes)."""
    artist_mbid: str
    status: Literal["ready", "unavailable"]
    bio: Bio | None


class ArtistProfileResponse(BaseModel):
    """Perfil modular: cada módulo puede faltar sin bloquear los demás (reutilizable por Carteles)."""
    artist: Artist
    identity: Identity = Identity()
    image: ArtistImage | None
    image_reason: str | None = None
    styles: list[Style]
    bio: Bio | None
    bio_pending: bool = False     # la app puede pedir /biography: se está (o se puede) generar una mejor
    summary: Excerpt | None = None  # introducción de Wikipedia (vista rápida de Carteles), con su atribución
    top_tracks: list[TopTrack]
    top_tracks_status: SectionStatus
    recent_releases: list[RecentRelease]
    releases_status: SectionStatus
    # Lanzamiento propio más antiguo, solo si MusicBrainz devolvió la discografía completa (si no, no sería el primero)
    first_release: RecentRelease | None = None
    highlights: list[Highlight]
    highlights_title: Literal["collaborations", "connections"] | None
    recordings_status: SectionStatus
    platforms: list[Link]
    sources: list[SourceRef]


class RecommendationReason(BaseModel):
    kind: Literal["affinity", "shared_label", "collaboration"]
    seed_mbid: str
    seed_name: str
    strength: float               # fuerza técnica de la señal (0–1), para depurar y explicar el orden
    detail: str | None = None     # sello o título del lanzamiento conjunto
    text: str


class Recommendation(BaseModel):
    artist: ArtistSummary
    score: float                  # combinación noisy-OR de las señales (0–1); no es una «probabilidad de gustar»
    kind: Literal["affinity", "shared_label", "collaboration", "multiple_favorites"]
    tag: str                      # etiqueta corta según la evidencia («Afinidad de escucha», «Sello compartido»…)
    headline: str                 # explicación breve para la tarjeta
    reasons: list[RecommendationReason]


class DiscoveryResponse(BaseModel):
    cards: list[Recommendation]
    seeds_without_results: list[str]
    seeds_failed: list[str]
    sources: list[SourceRef]


class ErrorBody(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    error: ErrorBody


# --- TrackDNA de canciones (T2.0) ---------------------------------------------------------------------------------
class TrackSearchResult(BaseModel):
    """Una grabación de MusicBrainz (o varias idénticas agrupadas: mismo título, créditos y duración)."""
    mbid: str                     # grabación representativa (la que más lanzamientos tiene); en Discogs, «discogs:<release>:<pos>»
    catalog: Literal["musicbrainz", "discogs", "deezer"] = "musicbrainz"  # discogs (V5.6), deezer (V6.1): si MB no la tiene
    title: str
    artist_credit: list[CreditedArtist]
    artist_name: str              # crédito tal como lo escribe MusicBrainz («A feat. B»)
    artist_disambiguation: str | None = None  # del artista principal: distingue homónimos («Australian house DJ»)
    length_ms: int | None = None
    first_release_date: str | None = None
    disambiguation: str | None = None
    version: str | None = None    # «Remix», «Directo», «Vídeo»… solo si el título o MusicBrainz lo indican
    release_title: str | None = None
    release_type: str | None = None
    cover_url: str | None = None
    merged_count: int = 1         # grabaciones idénticas fusionadas en este resultado
    release_count: int = 0


class TrackSearchResponse(BaseModel):
    query: str
    results: list[TrackSearchResult]
    omitted_mix_fragments: int = 0  # fragmentos de DJ mixes (no son la canción en sí) que no se muestran
    source: Source


class TrackRelease(BaseModel):
    """Grupo de lanzamientos en el que aparece la grabación (álbum, single, recopilatorio…)."""
    mbid: str                     # release group
    title: str
    primary_type: str | None = None
    secondary_types: list[str] = []
    date: str | None = None       # primera fecha documentada entre sus ediciones
    labels: list[str] = []
    catalog_number: str | None = None
    formats: list[str] = []
    own: bool = True              # acreditado al artista de la canción (no un recopilatorio de varios)
    self_released: bool = False   # sin sellos y con «[no label]» explícito en MusicBrainz (no por falta de datos)
    cover_url: str | None = None
    url: str


class TrackCredit(BaseModel):
    role: str                     # «Producción», «Remezcla», «Composición»…
    artists: list[ArtistSummary]


class TrackLink(BaseModel):
    """Otra grabación relacionada documentada en MusicBrainz (remezcla, original, sample…)."""
    mbid: str
    title: str
    artist_name: str
    length_ms: int | None = None


class TrackRelations(BaseModel):
    remix_of: list[TrackLink] = []   # esta grabación es una remezcla o edit de…
    remixes: list[TrackLink] = []    # remezclas y edits de esta grabación
    remix_count: int = 0
    dj_mix_count: int = 0            # DJ mixes documentados que la incluyen (mínimo verificado, no un total)
    dj_mixes: list[str] = []         # algunos títulos de esos DJ mixes
    samples: list[TrackLink] = []    # V5.2: grabaciones de las que esta toma samples («samples material»)
    sampled_by: list[TrackLink] = [] # grabaciones que samplean esta
    mashups: list[TrackLink] = []    # mashups en los que aparece o que esta combina («mashes up»)
    cover_of: str | None = None      # título de la obra si MusicBrainz marca la interpretación como cover
    cover_writers: list[str] = []    # autores de esa obra (relación de la obra, no de esta grabación)


class DnaTrait(BaseModel):
    """Un rasgo del ADN con su procedencia. «measured» queda reservado para un futuro análisis acústico real;
    las interpretaciones de IA NUNCA son rasgos (van aparte, en TrackInterpretation)."""
    key: str                      # genre, artist_style, label, version, dj_mixes, remixes, bpm, key, energy…
    group: Literal["classification", "context", "acoustic"]
    label: str
    status: Literal["verified", "community", "measured", "unavailable"]
    scope: Literal["track", "release", "artist"] = "track"
    values: list[str] = []
    detail: str | None = None
    sources: list[SourceRef] = []


class TrackDna(BaseModel):
    recording_mbid: str
    traits: list[DnaTrait]
    acoustic_analysis: Literal["unavailable"] = "unavailable"  # sin fuente autorizada de audio en esta versión


class TrackArtist(BaseModel):
    mbid: str
    name: str
    styles: list[Style] = []      # Wikidata P136 del artista (contexto, no de la canción)


class ExternalId(BaseModel):
    """ID de otro proveedor leído de una URL que documenta MusicBrainz (nunca de una búsqueda por nombre)."""
    provider: str                 # spotify, deezer, apple_music, tidal, discogs, beatport, bandcamp
    kind: str                     # album, track, release, master…
    id: str                       # en Bandcamp, la URL canónica (no hay ID numérico público)
    url: str
    scope: Literal["recording", "release"]
    release_mbid: str | None = None  # edición de MusicBrainz que documenta el enlace (scope = release)


class TrackIdentifiers(BaseModel):
    """Claves para cruzar con otros proveedores en fases futuras: MBID, ISRC, barcode/UPC e IDs documentados."""
    recording_mbid: str
    isrcs: list[str] = []
    release_group_mbid: str | None = None
    release_mbid: str | None = None   # edición original elegida
    barcodes: list[str] = []          # de las ediciones propias (UPC/EAN), sin recopilatorios
    external: list[ExternalId] = []


class TrackInterpretation(BaseModel):
    text: str
    sources: list[SourceRef]
    generated_at: str


class TrackResponse(BaseModel):
    mbid: str                     # MBID canónico (MusicBrainz redirige los fusionados); en Discogs, «discogs:<release>:<pos>»
    catalog: Literal["musicbrainz", "discogs", "deezer"] = "musicbrainz"  # discogs y deezer: /v1/tracks/ext/{id}
    title: str
    artist_credit: list[CreditedArtist]
    artist_name: str
    main_artist: TrackArtist | None
    length_ms: int | None = None
    first_release_date: str | None = None
    disambiguation: str | None = None
    video: bool = False
    version: str | None = None
    isrcs: list[str] = []
    cover_url: str | None = None
    cover_release_mbid: str | None = None
    original_release: TrackRelease | None = None
    releases: list[TrackRelease] = []
    release_count: int = 0
    releases_status: SectionStatus
    credits: list[TrackCredit] = []
    relations: TrackRelations
    links: list[Link] = []
    identifiers: TrackIdentifiers | None = None
    dna: TrackDna
    interpretation: TrackInterpretation | None = None
    interpretation_status: Literal["ready", "pending", "insufficient_sources", "unavailable"] = "unavailable"
    # V6.1: la misma grabación en Deezer (ISRC y duración). Con ella hay extracto de 30 s en /tracks/{mbid}/preview.
    deezer_url: str | None = None
    sources: list[SourceRef]
    source: Source


class TrackPreviewResponse(BaseModel):
    """Extracto de 30 s de Deezer: URL firmada que caduca en minutos (se pide al pulsar «Escuchar», nunca se guarda)."""
    recording_mbid: str
    url: str | None = None
    deezer_url: str | None = None
    reason: str | None = None     # no_match | no_preview | disabled | unavailable


class TrackInterpretationResponse(BaseModel):
    recording_mbid: str
    status: Literal["ready", "insufficient_sources", "unavailable"]
    interpretation: TrackInterpretation | None = None


# --- Carteles (Fase 3.1): extracción de IA auditada, sin editar. El evento editable vive en el móvil. ---

class PosterDate(BaseModel):
    text: str
    iso: str | None = None  # solo con día, mes y año impresos en ese mismo texto


class PosterSession(BaseModel):
    date: PosterDate | None = None
    label: str | None = None
    stage: str | None = None
    time: str | None = None  # hora impresa del bloque: no es la hora de cada DJ
    artists: list[str]


class PosterArtistRow(BaseModel):
    name: str
    stage: str | None = None
    day: str | None = None


class PosterTime(BaseModel):
    name: str
    time: str


class PosterB2B(BaseModel):
    artists: list[str]
    text: str | None = None


class PosterReview(BaseModel):
    field: str
    value: str | None = None
    action: str  # descartado | reparado
    reason: str


class PosterUsage(BaseModel):
    input: int
    output: int


class PosterExtraction(BaseModel):
    mode: Literal["full", "continue", "region"]
    complete: bool  # False: la respuesta se cortó (finish_reason length) y solo se conserva lo completo
    model: str
    event_name: str | None = None
    dates: list[PosterDate] = []
    location: str | None = None
    stages: list[str] = []
    colors: list[str] = []
    sessions: list[PosterSession] = []
    artists: list[PosterArtistRow] = []
    individual_times: list[PosterTime] = []
    b2b: list[PosterB2B] = []
    uncertain: list[str] = []
    unreadable_text: list[str] = []
    review: list[PosterReview] = []
    usage: PosterUsage | None = None


class PosterAnalyzeRequest(BaseModel):
    image: str  # base64 (JPEG, PNG o WebP; el móvil convierte HEIC antes de enviar)
    mode: Literal["full", "continue", "region"] = "full"
    known_sessions: list[str] = []  # continuación: bloques ya leídos
    known_names: list[str] = []     # continuación: nombres ya leídos


# --- Carteles (Fase 3.4): identidad musical de los nombres del cartel. Sin catálogo propio: solo MBID. ---

class PosterResolveRequest(BaseModel):
    names: list[str]


class PosterCandidate(BaseModel):
    mbid: str
    name: str
    disambiguation: str | None = None
    type: str | None = None
    country: str | None = None
    score: int | None = None
    match: Literal["name", "alias", "similar"]  # similar = parecido (posible errata), nunca se enlaza solo
    alias: str | None = None     # alias de MusicBrainz que coincide con el nombre del cartel
    scene: bool = False          # su desambiguación lo sitúa en la escena electrónica (orienta, no decide)


class PosterResolution(BaseModel):
    name: str                    # tal como se envió (el nombre del cartel no se corrige)
    status: Literal["linked", "ambiguous", "none", "error"]
    mbid: str | None = None
    canonical: str | None = None
    candidates: list[PosterCandidate] = []
    evidence: str | None = None
    source: str | None = None


class PosterResolveResponse(BaseModel):
    results: list[PosterResolution]


class PosterTrack(BaseModel):
    recording_mbid: str
    title: str
    artist_credit: str
    first_release_date: str | None = None


class PosterTracksResponse(BaseModel):
    """Canciones propias documentadas en MusicBrainz, por fecha (no es un ranking): alternativa a `top_tracks`."""
    artist_mbid: str
    tracks: list[PosterTrack]
    source: Source
