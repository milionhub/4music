/**
 * Guardados V6.7: tu cajón de discos, solo en este dispositivo. Cartel con lo que suma la biblioteca (tiempo, época,
 * sellos), la última canción guardada en grande y el resto como un tracklist numerado, con orden a elegir.
 */
import { router } from 'expo-router';
import { useState } from 'react';
import { Alert, Pressable, StyleSheet, Text, useWindowDimensions, View } from 'react-native';
import Animated, { FadeIn, ReduceMotion } from 'react-native-reanimated';

import { CoverPlate, decorative, EmptyPoster, Kicker, ScreenPoster, TagPill } from '@/components/editorial';
import { Segmented, type Stat, StatStrip } from '@/components/library';
import { openTrack } from '@/components/track';
import { Screen } from '@/components/ui';
import { C, Fonts, MaxContentWidth, Radius, Space } from '@/constants/theme';
import { fixedIdentity, identityFor, SECTION_PALETTES, surfaces } from '@/lib/artist-identity';
import { duration, withUniqueKeys } from '@/lib/format';
import { libraryStats, SORT_LABELS, type SortMode, sortSaved, totalTime, yearSpan } from '@/lib/library-stats';
import { useLibrary } from '@/state/library';
import type { SavedTrack } from '@/storage/local-store';

const ID = fixedIdentity(SECTION_PALETTES.saved, 'anton');
const P = ID.palette;
const S = surfaces(P);

export default function Saved() {
  const lib = useLibrary();
  const { width } = useWindowDimensions();
  const [mode, setMode] = useState<SortMode>('recent');
  const pageWidth = Math.min(width, MaxContentWidth);
  const tracks = lib.savedTracks;
  const stats = libraryStats(tracks);
  const sorted = sortSaved(tracks, mode);
  // La última guardada va destacada solo en «Recientes»: en los otros órdenes, la lista manda.
  const [featured, rest] = mode === 'recent' && sorted.length ? [sorted[0], sorted.slice(1)] : [null, sorted];

  const strip: Stat[] = [
    totalTime(stats.totalMs) && { label: stats.timed < stats.count ? 'De música (aprox.)' : 'De música', value: totalTime(stats.totalMs)! },
    yearSpan(stats.years) && { label: 'Época', value: yearSpan(stats.years)! },
    stats.labels[0] && { label: 'Sello que más', value: stats.labels[0].name },
  ].filter((x): x is Stat => !!x);

  function confirmRemove(t: SavedTrack) {
    Alert.alert(`¿Quitar «${t.title}»?`, 'Dejará de estar en Guardados. Podrás volver a guardarla desde TrackDNA.', [
      { text: 'Cancelar', style: 'cancel' },
      { text: 'Quitar', style: 'destructive', onPress: () => lib.removeTrack(t) },
    ]);
  }

  return (
    <Screen background={S.screen} topTint={P.bg}>
      <View style={{ marginHorizontal: -Space.lg, marginTop: -Space.lg }}>
        <ScreenPoster id={ID} width={pageWidth} word="Guardados" kicker="Tu cajón · solo en este dispositivo"
          figure={tracks.length ? String(tracks.length).padStart(2, '0') : undefined}>
          {tracks.length ? <StatStrip stats={strip} ink={P.ink} size={strip.some((s) => s.value.length > 10) ? 22 : 30} /> : null}
        </ScreenPoster>
      </View>
      {tracks.length === 0 ? (
        <EmptyPoster id={ID} glyph="♡" title="Tu cajón está vacío" message="Busca una canción en TrackDNA y pulsa «Guardar»: aparecerá aquí, también sin conexión."
          actionLabel="Buscar en TrackDNA" onAction={() => router.navigate('/trackdna')} />
      ) : (
        <View style={{ gap: Space.lg }}>
          {tracks.length > 1 ? <Segmented options={SORT_LABELS} value={mode} onChange={setMode} palette={P} label="Ordenar Guardados" /> : null}
          {featured ? <Featured track={featured} width={pageWidth - Space.lg * 2} onRemove={() => confirmRemove(featured)} /> : null}
          {rest.length ? (
            <View>
              {featured ? <Kicker color={P.glow} style={{ marginBottom: Space.xs }}>Antes en el cajón</Kicker> : null}
              {withUniqueKeys(rest, (t) => t.mbid).map(({ key, item }, i) => (
                <SavedRow key={key} track={item} index={i} number={i + (featured ? 2 : 1)} onRemove={() => confirmRemove(item)} />
              ))}
            </View>
          ) : null}
        </View>
      )}
    </Screen>
  );
}

const metaOf = (t: SavedTrack) => [t.year, duration(t.length_ms), t.label].filter(Boolean).join(' · ');

/** Última en entrar: portada grande con un bloque de color desfasado (como en la ficha) y el título en display. */
function Featured({ track, width, onRemove }: { track: SavedTrack; width: number; onRemove: () => void }) {
  const T = identityFor(track.mbid).palette;
  const cover = Math.round(Math.min(width * 0.44, 190));
  const meta = metaOf(track);
  return (
    <Animated.View entering={FadeIn.duration(250).reduceMotion(ReduceMotion.System)}>
      <Pressable onPress={() => openTrack(track.mbid)} onLongPress={onRemove} delayLongPress={450}
        accessibilityRole="button" accessibilityLabel={['Última guardada', track.title, track.artist_name, track.version, meta, 'Abrir ficha'].filter(Boolean).join(', ')}
        accessibilityActions={[{ name: 'remove', label: 'Quitar de Guardados' }]}
        onAccessibilityAction={(e) => e.nativeEvent.actionName === 'remove' && onRemove()}
        style={({ pressed }) => [styles.featured, pressed && { opacity: 0.85 }]}>
        <View style={{ width: cover + 10, height: cover + 10 }}>
          <View {...decorative} style={{ position: 'absolute', left: 10, top: 10, width: cover, height: cover, borderRadius: Radius.sm, backgroundColor: T.glow }} />
          <CoverPlate uri={track.cover_url} seed={track.mbid} title={track.title} size={cover} />
        </View>
        <View style={{ flex: 1, gap: Space.xs, justifyContent: 'flex-end' }}>
          <Kicker color={P.glow}>Última en entrar</Kicker>
          <Text style={styles.featuredTitle} numberOfLines={4}>{track.title}</Text>
          <Text style={styles.artist} numberOfLines={2}>{track.artist_name}</Text>
          {track.version ? <TagPill label={track.version} color={T.glow} ink={T.onGlow} /> : null}
          {meta ? <Text style={styles.meta} numberOfLines={2}>{meta}</Text> : null}
        </View>
      </Pressable>
    </Animated.View>
  );
}

/** Fila de tracklist: número de pista en serif cursiva, portada, título en display y quitar. */
function SavedRow({ track, index, number, onRemove }: { track: SavedTrack; index: number; number: number; onRemove: () => void }) {
  const T = identityFor(track.mbid).palette;
  const meta = metaOf(track);
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
        style={({ pressed }) => [styles.row, { borderBottomColor: S.line }, pressed && { backgroundColor: S.raised }]}>
        <Text {...decorative} style={[styles.number, { color: T.glow }]}>{String(number).padStart(2, '0')}</Text>
        <CoverPlate uri={track.cover_url} seed={track.mbid} title={track.title} size={56} />
        <View style={{ flex: 1, gap: 2 }}>
          <Text style={styles.title} numberOfLines={2}>{track.title}</Text>
          <Text style={styles.artist} numberOfLines={1}>{track.artist_name}</Text>
          {track.version ? <TagPill label={track.version} color={T.glow} ink={T.onGlow} /> : null}
          {meta ? <Text style={styles.meta} numberOfLines={1}>{meta}</Text> : null}
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
  featured: { flexDirection: 'row', gap: Space.lg, alignItems: 'stretch' },
  featuredTitle: { color: C.text, fontFamily: Fonts.display, fontSize: 32, lineHeight: 36, includeFontPadding: false },
  row: { flexDirection: 'row', alignItems: 'center', gap: Space.md, paddingVertical: Space.md, borderBottomWidth: StyleSheet.hairlineWidth },
  number: { fontFamily: Fonts.serifItalic, fontSize: 28, lineHeight: 34, width: 40 },
  // V5.4: Anton (la voz del cartel de Guardados) en caja normal: misma tipografía para todos los títulos.
  title: { color: C.text, fontFamily: Fonts.display, fontSize: 20, lineHeight: 25, letterSpacing: 0.3, includeFontPadding: false },
  artist: { color: C.muted, fontFamily: Fonts.sansBold, fontSize: 14 },
  meta: { color: C.faint, fontFamily: Fonts.mono, fontSize: 11, letterSpacing: 0.3 },
  remove: { width: 38, height: 38, borderRadius: 19, borderWidth: 1.5, alignItems: 'center', justifyContent: 'center' },
  removeLabel: { color: C.muted, fontSize: 14, fontWeight: '900' },
});
