/** TrackDNA: «Escuchar» solo con datos reales y artistas enlazados solo por MBID (ADN e historia: track-sheet.test.ts). */
import assert from 'node:assert/strict';
import { test } from 'node:test';

import { creditParts, linkableArtist, linkTarget, listenOptions, releaseLabels, trackFacts } from '../src/lib/format.ts';
import type { Link } from '../src/types/music.ts';

const PAWSA = '11111111-1111-4111-8111-111111111111';
const STEVIE = '22222222-2222-4222-8222-222222222222';
const VARIOUS = '89ad4ac3-39f7-470e-963a-56509c546377';

test('línea de canción solo con datos existentes', () => {
  assert.equal(trackFacts({ first_release_date: '2009-09-22', length_ms: 634467, release_type: 'Album' }), '2009 · 10:34 · Álbum');
  assert.equal(trackFacts({ first_release_date: null, length_ms: null, release_type: null }), '');
});

test('artistas: solo se enlazan con MBID válido; «Various Artists» y nombres sin identidad quedan sin enlace', () => {
  assert.ok(linkableArtist(PAWSA));
  assert.ok(!linkableArtist(VARIOUS) && !linkableArtist('') && !linkableArtist('PAWSA') && !linkableArtist(null));
  const parts = creditParts([
    { mbid: PAWSA, name: 'PAWSA', join_phrase: ' & ' }, { mbid: STEVIE, name: 'Adventures of Stevie V', join_phrase: '' },
  ], 'x');
  assert.deepEqual(parts, [{ name: 'PAWSA', mbid: PAWSA, join: ' & ', guest: false }, { name: 'Adventures of Stevie V', mbid: STEVIE, join: '', guest: false }]);
  assert.deepEqual(creditParts([{ mbid: VARIOUS, name: 'Various Artists', join_phrase: '' }], ''), [{ name: 'Various Artists', mbid: null, join: '', guest: false }]);
  assert.deepEqual(creditParts([], 'Artista sin MBID'), [{ name: 'Artista sin MBID', mbid: null, join: '', guest: false }]);
});

test('artistas invitados: solo los que siguen a «feat.» en el crédito', () => {
  const parts = creditParts([{ mbid: PAWSA, name: 'ANOTR', join_phrase: ' feat. ' }, { mbid: STEVIE, name: 'PAMÉ', join_phrase: '' }], '');
  assert.deepEqual(parts.map((p) => [p.name, p.guest]), [['ANOTR', false], ['PAMÉ', true]]);
  assert.ok(creditParts([{ mbid: PAWSA, name: 'A', join_phrase: ' & ' }, { mbid: STEVIE, name: 'B', join_phrase: '' }], '').every((p) => !p.guest));
});

test('sello y destino de enlaces sin deducir nada', () => {
  assert.deepEqual(releaseLabels({ labels: [], self_released: true }), ['Autoedición']);
  assert.deepEqual(releaseLabels({ labels: [] }), []);
  assert.equal(linkTarget({ target: 'track', release_type: null }), 'Canción');
  assert.equal(linkTarget({ target: 'release', release_type: 'Album' }), 'Álbum');
  assert.equal(linkTarget({}), null);
});

const link = (label: string, url: string, over: Partial<Link> = {}): Link => ({
  url, label, platform: label, kinds: [], detail: null, primary: true, scope: 'release', target: 'release', release_type: 'Single', ...over,
});

test('«Escuchar»: solo Spotify, Apple Music, SoundCloud y Discogs físico; directo antes que búsqueda', () => {
  const links = [
    link('Beatport', 'https://www.beatport.com/release/x/1'), link('Deezer', 'https://www.deezer.com/album/1'),
    link('TIDAL', 'https://tidal.com/album/1'), link('Qobuz', 'https://www.qobuz.com/album/1'),
    link('Spotify', 'https://open.spotify.com/album/1'), link('Spotify', 'https://open.spotify.com/track/2', { target: 'track' }),
    link('iTunes', 'https://itunes.apple.com/album/3', { release_type: 'EP' }),
    link('Discogs', 'https://www.discogs.com/release/9-Dirty-Cash', { formats: ['Digital Media'] }),
  ];
  const out = listenOptions(links, 'PAWSA Dirty Cash');
  assert.deepEqual(out.map((o) => [o.label, o.target, o.direct]), [
    ['Spotify', 'Canción', true], ['Apple Music', 'EP', true], ['SoundCloud', 'Búsqueda', false],
  ]);
  assert.equal(out[0].url, 'https://open.spotify.com/track/2');
  assert.ok(out[2].url.startsWith('https://soundcloud.com/search?q='));
  // Discogs solo con una edición física documentada, y como edición (nunca venta ni disponibilidad).
  const vinyl = listenOptions([link('Discogs', 'https://www.discogs.com/release/9', { formats: ['12" Vinyl'] }),
    link('Discogs', 'https://www.discogs.com/master/8', { formats: ['12" Vinyl'] })], '');
  assert.deepEqual(vinyl.map((o) => [o.label, o.target, o.url]), [['Discogs', 'Edición en vinilo', 'https://www.discogs.com/release/9']]);
  assert.deepEqual(listenOptions([], ''), []);
});
