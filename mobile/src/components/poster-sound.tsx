/**
 * Carteles 4 · Pieza 2 (V6.8): el sonido del cartel y los extractos de «Para ti».
 *
 * - `PosterSound`: barras horizontales ordenadas de un solo color (el acento del evento) con el porcentaje escrito; no
 *   hace falta distinguir colores para leerlas. Y el estilo que más se repite por escenario y por día.
 * - `SnippetDeck`: un solo reproductor para los extractos de 30 s de Deezer (nunca suenan dos a la vez). La URL se pide
 *   al pulsar y no se guarda, como en TrackDNA.
 */
import { setAudioModeAsync, useAudioPlayer, useAudioPlayerStatus } from 'expo-audio';
import { createContext, type ReactNode, useCallback, useContext, useState } from 'react';
import { ActivityIndicator, Pressable, StyleSheet, Text, View } from 'react-native';

import { C, Fonts, Space } from '@/constants/theme';
import { EventCard } from '@/components/poster';
import type { EventArt } from '@/lib/poster-art';
import { type EventSound, SOUND_MIN } from '@/lib/poster-sound';
import { getTrackPreview } from '@/services/music';

export function PosterSound({ sound, art }: { sound: EventSound; art: EventArt }) {
  const P = art.palette;
  if (sound.classified < SOUND_MIN) return null;
  const groups = [...sound.stages.map((g) => ({ ...g, kind: 'stage' })), ...sound.days.map((g) => ({ ...g, kind: 'day' }))];
  return (
    <EventCard title="El sonido del cartel" art={art} right={`${sound.classified} de ${sound.total} artistas`}>
      <View style={{ gap: Space.md }}>
        {sound.families.map((f) => (
          <View key={f.family} accessible accessibilityLabel={`${f.family}: ${f.pct} %, ${f.count} ${f.count === 1 ? 'artista' : 'artistas'}${f.styles.length ? `, sobre todo ${f.styles.join(', ')}` : ''}`}
            style={{ gap: 4 }}>
            <View style={styles.barLine}>
              <Text style={styles.family} numberOfLines={1}>{f.family}</Text>
              <Text style={styles.pct}>{`${f.pct} %`}</Text>
            </View>
            <View style={[styles.track, { backgroundColor: art.surfaces.raised }]}>
              <View style={[styles.fill, { width: `${Math.max(f.pct, 2)}%`, backgroundColor: P.glow }]} />
            </View>
            {f.styles.length ? <Text style={styles.styles} numberOfLines={1}>{f.styles.join(' · ')}</Text> : null}
          </View>
        ))}
      </View>
      {groups.length ? (
        <View>
          {groups.map((g) => (
            <View key={`${g.kind}-${g.id}`} style={[styles.groupRow, { borderBottomColor: art.surfaces.line }]} accessible
              accessibilityLabel={`${g.name}: sobre todo ${g.lead}`}>
              <Text style={[styles.mono, styles.groupName, { color: C.muted }]} numberOfLines={1}>{g.name}</Text>
              <Text style={styles.group} numberOfLines={1}>{g.lead}</Text>
            </View>
          ))}
        </View>
      ) : null}
      <Text style={styles.note}>
        Estilos habituales de cada artista en Discogs, no lo que pinchará esa noche.
      </Text>
    </EventCard>
  );
}

// --- Extractos ----------------------------------------------------------------------------------------------------
type Deck = { current: string | null; phase: 'idle' | 'loading' | 'playing' | 'paused' | 'none'; failed: Set<string>; toggle: (id: string) => void };
const DeckContext = createContext<Deck | null>(null);

/** Un reproductor para todos los extractos de la pantalla. */
export function SnippetDeck({ children }: { children: ReactNode }) {
  const player = useAudioPlayer(null);
  const status = useAudioPlayerStatus(player);
  const [current, setCurrent] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [failed, setFailed] = useState<Set<string>>(() => new Set());

  const toggle = useCallback(async (id: string) => {
    if (id === current) {
      if (status.playing) return player.pause();
      // Terminado: vuelve a empezar.
      if (status.duration > 0 && status.currentTime >= status.duration - 0.2) await player.seekTo(0);
      return player.play();
    }
    player.pause();
    setCurrent(id);
    setLoading(true);
    const res = await getTrackPreview(id);
    setLoading(false);
    if (!res.ok || !res.data.url) {
      setFailed((prev) => new Set(prev).add(id));
      setCurrent(null);
      return;
    }
    await setAudioModeAsync({ playsInSilentMode: true }).catch(() => undefined);
    player.replace({ uri: res.data.url });
    player.play();
  }, [current, player, status.playing, status.duration, status.currentTime]);

  const phase: Deck['phase'] = loading ? 'loading' : !current ? 'idle' : status.playing ? 'playing' : 'paused';
  return <DeckContext.Provider value={{ current, phase, failed, toggle: (id) => void toggle(id) }}>{children}</DeckContext.Provider>;
}

/** Extracto de un tema esencial: botón pequeño con el título. Sin extracto disponible, desaparece. */
export function Snippet({ id, title, accent, onAccent }: { id: string; title: string; accent: string; onAccent: string }) {
  const deck = useContext(DeckContext);
  if (!deck || deck.failed.has(id)) return null;
  const mine = deck.current === id;
  const playing = mine && deck.phase === 'playing';
  const loading = mine && deck.phase === 'loading';
  return (
    <Pressable onPress={() => deck.toggle(id)} accessibilityRole="button" hitSlop={6}
      accessibilityLabel={`${playing ? 'Pausar' : 'Escuchar'} extracto de 30 segundos de «${title}» (Deezer)`}
      accessibilityState={{ busy: loading }}
      style={({ pressed }) => [styles.snippet, { borderColor: accent }, playing && { backgroundColor: accent }, pressed && { opacity: 0.75 }]}>
      <View style={[styles.play, { backgroundColor: playing ? onAccent : accent }]}>
        {loading ? <ActivityIndicator size="small" color={onAccent} /> : playing ? (
          <View style={{ flexDirection: 'row', gap: 3 }}>
            <View style={[styles.pauseBar, { backgroundColor: accent }]} />
            <View style={[styles.pauseBar, { backgroundColor: accent }]} />
          </View>
        ) : <View style={[styles.tri, { borderLeftColor: onAccent }]} />}
      </View>
      <Text style={[styles.snippetText, { color: playing ? onAccent : C.text }]} numberOfLines={1}>{`«${title}»`}</Text>
      <Text style={[styles.mono, { color: playing ? onAccent : C.muted }]}>0:30</Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  mono: { fontFamily: Fonts.monoBold, fontSize: 11, letterSpacing: 1.3, textTransform: 'uppercase' },
  barLine: { flexDirection: 'row', alignItems: 'baseline', justifyContent: 'space-between', gap: Space.md },
  family: { color: C.text, fontFamily: Fonts.sansBold, fontSize: 16, lineHeight: 22, flexShrink: 1 },
  pct: { color: C.text, fontFamily: Fonts.monoBold, fontSize: 13 },
  track: { height: 8, borderRadius: 4, overflow: 'hidden' },
  fill: { height: '100%', borderRadius: 4 },
  styles: { color: C.muted, fontFamily: Fonts.mono, fontSize: 11 },
  groupRow: { flexDirection: 'row', alignItems: 'baseline', gap: Space.md, paddingVertical: Space.sm, borderBottomWidth: StyleSheet.hairlineWidth },
  groupName: { width: 96 },
  group: { color: C.text, fontFamily: Fonts.sansBold, fontSize: 15, flex: 1, textTransform: 'capitalize' },
  note: { color: C.faint, fontFamily: Fonts.mono, fontSize: 11, lineHeight: 16 },
  snippet: { flexDirection: 'row', alignItems: 'center', gap: Space.sm, alignSelf: 'flex-start', maxWidth: '100%', borderWidth: 1.5,
    borderRadius: 999, paddingLeft: 4, paddingRight: Space.md, paddingVertical: 4, marginTop: 4 },
  play: { width: 30, height: 30, borderRadius: 15, alignItems: 'center', justifyContent: 'center' },
  tri: { marginLeft: 2, width: 0, height: 0, borderTopWidth: 6, borderBottomWidth: 6, borderLeftWidth: 10,
    borderTopColor: 'transparent', borderBottomColor: 'transparent' },
  pauseBar: { width: 3, height: 11, borderRadius: 1 },
  snippetText: { fontFamily: Fonts.sansBold, fontSize: 14, flexShrink: 1 },
});
