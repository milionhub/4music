/**
 * Carteles 4 · Hoja de ruta (V6.8): solo con horas impresas por actuación (`timeScope: 'set'`); una hora de bloque no
 * dice cuándo toca cada DJ y nunca se reparte. Lógica pura.
 *
 * - Minutos desde la medianoche del día del evento. En una noche (alguna actuación empieza a partir de las 12:00), las
 *   horas de madrugada (antes de las 08:00) son del día siguiente: 00:00 → 24:00.
 * - Sin hora de fin, una actuación dura hasta la siguiente de su escenario; si no hay siguiente, se marca como abierta.
 * - Ruta propuesta: la combinación sin solapes que más te encaja (selección de intervalos con pesos), por día.
 */
import type { PosterEvent, PosterSet } from '../types/poster.ts';

const NIGHT_FROM = 12 * 60;
const EARLY_UNTIL = 8 * 60;
const OPEN_END = 60;
/** Un hueco de menos de media hora no se anuncia: es ir de un escenario a otro. */
export const GAP_MIN = 30;

export type Slot = { set: PosterSet; day: string; start: number; end: number; endKnown: boolean };
export type Clash = { a: string; b: string; from: number; to: number };
export type RouteItem = { kind: 'set'; slot: Slot } | { kind: 'gap'; from: number; to: number };

const toMin = (hhmm: string) => Number(hhmm.slice(0, 2)) * 60 + Number(hhmm.slice(3, 5));

/** «23:30», «01:30» (las horas de la madrugada siguiente vuelven a 00–07). */
export function clock(min: number): string {
  const m = ((min % 1440) + 1440) % 1440;
  return `${String(Math.floor(m / 60)).padStart(2, '0')}:${String(m % 60).padStart(2, '0')}`;
}

export function timeline(e: PosterEvent): Slot[] {
  const timed = e.sets.filter((s) => s.timeScope === 'set' && s.start && /^\d{2}:\d{2}$/.test(s.start));
  const byDay = new Map<string, PosterSet[]>();
  for (const s of timed) byDay.set(s.dayId ?? '', [...(byDay.get(s.dayId ?? '') ?? []), s]);
  const out: Slot[] = [];
  for (const [day, sets] of byDay) {
    const night = sets.some((s) => toMin(s.start!) >= NIGHT_FROM);
    const startOf = (s: PosterSet) => toMin(s.start!) + (night && toMin(s.start!) < EARLY_UNTIL ? 1440 : 0);
    for (const s of sets) {
      const start = startOf(s);
      let end: number | null = null;
      if (s.end && /^\d{2}:\d{2}$/.test(s.end)) {
        const d = toMin(s.end) - toMin(s.start!);
        end = start + (d <= 0 ? d + 1440 : d);
      } else {
        const next = sets.filter((x) => x.stageId === s.stageId && startOf(x) > start).map(startOf).sort((a, b) => a - b)[0];
        end = next ?? null;
      }
      out.push({ set: s, day, start, end: end ?? start + OPEN_END, endKnown: end !== null });
    }
  }
  return out.sort((a, b) => a.day.localeCompare(b.day) || a.start - b.start || a.set.order - b.set.order);
}

/** Hay hoja de ruta si al menos dos actuaciones tienen su hora impresa. */
export const hasRoute = (slots: Slot[]) => slots.length >= 2;

/** Solapes entre las actuaciones elegidas (mismo día). */
export function clashes(slots: Slot[], ids: readonly string[]): Clash[] {
  const chosen = slots.filter((s) => ids.includes(s.set.id));
  const out: Clash[] = [];
  for (let i = 0; i < chosen.length; i++) {
    for (let j = i + 1; j < chosen.length; j++) {
      const x = chosen[i];
      const y = chosen[j];
      const from = Math.max(x.start, y.start);
      const to = Math.min(x.end, y.end);
      if (x.day === y.day && to > from) out.push({ a: x.set.id, b: y.set.id, from, to });
    }
  }
  return out;
}

/**
 * Ruta sin solapes que suma el mayor peso (por día), viendo a cada artista una sola vez: si la mejor ruta repite a
 * alguien (Prospa en dos escenarios), su segunda actuación deja de contar y se vuelve a calcular.
 */
export function propose(slots: Slot[], weight: (s: PosterSet) => number): string[] {
  const dropped = new Set<string>();
  for (;;) {
    const route = bestRoute(slots, (s) => (dropped.has(s.id) ? 0 : weight(s)));
    const seen = new Set<string>();
    let repeat: string | null = null;
    for (const id of route) {
      const set = slots.find((x) => x.set.id === id)!.set;
      if (set.artistIds.some((a) => seen.has(a))) {
        repeat = id;
        break;
      }
      set.artistIds.forEach((a) => seen.add(a));
    }
    if (!repeat) return route;
    dropped.add(repeat);
  }
}

/** Selección de intervalos con pesos: solo actuaciones con peso > 0; empate: la que acaba antes. */
function bestRoute(slots: Slot[], weight: (s: PosterSet) => number): string[] {
  const out: string[] = [];
  for (const day of new Set(slots.map((s) => s.day))) {
    const xs = slots.filter((s) => s.day === day && weight(s.set) > 0).sort((a, b) => a.end - b.end || a.start - b.start);
    // best[i] = mejor suma usando las i primeras; prev[i] = última compatible antes de la i-ésima.
    const best = [0];
    const take: boolean[] = [];
    const prev = xs.map((x, i) => {
      let k = i - 1;
      while (k >= 0 && xs[k].end > x.start) k--;
      return k;
    });
    xs.forEach((x, i) => {
      const withIt = weight(x.set) + best[prev[i] + 1];
      take[i] = withIt > best[i];
      best.push(take[i] ? withIt : best[i]);
    });
    const picked: string[] = [];
    for (let i = xs.length - 1; i >= 0;) {
      if (take[i]) {
        picked.push(xs[i].set.id);
        i = prev[i];
      } else i--;
    }
    out.push(...picked.reverse());
  }
  return out;
}

/** Tu ruta en orden, con los huecos libres de media hora o más entre una actuación y la siguiente. */
export function routeItems(slots: Slot[], ids: readonly string[]): RouteItem[] {
  const chosen = slots.filter((s) => ids.includes(s.set.id));
  const out: RouteItem[] = [];
  chosen.forEach((slot, i) => {
    const before = chosen[i - 1];
    if (before && before.day === slot.day && slot.start - before.end >= GAP_MIN) out.push({ kind: 'gap', from: before.end, to: slot.start });
    out.push({ kind: 'set', slot });
  });
  return out;
}

/** Actuaciones marcadas que siguen existiendo (una edición puede haber borrado alguna). */
export function planOf(e: PosterEvent): string[] {
  return (e.plan ?? []).filter((id) => e.sets.some((s) => s.id === id));
}

export function togglePlan(e: PosterEvent, setId: string): PosterEvent {
  const plan = planOf(e);
  return { ...e, plan: plan.includes(setId) ? plan.filter((x) => x !== setId) : [...plan, setId] };
}

export function setPlan(e: PosterEvent, ids: string[]): PosterEvent {
  return { ...e, plan: [...new Set(ids)].filter((id) => e.sets.some((s) => s.id === id)) };
}
