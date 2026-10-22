/**
 * Carteles (Fase 3.1–3.3). `PosterExtraction` es la propuesta de la IA tal como la devuelve el backend (no se edita);
 * `PosterEvent` es el evento del usuario, editable y guardado solo en este dispositivo. Ausente = null, nunca texto.
 */

export type PosterDate = { text: string; iso: string | null };

export type PosterExtraction = {
  mode: 'full' | 'continue' | 'region';
  complete: boolean;
  model: string;
  event_name: string | null;
  dates: PosterDate[];
  location: string | null;
  stages: string[];
  colors: string[];
  sessions: { date: PosterDate | null; label: string | null; stage: string | null; time: string | null; artists: string[] }[];
  artists: { name: string; stage: string | null; day: string | null }[];
  individual_times: { name: string; time: string }[];
  b2b: { artists: string[]; text: string | null }[];
  uncertain: string[];
  unreadable_text: string[];
  review: { field: string; value: string | null; action: string; reason: string }[];
  usage: { input: number; output: number } | null;
};

export type Origin = 'ai' | 'user';

/** Avisos guardados con el dato (los de la extracción). Los demás se calculan al vuelo: ver lib/poster-model. */
export type Flag =
  | 'similar_name' | 'odd_spelling' | 'possible_brand' | 'collective' | 'possible_merge'
  | 'model_uncertain' | 'block_time' | 'year_not_printed' | 'incomplete' | 'suspicious_name';

/** `locked`: campos editados o confirmados a mano; un reanálisis nunca los cambia. */
export type Meta = { origin: Origin; flags: Flag[]; locked: string[]; printed: string | null };

export type PosterDay = { id: string; label: string; date: string | null; order: number; meta: Meta };
export type PosterStage = { id: string; name: string; meta: Meta };

export type PosterArtist = {
  id: string;
  name: string;
  meta: Meta;
  /** Identidad musical (3.4). Los campos opcionales no existían en 3.3: los eventos guardados siguen siendo válidos. */
  link: ArtistLink;
};

/** Candidato de MusicBrainz para un nombre del cartel. `similar` = nombre parecido (posible errata): nunca se enlaza solo. */
export type LinkCandidate = {
  refId: string;
  name: string;
  disambiguation: string | null;
  country?: string | null;
  type?: string | null;
  match?: 'name' | 'alias' | 'similar' | 'manual';
  scene?: boolean;
};

/**
 * `origin: 'user'`: el usuario eligió la identidad o la dejó sin identificar; la resolución automática ya no la toca.
 * `query`: nombre normalizado con el que se resolvió (si el nombre cambia, el enlace automático deja de valer).
 */
export type ArtistLink = {
  status: 'pending' | 'linked' | 'ambiguous' | 'none';
  catalog: 'musicbrainz' | 'discogs' | null;
  refId: string | null;
  name?: string | null;
  candidates?: LinkCandidate[];
  evidence?: string | null;
  origin?: Origin;
  query?: string | null;
};

/** Actuación: 1 artista = individual; 2 o más = B2B (una sola actuación). */
export type PosterSet = {
  id: string;
  artistIds: string[];
  connector: string | null;
  dayId: string | null;
  stageId: string | null;
  block: string | null;
  start: string | null;
  end: string | null;
  /** 'block' = hora impresa del bloque, no la de cada DJ. */
  timeScope: 'set' | 'block' | null;
  endsNextDay: boolean;
  order: number;
  meta: Meta;
};

/** Dato nuevo de un reanálisis que contradice lo existente: nunca se aplica solo. */
export type PosterSuggestion = {
  id: string;
  target: 'event' | 'set';
  targetId: string | null;
  field: string;
  value: string;
  label: string;
};

export type PosterImage = { width: number; height: number; bytes: number };

export type PosterEvent = {
  schema: 1;
  id: string;
  fingerprint: string | null;
  assetId: string | null;
  status: 'draft' | 'partial' | 'confirmed';
  name: string | null;
  dateText: string | null;
  location: string | null;
  meta: Meta;
  image: PosterImage;
  days: PosterDay[];
  stages: PosterStage[];
  artists: PosterArtist[];
  sets: PosterSet[];
  palette: { source: 'poster' | 'fallback'; seeds: string[] };
  /** Nombres normalizados que el usuario eliminó: un reanálisis no los vuelve a añadir. */
  discarded: string[];
  suggestions: PosterSuggestion[];
  analysis: { model: string; calls: number; incomplete: boolean; lastError: string | null; review: string[]; at: string };
  createdAt: string;
  updatedAt: string;
};

/** Entrada ligera del índice de la biblioteca (lo que pinta la lista sin leer cada evento). */
export type PosterIndexEntry = {
  id: string;
  name: string | null;
  dateText: string | null;
  status: PosterEvent['status'];
  artists: number;
  fingerprint: string | null;
  assetId: string | null;
  seeds: string[];
  updatedAt: string;
};
