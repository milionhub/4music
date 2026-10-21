/** Inicio V6: edición diaria estable y variada, selección editorial válida y Tu frecuencia explicable y sin duplicados. */
import assert from 'node:assert/strict';
import { test } from 'node:test';

import { contrast, fitSize } from '../src/lib/artist-identity.ts';
import { EDITORIAL_PICKS } from '../src/lib/home-catalog.ts';
import { COVER_SURFACE, dayIndexOf, editionFor, fitLines, HEADLINES, LAYOUTS, localDayKey } from '../src/lib/home-edition.ts';
import {
  behindFact, dailySlots, formatsEs, frequency, FREQUENCY_LOOKUPS, isRealCover, mainArtist, radarFact, releaseFact, songFamily, soundFacts,
  versionClass,
} from '../src/lib/home-picks.ts';
import type { SavedTrack } from '../src/lib/preferences.ts';
import { ART_PALETTES, TRIOS } from '../src/lib/track-art.ts';
import type { TrackLink, TrackRelease, TrackResponse } from '../src/types/music.ts';

const MBID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
const days = (from: string, n: number) => Array.from({ length: n }, (_, i) => {
  const d = new Date(`${from}T12:00:00`);
  d.setDate(d.getDate() + i);
  return localDayKey(d);
});

const link = (mbid: string, title: string, artist_name: string): TrackLink => ({ mbid, title, artist_name, length_ms: null });
const uuid = (n: number) => `00000000-0000-4000-8000-${String(n).padStart(12, '0')}`;

function track(over: Partial<TrackResponse> & { mbid: string; title: string }): TrackResponse {
  return {
    artist_credit: [], artist_name: 'Artista', main_artist: null, length_ms: 300000, first_release_date: '1999', disambiguation: null,
    video: false, version: null, isrcs: [], cover_url: null, cover_release_mbid: null, original_release: null, releases: [], release_count: 0,
    releases_status: { status: 'ok', error_code: null, total: 0, skipped: 0, source: null }, credits: [],
    relations: { remix_of: [], remixes: [], remix_count: 0, dj_mix_count: 0, dj_mixes: [], samples: [], sampled_by: [], mashups: [] },
    links: [], identifiers: null, dna: { recording_mbid: over.mbid, traits: [], acoustic_analysis: 'unavailable' }, interpretation: null,
    interpretation_status: 'unavailable', sources: [], source: { provider: 'musicbrainz', url: '', fetched_at: '', license: 'CC0', stale: false },
    ...over,
  };
}

function saved(mbid: string, title: string, artist: string, extra: Partial<SavedTrack> = {}): SavedTrack {
  return { kind: 'track', mbid, title, artists: [], artist_name: artist, version: null, cover_url: null, length_ms: null, year: null,
    label: null, isrcs: [], saved_at: '2026-10-20T10:00:00Z', ...extra };
}

const genre = (values: string[]) => ({ key: 'genre', group: 'classification' as const, label: 'Género', status: 'community' as const,
  scope: 'track' as const, values, detail: null, sources: [] });

// --- Edición diaria -----------------------------------------------------------------------------------------------
test('la edición es estable durante el día (cualquier hora) y depende de la fecha local', () => {
  assert.equal(localDayKey(new Date(2026, 9, 20, 0, 1)), '2026-10-20');
  assert.equal(localDayKey(new Date(2026, 9, 20, 23, 59)), '2026-10-20');
  assert.deepEqual(editionFor('2026-10-20'), editionFor('2026-10-20'));
  assert.equal(dayIndexOf('2026-10-21') - dayIndexOf('2026-10-20'), 1);
  assert.equal(dayIndexOf('2026-03-30') - dayIndexOf('2026-03-29'), 1); // cambio de hora: sin saltos
  assert.equal(editionFor('2026-10-20').dateLabel, 'martes 20 oct');
});

test('dos días seguidos nunca repiten composición, paleta, pareja tipográfica, titular ni encabezados', () => {
  const eds = days('2026-01-01', 400).map(editionFor);
  for (let i = 1; i < eds.length; i++) {
    const [a, b] = [eds[i - 1], eds[i]];
    assert.notEqual(a.layout, b.layout, b.key);
    assert.notEqual(a.palette.name, b.palette.name, b.key);
    assert.notEqual(a.trio.key, b.trio.key, b.key);
    assert.notEqual(a.headline.word, b.headline.word, b.key);
    assert.notEqual(a.head, b.head, b.key);
  }
  // En pocos días aparecen todas las opciones (ciclos completos).
  const week = eds.slice(0, 11);
  assert.equal(new Set(week.slice(0, 5).map((e) => e.layout)).size, LAYOUTS.length);
  assert.equal(new Set(week.slice(0, 8).map((e) => e.palette.name)).size, ART_PALETTES.length);
  assert.equal(new Set(week.slice(0, 6).map((e) => e.trio.key)).size, TRIOS.length);
  assert.equal(new Set(week.map((e) => e.headline.word)).size, HEADLINES.length);
  assert.ok(new Set(eds.map((e) => `${e.layout}|${e.palette.name}|${e.trio.key}|${e.headline.word}`)).size > 300);
});

test('las secciones alternan superficie y la primera no se pega a la portada', () => {
  for (const key of days('2026-01-01', 120)) {
    const e = editionFor(key);
    assert.notEqual(e.rhythm[0], COVER_SURFACE[e.layout], key);
    assert.notEqual(e.rhythm[0], e.rhythm[1], key);
    assert.notEqual(e.rhythm[1], e.rhythm[2], key);
  }
});

test('los titulares caben en un iPhone pequeño con todas las tipografías, sin bajar del mínimo legible', () => {
  const inner = 320 - 32;
  assert.deepEqual(fitLines('de madrugada', 400, TRIOS[0].voice, 54).lines, ['de madrugada']); // corta: una línea
  for (const h of HEADLINES) {
    assert.ok(h.word.length <= 8 && h.voice.length <= 16, `${h.word} ${h.voice}: titular breve`);
    for (const trio of TRIOS) {
      const word = trio.title.upper ? h.word.toUpperCase() : h.word;
      assert.ok(fitSize(word, inner, trio.title, 230, 1) >= 34, `${h.word} en ${trio.title.family}`);
      const voice = trio.voice.upper ? h.voice.toUpperCase() : h.voice;
      // La frase de contraste se reparte en líneas si así gana cuerpo (Syne, Rubik: muy anchas).
      const fitted = fitLines(voice, inner, trio.voice, 54);
      assert.ok(fitted.size >= 22 && fitted.lines.length <= 3, `${h.voice} en ${trio.voice.family}: ${fitted.size}`);
      assert.equal(fitted.lines.join(' '), voice);
    }
  }
});

test('contraste: la tinta de cada superficie de la edición es legible (texto normal ≥ 4,5:1)', () => {
  for (const p of ART_PALETTES) {
    for (const k of ['hero', 'alt', 'paper', 'night'] as const) {
      assert.ok(contrast(p[k].ink, p[k].bg) >= 4.5, `${p.name} ${k}`);
      assert.ok(contrast(p[k].soft, p[k].bg) >= 4.5, `${p.name} ${k} suave`);
    }
    // Cabecera en noche: los iconos claros de la barra de estado deben leerse.
    assert.ok(contrast('#FFFFFF', p.night.bg) >= 7, `${p.name}: noche oscura`);
  }
});

// --- Selección editorial ------------------------------------------------------------------------------------------
test('la selección editorial son grabaciones con MBID válido, sin duplicados y con los datos mínimos', () => {
  assert.ok(EDITORIAL_PICKS.length >= 12);
  assert.equal(new Set(EDITORIAL_PICKS.map((p) => p.mbid)).size, EDITORIAL_PICKS.length);
  for (const p of EDITORIAL_PICKS) {
    assert.match(p.mbid, MBID);
    assert.match(p.artist_mbid, MBID);
    assert.ok(p.title.trim() && p.artist.trim(), p.mbid);
  }
  assert.ok(EDITORIAL_PICKS.filter((p) => p.connections).length >= 5);
});

test('huecos del día: estables, distintos entre sí (canción y artista), sin Guardados y con reservas', () => {
  const day = dayIndexOf('2026-10-20');
  assert.deepEqual(dailySlots(day, []), dailySlots(day, []));
  for (let d = day; d < day + 60; d++) {
    const s = dailySlots(d, []);
    const all = [...s.cover, ...s.radar, ...s.behind];
    assert.equal(new Set(all.map((p) => p.mbid)).size, all.length);
    assert.equal(new Set(all.map((p) => p.artist_mbid)).size, all.length);
    assert.ok(s.cover.length >= 2 && s.radar.length >= 2 && s.behind.length >= 1);
    assert.ok(s.behind.every((p) => p.connections));
  }
  assert.notEqual(dailySlots(day, []).cover[0].mbid, dailySlots(day + 1, []).cover[0].mbid);
  const first = dailySlots(day, []).cover[0].mbid;
  assert.ok(!dailySlots(day, [first]).cover.concat(dailySlots(day, [first]).radar).some((p) => p.mbid === first));
});

// --- Datos verdaderos ---------------------------------------------------------------------------------------------
test('el dato sale solo de la ficha: sample primero; sin datos no hay dato (fallback)', () => {
  const deep = track({
    mbid: uuid(1), title: 'Deep Burnt', artist_name: 'Pépé Bradock',
    relations: { remix_of: [], remixes: [], remix_count: 0, dj_mix_count: 0, dj_mixes: [], samples: [link(uuid(2), 'Little Sunflower', 'Freddie Hubbard')] },
  });
  const f = radarFact(deep)!;
  assert.equal(f.kind, 'sample');
  assert.equal(f.text, '«Deep Burnt» incluye un sample de «Little Sunflower», de Freddie Hubbard.');
  assert.equal(f.other?.mbid, uuid(2));
  assert.equal(radarFact(track({ mbid: uuid(3), title: 'Sin datos', first_release_date: null })), null);
  // La producción solo es un dato si no es el propio artista acreditado.
  const self = track({ mbid: uuid(4), title: 'X', artist_name: 'Underworld', credits: [{ role: 'Producción', artists: [{ mbid: uuid(5), name: 'Underworld' } as never] }] });
  assert.ok(!soundFacts(self).some((x) => x.kind === 'producer'));
  const other = track({ mbid: uuid(6), title: 'Music', artist_name: 'Stardust', credits: [{ role: 'Producción', artists: [{ mbid: uuid(7), name: 'Thomas Bangalter' } as never] }] });
  assert.match(soundFacts(other).find((x) => x.kind === 'producer')!.text, /Thomas Bangalter/);
});

test('edición original: sello, formato y catálogo solo si constan', () => {
  const t = track({ mbid: uuid(8), title: 'Strings of Life', original_release: {
    mbid: uuid(9), title: 'Strings of Life', primary_type: 'Single', secondary_types: [], date: '1987-05', labels: ['Transmat'], catalog_number: 'MS-04',
    formats: ['12" Vinyl'], own: true, self_released: false, cover_url: null, url: '' } });
  assert.equal(soundFacts(t).find((x) => x.kind === 'release')!.text, 'Se publicó en 1987 en Transmat (MS-04), en vinilo de 12".');
});

test('Detrás del sonido: prefiere tus Guardados, nunca repite lo ya mostrado y se oculta sin conexiones', () => {
  const mine = track({ mbid: uuid(10), title: 'Good Life', relations: { remix_of: [], remixes: [link(uuid(11), 'Good Life (edit)', 'Inner City')], remix_count: 17, dj_mix_count: 0, dj_mixes: [] } });
  const editorial = track({ mbid: uuid(12), title: 'Deep Burnt', relations: { remix_of: [], remixes: [], remix_count: 0, dj_mix_count: 0, dj_mixes: [], samples: [link(uuid(13), 'Little Sunflower', 'Freddie Hubbard')] } });
  // El sample (más singular) gana aunque venga de la selección; con el sample ya mostrado, entra la remezcla de tus Guardados.
  assert.equal(behindFact([mine, editorial], new Set())!.kind, 'sample');
  assert.equal(behindFact([mine, editorial], new Set([uuid(13)]))!.track.mbid, uuid(10));
  assert.equal(behindFact([mine], new Set([uuid(11)])), null);
  assert.equal(behindFact([undefined, track({ mbid: uuid(14), title: 'Nada' })], new Set()), null);
});

// --- Tu frecuencia ------------------------------------------------------------------------------------------------
test('sin Guardados: descubrimiento editorial variado (nunca vacío), sin repetir artista ni lo ya mostrado', () => {
  const day = dayIndexOf('2026-10-20');
  const exclude = [EDITORIAL_PICKS[0].mbid];
  const f = frequency({ saved: [], details: {}, dayIndex: day, exclude });
  assert.equal(f.personal, 0);
  assert.equal(f.items.length, 8);
  assert.ok(f.items.every((i) => i.kind === 'editorial' && i.reason === 'Selección de la redacción'));
  assert.equal(new Set(f.items.map((i) => i.artist)).size, f.items.length);
  assert.ok(!f.items.some((i) => exclude.includes(i.mbid)));
  assert.deepEqual(frequency({ saved: [], details: {}, dayIndex: day, exclude }), f);
});

test('sin Guardados pero con estilos declarados: el motivo es el estilo y solo si el género consta', () => {
  const f = frequency({ saved: [], details: {}, dayIndex: 1, declaredStyles: ['Techno'] });
  const styled = f.items.filter((i) => i.kind === 'style');
  assert.ok(styled.length > 0);
  for (const i of styled) {
    assert.equal(i.reason, 'Techno, uno de tus estilos');
    assert.ok(EDITORIAL_PICKS.find((p) => p.mbid === i.mbid)!.genres.includes('Techno'));
  }
});

test('guardar o quitar una canción cambia la frecuencia (y lo guardado desaparece de ella)', () => {
  const pick = EDITORIAL_PICKS.find((p) => p.label === 'Transmat')!;
  const before = frequency({ saved: [], details: {}, dayIndex: 9 });
  const s = saved(uuid(50), 'Otra', 'Alguien', { label: 'Transmat', artists: [{ mbid: EDITORIAL_PICKS[1].artist_mbid, name: EDITORIAL_PICKS[1].artist, join_phrase: '' }] });
  const after = frequency({ saved: [s], details: {}, dayIndex: 9 });
  assert.notDeepEqual(after.items, before.items);
  assert.ok(after.items.some((i) => i.mbid === pick.mbid && i.reason === 'Mismo sello que «Otra»: Transmat'));
  assert.ok(after.items.some((i) => i.kind === 'artist' && i.reason === `Más de ${EDITORIAL_PICKS[1].artist}`));
  const savedPick = saved(pick.mbid, pick.title, pick.artist);
  assert.ok(!frequency({ saved: [savedPick], details: {}, dayIndex: 9 }).items.some((i) => i.mbid === pick.mbid));
});

// --- Versiones oficiales, ediciones y artistas principales ----------------------------------------------------------
const rel = (o: Partial<TrackResponse['relations']>): TrackResponse['relations'] =>
  ({ remix_of: [], remixes: [], remix_count: 0, dj_mix_count: 0, dj_mixes: [], ...o });
const release = (over: Partial<TrackRelease>): TrackRelease => ({
  mbid: uuid(90), title: 'Born Slippy', primary_type: 'Single', secondary_types: [], date: '1995', labels: [], catalog_number: null,
  formats: [], own: true, self_released: false, cover_url: null, url: '', ...over });

test('clases de versión: original, versión oficial, remezcla y no oficial (bootleg, mashup, «vs.»)', () => {
  const c = (title: string, artist_name = 'Inner City') => versionClass({ title, artist_name });
  assert.equal(c('Good Life'), 'original');
  assert.equal(c('Dirty Cash (Money Talks)'), 'original'); // subtítulo, no versión
  for (const v of ['Hoodlum (original mix)', 'Good Life (radio edit)', 'Strings of Life (Extended Mix)', 'Music Sounds Better With You (12” club mix)']) {
    assert.equal(c(v), 'version', v);
  }
  assert.equal(c('Ride the Storm (Joey Negro Medusa mix)'), 'remix');
  assert.equal(c('Good Life (Mr. B Special edit)'), 'remix');
  assert.equal(c('Lovelee Dae (Riso & Matthijs Wentink bootleg)', 'Blaze vs. Dennis Ferrer'), 'unofficial');
  // La selección editorial puede fijar la clase cuando el título no basta (Born Slippy, «Nuxx edit» oficial).
  assert.equal(EDITORIAL_PICKS.find((p) => p.title.startsWith('Born Slippy'))!.version, 'version');
});

test('En el radar: un bootleg o un edit no desplazan los datos de originales, pero se usan si no hay otros', () => {
  const lovelee = track({ mbid: uuid(60), title: 'Lovelee Dae', original_release: release({ title: 'Lovelee Dae', date: '1997', labels: ['Playhouse'] }),
    relations: rel({ mashups: [link(uuid(61), 'Lovelee Dae (Riso & Matthijs Wentink bootleg)', 'Blaze vs. Dennis Ferrer')] }) });
  assert.equal(radarFact(lovelee)!.kind, 'release');
  const onlyBootleg = track({ mbid: uuid(62), title: 'X', first_release_date: null, relations: rel({ mashups: [link(uuid(63), 'X (bootleg)', 'A vs. B')] }) });
  const f = radarFact(onlyBootleg)!;
  assert.equal(f.kicker, 'Un bootleg (no oficial)');
  assert.match(f.text, /identifica como bootleg/);
  // Entre quienes la samplean, primero una grabación original; un edit de terceros, después y dicho así.
  const good = track({ mbid: uuid(64), title: 'Good Life',
    relations: rel({ sampled_by: [link(uuid(65), 'Good Life (Mr. B Special edit)', 'Killa Productions'), link(uuid(66), 'Otra canción', 'Alguien')] }) });
  assert.equal(soundFacts(good).find((x) => x.kind === 'sampled')!.other!.mbid, uuid(66));
  const edit = track({ mbid: uuid(67), title: 'Good Life', relations: rel({ sampled_by: [link(uuid(65), 'Good Life (Mr. B Special edit)', 'Killa Productions')] }) });
  assert.equal(soundFacts(edit).find((x) => x.kind === 'sampled')!.kicker, 'Sampleada en un edit o remezcla');
  // Los créditos de producción (oficiales) van antes que un edit de terceros.
  const credited = track({ ...edit, credits: [{ role: 'Producción', artists: [{ mbid: uuid(68), name: 'Kevin Saunderson' } as never] }] });
  assert.equal(radarFact(credited)!.kind, 'producer');
});

test('ediciones: solo lo inequívoco del grupo de lanzamientos, sin preferir un formato', () => {
  // Sellos y formatos reunidos de todas sus ediciones: no se atribuye uno solo a 1995 ni se da un catálogo suelto.
  const multi = releaseFact({ original_release: release({ labels: ['Smith Hyde Productions', 'Wax Trax! Records', 'Junior Boy’s Own', 'Sony Records'],
    catalog_number: 'X1', formats: ['Digital Media', 'CD'] }), releases: [] })!;
  assert.equal(multi.text, 'Se publicó en 1995; sus ediciones salieron en Smith Hyde Productions, Wax Trax! Records, Junior Boy’s Own y otros sellos, en digital y CD.');
  // Sello único y varios formatos: los formatos son de sus ediciones, en el orden de la fuente.
  assert.equal(releaseFact({ original_release: release({ labels: ['Desolat'], catalog_number: 'DESOLAT 038', formats: ['Digital Media', '12" Vinyl'] }), releases: [] })!.text,
    'Se publicó en 1995 en Desolat (DESOLAT 038); sus ediciones, en digital y vinilo de 12".');
  assert.deepEqual(formatsEs(['Digital Media', '12" Vinyl', 'CD', 'Digital Media', 'Blu-spec CD']), ['digital', 'vinilo de 12"', 'CD']);
  // Sin sello ni formato: solo el año. Sin año: nada.
  assert.equal(releaseFact({ original_release: release({}), releases: [] })!.text, 'Se publicó por primera vez en 1995, según MusicBrainz.');
  assert.equal(releaseFact({ original_release: release({ date: null }), releases: [] }), null);
  // Otro lanzamiento propio del mismo año con más información verificable (sello y catálogo) gana a la original pobre…
  const richer = release({ mbid: uuid(91), title: 'Born Slippy EP', labels: ['Junior Boy’s Own'], catalog_number: 'JBO 29' });
  assert.equal(releaseFact({ original_release: release({}), releases: [richer] })!.text, 'Se publicó en 1995 en Junior Boy’s Own (JBO 29).');
  // …pero nunca uno de otro año ni un recopilatorio.
  assert.equal(releaseFact({ original_release: release({}), releases: [{ ...richer, date: '1996' }, { ...richer, secondary_types: ['Compilation'] }] })!.text,
    'Se publicó por primera vez en 1995, según MusicBrainz.');
});

// --- Tu frecuencia V6.1: identidad musical, portadas reales y diversidad ----------------------------------------------
const CAA = (n: number) => `https://coverartarchive.org/release/${uuid(n)}/front-500`;
const MSBWY = 'Music Sounds Better With You (12” club mix)';

/** Caso real: «Music Sounds Better With You» guardada, con sus remezclas, el sample de «Fate» y quien la samplea. */
function stardustCase() {
  const s = saved(uuid(200), MSBWY, 'Stardust');
  const b = saved(uuid(201), 'Deep Burnt', 'Pépé Bradock');
  const details = {
    [s.mbid]: track({ mbid: s.mbid, title: MSBWY, artist_name: 'Stardust', relations: rel({ remix_count: 3, remixes: [
      link(uuid(210), 'Music Sounds Better With You (radio edit)', 'Stardust'), link(uuid(211), 'Music Sounds Better With You (Bob Sinclar remix)', 'Stardust'),
      link(uuid(212), 'Music Sounds Better With You (Anthem From Paris)', 'Stardust')],
    samples: [link(uuid(220), 'Fate', 'Chaka Khan')], sampled_by: [link(uuid(221), 'Music Sounds Better With U', 'Big Time Rush feat. Mann')],
    mashups: [link(uuid(222), 'Lady, Music Sounds Better With You', 'Modjo vs. Stardust')] }) }),
    [b.mbid]: track({ mbid: b.mbid, title: 'Deep Burnt', relations: rel({ samples: [link(uuid(230), 'Little Sunflower', 'Freddie Hubbard')] }) }),
  };
  return { s, b, details };
}

test('V6.1: nunca otra versión de una canción guardada (relación de MusicBrainz o mismo título base y artista)', () => {
  const { s, b, details } = stardustCase();
  // Primera pasada: los candidatos por relación esperan su ficha (portada), alternando Guardados y con límite.
  const first = frequency({ saved: [s, b], details, dayIndex: 5 });
  assert.deepEqual(first.lookups, [uuid(220), uuid(230), uuid(221)]);
  assert.ok(!first.items.some((i) => i.kind === 'relation'));
  // Llegan las fichas: «Fate» y Big Time Rush con portada; «Little Sunflower» sin ella.
  const candidates = {
    [uuid(220)]: track({ mbid: uuid(220), title: 'Fate', artist_name: 'Chaka Khan', cover_url: CAA(1) }),
    [uuid(221)]: track({ mbid: uuid(221), title: 'Music Sounds Better With U', artist_name: 'Big Time Rush feat. Mann', cover_url: CAA(2) }),
    [uuid(230)]: track({ mbid: uuid(230), title: 'Little Sunflower', artist_name: 'Freddie Hubbard', cover_url: null }),
  };
  const f = frequency({ saved: [s, b], details, candidates, dayIndex: 5 });
  assert.equal(f.items[0].title, 'Fate');
  assert.equal(f.items[0].reason, `Sampleada en «${MSBWY}»`);
  assert.equal(f.items[0].mbid, uuid(220), 'abre el MBID del enlace');
  assert.ok(!f.items.some((i) => i.title.startsWith('Music Sounds Better With You')), 'ni radio edit, ni remix, ni mashup');
  assert.ok(!f.items.some((i) => i.mbid === uuid(221)), 'una sola relación por Guardado: no se sobreexplota una canción');
  assert.ok(!f.items.some((i) => i.mbid === uuid(230)), 'sin portada real no entra');
  assert.ok(f.discarded.duplicates >= 3 && f.discarded.noCover >= 1, JSON.stringify(f.discarded));
  assert.ok(f.items.every((i) => isRealCover(i.cover)));
  assert.equal(new Set(f.items.map((i) => mainArtist(i.artist))).size, f.items.length, 'un artista por carrusel');
  // Una versión de la guardada en la selección editorial (mismo título base y artista) tampoco entra.
  const pool = [{ ...EDITORIAL_PICKS[0], mbid: uuid(240), title: 'Music Sounds Better With You (radio edit)', artist: 'Stardust', artist_mbid: uuid(241) }, EDITORIAL_PICKS[1]];
  assert.deepEqual(frequency({ saved: [s], details, candidates, dayIndex: 5, pool }).items.map((i) => i.title), ['Fate', EDITORIAL_PICKS[1].title]);
});

test('V6.1: un sample une dos canciones distintas sin fusionarlas; covers y homónimos de otro artista son otras canciones', () => {
  assert.notEqual(songFamily('Music Sounds Better With U', 'Big Time Rush feat. Mann'), songFamily(MSBWY, 'Stardust'));
  assert.equal(songFamily('Music Sounds Better With You (radio edit)', 'Stardust'), songFamily(MSBWY, 'Stardust'));
  assert.equal(songFamily('Lovelee Dae (Seth Troxler remix)', 'Blaze'), songFamily('Lovelee Dae', 'Blaze'));
  assert.equal(songFamily('Crazy', 'ANOTR feat. PAMÉ'), songFamily('Crazy (Extended Mix)', 'ANOTR'));
  assert.notEqual(songFamily('Sing It Back', 'Moloko'), songFamily('Sing It Back', 'Otra banda'), 'una cover de otro artista no es la misma');
  assert.notEqual(songFamily('Dirty Cash (Money Talks)', 'PAWSA'), songFamily('Dirty Cash', 'PAWSA'), 'un subtítulo no es una versión');
  // Sin otra relación del Guardado, quien la samplea sí se recomienda (canción distinta).
  const { s, details } = stardustCase();
  const only = { [s.mbid]: track({ ...details[s.mbid], relations: rel({ sampled_by: details[s.mbid].relations.sampled_by }) }) };
  const candidates = { [uuid(221)]: track({ mbid: uuid(221), title: 'Music Sounds Better With U', artist_name: 'Big Time Rush feat. Mann', cover_url: CAA(2) }) };
  assert.equal(frequency({ saved: [s], details: only, candidates, dayIndex: 1 }).items[0].reason, `Samplea «${MSBWY}»`);
  // Su ficha dice que es una remezcla de la guardada: fuera, aunque el título no lo diga.
  const remix = { [uuid(221)]: track({ ...candidates[uuid(221)], relations: rel({ remix_of: [link(s.mbid, MSBWY, 'Stardust')] }) }) };
  assert.ok(!frequency({ saved: [s], details: only, candidates: remix, dayIndex: 1 }).items.some((i) => i.mbid === uuid(221)));
});

test('V6.1: portadas reales de Cover Art Archive; la que no carga en el dispositivo saca al candidato', () => {
  assert.ok(isRealCover(EDITORIAL_PICKS[0].cover));
  assert.ok(EDITORIAL_PICKS.every((p) => isRealCover(p.cover)));
  for (const bad of [null, '', 'http://coverartarchive.org/release/x/front-500', 'https://example.com/cover.jpg', 'no es una url',
    'https://coverartarchive.org/'] as const) assert.ok(!isRealCover(bad), String(bad));
  const f = frequency({ saved: [], details: {}, dayIndex: 3 });
  const g = frequency({ saved: [], details: {}, dayIndex: 3, failedCovers: [f.items[0].cover] });
  assert.ok(!g.items.some((i) => i.mbid === f.items[0].mbid));
  assert.equal(g.discarded.noCover, 1);
  const noCover = [{ ...EDITORIAL_PICKS[0], cover: null }, EDITORIAL_PICKS[1]];
  assert.deepEqual(frequency({ saved: [], details: {}, dayIndex: 3, pool: noCover }).items.map((i) => i.mbid), [EDITORIAL_PICKS[1].mbid]);
});

test('V6.1: diversidad — un artista, un motivo y como mucho dos propuestas por Guardado; mejor menos que variantes', () => {
  const s = saved(uuid(70), 'Deep Burnt', 'Pépé Bradock');
  const details = { [s.mbid]: track({ mbid: s.mbid, title: 'Deep Burnt', relations: rel({ sampled_by: [
    link(uuid(72), 'Ride the Storm (Joey Negro Medusa mix)', 'Akabu feat. Linda Clifford'), link(uuid(71), 'Ride the Storm', 'Akabu')] }) }) };
  const candidates = { [uuid(72)]: track({ mbid: uuid(72), title: 'x', cover_url: CAA(3) }), [uuid(71)]: track({ mbid: uuid(71), title: 'x', cover_url: CAA(4) }) };
  const f = frequency({ saved: [s], details, candidates, dayIndex: 3 });
  assert.equal(f.items.filter((i) => mainArtist(i.artist) === 'Akabu').length, 1);
  assert.ok(f.items.some((i) => i.artist === 'Akabu feat. Linda Clifford'), 'crédito completo intacto');
  const personal = f.items.filter((i) => i.kind !== 'editorial');
  assert.equal(new Set(personal.map((i) => i.reason)).size, personal.length, 'nunca dos propuestas por el mismo motivo');
  // Muchos Guardados con relaciones: las fichas que se piden están acotadas.
  const many = Array.from({ length: 6 }, (_, i) => saved(uuid(300 + i), `T${i}`, `A${i}`));
  const det = Object.fromEntries(many.map((m, i) => [m.mbid, track({ mbid: m.mbid, title: m.title, relations: rel({
    samples: [link(uuid(400 + i), `S${i}`, `B${i}`), link(uuid(500 + i), `R${i}`, `C${i}`)] }) })]));
  assert.ok(frequency({ saved: many, details: det, dayIndex: 1 }).lookups.length <= FREQUENCY_LOOKUPS);
  // Pocos candidatos válidos: carrusel corto, sin relleno.
  assert.equal(frequency({ saved: [], details: {}, dayIndex: 1, pool: EDITORIAL_PICKS.slice(0, 2) }).items.length, 2);
});

test('Tu frecuencia: un invitado («feat.») no se presenta como artista principal de tu canción', () => {
  const main = EDITORIAL_PICKS[3];
  const guest = EDITORIAL_PICKS[2];
  const s = saved(uuid(80), 'Crazy', `${main.artist} feat. ${guest.artist}`, { artists: [
    { mbid: main.artist_mbid, name: main.artist, join_phrase: ' feat. ' }, { mbid: guest.artist_mbid, name: guest.artist, join_phrase: '' }] });
  const f = frequency({ saved: [s], details: {}, dayIndex: 2, size: 20 });
  assert.equal(f.items.find((i) => i.mbid === main.mbid)?.reason, `Más de ${main.artist}`);
  assert.equal(f.items.find((i) => i.mbid === guest.mbid)?.reason, `${guest.artist}, invitado en «Crazy»`);
});
