/** Carteles 3.1–3.4: B2B, ausencias, correcciones protegidas, recuperación parcial, duplicados y biblioteca. */
import assert from 'node:assert/strict';
import { test } from 'node:test';

import {
  addArtist, applySuggestion, confirmArtist, fromExtraction, groupByDay, joinSets, knownContext, mergeExtraction,
  parseTime, removeArtist, removeSet, renameArtist, reviewFlags, setLabel, splitSet, suspiciousName, updateEvent, updateSet, userTime,
} from '../src/lib/poster-model.ts';
import {
  type ApiCandidate, applyResolution, chooseIdentity, leaveUnidentified, linkedMbid, parseLink, resetIdentity, type Resolution,
  resolutionQueue,
} from '../src/lib/poster-identity.ts';
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

// --- 3.4: identidad de artistas -------------------------------------------------------------------------------------

const res = (name: string, over: Partial<Resolution> = {}): Resolution => ({
  name, status: 'linked', mbid: `mbid-${name}`, canonical: name, candidates: [], evidence: 'Nombre exacto', source: null, ...over,
});
const cand = (mbid: string, name: string, match: ApiCandidate['match'] = 'name'): ApiCandidate => ({
  mbid, name, disambiguation: null, type: null, country: null, score: 100, match, alias: null, scene: false,
});

test('nombres sospechosos: avisa de 9999999999 sin señalar nombres reales con cifras o símbolos', () => {
  for (const bad of ['9999999999', '+44 7911 123456 0', '***', '-- // --', 'Tickets on sale now at the venue box office and online stores']) {
    assert.equal(suspiciousName(bad), true, bad);
  }
  for (const ok of ['999999999', 'Future.666', '808 State', 'Âme', '2562', '&ME', 'DJ Stingray 313', 'Kyle Hall', 'Byron the Aquarius']) {
    assert.equal(suspiciousName(ok), false, ok);
  }
  const e = fromExtraction(ext({ b2b: [], sessions: [{ date: null, label: null, stage: null, time: null, artists: ['9999999999', '999999999'] }] }), INIT);
  const flags = reviewFlags(e);
  assert.ok(flags.get(byName(e, '9999999999').id)?.includes('suspicious_name'));
  assert.ok(!flags.get(byName(e, '999999999').id)?.includes('suspicious_name'));
  // Es un aviso: el nombre sigue en el evento y, confirmado a mano, deja de señalarse.
  assert.equal(reviewFlags(confirmArtist(e, byName(e, '9999999999').id, LATER)).get(byName(e, '9999999999').id), undefined);
});

test('resolución: exacta enlaza, homónimos quedan ambiguos y un fallo deja el artista pendiente', () => {
  const e = fromExtraction(ext(), INIT);
  const cuky = byName(e, 'CUKY').id, persic = byName(e, 'PERSIC').id, mihigh = byName(e, 'MIHIGH').id;
  let next = applyResolution(e, cuky, res('CUKY'));
  next = applyResolution(next, persic, res('PERSIC', { status: 'ambiguous', mbid: null, canonical: null, candidates: [cand('a', 'Persic'), cand('b', 'Persic')] }));
  next = applyResolution(next, mihigh, res('MIHIGH', { status: 'error', mbid: null }));
  assert.deepEqual(linkedMbid(byName(next, 'CUKY')), 'mbid-CUKY');
  assert.equal(byName(next, 'PERSIC').link.status, 'ambiguous');
  assert.equal(linkedMbid(byName(next, 'PERSIC')), null);
  assert.equal(byName(next, 'PERSIC').link.candidates?.length, 2);
  assert.equal(byName(next, 'MIHIGH').link.status, 'pending');
  assert.equal(next.updatedAt, e.updatedAt); // resolver no es una edición del usuario
  // Una respuesta para un nombre que cambió mientras tanto no se aplica.
  const renamed = renameArtist(e, cuky, 'CUKY OTRO', LATER);
  assert.equal(applyResolution(renamed, cuky, res('CUKY')).artists.find((a) => a.id === cuky)?.link.status, 'pending');
});

test('B2B: una sola actuación y cada artista con su identidad; el abierto se resuelve primero', () => {
  const e = fromExtraction(ext(), INIT);
  const b2b = e.sets.find((s) => s.artistIds.length === 2 && s.artistIds.includes(byName(e, 'CUKY').id))!;
  const queue = resolutionQueue(e, [byName(e, 'PERSIC').id]);
  assert.equal(queue[0], byName(e, 'PERSIC').id);
  assert.equal(new Set(queue).size, e.artists.length);
  let next = applyResolution(e, b2b.artistIds[0], res('CUKY'));
  next = applyResolution(next, b2b.artistIds[1], res('PERSIC'));
  assert.equal(next.sets.length, e.sets.length);
  assert.deepEqual(next.sets.find((s) => s.id === b2b.id)?.artistIds, b2b.artistIds);
  assert.deepEqual(b2b.artistIds.map((id) => linkedMbid(next.artists.find((a) => a.id === id)!)), ['mbid-CUKY', 'mbid-PERSIC']);
  assert.ok(!next.artists.some((a) => /b2b/i.test(a.name)));
  assert.deepEqual(resolutionQueue(next), resolutionQueue(e).filter((id) => !b2b.artistIds.includes(id)));
});

test('identidad elegida a mano: se guarda, sobrevive a reabrir y ninguna resolución la pisa', () => {
  const e = fromExtraction(ext(), INIT);
  const id = byName(e, 'PERSIC').id;
  const chosen = chooseIdentity(e, id, { refId: 'mb-b', name: 'Persic', disambiguation: 'techno DJ', match: 'manual' }, LATER);
  const reopened = parsePosterEvent(serializePosterEvent(chosen))!;
  const a = reopened.artists.find((x) => x.id === id)!;
  assert.equal(linkedMbid(a), 'mb-b');
  assert.equal(a.link.origin, 'user');
  assert.equal(reopened.updatedAt, LATER);
  assert.equal(applyResolution(reopened, id, res('PERSIC', { mbid: 'otro' })).artists.find((x) => x.id === id)?.link.refId, 'mb-b');
  assert.ok(!resolutionQueue(reopened).includes(id));
  // Renombrar no borra lo elegido; un reanálisis tampoco.
  assert.equal(renameArtist(reopened, id, 'PERSIC (live)', LATER).artists.find((x) => x.id === id)?.link.refId, 'mb-b');
  assert.equal(mergeExtraction(reopened, ext(), LATER).artists.find((x) => x.id === id)?.link.refId, 'mb-b');
  // Dejarlo sin identificar también se respeta, y se puede volver a la identificación automática.
  const none = leaveUnidentified(reopened, id, LATER);
  assert.equal(none.artists.find((x) => x.id === id)?.link.status, 'none');
  assert.ok(!resolutionQueue(none).includes(id));
  assert.ok(resolutionQueue(resetIdentity(none, id, LATER)).includes(id));
});

test('un enlace automático se vuelve a resolver si el usuario corrige el nombre', () => {
  const e = fromExtraction(ext(), INIT);
  const id = byName(e, 'CUKY').id;
  const linked = applyResolution(e, id, res('CUKY'));
  assert.equal(renameArtist(linked, id, 'Cuky', LATER).artists.find((a) => a.id === id)?.link.status, 'linked'); // misma clave
  assert.equal(renameArtist(linked, id, 'CUKI', LATER).artists.find((a) => a.id === id)?.link.status, 'pending');
});

test('eventos guardados en 3.3 y enlaces dañados se leen como pendientes', () => {
  const e = fromExtraction(ext(), INIT);
  const raw = JSON.parse(serializePosterEvent(e));
  raw.artists[0].link = { status: 'pending', catalog: null, refId: null }; // forma de 3.3
  raw.artists[1].link = { status: 'linked', catalog: 'musicbrainz', refId: null }; // enlazado sin id
  raw.artists[2].link = 'roto';
  delete raw.artists[3].link;
  const back = parsePosterEvent(JSON.stringify(raw))!;
  assert.deepEqual(back.artists.slice(0, 4).map((a) => a.link.status), ['pending', 'pending', 'pending', 'pending']);
  assert.equal(parseLink({ status: 'linked', catalog: 'musicbrainz', refId: 'x', origin: 'user' }).origin, 'user');
});
