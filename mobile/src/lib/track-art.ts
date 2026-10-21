/**
 * Dirección artística de TrackDNA: cada canción tiene una identidad estable derivada de su MBID (paleta, trío
 * tipográfico, composición del cartel y separador). Desde V5.4 esa variedad vive en el cartel y en el acento; el
 * interior de la ficha usa el sistema común `SHEET`. Lógica pura (sin React), reutilizable en Inicio V6.
 *
 * Legibilidad: cada superficie lleva su tinta y una tinta suave, ambas con contraste WCAG ≥ 4,5:1 (probado en
 * tests/track-art.test.ts). Los acentos solo se usan en formas, bandas y textos gigantes decorativos.
 */
import {
  ABRIL, contrast, DM_SERIF, DM_SERIF_ITALIC, mix, seedOf, SYNE, type Typeface, TYPEFACES,
} from './artist-identity.ts'; // relativo: también lo importan las pruebas de Node

export type Surface = { bg: string; ink: string; soft: string; line: string };
export type SurfaceKey = 'hero' | 'alt' | 'paper' | 'night';

export type ArtPalette = {
  name: string;
  hero: Surface;
  alt: Surface;
  paper: Surface;
  night: Surface;
  /** Formas y bandas (decorativos). */
  accent: string;
  accent2: string;
};

function surface(bg: string, ink: string): Surface {
  // Tinta suave: lo más cerca posible del fondo sin bajar de 4,5:1.
  let soft = ink;
  for (const t of [0.4, 0.32, 0.24, 0.16, 0.08]) {
    const c = mix(ink, bg, t);
    if (contrast(c, bg) >= 4.6) {
      soft = c;
      break;
    }
  }
  return { bg, ink, soft, line: mix(bg, ink, 0.28) };
}

function palette(name: string, hero: [string, string], alt: [string, string], paper: [string, string],
  night: [string, string], accent: string, accent2: string): ArtPalette {
  return { name, hero: surface(...hero), alt: surface(...alt), paper: surface(...paper), night: surface(...night), accent, accent2 };
}

/** Combinaciones de cartel de club: dos saturados que chocan, un papel claro y una noche profunda. */
export const ART_PALETTES: ArtPalette[] = [
  palette('Invernadero', ['#1D6B3A', '#FFEBDD'], ['#C81E1E', '#FFF2E8'], ['#F4EEDC', '#173A22'], ['#0E2416', '#F4EEDC'], '#E8322B', '#F4EEDC'),
  palette('Mandarina', ['#EE5A12', '#1C0700'], ['#FFE14A', '#3A1300'], ['#FFF3D6', '#3A1300'], ['#2A0E00', '#FFE14A'], '#FFE14A', '#2A0E00'),
  palette('Neón marino', ['#FF5FA2', '#0B1440'], ['#1F3BFF', '#FFE6F1'], ['#FFF0F6', '#0B1440'], ['#0B1440', '#FFC6DD'], '#1F3BFF', '#FFF0F6'),
  palette('Ácido fucsia', ['#C8FF3D', '#2A0024'], ['#C4006B', '#FFFFFF'], ['#F6FFE0', '#2A0024'], ['#1A0018', '#C8FF3D'], '#E6007E', '#2A0024'),
  palette('Lavanda crema', ['#5B2EFF', '#FFF6E0'], ['#FF7A59', '#22052E'], ['#FFF6E0', '#2B1170'], ['#170A3D', '#FFF6E0'], '#FF7A59', '#FFF6E0'),
  palette('Sala roja', ['#D7263D', '#FFF4E4'], ['#FFB627', '#2B0A00'], ['#FFF4E4', '#3A0A10'], ['#2B0A10', '#FFB627'], '#FFB627', '#FFF4E4'),
  palette('Petróleo mostaza', ['#0F4C5C', '#FFE8A3'], ['#FFB000', '#10262C'], ['#F3EBD8', '#10262C'], ['#08262E', '#FFB000'], '#FFB000', '#F3EBD8'),
  palette('Chicle bosque', ['#FF9CCB', '#0F3B1F'], ['#0E7A2F', '#FFF0F7'], ['#FFF0F7', '#0F3B1F'], ['#0F2A17', '#FF9CCB'], '#138A36', '#0F3B1F'),
];

const face = (key: Typeface['key']) => TYPEFACES.find((t) => t.key === key)!;

/** Tríos: titular + voz de contraste; la interfaz siempre en Space Grotesk y los datos breves en Space Mono. */
export type TypeTrio = { key: string; title: Typeface; voice: Typeface };
export const TRIOS: TypeTrio[] = [
  { key: 'club', title: face('anton'), voice: DM_SERIF_ITALIC },       // condensada + serif cursiva
  { key: 'fat', title: ABRIL, voice: SYNE },                           // serif fat display + geométrica ancha
  { key: 'geo', title: SYNE, voice: face('serif') },                   // geométrica ancha + cursiva fina retro
  { key: 'editorial', title: DM_SERIF, voice: face('archivo') },       // serif editorial + sans pesada
  { key: 'rave', title: face('rubik'), voice: ABRIL },                 // geométrica mono ancha + fat serif
  { key: 'press', title: face('archivo'), voice: DM_SERIF_ITALIC },    // sans pesada + serif cursiva
];

/** Composiciones del cartel: no es solo el color, cambia la estructura. */
export type HeroKind = 'stack' | 'band' | 'orbit' | 'split';
export const HEROES: HeroKind[] = ['stack', 'band', 'orbit', 'split'];

export type DividerKind = 'ticker' | 'dots' | 'stripes';

export type TrackArt = {
  palette: ArtPalette;
  trio: TypeTrio;
  hero: HeroKind;
  divider: DividerKind;
};

/**
 * Generación de la dirección artística: cambiarla redistribuye todas las identidades (nunca entre renders). «g14» se
 * eligió para que las tres fichas de referencia (Hoodlum, Lovelee Dae, Desire) difieran en paleta, tipografía y
 * composición; comprobado en tests/track-art.test.ts.
 */
export const ART_GENERATION = 'g14';

/**
 * FNV-1a con el finalizador de MurmurHash3 (fmix32): los bits bajos de FNV solo se mezclan con el final de la cadena,
 * y con `% 4` canciones distintas caían casi siempre en la misma composición.
 */
export function mixed(text: string): number {
  let h = seedOf(text);
  h ^= h >>> 16;
  h = Math.imul(h, 0x85ebca6b);
  h ^= h >>> 13;
  h = Math.imul(h, 0xc2b2ae35);
  h ^= h >>> 16;
  return h >>> 0;
}

/**
 * Identidad artística estable de una grabación. Cada rasgo usa su propio hash (MBID + nombre del rasgo): así las
 * combinaciones no van correlacionadas (con bits de una sola semilla, muchas canciones repetían trío y paleta).
 */
export function trackArt(mbid: string): TrackArt {
  const id = mbid || 'unknown';
  const pick = <T,>(list: readonly T[], trait: string) => list[mixed(`${ART_GENERATION}:${trait}:${id}`) % list.length];
  return {
    palette: pick(ART_PALETTES, 'palette'),
    trio: pick(TRIOS, 'type'),
    hero: pick(HEROES, 'hero'),
    divider: pick(['ticker', 'dots', 'stripes'] as const, 'divider'),
  };
}


// --- Sistema común de fichas (V5.4) ---------------------------------------------------------------------------------
/**
 * Misma marca, distintas canciones: todas las fichas (TrackDNA y artistas) comparten una base de tinta berenjena con
 * texto crema, una superficie elevada para las tarjetas y un papel claro de uso excepcional. Lo que cambia por canción
 * o artista es el cartel y el acento. Contraste comprobado en tests/track-art.test.ts.
 */
export const SHEET = {
  base: surface('#1A1117', '#F3E8D6'),
  raised: surface('#261A22', '#F3E8D6'),
  deep: surface('#130C10', '#F3E8D6'),
  paper: surface('#F2E7D5', '#1A1117'),
};

/** Croma (0–1): cuánto color tiene de verdad (un crema claro no es un acento aunque su saturación HSL sea alta). */
function chroma(hex: string): number {
  const [r, g, b] = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255);
  return Math.max(r, g, b) - Math.min(r, g, b);
}

/** Acento de una paleta sobre la base común: el primer color vivo legible (≥ 4,5:1 sobre base y tarjeta), y su tinta. */
export function sheetAccent(p: Pick<ArtPalette, 'accent' | 'accent2' | 'hero' | 'alt' | 'night'>): { color: string; ink: string } {
  const ok = (c: string) => chroma(c) >= 0.35 && contrast(c, SHEET.base.bg) >= 4.5 && contrast(c, SHEET.raised.bg) >= 4.5;
  const color = [p.accent, p.hero.bg, p.alt.bg, p.night.ink, p.accent2, p.hero.ink].find(ok)
    ?? mix(p.accent, SHEET.base.ink, 0.45);
  return { color, ink: contrast(SHEET.base.bg, color) >= contrast(SHEET.base.ink, color) ? SHEET.base.bg : SHEET.base.ink };
}
