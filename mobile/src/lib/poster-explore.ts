/**
 * Carteles 3.5: explorador del line-up. Lógica pura (filtros, filas y etiquetas), probada en tests/posters.test.ts.
 *
 * Reglas: se filtran actuaciones (un B2B es una sola fila, nunca se duplica); el orden es el del cartel (`order`),
 * nunca alfabético; un filtro solo aparece si separa algo (2 o más opciones con datos); las horas de bloque no son
 * horas de cada artista y no cuentan para el filtro de horario; lo que no tiene día solo aparece en «Todos».
 */
import { groupByDay } from './poster-model.ts';
import type { PosterArtist, PosterEvent, PosterSet } from '../types/poster.ts';

export type TimeBand = 'day' | 'night' | 'late';
export const TIME_BAND_LABEL: Record<TimeBand, string> = { day: 'Día (6–18 h)', night: 'Noche (18–24 h)', late: 'Madrugada (0–6 h)' };
const BAND_ORDER: TimeBand[] = ['day', 'night', 'late'];

export type ExploreFilter = { day: string | null; stage: string | null; band: TimeBand | null; style: string | null };
export const NO_FILTER: ExploreFilter = { day: null, stage: null, band: null, style: null };

export type Facets = {
  days: { id: string; label: string; count: number }[];
  stages: { id: string; label: string; count: number }[];
  bands: { id: TimeBand; label: string; count: number }[];
  styles: { id: string; label: string; count: number }[];
};

/** Franja de una actuación solo con hora propia impresa (`timeScope: 'set'`). */
export function timeBand(s: PosterSet): TimeBand | null {
  if (s.timeScope !== 'set' || !s.start) return null;
  const h = Number(s.start.slice(0, 2));
  if (!Number.isFinite(h)) return null;
  return h < 6 ? 'late' : h < 18 ? 'day' : 'night';
}

/** Estilos documentados de un artista (copiados de su perfil al abrir la vista rápida). */
export function artistStyles(a: PosterArtist | undefined): string[] {
  return Array.isArray(a?.styles) ? a.styles.filter((x): x is string => typeof x === 'string' && !!x) : [];
}

function setStyles(e: PosterEvent, s: PosterSet): Set<string> {
  return new Set(s.artistIds.flatMap((id) => artistStyles(e.artists.find((a) => a.id === id)).map((x) => x.toLowerCase())));
}

function count<K extends string>(sets: PosterSet[], keyOf: (s: PosterSet) => K | K[] | null): Map<K, number> {
  const out = new Map<K, number>();
  for (const s of sets) {
    const k = keyOf(s);
    for (const x of k === null ? [] : Array.isArray(k) ? k : [k]) out.set(x, (out.get(x) ?? 0) + 1);
  }
  return out;
}

/** Opciones de cada filtro con datos reales; un filtro con menos de 2 opciones no se muestra (lista vacía). */
export function facets(e: PosterEvent): Facets {
  const days = count(e.sets, (s) => s.dayId);
  const stages = count(e.sets, (s) => s.stageId);
  const bands = count(e.sets, timeBand);
  const styles = count(e.sets, (s) => [...setStyles(e, s)]);
  const labels = new Map<string, string>();
  for (const a of e.artists) for (const st of artistStyles(a)) if (!labels.has(st.toLowerCase())) labels.set(st.toLowerCase(), st);
  const two = <T,>(xs: T[]) => (xs.length >= 2 ? xs : []);
  const shared = [...styles].filter(([, n]) => n >= 2).sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0])).slice(0, 8);
  // Un estilo filtra si lo comparten 2 o más actuaciones y separa algo (no las cubre todas, o hay más de uno).
  const styleList = shared.length >= 2 || (shared.length === 1 && shared[0][1] < e.sets.length) ? shared : [];
  return {
    days: two([...e.days].sort((a, b) => a.order - b.order).filter((d) => days.has(d.id)).map((d) => ({ id: d.id, label: d.label, count: days.get(d.id)! }))),
    stages: two(e.stages.filter((st) => stages.has(st.id)).map((st) => ({ id: st.id, label: st.name, count: stages.get(st.id)! }))),
    bands: two(BAND_ORDER.filter((b) => bands.has(b)).map((b) => ({ id: b, label: TIME_BAND_LABEL[b], count: bands.get(b)! }))),
    // Orden: el estilo más frecuente primero, como máximo 8.
    styles: styleList.map(([k, n]) => ({ id: k, label: labels.get(k) ?? k, count: n })),
  };
}

/** Quita del filtro los valores que ya no existen (p. ej., tras editar el evento). */
export function validFilter(f: ExploreFilter, fx: Facets): ExploreFilter {
  return {
    day: fx.days.some((x) => x.id === f.day) ? f.day : null,
    stage: fx.stages.some((x) => x.id === f.stage) ? f.stage : null,
    band: fx.bands.some((x) => x.id === f.band) ? f.band : null,
    style: fx.styles.some((x) => x.id === f.style) ? f.style : null,
  };
}

export function filterSets(e: PosterEvent, f: ExploreFilter): PosterSet[] {
  return [...e.sets].sort((a, b) => a.order - b.order).filter((s) =>
    (f.day === null || s.dayId === f.day)
    && (f.stage === null || s.stageId === f.stage)
    && (f.band === null || timeBand(s) === f.band)
    && (f.style === null || setStyles(e, s).has(f.style)));
}

export type ExploreRow =
  | { kind: 'day'; key: string; label: string; count: number }
  | { kind: 'set'; key: string; set: PosterSet };

/** Filas del explorador: con «Todos» y varios días, agrupadas por día (lo que no tiene día, al final). */
export function exploreRows(e: PosterEvent, f: ExploreFilter): ExploreRow[] {
  const sets = filterSets(e, f);
  const keep = new Set(sets.map((s) => s.id));
  const multiDay = facets(e).days.length > 0;
  if (f.day !== null || !multiDay) return sets.map((s) => ({ kind: 'set', key: s.id, set: s }));
  return groupByDay(e).flatMap((g) => {
    const rows = g.sets.filter((s) => keep.has(s.id)).sort((a, b) => a.order - b.order);
    if (!rows.length) return [];
    return [
      { kind: 'day' as const, key: `day:${g.day?.id ?? 'none'}`, label: g.day?.label ?? 'Sin día confirmado', count: rows.length },
      ...rows.map((s) => ({ kind: 'set' as const, key: s.id, set: s })),
    ];
  });
}

/** Hora tal como se puede afirmar: la propia del artista, o la del bloque dicha como tal. Nunca una hora deducida. */
export function timeLabel(s: PosterSet): string | null {
  if (!s.start) return null;
  const range = s.end ? `${s.start}–${s.end}` : s.start;
  return s.timeScope === 'block' ? `Bloque ${s.end ? range : `desde ${s.start}`}` : range;
}

/** Resumen del line-up para la portada: solo recuentos de lo que hay. */
export function lineupSummary(e: PosterEvent): string[] {
  const used = (ids: (string | null)[]) => new Set(ids.filter(Boolean)).size;
  const days = used(e.sets.map((s) => s.dayId));
  const stages = used(e.sets.map((s) => s.stageId));
  const b2b = e.sets.filter((s) => s.artistIds.length > 1).length;
  return [
    `${e.artists.length} ${e.artists.length === 1 ? 'artista' : 'artistas'}`,
    days > 1 ? `${days} días` : null,
    stages > 1 ? `${stages} escenarios` : null,
    b2b ? `${b2b} B2B` : null,
  ].filter((x): x is string => !!x);
}
