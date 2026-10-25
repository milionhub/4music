/** Carteles 3.5: paleta del evento, explorador con filtros, vista rápida (foto y «Sobre el artista») y compatibilidad. */
import assert from 'node:assert/strict';
import { test } from 'node:test';

import { contrast, PALETTES } from '../src/lib/artist-identity.ts';
import { COVER_KINDS, eventArt, usableSeeds } from '../src/lib/poster-art.ts';
import { exploreRows, facets, filterSets, lineupSummary, NO_FILTER, timeLabel, validFilter } from '../src/lib/poster-explore.ts';
import { applyResolution, chooseIdentity, type Resolution, setArtistStyles } from '../src/lib/poster-identity.ts';
import { fromExtraction, renameArtist } from '../src/lib/poster-model.ts';
import { artistSpotlight, fitText, identityLine, licenseUrl, photoCredit, photoShortCredit, spotlightCredits, SPOTLIGHT_MAX_WORDS, verifiablePhoto } from '../src/lib/poster-quick.ts';
import { parsePosterEvent, serializePosterEvent } from '../src/lib/poster-store.ts';
import type { ArtistIdentity, ArtistProfileResponse } from '../src/types/music.ts';
import type { PosterEvent, PosterExtraction } from '../src/types/poster.ts';

const NOW = '2026-10-21T20:00:00.000Z';
const LATER = '2026-10-21T21:00:00.000Z';
const INIT = { id: 'p1', now: NOW, fingerprint: 'md5-a', assetId: 'asset-1', image: { width: 1080, height: 1350, bytes: 200_000 } };

function ext(over: Partial<PosterExtraction> = {}): PosterExtraction {
  return {
    mode: 'full', complete: true, model: 'm', event_name: 'SW38', dates: [], location: null, stages: ['1', '2'], colors: ['#FF2E88', '#07060B'],
    artists: [], individual_times: [], uncertain: [], unreadable_text: [], review: [], usage: null,
    sessions: [
      { date: { text: '03.09', iso: null }, label: 'THURSDAY NIGHTTIME', stage: '1', time: '22:00', artists: ['CUKY', 'PERSIC', 'MIHIGH'] },
      { date: { text: '04.09', iso: null }, label: 'FRIDAY DAYTIME', stage: '2', time: null, artists: ['JAMIE JONES', 'JOSEPH CAPRIATI', 'MIHIGH'] },
    ],
    b2b: [{ artists: ['CUKY', 'PERSIC'], text: 'CUKY B2B PERSIC' }, { artists: ['JAMIE JONES', 'JOSEPH CAPRIATI'], text: null }],
    ...over,
  };
}

const byName = (e: PosterEvent, name: string) => e.artists.find((a) => a.name === name)!;
const res = (name: string): Resolution => ({ name, status: 'linked', mbid: `mbid-${name}`, canonical: name, candidates: [], evidence: null, source: null });

/** SW38 sintético con un escenario sin actuaciones y dos horas propias impresas (las demás son de bloque). */
function festival(): PosterEvent {
  const e = fromExtraction(ext(), INIT);
  return {
    ...e,
    stages: [...e.stages, { id: 'st9', name: 'Vacío', meta: e.stages[0].meta }],
    sets: e.sets.map((s, i) => (i === 0 ? { ...s, start: '23:30', end: '01:00', timeScope: 'set' as const }
      : i === 1 ? { ...s, start: '03:00', end: null, timeScope: 'set' as const } : s)),
  };
}

test('paleta del evento: colores del cartel ajustados al sistema, estable y con contraste; si no, determinista', () => {
  const pink = eventArt({ id: 'p1', fingerprint: 'md5-a', seeds: ['#FF2E88', '#07060B'] });
  assert.equal(pink.source, 'poster');
  assert.equal(pink.palette.name, 'Infrarrojo');
  assert.deepEqual(eventArt({ id: 'p1', fingerprint: 'md5-a', seeds: ['#FF2E88', '#07060B'] }), pink);
  // Cartel de fondo oscuro con acento neón → paleta oscura con el acento más cercano.
  assert.equal(eventArt({ id: 'p2', fingerprint: null, seeds: ['#050505', '#00FF99'] }).palette.name, 'Negro neón');
  // Sin colores útiles (inválidos, negros, blancos o grises): alternativa por la huella, igual en cada apertura.
  for (const seeds of [[], ['nope', '#000000', '#FFFFFF', '#808080']]) {
    const a = eventArt({ id: 'p3', fingerprint: 'md5-z', seeds });
    assert.equal(a.source, 'fallback');
    assert.equal(a.palette.name, eventArt({ id: 'otro', fingerprint: 'md5-z', seeds: [] }).palette.name);
  }
  assert.deepEqual(usableSeeds(['#FF2E88', '#0A0A0A', '#FAFAFA', '#777777', 'x']), ['#FF2E88']);
  for (const p of PALETTES) {
    const a = eventArt({ id: 'x', fingerprint: null, seeds: [p.bg, p.pop] });
    assert.ok(contrast(a.palette.ink, a.palette.bg) >= 4.5 && contrast(a.palette.glow, a.surfaces.screen) >= 4.5, p.name);
  }
  assert.ok(COVER_KINDS.includes(pink.kind));
  assert.ok(new Set('abcdefgh'.split('').map((f) => eventArt({ id: 'p', fingerprint: f, seeds: [] }).kind)).size > 1);
});

test('filtros: solo con datos que separan, sin horas de bloque ni escenarios vacíos', () => {
  const e = festival();
  const fx = facets(e);
  assert.equal(fx.days.length, 2);
  assert.deepEqual(fx.stages.map((s) => s.label), ['1', '2']); // «Vacío» no tiene actuaciones
  assert.deepEqual(fx.bands.map((b) => b.id), ['night', 'late']);
  assert.deepEqual(fx.styles, []); // sin estilos documentados no hay filtro de estilo
  const plain = fromExtraction(ext({ b2b: [], stages: [], sessions: [{ date: null, label: null, stage: null, time: '22:00', artists: ['A', 'B', 'C'] }] }), INIT);
  assert.deepEqual(facets(plain), { days: [], stages: [], bands: [], styles: [] }); // la hora de bloque no crea filtro
  assert.equal(timeLabel(plain.sets[0]), 'Bloque desde 22:00');
  assert.equal(timeLabel(e.sets[0]), '23:30–01:00');
  assert.equal(timeLabel({ ...plain.sets[0], start: null, timeScope: null }), null); // sin hora no se inventa
});

test('explorador: un B2B es una sola fila, orden del cartel y lo que no tiene día solo en «Todos»', () => {
  let e = festival();
  e = { ...e, sets: [...e.sets, { ...e.sets[2], id: 's99', dayId: null, artistIds: [byName(e, 'MIHIGH').id], order: 99 }] };
  const all = exploreRows(e, NO_FILTER);
  const sets = all.filter((r) => r.kind === 'set');
  assert.equal(sets.length, e.sets.length);
  assert.deepEqual(all.flatMap((r) => (r.kind === 'day' ? [r.label] : [])), ['03.09', '04.09', 'Sin día confirmado']);
  assert.equal(sets.filter((r) => r.kind === 'set' && r.set.artistIds.length === 2).length, 2);
  const day1 = exploreRows(e, { ...NO_FILTER, day: e.days[0].id });
  assert.ok(day1.every((r) => r.kind === 'set' && r.set.dayId === e.days[0].id));
  const orders = day1.map((r) => (r.kind === 'set' ? r.set.order : -1));
  assert.deepEqual(orders, [...orders].sort((a, b) => a - b));
  assert.deepEqual(exploreRows(e, { ...NO_FILTER, stage: 'st9' }), []);
  // Un filtro que ya no existe (evento editado) se ignora en lugar de vaciar la lista.
  assert.equal(validFilter({ ...NO_FILTER, stage: 'st9' }, facets(e)).stage, null);
  assert.deepEqual(lineupSummary(e), ['5 artistas', '2 días', '2 escenarios', '2 B2B']);
});

test('estilo: se guarda al abrir el perfil, filtra actuaciones (B2B incluidos) y se borra si cambia la identidad', () => {
  let e = festival();
  const [cuky, persic, jamie] = ['CUKY', 'PERSIC', 'JAMIE JONES'].map((n) => byName(e, n).id);
  e = applyResolution(applyResolution(applyResolution(e, cuky, res('CUKY')), persic, res('PERSIC')), jamie, res('JAMIE JONES'));
  assert.equal(setArtistStyles(e, cuky, 'otro-mbid', ['techno']), e); // solo para el MBID enlazado
  e = setArtistStyles(e, cuky, 'mbid-CUKY', ['música techno', 'house']);
  e = setArtistStyles(e, jamie, 'mbid-JAMIE JONES', ['Tech house', 'House']);
  assert.deepEqual(byName(e, 'CUKY').styles, ['techno', 'house']);
  assert.equal(e.updatedAt, NOW); // no es una edición del usuario
  assert.equal(setArtistStyles(e, cuky, 'mbid-CUKY', ['techno', 'house']), e); // sin cambios: mismo objeto, no se guarda
  assert.deepEqual(facets(e).styles.map((s) => s.id), ['house']); // compartido por 2 actuaciones; «techno», por 1
  const rows = filterSets(e, { ...NO_FILTER, style: 'house' });
  assert.equal(rows.length, 2);
  assert.ok(rows.every((s) => s.artistIds.includes(cuky) || s.artistIds.includes(jamie)));
  const reopened = parsePosterEvent(serializePosterEvent(e))!;
  assert.deepEqual(byName(reopened, 'CUKY').styles, ['techno', 'house']);
  assert.equal(byName(chooseIdentity(reopened, cuky, { refId: 'otro', name: 'Cuky', disambiguation: null }, LATER), 'CUKY').styles, undefined);
  assert.equal(byName(renameArtist(reopened, cuky, 'CUKI', LATER), 'CUKI').styles, undefined);
});

test('vista rápida: foto solo con derechos verificables y crédito completo', () => {
  const base = { url: 'https://upload.wikimedia.org/a.jpg', page_url: 'https://commons.wikimedia.org/wiki/File:A.jpg', author: 'Ana',
    license: 'CC BY-SA 4.0', license_url: null, source: 'wikimedia_commons' as const };
  assert.ok(verifiablePhoto(base));
  assert.ok(verifiablePhoto({ ...base, author: null, license: 'CC0' }));
  for (const bad of [{ author: null }, { license: '' }, { license: 'CC BY-NC 4.0' }, { license: 'CC BY-ND 2.0' }, { license: 'All rights reserved' },
    { page_url: '' }, { url: 'http://inseguro/a.jpg' }]) {
    assert.ok(!verifiablePhoto({ ...base, ...bad }), JSON.stringify(bad));
  }
  assert.ok(!verifiablePhoto(null));
  assert.ok(verifiablePhoto({ ...base, source: 'editorial', license: 'Permiso del artista' }));
  assert.ok(!verifiablePhoto({ ...base, source: 'editorial', author: null }));
  assert.equal(photoCredit(base), 'Foto: Ana · CC BY-SA 4.0 · Wikimedia Commons');
  assert.equal(photoShortCredit(base), 'Foto · Ana · CC BY-SA 4.0');
});

test('V6: foto de Deezer solo enlazada a su ficha, con crédito propio', () => {
  const dz = { url: 'https://cdn-images.dzcdn.net/images/artist/6c2b/1000x1000-000000-80-0-0.jpg', page_url: 'https://www.deezer.com/artist/5359276',
    author: null, license: '© titulares de derechos · Deezer API (uso no comercial)', license_url: 'https://developers.deezer.com/termsofuse',
    source: 'deezer' as const };
  assert.ok(verifiablePhoto(dz));
  assert.ok(!verifiablePhoto({ ...dz, page_url: 'https://example.com/artist/1' }));
  assert.ok(!verifiablePhoto({ ...dz, url: 'http://cdn-images.dzcdn.net/a.jpg' }));
  assert.equal(photoCredit(dz), 'Foto: Deezer · © titulares de derechos · Deezer API (uso no comercial)');
  assert.equal(photoShortCredit(dz), 'Foto · Deezer');
});

// Perfiles reales de GET /v1/artists/{mbid} (2026-10-23), reducidos a lo que usa «Sobre el artista».
const MB = { label: 'MusicBrainz', url: 'https://musicbrainz.org/artist/x', license: 'CC0' };
const DISCOGS = { label: 'Discogs (perfil)', url: 'https://www.discogs.com/artist/1', license: 'CC0' };
const NO_ID: ArtistIdentity = { country_name: null, area: null, origin: null, origin_kind: null, formed_year: null, active_since: null };
type P = Parameters<typeof artistSpotlight>[0];
const wiki = (lang: string, text: string) => ({ text, language: lang, source: { label: `Wikipedia (${lang})`, url: `https://${lang}.wikipedia.org/wiki/X`, license: 'CC BY-SA 4.0' } });
const wikidata = (text: string) => ({ kind: 'factual' as const, text, language: 'es', reviewed: null, sources: [{ label: 'Wikidata Q1', url: 'https://www.wikidata.org/wiki/Q1', license: 'CC0' }] });
function profile(name: string, over: Partial<P> = {}): P {
  return { artist: { name } as ArtistProfileResponse['artist'], bio: null, summary: null, identity: NO_ID, sources: [MB], ...over };
}
const CARL = profile('Carl Craig', {
  bio: wikidata('DJ, músico y productor de música techno estadounidense.'),
  summary: wiki('es', 'Carl Craig es un productor de música techno de Detroit, también DJ y músico estadounidense. Está considerado como uno de los nombres más significativos de la comunidad techno de Detroit en "términos artísticos, de influencia y de diversidad". Carl Craig se ha acercado al techno inspirándose en un amplio rango de géneros musicales, incluyendo el jazz y el soul.'),
  identity: { ...NO_ID, origin: 'Detroit', origin_kind: 'birth', active_since: '1989', founded_labels: ['Planet E', 'Planet E Communications'],
    projects: ['Urban Tribe', 'Innerzone Orchestra', 'The Detroit Experiment'] },
});
const PACO = profile('Paco Osuna', {
  bio: wikidata('DJ español.'),
  summary: wiki('es', 'Paco Osuna (Barcelona, 1974) es un disc jockey español conocido por su larga carrera, centrada principalmente en Ibiza. Su estancia en la isla comenzó con una residencia en la discoteca Amnesia, en 1999. Entre sus gustos musicales destacan el techno y el house.\nEn 2003 fundó su propio sello discográfico, Shake Records, refundado en 2006 como Mind Shake.'),
  identity: { ...NO_ID, origin: 'Barcelona', origin_kind: 'birth', founded_labels: ['Shake Records'] },
  sources: [MB, DISCOGS],
});
const nWords = (ps: string[]) => ps.join(' ').split(/\s+/).filter(Boolean).length;

test('spotlight: Carl Craig, introducción de Wikipedia + relaciones de MusicBrainz que no menciona', () => {
  const s = artistSpotlight(CARL);
  assert.equal(s.basis, 'wikipedia');
  assert.equal(s.paragraphs.length, 2);
  // Detroit ya está en el texto: no se repite su origen. «Planet E» y «Planet E Communications», un solo sello.
  assert.equal(s.paragraphs[1], 'En activo desde 1989, fundó el sello Planet E Communications y ha formado parte de Urban Tribe, Innerzone Orchestra y The Detroit Experiment.');
  assert.deepEqual(s.sources.map((x) => x.label), ['Wikipedia (es)', 'MusicBrainz']);
  assert.equal(s.adapted, false);
});

test('spotlight: Paco Osuna, sin fecha de nacimiento, sin repetir el sello y con el recorte indicado', () => {
  const s = artistSpotlight(PACO);
  const text = s.paragraphs.join(' ');
  assert.ok(text.startsWith('Paco Osuna es un disc jockey español'));
  assert.ok(!text.includes('1974'));
  assert.equal(text.match(/Shake Records/g)?.length, 1);
  assert.ok(text.endsWith('Mind Shake. Paco Osuna es natural de Barcelona.'));
  assert.equal(s.adapted, true); // «Extracto adaptado»: se quitó el paréntesis con la fecha
  assert.deepEqual(s.sources.map((x) => x.label), ['Wikipedia (es)', 'MusicBrainz']); // Discogs no aporta nada aquí
});

test('spotlight: Cajmere, la introducción en inglés no se muestra; descripción de Wikidata y datos documentados', () => {
  const s = artistSpotlight(profile('Cajmere', {
    bio: wikidata('Músico estadounidense.'),
    summary: wiki('en', 'Curtis Alan Jones (born April 26, 1968), better known by his stage name Green Velvet, is an American disc jockey.'),
    identity: { ...NO_ID, origin: 'Chicago', origin_kind: 'birth', active_since: '1991' },
  }));
  assert.equal(s.basis, 'wikidata');
  assert.deepEqual(s.paragraphs, ['Músico estadounidense. Cajmere es natural de Chicago y está en activo desde 1991.']);
  assert.deepEqual(s.sources.map((x) => x.label), ['Wikidata Q1', 'MusicBrainz']);
});

test('spotlight: sin datos (Future.666, desconocido) no se inventa nada', () => {
  assert.deepEqual(artistSpotlight(profile('future.666')), { paragraphs: [], basis: null, sources: [], adapted: false });
  // Una descripción solo en inglés tampoco se muestra sin traducir.
  assert.equal(artistSpotlight(profile('X', { bio: { ...wikidata('American musician.'), language: 'en' } })).basis, null);
  assert.equal(identityLine(undefined), null);
  assert.equal(identityLine(NO_ID), null);
});

test('spotlight: un homónimo elegido a mano trae el texto de su propia identidad', () => {
  const vocalist = artistSpotlight(profile('Carl Craig', { identity: { ...NO_ID, projects: ['The Pair Extraordinaire'] } }));
  assert.deepEqual(vocalist.paragraphs, ['Carl Craig ha formado parte de The Pair Extraordinaire.']);
  assert.ok(!vocalist.paragraphs.join(' ').includes('Planet E'));
});

test('spotlight: la biografía validada del perfil manda; frases completas hasta ~110 palabras', () => {
  const long = Array.from({ length: 12 }, (_, i) => `Frase número ${i + 1} con un dato concreto sobre su trayectoria en clubes.`).join(' ');
  const s = artistSpotlight({ ...CARL, bio: { kind: 'generated', text: `${long}\n\nSegundo párrafo.`, language: 'es', reviewed: null, sources: [MB] } });
  assert.equal(s.basis, 'generated');
  assert.ok(nWords(s.paragraphs) <= SPOTLIGHT_MAX_WORDS);
  assert.ok(s.paragraphs.every((p) => p.endsWith('.')));
  assert.ok(!s.paragraphs.join(' ').includes('Planet E')); // a una biografía no se le añaden datos sueltos
  assert.deepEqual(fitText('Joseph Capriati, nacido como Giuseppe Capriati el 25 de julio de 1987 en Caserta, Italia, inició su trayectoria como DJ. Nació en Caserta en 1987.'),
    ['Joseph Capriati inició su trayectoria como DJ.']);
  // «nacido en Caernarfon» sin fecha se conserva: solo salen las fechas de nacimiento.
  assert.deepEqual(fitText('Jamie Jones es un DJ galés nacido en Caernarfon, activo desde 2003.'), ['Jamie Jones es un DJ galés nacido en Caernarfon, activo desde 2003.']);
});

test('eventos de 3.3–3.4 se abren igual: sin estilos, enlaces antiguos y paleta derivada sin reescribir', () => {
  const e = fromExtraction(ext(), INIT);
  const raw = JSON.parse(serializePosterEvent(e));
  raw.artists[0].styles = 'roto';
  raw.artists[1].link = { status: 'pending', catalog: null, refId: null };
  const back = parsePosterEvent(JSON.stringify(raw))!;
  assert.equal(back.artists[0].styles, undefined);
  assert.equal(back.artists[1].link.status, 'pending');
  assert.deepEqual(back.palette, e.palette); // la paleta guardada no cambia: la portada la deriva
  assert.deepEqual(eventArt({ id: back.id, fingerprint: back.fingerprint, seeds: back.palette.seeds }),
    eventArt({ id: e.id, fingerprint: e.fingerprint, seeds: e.palette.seeds }));
});

test('3.5C fuentes y créditos: foto con autor, fuente y licencia; texto con su atribución y si se adaptó', () => {
  const photo = { url: 'https://upload.wikimedia.org/a.jpg', page_url: 'https://commons.wikimedia.org/wiki/File:A.jpg', author: 'Monty Luke',
    license: 'CC BY-SA 3.0', license_url: null, source: 'wikimedia_commons' as const };
  const credits = spotlightCredits(photo, artistSpotlight(PACO));
  assert.deepEqual(credits.map((c) => c.title), ['Fotografía', 'Texto', 'Datos añadidos']); // «natural de Barcelona»: MusicBrainz
  assert.equal(credits[0].detail, 'Foto: Monty Luke · CC BY-SA 3.0 · Wikimedia Commons');
  assert.deepEqual(credits[0].links.map((l) => l.url), [photo.page_url, 'https://creativecommons.org/licenses/by-sa/3.0/']);
  assert.ok(credits[1].detail.startsWith('Extracto adaptado'));
  assert.deepEqual(credits[1].links.map((l) => l.url), ['https://es.wikipedia.org/wiki/X', 'https://creativecommons.org/licenses/by-sa/4.0/']);

  const carl = spotlightCredits(null, artistSpotlight(CARL));
  assert.deepEqual(carl.map((c) => c.title), ['Texto', 'Datos añadidos']);
  assert.ok(carl[0].detail.startsWith('Extracto literal de Wikipedia (es) · CC BY-SA 4.0'));
  assert.deepEqual(carl[1].links.map((l) => l.label), ['MusicBrainz (CC0)']); // CC0: sin enlace de licencia obligatorio
});

test('3.5C fuentes y créditos: sin licencia acreditable no hay foto (cartel tipográfico) ni créditos inventados', () => {
  const noLicense = { url: 'https://x/a.jpg', page_url: 'https://x/a', author: 'Ana', license: '', license_url: null, source: 'wikimedia_commons' as const };
  assert.deepEqual(spotlightCredits(noLicense, null), []);
  assert.deepEqual(spotlightCredits({ ...noLicense, license: 'CC BY-NC 4.0' }, null), []);
  assert.deepEqual(spotlightCredits(null, artistSpotlight(profile('future.666'))), []); // sin nada que acreditar: sin botón ⓘ
  assert.equal(licenseUrl('CC BY 2.0'), 'https://creativecommons.org/licenses/by/2.0/');
  assert.equal(licenseUrl('CC0'), 'https://creativecommons.org/publicdomain/zero/1.0/');
  assert.equal(licenseUrl('Permiso del artista'), null);
  assert.equal(licenseUrl('CC BY-SA 4.0', 'https://example.org/terms'), 'https://example.org/terms');
});
