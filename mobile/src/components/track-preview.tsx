/**
 * Extracto de 30 s de Deezer (V6.1, uso no comercial) dentro de «Escuchar». La URL la firma Deezer y caduca en minutos:
 * se pide al backend al pulsar, nunca antes ni se guarda, y el audio se reproduce en streaming (sus guidelines prohíben
 * guardarlo en el dispositivo). Solo aparece si el backend ha identificado la misma grabación (`deezer_url`).
 */
import { setAudioModeAsync, useAudioPlayer, useAudioPlayerStatus } from 'expo-audio';
import { openBrowserAsync } from 'expo-web-browser';
import { useEffect, useState } from 'react';
import { ActivityIndicator, Platform, Pressable, StyleSheet, Text, View } from 'react-native';

import { Fonts, Radius, Space } from '@/constants/theme';
import { SHEET } from '@/lib/track-art';
import { getTrackPreview } from '@/services/music';

const BROWSER_OPTIONS = Platform.OS === 'android' ? { createTask: false } : undefined;
const MONO = { fontFamily: 'SpaceMono-Bold', fontSize: 10, letterSpacing: 1.4, textTransform: 'uppercase' as const };

type Phase = 'idle' | 'loading' | 'ready' | 'none';

const clock = (s: number) => `0:${String(Math.max(0, Math.floor(s))).padStart(2, '0')}`;

export function PreviewPlayer({ mbid, deezerUrl, accent }: { mbid: string; deezerUrl: string; accent: string }) {
  const B = SHEET.base;
  const player = useAudioPlayer(null);
  const status = useAudioPlayerStatus(player);
  const [phase, setPhase] = useState<Phase>('idle');

  useEffect(() => {
    if (phase === 'ready' && status.isLoaded && !status.playing && status.currentTime === 0) player.play();
  }, [phase, status.isLoaded, status.playing, status.currentTime, player]);

  async function toggle() {
    if (phase === 'ready') {
      if (status.playing) return player.pause();
      if (status.didJustFinish || (status.duration > 0 && status.currentTime >= status.duration - 0.2)) await player.seekTo(0);
      return player.play();
    }
    setPhase('loading');
    const res = await getTrackPreview(mbid);
    if (!res.ok || !res.data.url) return setPhase('none');
    await setAudioModeAsync({ playsInSilentMode: true }).catch(() => undefined);
    player.replace({ uri: res.data.url });
    setPhase('ready');
  }

  const playing = phase === 'ready' && status.playing;
  const label = phase === 'none' ? 'Extracto no disponible' : playing ? 'Pausar extracto' : 'Escuchar extracto';
  const progress = status.duration > 0 ? Math.min(1, status.currentTime / status.duration) : 0;

  return (
    <View style={{ gap: Space.sm, paddingBottom: Space.md }}>
      <Pressable onPress={toggle} disabled={phase === 'loading' || phase === 'none'} accessibilityRole="button"
        accessibilityLabel={`${label} de 30 segundos (Deezer)`} accessibilityState={{ disabled: phase === 'none', busy: phase === 'loading' }}
        style={({ pressed }) => [styles.row, { borderColor: B.ink }, pressed && { opacity: 0.7 }]}>
        <View style={[styles.button, { backgroundColor: phase === 'none' ? B.soft : accent }]}>
          {phase === 'loading' ? <ActivityIndicator color={B.bg} /> : <Text style={[styles.glyph, { color: B.bg }]}>{playing ? '❚❚' : '▶'}</Text>}
        </View>
        <View style={{ flex: 1, gap: 6 }}>
          <Text style={[styles.label, { color: B.ink }]} numberOfLines={1}>{label}</Text>
          <View style={[styles.track, { backgroundColor: B.line }]}>
            <View style={{ width: `${progress * 100}%`, height: '100%', backgroundColor: accent }} />
          </View>
        </View>
        <Text style={[MONO, { color: B.soft }]}>{phase === 'ready' ? `${clock(status.currentTime)} / ${clock(status.duration || 30)}` : '0:30'}</Text>
      </Pressable>
      <Text onPress={() => openBrowserAsync(deezerUrl, BROWSER_OPTIONS)} accessibilityRole="link" style={[MONO, { color: B.soft }]}>
        Extracto de 30 s · Deezer ↗
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  row: { flexDirection: 'row', alignItems: 'center', gap: Space.md, minHeight: 64, borderWidth: 1.5, borderRadius: Radius.sm, padding: Space.sm },
  button: { width: 46, height: 46, borderRadius: 23, alignItems: 'center', justifyContent: 'center' },
  glyph: { fontSize: 16, fontFamily: Fonts.sansBold },
  label: { fontFamily: Fonts.sansBold, fontSize: 16 },
  track: { height: 4, borderRadius: 2, overflow: 'hidden' },
});
