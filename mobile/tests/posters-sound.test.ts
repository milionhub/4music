/** Carteles 4 · El sonido del cartel (V6.8): reparto de familias y estilo por escenario (lib/poster-sound.ts). */
import assert from 'node:assert/strict';
import { test } from 'node:test';

import { setArtistSound } from '../src/lib/poster-fit.ts';
import { applyResolution } from '../src/lib/poster-identity.ts';
import { fromExtraction } from '../src/lib/poster-model.ts';
import { eventSound } from '../src/lib/poster-sound.ts';
import type { PosterEvent, PosterExtraction } from '../src/types/poster.ts';

const GENRES: Record<string, string[]> = {
  ANOTR: ['House', 'Tech House'], PROSPA: ['Breakbeat'], 'SETH TROXLER': ['House', 'Minimal', 'Tech House'],
  'JIMI JULES': ['House', 'Deep House'], 'DJ TENNIS': ['Techno'], 'JOY ORBISON': ['House'],
};

function closing(classify: string[]): PosterEvent {
  const x: PosterExtraction = {
    mode: 'full', complete: true, model: 'm', event_name: 'closing party', dates: [], location: null,
    stages: ['GARDEN', 'TERRACE', 'MAIN ROOM'], colors: [], uncertain: [], unreadable_text: [], review: [], usage: null, b2b: [],
    sessions: [
      { date: null, label: null, stage: 'GARDEN', time: null, artists: ['ANOTR', 'PROSPA'] },
      { date: null, label: null, stage: 'TERRACE', time: null, artists: ['SETH TROXLER', 'PROSPA', 'TANIA VULCANO'] },
      { date: null, label: null, stage: 'MAIN ROOM', time: null, artists: ['JIMI JULES', 'DJ TENNIS', 'JOY ORBISON'] },
    ],
    artists: [], individual_times: [],
  };
  let e = fromExtraction(x, { id: 'cc', now: 'n', fingerprint: null, assetId: null, image: { width: 1, height: 1, bytes: 1 } });
  for (const a of e.artists) {
    e = applyResolution(e, a.id, { name: a.name, status: 'linked', mbid: `m-${a.name}`, canonical: a.name, candidates: [], evidence: null, source: null });
    if (classify.includes(a.name)) e = setArtistSound(e, a.id, { mbid: `m-${a.name}`, genre: GENRES[a.name], styles: [], labels: [], related: [], at: 'n' });
  }
  return e;
}

test('V6.8: reparto por artista (no por actuación) y estilo dominante por escenario', () => {
  const s = eventSound(closing(Object.keys(GENRES)));
  assert.equal(s.classified, 6);
  assert.equal(s.total, 7, 'Tania Vulcano sin estilos no cuenta, pero sí en el total');
  assert.deepEqual(s.families.map((f) => [f.family, f.count, f.pct]), [['House', 4, 67], ['Breakbeat', 1, 17], ['Techno', 1, 17]]);
  assert.deepEqual(s.families[0].styles, ['Tech House', 'Minimal', 'Deep House'], 'empate: orden del cartel');
  // GARDEN (tech house y breakbeat) y TERRACE no repiten nada; en MAIN ROOM dos de tres son house.
  assert.deepEqual(s.stages.map((g) => [g.name, g.lead]), [['MAIN ROOM', 'House']]);
  assert.deepEqual(s.days, [], 'un solo día: sin reparto por días');
});

test('V6.8: con pocos artistas clasificados no hay reparto que enseñar', () => {
  const s = eventSound(closing(['ANOTR', 'PROSPA']));
  assert.equal(s.classified, 2);
  assert.deepEqual(s.stages, [], 'dos artistas distintos no hacen un «sobre todo»');
});
