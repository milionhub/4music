/** V5.4: qué muestra la ficha TrackDNA (lib/track-sheet.ts), con los cinco casos de referencia y datos vacíos. */
import assert from 'node:assert/strict';
import { test } from 'node:test';

import { uniqueBy, withUniqueKeys } from '../src/lib/format.ts';
import { hasDna, plainTitle, trackArtists, trackDna, trackStory, trackVersions, versionClass } from '../src/lib/track-sheet.ts';
import type { DnaTrait, TrackLink, TrackRelations, TrackRelease, TrackResponse } from '../src/types/music.ts';

const MB = (n: number) => `${String(n).padStart(8, '0')}-0000-4000-8000-000000000000`;
const NO_RELATIONS: TrackRelations = { remix_of: [], remixes: [], remix_count: 0, dj_mix_count: 0, dj_mixes: [], samples: [], sampled_by: [], mashups: [] };
const trait = (key: string, status: DnaTrait['status'], values: string[], scope: DnaTrait['scope'] = 'track'): DnaTrait => ({
  key, group: 'context', label: key, status, scope, values, detail: null, sources: [],
});
const link = (n: number, title: string, artist_name: string, length_ms: number | null = null): TrackLink => ({ mbid: MB(n), title, artist_name, length_ms });
const release = (over: Partial<TrackRelease>): TrackRelease => ({
  mbid: 'rg', title: 'x', primary_type: 'Single', secondary_types: [], date: null, labels: [], catalog_number: null, formats: [],
  own: true, self_released: false, cover_url: null, url: 'https://musicbrainz.org/release-group/rg', ...over,
});

type Sheet = Pick<TrackResponse, 'mbid' | 'title' | 'version' | 'artist_name' | 'artist_credit' | 'credits' | 'relations' | 'dna' | 'length_ms' | 'original_release'>;
const track = (over: Partial<Sheet> & { traits?: DnaTrait[] }): Sheet => ({
  mbid: MB(1), title: 'Song', version: null, artist_name: 'Artist', artist_credit: [{ mbid: MB(900), name: over.artist_name ?? 'Artist', join_phrase: '' }],
  credits: [], relations: NO_RELATIONS, length_ms: null, original_release: null,
  dna: { recording_mbid: MB(1), traits: over.traits ?? [], acoustic_analysis: 'unavailable' }, ...over,
});

// --- Casos de referencia (datos reales de la caché del backend, recortados) ----------------------------------------
const HOODLUM = track({
  title: 'Hoodlum (original mix)', version: 'Original mix', artist_name: 'Traumer', length_ms: 415000,
  original_release: release({ title: 'Dedust', primary_type: 'EP', labels: ['Desolat'] }),
  relations: { ...NO_RELATIONS, dj_mix_count: 2 },
  traits: [trait('genre', 'community', ['House']), trait('label', 'verified', ['Desolat']), trait('bpm', 'measured', ['123']),
    trait('key', 'measured', ['Sol# menor', '1A'])],
});
const LOVELEE = track({
  title: 'Lovelee Dae', artist_name: 'Blaze', length_ms: 456000,
  credits: [{ role: 'Autoría', artists: [{ mbid: MB(10), name: 'Kevin Hedge', sort_name: null, disambiguation: null, type: null, country: null, area: null, begin_date: null }] }],
  original_release: release({ title: 'Lovelee Dae', labels: ['Urban Tracks', 'Classic'] }),
  relations: { ...NO_RELATIONS, remixes: [link(2, 'Lovelee Dae (Seth Troxler remix)', 'Blaze')], remix_count: 1, dj_mix_count: 2,
    mashups: [link(3, 'Lovelee Dae (Riso & Matthijs Wentink bootleg)', 'Blaze vs. Dennis Ferrer')] },
  traits: [trait('genre', 'community', ['House', 'Deep House'], 'release'), trait('artist_style', 'community', ['Garage House'], 'artist'),
    trait('label', 'verified', ['Urban Tracks', 'Classic', 'Substance']), trait('bpm', 'measured', ['124'])],
});
const DOUBLE_C = track({
  title: 'DOUBLE C', artist_name: 'PAWSA', length_ms: 227000,
  credits: [{ role: 'Producción', artists: [{ mbid: MB(900), name: 'PAWSA', sort_name: null, disambiguation: null, type: null, country: null, area: null, begin_date: null }] }],
  original_release: release({ title: 'F1 The Album', primary_type: 'Album', secondary_types: ['Soundtrack'], labels: ['Atlantic'], own: false }),
  traits: [trait('genre', 'community', ['Pop'], 'release'), trait('artist_style', 'community', ['tech house'], 'artist')],
});
const person = (n: number, name: string) => ({ mbid: MB(n), name, sort_name: null, disambiguation: null, type: null, country: null, area: null, begin_date: null });
const MSBWY = track({
  title: 'Music Sounds Better With You (12” club mix)', version: '12” club mix', artist_name: 'Stardust', length_ms: 409800,
  artist_credit: [{ mbid: MB(900), name: 'Stardust', join_phrase: '' }],
  credits: [{ role: 'Producción', artists: [person(20, 'Thomas Bangalter')] }, { role: 'Composición', artists: [person(20, 'Thomas Bangalter'), person(21, 'Benjamin Diamond')] },
    { role: 'Voz', artists: [person(21, 'Benjamin Diamond')] }, { role: 'Programación', artists: [person(900, 'Stardust')] }],
  original_release: release({ title: 'Music Sounds Better With You', labels: ['Virgin', 'Roulé'] }),
  relations: { ...NO_RELATIONS, remix_count: 10,
    remixes: [link(4, 'Music Sounds Better With You (radio edit)', 'Stardust'), link(5, 'Music Sounds Better With You (32 on Red dubmix)', 'Stardust'),
      link(6, 'Music Sounds Better With You (Anthem From Paris)', 'Stardust'), link(7, 'Music Sounds Better With You (Bob Sinclar remix)', 'Stardust'),
      link(8, 'Music Sounds Better With You (Château Flight remix)', 'Stardust'), link(9, 'Music Sounds Better With You (Another remix)', 'Stardust')],
    samples: [link(11, 'Fate', 'Chaka Khan')], sampled_by: [link(12, 'Music Sounds Better With U', 'Big Time Rush feat. Mann')],
    mashups: [link(13, 'Neverender Sounds Better With Stardust (Justice vs. Stardust)', 'Party Ben')] },
  traits: [trait('genre', 'community', ['House', 'Electro', 'French House']), trait('label', 'verified', ['Virgin', 'Roulé', 'Virgin France S.A.']),
    trait('bpm', 'measured', ['124']), trait('key', 'measured', ['Sib menor', '3A'])],
});
const DESIRE = track({ title: 'Desire', artist_name: 'Chris Stussy', length_ms: 172000, original_release: release({ title: 'Desire' }),
  traits: [trait('genre', 'unavailable', []), trait('label', 'unavailable', []), trait('bpm', 'unavailable', [])] });

test('Hoodlum: ADN completo con BPM y tonalidad estimados, Camelot integrado, sin historia ni versiones de relleno', () => {
  const d = trackDna(HOODLUM);
  assert.deepEqual(d.genre, { family: 'House', styles: [], note: null });
  assert.deepEqual(d.bpm, { value: '123', note: 'estimado' });
  assert.deepEqual(d.key, { value: 'Sol# menor', camelot: '1A', note: 'estimado' });
  assert.deepEqual(d.rows.map((r) => [r.label, r.value]), [['Duración', '6:55'], ['Sello', 'Desolat'], ['Formato', 'EP'], ['Versión', 'Original']]);
  assert.equal(trackStory(HOODLUM), null, 'pertenecer a un EP o salir en DJ mixes no es una historia');
  assert.deepEqual(trackVersions(HOODLUM), []);
});

test('Lovelee Dae: House con Deep House del lanzamiento, BPM estimado, un remix y ningún mashup ni bootleg', () => {
  const d = trackDna(LOVELEE);
  assert.deepEqual(d.genre, { family: 'House', styles: ['Deep House'], note: 'del lanzamiento' });
  assert.deepEqual(d.bpm, { value: '124', note: 'estimado' });
  assert.equal(d.key, null);
  assert.equal(d.rows.find((r) => r.key === 'label')?.value, 'Urban Tracks · Classic');
  assert.ok(!JSON.stringify(d).includes('Garage House'), 'el estilo del artista no es ADN de la canción');
  assert.deepEqual(trackVersions(LOVELEE).map((v) => [v.kind, v.item.title]), [['Remix', 'Lovelee Dae (Seth Troxler remix)']]);
  assert.equal(trackStory(LOVELEE), null);
  assert.deepEqual(trackArtists(LOVELEE).map((a) => [a.name, a.role]), [['Blaze', 'Artista principal']], 'autoría no es un artista del tema');
});

test('Double C: el género de la banda sonora no es el del track y F1 The Album no es una historia', () => {
  const d = trackDna(DOUBLE_C);
  assert.equal(d.genre, null);
  assert.deepEqual(d.rows.map((r) => [r.label, r.value]), [['Duración', '3:47'], ['Formato', 'Álbum · Banda sonora']]);
  assert.equal(trackStory(DOUBLE_C), null, 'producida por quien la firma: nada singular que contar');
  assert.deepEqual(trackArtists(DOUBLE_C).map((a) => a.name), ['PAWSA']);
});

test('Music Sounds Better With You: sample como historia, un solo artista y solo dos remixes con firma', () => {
  const d = trackDna(MSBWY);
  assert.deepEqual([d.genre?.family, d.genre?.styles, d.bpm?.value, d.key?.value, d.key?.camelot], ['House', ['Electro', 'French House'], '124', 'Sib menor', '3A']);
  assert.equal(d.rows.find((r) => r.key === 'version')?.value, 'Extended');
  const story = trackStory(MSBWY)!;
  assert.equal(story.key, 'sample');
  assert.equal(story.mbid, MB(11));
  assert.equal(story.text, '«Music Sounds Better With You» toma un sample de «Fate», de Chaka Khan. Abre su ficha para escuchar de dónde sale.');
  const words = story.text.split(/\s+/).length;
  assert.ok(words <= 55, `${words} palabras`);
  assert.deepEqual(trackArtists(MSBWY).map((a) => [a.name, a.role]), [['Stardust', 'Artista principal']], 'sin créditos técnicos');
  // Es ya la versión larga: no se ofrece otra extended; radio edit, dub y versiones sin firma quedan fuera; máximo dos.
  assert.deepEqual(trackVersions(MSBWY).map((v) => [v.kind, v.item.title]), [
    ['Remix', 'Music Sounds Better With You (Bob Sinclar remix)'], ['Remix', 'Music Sounds Better With You (Château Flight remix)']]);
});

test('Desire: cobertura limitada, sin inventar nada; la ficha se compone con lo que hay', () => {
  const d = trackDna(DESIRE);
  assert.deepEqual(d, { genre: null, bpm: null, key: null, rows: [{ key: 'length', label: 'Duración', value: '2:52' }, { key: 'format', label: 'Formato', value: 'Single' }] });
  assert.ok(hasDna(d));
  assert.equal(trackStory(DESIRE), null);
  assert.deepEqual(trackVersions(DESIRE), []);
});

test('datos vacíos: ningún bloque con relleno', () => {
  const empty = track({ artist_credit: [], artist_name: '' });
  assert.ok(!hasDna(trackDna(empty)));
  assert.equal(trackStory(empty), null);
  assert.deepEqual(trackVersions(empty), []);
  assert.deepEqual(trackArtists(empty), []);
});

test('versiones: extended de la misma canción, original si esta es un remix, nada no oficial ni repetido', () => {
  const t = track({ title: 'Crazy', relations: { ...NO_RELATIONS, remixes: [
    link(2, 'Crazy (Extended Mix)', 'ANOTR'), link(3, 'Other Song (Extended Mix)', 'ANOTR'), link(4, 'Crazy (Extended Mix)', 'ANOTR'),
    link(5, 'Crazy (DJ X bootleg)', 'ANOTR'), link(6, 'Crazy (Y remix)', 'ANOTR vs. Y'), link(7, 'Crazy (Z remix)', 'ANOTR'), link(1, 'Crazy (Z remix)', 'ANOTR')] } });
  assert.deepEqual(trackVersions(t).map((v) => [v.kind, v.item.mbid]), [['Extended', MB(2)], ['Remix', MB(7)]]);
  const remix = track({ title: 'Crazy (Z remix)', version: 'Z remix', relations: { ...NO_RELATIONS, remix_of: [link(9, 'Crazy', 'ANOTR')] } });
  assert.deepEqual(trackVersions(remix).map((v) => [v.kind, v.item.mbid]), [['Original', MB(9)]]);
  assert.deepEqual(['Crazy', 'Crazy (Original Mix)', 'Crazy (Extended Mix)', 'Crazy (12" club mix)', 'Crazy (Radio Edit)', 'Crazy (Z remix)', 'Crazy (Z bootleg)', 'Crazy (Dub)']
    .map((title) => versionClass({ title })), ['original', 'original', 'extended', 'extended', 'edit', 'remix', 'unofficial', 'other']);
  assert.equal(plainTitle('Hoodlum (original mix)'), 'Hoodlum');
  assert.equal(plainTitle('Dirty Cash (Money Talks)'), 'Dirty Cash (Money Talks)');
});

test('historia: un solo hecho y por orden de interés (sample > versión de una obra > producción > sampleada después)', () => {
  const producer = track({ title: 'X', artist_name: 'Alias', credits: [{ role: 'Producción', artists: [person(30, 'Real Name')] }],
    relations: { ...NO_RELATIONS, sampled_by: [link(5, 'Later', 'DJ Y')] } });
  assert.equal(trackStory(producer)?.key, 'producer');
  assert.equal(trackStory({ ...producer, credits: [] })?.key, 'sampled');
  assert.equal(trackStory({ ...producer, relations: { ...NO_RELATIONS, cover_of: 'Obra', cover_writers: ['A', 'B'] } })?.text,
    '«X» es una versión de «Obra», obra escrita por A y B.');
  assert.equal(trackStory({ ...producer, credits: [], relations: { ...NO_RELATIONS, sampled_by: [link(6, 'Mash (bootleg)', 'Z')] } }), null);
});

test('artistas: cada uno una vez, invitados y remezclador solo si esta grabación es un remix', () => {
  const t = track({
    title: 'Crazy (Z remix)', version: 'Z remix', artist_name: 'ANOTR feat. PAMÉ & ANOTR',
    artist_credit: [{ mbid: MB(1), name: 'ANOTR', join_phrase: ' feat. ' }, { mbid: MB(2), name: 'PAMÉ', join_phrase: ' & ' }, { mbid: MB(1), name: 'ANOTR', join_phrase: '' }],
    credits: [{ role: 'Remezcla', artists: [person(3, 'Z')] }, { role: 'Producción', artists: [person(4, 'P')] }],
  });
  assert.deepEqual(trackArtists(t).map((a) => [a.name, a.role]), [['ANOTR', 'Artista principal'], ['PAMÉ', 'Artista invitado'], ['Z', 'Remezcla']]);
  assert.equal(new Set(trackArtists(t).map((a) => a.key)).size, 3, 'claves únicas para React');
  assert.deepEqual(trackArtists({ ...t, title: 'Crazy', version: null }).map((a) => a.name), ['ANOTR', 'PAMÉ']);
});

test('claves de listas: uniqueBy quita duplicados reales y withUniqueKeys nunca repite clave', () => {
  const items = [{ url: 'a' }, { url: 'b' }, { url: 'a' }];
  assert.deepEqual(uniqueBy(items, (x) => x.url).map((x) => x.url), ['a', 'b']);
  assert.deepEqual(withUniqueKeys(items, (x) => x.url).map((x) => x.key), ['a', 'b', 'a#1']);
});
