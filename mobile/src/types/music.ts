/** Contrato /v1 del backend (docs/t0-contrato-datos.md). null = la fuente no tiene el dato. */

export type Source = {
  provider: 'musicbrainz' | 'discogs';
  url: string;
  fetched_at: string;
  license: string;
  stale: boolean;
};

export type ArtistSummary = {
  mbid: string;
  name: string;
  sort_name: string | null;
  disambiguation: string | null;
  type: string | null;
  country: string | null;
  area: string | null;
  begin_date: string | null;
};

export type Link = {
  url: string;
  label: string;
  /** Plataforma musical reconocida por dominio (Spotify, Beatport…); null en el resto. */
  platform: string | null;
  kinds: string[];
  detail: string | null;
  primary: boolean;
  /** TrackDNA: enlace de la propia grabación o de un lanzamiento suyo (en artistas, null). */
  scope?: 'recording' | 'release' | null;
  /** TrackDNA: abre la propia pista o el lanzamiento que la contiene (en artistas, null). */
  target?: 'track' | 'release' | null;
  /** Tipo principal del lanzamiento de MusicBrainz (Album, EP, Single) cuando target = release. */
  release_type?: string | null;
  /** TrackDNA: formatos de la edición de la que sale el enlace («12" Vinyl», «Digital Media»). */
  formats?: string[];
};

export type Artist = ArtistSummary & {
  aliases: string[];
  links: Link[];
  source: Source;
};

export type SearchResult = {
  mbid: string;
  name: string;
  disambiguation: string | null;
  type: string | null;
  country: string | null;
  area: string | null;
  score: number | null;
};

export type SearchResponse = { query: string; results: SearchResult[]; source: Source };

export type Recording = {
  mbid: string;
  title: string;
  artist_credit: { mbid: string; name: string; join_phrase: string }[];
  length_ms: number | null;
  first_release_date: string | null;
  disambiguation: string | null;
};

export type SectionStatus = {
  status: 'ok' | 'empty' | 'error';
  error_code: string | null;
  total: number | null;
  skipped: number;
  source: Source | null;
};

export type SourceRef = { label: string; url: string; license: string | null };

/** Texto literal de una fuente con licencia, en su idioma original. */
export type Excerpt = { text: string; language: string; source: SourceRef };

/** editorial: texto original del catálogo con fuentes; factual: frase con datos verificados (Wikidata + MusicBrainz). */
export type Bio = {
  kind: 'editorial' | 'generated' | 'factual';
  text: string;
  language: string;
  sources: SourceRef[];
  reviewed: boolean | null;
  /** factual: descripción breve traducida (p. ej. 'en'), sin añadir información. */
  translated_from?: string | null;
  /** generated: biografía válida de una versión anterior del validador (no se usan sus frases como verificadas). */
  legacy?: boolean;
};

/** Género con su fuente: Wikidata (P136), descripción de MusicBrainz o presentación de Wikipedia. */
export type Style = { label: string; qid: string | null; source: 'wikidata' | 'musicbrainz' | 'wikipedia' };

export type TopTrack = {
  recording_mbid: string;
  title: string;
  artist_name: string;
  listen_count: number;
  user_count: number | null;
  release_name: string | null;
  cover_url: string | null;
  /** Para abrir una búsqueda en una plataforma: nunca es un enlace exacto a la canción. */
  search_query: string;
};

export type RecentRelease = {
  mbid: string;
  title: string;
  primary_type: string | null;
  secondary_types: string[];
  first_release_date: string;
  with_artists: string[];
  cover_url: string | null;
  url: string;
};

export type Highlight = {
  artist: ArtistSummary;
  kind: 'joint_release' | 'featuring' | 'co_credit' | 'relation';
  reason: string;
  evidence_count: number;
};

/** Foto verificada por MBID: catálogo editorial con permiso o Wikimedia Commons con licencia libre. */
export type ArtistImage = {
  url: string;
  width: number | null;
  height: number | null;
  page_url: string;
  author: string | null;
  license: string;
  license_url: string | null;
  source: 'wikimedia_commons' | 'editorial';
  via: string | null;
  wikidata_id: string | null;
};

export type ArtistImageResponse = { mbid: string; image: ArtistImage | null; reason: string | null };

export type BiographyResponse = { artist_mbid: string; status: 'ready' | 'unavailable'; bio: Bio | null };
/** Historia de «Más allá de la cabina»: breve, en español, con las fuentes de los hechos que cita. */
export type Story = { key: 'inicios' | 'universo' | 'momento'; title: string; text: string; sources: SourceRef[] };
/** generated: redactadas y validadas contra los hechos citados; structured: plantillas con datos verificados. */
export type StoriesResponse = {
  artist_mbid: string;
  status: 'ready' | 'unavailable';
  mode: 'generated' | 'structured' | 'mixed' | null;
  stories: Story[];
  generated_at: string | null;
};

/** Identidad documentada (MusicBrainz + Wikidata). `area`: área asociada (no residencia); `origin`: begin-area. */
export type ArtistIdentity = {
  country_name: string | null;
  area: string | null;
  origin: string | null;
  origin_kind: 'birth' | 'formation' | null;
  formed_year: string | null;
  active_since: string | null;
  /** Relaciones explícitas de MusicBrainz: «label founder» y «member of band» (publicar en un sello no basta). */
  founded_labels?: string[];
  /** Sellos que dirige o posee según las notas de Discogs (no consta que los fundara). */
  run_labels?: string[];
  /** Año de fundación o inicio de un sello, solo si consta. */
  label_years?: Record<string, string>;
  projects?: string[];
  members?: string[];
};

/** Perfil modular: cada módulo puede venir vacío sin bloquear los demás. */
export type ArtistProfileResponse = {
  artist: Artist;
  identity?: ArtistIdentity;
  image: ArtistImage | null;
  image_reason: string | null;
  styles: Style[];
  bio: Bio | null;
  /** Se puede pedir /biography para obtener (o generar) una biografía editorial mejor. */
  bio_pending: boolean;
  /** Introducción literal de Wikipedia del ítem verificado por MBID, con su atribución (vista rápida de Carteles). */
  summary?: Excerpt | null;
  top_tracks: TopTrack[];
  top_tracks_status: SectionStatus;
  recent_releases: RecentRelease[];
  releases_status: SectionStatus;
  /** Lanzamiento propio más antiguo, solo con la discografía completa. */
  first_release?: RecentRelease | null;
  highlights: Highlight[];
  highlights_title: 'collaborations' | 'connections' | null;
  recordings_status: SectionStatus;
  platforms: Link[];
  sources: SourceRef[];
};

export type RecommendationReason = {
  kind: 'affinity' | 'shared_label' | 'collaboration';
  seed_mbid: string;
  seed_name: string;
  strength: number;
  detail: string | null;
  text: string;
};

/** Recomendación del motor T1.3: puntuación técnica, etiqueta según la evidencia y explicación breve. */
export type Recommendation = {
  artist: ArtistSummary;
  score: number;
  kind: 'affinity' | 'shared_label' | 'collaboration' | 'multiple_favorites';
  tag: string;
  headline: string;
  reasons: RecommendationReason[];
};

export type DiscoveryResponse = {
  cards: Recommendation[];
  seeds_without_results: string[];
  seeds_failed: string[];
  sources: SourceRef[];
};

/** Lo mínimo que se guarda en el dispositivo para reconocer a un artista sin conexión. */
export type ArtistRef = { mbid: string; name: string; disambiguation: string | null };

// --- TrackDNA de canciones (T2.0) ---------------------------------------------------------------------------------
export type CreditedArtist = { mbid: string; name: string; join_phrase: string };

/** V5.6: «discogs» solo si MusicBrainz no encuentra la canción; su id es `discogs:<release>:<posición>` (no un MBID). */
export type TrackCatalog = 'musicbrainz' | 'discogs';

export type TrackSearchResult = {
  mbid: string;
  catalog?: TrackCatalog;
  title: string;
  artist_credit: CreditedArtist[];
  artist_name: string;
  /** Desambiguación del artista principal en MusicBrainz: distingue homónimos. */
  artist_disambiguation: string | null;
  length_ms: number | null;
  first_release_date: string | null;
  disambiguation: string | null;
  /** «Remix de X», «Directo», «Vídeo»… solo si el título o MusicBrainz lo indican. */
  version: string | null;
  release_title: string | null;
  release_type: string | null;
  cover_url: string | null;
  merged_count: number;
  release_count: number;
};

export type TrackSearchResponse = { query: string; results: TrackSearchResult[]; omitted_mix_fragments: number; source: Source };

export type TrackRelease = {
  mbid: string;
  title: string;
  primary_type: string | null;
  secondary_types: string[];
  date: string | null;
  labels: string[];
  catalog_number: string | null;
  formats: string[];
  own: boolean;
  /** Sin sellos y con «[no label]» explícito en MusicBrainz: autoedición documentada (no una falta de datos). */
  self_released: boolean;
  cover_url: string | null;
  url: string;
};

/** Identificadores para cruces futuros: MBID, ISRC, barcode e IDs leídos de URL documentadas (nunca por nombre). */
export type TrackIdentifiers = {
  recording_mbid: string;
  isrcs: string[];
  release_group_mbid: string | null;
  release_mbid: string | null;
  barcodes: string[];
  external: { provider: string; kind: string; id: string; url: string; scope: 'recording' | 'release'; release_mbid: string | null }[];
};

export type TrackLink = { mbid: string; title: string; artist_name: string; length_ms: number | null };

export type TrackRelations = {
  remix_of: TrackLink[];
  remixes: TrackLink[];
  remix_count: number;
  dj_mix_count: number;
  dj_mixes: string[];
  /** V5.2: relaciones documentadas en MusicBrainz (opcionales: fichas en caché anteriores no las traen). */
  samples?: TrackLink[];
  sampled_by?: TrackLink[];
  mashups?: TrackLink[];
  /** Título de la obra cuando MusicBrainz marca esta interpretación como cover, y sus autores. */
  cover_of?: string | null;
  cover_writers?: string[];
};

/**
 * Procedencia de un rasgo del ADN. `measured` queda reservado para un análisis acústico real futuro;
 * la IA nunca produce rasgos (su texto va en `TrackInterpretation`).
 */
export type DnaStatus = 'verified' | 'community' | 'measured' | 'unavailable';

export type DnaTrait = {
  key: string;
  group: 'classification' | 'context' | 'acoustic';
  label: string;
  status: DnaStatus;
  scope: 'track' | 'release' | 'artist';
  values: string[];
  detail: string | null;
  sources: SourceRef[];
};

export type TrackDna = { recording_mbid: string; traits: DnaTrait[]; acoustic_analysis: 'unavailable' };

export type TrackInterpretation = { text: string; sources: SourceRef[]; generated_at: string };

export type TrackResponse = {
  mbid: string;
  catalog?: TrackCatalog;
  title: string;
  artist_credit: CreditedArtist[];
  artist_name: string;
  main_artist: { mbid: string; name: string; styles: Style[] } | null;
  length_ms: number | null;
  first_release_date: string | null;
  disambiguation: string | null;
  video: boolean;
  version: string | null;
  isrcs: string[];
  cover_url: string | null;
  cover_release_mbid: string | null;
  original_release: TrackRelease | null;
  releases: TrackRelease[];
  release_count: number;
  releases_status: SectionStatus;
  credits: { role: string; artists: ArtistSummary[] }[];
  relations: TrackRelations;
  links: Link[];
  identifiers: TrackIdentifiers | null;
  dna: TrackDna;
  interpretation: TrackInterpretation | null;
  interpretation_status: 'ready' | 'pending' | 'insufficient_sources' | 'unavailable';
  sources: SourceRef[];
  source: Source;
};

export type TrackInterpretationResponse = {
  recording_mbid: string;
  status: 'ready' | 'insufficient_sources' | 'unavailable';
  interpretation: TrackInterpretation | null;
};
