/**
 * Carteles 3.3–3.5: evento guardado (se abre sin red y sin IA). Portada editorial con la paleta del cartel, explorador
 * del line-up con filtros fijos arriba (lista virtualizada: 6 o más de 50 actuaciones) y vista rápida de artista.
 * Las identidades se resuelven poco a poco mientras la pantalla está abierta (primero la que abre el usuario).
 * La hoja es estado de esta pantalla (`?set=&artist=`): el perfil y TrackDNA se apilan encima y, al volver, siguen
 * igual la hoja, los filtros y el scroll.
 */
import { Image } from 'expo-image';
import { router, useFocusEffect, useLocalSearchParams } from 'expo-router';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { ActivityIndicator, Alert, FlatList, Modal, Pressable, ScrollView, StyleSheet, Text, useWindowDimensions, View } from 'react-native';
import { SafeAreaView, useSafeAreaInsets } from 'react-native-safe-area-context';

import { POSTER_TONE, STATUS_LABEL } from '@/components/poster';
import { ArtistQuickView, type IdentityAction } from '@/components/poster-artist';
import { EventCover } from '@/components/poster-cover';
import { StatStrip } from '@/components/library';
import { ForYou } from '@/components/poster-foryou';
import { PosterSound, SnippetDeck } from '@/components/poster-sound';
import { DayHeader, FilterBar, LineupRow } from '@/components/poster-lineup';
import { Button, Chip, Meta, Notice, Screen, StateView, ToneProvider } from '@/components/ui';
import { C, Fonts, MaxContentWidth, Radius, Space } from '@/constants/theme';
import { usePosterResolution } from '@/hooks/use-poster-resolution';
import { usePosterSound } from '@/hooks/use-poster-sound';
import { eventArt, inkOn } from '@/lib/poster-art';
import { type ExploreFilter, exploreRows, type ExploreRow, facets, NO_FILTER, validFilter } from '@/lib/poster-explore';
import { eventFits, FIT_MIN, soundProgress } from '@/lib/poster-fit';
import { clashes, clock, hasRoute, planOf, timeline } from '@/lib/poster-route';
import { eventSound } from '@/lib/poster-sound';
import { chooseIdentity, identityCounts, leaveUnidentified, resetIdentity, setArtistStyles } from '@/lib/poster-identity';
import { useLibrary } from '@/state/library';
import { deleteEvent, loadEvent, posterImageUri, saveEvent } from '@/storage/poster-library';
import type { PosterEvent } from '@/types/poster';

type Item = ExploreRow | { kind: 'filters'; key: string } | { kind: 'empty'; key: string };

export default function PosterEventScreen() {
  const { id, set: setParam, artist: artistParam } = useLocalSearchParams<{ id: string; set?: string; artist?: string }>();
  const { width } = useWindowDimensions();
  const insets = useSafeAreaInsets();
  const [event, setEvent] = useState<PosterEvent | null>(null);
  const [loaded, setLoaded] = useState(false);
  const [filterState, setFilter] = useState<ExploreFilter>(NO_FILTER);
  const [zoom, setZoom] = useState(false);
  const [zoomBox, setZoomBox] = useState<{ width: number; height: number } | null>(null);
  const [error, setError] = useState<string | null>(null);

  useFocusEffect(useCallback(() => {
    setEvent(id ? loadEvent(id) : null);
    setLoaded(true);
  }, [id]));
  const resolution = usePosterResolution(id, setEvent);
  const { prioritize } = resolution;
  // Carteles 4: sonido de cada artista enlazado (para «Para ti»); arranca de nuevo cuando la resolución enlaza más.
  const sound = usePosterSound(id, setEvent);
  const { kick } = sound;
  const linkedCount = event ? identityCounts(event).linked : 0;
  useEffect(() => {
    if (linkedCount) void kick();
  }, [linkedCount, kick]);
  const lib = useLibrary();
  const taste = useMemo(() => ({ favorites: lib.favorites, saved: lib.savedTracks, styles: lib.preferences.declared_styles }),
    [lib.favorites, lib.savedTracks, lib.preferences.declared_styles]);
  const hasTaste = taste.favorites.length + taste.saved.length + taste.styles.length > 0;
  const fits = useMemo(() => (event ? eventFits(event, taste) : []), [event, taste]);
  const slots = useMemo(() => (event ? timeline(event) : []), [event]);
  const lineupSound = useMemo(() => (event ? eventSound(event) : null), [event]);
  const fitIds = useMemo(() => new Set(fits.filter((f) => f.score >= FIT_MIN).map((f) => f.artist.id)), [fits]);

  // El artista abierto se resuelve el primero (también al volver a una hoja abierta desde el parámetro).
  useEffect(() => {
    if (artistParam) prioritize(artistParam);
  }, [artistParam, prioritize]);

  const openArtist = useCallback((setId: string | null, artistId: string, members: string[]) => {
    prioritize(artistId);
    members.filter((m) => m !== artistId).forEach(prioritize);
    router.setParams({ set: setId ?? undefined, artist: artistId });
  }, [prioritize]);
  const closeSheet = useCallback(() => router.setParams({ set: undefined, artist: undefined }), []);

  const onIdentity = useCallback((artistId: string, action: IdentityAction) => {
    const base = id ? loadEvent(id) : null;
    if (!base) return;
    const now = new Date().toISOString();
    const next = action.kind === 'choose' ? chooseIdentity(base, artistId, action.candidate, now)
      : action.kind === 'unidentified' ? leaveUnidentified(base, artistId, now)
        : resetIdentity(base, artistId, now);
    const saved = saveEvent(next);
    setEvent(next);
    setError(saved.ok ? null : saved.message);
    if (action.kind === 'reset') prioritize(artistId);
  }, [id, prioritize]);

  // Estilos documentados del perfil abierto: se guardan para el filtro de estilo (sin red ni búsquedas extra).
  const onStyles = useCallback((artistId: string, mbid: string, styles: string[]) => {
    const base = id ? loadEvent(id) : null;
    if (!base) return;
    const next = setArtistStyles(base, artistId, mbid, styles);
    if (next === base) return;
    if (saveEvent(next).ok) setEvent(next);
  }, [id]);

  const art = useMemo(() => (event ? eventArt({ id: event.id, fingerprint: event.fingerprint, seeds: event.palette.seeds }) : null), [event]);
  const fx = useMemo(() => (event ? facets(event) : null), [event]);
  const filter = fx ? validFilter(filterState, fx) : NO_FILTER;
  const rows = event ? exploreRows(event, filter) : [];

  if (!loaded) return <Screen withTabBar={false}>{null}</Screen>;
  if (!event || !art || !fx) {
    return (
      <Screen withTabBar={false}>
        <StateView kind="error" title="Evento no encontrado" message="Puede que se haya eliminado." actionLabel="Volver" onAction={() => router.back()} />
      </Screen>
    );
  }
  const e = event;
  const P = art.palette;
  const S = art.surfaces;
  const counts = identityCounts(e);
  const sheetArtist = artistParam && e.artists.some((a) => a.id === artistParam) ? artistParam : null;
  const coverTop = art.kind === 'billboard' || art.kind === 'stamp' ? P.bg : art.kind === 'column' ? P.bg : S.screen;
  const coverWidth = Math.min(width, MaxContentWidth);
  const shown = rows.filter((r) => r.kind === 'set').length;
  const items: Item[] = [{ kind: 'filters', key: 'filters' }, ...(rows.length ? rows : [{ kind: 'empty' as const, key: 'empty' }])];

  function confirmDelete() {
    Alert.alert('¿Eliminar este evento?', 'Se borrarán el evento, tus correcciones y la imagen guardada en este dispositivo.', [
      { text: 'Cancelar', style: 'cancel' },
      { text: 'Eliminar', style: 'destructive', onPress: () => {
        const r = deleteEvent(e.id);
        if (r.ok) router.back();
        else setError(r.message);
      } },
    ]);
  }

  const header = (
    <View>
      <View style={[styles.toolbar, { backgroundColor: coverTop }]}>
        <Pressable onPress={() => router.back()} accessibilityRole="button" accessibilityLabel="Volver" hitSlop={10}
          style={[styles.toolBtn, { borderColor: inkOn(coverTop) }]}>
          <Text style={[styles.toolLabel, { color: inkOn(coverTop) }]}>←</Text>
        </Pressable>
        <Pressable onPress={() => router.push(`/poster/${e.id}/review`)} accessibilityRole="button" accessibilityLabel="Editar evento" hitSlop={10}
          style={[styles.toolBtn, styles.toolWide, { borderColor: inkOn(coverTop) }]}>
          <Text style={[styles.toolText, { color: inkOn(coverTop) }]}>Editar</Text>
        </Pressable>
      </View>
      <View style={{ marginHorizontal: -Space.lg }}>
        <EventCover event={e} art={art} width={coverWidth} onOpenPoster={() => setZoom(true)} />
      </View>
      <View style={{ gap: Space.md, paddingTop: Space.lg, paddingBottom: Space.md }}>
        <StatStrip ink={P.glow} size={26} stats={[
          { label: 'Artistas', value: String(e.artists.length).padStart(2, '0') },
          ...(e.stages.length > 1 ? [{ label: 'Escenarios', value: String(e.stages.length).padStart(2, '0') }] : []),
          ...(hasTaste && fitIds.size ? [{ label: 'Para ti', value: String(fitIds.size).padStart(2, '0') }] : []),
        ]} />
        {error ? <Notice tone="warn">{error}</Notice> : null}
        {e.status !== 'confirmed' ? <Notice tone="warn">{STATUS_LABEL[e.status]}: revisa los avisos en «Editar» cuando quieras. Ya puedes explorar el line-up.</Notice> : null}
        {e.analysis.incomplete ? <Notice tone="warn">El análisis quedó incompleto: puede faltar parte del line-up. Puedes completarlo en «Editar».</Notice> : null}
        {/* Identidades: progreso visible, pausable y sin bloquear la exploración del line-up. */}
        {counts.pending || resolution.error ? (
          <View style={[styles.progress, { borderColor: S.line, backgroundColor: S.raised }]} accessibilityLiveRegion="polite">
            {resolution.running ? <ActivityIndicator color={P.glow} size="small" /> : null}
            <View style={{ flex: 1, gap: 2 }}>
              <Text style={styles.progressTitle}>
                {resolution.error ? 'Identificación detenida' : resolution.paused ? 'Identificación en pausa' : 'Identificando artistas'}
              </Text>
              <Meta>{resolution.error ?? `${e.artists.length - counts.pending} de ${e.artists.length} en MusicBrainz · puedes explorar mientras tanto`}</Meta>
            </View>
            {resolution.error ? <Chip label="Reintentar" onPress={resolution.retry} />
              : <Chip label={resolution.paused ? 'Seguir' : 'Pausar'} onPress={() => resolution.setPaused(!resolution.paused)} />}
          </View>
        ) : (
          <Text style={styles.idLine}>{[`↗ ${counts.linked} identificados`, counts.ambiguous ? `? ${counts.ambiguous} con varios candidatos` : null,
            counts.none ? `– ${counts.none} sin identificar` : null].filter(Boolean).join('   ')}</Text>
        )}
        {hasRoute(slots) ? (() => {
          const plan = planOf(e);
          const n = clashes(slots, plan).length;
          const from = Math.min(...slots.map((s) => s.start));
          const to = Math.max(...slots.map((s) => s.end));
          return (
            <Pressable onPress={() => router.push(`/poster/${e.id}/route`)} accessibilityRole="button"
              style={({ pressed }) => [styles.routeCard, { borderColor: P.glow, backgroundColor: S.raised }, pressed && { opacity: 0.85 }]}>
              <Text style={[styles.routeKicker, { color: P.glow }]}>Hoja de ruta ↗</Text>
              <Text style={styles.routeTitle}>{plan.length ? `Tu ruta · ${plan.length} ${plan.length === 1 ? 'actuación' : 'actuaciones'}` : 'Arma tu noche'}</Text>
              <Text style={styles.idLine}>
                {plan.length ? (n ? `${n} ${n === 1 ? 'solape' : 'solapes'} por resolver` : 'Sin solapes')
                  : `${slots.length} actuaciones con hora · ${clock(from)}–${clock(to)} · te proponemos una ruta`}
              </Text>
            </Pressable>
          );
        })() : null}
        <View style={{ gap: Space.xl, paddingTop: Space.md }}>
          <ForYou event={e} fits={fits} art={art} progress={soundProgress(e)} running={sound.running} hasTaste={hasTaste} onOpen={openArtist} />
          {lineupSound ? <PosterSound sound={lineupSound} art={art} /> : null}
        </View>
        <View style={[styles.lineupHead, { borderTopColor: P.glow }]} accessibilityRole="header">
          <Text style={styles.lineupTitle}>Line-up</Text>
          <Text style={styles.idLine}>{`${e.sets.length} ${e.sets.length === 1 ? 'actuación' : 'actuaciones'}`}</Text>
        </View>
      </View>
    </View>
  );

  const footer = (
    <View style={{ gap: Space.md, paddingTop: Space.xl }}>
      <Button label="Editar evento" variant="ghost" onPress={() => router.push(`/poster/${e.id}/review`)} />
      <Button label="Eliminar evento" variant="danger" onPress={confirmDelete} />
    </View>
  );

  const renderItem = ({ item }: { item: Item }) => {
    if (item.kind === 'filters') {
      return <FilterBar facets={fx} filter={filter} onChange={setFilter} shown={shown} total={e.sets.length} art={art} />;
    }
    if (item.kind === 'empty') {
      return (
        <View style={styles.empty}>
          <Text style={styles.emptyTitle}>{e.sets.length ? 'Ninguna actuación con estos filtros' : 'Este evento aún no tiene actuaciones'}</Text>
          {e.sets.length ? <Button label="Quitar filtros" variant="ghost" onPress={() => setFilter(NO_FILTER)} />
            : <Button label="Añadir artistas en «Editar»" variant="ghost" onPress={() => router.push(`/poster/${e.id}/review`)} />}
        </View>
      );
    }
    if (item.kind === 'day') return <DayHeader label={item.label} count={item.count} art={art} />;
    const s = item.set;
    return <LineupRow event={e} set={s} art={art} fits={fitIds} onOpen={(aid) => openArtist(s.id, aid, s.artistIds)} />;
  };

  return (
    <ToneProvider value={POSTER_TONE}>
    <SnippetDeck>
    <View style={{ flex: 1, backgroundColor: S.screen }}>
      <SafeAreaView edges={['top', 'left', 'right']} style={{ flex: 1, backgroundColor: coverTop }}>
        <FlatList
          data={items}
          keyExtractor={(x) => x.key}
          renderItem={renderItem}
          ListHeaderComponent={header}
          ListFooterComponent={footer}
          stickyHeaderIndices={[1]}
          initialNumToRender={14}
          windowSize={9}
          style={{ backgroundColor: S.screen }}
          contentContainerStyle={[styles.content, { paddingBottom: insets.bottom + Space.xxxl }]}
        />
      </SafeAreaView>

      {zoom ? (
        <Modal animationType="fade" onRequestClose={() => setZoom(false)} supportedOrientations={['portrait', 'landscape']}>
          <SafeAreaView style={{ flex: 1, backgroundColor: '#000' }} edges={['bottom', 'left', 'right']}>
            {/* Pellizco para ampliar con el zoom nativo de ScrollView (iOS). En Android no hay zoom: se ve completo. */}
            <ScrollView style={{ flex: 1 }} maximumZoomScale={4} minimumZoomScale={1} centerContent bouncesZoom
              showsHorizontalScrollIndicator={false} showsVerticalScrollIndicator={false}
              onLayout={(ev) => setZoomBox({ width: ev.nativeEvent.layout.width, height: ev.nativeEvent.layout.height })}>
              {zoomBox ? (
                <Image source={{ uri: posterImageUri(e.id) }} style={zoomBox} contentFit="contain"
                  accessibilityLabel="Cartel original completo. Pellizca para ampliar." />
              ) : null}
            </ScrollView>
            <Pressable onPress={() => setZoom(false)} accessibilityRole="button" accessibilityLabel="Cerrar cartel" hitSlop={12}
              style={[styles.zoomClose, { top: insets.top + Space.md }]}>
              <Text style={styles.zoomCloseText}>✕  Cerrar</Text>
            </Pressable>
          </SafeAreaView>
        </Modal>
      ) : null}

      {sheetArtist ? (
        <ArtistQuickView event={e} setId={setParam ?? null} artistId={sheetArtist} resolveError={resolution.error} art={art}
          onSelect={(aid) => { prioritize(aid); router.setParams({ artist: aid }); }} onAction={onIdentity} onStyles={onStyles}
          onRetry={resolution.retry} onClose={closeSheet} />
      ) : null}
    </View>
    </SnippetDeck>
    </ToneProvider>
  );
}

const styles = StyleSheet.create({
  content: { paddingHorizontal: Space.lg, width: '100%', maxWidth: MaxContentWidth, alignSelf: 'center' },
  toolbar: { flexDirection: 'row', justifyContent: 'space-between', marginHorizontal: -Space.lg, paddingHorizontal: Space.lg, paddingVertical: Space.sm },
  toolBtn: { minWidth: 44, height: 44, borderRadius: 22, borderWidth: 1.5, alignItems: 'center', justifyContent: 'center' },
  toolWide: { paddingHorizontal: Space.lg },
  toolLabel: { fontSize: 20, fontWeight: '800' },
  toolText: { fontFamily: Fonts.monoBold, fontSize: 13, textTransform: 'uppercase', letterSpacing: 1 },
  progress: { flexDirection: 'row', alignItems: 'center', gap: Space.md, padding: Space.md, borderRadius: Radius.md, borderWidth: 1 },
  routeCard: { borderWidth: 2, borderRadius: Radius.md, padding: Space.lg, gap: 4 },
  routeKicker: { fontFamily: Fonts.monoBold, fontSize: 11, letterSpacing: 1.3, textTransform: 'uppercase' },
  routeTitle: { color: C.text, fontFamily: Fonts.display, fontSize: 28, lineHeight: 32, textTransform: 'uppercase', includeFontPadding: false },
  lineupHead: { flexDirection: 'row', alignItems: 'baseline', justifyContent: 'space-between', gap: Space.md, borderTopWidth: 3, paddingTop: Space.md,
    marginTop: Space.xl },
  lineupTitle: { color: C.text, fontFamily: Fonts.display, fontSize: 34, lineHeight: 38, textTransform: 'uppercase', includeFontPadding: false },
  idLine: { color: C.muted, fontFamily: Fonts.monoBold, fontSize: 11, letterSpacing: 0.8, textTransform: 'uppercase' },
  progressTitle: { color: C.text, fontFamily: Fonts.sansBold, fontSize: 14 },
  empty: { alignItems: 'center', gap: Space.md, paddingVertical: Space.xxl },
  emptyTitle: { color: C.text, fontFamily: Fonts.sansBold, fontSize: 16, textAlign: 'center' },
  zoomClose: { position: 'absolute', right: Space.lg, backgroundColor: 'rgba(7,6,11,0.8)', borderRadius: Radius.pill,
    paddingHorizontal: Space.lg, minHeight: 44, justifyContent: 'center' },
  zoomCloseText: { color: C.text, fontFamily: Fonts.monoBold, fontSize: 13 },
});
