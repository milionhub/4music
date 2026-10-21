/**
 * Lógica pura del estado local (sin React ni almacenamiento), probada con `node --test` (mobile/tests).
 * Lectura tolerante: datos ausentes, corruptos o de otra versión → valores vacíos, nunca una excepción.
 */
import type { ArtistRef, CreditedArtist, TrackResponse } from '@/types/music';

export type OnboardingState = 'pending' | 'completed' | 'skipped';

export type Preferences = {
  version: 1;
  onboarding: OnboardingState;
  /** Estilos declarados por el usuario (lista editorial propia). No son datos de MusicBrainz. */
  declared_styles: string[];
  updated_at: string;
};

/** Artistas de partida de Inicio (T1). Desde v5 ya no se muestran en Guardados, pero se conservan intactos. */
export type Favorite = ArtistRef & { kind: 'artist'; saved_at: string };
export type Discarded = { kind: 'artist'; mbid: string; discarded_at: string };

export const EMPTY_PREFERENCES: Preferences = {
  version: 1,
  onboarding: 'pending',
  declared_styles: [],
  updated_at: new Date(0).toISOString(),
};

const ONBOARDING_STATES: OnboardingState[] = ['pending', 'completed', 'skipped'];
const isString = (v: unknown): v is string => typeof v === 'string';

function parseJson(raw: string | null): unknown {
  if (!raw) return null;
  try {
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

export function parsePreferences(raw: string | null): Preferences {
  const v = parseJson(raw) as Partial<Preferences> | null;
  if (!v || typeof v !== 'object' || v.version !== 1 || !ONBOARDING_STATES.includes(v.onboarding as OnboardingState)) {
    return EMPTY_PREFERENCES;
  }
  return {
    version: 1,
    onboarding: v.onboarding as OnboardingState,
    declared_styles: Array.isArray(v.declared_styles) ? [...new Set(v.declared_styles.filter(isString))] : [],
    updated_at: isString(v.updated_at) ? v.updated_at : EMPTY_PREFERENCES.updated_at,
  };
}

function parseList<T extends { mbid: string }>(raw: string | null, isValid: (item: Record<string, unknown>) => boolean): T[] {
  const v = parseJson(raw) as { version?: unknown; items?: unknown } | null;
  if (!v || typeof v !== 'object' || v.version !== 1 || !Array.isArray(v.items)) return [];
  const seen = new Set<string>();
  const out: T[] = [];
  for (const item of v.items) {
    if (item && typeof item === 'object' && isValid(item as Record<string, unknown>) && !seen.has((item as T).mbid)) {
      seen.add((item as T).mbid);
      out.push(item as T);
    }
  }
  return out;
}

export function parseFavorites(raw: string | null): Favorite[] {
  return parseList<Favorite>(
    raw,
    (i) => i.kind === 'artist' && isString(i.mbid) && isString(i.name) && isString(i.saved_at) &&
      (i.disambiguation === null || i.disambiguation === undefined || isString(i.disambiguation)),
  ).map((f) => ({ ...f, disambiguation: f.disambiguation ?? null }));
}

export function parseDiscarded(raw: string | null): Discarded[] {
  return parseList<Discarded>(raw, (i) => i.kind === 'artist' && isString(i.mbid) && isString(i.discarded_at));
}

export const serializePreferences = (p: Preferences) => JSON.stringify(p);
export const serializeList = <T>(items: T[]) => JSON.stringify({ version: 1, items });

/** Fin de la bienvenida en UNA sola actualización: estilos y estado juntos, sin tocar favoritos. */
export function finishOnboarding(prefs: Preferences, state: 'completed' | 'skipped', styles: string[], now: string): Preferences {
  return {
    ...prefs,
    // Si ya estaba terminada (edición desde Perfil), no se degrada a «omitida».
    onboarding: prefs.onboarding === 'pending' ? state : prefs.onboarding,
    declared_styles: [...new Set(styles)],
    updated_at: now,
  };
}

export const shouldShowOnboarding = (prefs: Preferences) => prefs.onboarding === 'pending';

export function toggleFavorite(list: Favorite[], artist: ArtistRef, now: string): Favorite[] {
  if (list.some((f) => f.mbid === artist.mbid)) return list.filter((f) => f.mbid !== artist.mbid);
  return [{ kind: 'artist', mbid: artist.mbid, name: artist.name, disambiguation: artist.disambiguation ?? null, saved_at: now }, ...list];
}

// --- Guardados v5: biblioteca de canciones ------------------------------------------------------------------------

/**
 * Canción guardada desde TrackDNA. Se identifica por el MBID de la grabación (el canónico que devuelve la ficha);
 * el resto es lo mínimo para listarla sin conexión y reabrir su ficha. Título y portada son solo presentación.
 */
export type SavedTrack = {
  kind: 'track';
  mbid: string;
  title: string;
  artists: CreditedArtist[];
  artist_name: string;
  /** «Remix de X», «Extended Mix»…: distingue versiones de la misma canción. */
  version: string | null;
  cover_url: string | null;
  length_ms: number | null;
  year: string | null;
  label: string | null;
  isrcs: string[];
  saved_at: string;
};

const isNullableString = (v: unknown) => v === null || v === undefined || isString(v);

export function parseSavedTracks(raw: string | null): SavedTrack[] {
  return parseList<SavedTrack>(
    raw,
    (i) => i.kind === 'track' && isString(i.mbid) && isString(i.title) && isString(i.saved_at) && isNullableString(i.version),
  ).map((t) => ({
    kind: 'track',
    mbid: t.mbid,
    title: t.title,
    artists: Array.isArray(t.artists)
      ? t.artists.filter((a) => a && isString(a.mbid) && isString(a.name)).map((a) => ({ mbid: a.mbid, name: a.name, join_phrase: isString(a.join_phrase) ? a.join_phrase : '' }))
      : [],
    artist_name: isString(t.artist_name) ? t.artist_name : '',
    version: t.version ?? null,
    cover_url: isString(t.cover_url) ? t.cover_url : null,
    length_ms: typeof t.length_ms === 'number' ? t.length_ms : null,
    year: isString(t.year) ? t.year : null,
    label: isString(t.label) ? t.label : null,
    isrcs: Array.isArray(t.isrcs) ? t.isrcs.filter(isString) : [],
    saved_at: t.saved_at,
  }));
}

/**
 * Misma canción: mismo MBID de grabación o, si MusicBrainz la tiene duplicada, un ISRC común con la misma versión.
 * Un remix o un edit nunca coincide con el original (otra versión, otra grabación).
 */
export function sameTrack(a: Pick<SavedTrack, 'mbid' | 'isrcs' | 'version'>, b: Pick<SavedTrack, 'mbid' | 'isrcs' | 'version'>): boolean {
  if (a.mbid === b.mbid) return true;
  return (a.version ?? '') === (b.version ?? '') && a.isrcs.some((i) => b.isrcs.includes(i));
}

export function toggleSavedTrack(list: SavedTrack[], track: SavedTrack): SavedTrack[] {
  if (list.some((t) => sameTrack(t, track))) return list.filter((t) => !sameTrack(t, track));
  return [track, ...list];
}

/** Lo que se guarda de una ficha TrackDNA (sin datos inventados: lo que falta queda en null). */
export function savedTrackFrom(t: TrackResponse, now: string): SavedTrack {
  const label = t.dna.traits.find((x) => x.key === 'label' && x.status !== 'unavailable')?.values[0]
    ?? t.original_release?.labels[0] ?? null;
  return {
    kind: 'track',
    mbid: t.mbid,
    title: t.title,
    artists: t.artist_credit.map((a) => ({ mbid: a.mbid, name: a.name, join_phrase: a.join_phrase })),
    artist_name: t.artist_name,
    version: t.version,
    cover_url: t.cover_url,
    length_ms: t.length_ms,
    year: t.first_release_date?.slice(0, 4) || null,
    label,
    isrcs: t.isrcs,
    saved_at: now,
  };
}
