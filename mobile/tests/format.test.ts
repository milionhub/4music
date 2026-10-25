/** Regresión T1.1: claves únicas en listas, enlaces sin duplicados y datos ausentes sin texto inventado. */
import assert from 'node:assert/strict';
import { test } from 'node:test';

import { artistFacts, duration, identityFacts, formatCount, sceneFacts, platformSearchUrl, releaseKind, sectionMessage, splitLinks, withUniqueKeys } from '../src/lib/format.ts';
import type { Link, SectionStatus } from '../src/types/music.ts';

const link = (url: string, label: string, primary: boolean): Link => ({ url, label, platform: primary ? label : null, kinds: [], detail: null, primary });

test('claves únicas aunque la fuente repita valores (caso Qobuz duplicado en Cloonee)', () => {
  const keys = withUniqueKeys(['q', 'x', 'q', 'q'], (v) => v).map((k) => k.key);
  assert.deepEqual(keys, ['q', 'x', 'q#1', 'q#2']);
  assert.equal(new Set(keys).size, keys.length);
  assert.equal(withUniqueKeys([''], (v) => v)[0].key, 'item');
});

test('enlaces: separa plataformas destacadas y elimina URL repetidas', () => {
  const { primary, more } = splitLinks([
    link('https://open.spotify.com/artist/1', 'Spotify', true),
    link('https://open.spotify.com/artist/1/', 'Spotify', true),
    link('https://www.instagram.com/x', 'Instagram', false),
  ]);
  assert.deepEqual(primary.map((l) => l.label), ['Spotify']);
  assert.deepEqual(more.map((l) => l.label), ['Instagram']);
});

test('datos ausentes: sin «undefined», «null» ni campos inventados', () => {
  assert.equal(artistFacts({ type: null, country: null, area: null, begin_date: null }), '');
  assert.equal(artistFacts({ type: 'Person', country: 'GB', area: 'London', begin_date: null }), 'Person · London (GB)');
  assert.equal(artistFacts({ type: null, country: 'BE', area: 'BE', begin_date: '1990' }), 'BE · desde 1990');
  assert.equal(duration(null), null);
  assert.equal(duration(301000), '5:01');
  assert.equal(releaseKind({ primary_type: null, secondary_types: [] }), null);
  assert.equal(releaseKind({ primary_type: 'Single', secondary_types: ['Remix'] }), 'Single · Remezclas');
});

test('secciones: distingue vacío (sin datos), error temporal y formato inesperado', () => {
  const s = (status: SectionStatus['status'], error_code: string | null = null): SectionStatus => ({ status, error_code, total: null, skipped: 0, source: null });
  assert.equal(sectionMessage(s('ok'), 'lanzamientos'), null);
  assert.deepEqual(sectionMessage(s('empty'), 'lanzamientos')?.retry, false);
  assert.match(sectionMessage(s('error', 'provider_unavailable'), 'grabaciones')!.text, /temporal/);
  assert.equal(sectionMessage(s('error', 'provider_unavailable'), 'grabaciones')!.retry, true);
  assert.match(sectionMessage(s('error', 'provider_bad_response'), 'grabaciones')!.text, /formato inesperado/);
});

test('canciones sin URL verificada: solo búsqueda en la plataforma, nunca un enlace exacto inventado', () => {
  const url = platformSearchUrl('spotify', 'Dirty Cash (Money Talks) PAWSA');
  assert.equal(url, 'https://open.spotify.com/search/Dirty%20Cash%20(Money%20Talks)%20PAWSA');
  assert.doesNotMatch(url, /\/track\//);
  assert.equal(platformSearchUrl('soundcloud', 'a b'), 'https://soundcloud.com/search?q=a%20b');
});

test('recuentos de ListenBrainz en formato compacto sin inventar precisión', () => {
  assert.deepEqual([950, 1000, 1234, 9999, 15400].map(formatCount), ['950', '1 K', '1,2 K', '10 K', '15 K']);
});

test('identidad: país legible, nacimiento y formación sin confundirse; nacimiento nunca como «desde»', () => {
  const none = { country_name: null, area: null, origin: null, origin_kind: null, formed_year: null, active_since: null } as const;
  assert.equal(identityFacts({ type: null, country: 'GB' }, { ...none, country_name: 'Reino Unido' }), 'Reino Unido');
  assert.equal(identityFacts({ type: 'Person', country: 'GB' },
    { ...none, area: 'Manchester', country_name: 'Reino Unido', origin: 'Salford', origin_kind: 'birth', active_since: '2012' }),
    'Manchester, Reino Unido · Nacimiento: Salford · En activo desde 2012');
  assert.equal(identityFacts({ type: 'Group', country: 'DE' },
    { ...none, area: 'Berlin', origin: 'Hamburg', origin_kind: 'formation', formed_year: '2004', active_since: '2004' }),
    'Grupo · Berlin, DE · Formación: Hamburg, 2004');
  assert.equal(identityFacts({ type: 'Person', country: null }, none), '');
  assert.equal(identityFacts({ type: null, country: 'BE' }, undefined), 'BE'); // respuesta antigua sin identidad
});

test('sellos fundados, proyectos e integrantes: solo los documentados, una línea por tipo', () => {
  const none = { country_name: null, area: null, origin: null, origin_kind: null, formed_year: null, active_since: null } as const;
  assert.deepEqual(sceneFacts({ ...none, founded_labels: ['Hot Creations'], projects: ['Hot Natured'], members: [] }),
    ['Sello fundado: Hot Creations', 'Proyectos: Hot Natured']);
  assert.deepEqual(sceneFacts({ ...none, founded_labels: ['Zenit', 'Question'] }), ['Sellos fundados: Zenit, Question']);
  assert.deepEqual(sceneFacts(none), []); // respuesta antigua sin estos campos
  assert.deepEqual(sceneFacts(undefined), []);
});

test('V6: «Escuchar» del artista solo con Spotify, Apple Music, SoundCloud y Discogs; búsqueda marcada si falta', async () => {
  const { artistPlatforms } = await import('../src/lib/format.ts');
  const link = (label: string, url: string) => ({ url, label, platform: label, kinds: [], detail: 'Streaming', primary: true });
  const out = artistPlatforms([link('Beatport', 'https://www.beatport.com/artist/x/1'), link('Spotify', 'https://open.spotify.com/artist/abc'),
    link('Discogs', 'https://www.discogs.com/artist/6362')], 'Luciano');
  assert.deepEqual(out.map((l) => [l.label, l.detail]), [['Spotify', null], ['Apple Music', 'Búsqueda'], ['SoundCloud', 'Búsqueda'], ['Discogs', null]]);
  assert.equal(out[0].url, 'https://open.spotify.com/artist/abc');
  assert.equal(out[1].url, 'https://music.apple.com/search?term=Luciano');
  assert.deepEqual(artistPlatforms([], '  '), []);
});
