/** v5 + Carteles 3.1–3.4: navegación inferior con cinco destinos reales (sin «Buscar»), sin rutas huérfanas ni enlaces a Explorar. */
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
  assert.deepEqual(triggers, ['index', 'trackdna', 'posters', 'saved', 'profile']);
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
  // Excepción aprobada en Carteles 3.5: la vista rápida solo con derechos verificables y crédito accesible.
  const sheet = readFileSync(join(SRC, 'components', 'poster-artist.tsx'), 'utf8');
  assert.ok(/verifiablePhoto\(data\.image\)/.test(sheet) && /spotlightCredits\(photo, spotlight\)/.test(sheet));
});

test('Carteles 3.4–3.5B: la vista rápida abre el perfil en la pila y es estado del evento (no un Modal)', () => {
  const sheet = readFileSync(join(SRC, 'components', 'poster-artist.tsx'), 'utf8');
  const event = readFileSync(join(SRC, 'app', 'poster', '[id].tsx'), 'utf8');
  assert.ok(sheet.includes('router.push(`/artist/${mbid}`)'));
  // 3.5B: la vista rápida presenta al artista; canciones y TrackDNA se abren desde el perfil completo.
  assert.ok(!sheet.includes('/track/') && sheet.includes('Explorar perfil y música'));
  assert.ok(!/<Modal\b/.test(sheet), 'un Modal nativo quedaría por encima del perfil apilado');
  assert.ok(/router\.setParams\(\{ set: setId, artist: artistId \}\)/.test(event));
  assert.ok(/<FlatList\b/.test(event) && /stickyHeaderIndices/.test(event), 'line-up virtualizado con filtros fijos');
  assert.ok(/BackHandler/.test(sheet), 'Atrás en Android cierra la hoja');
  // 3.5C: la animación de entrada va en un marco de tamaño fijo; la tarjeta (sin animación de layout) se ajusta al
  // contenido y desplaza a partir del 100 %. Así, una ficha que llega durante la animación no deja la hoja a media altura.
  const frame = sheet.match(/<Animated\.View entering=\{SlideInDown[^>]*>/s)?.[0] ?? '';
  assert.ok(frame.includes('styles.frame') && !/maxHeight|styles\.sheet/.test(frame), 'el nodo animado no depende del contenido');
  assert.ok(/frame: \{ position: 'absolute', left: 0, right: 0, bottom: 0/.test(sheet) && /top: insets\.top \+ Space\.xl/.test(sheet));
  assert.ok(/sheet: \{ maxHeight: '100%', flexShrink: 1/.test(sheet) && /scroll: \{ flexGrow: 0, flexShrink: 1 \}/.test(sheet));
  assert.ok(/<ScrollView key=\{artistId\}/.test(sheet), 'cada artista del B2B empieza arriba');
  assert.ok(!/height: \d+[^,]*, *\/\/ hoja|styles\.sheet, \{ height/.test(sheet), 'sin altura rígida en la hoja');
  // El botón está dentro del ScrollView: siempre alcanzable desplazando.
  const scroll = sheet.slice(sheet.indexOf('function LinkedArtist'));
  assert.ok(scroll.includes('Explorar perfil y música'));
  // 3.5C: sin líneas de créditos en el flujo; todo tras ⓘ «Fuentes y créditos».
  assert.ok(!/Extracto adaptado de |' · Datos: '|creditToggle/.test(sheet) && sheet.includes('Fuentes y créditos'));
});
