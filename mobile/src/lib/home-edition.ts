/**
 * Edición diaria de Inicio (V6): la portada cambia cada día local y es estable durante ese día (nunca entre renders).
 * Sin servidor ni imágenes generadas: la fecha local y `EDITION_GENERATION` deciden composición, paleta, pareja
 * tipográfica, titular y tratamiento de las secciones. Lógica pura (sin React), probada en tests/home.test.ts.
 *
 * Cada rasgo avanza con un paso coprimo con el tamaño de su lista: dos días seguidos nunca repiten composición,
 * paleta, pareja ni titular, y todas las opciones aparecen en cada ciclo. Paletas y parejas son las de TrackDNA V5.3
 * (lib/track-art.ts): un solo sistema visual, con el contraste ya comprobado en cada superficie.
 */
import { fitSize, type Typeface } from './artist-identity.ts';
import { ART_PALETTES, type ArtPalette, mixed, type SurfaceKey, TRIOS, type TypeTrio } from './track-art.ts';

/** Cambiarla redistribuye todas las ediciones (p. ej. al añadir composiciones). */
export const EDITION_GENERATION = 'e1';

/**
 * Familias editoriales de la portada: cada una cambia la distribución, no solo el color.
 * stack: tipografía gigante apilada · cross: titulares cruzados y bandas · asym: asimétrica con la portada musical ·
 * serif: serif protagonista con texto de contraste · blocks: bloques geométricos y espacio negativo.
 */
export type CoverLayout = 'stack' | 'cross' | 'asym' | 'serif' | 'blocks';
export const LAYOUTS: CoverLayout[] = ['stack', 'cross', 'asym', 'serif', 'blocks'];

/** Superficie de fondo de cada composición (la cabecera fija va siempre en `night`: iconos claros legibles). */
export const COVER_SURFACE: Record<CoverLayout, SurfaceKey> = { stack: 'hero', cross: 'paper', asym: 'alt', serif: 'paper', blocks: 'night' };

/** Encabezados de sección: banda de tinta a sangre, filete editorial o bloque de color con la palabra gigante. */
export type SectionHead = 'band' | 'rule' | 'block';
export const SECTION_HEADS: SectionHead[] = ['band', 'rule', 'block'];

/** Titular en dos voces: palabra gigante (titular) y frase corta en la voz de contraste. Textos propios de la marca. */
export type Headline = { word: string; voice: string };
export const HEADLINES: Headline[] = [
  { word: 'Señal', voice: 'de madrugada' },
  { word: 'Graves', voice: 'con memoria' },
  { word: 'Club', voice: 'sin mapa' },
  { word: 'Pulso', voice: 'bajo tierra' },
  { word: 'Ecos', voice: 'del sótano' },
  { word: 'Ruido', voice: 'con raíces' },
  { word: 'Hoy', voice: 'suena distinto' },
  { word: 'Voltaje', voice: 'lento' },
  { word: 'Niebla', voice: 'y bombo' },
  { word: 'Desvío', voice: 'al amanecer' },
  { word: 'Calor', voice: 'de cabina' },
];

export type Edition = {
  /** Fecha local AAAA-MM-DD: identifica la edición. */
  key: string;
  dayIndex: number;
  /** «martes 20 oct». */
  dateLabel: string;
  layout: CoverLayout;
  palette: ArtPalette;
  trio: TypeTrio;
  headline: Headline;
  head: SectionHead;
  /** Superficies de En el radar, Tu frecuencia y Detrás del sonido (sin dos seguidas iguales ni pegadas a la portada). */
  rhythm: [SurfaceKey, SurfaceKey, SurfaceKey];
};

const DAYS = ['domingo', 'lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado'];
const MONTHS = ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sept', 'oct', 'nov', 'dic'];

/** Fecha LOCAL del dispositivo (no UTC: la edición cambia a medianoche del usuario). */
export function localDayKey(date: Date): string {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`;
}

/** Días desde 1970-01-01 de una clave local (aritmética en UTC: sin saltos por cambio de hora). */
export function dayIndexOf(key: string): number {
  const [y, m, d] = key.split('-').map(Number);
  return Math.floor(Date.UTC(y, (m || 1) - 1, d || 1) / 86400000);
}

/** Elemento `step` posiciones más allá cada día; con `step` coprimo con la longitud recorre toda la lista. */
export function rotate<T>(list: readonly T[], dayIndex: number, step: number, trait: string): T {
  const offset = mixed(`${EDITION_GENERATION}:${trait}`) % list.length;
  return list[(((dayIndex * step + offset) % list.length) + list.length) % list.length];
}

const SURFACES: SurfaceKey[] = ['hero', 'alt', 'paper', 'night'];
/** Todas las secuencias de tres superficies sin dos seguidas iguales. */
const RHYTHMS: [SurfaceKey, SurfaceKey, SurfaceKey][] = SURFACES.flatMap((a) => SURFACES.flatMap((b) => SURFACES.map((c) => [a, b, c] as [SurfaceKey, SurfaceKey, SurfaceKey])))
  .filter(([a, b, c]) => a !== b && b !== c);

export function editionFor(key: string): Edition {
  const dayIndex = dayIndexOf(key);
  const layout = rotate(LAYOUTS, dayIndex, 2, 'layout'); // 2 y 5: coprimos
  const rhythms = RHYTHMS.filter((r) => r[0] !== COVER_SURFACE[layout]);
  const [y, m, d] = key.split('-').map(Number);
  const weekday = new Date(Date.UTC(y, m - 1, d)).getUTCDay();
  return {
    key,
    dayIndex,
    dateLabel: `${DAYS[weekday]} ${d} ${MONTHS[m - 1]}`,
    layout,
    palette: rotate(ART_PALETTES, dayIndex, 3, 'palette'), // 3 y 8
    trio: rotate(TRIOS, dayIndex, 5, 'trio'), // 5 y 6
    headline: rotate(HEADLINES, dayIndex, 4, 'headline'), // 4 y 11
    head: rotate(SECTION_HEADS, dayIndex, 1, 'head'),
    rhythm: rotate(rhythms, dayIndex, 7, 'rhythm'),
  };
}

/**
 * Reparte un texto ya en su caja (mayúsculas si la familia las usa) en 1–3 líneas para el mayor cuerpo que quepa en
 * `width`. Una línea más solo si gana al menos un 15 % de cuerpo: los titulares cortos siguen en una sola línea.
 */
export function fitLines(text: string, width: number, face: Typeface, max: number): { lines: string[]; size: number } {
  const words = text.trim().split(/\s+/);
  const measure = (lines: string[]) => Math.min(...lines.map((l) => fitSize(l, width, face, max, 1)));
  let best = { lines: [words.join(' ')], size: measure([words.join(' ')]) };
  const cuts = (n: number, from: number): number[][] =>
    n === 1 ? [[]] : Array.from({ length: words.length - from - n + 1 }, (_, i) => from + i + 1).flatMap((c) => cuts(n - 1, c).map((rest) => [c, ...rest]));
  for (let n = 2; n <= Math.min(3, words.length); n++) {
    for (const cut of cuts(n, 0)) {
      const bounds = [0, ...cut, words.length];
      const lines = bounds.slice(0, -1).map((b, i) => words.slice(b, bounds[i + 1]).join(' '));
      const size = measure(lines);
      if (size > best.size * 1.15) best = { lines, size };
    }
  }
  return best;
}
