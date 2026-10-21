/** Artist Experience v3: identidad visual determinista y accesible, nombres siempre enteros, ficha verificada y
 * «Más allá de la cabina» sin inventar. */
import assert from 'node:assert/strict';
import { test } from 'node:test';

import {
  ABRIL, COMPOSITIONS, contrast, display, DM_SERIF, DM_SERIF_ITALIC, fitSize, identityFor, nameLines, PALETTES, splitTitle, surfaces, SYNE,
  textWidthEm, TYPEFACES,
} from '../src/lib/artist-identity.ts';
import { artistCardRows } from '../src/lib/format.ts';
import type { ArtistIdentity } from '../src/types/music.ts';

const APP_BG = '#07060B';

test('identidad estable por MBID y variada entre artistas', () => {
  const mbid = '80186758-4231-4850-a29d-6ff30f014092';
  assert.deepEqual(identityFor(mbid), identityFor(mbid));
  const ids = Array.from({ length: 300 }, (_, i) => identityFor(`${i.toString(16).padStart(8, '0')}-0000-4000-8000-${i * 7919}`));
  assert.equal(new Set(ids.map((x) => x.palette.name)).size, PALETTES.length);
  assert.equal(new Set(ids.map((x) => x.type.key)).size, TYPEFACES.length);
  assert.equal(new Set(ids.map((x) => x.composition)).size, COMPOSITIONS.length);
  assert.ok(new Set(ids.map((x) => `${x.palette.name}|${x.type.key}|${x.composition}`)).size > 120);
});

test('todas las paletas son legibles: texto del cartel, acentos sobre fondo oscuro y botón', () => {
  for (const p of PALETTES) {
    assert.ok(contrast(p.ink, p.bg) >= 4.5, `${p.name}: ink/bg ${contrast(p.ink, p.bg).toFixed(2)}`);
    assert.ok(contrast(p.glow, APP_BG) >= 4.5, `${p.name}: glow/fondo ${contrast(p.glow, APP_BG).toFixed(2)}`);
    assert.ok(contrast(p.onGlow, p.glow) >= 4.5, `${p.name}: botón ${contrast(p.onGlow, p.glow).toFixed(2)}`);
  }
});

test('el nombre siempre cabe entero: anchos reales de cada letra (casos ARAPU y PAWSA) en móviles estrechos', () => {
  for (const type of TYPEFACES) {
    for (const width of [288, 343, 398]) {
      for (const name of ['ARAPU', 'PAWSA', 'WWWWWW', 'The Martinez Brothers', 'Joseph Capriati']) {
        for (const line of nameLines(name)) {
          const text = display(line, type);
          const size = fitSize(text, width, type, 140, 8);
          const used = textWidthEm(text, type) * size + type.tracking * ([...text].length - 1);
          assert.ok(used <= width, `${type.key} ${width}px «${text}»: ${used.toFixed(1)}px`);
        }
      }
    }
  }
  // Rubik Mono One es ancha: la estimación media anterior se quedaba corta con nombres de letras anchas.
  const rubik = TYPEFACES.find((t) => t.key === 'rubik')!;
  assert.ok(textWidthEm('PAWSA', rubik) >= 4.2);
});

test('nombres largos y dúos se reparten en líneas sin huérfanas', () => {
  assert.deepEqual(nameLines('Priku'), ['Priku']);
  assert.deepEqual(nameLines('The Martinez Brothers'), ['The Martinez', 'Brothers']);
  assert.ok(nameLines('Argy & The Martinez Brothers & Friends Of The Club').length <= 3);
});

const identity = (over: Partial<ArtistIdentity>): ArtistIdentity => ({
  country_name: null, area: null, origin: null, origin_kind: null, formed_year: null, active_since: null, ...over,
});

test('«Conoce al artista»: solo campos que constan, fundar ≠ estar al frente, sin repetir lugares', () => {
  const duo = artistCardRows({ type: 'Group', identity: identity({ country_name: 'Países Bajos', area: 'Amsterdam',
    founded_labels: ['NO ART'], label_years: { 'NO ART': '2017' }, members: ['Oguz Han Guney', 'Jesse Van Der Heijden'] }) });
  assert.deepEqual(duo, [
    { label: 'Formato', value: 'Dúo' }, { label: 'País', value: 'Países Bajos' }, { label: 'Ciudad asociada', value: 'Amsterdam' },
    { label: 'Sello fundado', value: 'NO ART (2017)' }, { label: 'Integrantes', value: 'Oguz Han Guney y Jesse Van Der Heijden' },
  ]);
  const runner = artistCardRows({ type: 'Person', identity: identity({ country_name: 'Francia', area: 'Francia', run_labels: ['Gettraum'] }) });
  assert.deepEqual(runner, [{ label: 'País', value: 'Francia' }, { label: 'Al frente del sello', value: 'Gettraum' }]);
  assert.deepEqual(artistCardRows({ type: null, identity: identity({}) }), []); // nada vacío ni «desconocido»
});

test('superficies teñidas con la paleta: el texto de la ficha y los acentos siguen siendo legibles', () => {
  for (const p of PALETTES) {
    const S = surfaces(p);
    for (const [k, bg] of Object.entries({ screen: S.screen, raised: S.raised, deep: S.deep })) {
      assert.ok(contrast('#F6F3FF', bg) >= 12, `${p.name} ${k}: texto ${contrast('#F6F3FF', bg).toFixed(1)}`);
      assert.ok(contrast(p.glow, bg) >= 4.5, `${p.name} ${k}: acento ${contrast(p.glow, bg).toFixed(1)}`);
    }
  }
});

test('títulos de canción en dos voces y siempre enteros con las serif nuevas', () => {
  assert.deepEqual(splitTitle('Dirty Cash (Money Talks)'), { main: 'Dirty Cash', aside: 'Money Talks' });
  assert.deepEqual(splitTitle('Relax My Eyes - Extended Mix'), { main: 'Relax My Eyes', aside: 'Extended Mix' });
  assert.deepEqual(splitTitle('Desire'), { main: 'Desire', aside: null });
  assert.deepEqual(splitTitle('(I Just) Died in Your Arms'), { main: '(I Just) Died in Your Arms', aside: null });
  for (const type of [DM_SERIF, DM_SERIF_ITALIC, ABRIL, SYNE]) {
    for (const width of [288, 343, 398]) {
      for (const title of ['Dirty Cash', 'Fizheuer Zieheuer', 'WWWWWWWW', 'Hoodlum']) {
        for (const raw of nameLines(title)) {
          const line = display(raw, type);
          const size = fitSize(line, width, type, 140, 8);
          const used = textWidthEm(line, type) * size + type.tracking * ([...line].length - 1);
          assert.ok(used <= width, `${type.key} ${width}px «${line}»: ${used.toFixed(1)}px`);
        }
      }
    }
  }
});
