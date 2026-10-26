/** Carteles 4 · Hoja de ruta (V6.8): horas de la noche, solapes, ruta propuesta y huecos (lib/poster-route.ts). */
import assert from 'node:assert/strict';
import { test } from 'node:test';

import { fromExtraction } from '../src/lib/poster-model.ts';
import { clashes, clock, hasRoute, planOf, propose, routeItems, setPlan, timeline, togglePlan } from '../src/lib/poster-route.ts';
import { parsePosterEvent, serializePosterEvent } from '../src/lib/poster-store.ts';
import type { PosterEvent, PosterExtraction } from '../src/types/poster.ts';

/** Cartel 05 (Circoloco closing 2024), recortado: tres escenarios, horas por actuación que cruzan la medianoche. */
const LINEUP: [string, string, string][] = [
  ['GARDEN', 'ANOTR', '20:00 - 22:00'], ['GARDEN', 'PROSPA', '22:00 - 23:00'],
  ['TERRACE', 'CHRIS STUSSY', '20:30 - 22:30'], ['TERRACE', 'LUCIANO', '22:30 - 00:00'], ['TERRACE', 'PROSPA', '02:00 - 03:00'],
  ['TERRACE', 'SETH TROXLER', '04:30 - 07:00'],
  ['MAIN ROOM', 'IVAN SMAGGHE', '22:00 - 23:30'], ['MAIN ROOM', 'BEDOUIN', '23:30 - 01:30'], ['MAIN ROOM', 'JOY ORBISON', '01:30 - 03:00'],
];

function closing(): PosterEvent {
  const stages = ['GARDEN', 'TERRACE', 'MAIN ROOM'];
  const x: PosterExtraction = {
    mode: 'full', complete: true, model: 'm', event_name: 'closing party', dates: [{ text: '14TH OCTOBER 2024', iso: '2024-10-14' }],
    location: null, stages, colors: [], uncertain: [], unreadable_text: [], review: [], usage: null, b2b: [], artists: [],
    sessions: stages.map((st) => ({ date: null, label: null, stage: st, time: null, artists: LINEUP.filter((l) => l[0] === st).map((l) => l[1]) })),
    individual_times: LINEUP.map(([, name, time]) => ({ name, time })),
  };
  return fromExtraction(x, { id: 'cc', now: 'n', fingerprint: null, assetId: null, image: { width: 1, height: 1, bytes: 1 } });
}
const setOf = (e: PosterEvent, name: string, nth = 0) =>
  e.sets.filter((s) => s.artistIds.some((id) => e.artists.find((a) => a.id === id)!.name === name))[nth].id;

test('V6.8: la madrugada es del día siguiente y una actuación termina pasada la medianoche', () => {
  const e = closing();
  const slots = timeline(e);
  assert.ok(hasRoute(slots));
  const by = (name: string, nth = 0) => slots.find((s) => s.set.id === setOf(e, name, nth))!;
  assert.deepEqual([by('LUCIANO').start, by('LUCIANO').end], [22 * 60 + 30, 24 * 60]);
  assert.deepEqual([by('PROSPA', 1).start, by('PROSPA', 1).end], [26 * 60, 27 * 60], '02:00 de la misma noche');
  assert.equal(clock(by('SETH TROXLER').end), '07:00');
  assert.equal(slots[0].set.id, setOf(e, 'ANOTR'), 'en orden de la noche');
});

test('V6.8: solapes entre lo que marcas y ruta propuesta sin solapes', () => {
  const e = closing();
  const slots = timeline(e);
  const marked = [setOf(e, 'ANOTR'), setOf(e, 'CHRIS STUSSY'), setOf(e, 'JOY ORBISON')];
  assert.deepEqual(clashes(slots, marked).map((c) => [clock(c.from), clock(c.to)]), [['20:30', '22:00']], 'ANOTR y Chris Stussy');
  // Pesos de «Para ti»: ANOTR 11, Chris 5, Prospa 3 (dos actuaciones), Luciano 5.
  const W: Record<string, number> = { ANOTR: 11, 'CHRIS STUSSY': 5, PROSPA: 3, LUCIANO: 5 };
  const weight = (s: { artistIds: string[] }) => Math.max(0, ...s.artistIds.map((id) => W[e.artists.find((a) => a.id === id)!.name] ?? 0));
  const route = propose(slots, weight);
  const names = route.map((id) => e.artists.find((a) => a.id === e.sets.find((s) => s.id === id)!.artistIds[0])!.name);
  assert.deepEqual(names, ['ANOTR', 'LUCIANO', 'PROSPA'], 'ANOTR gana a Chris; Luciano tapa a Prospa en Garden; Prospa a las 02:00');
  // Sin Luciano, Prospa podría entrar dos veces (Garden y Terrace): se le ve una sola.
  const once = propose(slots, (s) => (s.artistIds.some((id) => e.artists.find((a) => a.id === id)!.name === 'LUCIANO') ? 0 : weight(s)));
  assert.equal(once.filter((id) => e.sets.find((s) => s.id === id)!.artistIds.some((a) => e.artists.find((x) => x.id === a)!.name === 'PROSPA')).length, 1);
  assert.deepEqual(clashes(slots, route), []);
  const items = routeItems(slots, route);
  assert.deepEqual(items.map((i) => (i.kind === 'gap' ? `libre ${clock(i.from)}–${clock(i.to)}` : clock(i.slot.start))),
    ['20:00', 'libre 22:00–22:30', '22:30', 'libre 00:00–02:00', '02:00']);
});

test('V6.8: lo que marcas se guarda, sobrevive al guardado y olvida actuaciones borradas', () => {
  let e = closing();
  e = togglePlan(e, setOf(e, 'ANOTR'));
  e = togglePlan(e, setOf(e, 'BEDOUIN'));
  e = togglePlan(e, setOf(e, 'ANOTR'));
  assert.deepEqual(planOf(e), [setOf(e, 'BEDOUIN')]);
  const back = parsePosterEvent(serializePosterEvent(setPlan(e, [setOf(e, 'JOY ORBISON'), 'borrada'])))!;
  assert.deepEqual(planOf(back), [setOf(e, 'JOY ORBISON')]);
  assert.equal(parsePosterEvent(JSON.stringify({ ...JSON.parse(serializePosterEvent(e)), plan: 'x' }))!.plan, undefined);
});

test('V6.8: sin horas por actuación no hay hoja de ruta (una hora de bloque no se reparte)', () => {
  const e = closing();
  const blocks = { ...e, sets: e.sets.map((s) => ({ ...s, timeScope: 'block' as const })) };
  assert.equal(hasRoute(timeline(blocks)), false);
});
