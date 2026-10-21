/**
 * Ficha TrackDNA V5.4: misma marca, distintas canciones. Cartel con la identidad de la canción (lib/track-art.ts) y,
 * debajo, siempre el mismo orden sobre la base común: ADN musical, La historia del track, Artistas, Versiones y
 * Escuchar. Qué entra en cada bloque se decide en lib/track-sheet.ts; un bloque sin nada real no se muestra.
 */
import { router, useLocalSearchParams } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import type { ReactElement } from 'react';
import { Pressable, StyleSheet, Text, useWindowDimensions, View } from 'react-native';
import Animated, { FadeIn, ReduceMotion } from 'react-native-reanimated';
import { SafeAreaView } from 'react-native-safe-area-context';

import { SheetSection } from '@/components/sheet';
import { StatusBarScrim } from '@/components/status-bar-scrim';
import {
  ArtDivider, ArtHero, ArtistList, ArtSave, DnaCard, GUTTER, heroTop, ListenList, StoryCard, VersionList,
} from '@/components/track-art';
import { StateView } from '@/components/ui';
import { C, MaxContentWidth, Radius, Space } from '@/constants/theme';
import { useRemote } from '@/hooks/use-remote';
import { contrast } from '@/lib/artist-identity';
import { listenOptions } from '@/lib/format';
import { savedTrackFrom } from '@/lib/preferences';
import { SHEET, sheetAccent, type TrackArt, trackArt } from '@/lib/track-art';
import { hasDna, trackArtists, trackDna, trackStory, trackVersions } from '@/lib/track-sheet';
import { describeError } from '@/services/api-client';
import { getTrack } from '@/services/music';
import { useLibrary } from '@/state/library';
import type { TrackResponse } from '@/types/music';

function goBack() {
  if (router.canGoBack()) router.back();
  else router.replace('/trackdna');
}

/** Iconos de la barra de estado legibles sobre el color de arriba del cartel. */
const barStyle = (bg: string) => (contrast('#000000', bg) > contrast('#FFFFFF', bg) ? 'dark' : 'light');

export default function TrackScreen() {
  const { mbid } = useLocalSearchParams<{ mbid: string }>();
  const { state, reload } = useRemote(mbid ?? null, () => getTrack(mbid));
  const data = state.status === 'success' ? state.data : null;
  const notFound = state.status === 'error' && state.error.code === 'not_found';
  const art = trackArt(data?.mbid ?? mbid ?? '');
  const top = heroTop(art);

  return (
    <SafeAreaView style={[styles.screen, { backgroundColor: top }]} edges={['left', 'right']}>
      <StatusBar style={barStyle(top)} />
      {data ? (
        <TrackProfile data={data} art={art} />
      ) : (
        <SafeAreaView edges={['top']} style={{ flex: 1, padding: GUTTER, gap: Space.xl }}>
          <BackButton art={art} />
          {state.status === 'error' ? (
            <StateView
              kind="error"
              title={notFound ? 'Canción no encontrada' : 'No se pudo cargar la canción'}
              message={notFound ? 'Esta grabación ya no existe en el catálogo (puede haberse fusionado o eliminado).' : describeError(state.error)}
              actionLabel={notFound ? undefined : 'Reintentar'}
              onAction={notFound ? undefined : reload}
            />
          ) : (
            <LoadingSkeleton art={art} />
          )}
        </SafeAreaView>
      )}
    </SafeAreaView>
  );
}

/** Volver: la tinta del cartel sobre un disco del color de fondo (legible sobre cualquier composición). */
function BackButton({ art }: { art: TrackArt }) {
  const s = art.hero === 'split' ? art.palette.paper : art.palette.hero;
  return (
    <Pressable onPress={goBack} accessibilityRole="button" accessibilityLabel="Volver" hitSlop={12}
      style={[styles.back, { backgroundColor: s.ink }]}>
      <Text style={[styles.backLabel, { color: s.bg }]}>←</Text>
    </Pressable>
  );
}

/** Mientras carga, ya con los colores de la canción: la llegada del cartel no es un salto de color. */
function LoadingSkeleton({ art }: { art: TrackArt }) {
  const s = art.hero === 'split' ? art.palette.paper : art.palette.hero;
  const bars: [`${number}%`, number][] = [['85%', 56], ['60%', 56], ['100%', 200], ['50%', 20]];
  return (
    <View style={{ gap: Space.lg }} accessibilityLabel="Cargando la canción" accessibilityLiveRegion="polite">
      {bars.map(([w, h], i) => <View key={i} style={[styles.skeleton, { width: w, height: h, backgroundColor: s.line }]} />)}
    </View>
  );
}

function TrackProfile({ data, art }: { data: TrackResponse; art: TrackArt }) {
  const lib = useLibrary();
  const { width } = useWindowDimensions();
  const P = art.palette;
  const pageWidth = Math.min(width, MaxContentWidth);
  const saved = lib.isTrackSaved({ mbid: data.mbid, isrcs: data.isrcs, version: data.version });
  const accent = sheetAccent(P);

  // Qué se muestra (lib/track-sheet.ts): cada bloque vacío se oculta. Créditos técnicos, mashups, DJ mixes y la lectura
  // con IA siguen en la API; la ficha solo enseña lo musicalmente útil y verificable.
  const dna = trackDna(data);
  const story = trackStory(data);
  const artists = trackArtists(data);
  const versions = trackVersions(data);
  const listen = listenOptions(data.links, `${data.artist_name} ${data.title}`);
  const sections = [
    hasDna(dna) && { key: 'dna', title: 'ADN musical', body: <DnaCard dna={dna} accent={accent} width={pageWidth} /> },
    story && { key: 'story', title: 'La historia del track', body: <StoryCard story={story} accent={accent} /> },
    artists.length > 0 && { key: 'artists', title: artists.length > 1 ? 'Artistas' : 'Artista', body: <ArtistList artists={artists} /> },
    versions.length > 0 && { key: 'versions', title: 'Versiones', body: <VersionList rows={versions} accent={accent} /> },
    listen.length > 0 && { key: 'listen', title: 'Escuchar', body: <ListenList options={listen} /> },
  ].filter((x): x is { key: string; title: string; body: ReactElement } => !!x);

  return (
    <>
      <Animated.ScrollView style={{ backgroundColor: SHEET.base.bg }} contentInsetAdjustmentBehavior="never">
        <View style={{ alignSelf: 'center', width: pageWidth }}>
          <ArtHero data={data} art={art} width={pageWidth} back={<BackButton art={art} />}
            footer={<ArtSave saved={saved} s={art.hero === 'split' ? P.alt : P.hero} onPress={() => lib.toggleTrack(savedTrackFrom(data, new Date().toISOString()))} />} />
          <ArtDivider art={art} width={pageWidth} word={data.title} />
          <Animated.View entering={FadeIn.duration(250).reduceMotion(ReduceMotion.System)}>
            {sections.map((sec, i) => (
              <SheetSection key={sec.key} index={String(i + 1).padStart(2, '0')} title={sec.title} accent={accent.color} last={i === sections.length - 1}>
                {sec.body}
              </SheetSection>
            ))}
            {sections.length === 0 ? <View style={{ height: Space.xxxl * 2 }} /> : null}
          </Animated.View>
        </View>
      </Animated.ScrollView>
      {/* Franja fija del color de arriba del cartel: los iconos de la barra siguen legibles al desplazar. */}
      <StatusBarScrim tint={heroTop(art)} />
    </>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: C.bg },
  back: { width: 42, height: 42, borderRadius: 21, alignItems: 'center', justifyContent: 'center' },
  backLabel: { fontSize: 20, fontWeight: '800' },
  skeleton: { borderRadius: Radius.sm },
});
