/**
 * Cartel de inicio de TrackDNA (V6.6): edición del día como un flyer. La paleta cambia cada día (las mismas del
 * sistema visual), el número de edición es el día del año y el código de barras del ADN sale de la fecha: estable
 * durante el día, distinto al siguiente. Nada de datos inventados: es decoración, no información de una canción.
 */
import { type ArtistIdentity, fixedIdentity, PALETTES } from './artist-identity.ts';
import { dayIndexOf, localDayKey } from './home-edition.ts';

function dayOfYear(d: Date): number {
  return dayIndexOf(localDayKey(d)) - dayIndexOf(`${d.getFullYear() - 1}-12-31`);
}

export type DailyEdition = { id: ArtistIdentity; issue: string; date: string; bars: number[] };

/** Edición del día: identidad (paleta del día, tipografía Anton), «Nº 299», «26.10.26» y alturas de barra (0,2–1). */
export function dailyEdition(d: Date, barCount = 28): DailyEdition {
  const palette = PALETTES[dayIndexOf(localDayKey(d)) % PALETTES.length];
  const id = fixedIdentity(palette.name, 'anton');
  const pad = (n: number) => String(n).padStart(2, '0');
  // Generador congruencial con la fecha como semilla: el mismo patrón todo el día.
  let s = (dayIndexOf(localDayKey(d)) * 2654435761) >>> 0;
  const bars = Array.from({ length: barCount }, () => {
    s = (Math.imul(s, 1664525) + 1013904223) >>> 0;
    return Math.round((0.2 + (s / 2 ** 32) * 0.8) * 100) / 100;
  });
  return {
    id,
    issue: `Nº ${String(dayOfYear(d)).padStart(3, '0')}`,
    date: `${pad(d.getDate())}.${pad(d.getMonth() + 1)}.${String(d.getFullYear()).slice(2)}`,
    bars,
  };
}

/** Lo que lee una ficha, para la cinta del cartel. Solo lo que TrackDNA muestra de verdad. */
export const TICKER = ['Género', 'BPM', 'Sello', 'Samples', 'Remezclas', 'DJ mixes', 'Edición original', 'Dónde escuchar'];
