/**
 * Carteles 3.3–3.4: evento guardado (se abre sin red y sin IA) con la vista rápida de artista. Las identidades se
 * resuelven poco a poco mientras la pantalla está abierta (primero la que abre el usuario) y quedan guardadas.
 * La hoja es estado de esta pantalla (`?set=&artist=`): el perfil y TrackDNA se apilan encima y, al volver, sigue abierta.
 * La portada editorial y el explorador con filtros llegan en 3.5.
 */
import { Image } from 'expo-image';
import { router, useFocusEffect, useLocalSearchParams } from 'expo-router';
import { useCallback, useEffect, useState } from 'react';
import { ActivityIndicator, Alert, Modal, Pressable, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { eventColor, PS, SetRow, STATUS_LABEL } from '@/components/poster';
import { ArtistQuickView, type IdentityAction } from '@/components/poster-artist';
import { Button, Chip, Meta, Notice, Screen, StateView } from '@/components/ui';
import { C, Fonts, Radius, Space } from '@/constants/theme';
import { usePosterResolution } from '@/hooks/use-poster-resolution';
import { chooseIdentity, identityCounts, leaveUnidentified, linkNote, resetIdentity } from '@/lib/poster-identity';
import { groupByDay } from '@/lib/poster-model';
import { deleteEvent, loadEvent, posterImageUri, saveEvent } from '@/storage/poster-library';
import type { PosterEvent, PosterSet } from '@/types/poster';

export default function PosterEventScreen() {
  const { id, set: setParam, artist: artistParam } = useLocalSearchParams<{ id: string; set?: string; artist?: string }>();
  const [event, setEvent] = useState<PosterEvent | null>(null);
  const [loaded, setLoaded] = useState(false);
  const [day, setDay] = useState<string | null>(null);
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

  const openSet = useCallback((s: PosterSet) => {
    s.artistIds.forEach(prioritize);
    router.setParams({ set: s.id, artist: s.artistIds[0] });
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

  if (!loaded) return <Screen withTabBar={false}>{null}</Screen>;
  if (!event) {
    return (
      <Screen withTabBar={false}>
        <StateView kind="error" title="Evento no encontrado" message="Puede que se haya eliminado." actionLabel="Volver" onAction={() => router.back()} />
      </Screen>
    );
  }
  const e = event;
  const color = eventColor({ id: e.id, seeds: e.palette.seeds });
  const groups = groupByDay(e).filter((g) => !day || g.day?.id === day || g.day === null);
  const daysWithSets = e.days.filter((d) => e.sets.some((s) => s.dayId === d.id));
  const counts = identityCounts(e);
  const sheetArtist = artistParam && e.artists.some((a) => a.id === artistParam) ? artistParam : null;
  const noteFor = (s: PosterSet) => {
    const notes = s.artistIds.flatMap((aid) => {
      const a = e.artists.find((x) => x.id === aid);
      const note = a ? linkNote(a) : null;
      return a && note ? [s.artistIds.length > 1 ? `${a.name}: ${note}` : note] : [];
    });
    return notes.length ? notes.join(' · ') : null;
  };

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

  return (
    <View style={{ flex: 1, backgroundColor: PS.screen }}>
    <Screen withTabBar={false} background={PS.screen}>
      <Button label="← Volver" variant="ghost" onPress={() => router.back()} style={{ alignSelf: 'flex-start' }} />
      <View style={[styles.head, { borderColor: color }]}>
        <Pressable onPress={() => setZoom(true)} accessibilityRole="imagebutton" accessibilityLabel="Ver el cartel original">
          <Image source={{ uri: posterImageUri(e.id) }} style={styles.thumb} contentFit="cover" />
        </Pressable>
        <View style={{ flex: 1, gap: Space.xs }}>
          <Text style={styles.name}>{e.name ?? 'Sin nombre'}</Text>
          {e.dateText ? <Text style={styles.detail}>{e.dateText}</Text> : null}
          {e.location ? <Text style={styles.detail}>{e.location}</Text> : null}
          <Meta>{[STATUS_LABEL[e.status], `${e.artists.length} artistas`, `${e.sets.length} actuaciones`].join(' · ')}</Meta>
        </View>
      </View>
      {error ? <Notice tone="warn">{error}</Notice> : null}
      {e.analysis.incomplete ? <Notice tone="warn">El análisis quedó incompleto: puede faltar parte del line-up. Puedes completarlo en «Editar».</Notice> : null}

      {/* Identidades: progreso visible, pausable y sin bloquear la exploración del line-up. */}
      {counts.pending || resolution.error ? (
        <View style={styles.progress} accessibilityLiveRegion="polite">
          {resolution.running ? <ActivityIndicator color={C.acid} size="small" /> : null}
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
        <Meta>{[`${counts.linked} identificados`, counts.ambiguous ? `${counts.ambiguous} con varios candidatos` : null,
          counts.none ? `${counts.none} sin identificar` : null].filter(Boolean).join(' · ')}</Meta>
      )}

      {daysWithSets.length > 1 ? (
        <View style={styles.chips}>
          <Chip label="Todo" selected={day === null} onPress={() => setDay(null)} />
          {daysWithSets.map((d) => <Chip key={d.id} label={d.label} selected={day === d.id} onPress={() => setDay(d.id)} />)}
        </View>
      ) : null}

      <View style={{ gap: Space.lg }}>
        {groups.map((g) => (
          <View key={g.day?.id ?? 'none'} style={{ gap: Space.sm }}>
            {g.day || daysWithSets.length ? <Text style={styles.day}>{g.day?.label ?? 'Sin día confirmado'}</Text> : null}
            {g.sets.map((s) => <SetRow key={s.id} event={e} set={s} note={noteFor(s)} onPress={() => openSet(s)} />)}
          </View>
        ))}
      </View>

      <View style={{ gap: Space.md }}>
        <Button label="Editar evento" variant="ghost" onPress={() => router.push(`/poster/${e.id}/review`)} />
        <Button label="Eliminar evento" variant="danger" onPress={confirmDelete} />
      </View>

      {zoom ? (
        <Modal animationType="fade" onRequestClose={() => setZoom(false)}>
          <SafeAreaView style={{ flex: 1, backgroundColor: '#000' }}>
            <Pressable style={{ flex: 1 }} onPress={() => setZoom(false)} accessibilityRole="button" accessibilityLabel="Cerrar cartel">
              <Image source={{ uri: posterImageUri(e.id) }} style={{ flex: 1 }} contentFit="contain" />
            </Pressable>
          </SafeAreaView>
        </Modal>
      ) : null}
    </Screen>
    {sheetArtist ? (
      <ArtistQuickView event={e} setId={setParam ?? null} artistId={sheetArtist} resolveError={resolution.error}
        onSelect={(aid) => { prioritize(aid); router.setParams({ artist: aid }); }} onAction={onIdentity}
        onRetry={resolution.retry} onClose={closeSheet} />
    ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  head: { flexDirection: 'row', gap: Space.lg, padding: Space.md, borderRadius: Radius.lg, borderWidth: 2, backgroundColor: PS.raised },
  thumb: { width: 96, height: 120, borderRadius: Radius.sm, backgroundColor: PS.deep },
  name: { color: C.text, fontFamily: Fonts.display, fontSize: 30, lineHeight: 33, textTransform: 'uppercase' },
  detail: { color: C.text, fontFamily: Fonts.sans, fontSize: 15 },
  day: { color: C.text, fontFamily: Fonts.display, fontSize: 20, textTransform: 'uppercase' },
  chips: { flexDirection: 'row', flexWrap: 'wrap', gap: Space.sm },
  progress: { flexDirection: 'row', alignItems: 'center', gap: Space.md, padding: Space.md, borderRadius: Radius.md, borderWidth: 1,
    borderColor: PS.line, backgroundColor: PS.raised },
  progressTitle: { color: C.text, fontFamily: Fonts.sansBold, fontSize: 14 },
});
