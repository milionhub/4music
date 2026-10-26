/**
 * Carteles 4 · El sonido del cartel (V6.8): reparto de familias del line-up y estilo dominante por escenario y día, a
 * partir del sonido de cada artista (estilos habituales en Discogs). Es contexto del line-up, no lo que pinchará cada
 * uno. Cuenta artistas (no actuaciones): alguien que toca dos veces pesa uno. Lógica pura.
 */
import { soundOf } from './poster-fit.ts';
import type { PosterArtist, PosterEvent } from '../types/poster.ts';

/** Con menos artistas clasificados, un reparto engaña más que informa. */
export const SOUND_MIN = 3;
const MAX_FAMILIES = 5;

export type FamilyShare = { family: string; count: number; pct: number; styles: string[] };
export type SoundGroup = { id: string; name: string; lead: string; count: number };
export type EventSound = { classified: number; total: number; families: FamilyShare[]; stages: SoundGroup[]; days: SoundGroup[] };

const genreOf = (a: PosterArtist) => soundOf(a)?.genre ?? [];

/** Lo que más se repite en unos artistas: un estilo concreto compartido por dos o más y, si no, una familia con la
 * misma condición. Si nada se repite, null (dos artistas distintos no hacen un «sobre todo»). Empate: el primero. */
function lead(artists: PosterArtist[]): string | null {
  const top = (values: string[][]) => {
    const counts = new Map<string, number>();
    for (const v of values) for (const x of new Set(v)) counts.set(x, (counts.get(x) ?? 0) + 1);
    let best: string | null = null;
    for (const [x, n] of counts) if (n >= 2 && (!best || n > counts.get(best)!)) best = x;
    return best;
  };
  return top(artists.map((a) => genreOf(a).slice(1))) ?? top(artists.map((a) => genreOf(a).slice(0, 1)));
}

function groups(e: PosterEvent, key: 'stageId' | 'dayId', names: Map<string, string>): SoundGroup[] {
  const out: SoundGroup[] = [];
  for (const [id, name] of names) {
    const ids = new Set(e.sets.filter((s) => s[key] === id).flatMap((s) => s.artistIds));
    const artists = e.artists.filter((a) => ids.has(a.id) && genreOf(a).length);
    const l = artists.length >= 2 ? lead(artists) : null;
    if (l) out.push({ id, name, lead: l, count: artists.length });
  }
  return out;
}

export function eventSound(e: PosterEvent): EventSound {
  const classified = e.artists.filter((a) => genreOf(a).length);
  const byFamily = new Map<string, { count: number; styles: Map<string, number> }>();
  for (const a of classified) {
    const [family, ...styles] = genreOf(a);
    const f = byFamily.get(family) ?? { count: 0, styles: new Map() };
    f.count += 1;
    for (const s of styles) f.styles.set(s, (f.styles.get(s) ?? 0) + 1);
    byFamily.set(family, f);
  }
  const sorted = [...byFamily.entries()].sort((x, y) => y[1].count - x[1].count || x[0].localeCompare(y[0]));
  // Más de cinco familias: las menores se juntan en «Otros» (nunca un color o una fila por cada una).
  const head = sorted.slice(0, sorted.length > MAX_FAMILIES ? MAX_FAMILIES - 1 : MAX_FAMILIES);
  const rest = sorted.slice(head.length);
  const families: FamilyShare[] = head.map(([family, f]) => ({
    family, count: f.count, pct: 0,
    styles: [...f.styles.entries()].sort((x, y) => y[1] - x[1]).map(([s]) => s).slice(0, 3),
  }));
  if (rest.length) families.push({ family: 'Otros', count: rest.reduce((n, [, f]) => n + f.count, 0), pct: 0, styles: rest.map(([fam]) => fam).slice(0, 3) });
  const n = classified.length;
  for (const f of families) f.pct = n ? Math.round((f.count / n) * 100) : 0;
  const stageNames = new Map(e.stages.map((s) => [s.id, s.name]));
  const dayNames = new Map(e.days.map((d) => [d.id, d.label]));
  return {
    classified: n, total: e.artists.length, families,
    stages: stageNames.size > 1 ? groups(e, 'stageId', stageNames) : [],
    days: dayNames.size > 1 ? groups(e, 'dayId', dayNames) : [],
  };
}
