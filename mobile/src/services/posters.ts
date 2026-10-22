/** Carteles: análisis en el backend (Groq solo allí). Una petición = una llamada a la IA; aquí no hay reintentos. */
import { type ApiError, type ApiResult, getJson, postJson } from '@/services/api-client';
import type { Resolution } from '@/lib/poster-identity';
import type { PosterExtraction } from '@/types/poster';

const ANALYZE_TIMEOUT_MS = 75_000;
// Resolución: hasta RESOLVE_BATCH nombres en serie a 1 petición/1,1 s en MusicBrainz (con un reintento posible).
const RESOLVE_TIMEOUT_MS = 30_000;
const TRACKS_TIMEOUT_MS = 20_000;

export type PosterTrack = { recording_mbid: string; title: string; artist_credit: string; first_release_date: string | null };

export function resolveArtists(names: string[]): Promise<ApiResult<{ results: Resolution[] }>> {
  return postJson<{ results: Resolution[] }>('/v1/posters/resolve', { names }, RESOLVE_TIMEOUT_MS);
}

/** Canciones propias documentadas en MusicBrainz por fecha (alternativa a `top_tracks` sin ListenBrainz). */
export function getPosterArtistTracks(mbid: string): Promise<ApiResult<{ artist_mbid: string; tracks: PosterTrack[] }>> {
  return getJson(`/v1/posters/artists/${encodeURIComponent(mbid)}/tracks`, TRACKS_TIMEOUT_MS);
}

export type AnalyzeBody = {
  image: string;
  mode: PosterExtraction['mode'];
  known_sessions?: string[];
  known_names?: string[];
};

export function analyzePoster(body: AnalyzeBody): Promise<ApiResult<PosterExtraction>> {
  return postJson<PosterExtraction>('/v1/posters/analyze', body, ANALYZE_TIMEOUT_MS);
}

export function describePosterError(error: ApiError): string {
  switch (error.code) {
    case 'poster_ai_not_configured':
      return 'El servidor no tiene configurada la IA de carteles (GROQ_API_KEY).';
    case 'poster_ai_rate_limited':
      return 'La IA ha alcanzado su límite por minuto. Espera un poco y vuelve a intentarlo.';
    case 'poster_daily_limit':
      return 'Has alcanzado el límite de análisis de hoy. Puedes seguir corrigiendo el cartel a mano.';
    case 'poster_ai_unavailable':
      return 'La IA no responde ahora mismo. Inténtalo de nuevo más tarde.';
    case 'poster_ai_bad_response':
      return 'La IA devolvió una respuesta que no se pudo leer.';
    case 'image_too_large':
      return 'La imagen es demasiado grande. Prueba con otra o recórtala.';
    case 'unsupported_image':
    case 'invalid_image':
      return 'Formato de imagen no admitido.';
  }
  if (error.kind === 'timeout') return 'La IA tardó demasiado en responder. Puedes volver a intentarlo.';
  if (error.kind === 'network') return 'No hay conexión con el servidor de Chromatic Underground.';
  return error.message;
}
