/**
 * Identidad visual de cada artista: paleta, tipografía, composición y elementos gráficos derivados de su MBID.
 * Determinista (la misma ficha siempre se ve igual) y sin relación con el género musical. Lógica pura: sin React.
 *
 * Contraste: `ink` sobre `bg` (cartel) y `glow` sobre el fondo oscuro de la app se comprueban en las pruebas
 * (WCAG ≥ 4,5:1 para texto). `pop` es decorativo (formas, bandas) y nunca lleva texto pequeño.
 */

export type Palette = {
  name: string;
  /** Fondo del cartel. */
  bg: string;
  /** Texto sobre `bg`. */
  ink: string;
  /** Color de formas y bandas del cartel (decorativo). */
  pop: string;
  /** Acento sobre el fondo oscuro de la ficha (títulos de sección, etiquetas, botones). */
  glow: string;
  /** Texto sobre `glow` (botón principal, etiquetas rellenas). */
  onGlow: string;
};

export const PALETTES: Palette[] = [
  { name: 'Ácido', bg: '#D4FF3A', ink: '#101010', pop: '#FF3EA5', glow: '#D4FF3A', onGlow: '#101010' },
  { name: 'Ultravioleta', bg: '#2B12FF', ink: '#F4F1FF', pop: '#FF5E3A', glow: '#9C8CFF', onGlow: '#0B0430' },
  { name: 'Chicle', bg: '#FF8AD8', ink: '#1A0B2E', pop: '#1F3BFF', glow: '#FF8AD8', onGlow: '#1A0B2E' },
  { name: 'Señal', bg: '#FF5A1F', ink: '#120A06', pop: '#FFF6E0', glow: '#FF7A45', onGlow: '#120A06' },
  { name: 'Menta tóxica', bg: '#6CFFC4', ink: '#04131F', pop: '#FF2D55', glow: '#6CFFC4', onGlow: '#04131F' },
  { name: 'Sala roja', bg: '#1A0606', ink: '#FFE9E0', pop: '#FF2A1F', glow: '#FF5A4F', onGlow: '#1A0606' },
  { name: 'Cobalto', bg: '#0038FF', ink: '#F0F5FF', pop: '#D9FF3C', glow: '#7FA2FF', onGlow: '#000F45' },
  { name: 'Limón', bg: '#FFF14A', ink: '#0E0E0E', pop: '#FF2E88', glow: '#FFF14A', onGlow: '#0E0E0E' },
  { name: 'Lavanda', bg: '#C9B8FF', ink: '#14062E', pop: '#FF4F1F', glow: '#C9B8FF', onGlow: '#14062E' },
  { name: 'Bosque', bg: '#0E3B2E', ink: '#E9FFF3', pop: '#C8FF3D', glow: '#7DFFB2', onGlow: '#062018' },
  { name: 'Cereza', bg: '#C8103D', ink: '#FFF0F3', pop: '#FFD23F', glow: '#FF6F8E', onGlow: '#2A0410' },
  { name: 'Hormigón', bg: '#D9D6CF', ink: '#121212', pop: '#FF3B00', glow: '#E8E4DA', onGlow: '#121212' },
  { name: 'Petróleo', bg: '#062A33', ink: '#E3FBFF', pop: '#FF8A00', glow: '#5FE3FF', onGlow: '#03171C' },
  { name: 'Infrarrojo', bg: '#FF2E88', ink: '#14000A', pop: '#C8FF3D', glow: '#FF5FA2', onGlow: '#14000A' },
  { name: 'Cielo químico', bg: '#6FD3FF', ink: '#00121C', pop: '#FF3EA5', glow: '#6FD3FF', onGlow: '#00121C' },
  { name: 'Negro neón', bg: '#0A0A0A', ink: '#F5F5F5', pop: '#00FFA3', glow: '#00FFA3', onGlow: '#00140C' },
];

export type Typeface = {
  key: 'anton' | 'archivo' | 'rubik' | 'serif' | 'dmserif' | 'dmserifItalic' | 'abril' | 'syne';
  /** Nombre registrado con expo-font (app/_layout.tsx). */
  family: string;
  upper: boolean;
  /** Ancho medio de un carácter respecto al tamaño de letra: para ajustar el nombre al ancho disponible. */
  widthFactor: number;
  lineFactor: number;
  tracking: number;
};

export const TYPEFACES: Typeface[] = [
  { key: 'anton', family: 'Anton', upper: true, widthFactor: 0.46, lineFactor: 0.98, tracking: 0 },
  { key: 'archivo', family: 'ArchivoBlack', upper: true, widthFactor: 0.78, lineFactor: 0.92, tracking: -1 },
  { key: 'rubik', family: 'RubikMonoOne', upper: true, widthFactor: 0.86, lineFactor: 1.0, tracking: -1 },
  { key: 'serif', family: 'InstrumentSerif-Italic', upper: false, widthFactor: 0.42, lineFactor: 0.92, tracking: -1 },
];

/** Anchos de avance reales (em) de cada glifo, medidos en las tablas TrueType de assets/fonts (ver capa v3). */
const GLYPH_WIDTHS: Partial<Record<Typeface['key'], Record<string, number>>> = {
  anton: {
    "0": 0.494, "1": 0.331, "2": 0.494, "3": 0.494, "4": 0.494, "5": 0.494, "6": 0.494, "7": 0.494, "8": 0.494,
    "9": 0.494, "A": 0.485, "B": 0.479, "C": 0.474, "D": 0.493, "E": 0.412, "F": 0.399, "G": 0.485, "H": 0.499,
    "I": 0.227, "J": 0.466, "K": 0.472, "L": 0.397, "M": 0.746, "N": 0.498, "O": 0.486, "P": 0.472, "Q": 0.494,
    "R": 0.477, "S": 0.461, "T": 0.396, "U": 0.474, "V": 0.469, "W": 0.712, "X": 0.484, "Y": 0.446, "Z": 0.41,
    "a": 0.483, "b": 0.501, "c": 0.491, "d": 0.498, "e": 0.488, "f": 0.28, "g": 0.504, "h": 0.505, "i": 0.243,
    "j": 0.263, "k": 0.491, "l": 0.248, "m": 0.758, "n": 0.499, "o": 0.497, "p": 0.501, "q": 0.498, "r": 0.347,
    "s": 0.475, "t": 0.305, "u": 0.499, "v": 0.461, "w": 0.696, "x": 0.459, "y": 0.461, "z": 0.386, " ": 0.234,
    "&": 0.52, ".": 0.229, "-": 0.311, "'": 0.214, "�": 0.474, "!": 0.229, "?": 0.492,
  },
  archivo: {
    "0": 0.667, "1": 0.667, "2": 0.667, "3": 0.667, "4": 0.667, "5": 0.667, "6": 0.667, "7": 0.667, "8": 0.667,
    "9": 0.667, "A": 0.778, "B": 0.778, "C": 0.778, "D": 0.778, "E": 0.722, "F": 0.667, "G": 0.833, "H": 0.833,
    "I": 0.389, "J": 0.667, "K": 0.833, "L": 0.667, "M": 0.944, "N": 0.833, "O": 0.833, "P": 0.722, "Q": 0.833,
    "R": 0.778, "S": 0.722, "T": 0.722, "U": 0.833, "V": 0.778, "W": 1, "X": 0.778, "Y": 0.778, "Z": 0.722,
    "a": 0.667, "b": 0.667, "c": 0.667, "d": 0.667, "e": 0.667, "f": 0.389, "g": 0.667, "h": 0.667, "i": 0.333,
    "j": 0.333, "k": 0.667, "l": 0.333, "m": 1, "n": 0.667, "o": 0.667, "p": 0.667, "q": 0.667, "r": 0.444,
    "s": 0.611, "t": 0.444, "u": 0.667, "v": 0.611, "w": 0.944, "x": 0.667, "y": 0.611, "z": 0.556, " ": 0.333,
    "&": 0.889, ".": 0.333, "-": 0.333, "'": 0.278, "�": 0.778, "!": 0.333, "?": 0.611,
  },
  rubik: {
    "0": 0.85, "1": 0.85, "2": 0.85, "3": 0.85, "4": 0.85, "5": 0.85, "6": 0.85, "7": 0.85, "8": 0.85, "9": 0.85,
    "A": 0.85, "B": 0.85, "C": 0.85, "D": 0.85, "E": 0.85, "F": 0.85, "G": 0.85, "H": 0.85, "I": 0.85, "J": 0.85,
    "K": 0.85, "L": 0.85, "M": 0.85, "N": 0.85, "O": 0.85, "P": 0.85, "Q": 0.85, "R": 0.85, "S": 0.85, "T": 0.85,
    "U": 0.85, "V": 0.85, "W": 0.85, "X": 0.85, "Y": 0.85, "Z": 0.85, "a": 0.85, "b": 0.85, "c": 0.85, "d": 0.85,
    "e": 0.85, "f": 0.85, "g": 0.85, "h": 0.85, "i": 0.85, "j": 0.85, "k": 0.85, "l": 0.85, "m": 0.85, "n": 0.85,
    "o": 0.85, "p": 0.85, "q": 0.85, "r": 0.85, "s": 0.85, "t": 0.85, "u": 0.85, "v": 0.85, "w": 0.85, "x": 0.85,
    "y": 0.85, "z": 0.85, " ": 0.85, "&": 0.85, ".": 0.85, "-": 0.85, "'": 0.85, "�": 0.85, "!": 0.85, "?": 0.85,
  },
  serif: {
    "0": 0.461, "1": 0.248, "2": 0.404, "3": 0.373, "4": 0.394, "5": 0.387, "6": 0.411, "7": 0.365, "8": 0.437,
    "9": 0.414, "A": 0.457, "B": 0.479, "C": 0.475, "D": 0.536, "E": 0.454, "F": 0.411, "G": 0.514, "H": 0.545,
    "I": 0.25, "J": 0.251, "K": 0.499, "L": 0.414, "M": 0.665, "N": 0.542, "O": 0.54, "P": 0.469, "Q": 0.541,
    "R": 0.525, "S": 0.424, "T": 0.461, "U": 0.537, "V": 0.458, "W": 0.653, "X": 0.545, "Y": 0.478, "Z": 0.427,
    "a": 0.474, "b": 0.431, "c": 0.351, "d": 0.474, "e": 0.348, "f": 0.273, "g": 0.401, "h": 0.476, "i": 0.288,
    "j": 0.266, "k": 0.447, "l": 0.24, "m": 0.745, "n": 0.521, "o": 0.414, "p": 0.45, "q": 0.425, "r": 0.368,
    "s": 0.302, "t": 0.272, "u": 0.508, "v": 0.412, "w": 0.609, "x": 0.45, "y": 0.418, "z": 0.385, " ": 0.17,
    "&": 0.525, ".": 0.219, "-": 0.426, "'": 0.235, "�": 0.475, "!": 0.275, "?": 0.358,
  },
};


/**
 * Tipografías editoriales de TrackDNA (v5.1). No entran en `TYPEFACES`: las identidades de los artistas no cambian.
 * DM Serif Display (OFL), cargada en app/_layout.tsx con @expo-google-fonts.
 */
export const DM_SERIF: Typeface = { key: 'dmserif', family: 'DMSerifDisplay', upper: false, widthFactor: 0.52, lineFactor: 1.02, tracking: -0.5 };
export const DM_SERIF_ITALIC: Typeface = { key: 'dmserifItalic', family: 'DMSerifDisplay-Italic', upper: false, widthFactor: 0.5, lineFactor: 1.02, tracking: -0.5 };

Object.assign(GLYPH_WIDTHS, {
  dmserif: {
    "0": 0.502, "1": 0.35, "2": 0.532, "3": 0.532, "4": 0.538, "5": 0.532, "6": 0.53, "7": 0.489, "8": 0.502,
    "9": 0.532, "A": 0.65, "B": 0.598, "C": 0.603, "D": 0.648, "E": 0.555, "F": 0.538, "G": 0.656, "H": 0.691,
    "I": 0.301, "J": 0.427, "K": 0.654, "L": 0.54, "M": 0.791, "N": 0.653, "O": 0.67, "P": 0.565, "Q": 0.67,
    "R": 0.628, "S": 0.521, "T": 0.627, "U": 0.649, "V": 0.632, "W": 0.921, "X": 0.614, "Y": 0.59, "Z": 0.56,
    "a": 0.518, "b": 0.581, "c": 0.494, "d": 0.574, "e": 0.507, "f": 0.343, "g": 0.531, "h": 0.58, "i": 0.28,
    "j": 0.281, "k": 0.582, "l": 0.286, "m": 0.871, "n": 0.578, "o": 0.545, "p": 0.578, "q": 0.565, "r": 0.441,
    "s": 0.436, "t": 0.361, "u": 0.567, "v": 0.53, "w": 0.781, "x": 0.568, "y": 0.536, "z": 0.465, " ": 0.218,
    "&": 0.721, ".": 0.3, "-": 0.332, "'": 0.223, "!": 0.333, "?": 0.506, "(": 0.368, ")": 0.368,
  },
  dmserifItalic: {
    "0": 0.538, "1": 0.384, "2": 0.509, "3": 0.505, "4": 0.538, "5": 0.494, "6": 0.535, "7": 0.446, "8": 0.49,
    "9": 0.529, "A": 0.659, "B": 0.604, "C": 0.6, "D": 0.663, "E": 0.558, "F": 0.527, "G": 0.649, "H": 0.701,
    "I": 0.315, "J": 0.393, "K": 0.64, "L": 0.537, "M": 0.843, "N": 0.625, "O": 0.667, "P": 0.559, "Q": 0.667,
    "R": 0.642, "S": 0.499, "T": 0.599, "U": 0.622, "V": 0.603, "W": 0.876, "X": 0.623, "Y": 0.57, "Z": 0.543,
    "a": 0.559, "b": 0.512, "c": 0.454, "d": 0.553, "e": 0.456, "f": 0.332, "g": 0.522, "h": 0.545, "i": 0.285,
    "j": 0.283, "k": 0.49, "l": 0.275, "m": 0.823, "n": 0.553, "o": 0.523, "p": 0.523, "q": 0.526, "r": 0.426,
    "s": 0.407, "t": 0.342, "u": 0.555, "v": 0.512, "w": 0.78, "x": 0.565, "y": 0.521, "z": 0.489, " ": 0.221,
    "&": 0.726, ".": 0.308, "-": 0.337, "'": 0.274, "!": 0.299, "?": 0.455, "(": 0.387, ")": 0.387,
  },
});

/**
 * V5.3 (dirección artística de TrackDNA, lib/track-art.ts): serif *fat display* de cartel (Abril Fatface) y sans
 * geométrica ancha (Syne ExtraBold). OFL, @expo-google-fonts. Anchos medidos en los TTF.
 */
export const ABRIL: Typeface = { key: 'abril', family: 'AbrilFatface', upper: false, widthFactor: 0.6, lineFactor: 1.08, tracking: 0 };
export const SYNE: Typeface = { key: 'syne', family: 'Syne-ExtraBold', upper: true, widthFactor: 0.72, lineFactor: 1.0, tracking: -1 };

Object.assign(GLYPH_WIDTHS, {
  abril: {
    "0": 0.664, "1": 0.425, "2": 0.552, "3": 0.573, "4": 0.603, "5": 0.54, "6": 0.616, "7": 0.51, "8": 0.611,
    "9": 0.616, "A": 0.694, "B": 0.659, "C": 0.69, "D": 0.755, "E": 0.624, "F": 0.592, "G": 0.723, "H": 0.749,
    "I": 0.355, "J": 0.517, "K": 0.734, "L": 0.596, "M": 0.84, "N": 0.67, "O": 0.748, "P": 0.634, "Q": 0.748,
    "R": 0.716, "S": 0.6, "T": 0.683, "U": 0.683, "V": 0.685, "W": 1.015, "X": 0.711, "Y": 0.641, "Z": 0.612,
    "a": 0.549, "b": 0.588, "c": 0.483, "d": 0.588, "e": 0.516, "f": 0.383, "g": 0.522, "h": 0.616, "i": 0.317,
    "j": 0.311, "k": 0.62, "l": 0.316, "m": 0.888, "n": 0.616, "o": 0.543, "p": 0.588, "q": 0.588, "r": 0.495,
    "s": 0.434, "t": 0.394, "u": 0.605, "v": 0.532, "w": 0.834, "x": 0.595, "y": 0.532, "z": 0.52, " ": 0.18,
    "&": 0.822, ".": 0.265, "-": 0.352, "'": 0.186, "!": 0.377, "?": 0.58, "(": 0.351, ")": 0.351,
  },
  syne: {
    "0": 1.066, "1": 0.529, "2": 1.003, "3": 1.055, "4": 1.094, "5": 1.015, "6": 1.133, "7": 1.153, "8": 1.081,
    "9": 1.158, "A": 1.16, "B": 1.14, "C": 1.316, "D": 1.302, "E": 1.14, "F": 1.128, "G": 1.34, "H": 1.28, "I": 0.42,
    "J": 1.004, "K": 1.215, "L": 0.943, "M": 1.58, "N": 1.3, "O": 1.33, "P": 1.177, "Q": 1.33, "R": 1.232,
    "S": 1.056, "T": 1.1, "U": 1.289, "V": 1.16, "W": 1.882, "X": 1.14, "Y": 1.07, "Z": 1.2, "a": 1.063, "b": 1.098,
    "c": 0.994, "d": 1.098, "e": 0.994, "f": 0.674, "g": 0.969, "h": 1.008, "i": 0.364, "j": 0.364, "k": 0.942,
    "l": 0.36, "m": 1.654, "n": 0.998, "o": 1.016, "p": 1.063, "q": 1.098, "r": 0.563, "s": 0.842, "t": 0.628,
    "u": 0.998, "v": 0.918, "w": 1.462, "x": 0.98, "y": 0.93, "z": 0.896, " ": 0.31, "&": 1.22, ".": 0.354,
    "-": 0.59, "'": 0.3, "!": 0.394, "?": 0.864, "(": 0.405, ")": 0.405,
  },
});

/** Composiciones del cartel (y del tratamiento de la foto): ver components/artist-poster.tsx. */
export type Composition = 'tower' | 'marquee' | 'slash' | 'grid';
export const COMPOSITIONS: Composition[] = ['tower', 'marquee', 'slash', 'grid'];

export type Shape = 'circle' | 'bars' | 'ring' | 'block';
const SHAPES: Shape[] = ['circle', 'bars', 'ring', 'block'];

export type ArtistIdentity = {
  palette: Palette;
  type: Typeface;
  composition: Composition;
  shape: Shape;
  /** Inclinación del texto gigante (grados), siempre pequeña para no perder legibilidad. */
  tilt: number;
  /** Número de «edición» del cartel (decorativo, estable): 01–99. */
  issue: string;
};

/** FNV-1a de 32 bits: estable entre plataformas y versiones (no depende del motor de JavaScript). */
export function seedOf(id: string): number {
  let h = 0x811c9dc5;
  for (let i = 0; i < id.length; i++) {
    h ^= id.charCodeAt(i);
    h = Math.imul(h, 0x01000193) >>> 0;
  }
  return h >>> 0;
}

/** Cada rasgo sale de bits distintos de la semilla: combinaciones variadas, no una plantilla con el color cambiado. */
export function identityFor(id: string): ArtistIdentity {
  const s = seedOf(id || 'unknown');
  const pick = <T,>(list: T[], shift: number) => list[(s >>> shift) % list.length];
  return {
    palette: pick(PALETTES, 0),
    type: pick(TYPEFACES, 5),
    composition: pick(COMPOSITIONS, 9),
    shape: pick(SHAPES, 13),
    tilt: [-7, -4, 0, 3, 6][(s >>> 17) % 5],
    issue: String(((s >>> 20) % 99) + 1).padStart(2, '0'),
  };
}

/**
 * Paleta propia de cada sección con identidad fija (V6.8). TrackDNA rota a diario por las demás: así ningún día se
 * confunde con Guardados, Perfil o Carteles.
 */
export const SECTION_PALETTES = { saved: 'Cielo químico', profile: 'Ultravioleta', posters: 'Señal' } as const;

/**
 * Identidad fija para pantallas de la app (TrackDNA, Guardados): las mismas paletas y tipografías que los artistas,
 * elegidas por nombre, para que todo pertenezca al mismo sistema visual.
 */
export function fixedIdentity(palette: string, type: Typeface['key'], composition: Composition = 'grid', shape: Shape = 'circle'): ArtistIdentity {
  return {
    palette: PALETTES.find((p) => p.name === palette) ?? PALETTES[0],
    type: TYPEFACES.find((t) => t.key === type) ?? TYPEFACES[0],
    composition, shape, tilt: 0, issue: '01',
  };
}

/**
 * Título de canción en dos voces: el nombre y, aparte, la versión o el subtítulo entre paréntesis o tras un guion
 * («Dirty Cash» + «Money Talks»). Así los títulos largos se leen enteros sin encoger todo el cartel.
 */
export function splitTitle(title: string): { main: string; aside: string | null } {
  const t = title.trim();
  const paren = t.match(/^(.+?)\s*[([]([^()[\]]+)[)\]]\s*$/);
  if (paren && paren[1].trim().length >= 2) return { main: paren[1].trim(), aside: paren[2].trim() };
  const dash = t.match(/^(.+?)\s+[-–—]\s+(.+)$/);
  if (dash && dash[1].trim().length >= 2) return { main: dash[1].trim(), aside: dash[2].trim() };
  return { main: t, aside: null };
}

/** Texto tal como se pinta (mayúsculas según la familia). */
export function display(text: string, type: Typeface): string {
  return type.upper ? text.toUpperCase() : text;
}

/** Ancho en em de un texto con la tipografía dada (anchos reales de cada glifo; media para los desconocidos). */
export function textWidthEm(text: string, type: Typeface): number {
  const widths = GLYPH_WIDTHS[type.key] ?? {};
  return [...text].reduce((sum, ch) => sum + (widths[ch] ?? type.widthFactor), 0);
}

/**
 * Tamaño de letra para que `text` quepa entero en una línea de `width` px, entre `min` y `max`: suma el ancho real
 * de cada letra y el espaciado, con un 6 % de margen (el nombre nunca debe quedar cortado por el borde).
 */
export function fitSize(text: string, width: number, type: Typeface, max: number, min = 18): number {
  const em = Math.max(0.3, textWidthEm(text, type));
  const tracking = type.tracking * Math.max(0, [...text].length - 1);
  return Math.floor(Math.max(min, Math.min(max, (width * 0.94 - tracking) / em)));
}

/**
 * Líneas del nombre para un cartel: palabra a palabra, uniendo las muy cortas («&», «DJ», «The») a la siguiente
 * para que no queden huérfanas. Un nombre de una palabra larga queda en una línea (se ajusta por tamaño).
 */
export function nameLines(name: string, maxLines = 3): string[] {
  const words = name.trim().split(/\s+/).filter(Boolean);
  const lines: string[] = [];
  for (const w of words) {
    const last = lines[lines.length - 1];
    if (last !== undefined && (last.length <= 3 || w.length <= 2)) lines[lines.length - 1] = `${last} ${w}`;
    else lines.push(w);
  }
  while (lines.length > maxLines) {
    // Une la pareja de líneas contiguas más corta hasta no pasar del máximo.
    let best = 0;
    for (let i = 1; i < lines.length - 1; i++) {
      if (lines[i].length + lines[i + 1].length < lines[best].length + lines[best + 1].length) best = i;
    }
    lines.splice(best, 2, `${lines[best]} ${lines[best + 1]}`);
  }
  return lines.length ? lines : [name];
}

/** Luminancia relativa y contraste WCAG (para pruebas y para elegir el color de texto sobre la paleta). */
export function contrast(a: string, b: string): number {
  const lum = (hex: string) => {
    const [r, g, bl] = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255)
      .map((c) => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4));
    return 0.2126 * r + 0.7152 * g + 0.0722 * bl;
  };
  const [hi, lo] = [lum(a), lum(b)].sort((x, y) => y - x);
  return (hi + 0.05) / (lo + 0.05);
}

/** Color con transparencia a partir de un hexadecimal (#RRGGBB). */
export function alpha(hex: string, opacity: number): string {
  return `${hex}${Math.round(Math.max(0, Math.min(1, opacity)) * 255).toString(16).padStart(2, '0')}`;
}

/** Mezcla lineal de dos colores #RRGGBB (t = 0 → a, t = 1 → b). */
export function mix(a: string, b: string, t: number): string {
  const ch = (hex: string, i: number) => parseInt(hex.slice(i, i + 2), 16);
  return `#${[1, 3, 5].map((i) => Math.round(ch(a, i) + (ch(b, i) - ch(a, i)) * t).toString(16).padStart(2, '0')).join('')}`;
}

/**
 * Superficies oscuras de la ficha teñidas con la paleta del artista: continuidad con el cartel sin pantallas de color
 * brillante. El texto claro de la app mantiene contraste alto sobre todas (comprobado en las pruebas).
 */
export function surfaces(p: Palette, base = '#07060B') {
  return {
    screen: mix(base, p.bg, 0.1),
    raised: mix(base, p.bg, 0.17),
    deep: mix(base, p.bg, 0.05),
    line: mix(base, p.bg, 0.32),
  };
}
