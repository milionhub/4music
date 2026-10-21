/** v5: navegación inferior con cuatro destinos reales (sin «Buscar»), sin rutas huérfanas ni enlaces a Explorar. */
import assert from 'node:assert/strict';
import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join } from 'node:path';
import { test } from 'node:test';

const SRC = join(import.meta.dirname, '..', 'src');
const TABS = join(SRC, 'app', '(tabs)');

function files(dir: string): string[] {
  return readdirSync(dir).flatMap((f) => (statSync(join(dir, f)).isDirectory() ? files(join(dir, f)) : [join(dir, f)]));
}

test('la barra inferior declara exactamente las pantallas de (tabs), en orden, y no hay pestaña Buscar', () => {
  const layout = readFileSync(join(TABS, '_layout.tsx'), 'utf8');
  const triggers = [...layout.matchAll(/NativeTabs\.Trigger name="([^"]+)"/g)].map((m) => m[1]);
  assert.deepEqual(triggers, ['index', 'trackdna', 'saved', 'profile']);
  const screens = readdirSync(TABS).filter((f) => f.endsWith('.tsx') && f !== '_layout.tsx').map((f) => f.replace('.tsx', '')).sort();
  assert.deepEqual(screens, [...triggers].sort());
  assert.ok(!/Explorar|Buscar<\/NativeTabs/.test(layout));
});

test('ningún enlace apunta a la antigua pestaña Explorar y las rutas usadas existen', () => {
  const sources = files(SRC).filter((f) => f.endsWith('.tsx') || f.endsWith('.ts')).map((f) => readFileSync(f, 'utf8')).join('\n');
  assert.ok(!sources.includes("'/explore'"));
  for (const route of ['/trackdna', '/saved', '/onboarding', '/track/[mbid]', '/artist/[mbid]']) {
    assert.ok(sources.includes(`'${route}`), `uso de ${route}`);
  }
  for (const file of ['app/track/[mbid].tsx', 'app/artist/[mbid].tsx', 'app/onboarding.tsx', 'app/(tabs)/trackdna.tsx', 'app/(tabs)/saved.tsx']) {
    assert.ok(statSync(join(SRC, file)).isFile(), file);
  }
});

test('sin fotos de artistas en la interfaz (se conservan las portadas de lanzamientos)', () => {
  const ui = files(SRC).filter((f) => f.endsWith('.tsx')).map((f) => readFileSync(f, 'utf8')).join('\n');
  assert.ok(!/ArtistPhoto|useArtistImage|PhotoCredit|getArtistImage/.test(ui));
  assert.ok(/cover_url/.test(ui));
});
