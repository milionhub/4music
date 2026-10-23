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
import { ActivityIndicator, Alert, FlatList, Modal, Pressable, StyleSheet, Text, useWindowDimensions, View } from 'react-native';
import { SafeAreaView, useSafeAreaInsets } from 'react-native-safe-area-context';

import { STATUS_LABEL } from '@/components/poster';
import { ArtistQuickView, type IdentityAction } from '@/components/poster-artist';
import { EventCover } from '@/components/poster-cover';
import { DayHeader, FilterBar, LineupRow } from '@/components/poster-lineup';
import { Button, Chip, Meta, Notice, Screen, StateView } from '@/components/ui';
import { C, Fonts, MaxContentWidth, Radius, Space } from '@/constants/theme';
import { usePosterResolution } from '@/hooks/use-poster-resolution';
import { eventArt, inkOn } from '@/lib/poster-art';
import { type ExploreFilter, exploreRows, type ExploreRow, facets, NO_FILTER, validFilter } from '@/lib/poster-explore';
import { chooseIdentity, identityCounts, leaveUnidentified, resetIdentity, setArtistStyles } from '@/lib/poster-identity';
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
  const [error, setError] = useState<string | null>(null);

  useFocusEffect(useCallback(() => {
    setEvent(id ? loadEvent(id) : null);
    setLoaded(true);
  }, [id]));
  const resolution = usePosterResolution(id, setEvent);
  const { prioritize } = resolution;

  // El artista abierto se resuelve el primero (también al volver a una hoja abierta desde el parámetro).
  useEffect(() => {
    if (artistParam) prioritize(artistParam);
  }, [artistParam, prioritize]);

  const openArtist = useCallback((setId: string, artistId: string, members: string[]) => {
    prioritize(artistId);
    members.filter((m) => m !== artistId).forEach(prioritize);
    router.setParams({ set: setId, artist: artistId });
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
      <View style={{ gap: Space.md, paddingTop: Space.lg }}>
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
          <Meta>{[`↗ ${counts.linked} identificados`, counts.ambiguous ? `? ${counts.ambiguous} con varios candidatos` : null,
            counts.none ? `– ${counts.none} sin identificar` : null].filter(Boolean).join('   ')}</Meta>
        )}
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
    return <LineupRow event={e} set={s} art={art} onOpen={(aid) => openArtist(s.id, aid, s.artistIds)} />;
  };

  return (
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
            <Image source={{ uri: posterImageUri(e.id) }} style={{ flex: 1 }} contentFit="contain" accessibilityLabel="Cartel original completo" />
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
  progressTitle: { color: C.text, fontFamily: Fonts.sansBold, fontSize: 14 },
  empty: { alignItems: 'center', gap: Space.md, paddingVertical: Space.xxl },
  emptyTitle: { color: C.text, fontFamily: Fonts.sansBold, fontSize: 16, textAlign: 'center' },
  zoomClose: { position: 'absolute', right: Space.lg, backgroundColor: 'rgba(7,6,11,0.8)', borderRadius: Radius.pill,
    paddingHorizontal: Space.lg, minHeight: 44, justifyContent: 'center' },
  zoomCloseText: { color: C.text, fontFamily: Fonts.monoBold, fontSize: 13 },
});
