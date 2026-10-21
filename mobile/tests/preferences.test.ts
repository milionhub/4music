/** Regresión T1.1 + Guardados v5: bienvenida, artistas de partida y canciones guardadas sobreviven a lecturas y escrituras. */
import assert from 'node:assert/strict';
import { test } from 'node:test';

import {
  EMPTY_PREFERENCES,
  finishOnboarding,
  parseDiscarded,
  parseFavorites,
  parsePreferences,
  parseSavedTracks,
  sameTrack,
  type SavedTrack,
  savedTrackFrom,
  serializeList,
  serializePreferences,
  shouldShowOnboarding,
  toggleFavorite,
  toggleSavedTrack,
} from '../src/lib/preferences.ts';
import type { TrackResponse } from '../src/types/music.ts';

const NOW = '2026-10-16T18:00:00.000Z';

test('terminar u omitir la bienvenida persiste y no vuelve a mostrarse tras releer', () => {
  for (const state of ['completed', 'skipped'] as const) {
    const done = finishOnboarding(EMPTY_PREFERENCES, state, ['Techno', 'Techno', 'House'], NOW);
    const reread = parsePreferences(serializePreferences(done));
    assert.equal(reread.onboarding, state);
    assert.deepEqual(reread.declared_styles, ['Techno', 'House']);
    assert.equal(shouldShowOnboarding(reread), false);
  }
});

test('editar gustos desde Perfil no degrada una bienvenida ya completada', () => {
  const completed = finishOnboarding(EMPTY_PREFERENCES, 'completed', [], NOW);
  assert.equal(finishOnboarding(completed, 'skipped', ['Minimal'], NOW).onboarding, 'completed');
});

test('preferencias ausentes, corruptas o de otra versión: bienvenida pendiente, sin excepción', () => {
  for (const raw of [null, '', '{nope', '[]', '{"version":2,"onboarding":"completed"}', '{"version":1,"onboarding":"x"}']) {
    assert.deepEqual(parsePreferences(raw), EMPTY_PREFERENCES);
  }
});

test('los favoritos guardados por T1 se leen igual (sin migración destructiva) y sin duplicados', () => {
  const t1 = JSON.stringify({
    version: 1,
    items: [
      { kind: 'artist', mbid: 'a', name: 'PAWSA', disambiguation: null, saved_at: NOW },
      { kind: 'artist', mbid: 'b', name: 'Traumer', disambiguation: 'house/techno', saved_at: NOW },
      { kind: 'artist', mbid: 'a', name: 'PAWSA duplicado', disambiguation: null, saved_at: NOW },
      { kind: 'artist', mbid: 'c', saved_at: NOW },
      'basura',
    ],
  });
  const favs = parseFavorites(t1);
  assert.deepEqual(favs.map((f) => f.name), ['PAWSA', 'Traumer']);
  assert.deepEqual(parseFavorites(serializeList(favs)), favs);
  assert.deepEqual(parseFavorites('{rota'), []);
  assert.deepEqual(parseDiscarded(null), []);
});

test('alternar favorito añade al principio y quita sin tocar el resto', () => {
  const base = parseFavorites(serializeList([{ kind: 'artist', mbid: 'a', name: 'A', disambiguation: null, saved_at: NOW }]));
  const added = toggleFavorite(base, { mbid: 'b', name: 'B', disambiguation: null }, NOW);
  assert.deepEqual(added.map((f) => f.mbid), ['b', 'a']);
  assert.deepEqual(toggleFavorite(added, { mbid: 'b', name: 'B', disambiguation: null }, NOW), base);
});

// --- Guardados v5: canciones ---------------------------------------------------------------------------------------

const song = (over: Partial<SavedTrack>): SavedTrack => ({
  kind: 'track', mbid: 'rec-1', title: 'Dirty Cash (Money Talks)', artists: [], artist_name: 'PAWSA & Adventures of Stevie V',
  version: null, cover_url: null, length_ms: 372000, year: '2024', label: null, isrcs: ['GBX1'], saved_at: NOW, ...over,
});

test('guardar y desguardar una canción; persiste tras serializar y releer', () => {
  const saved = toggleSavedTrack([], song({}));
  assert.equal(saved.length, 1);
  assert.deepEqual(parseSavedTracks(serializeList(saved)), saved);
  assert.deepEqual(toggleSavedTrack(saved, song({})), []);
});

test('sin duplicados por título o portada distintos ni por un MBID duplicado con el mismo ISRC; remixes aparte', () => {
  const list = toggleSavedTrack([], song({}));
  assert.ok(sameTrack(list[0], song({ title: 'Dirty Cash', cover_url: 'https://x/otra.jpg' })));
  assert.ok(sameTrack(list[0], song({ mbid: 'rec-duplicada' })), 'misma grabación duplicada en MusicBrainz (ISRC común)');
  const remix = song({ mbid: 'rec-2', version: 'Extended Mix' });
  assert.ok(!sameTrack(list[0], remix), 'un extended mix no es el original aunque comparta ISRC');
  assert.equal(toggleSavedTrack(list, remix).length, 2);
});

test('los favoritos de artistas antiguos no se tocan y los datos dañados no rompen la biblioteca', () => {
  const t1 = JSON.stringify({ version: 1, items: [{ kind: 'artist', mbid: 'a', name: 'PAWSA', disambiguation: null, saved_at: NOW }] });
  assert.deepEqual(parseSavedTracks(t1), []);  // otra clave y otro tipo: no se mezclan
  assert.equal(parseFavorites(t1).length, 1);  // siguen leyéndose igual
  const raw = JSON.stringify({ version: 1, items: [song({}), song({}), { kind: 'track', mbid: 'x' }, 'basura',
    { kind: 'track', mbid: 'old', title: 'Sin campos nuevos', saved_at: NOW }] });
  const parsed = parseSavedTracks(raw);
  assert.deepEqual(parsed.map((t) => t.mbid), ['rec-1', 'old']);
  assert.deepEqual(parsed[1], { ...song({}), mbid: 'old', title: 'Sin campos nuevos', artist_name: '', length_ms: null, year: null, isrcs: [] });
  assert.deepEqual(parseSavedTracks('{rota'), []);
});

test('lo guardado sale de la ficha sin inventar: sello del ADN o del original, año de la fecha', () => {
  const track = {
    mbid: 'rec-1', title: 'Dirty Cash (Money Talks)', artist_name: 'PAWSA & Adventures of Stevie V', version: null, cover_url: null,
    artist_credit: [{ mbid: 'a', name: 'PAWSA', join_phrase: ' & ' }], length_ms: null, first_release_date: '2024-06-14', isrcs: [],
    original_release: null,
    dna: { recording_mbid: 'rec-1', acoustic_analysis: 'unavailable', traits: [
      { key: 'label', group: 'context', label: 'Sello', status: 'verified', scope: 'track', values: ['Solid Grooves Records'], detail: null, sources: [] }] },
  } as unknown as TrackResponse;
  const s = savedTrackFrom(track, NOW);
  assert.equal(s.label, 'Solid Grooves Records');
  assert.equal(s.year, '2024');
  assert.equal(s.length_ms, null);
  assert.deepEqual(s.artists, [{ mbid: 'a', name: 'PAWSA', join_phrase: ' & ' }]);
});
