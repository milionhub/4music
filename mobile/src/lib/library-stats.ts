/**
 * Guardados y Perfil (V6.7): lo que dice tu biblioteca, calculado solo con lo guardado en este dispositivo. Sin datos
 * inventados: cada cifra sale de las canciones guardadas (lo que no consta, no cuenta).
 */
import type { SavedTrack } from './preferences.ts';

export type SortMode = 'recent' | 'az' | 'year';
export const SORT_LABELS: Record<SortMode, string> = { recent: 'Recientes', az: 'A–Z', year: 'Año' };

export type Ranked = { name: string; count: number };
export type LibraryStats = {
  count: number;
  /** Suma de duraciones conocidas; `timed` = cuántas canciones la tienen. */
  totalMs: number;
  timed: number;
  years: { from: string; to: string } | null;
  /** Solo lo que se repite (dos o más canciones): una sola no es «tu sonido». */
  labels: Ranked[];
  artists: Ranked[];
};

function ranked(values: (string | null | undefined)[], limit = 3): Ranked[] {
  const counts = new Map<string, Ranked>();
  for (const v of values) {
    const name = v?.trim();
    if (!name) continue;
    const key = name.toLocaleLowerCase('es');
    const hit = counts.get(key);
    if (hit) hit.count += 1;
    else counts.set(key, { name, count: 1 });
  }
  return [...counts.values()].filter((r) => r.count >= 2)
    .sort((a, b) => b.count - a.count || a.name.localeCompare(b.name, 'es')).slice(0, limit);
}

export function libraryStats(tracks: SavedTrack[]): LibraryStats {
  const timed = tracks.filter((t) => typeof t.length_ms === 'number' && t.length_ms > 0);
  const years = tracks.map((t) => t.year?.slice(0, 4)).filter((y): y is string => !!y && /^\d{4}$/.test(y)).sort();
  return {
    count: tracks.length,
    totalMs: timed.reduce((n, t) => n + (t.length_ms ?? 0), 0),
    timed: timed.length,
    years: years.length ? { from: years[0], to: years[years.length - 1] } : null,
    labels: ranked(tracks.map((t) => t.label)),
    // Artista principal de cada canción (el primero acreditado), no la línea entera «A & B».
    artists: ranked(tracks.map((t) => t.artists[0]?.name ?? t.artist_name)),
  };
}

/** «2 h 41 min», «48 min»; null sin duraciones. */
export function totalTime(ms: number): string | null {
  if (!ms) return null;
  const min = Math.round(ms / 60000);
  const h = Math.floor(min / 60);
  return h ? `${h} h ${String(min % 60).padStart(2, '0')} min` : `${min} min`;
}

/** «1987–2026», «2024». */
export function yearSpan(y: LibraryStats['years']): string | null {
  return y ? (y.from === y.to ? y.from : `${y.from}–${y.to}`) : null;
}

/** Orden de la lista: recientes (como se guardaron, la última arriba), por título o por año (sin año, al final). */
export function sortSaved(tracks: SavedTrack[], mode: SortMode): SavedTrack[] {
  if (mode === 'recent') return [...tracks].sort((a, b) => b.saved_at.localeCompare(a.saved_at));
  if (mode === 'az') return [...tracks].sort((a, b) => a.title.localeCompare(b.title, 'es', { sensitivity: 'base' }));
  return [...tracks].sort((a, b) => (a.year ?? '9999').localeCompare(b.year ?? '9999') || a.title.localeCompare(b.title, 'es'));
}
