/** Carteles 3.1–3.3: B2B, ausencias, correcciones protegidas, recuperación parcial, duplicados y biblioteca. */
import assert from 'node:assert/strict';
import { test } from 'node:test';

import {
  addArtist, applySuggestion, confirmArtist, fromExtraction, groupByDay, joinSets, knownContext, mergeExtraction,
  parseTime, removeArtist, removeSet, renameArtist, reviewFlags, setLabel, splitSet, updateEvent, updateSet, userTime,
} from '../src/lib/poster-model.ts';
import {
  findDuplicate, idsFromKeys, indexEntry, parseIndex, parsePosterEvent, POSTER_INDEX_KEY, posterKey, serializePosterEvent,
  upsertIndex,
} from '../src/lib/poster-store.ts';
import type { PosterEvent, PosterExtraction } from '../src/types/poster.ts';

const NOW = '2026-10-21T20:00:00.000Z';
const LATER = '2026-10-21T21:00:00.000Z';
const INIT = { id: 'p1', now: NOW, fingerprint: 'md5-a', assetId: 'asset-1', image: { width: 1080, height: 1350, bytes: 200_000 } };

function ext(over: Partial<PosterExtraction> = {}): PosterExtraction {
  return {
    mode: 'full', complete: true, model: 'qwen/qwen3.8-27b', event_name: 'SW38', dates: [{ text: '3-7 SEPTEMBER 2026', iso: null }],
    location: null, stages: ['1', '2'], colors: ['#FF2E88', '#07060B'], artists: [], individual_times: [], uncertain: [],
    unreadable_text: [], review: [], usage: null,
    sessions: [
      { date: { text: '03.09', iso: null }, label: 'THURSDAY NIGHTTIME', stage: '1', time: '22:00', artists: ['CUKY', 'PERSIC', 'MIHIGH'] },
      { date: { text: '04.09', iso: null }, label: 'FRIDAY DAYTIME', stage: '2', time: null, artists: ['JAMIE JONES', 'JOSEPH CAPRIATI', 'MIHIGH'] },
    ],
    b2b: [{ artists: ['CUKY', 'PERSIC'], text: 'CUKY B2B PERSIC' }, { artists: ['JAMIE JONES', 'JOSEPH CAPRIATI'], text: 'B2B JOSEPH CAPRIATI' }],
    ...over,
  };
}

const byName = (e: PosterEvent, name: string) => e.artists.find((a) => a.name === name)!;
const setsOf = (e: PosterEvent, name: string) => e.sets.filter((s) => s.artistIds.includes(byName(e, name).id));

test('un B2B es una sola actuación y un artista que repite no duplica su identidad', () => {
  const e = fromExtraction(ext(), INIT);
  assert.equal(e.artists.length, 5);
  assert.equal(e.sets.length, 4);
  const b2b = e.sets.filter((s) => s.artistIds.length === 2);
  assert.deepEqual(b2b.map((s) => setLabel(e, s)), ['CUKY B2B PERSIC', 'JAMIE JONES B2B JOSEPH CAPRIATI']);
  assert.equal(setsOf(e, 'MIHIGH').length, 2); // actúa dos días: dos actuaciones, una identidad
  assert.notEqual(setsOf(e, 'MIHIGH')[0].dayId, setsOf(e, 'MIHIGH')[1].dayId);
  assert.equal(setsOf(e, 'CUKY').length, 1);
});

test('lo ausente es null: sin años, lugar, horas de DJ ni escenarios inventados', () => {
  const e = fromExtraction(ext(), INIT);
  assert.equal(e.location, null);
  assert.ok(e.days.every((d) => d.date === null)); // «03.09» no lleva año impreso
  const night = setsOf(e, 'CUKY')[0];
  assert.equal(night.start, '22:00');
  assert.equal(night.timeScope, 'block'); // hora del bloque, no de cada DJ
  const day = setsOf(e, 'JAMIE JONES')[0];
  assert.equal(day.start, null);
  assert.equal(day.timeScope, null);
  const flat = fromExtraction(ext({ sessions: [], b2b: [], stages: [], artists: [{ name: 'PACO OSUNA', stage: null, day: null }] }), INIT);
  assert.deepEqual([flat.sets[0].dayId, flat.sets[0].stageId, flat.sets[0].start], [null, null, null]);
  assert.equal(flat.days.length, 0);
});

test('un nombre «A B2B B» sin separar y un B2B sin bloque se conservan como una actuación conjunta', () => {
  const e = fromExtraction(ext({ sessions: [], b2b: [{ artists: ['ROBER PEINADO', 'GABI'], text: null }], artists: [{ name: 'SERA DE VILLALTA B2B FELIPE BRAVO', stage: null, day: null }] }), INIT);
  assert.deepEqual(e.sets.map((s) => s.artistIds.length), [2, 2]);
  assert.deepEqual(e.artists.map((a) => a.name), ['SERA DE VILLALTA', 'FELIPE BRAVO', 'ROBER PEINADO', 'GABI']);
});

test('las horas: rangos que cruzan medianoche y entrada del usuario', () => {
  assert.deepEqual(parseTime('22:00 - 06:00'), { start: '22:00', end: '06:00' });
  assert.deepEqual(parseTime('11PM'), { start: '23:00', end: null });
  assert.equal(parseTime('STAGE 2'), null);
  assert.equal(userTime('9:30'), '09:30');
  assert.equal(userTime(''), null);
  assert.equal(userTime('25:00'), undefined);
  const e = fromExtraction(ext(), INIT);
  const s = setsOf(e, 'MIHIGH')[0];
  const next = updateSet(e, s.id, { start: '23:30', end: '02:00' }, LATER);
  const edited = next.sets.find((x) => x.id === s.id)!;
  assert.equal(edited.endsNextDay, true);
  assert.equal(edited.timeScope, 'set');
});

test('un reanálisis no sobrescribe lo editado, no resucita lo eliminado y conserva lo creado a mano', () => {
  let e = fromExtraction(ext(), INIT);
  e = updateEvent(e, { name: 'SW38 Festival' }, LATER);
  e = renameArtist(e, byName(e, 'MIHIGH').id, 'MI HIGH', LATER);
  e = removeArtist(e, byName(e, 'PERSIC').id, LATER);
  e = addArtist(e, 'GEOUSHY', { dayId: null, stageId: null }, LATER);
  const s = setsOf(e, 'JAMIE JONES')[0];
  e = updateSet(e, s.id, { start: '16:00' }, LATER);

  const merged = mergeExtraction(e, ext({ event_name: 'SW38', sessions: [...ext().sessions.map((x) => x.label === 'FRIDAY DAYTIME' ? { ...x, time: '14:00' } : x)] }), LATER);
  assert.equal(merged.name, 'SW38 Festival');
  assert.ok(byName(merged, 'MI HIGH'));
  assert.ok(!merged.artists.some((a) => a.name === 'MIHIGH')); // el nombre leído no vuelve como artista nuevo
  assert.ok(!merged.artists.some((a) => a.name === 'PERSIC'));
  assert.equal(setsOf(merged, 'CUKY')[0].artistIds.length, 1); // el B2B sin PERSIC sigue individual
  assert.ok(byName(merged, 'GEOUSHY'));
  assert.equal(merged.sets.find((x) => x.id === s.id)!.start, '16:00');
  assert.equal(merged.artists.length, e.artists.length);
  assert.equal(merged.sets.length, e.sets.length);
  assert.equal(merged.analysis.calls, 2);
});

test('los datos nuevos incompatibles llegan como sugerencias, nunca se aplican solos', () => {
  const solo = fromExtraction(ext({ b2b: [] }), INIT);
  assert.equal(solo.sets.length, 6);
  const merged = mergeExtraction(solo, ext({ event_name: 'SW 38 ROQUETAS' }), LATER);
  assert.equal(merged.name, 'SW38');
  assert.equal(merged.sets.length, 6); // no se reestructura en B2B automáticamente
  const kinds = merged.suggestions.map((x) => x.field).sort();
  assert.deepEqual(kinds, ['b2b', 'b2b', 'name']);
  const b2b = merged.suggestions.find((x) => x.field === 'b2b')!;
  const applied = applySuggestion(merged, b2b.id, LATER);
  assert.equal(applied.sets.length, 5);
  assert.equal(applied.suggestions.length, 2);
});

test('unir y separar B2B mantiene una sola actuación conjunta y la protege', () => {
  const e = fromExtraction(ext({ b2b: [] }), INIT);
  const ids = [setsOf(e, 'CUKY')[0].id, setsOf(e, 'PERSIC')[0].id];
  const joined = joinSets(e, ids, LATER);
  const b2b = joined.sets.filter((s) => s.artistIds.length === 2);
  assert.equal(b2b.length, 1);
  assert.equal(joined.sets.length, 5);
  assert.ok(b2b[0].meta.locked.includes('artistIds'));
  const split = splitSet(joined, b2b[0].id, LATER);
  assert.equal(split.sets.length, 6);
  assert.ok(split.sets.every((s) => s.artistIds.length === 1));
  const again = mergeExtraction(split, ext(), LATER); // la IA vuelve a proponer el B2B: solo como sugerencia
  assert.equal(again.sets.length, 6);
  assert.ok(again.suggestions.some((x) => x.field === 'b2b'));
});

test('eliminar una actuación descarta a sus artistas sin otras actuaciones', () => {
  const e = fromExtraction(ext(), INIT);
  const r = removeSet(e, setsOf(e, 'CUKY')[0].id, LATER);
  assert.ok(!r.artists.some((a) => a.name === 'CUKY' || a.name === 'PERSIC'));
  assert.ok(r.discarded.includes('cuky'));
  const m = removeSet(e, setsOf(e, 'MIHIGH')[0].id, LATER);
  assert.ok(byName(m, 'MIHIGH')); // sigue actuando otro día
});

test('respuesta cortada: se conserva como parcial y la continuación completa sin duplicar', () => {
  const first = ext({ complete: false, sessions: [ext().sessions[0]], b2b: [] });
  let e = fromExtraction(first, INIT);
  assert.equal(e.status, 'partial');
  assert.equal(e.analysis.incomplete, true);
  const ctx = knownContext(e);
  assert.ok(ctx.known_names.includes('CUKY'));
  assert.ok(ctx.known_sessions[0].includes('THURSDAY NIGHTTIME'));
  e = mergeExtraction(e, ext({ mode: 'continue', sessions: [ext().sessions[1]] }), LATER);
  assert.equal(e.status, 'draft');
  assert.equal(e.analysis.incomplete, false);
  assert.equal(e.artists.length, 5);
  assert.ok(e.suggestions.some((x) => x.field === 'b2b')); // CUKY y PERSIC ya eran individuales
  assert.equal(groupByDay(e).length, 2);
  const region = mergeExtraction({ ...e, analysis: { ...e.analysis, incomplete: true } }, ext({ mode: 'region', complete: true }), LATER);
  assert.equal(region.analysis.incomplete, true); // una zona no cierra un análisis incompleto
});

test('avisos deterministas; lo confirmado deja de señalarse', () => {
  const e = fromExtraction(ext({ sessions: [], b2b: [], uncertain: ['DYED SOUNDOROM'], artists: [
    { name: '5UNIVERSOS', stage: null, day: null }, { name: 'REELow', stage: null, day: null }, { name: 'IBIZA26', stage: null, day: null },
    { name: 'GEOUSHY', stage: null, day: null }, { name: 'GEOUSH', stage: null, day: null }, { name: 'DYED SOUNDOROM', stage: null, day: null },
    { name: '[A:RPIA:R] (PETRE INSPIRESCU RARESH RHADOO)', stage: null, day: null }, { name: 'PACO OSUNA', stage: null, day: null },
  ] }), INIT);
  const f = reviewFlags(e);
  const of = (n: string) => f.get(byName(e, n).id) ?? [];
  assert.ok(of('5UNIVERSOS').includes('odd_spelling'));
  assert.ok(of('REELow').includes('odd_spelling'));
  assert.ok(of('IBIZA26').includes('possible_brand'));
  assert.ok(of('GEOUSHY').includes('similar_name'));
  assert.ok(of('DYED SOUNDOROM').includes('model_uncertain'));
  assert.ok(of('[A:RPIA:R] (PETRE INSPIRESCU RARESH RHADOO)').includes('collective'));
  assert.deepEqual(of('PACO OSUNA'), []);
  const named = fromExtraction(ext({ event_name: 'NOW HERE BY PACO OSUNA', location: 'SCENE JARDÍN BOTÁNICO', sessions: [], b2b: [], stages: [],
    artists: [{ name: 'PACO OSUNA', stage: null, day: null }, { name: 'SCENE', stage: null, day: null }] }), INIT);
  assert.equal(reviewFlags(named).get(byName(named, 'PACO OSUNA').id), undefined); // datos reales de Now Here
  assert.ok(reviewFlags(named).get(byName(named, 'SCENE').id)?.includes('possible_brand'));
  const ok = confirmArtist(e, byName(e, '5UNIVERSOS').id, LATER);
  assert.equal(reviewFlags(ok).get(byName(e, '5UNIVERSOS').id), undefined);
});

test('biblioteca: lectura tolerante, índice sin duplicados y detección del mismo cartel', () => {
  const e = fromExtraction(ext(), INIT);
  assert.deepEqual(parsePosterEvent(serializePosterEvent(e)), e);
  assert.equal(parsePosterEvent('{roto'), null);
  assert.equal(parsePosterEvent(JSON.stringify({ schema: 2, id: 'x' })), null);
  const legacy = JSON.parse(serializePosterEvent(e));
  delete legacy.suggestions;
  delete legacy.discarded;
  assert.deepEqual(parsePosterEvent(JSON.stringify(legacy))!.suggestions, []);

  let index = upsertIndex([], indexEntry(e));
  index = upsertIndex(index, { ...indexEntry(e), updatedAt: LATER, name: 'SW38 editado' });
  assert.equal(index.length, 1);
  assert.equal(index[0].name, 'SW38 editado');
  assert.deepEqual(parseIndex(JSON.stringify(index)), index);
  assert.deepEqual(parseIndex('basura'), []);
  assert.equal(findDuplicate(index, 'md5-a', null)?.id, 'p1');
  assert.equal(findDuplicate(index, null, 'asset-1')?.id, 'p1');
  assert.equal(findDuplicate(index, 'md5-b', 'asset-2'), null);
  assert.equal(findDuplicate(index, null, null), null);
  assert.deepEqual(idsFromKeys([posterKey('p1'), POSTER_INDEX_KEY, 'md.saved_tracks.v1', 'md.preferences.v1']), ['p1']);
  assert.ok(![POSTER_INDEX_KEY, posterKey('p1')].some((k) => k.startsWith('md.saved_tracks') || k.startsWith('md.favorites')));
});
