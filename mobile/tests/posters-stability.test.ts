/** Carteles 3.6A: casos reproducidos con los pilotos de Fase 1.4 (SW38, Circoloco) y con respuestas parciales simuladas. */
import assert from 'node:assert/strict';
import { test } from 'node:test';

import {
  applySuggestion, dismissSuggestion, fromExtraction, mergeExtraction, printedIso, removeSet, renameArtist, reviewFlags,
} from '../src/lib/poster-model.ts';
import { applyResolution, type Resolution } from '../src/lib/poster-identity.ts';
import type { PosterEvent, PosterExtraction } from '../src/types/poster.ts';

const NOW = '2026-10-23T20:00:00.000Z';
const LATER = '2026-10-23T21:00:00.000Z';
const INIT = { id: 'p1', now: NOW, fingerprint: 'md5-a', assetId: null, image: { width: 1080, height: 1350, bytes: 200_000 } };

type Session = PosterExtraction['sessions'][number];
const block = (text: string, stage: string, time: string | null, artists: string[]): Session =>
  ({ date: { text, iso: null }, label: null, stage, time, artists });

/** Salida real del piloto compacto de SW38 (Fase 1.4): día y franja en un solo texto, un bloque mezclado y «B2B X» en dos líneas. */
function sw38(over: Partial<PosterExtraction> = {}): PosterExtraction {
  return {
    mode: 'full', complete: true, model: 'qwen/qwen3.8-27b', event_name: 'SW38', dates: [{ text: '3-7 SEPTEMBER 2026', iso: null }],
    location: 'ROQUETAS DE MAR, SPAIN', stages: ['1', '2'], colors: [], artists: [], individual_times: [], uncertain: [],
    unreadable_text: [], review: [], usage: null,
    sessions: [
      block('03.09 THURSDAY NIGHTTIME', '1', '22:00', ['CUKY', 'PERSIC', 'PACO OSUNA', 'MANDA MOOR']),
      block('04.09 FRIDAY DAYTIME', '2', '22:00', ['GAGA', 'DYED SOUNDOROM', 'TRAUMER', 'NU ZAU', 'IGNACIO MORALES', 'SUNIVERSOS', 'COSMINA', 'CRISTIAN MARTLANDED', 'MIN8', 'HERODOT']),
      block('04.09 FRIDAY NIGHTTIME', '1', '22:00', ['GEOSH', 'BLUEZT', 'AJ CHRISTOU', 'MARCO FARAONE']),
      block('04.09 FRIDAY NIGHTTIME', '2', null, ['ION LUDWIG', 'PRIKU', 'PETRE INSPIRESCU', 'GESCU']),
      block('05.09 SATURDAY DAYTIME', '2', null, ['SUBLEE', 'MAKS', 'CALLY', 'ZYA', 'BILA']),
      block('05.09 SATURDAY NIGHTTIME', '1', '22:00', ['JOE VANDITTI', 'MAHONY', 'JAMIE JONES', 'JOSEPH CAPRIATI']),
      block('05.09 SATURDAY NIGHTTIME', '2', null, ['MIHNEA ROG', 'DAN ANDREI', 'RHADOO', 'MAAYAN NIDAM']),
      block('06.09 SUNDAY DAYTIME', '1', null, ['KIDOO', 'ROBER PEINADO', 'GABI', 'SERA DE VILLALTA', 'FELIPE BRAVO', 'SARAGA']),
      block('06.09 SUNDAY DAYTIME', '2', null, ['ALEXIS CABRERA', 'CRISTI CONS', 'GOJNEA76', 'SUCIU', 'SHONKY', 'CHARLIE']),
      block('06.09 SUNDAY NIGHTTIME', '1', null, ['JEAN PIERRE', 'MELANIE RIBBE', 'JOËLLA JACKSON']),
      block('06.09 SUNDAY NIGHTTIME', '2', null, ['MIHIGH', 'CAP', 'CEZAR', 'ANDREI CIUBUC']),
    ],
    b2b: [
      { artists: ['CUKY', 'PERSIC'], text: 'CUKY B2B PERSIC' }, { artists: ['JAMIE JONES', 'JOSEPH CAPRIATI'], text: 'B2B JOSEPH CAPRIATI' },
      { artists: ['ROBER PEINADO', 'GABI'], text: 'ROBER PEINADO B2B GABI' }, { artists: ['SERA DE VILLALTA', 'FELIPE BRAVO'], text: 'B2B FELIPE BRAVO' },
    ],
    ...over,
  };
}

const idOf = (e: PosterEvent, name: string) => e.artists.find((a) => a.name === name)!.id;
const setsOf = (e: PosterEvent, name: string) => e.sets.filter((s) => s.artistIds.includes(idOf(e, name)));

test('SW38 real: 4 días con su franja como bloque, 4 B2B de una sola actuación y sin años ni horas de DJ inventados', () => {
  const e = fromExtraction(sw38(), INIT);
  assert.deepEqual(e.days.map((d) => [d.label, d.date]), [['03.09', null], ['04.09', null], ['05.09', null], ['06.09', null]]);
  assert.equal(e.dateText, '3-7 SEPTEMBER 2026'); // el año de la cabecera se conserva tal cual, sin pasar a los días
  const jj = setsOf(e, 'JAMIE JONES');
  assert.equal(jj.length, 1);
  assert.equal(jj[0].artistIds.length, 2);
  assert.equal(jj[0].block, 'SATURDAY NIGHTTIME');
  assert.deepEqual([jj[0].start, jj[0].timeScope], ['22:00', 'block']);
  assert.equal(e.sets.filter((s) => s.artistIds.length > 1).length, 4);
  assert.equal(e.sets.length, 54 - 4);
  assert.equal(new Set(e.artists.map((a) => a.name)).size, e.artists.length); // cada nombre, una identidad
  // El bloque que mezcló dos franjas (10 artistas) se señala; los normales no.
  const flags = reviewFlags(e);
  assert.deepEqual(setsOf(e, 'GAGA').map((s) => flags.get(s.id)), [['possible_merge']]);
  assert.equal(flags.get(setsOf(e, 'KIDOO')[0].id), undefined);
});

test('un texto de día solo se separa si empieza por una fecha numérica y no hay etiqueta propia', () => {
  const e = fromExtraction(sw38({ sessions: [
    { date: { text: 'SATURDAY 05.09', iso: null }, label: null, stage: null, time: null, artists: ['A'] },
    { date: { text: '06.09', iso: null }, label: 'SUNDAY', stage: null, time: null, artists: ['B'] },
    { date: { text: '07.09.26 OPENING', iso: '2026-09-07' }, label: null, stage: null, time: null, artists: ['C'] },
  ], b2b: [] }), INIT);
  assert.deepEqual(e.days.map((d) => [d.label, d.date]), [['SATURDAY 05.09', null], ['06.09', null], ['07.09.26', '2026-09-07']]);
  assert.deepEqual(e.sets.map((s) => s.block), [null, 'SUNDAY', 'OPENING']);
});

test('año: solo se conserva el impreso en esa fecha (también con dos cifras) y nunca una fecha imposible', () => {
  assert.equal(printedIso('10.09.26', '2026-09-10'), '2026-09-10');
  assert.equal(printedIso('SEPTEMBER 10 2026', '2026-09-10'), '2026-09-10');
  assert.equal(printedIso('03.09', '2026-09-03'), null); // año de la cabecera: no es suyo
  assert.equal(printedIso('IBIZA26', '2026-01-01'), null);
  assert.equal(printedIso('31.02.2026', '2026-02-31'), null);
  // Defensa en el móvil aunque el backend no lo hubiera auditado.
  const e = fromExtraction(sw38({ sessions: [{ date: { text: '03.09', iso: '2026-09-03' }, label: 'THURSDAY', stage: '1', time: null, artists: ['CUKY'] }], b2b: [] }), INIT);
  assert.equal(e.days[0].date, null);
});

test('un B2B con su propia hora impresa la conserva como hora de la actuación, no del bloque', () => {
  const e = fromExtraction(sw38({ individual_times: [{ name: 'CUKY', time: '23:00 - 01:00' }, { name: 'PERSIC', time: '23:00 - 01:00' }] }), INIT);
  const s = setsOf(e, 'CUKY')[0];
  assert.deepEqual([s.artistIds.length, s.start, s.end, s.timeScope, s.endsNextDay], [2, '23:00', '01:00', 'set', true]);
  // Horas distintas para sus miembros: no se elige ninguna, queda la del bloque.
  const odd = fromExtraction(sw38({ individual_times: [{ name: 'CUKY', time: '23:00' }, { name: 'PERSIC', time: '01:00' }] }), INIT);
  assert.deepEqual([setsOf(odd, 'CUKY')[0].start, setsOf(odd, 'CUKY')[0].timeScope], ['22:00', 'block']);
});

test('un colectivo y sus miembros entre paréntesis no se separan solos: se señalan para que decida el usuario', () => {
  // Salida real del piloto de Circoloco: el modelo dejó los miembros como una entrada aparte.
  const e = fromExtraction(sw38({
    event_name: 'CIRCO LOGO NEW YEAR\'S DAY', dates: [{ text: 'NEW YEAR\'S DAY', iso: null }], sessions: [], b2b: [],
    artists: ['[A:RPIA:R]', '(PETRE INSPIRESCU RARESH - RHADOO)', 'ROSSI.', 'CARL CRAIG'].map((name) => ({ name, stage: null, day: null })),
  }), INIT);
  assert.deepEqual(e.artists.map((a) => a.name), ['[A:RPIA:R]', '(PETRE INSPIRESCU RARESH - RHADOO)', 'ROSSI.', 'CARL CRAIG']);
  assert.ok(e.sets.every((s) => s.artistIds.length === 1));
  assert.ok(reviewFlags(e).get(idOf(e, '(PETRE INSPIRESCU RARESH - RHADOO)'))?.includes('collective'));
  assert.equal(reviewFlags(e).get(idOf(e, 'CARL CRAIG')), undefined);
});

test('reanalizar una zona con un B2B cortado no duplica a sus miembros como actuaciones individuales', () => {
  const e = fromExtraction(sw38(), INIT);
  const region = sw38({ mode: 'region', dates: [], stages: [], b2b: [],
    sessions: [block('05.09 SATURDAY NIGHTTIME', '1', null, ['JAMIE JONES', 'MAHONY'])] });
  const m = mergeExtraction(e, region, LATER);
  assert.equal(setsOf(m, 'JAMIE JONES').length, 1);
  assert.equal(setsOf(m, 'MAHONY').length, 1);
  assert.equal(m.sets.length, e.sets.length);
  // Sin contexto (fragmento sin cabecera) tampoco.
  const bare = mergeExtraction(e, sw38({ mode: 'region', dates: [], stages: [], b2b: [], sessions: [],
    artists: [{ name: 'JOSEPH CAPRIATI', stage: null, day: null }] }), LATER);
  assert.equal(setsOf(bare, 'JOSEPH CAPRIATI').length, 1);
});

test('un artista puede tener varias actuaciones legítimas en bloques distintos', () => {
  const e = fromExtraction(sw38(), INIT);
  const m = mergeExtraction(e, sw38({ mode: 'continue', dates: [], b2b: [],
    sessions: [block('07.09 MONDAY CLOSING', '1', null, ['JAMIE JONES'])] }), LATER);
  assert.deepEqual(setsOf(m, 'JAMIE JONES').map((s) => s.artistIds.length), [2, 1]);
});

test('una actuación borrada a mano no vuelve con un reanálisis aunque el artista siga en su B2B', () => {
  // Primera lectura con el B2B sin reconocer: JAMIE JONES suelto y además en el B2B.
  const e = fromExtraction(sw38({ sessions: [
    block('05.09 SATURDAY NIGHTTIME', '1', '22:00', ['JAMIE JONES']),
    block('05.09 SATURDAY NIGHTTIME', '1', '22:00', ['JAMIE JONES B2B JOSEPH CAPRIATI']),
  ], b2b: [] }), INIT);
  const solo = setsOf(e, 'JAMIE JONES').find((s) => s.artistIds.length === 1)!;
  const cleaned = removeSet(e, solo.id, LATER);
  assert.ok(cleaned.artists.some((a) => a.name === 'JAMIE JONES')); // sigue en el B2B
  const again = mergeExtraction(cleaned, sw38({ sessions: [block('05.09 SATURDAY NIGHTTIME', '1', '22:00', ['JAMIE JONES', 'MAHONY'])], b2b: [] }), LATER);
  assert.deepEqual(setsOf(again, 'JAMIE JONES').map((s) => s.artistIds.length), [2]);
  assert.equal(setsOf(again, 'MAHONY').length, 1);
});

test('respuesta cortada dentro de los B2B: queda parcial y la continuación propone unirlos sin reestructurar sola', () => {
  const cut = sw38({ complete: false, b2b: [{ artists: ['CUKY', 'PERSIC'], text: 'CUKY B2B PERSIC' }] });
  const e = fromExtraction(cut, INIT);
  assert.equal(e.status, 'partial');
  assert.equal(setsOf(e, 'JAMIE JONES')[0].artistIds.length, 1); // sin su B2B, cada uno por separado
  const locked = renameArtist(e, idOf(e, 'MAHONY'), 'MAHONY (LIVE)', LATER);
  const cont = mergeExtraction(locked, sw38({ mode: 'continue', sessions: [], dates: [] }), LATER);
  assert.equal(cont.status, 'draft');
  assert.equal(cont.analysis.incomplete, false);
  assert.ok(cont.artists.some((a) => a.name === 'MAHONY (LIVE)') && !cont.artists.some((a) => a.name === 'MAHONY'));
  const b2b = cont.suggestions.filter((s) => s.field === 'b2b');
  assert.equal(b2b.length, 3); // los tres B2B que faltaban, como propuesta
  assert.equal(setsOf(cont, 'JAMIE JONES').length, 1);
  const joined = applySuggestion(cont, b2b.find((s) => s.label.includes('JAMIE JONES'))!.id, LATER);
  assert.deepEqual(setsOf(joined, 'JAMIE JONES').map((s) => s.artistIds.length), [2]);
  assert.equal(joined.sets.length, cont.sets.length - 1);
});

test('un B2B nuevo con solo un miembro ya presente es una propuesta: ni duplica ni deja nombres sueltos', () => {
  const e = fromExtraction(sw38({ sessions: [block('05.09 SATURDAY NIGHTTIME', '1', '22:00', ['JOE VANDITTI', 'JAMIE JONES'])], b2b: [] }), INIT);
  const region = sw38({ mode: 'region', dates: [], stages: [],
    sessions: [block('05.09 SATURDAY NIGHTTIME', '1', null, ['JAMIE JONES', 'JOSEPH CAPRIATI'])],
    b2b: [{ artists: ['JAMIE JONES', 'JOSEPH CAPRIATI'], text: 'B2B JOSEPH CAPRIATI' }] });
  const m = mergeExtraction(e, region, LATER);
  assert.equal(setsOf(m, 'JAMIE JONES').length, 1);
  const s = m.suggestions.find((x) => x.field === 'b2b')!;
  assert.match(s.label, /JAMIE JONES \+ JOSEPH CAPRIATI/);
  const joined = applySuggestion(m, s.id, LATER);
  assert.deepEqual(setsOf(joined, 'JOSEPH CAPRIATI').map((x) => x.artistIds.map((id) => joined.artists.find((a) => a.id === id)!.name)),
    [['JAMIE JONES', 'JOSEPH CAPRIATI']]);
  assert.equal(setsOf(joined, 'JOSEPH CAPRIATI')[0].connector, 'B2B');
  const dismissed = dismissSuggestion(m, s.id, LATER);
  assert.ok(!dismissed.artists.some((a) => a.name === 'JOSEPH CAPRIATI')); // sin actuación ni propuesta: no queda suelto
  assert.ok(dismissed.artists.some((a) => a.name === 'JAMIE JONES'));
});

test('PETER GROCE: el parecido de MusicBrainz es una sugerencia con evidencia y nunca cambia el nombre ni la corrección', () => {
  const e = fromExtraction(sw38({ sessions: [], b2b: [], artists: [{ name: 'PETER GROCE', stage: null, day: null }, { name: '9999999999', stage: null, day: null }] }), INIT);
  const id = idOf(e, 'PETER GROCE');
  const similar: Resolution = {
    name: 'PETER GROCE', status: 'none', mbid: null, canonical: null, source: null,
    evidence: 'Ningún artista de MusicBrainz se llama exactamente así; hay nombres parecidos (¿errata del cartel?)',
    candidates: [{ mbid: 'mb-croce', name: 'Peter Croce', disambiguation: null, type: 'Person', country: null, score: 72, match: 'similar', alias: null, scene: false }],
  };
  const r = applyResolution(e, id, similar);
  const a = r.artists.find((x) => x.id === id)!;
  assert.deepEqual([a.name, a.link.status, a.link.refId, a.link.candidates?.[0].match], ['PETER GROCE', 'none', null, 'similar']);
  assert.match(a.link.evidence ?? '', /parecidos/);
  // Si el usuario lo corrige, una resolución tardía del nombre impreso no lo pisa y un reanálisis no lo resucita.
  const fixed = renameArtist(r, id, 'PETER CROCE', LATER);
  assert.equal(applyResolution(fixed, id, similar), fixed);
  const again = mergeExtraction(fixed, sw38({ sessions: [], b2b: [], artists: [{ name: 'PETER GROCE', stage: null, day: null }] }), LATER);
  assert.deepEqual(again.artists.map((x) => x.name), ['PETER CROCE', '9999999999']);
  // El nombre numérico se señala, no se elimina.
  assert.deepEqual(reviewFlags(again).get(idOf(again, '9999999999')), ['suspicious_name']);
});
