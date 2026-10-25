/**
 * Ficha de artista — Artist Experience v4 (pantalla secundaria desde v5: se abre desde las canciones; los artistas ya
 * no se guardan en Guardados): cartel con la identidad visual del artista (con su foto si tiene derechos verificables, V6; si no, tipográfico), que se
 * prolonga en los acentos sobre la base común de las fichas (V5.4, igual que TrackDNA), «Conoce al artista», historias de
 * «Más allá de la cabina» con sus tracks esenciales (TrackDNA) y «Escuchar» (Spotify, Apple Music, SoundCloud y Discogs).
 * Sin bloque de fuentes ni metadatos (V6): el crédito de la foto, que su licencia exige, va sobre la foto y abre su origen.
 * Solo datos verificables; cada módulo es opcional y la ficha nunca queda a medias.
 */
import { router, useLocalSearchParams } from 'expo-router';
import { useMemo, useState } from 'react';
import { Pressable, StyleSheet, Text, useWindowDimensions, View } from 'react-native';
import Animated, { FadeIn, ReduceMotion, useAnimatedRef, useScrollOffset } from 'react-native-reanimated';
import { SafeAreaView } from 'react-native-safe-area-context';

import {
  ARTIST_SURFACES, ArtistCard, ArtistHero, EssentialTracks, GUTTER, NameBand, PlatformDock, SectionHead, StoryBlocks,
} from '@/components/artist-experience';
import { StatusBarScrim } from '@/components/status-bar-scrim';
import { Meta, Notice, StateView } from '@/components/ui';
import { C, MaxContentWidth, Radius, Space } from '@/constants/theme';
import { useRemote } from '@/hooks/use-remote';
import { alpha, type ArtistIdentity, identityFor } from '@/lib/artist-identity';
import { artistCardRows, artistPlatforms } from '@/lib/format';
import { photoShortCredit, verifiablePhoto } from '@/lib/poster-quick';
import { SHEET } from '@/lib/track-art';
import { describeError } from '@/services/api-client';
import { getArtist, getEssentials, getStories } from '@/services/music';
import type { ArtistProfileResponse } from '@/types/music';


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
        <Profile data={data} />
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

function Profile({ data }: { data: ArtistProfileResponse }) {
  const { width } = useWindowDimensions();
  const [photoFailed, setPhotoFailed] = useState(false);
  const { artist, styles: artistStyles } = data;
  // «Escuchar»: solo Spotify, Apple Music, SoundCloud y Discogs (directo o búsqueda marcada).
  const platforms = artistPlatforms(artist.links, artist.name);
  // Historias: se investigan aparte (caché en el servidor) para que la ficha nunca las espere.
  const storiesRemote = useRemote(`stories:${artist.mbid}`, () => getStories(artist.mbid));
  const storiesLoading = storiesRemote.state.status === 'loading' || storiesRemote.state.status === 'idle';
  const stories = storiesRemote.state.status === 'success' ? storiesRemote.state.data.stories : [];
  // Tracks esenciales (Deezer + MusicBrainz por ISRC): aparte, con caché propia en el servidor.
  const essentialsRemote = useRemote(`essentials:${artist.mbid}`, () => getEssentials(artist.mbid));
  const essentials = essentialsRemote.state.status === 'success' ? essentialsRemote.state.data : null;
  const essentialTracks = essentials?.tracks ?? [];
  const id = useMemo(() => identityFor(artist.mbid), [artist.mbid]);
  const P = id.palette;
  const S = ARTIST_SURFACES;
  const heroWidth = Math.min(width, MaxContentWidth);
  const heroHeight = Math.round(Math.min(Math.max(heroWidth * 1.12, 440), 580));
  const contentWidth = heroWidth - GUTTER * 2;
  const ident = data.identity;
  const genres = [...new Set(artistStyles.map((s) => s.label.replace(/^música /i, '')))].slice(0, 3);
  const rows = artistCardRows({ type: artist.type, identity: ident });
  const labelCredit = ident?.founded_labels?.[0] ?? ident?.run_labels?.[0];
  const credits = [ident?.country_name, labelCredit ? `Sello ${labelCredit}` : null].filter((x): x is string => Boolean(x));
  const photo = data.image && verifiablePhoto(data.image) && !photoFailed ? data.image : null;
  const scrollRef = useAnimatedRef<Animated.ScrollView>();
  const scrollY = useScrollOffset(scrollRef);

  let n = 0;
  const next = () => String(++n).padStart(2, '0');

  return (
    <>
      <Animated.ScrollView ref={scrollRef} style={{ backgroundColor: S.screen }} contentContainerStyle={{ paddingBottom: Space.xxxl * 2 }}
        contentInsetAdjustmentBehavior="never">
        <View style={{ alignSelf: 'center' }}>
          <ArtistHero name={artist.name} id={id} width={heroWidth} height={heroHeight} tags={genres} credits={credits}
            photo={photo ? { url: photo.url, credit: photoShortCredit(photo), sourceUrl: photo.page_url } : null}
            onPhotoError={() => setPhotoFailed(true)} />
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

          {storiesLoading || stories.length || essentialTracks.length ? (
            <View style={{ gap: Space.md }}>
              <SectionHead index={next()} title="Más allá de la cabina" id={id} />
              {storiesLoading || stories.length ? <StoryBlocks stories={stories} id={id} loading={storiesLoading} /> : null}
              {essentialTracks.length ? <EssentialTracks tracks={essentialTracks} id={id} basis={essentials?.basis ?? null} /> : null}
            </View>
          ) : null}

          <NameBand name={artist.name} id={id} width={heroWidth} />

          {platforms.length ? (
            <View style={{ gap: Space.md }}>
              <SectionHead index={next()} title="Escuchar" id={id} />
              <PlatformDock links={platforms} id={id} width={contentWidth} cols={2} detail={(l) => l.detail} />
            </View>
          ) : null}

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
  skeleton: { borderRadius: Radius.md },
});
