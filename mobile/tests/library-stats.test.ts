/** V6.7: lo que dice tu biblioteca en Guardados y Perfil (lib/library-stats.ts). */
import assert from 'node:assert/strict';
import { test } from 'node:test';

import { libraryStats, sortSaved, totalTime, yearSpan } from '../src/lib/library-stats.ts';
import type { SavedTrack } from '../src/lib/preferences.ts';

const saved = (title: string, artist: string, over: Partial<SavedTrack> = {}): SavedTrack => ({
  kind: 'track', mbid: title, title, artists: [{ mbid: artist, name: artist, join_phrase: '' }], artist_name: artist, version: null,
  cover_url: null, length_ms: null, year: null, label: null, isrcs: [], saved_at: '2026-10-01T00:00:00Z', ...over,
});

const LIB = [
  saved('Dirty Cash', 'PAWSA', { length_ms: 400000, year: '2023', label: 'Solid Grooves Records', saved_at: '2026-10-03T00:00:00Z' }),
  saved('Ride On Me', 'PAWSA', { length_ms: 229845, year: '2026', label: 'Solid Grooves Records', saved_at: '2026-10-05T00:00:00Z' }),
  saved('Strings of Life', 'Rhythim Is Rhythim', { length_ms: 443000, year: '1987', label: 'Transmat', saved_at: '2026-10-02T00:00:00Z' }),
  saved('álbum sin datos', 'X'),
];

test('V6.7: cifras de la biblioteca solo con lo que consta, y solo lo que se repite', () => {
  const s = libraryStats(LIB);
  assert.equal(s.count, 4);
  assert.equal(s.timed, 3);
  assert.equal(totalTime(s.totalMs), '18 min');
  assert.equal(yearSpan(s.years), '1987–2026');
  assert.deepEqual(s.artists, [{ name: 'PAWSA', count: 2 }]);
  assert.deepEqual(s.labels, [{ name: 'Solid Grooves Records', count: 2 }], 'un sello con una sola canción no es «tu sello»');
  assert.equal(totalTime(0), null);
  assert.equal(totalTime(2 * 3600000 + 41 * 60000), '2 h 41 min');
  assert.equal(yearSpan(libraryStats([LIB[0]]).years), '2023');
  assert.equal(yearSpan(libraryStats([]).years), null);
});

test('V6.7: orden de Guardados', () => {
  assert.deepEqual(sortSaved(LIB, 'recent').map((t) => t.title), ['Ride On Me', 'Dirty Cash', 'Strings of Life', 'álbum sin datos']);
  assert.deepEqual(sortSaved(LIB, 'az').map((t) => t.title), ['álbum sin datos', 'Dirty Cash', 'Ride On Me', 'Strings of Life']);
  assert.deepEqual(sortSaved(LIB, 'year').map((t) => t.title), ['Strings of Life', 'Dirty Cash', 'Ride On Me', 'álbum sin datos']);
});
