/** Dirección artística de TrackDNA: cartel estable y variado; interior con el sistema común V5.4, legible. */
import assert from 'node:assert/strict';
import { test } from 'node:test';

import { contrast, PALETTES } from '../src/lib/artist-identity.ts';
import { ART_PALETTES, HEROES, SHEET, sheetAccent, trackArt, TRIOS } from '../src/lib/track-art.ts';

const HOODLUM = '98e34bc2-0e71-4205-8986-af891195ed4e';
const LOVELEE = '8edae321-48fc-4ae6-add1-bc976cb1a823';
const DESIRE = '9d619150-6b0f-4f14-b038-8503ae4c6c8f';

test('cada superficie de cada paleta es legible: tinta y tinta suave ≥ 4,5:1', () => {
  for (const p of ART_PALETTES) {
    for (const k of ['hero', 'alt', 'paper', 'night'] as const) {
      const s = p[k];
      assert.ok(contrast(s.ink, s.bg) >= 4.5, `${p.name} ${k}: tinta ${contrast(s.ink, s.bg).toFixed(2)}`);
      assert.ok(contrast(s.soft, s.bg) >= 4.5, `${p.name} ${k}: suave ${contrast(s.soft, s.bg).toFixed(2)}`);
    }
    // Una paleta de cartel: superficies distintas, una clara y una oscura.
    assert.equal(new Set([p.hero.bg, p.alt.bg, p.paper.bg, p.night.bg]).size, 4);
    assert.ok(contrast(p.paper.bg, p.night.bg) >= 7, `${p.name}: papel frente a noche`);
  }
});

test('identidad estable por grabación y con variación real entre canciones', () => {
  assert.deepEqual(trackArt(HOODLUM), trackArt(HOODLUM));
  const all = Array.from({ length: 400 }, (_, i) => trackArt(`${i.toString(16).padStart(8, '0')}-0000-4000-8000-${i * 7919}`));
  assert.equal(new Set(all.map((a) => a.palette.name)).size, ART_PALETTES.length);
  assert.equal(new Set(all.map((a) => a.trio.key)).size, TRIOS.length);
  assert.equal(new Set(all.map((a) => a.hero)).size, HEROES.length);
  assert.ok(new Set(all.map((a) => `${a.palette.name}|${a.trio.key}|${a.hero}`)).size > 150);
  for (const t of TRIOS) assert.notEqual(t.title.family, t.voice.family, `${t.key}: dos voces distintas`);
});

test('Hoodlum, Lovelee Dae y Desire son tres composiciones distintas, no la misma plantilla recoloreada', () => {
  const arts = [HOODLUM, LOVELEE, DESIRE].map(trackArt);
  for (const trait of ['palette', 'trio', 'hero'] as const) {
    assert.equal(new Set(arts.map((a) => JSON.stringify(a[trait]))).size, 3, trait);
  }
});

test('V5.4: base común para todas las fichas, con texto crema legible y acentos vivos por canción', () => {
  for (const [k, sf] of Object.entries(SHEET)) {
    assert.ok(contrast(sf.ink, sf.bg) >= 7, `${k}: tinta ${contrast(sf.ink, sf.bg).toFixed(2)}`);
    assert.ok(contrast(sf.soft, sf.bg) >= 4.5, `${k}: suave ${contrast(sf.soft, sf.bg).toFixed(2)}`);
  }
  assert.notEqual(SHEET.base.bg, '#000000', 'nunca negro puro');
  const accents = ART_PALETTES.map((p) => sheetAccent(p));
  for (const [i, a] of accents.entries()) {
    const name = ART_PALETTES[i].name;
    for (const bg of [SHEET.base.bg, SHEET.raised.bg]) assert.ok(contrast(a.color, bg) >= 4.5, `${name}: acento ${contrast(a.color, bg).toFixed(2)}`);
    assert.ok(contrast(a.ink, a.color) >= 4.5, `${name}: texto sobre el acento`);
  }
  assert.ok(new Set(accents.map((a) => a.color)).size >= 6, 'los acentos diferencian las canciones');
});

test('perfiles de artista sobre la misma base: su acento sigue siendo legible en todas las superficies', () => {
  for (const p of PALETTES) {
    for (const bg of [SHEET.base.bg, SHEET.raised.bg, SHEET.deep.bg]) assert.ok(contrast(p.glow, bg) >= 4.5, `${p.name}: ${contrast(p.glow, bg).toFixed(2)}`);
  }
});
