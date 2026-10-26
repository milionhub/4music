/** Carteles 4 · Para ti (V6.8): qué artistas del cartel te encajan y por qué (lib/poster-fit.ts). */
import assert from 'node:assert/strict';
import { test } from 'node:test';

import { eventFits, fitReasons, setArtistSound, soundOf, soundProgress, type Taste } from '../src/lib/poster-fit.ts';
import { applyResolution, type Resolution } from '../src/lib/poster-identity.ts';
import { fromExtraction } from '../src/lib/poster-model.ts';
import { parsePosterEvent, serializePosterEvent } from '../src/lib/poster-store.ts';
import type { SavedTrack } from '../src/lib/preferences.ts';
import type { ArtistSound, PosterEvent, PosterExtraction } from '../src/types/poster.ts';

const NOW = '2026-10-26T20:00:00.000Z';
const INIT = { id: 'cc', now: NOW, fingerprint: 'md5-c', assetId: null, image: { width: 1179, height: 1419, bytes: 94_346 } };

function closing(): PosterEvent {
  const x: PosterExtraction = {
    mode: 'full', complete: true, model: 'm', event_name: 'closing party', dates: [{ text: '14TH OCTOBER 2024', iso: '2024-10-14' }],
    location: null, stages: ['GARDEN', 'TERRACE'], colors: [], uncertain: [], unreadable_text: [], review: [], usage: null, b2b: [],
    sessions: [
      { date: null, label: null, stage: 'GARDEN', time: null, artists: ['ANOTR', 'PROSPA'] },
      { date: null, label: null, stage: 'TERRACE', time: null, artists: ['CHRIS STUSSY', 'LUCIANO', 'DIXON'] },
    ],
    artists: [], individual_times: [],
  };
  let e = fromExtraction(x, INIT);
  for (const name of ['ANOTR', 'PROSPA', 'CHRIS STUSSY', 'LUCIANO', 'DIXON']) {
    const a = e.artists.find((y) => y.name === name)!;
    const r: Resolution = { name, status: 'linked', mbid: `mbid-${name}`, canonical: name, candidates: [], evidence: null, source: null };
    e = applyResolution(e, a.id, r);
  }
  return e;
}

const sound = (mbid: string, over: Partial<ArtistSound> = {}): ArtistSound =>
  ({ mbid, genre: [], styles: [], labels: [], related: [], at: NOW, ...over });
const saved = (title: string, artist: string, mbid: string, label: string | null = null): SavedTrack => ({
  kind: 'track', mbid: title, title, artists: [{ mbid, name: artist, join_phrase: '' }], artist_name: artist, version: null,
  cover_url: null, length_ms: null, year: null, label, isrcs: [], saved_at: NOW,
});
const id = (e: PosterEvent, name: string) => e.artists.find((a) => a.name === name)!.id;

const TASTE: Taste = {
  favorites: [{ mbid: 'mbid-LUCIANO', name: 'Luciano' }],
  saved: [saved('Crazy', 'ANOTR', 'mbid-ANOTR'), saved('Dirty Cash', 'PAWSA', 'mbid-pawsa', 'Solid Grooves Records')],
  styles: ['Tech House', 'Drum & Bass'],
};

test('V6.8: motivos comprobables, del que más encaja al que menos', () => {
  let e = closing();
  e = setArtistSound(e, id(e, 'CHRIS STUSSY'), sound('mbid-CHRIS STUSSY', { related: ['PAWSA', 'Chris Stussy'], labels: ['Solid Grooves Records'] }));
  e = setArtistSound(e, id(e, 'DIXON'), sound('mbid-DIXON', { genre: ['House', 'Deep House'] }));
  e = setArtistSound(e, id(e, 'PROSPA'), sound('mbid-PROSPA', { genre: ['House', 'Tech House'] }));
  const fits = eventFits(e, TASTE);
  assert.deepEqual(fits.map((f) => [f.artist.name, f.reasons.map((r) => r.kind)]), [
    ['ANOTR', ['saved']],
    ['CHRIS STUSSY', ['related', 'label']], // 3 + 2: empata con Luciano y desempata el orden del cartel
    ['LUCIANO', ['favorite']],
    ['PROSPA', ['style']],
  ]);
  const chris = fits[1].reasons.map((r) => r.text);
  assert.deepEqual(chris, ['Deezer lo relaciona con PAWSA', 'Publica en Solid Grooves Records, como «Dirty Cash»']);
  assert.equal(fits[0].reasons[0].text, 'Tienes guardada «Crazy»');
  assert.equal(fits[3].reasons[0].text, 'Tech House, uno de tus estilos');
  assert.equal(fits[0].sets.length, 1, 'con su actuación, para la hora y el escenario');
  assert.deepEqual(soundProgress(e), { done: 3, total: 5 });
});

test('V6.8: el sonido vale solo para su identidad y sobrevive al guardado', () => {
  let e = closing();
  const dixon = id(e, 'DIXON');
  assert.equal(setArtistSound(e, dixon, sound('otra-identidad')), e, 'no se guarda el sonido de otra identidad');
  e = setArtistSound(e, dixon, sound('mbid-DIXON', { genre: ['House', 'Deep House'] }));
  const a = e.artists.find((x) => x.id === dixon)!;
  assert.deepEqual(a.styles, ['House', 'Deep House'], 'sin estilos del perfil, el género alimenta el filtro');
  const back = parsePosterEvent(serializePosterEvent(e))!;
  assert.deepEqual(soundOf(back.artists.find((x) => x.id === dixon)!)?.genre, ['House', 'Deep House']);
  const broken = JSON.parse(serializePosterEvent(e));
  broken.artists.find((x: { id: string }) => x.id === dixon).sound = { mbid: 1 };
  assert.equal(parsePosterEvent(JSON.stringify(broken))!.artists.find((x) => x.id === dixon)!.sound, undefined);
  // Sin gustos, nadie encaja (nunca se rellena).
  assert.deepEqual(fitReasons(a, { favorites: [], saved: [], styles: [] }), []);
});
