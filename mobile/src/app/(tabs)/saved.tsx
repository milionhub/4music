/** Guardados v5: biblioteca de canciones encontradas en TrackDNA, guardada solo en este dispositivo. */
import { router } from 'expo-router';
import { Alert, Pressable, StyleSheet, Text, useWindowDimensions, View } from 'react-native';
import Animated, { FadeIn, ReduceMotion } from 'react-native-reanimated';

import { CoverPlate, EmptyPoster, Kicker, ScreenPoster, TagPill } from '@/components/editorial';
import { openTrack } from '@/components/track';
import { Screen } from '@/components/ui';
import { C, Fonts, MaxContentWidth, Radius, Space } from '@/constants/theme';
import { fixedIdentity, identityFor, surfaces } from '@/lib/artist-identity';
import { duration, withUniqueKeys } from '@/lib/format';
import { useLibrary } from '@/state/library';
import type { SavedTrack } from '@/storage/local-store';

const ID = fixedIdentity('Ácido', 'anton');

export default function Saved() {
  const lib = useLibrary();
  const { width } = useWindowDimensions();
  const S = surfaces(ID.palette);
  const tracks = lib.savedTracks;

  function confirmRemove(t: SavedTrack) {
    Alert.alert(`¿Quitar «${t.title}»?`, 'Dejará de estar en Guardados. Podrás volver a guardarla desde TrackDNA.', [
      { text: 'Cancelar', style: 'cancel' },
      { text: 'Quitar', style: 'destructive', onPress: () => lib.removeTrack(t) },
    ]);
  }

  return (
    <Screen background={S.screen} topTint={ID.palette.bg}>
      <View style={{ marginHorizontal: -Space.lg, marginTop: -Space.lg }}>
        <ScreenPoster id={ID} width={Math.min(width, MaxContentWidth)} word="Guardados" kicker="Tu biblioteca"
          figure={tracks.length ? String(tracks.length).padStart(2, '0') : undefined}
          subtitle={tracks.length ? `${tracks.length} ${tracks.length === 1 ? 'canción' : 'canciones'} · solo en este dispositivo` : undefined} />
      </View>
      {tracks.length === 0 ? (
        <EmptyPoster id={ID} glyph="♡" title="Tu biblioteca está vacía" message="Busca una canción en TrackDNA y pulsa «Guardar canción»: aparecerá aquí, también sin conexión."
          actionLabel="Buscar en TrackDNA" onAction={() => router.navigate('/trackdna')} />
      ) : (
        <View style={{ gap: Space.sm }}>
          {withUniqueKeys(tracks, (t) => t.mbid).map(({ key, item }, i) => (
            <SavedRow key={key} track={item} index={i} onRemove={() => confirmRemove(item)} />
          ))}
        </View>
      )}
    </Screen>
  );
}

function SavedRow({ track, index, onRemove }: { track: SavedTrack; index: number; onRemove: () => void }) {
  const P = identityFor(track.mbid).palette;
  const S = surfaces(ID.palette);
  const meta = [track.year, duration(track.length_ms), track.label].filter(Boolean).join(' · ');
  return (
    <Animated.View entering={FadeIn.delay(Math.min(index, 8) * 40).duration(250).reduceMotion(ReduceMotion.System)}>
      <Pressable
        onPress={() => openTrack(track.mbid)}
        onLongPress={onRemove}
        delayLongPress={450}
        accessibilityRole="button"
        accessibilityLabel={[track.title, track.artist_name, track.version, meta, 'Abrir ficha'].filter(Boolean).join(', ')}
        accessibilityActions={[{ name: 'remove', label: 'Quitar de Guardados' }]}
        onAccessibilityAction={(e) => e.nativeEvent.actionName === 'remove' && onRemove()}
        style={({ pressed }) => [styles.row, { backgroundColor: S.raised, borderColor: S.line }, pressed && { borderColor: P.glow }]}>
        <View style={[styles.edge, { backgroundColor: P.glow }]} />
        <CoverPlate uri={track.cover_url} seed={track.mbid} title={track.title} size={68} />
        <View style={{ flex: 1, gap: 3 }}>
          <Text style={styles.title} numberOfLines={2}>{track.title}</Text>
          <Text style={styles.artist} numberOfLines={1}>{track.artist_name}</Text>
          {track.version ? <TagPill label={track.version} color={P.glow} ink={P.onGlow} /> : null}
          {meta ? <Kicker size={10} style={{ letterSpacing: 0.4 }}>{meta}</Kicker> : null}
        </View>
        <Pressable onPress={onRemove} accessibilityRole="button" accessibilityLabel={`Quitar ${track.title} de Guardados`} hitSlop={10}
          style={({ pressed }) => [styles.remove, { borderColor: S.line }, pressed && { borderColor: C.danger }]}>
          <Text style={styles.removeLabel}>✕</Text>
        </Pressable>
      </Pressable>
    </Animated.View>
  );
}

const styles = StyleSheet.create({
  row: { flexDirection: 'row', alignItems: 'center', gap: Space.md, paddingVertical: Space.sm, paddingRight: Space.sm, borderRadius: Radius.md, borderWidth: 1, overflow: 'hidden' },
  edge: { width: 5, alignSelf: 'stretch' },
  // V5.4: Anton (la voz del cartel de Guardados) en caja normal: misma tipografía para todos los títulos, compacta para
  // los largos y con más presencia que la serif clásica.
  title: { color: C.text, fontFamily: Fonts.display, fontSize: 20, lineHeight: 25, letterSpacing: 0.3, includeFontPadding: false },
  artist: { color: C.muted, fontFamily: Fonts.sansBold, fontSize: 14 },
  remove: { width: 38, height: 38, borderRadius: 19, borderWidth: 1.5, alignItems: 'center', justifyContent: 'center' },
  removeLabel: { color: C.muted, fontSize: 14, fontWeight: '900' },
});
