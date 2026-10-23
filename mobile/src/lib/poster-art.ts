/**
 * Carteles 3.5: identidad visual de cada evento. Lógica pura, probada en tests/posters.test.ts.
 *
 * - Paleta: los colores que la IA leyó en el cartel (`palette.seeds`, ya guardados) se validan y se ajustan a la
 *   paleta más cercana del sistema Chromatic (`PALETTES`, con contraste WCAG ya comprobado). Sin colores útiles, una
 *   paleta determinista por la huella del cartel (o su id). Se calcula siempre igual a partir de lo guardado: estable
 *   entre aperturas y sin reescribir eventos antiguos.
 * - Composición: cuatro familias propias de Carteles (no las de Inicio ni TrackDNA), elegidas por la misma semilla.
 */
import {
  ABRIL, contrast, type Palette, PALETTES, seedOf, surfaces, SYNE, type Typeface, TYPEFACES,
} from './artist-identity.ts';

export type CoverKind = 'billboard' | 'ticket' | 'stamp' | 'column';
export const COVER_KINDS: CoverKind[] = ['billboard', 'ticket', 'stamp', 'column'];
/** Tipografías de cartel con masa suficiente para un nombre de evento (todas con anchos de glifo medidos). */
export const EVENT_TYPES: Typeface[] = [TYPEFACES[0], TYPEFACES[1], SYNE, ABRIL];

export type EventArt = {
  palette: Palette;
  source: 'poster' | 'fallback';
  kind: CoverKind;
  type: Typeface;
  surfaces: ReturnType<typeof surfaces>;
};

const HEX = /^#[0-9a-f]{6}$/i;
const rgb = (hex: string) => [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16));

function luminance(hex: string): number {
  const [r, g, b] = rgb(hex).map((c) => c / 255).map((c) => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4));
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

/** Croma aproximado (0–1): diferencia entre el canal mayor y el menor. */
function chroma(hex: string): number {
  const c = rgb(hex);
  return (Math.max(...c) - Math.min(...c)) / 255;
}

/** Distancia perceptual sencilla («redmean»): suficiente para elegir la paleta más cercana. */
function distance(a: string, b: string): number {
  const [r1, g1, b1] = rgb(a);
  const [r2, g2, b2] = rgb(b);
  const rm = (r1 + r2) / 2;
  return Math.sqrt((2 + rm / 256) * (r1 - r2) ** 2 + 4 * (g1 - g2) ** 2 + (2 + (255 - rm) / 256) * (b1 - b2) ** 2);
}

const isDark = (hex: string) => luminance(hex) < 0.05;
const DARK_PALETTES = PALETTES.filter((p) => isDark(p.bg));

/** Colores del cartel que sirven para elegir paleta: hex válidos, ni casi negros, ni casi blancos, ni grises. */
export function usableSeeds(seeds: readonly string[]): string[] {
  return seeds.filter((c) => HEX.test(c) && !isDark(c) && luminance(c) < 0.85 && chroma(c) >= 0.2);
}

/**
 * Paleta del sistema más cercana a los colores del cartel. Un cartel de fondo oscuro (primer color casi negro) usa
 * las paletas oscuras, comparando su color de acento; si no, se compara el fondo con el color dominante y el acento
 * con el segundo. null si no hay colores útiles.
 */
export function paletteFromSeeds(seeds: readonly string[]): Palette | null {
  const valid = seeds.filter((c) => HEX.test(c));
  const useful = usableSeeds(valid);
  if (!useful.length) return null;
  const [main, second] = useful;
  const score = valid.length && isDark(valid[0])
    ? (p: Palette) => Math.min(distance(p.pop, main), distance(p.glow, main))
    : (p: Palette) => distance(p.bg, main) + (second ? 0.5 * distance(p.pop, second) : 0);
  const pool = valid.length && isDark(valid[0]) ? DARK_PALETTES : PALETTES;
  return pool.reduce((best, p) => (score(p) < score(best) ? p : best), pool[0]);
}

/** Identidad completa de un evento (o de su entrada en la biblioteca). Misma entrada → mismo resultado. */
export function eventArt(e: { id: string; fingerprint: string | null; seeds: readonly string[] }): EventArt {
  const s = seedOf(e.fingerprint || e.id);
  const fromPoster = paletteFromSeeds(e.seeds);
  const palette = fromPoster ?? PALETTES[s % PALETTES.length];
  return {
    palette, source: fromPoster ? 'poster' : 'fallback',
    kind: COVER_KINDS[(s >>> 7) % COVER_KINDS.length],
    type: EVENT_TYPES[(s >>> 11) % EVENT_TYPES.length],
    surfaces: surfaces(palette),
  };
}

/** Tinta legible sobre un color arbitrario (para chips y etiquetas sobre la paleta). */
export function inkOn(bg: string): string {
  return contrast('#07060B', bg) >= contrast('#F6F3FF', bg) ? '#07060B' : '#F6F3FF';
}
