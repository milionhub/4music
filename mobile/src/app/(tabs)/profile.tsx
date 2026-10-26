/**
 * Perfil V6.7: «Tu pase», sin cuenta. Un pase de club hecho con lo que vive en este dispositivo: cifras de tu
 * biblioteca, lo que se repite en ella (tu sonido), tus artistas de partida y los estilos que te gustan (Tu frecuencia
 * los usa). Ajustes, conexión y fuentes, plegados en la sala de máquinas.
 */
import { router } from 'expo-router';
import { type ReactNode, useState } from 'react';
import { Pressable, StyleSheet, Text, useWindowDimensions, View } from 'react-native';

import { ArtistMark, decorative, Kicker, ScreenPoster } from '@/components/editorial';
import { type Stat, StatStrip } from '@/components/library';
import { Screen } from '@/components/ui';
import { getApiConfig } from '@/config/api';
import { EDITORIAL_STYLES } from '@/constants/styles';
import { C, Fonts, MaxContentWidth, Radius, Space } from '@/constants/theme';
import { fixedIdentity, surfaces } from '@/lib/artist-identity';
import { libraryStats, totalTime, yearSpan } from '@/lib/library-stats';
import { checkHealth } from '@/services/health';
import { useLibrary } from '@/state/library';

const ID = fixedIdentity('Ultravioleta', 'anton');
const P = ID.palette;
const S = surfaces(P);
/** Inclinación fija de cada pegatina de estilo (la misma siempre: que no baile al pulsar). */
const TILTS = [-3, 2, -1.5, 3, -2.5, 1, -3.5, 2.5, -1, 1.5];

type Health = { kind: 'idle' } | { kind: 'loading' } | { kind: 'ok' } | { kind: 'error'; message: string };

export default function Profile() {
  const lib = useLibrary();
  const { width } = useWindowDimensions();
  const pageWidth = Math.min(width, MaxContentWidth);
  const stats = libraryStats(lib.savedTracks);
  const chosen = lib.preferences.declared_styles;
  const toggle = (s: string) => lib.setDeclaredStyles(chosen.includes(s) ? chosen.filter((x) => x !== s) : [...chosen, s]);

  const strip: Stat[] = [
    { label: 'Canciones', value: String(stats.count).padStart(2, '0') },
    { label: 'Artistas', value: String(lib.favorites.length).padStart(2, '0') },
    totalTime(stats.totalMs) ? { label: 'De música', value: totalTime(stats.totalMs)! } : null,
  ].filter((x): x is Stat => !!x);

  const sound = [
    stats.artists[0] && { label: 'El artista que más guardas', value: stats.artists[0].name, note: `${stats.artists[0].count} canciones` },
    stats.labels[0] && { label: 'Tu sello', value: stats.labels[0].name, note: `${stats.labels[0].count} canciones` },
    yearSpan(stats.years) && stats.years!.from !== stats.years!.to && { label: 'Tu época', value: yearSpan(stats.years)!, note: 'de la más antigua a la más nueva' },
  ].filter((x): x is { label: string; value: string; note: string } => !!x);

  return (
    <Screen background={S.screen} topTint={P.bg}>
      <View style={{ marginHorizontal: -Space.lg, marginTop: -Space.lg }}>
        <ScreenPoster id={ID} width={pageWidth} word="Tu pase" kicker="Sin cuenta · vive en este móvil">
          <StatStrip stats={strip} ink={P.ink} size={strip.length > 2 ? 26 : 30} />
        </ScreenPoster>
      </View>

      <Block title="Tu sonido" action={stats.count ? { label: 'Guardados', onPress: () => router.navigate('/saved') } : undefined}>
        {sound.length ? sound.map((s) => (
          <View key={s.label} style={[styles.soundRow, { borderBottomColor: S.line }]} accessible accessibilityLabel={`${s.label}: ${s.value}, ${s.note}`}>
            <Text style={[styles.mono, { color: P.glow }]}>{s.label}</Text>
            <Text style={styles.soundValue} numberOfLines={2}>{s.value}</Text>
            <Text style={styles.note}>{s.note}</Text>
          </View>
        )) : (
          <Text style={styles.body}>Cuando guardes unas cuantas canciones, aquí aparecerá lo que se repite: tu artista, tu sello, tu época.</Text>
        )}
      </Block>

      <Block title={`Artistas de partida · ${lib.favorites.length}`} action={{ label: 'Editar', onPress: () => router.push('/onboarding?mode=edit') }}>
        {lib.favorites.length ? (
          <View style={styles.artists}>
            {lib.favorites.slice(0, 12).map((f) => (
              <Pressable key={f.mbid} onPress={() => router.push({ pathname: '/artist/[mbid]', params: { mbid: f.mbid } })}
                accessibilityRole="button" accessibilityLabel={`Abrir ${f.name}`} style={({ pressed }) => [styles.artist, pressed && { opacity: 0.7 }]}>
                <ArtistMark mbid={f.mbid} name={f.name} size={56} />
                <Text style={styles.artistName} numberOfLines={2}>{f.name}</Text>
              </Pressable>
            ))}
          </View>
        ) : (
          <Text style={styles.body}>Elige artistas para que Inicio parta de ellos.</Text>
        )}
      </Block>

      <Block title="Estilos que te gustan">
        <View style={styles.stickers}>
          {EDITORIAL_STYLES.map((s, i) => {
            const on = chosen.includes(s);
            return (
              <Pressable key={s} onPress={() => toggle(s)} accessibilityRole="checkbox" accessibilityState={{ checked: on }} accessibilityLabel={s}
                hitSlop={4} style={({ pressed }) => [styles.sticker, { transform: [{ rotate: `${TILTS[i % TILTS.length]}deg` }] },
                  on ? { backgroundColor: P.pop, borderColor: P.pop } : { borderColor: S.line }, pressed && { opacity: 0.8 }]}>
                <Text style={[styles.stickerText, { color: on ? P.onGlow : C.muted }]}>{s}</Text>
              </Pressable>
            );
          })}
        </View>
        <Text style={styles.note}>Tu frecuencia, en Inicio, los usa para proponerte canciones.</Text>
      </Block>

      <EngineRoom discarded={lib.discarded.length} onResetDiscarded={lib.resetDiscarded} />
    </Screen>
  );
}

/** Bloque con rótulo de cartel (filete y mono) y una acción opcional a la derecha. */
function Block({ title, action, children }: { title: string; action?: { label: string; onPress: () => void }; children: ReactNode }) {
  return (
    <View style={{ gap: Space.md }}>
      <View style={[styles.blockHead, { borderTopColor: P.glow }]}>
        <Text accessibilityRole="header" style={[styles.mono, { color: P.glow, flex: 1 }]}>{title}</Text>
        {action ? (
          <Pressable onPress={action.onPress} accessibilityRole="button" hitSlop={10}>
            <Text style={[styles.mono, { color: C.text }]}>{`${action.label} ↗`}</Text>
          </Pressable>
        ) : null}
      </View>
      {children}
    </View>
  );
}

/** Ajustes y créditos, plegados: conexión con el servidor, descartados y fuentes de datos. */
function EngineRoom({ discarded, onResetDiscarded }: { discarded: number; onResetDiscarded: () => void }) {
  const [open, setOpen] = useState(false);
  const [health, setHealth] = useState<Health>({ kind: 'idle' });
  const api = getApiConfig();

  async function runCheck() {
    if (!api.ok) return setHealth({ kind: 'error', message: api.reason });
    setHealth({ kind: 'loading' });
    const result = await checkHealth(api.baseUrl);
    setHealth(result.ok ? { kind: 'ok' } : { kind: 'error', message: result.message });
  }

  return (
    <View style={[styles.engine, { backgroundColor: S.raised, borderColor: S.line }]}>
      <Pressable onPress={() => setOpen((o) => !o)} accessibilityRole="button" accessibilityState={{ expanded: open }}
        style={styles.engineHead}>
        <Text style={[styles.mono, { color: C.muted, flex: 1 }]}>Sala de máquinas</Text>
        <Text {...decorative} style={[styles.mono, { color: C.muted }]}>{open ? '−' : '+'}</Text>
      </Pressable>
      {open ? (
        <View style={{ gap: Space.lg }}>
          <View style={{ gap: Space.xs }}>
            <Kicker>Conexión con el servidor</Kicker>
            <Text selectable style={styles.note}>{api.ok ? api.baseUrl : api.reason}</Text>
            <SmallButton label={health.kind === 'loading' ? 'Comprobando…' : 'Comprobar conexión'} disabled={health.kind === 'loading'} onPress={runCheck} />
            {health.kind === 'ok' ? <Text style={[styles.body, { color: C.acid }]}>Conectado</Text> : null}
            {health.kind === 'error' ? <Text style={[styles.body, { color: C.danger }]}>{health.message}</Text> : null}
          </View>
          <View style={{ gap: Space.xs }}>
            <Kicker>{`Artistas descartados · ${discarded}`}</Kicker>
            <SmallButton label="Volver a mostrarlos" disabled={!discarded} onPress={onResetDiscarded} />
          </View>
          <View style={{ gap: Space.xs }}>
            <Kicker>Fuentes</Kicker>
            <Text style={styles.note}>
              MusicBrainz, Wikidata y Discogs (datos abiertos); Deezer (fotos, extractos de 30 s, sellos y catálogo, uso no
              comercial); ReccoBeats y AcousticBrainz (tempo y perfil sonoro estimados). Todo pasa por el servidor de
              Chromatic Underground. Tus guardados, artistas y estilos no salen de este dispositivo.
            </Text>
          </View>
        </View>
      ) : null}
    </View>
  );
}

function SmallButton({ label, disabled, onPress }: { label: string; disabled?: boolean; onPress: () => void }) {
  return (
    <Pressable onPress={onPress} disabled={disabled} accessibilityRole="button" accessibilityState={{ disabled }}
      style={({ pressed }) => [styles.small, { borderColor: S.line }, disabled && { opacity: 0.4 }, pressed && { borderColor: P.glow }]}>
      <Text style={[styles.mono, { color: C.text }]}>{label}</Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  mono: { fontFamily: Fonts.monoBold, fontSize: 11, letterSpacing: 1.3, textTransform: 'uppercase' },
  body: { color: C.muted, fontFamily: Fonts.sans, fontSize: 15, lineHeight: 21 },
  note: { color: C.faint, fontFamily: Fonts.mono, fontSize: 11, lineHeight: 16 },
  blockHead: { flexDirection: 'row', alignItems: 'center', borderTopWidth: 2, paddingTop: Space.sm, marginTop: Space.md },
  soundRow: { gap: 2, paddingBottom: Space.md, borderBottomWidth: StyleSheet.hairlineWidth },
  soundValue: { color: C.text, fontFamily: Fonts.display, fontSize: 34, lineHeight: 40, includeFontPadding: false },
  artists: { flexDirection: 'row', flexWrap: 'wrap', gap: Space.md },
  artist: { width: 72, gap: 4 },
  artistName: { color: C.muted, fontFamily: Fonts.sansBold, fontSize: 12, lineHeight: 15 },
  stickers: { flexDirection: 'row', flexWrap: 'wrap', gap: Space.sm, paddingVertical: Space.xs },
  sticker: { borderWidth: 2, borderRadius: Radius.sm, paddingHorizontal: Space.md, paddingVertical: Space.sm },
  stickerText: { fontFamily: Fonts.display, fontSize: 20, lineHeight: 24, letterSpacing: 0.4, textTransform: 'uppercase', includeFontPadding: false },
  engine: { borderWidth: 1, borderRadius: Radius.md, padding: Space.lg, gap: Space.lg, marginTop: Space.lg },
  engineHead: { flexDirection: 'row', alignItems: 'center' },
  small: { alignSelf: 'flex-start', borderWidth: 1.5, borderRadius: 999, paddingHorizontal: Space.md, paddingVertical: Space.sm, marginTop: Space.xs },
});
