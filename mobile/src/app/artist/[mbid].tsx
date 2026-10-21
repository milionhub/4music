/**
 * Ficha de artista — Artist Experience v4 (pantalla secundaria desde v5: se abre desde las canciones; los artistas ya
 * no se guardan en Guardados): cartel tipográfico con la identidad visual del artista (sin fotos), que se
 * prolonga en los acentos sobre la base común de las fichas (V5.4, igual que TrackDNA), «Conoce al artista», historias de
 * «Más allá de la cabina» con sus fuentes, música con criterio explícito y plataformas con iconos.
 * Solo datos verificables; cada módulo es opcional y la ficha nunca queda a medias.
 */
import { router, useLocalSearchParams } from 'expo-router';
import { openBrowserAsync } from 'expo-web-browser';
import { useMemo, useState } from 'react';
import { Pressable, StyleSheet, Text, useWindowDimensions, View } from 'react-native';
import Animated, { FadeIn, ReduceMotion, useAnimatedRef, useScrollOffset } from 'react-native-reanimated';
import { SafeAreaView } from 'react-native-safe-area-context';

import {
  ARTIST_SURFACES, ArtistCard, ArtistHero, GUTTER, NameBand, PlatformDock, ReleaseList, SectionHead, StoryBlocks, TopTrackList,
} from '@/components/artist-experience';
import { StatusBarScrim } from '@/components/status-bar-scrim';
import { Chip, Meta, Notice, StateView } from '@/components/ui';
import { C, MaxContentWidth, Radius, Space } from '@/constants/theme';
import { useRemote } from '@/hooks/use-remote';
import { alpha, type ArtistIdentity, identityFor } from '@/lib/artist-identity';
import { artistCardRows, sectionMessage, uniqueBy } from '@/lib/format';
import { SHEET } from '@/lib/track-art';
import { describeError } from '@/services/api-client';
import { getArtist, getStories } from '@/services/music';
import type { ArtistProfileResponse } from '@/types/music';

const MONO_BOLD = 'SpaceMono-Bold';

function goBack() {
  if (router.canGoBack()) router.back();
  else router.replace('/');
}

export default function ArtistScreen() {
  const { mbid } = useLocalSearchParams<{ mbid: string }>();
  const { state, reload } = useRemote(mbid ?? null, () => getArtist(mbid));
  const data = state.status === 'success' ? state.data : null;
  const id = mbid ? identityFor(data?.artist.mbid ?? mbid) : null;

  return (
    <SafeAreaView style={styles.screen} edges={['left', 'right']}>
      {data ? (
        <Profile data={data} onRetry={reload} />
      ) : (
        <SafeAreaView edges={['top']} style={{ flex: 1, padding: GUTTER, gap: Space.xl }}>
          <BackButton />
          {state.status === 'error' ? (
            <StateView kind="error" title="No se pudo cargar la ficha" message={describeError(state.error)} actionLabel="Reintentar" onAction={reload} />
          ) : (
            <LoadingSkeleton id={id} />
          )}
        </SafeAreaView>
      )}
    </SafeAreaView>
  );
}

function BackButton({ floating }: { floating?: boolean }) {
  return (
    <Pressable onPress={goBack} accessibilityRole="button" accessibilityLabel="Volver" hitSlop={12}
      style={[styles.back, floating && styles.backFloating]}>
      <Text style={styles.backLabel}>←</Text>
    </Pressable>
  );
}

/** Mientras carga, ya con la paleta del artista: la transición al cartel no es un salto de color. */
function LoadingSkeleton({ id }: { id: ArtistIdentity | null }) {
  const raised = ARTIST_SURFACES.raised;
  return (
    <View style={{ gap: Space.lg }} accessibilityLabel="Cargando ficha" accessibilityLiveRegion="polite">
      <View style={[styles.skeleton, { height: 320, backgroundColor: id ? alpha(id.palette.bg, 0.3) : C.surface }]} />
      <View style={[styles.skeleton, { height: 36, width: '70%', backgroundColor: raised }]} />
      <View style={[styles.skeleton, { height: 80, backgroundColor: raised }]} />
      <Meta>Consultando MusicBrainz, Wikidata y Discogs…</Meta>
    </View>
  );
}

function Profile({ data, onRetry }: { data: ArtistProfileResponse; onRetry: () => void }) {
  const { width } = useWindowDimensions();
  const [technical, setTechnical] = useState(false);
  const { artist, styles: artistStyles, top_tracks, recent_releases, platforms } = data;
  // Historias: se investigan aparte (caché en el servidor) para que la ficha nunca las espere.
  const storiesRemote = useRemote(`stories:${artist.mbid}`, () => getStories(artist.mbid));
  const storiesLoading = storiesRemote.state.status === 'loading' || storiesRemote.state.status === 'idle';
  const stories = storiesRemote.state.status === 'success' ? storiesRemote.state.data.stories : [];
  const id = useMemo(() => identityFor(artist.mbid), [artist.mbid]);
  const P = id.palette;
  const S = ARTIST_SURFACES;
  const heroWidth = Math.min(width, MaxContentWidth);
  const heroHeight = Math.round(Math.min(Math.max(heroWidth * 1.12, 440), 580));
  const contentWidth = heroWidth - GUTTER * 2;
  const releasesMsg = sectionMessage(data.releases_status, 'lanzamientos');
  const ident = data.identity;
  const genres = [...new Set(artistStyles.map((s) => s.label.replace(/^música /i, '')))].slice(0, 3);
  const rows = artistCardRows({ type: artist.type, identity: ident });
  const labelCredit = ident?.founded_labels?.[0] ?? ident?.run_labels?.[0];
  const credits = [ident?.country_name, labelCredit ? `Sello ${labelCredit}` : null].filter((x): x is string => Boolean(x));
  const sources = data.sources.filter((s) => s.label !== 'Foto'); // la ficha no muestra fotos
  const storySources = stories.flatMap((s) => s.sources);
  const others = artist.links.filter((l) => !l.primary);
  const scrollRef = useAnimatedRef<Animated.ScrollView>();
  const scrollY = useScrollOffset(scrollRef);

  let n = 0;
  const next = () => String(++n).padStart(2, '0');

  return (
    <>
      <Animated.ScrollView ref={scrollRef} style={{ backgroundColor: S.screen }} contentContainerStyle={{ paddingBottom: Space.xxxl * 2 }}
        contentInsetAdjustmentBehavior="never">
        <View style={{ alignSelf: 'center' }}>
          <ArtistHero name={artist.name} id={id} width={heroWidth} height={heroHeight} tags={genres} credits={credits} />
          <SafeAreaView edges={['top']} style={styles.heroTop} pointerEvents="box-none">
            <BackButton floating />
          </SafeAreaView>
        </View>
        {/* Transición del cartel a la ficha: una franja con el acento del artista */}
        <View style={{ height: 6, backgroundColor: P.pop }} />

        <Animated.View entering={FadeIn.duration(250).reduceMotion(ReduceMotion.System)} style={styles.body}>
          {artist.source.stale ? <Notice tone="warn">MusicBrainz no respondió: ficha servida desde la caché del servidor.</Notice> : null}

          <View style={{ gap: Space.md }}>
            <SectionHead index={next()} title="Conoce al artista" id={id} />
            <ArtistCard name={artist.name} id={id} rows={rows} genres={genres} />
          </View>

          {storiesLoading || stories.length ? (
            <View style={{ gap: Space.md }}>
              <SectionHead index={next()} title="Más allá de la cabina" id={id} />
              <StoryBlocks stories={stories} id={id} loading={storiesLoading} />
            </View>
          ) : null}

          <NameBand name={artist.name} id={id} width={heroWidth} />

          {/* Música: ranking solo con escuchas reales (ListenBrainz); si no, discografía documentada por fecha */}
          {top_tracks.length ? (
            <View style={{ gap: Space.md }}>
              <SectionHead index={next()} title="Temas más escuchados" id={id} />
              <TopTrackList tracks={uniqueBy(top_tracks, (t) => t.recording_mbid)} id={id} />
              <Meta>Escuchas registradas por usuarios de ListenBrainz: no son reproducciones globales de todas las plataformas.</Meta>
            </View>
          ) : recent_releases.length || releasesMsg?.retry ? (
            <View style={{ gap: Space.md }}>
              <SectionHead index={next()} title="Su música" id={id} right={<Meta>por fecha</Meta>} />
              {recent_releases.length ? (
                <ReleaseList releases={uniqueBy(recent_releases, (r) => r.mbid)} id={id} />
              ) : (
                <Notice tone="warn">
                  {releasesMsg?.text}
                  <Text style={[styles.inlineAction, { color: P.glow }]} onPress={onRetry} accessibilityRole="button">{'  '}Reintentar</Text>
                </Notice>
              )}
              {recent_releases.length ? (
                <Meta>Sin datos de escuchas para este artista: singles, EP y álbumes propios documentados en MusicBrainz, por fecha.</Meta>
              ) : null}
            </View>
          ) : null}

          {platforms.length ? (
            <View style={{ gap: Space.md }}>
              <SectionHead index={next()} title="Escuchar" id={id} />
              <PlatformDock links={uniqueBy(platforms, (l) => l.url)} id={id} width={contentWidth} />
            </View>
          ) : null}

          {/* Información técnica y fuentes (plegada) */}
          <View style={[styles.technical, { borderTopColor: S.line }]}>
            <Pressable onPress={() => setTechnical((v) => !v)} accessibilityRole="button" accessibilityState={{ expanded: technical }} style={styles.technicalHeader}>
              <Text style={styles.technicalTitle}>Información técnica y fuentes</Text>
              <Text style={[styles.chev, { color: P.glow }]}>{technical ? '−' : '+'}</Text>
            </Pressable>
            {technical ? (
              <View style={{ gap: Space.sm }}>
                <Meta selectable>MBID {artist.mbid}</Meta>
                <Meta>Identidad visual · {P.name} · {id.type.family.replace('-Italic', '')} · {id.composition}</Meta>
                {uniqueBy([...sources, ...storySources], (s) => s.url).map((item) => (
                  <Text key={item.url} style={styles.sourceLink} onPress={() => openBrowserAsync(item.url)} accessibilityRole="link">
                    {item.label}{item.license ? ` · ${item.license}` : ''}
                  </Text>
                ))}
                {stories.length ? <Meta>Historias redactadas a partir de los hechos citados y validadas frase a frase con ellos.</Meta> : null}
                {platforms.length ? <Meta>Iconos de plataformas: Simple Icons (CC0). Las marcas pertenecen a sus titulares.</Meta> : null}
                {others.length ? (
                  <View style={styles.wrap}>
                    {uniqueBy(others, (l) => l.url).map((item) => <Chip key={item.url} label={item.label} onPress={() => openBrowserAsync(item.url)} />)}
                  </View>
                ) : null}
              </View>
            ) : null}
          </View>
        </Animated.View>
      </Animated.ScrollView>
      {/* Opaca antes de que el contenido llegue a la barra de estado; en reposo, el cartel se ve entero. */}
      <StatusBarScrim scrollY={scrollY} revealAt={Math.round(heroHeight * 0.35)} />
    </>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: SHEET.base.bg },
  back: { width: 42, height: 42, borderRadius: 21, alignItems: 'center', justifyContent: 'center', backgroundColor: C.surface },
  backFloating: { backgroundColor: 'rgba(7,6,11,0.72)', marginLeft: GUTTER, marginTop: Space.sm },
  backLabel: { color: C.text, fontSize: 20, fontWeight: '800' },
  heroTop: { position: 'absolute', top: 0, left: 0, right: 0 },
  body: { paddingHorizontal: GUTTER, paddingTop: Space.xl, gap: Space.xxl, width: '100%', maxWidth: MaxContentWidth, alignSelf: 'center' },
  wrap: { flexDirection: 'row', flexWrap: 'wrap', gap: Space.sm },
  technical: { borderTopWidth: StyleSheet.hairlineWidth, paddingTop: Space.md, gap: Space.md },
  technicalHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', minHeight: 44 },
  technicalTitle: { color: SHEET.base.soft, fontFamily: MONO_BOLD, fontSize: 11, letterSpacing: 1.6, textTransform: 'uppercase' },
  chev: { fontSize: 22, fontWeight: '800' },
  sourceLink: { color: SHEET.base.soft, fontSize: 13, textDecorationLine: 'underline' },
  inlineAction: { fontWeight: '800' },
  skeleton: { borderRadius: Radius.md },
});
