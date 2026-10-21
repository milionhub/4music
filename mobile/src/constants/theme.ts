/**
 * Chromatic Underground: base oscura, tipografía condensada contundente y acentos cromáticos.
 * El color de cada artista se deriva de su MBID (no de su género: sin asociación rígida color-género).
 */
import '@/global.css';

export const C = {
  bg: '#07060B',
  bgRaised: '#0F0D16',
  surface: '#16131F',
  surfaceHigh: '#1F1B2B',
  line: '#2C2739',
  text: '#F6F3FF',
  muted: '#A7A1BA',
  faint: '#726C86',
  acid: '#C8FF3D',
  magenta: '#FF2E88',
  cyan: '#2EE6FF',
  violet: '#7C5CFF',
  orange: '#FF7A1A',
  danger: '#FF6B6B',
  onAccent: '#07060B',
} as const;

const ACCENT_PAIRS = [
  [C.magenta, C.violet],
  [C.cyan, C.violet],
  [C.acid, C.cyan],
  [C.orange, C.magenta],
  [C.violet, C.cyan],
  [C.magenta, C.orange],
] as const;

export type AccentPair = readonly [string, string];

export function accentFor(id: string): AccentPair {
  let hash = 0;
  for (let i = 0; i < id.length; i++) hash = (hash * 31 + id.charCodeAt(i)) >>> 0;
  return ACCENT_PAIRS[hash % ACCENT_PAIRS.length];
}

/** Gradiente CSS para `experimental_backgroundImage` (RN 0.86, nueva arquitectura). */
export function gradient(pair: AccentPair, angleDeg = 135): string {
  return `linear-gradient(${angleDeg}deg, ${pair[0]}, ${pair[1]})`;
}

/**
 * Sistema tipográfico (v5.1), todo OFL y cargado en app/_layout.tsx. Cuatro roles:
 * A. display contundente (Anton, Archivo Black) · B. serif expresiva con cursiva (DM Serif Display) ·
 * C. sans de interfaz (Space Grotesk) · D. mono para metadatos (Space Mono).
 * Cada peso es una familia propia: nunca se combina con `fontWeight` (Android sintetizaría la negrita).
 */
export const Fonts = {
  display: 'Anton',
  displayWeight: '400' as const,
  /** Titulares con más masa (tarjetas, cifras). */
  heavy: 'ArchivoBlack',
  serifDisplay: 'DMSerifDisplay',
  serifItalic: 'DMSerifDisplay-Italic',
  serif: 'InstrumentSerif-Italic',
  sans: 'SpaceGrotesk-Medium',
  sansBold: 'SpaceGrotesk-Bold',
  mono: 'SpaceMono',
  monoBold: 'SpaceMono-Bold',
};

export const Space = { xs: 4, sm: 8, md: 12, lg: 16, xl: 24, xxl: 32, xxxl: 48 } as const;
export const Radius = { sm: 6, md: 12, lg: 20, pill: 999 } as const;
export const MaxContentWidth = 720;
