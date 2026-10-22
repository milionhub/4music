/**
 * Carteles 3.3: lectura tolerante, índice y duplicados de la biblioteca local. Lógica pura; la E/S está en
 * storage/poster-library.ts. Un evento ilegible se ignora (nunca rompe la biblioteca ni toca Guardados).
 */
import { parseLink } from './poster-identity.ts';
import type { PosterArtist, PosterEvent, PosterIndexEntry } from '../types/poster.ts';

export const POSTER_INDEX_KEY = 'md.posters.index.v1';
export const posterKey = (id: string) => `md.poster.${id}.v1`;
export const POSTER_KEY_RE = /^md\.poster\.([A-Za-z0-9_-]+)\.v1$/;

const isObj = (v: unknown): v is Record<string, unknown> => typeof v === 'object' && v !== null && !Array.isArray(v);
const arr = <T>(v: unknown): T[] => (Array.isArray(v) ? (v as T[]) : []);
const str = (v: unknown): string | null => (typeof v === 'string' && v ? v : null);

/** Evento guardado → objeto completo (rellena colecciones que falten). null si no es un evento de este esquema. */
export function parsePosterEvent(raw: string | null): PosterEvent | null {
  if (!raw) return null;
  let v: unknown;
  try {
    v = JSON.parse(raw);
  } catch {
    return null;
  }
  if (!isObj(v) || v.schema !== 1 || !str(v.id) || !isObj(v.image) || !isObj(v.meta) || !isObj(v.analysis)) return null;
  const status = v.status === 'confirmed' || v.status === 'partial' ? v.status : 'draft';
  return {
    ...(v as unknown as PosterEvent),
    status,
    days: arr(v.days), stages: arr(v.stages), sets: arr(v.sets),
    // 3.4: el enlace de identidad se lee con tolerancia (los eventos de 3.3 solo tienen `pending`).
    artists: arr<PosterArtist>(v.artists).filter(isObj).map((a) => ({ ...a, link: parseLink(a.link) })),
    discarded: arr(v.discarded), suggestions: arr(v.suggestions),
    palette: isObj(v.palette) ? (v.palette as PosterEvent['palette']) : { source: 'fallback', seeds: [] },
  };
}

export const serializePosterEvent = (e: PosterEvent) => JSON.stringify(e);

export function indexEntry(e: PosterEvent): PosterIndexEntry {
  return {
    id: e.id, name: e.name, dateText: e.dateText, status: e.status, artists: e.artists.length,
    fingerprint: e.fingerprint, assetId: e.assetId, seeds: e.palette.seeds, updatedAt: e.updatedAt,
  };
}

export function parseIndex(raw: string | null): PosterIndexEntry[] {
  if (!raw) return [];
  try {
    return arr<PosterIndexEntry>(JSON.parse(raw)).filter((x) => isObj(x) && !!str(x.id));
  } catch {
    return [];
  }
}

/** Índice sin duplicados, el más reciente primero. */
export function upsertIndex(index: PosterIndexEntry[], entry: PosterIndexEntry): PosterIndexEntry[] {
  return [entry, ...index.filter((x) => x.id !== entry.id)].sort((a, b) => b.updatedAt.localeCompare(a.updatedAt));
}

export const removeFromIndex = (index: PosterIndexEntry[], id: string) => index.filter((x) => x.id !== id);

/** Mismo cartel: misma huella del archivo o, si no hay huella, mismo recurso de la galería. */
export function findDuplicate(index: PosterIndexEntry[], fingerprint: string | null, assetId: string | null): PosterIndexEntry | null {
  return index.find((x) => (fingerprint && x.fingerprint === fingerprint) || (assetId && x.assetId === assetId)) ?? null;
}

/** Ids con evento guardado según las claves del almacenamiento (para reconstruir el índice y limpiar huérfanos). */
export function idsFromKeys(keys: string[]): string[] {
  return keys.map((k) => POSTER_KEY_RE.exec(k)?.[1]).filter((x): x is string => !!x);
}

/** Id local: tiempo + aleatorio, apto para nombres de carpeta. */
export function newPosterId(now = Date.now(), rand = Math.random): string {
  return `p${now.toString(36)}${Math.floor(rand() * 36 ** 4).toString(36).padStart(4, '0')}`;
}
