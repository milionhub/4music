import { externalTrack } from '@/lib/format';
import { getJson } from '@/services/api-client';
import type {
  ArtistProfileResponse,
  BiographyResponse,
  DiscoveryResponse,
  EssentialsResponse,
  SearchResponse,
  StoriesResponse,
  TrackInterpretationResponse,
  TrackPreviewResponse,
  TrackResponse,
  TrackSearchResponse,
} from '@/types/music';

/** Límite de semillas que acepta GET /v1/discovery. */
export const MAX_SEEDS = 5;

// Las consultas en frío esperan a MusicBrainz (1 petición cada 1,1 s en el backend).
const SEARCH_TIMEOUT_MS = 15000;
const ARTIST_TIMEOUT_MS = 30000;
const DISCOVERY_TIMEOUT_MS = 45000;
// La biografía puede generarse en el momento (fuentes + modelo): la ficha no la espera para mostrarse.
const BIOGRAPHY_TIMEOUT_MS = 45000;

export function searchArtists(query: string) {
  return getJson<SearchResponse>(`/v1/artists/search?q=${encodeURIComponent(query)}&limit=10`, SEARCH_TIMEOUT_MS);
}

export function getArtist(mbid: string) {
  return getJson<ArtistProfileResponse>(`/v1/artists/${encodeURIComponent(mbid)}`, ARTIST_TIMEOUT_MS);
}

export function getDiscovery(seeds: string[]) {
  return getJson<DiscoveryResponse>(
    `/v1/discovery?seeds=${seeds.map(encodeURIComponent).join(',')}&limit=40`,
    DISCOVERY_TIMEOUT_MS,
  );
}

// «Más allá de la cabina»: la investigación (fuentes + redacción validada) puede tardar; la ficha no la espera.
const STORIES_TIMEOUT_MS = 60000;

export function getStories(mbid: string) {
  return getJson<StoriesResponse>(`/v1/artists/${encodeURIComponent(mbid)}/stories`, STORIES_TIMEOUT_MS);
}

export function getEssentials(mbid: string) {
  return getJson<EssentialsResponse>(`/v1/artists/${encodeURIComponent(mbid)}/essentials`, STORIES_TIMEOUT_MS);
}

export function getBiography(mbid: string) {
  return getJson<BiographyResponse>(`/v1/artists/${encodeURIComponent(mbid)}/biography`, BIOGRAPHY_TIMEOUT_MS);
}

// --- TrackDNA de canciones (T2.0) ---
// La ficha en frío consulta MusicBrainz (3 peticiones a 1/s) y Wikidata; la interpretación puede generarse al momento.
const TRACK_SEARCH_TIMEOUT_MS = 20000;
const TRACK_TIMEOUT_MS = 35000;
const INTERPRETATION_TIMEOUT_MS = 45000;

export function searchTracks(query: string) {
  return getJson<TrackSearchResponse>(`/v1/tracks/search?q=${encodeURIComponent(query)}&limit=15`, TRACK_SEARCH_TIMEOUT_MS);
}

export function getTrack(mbid: string) {
  // Canciones de Discogs (V5.6): ruta aparte, mismo contrato. /v1/tracks/{mbid} solo acepta MBID.
  const path = externalTrack(mbid) ? `/v1/tracks/ext/${encodeURIComponent(mbid)}` : `/v1/tracks/${encodeURIComponent(mbid)}`;
  return getJson<TrackResponse>(path, TRACK_TIMEOUT_MS);
}

export function getTrackPreview(mbid: string) {
  const base = externalTrack(mbid) ? '/v1/tracks/ext' : '/v1/tracks';
  return getJson<TrackPreviewResponse>(`${base}/${encodeURIComponent(mbid)}/preview`, TRACK_TIMEOUT_MS);
}

export function getTrackInterpretation(mbid: string) {
  return getJson<TrackInterpretationResponse>(`/v1/tracks/${encodeURIComponent(mbid)}/interpretation`, INTERPRETATION_TIMEOUT_MS);
}
