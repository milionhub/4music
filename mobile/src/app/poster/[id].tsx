/**
 * Carteles 3.3: vista básica del evento guardado (se abre sin red y sin IA). Sirve para comprobar los datos; la
 * portada editorial, el explorador con filtros y la vista rápida de artista llegan en 3.4–3.5.
 */
import { Image } from 'expo-image';
import { router, useFocusEffect, useLocalSearchParams } from 'expo-router';
import { useCallback, useState } from 'react';
import { Alert, Modal, Pressable, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { eventColor, PS, SetRow, STATUS_LABEL } from '@/components/poster';
import { Button, Chip, Meta, Notice, Screen, StateView } from '@/components/ui';
import { C, Fonts, Radius, Space } from '@/constants/theme';
import { groupByDay } from '@/lib/poster-model';
import { deleteEvent, loadEvent, posterImageUri } from '@/storage/poster-library';
import type { PosterEvent } from '@/types/poster';

export default function PosterEventScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const [event, setEvent] = useState<PosterEvent | null>(null);
  const [loaded, setLoaded] = useState(false);
  const [day, setDay] = useState<string | null>(null);
  const [zoom, setZoom] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useFocusEffect(useCallback(() => {
    setEvent(id ? loadEvent(id) : null);
    setLoaded(true);
  }, [id]));

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
            {g.sets.map((s) => <SetRow key={s.id} event={e} set={s} />)}
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
  );
}

const styles = StyleSheet.create({
  head: { flexDirection: 'row', gap: Space.lg, padding: Space.md, borderRadius: Radius.lg, borderWidth: 2, backgroundColor: PS.raised },
  thumb: { width: 96, height: 120, borderRadius: Radius.sm, backgroundColor: PS.deep },
  name: { color: C.text, fontFamily: Fonts.display, fontSize: 30, lineHeight: 33, textTransform: 'uppercase' },
  detail: { color: C.text, fontFamily: Fonts.sans, fontSize: 15 },
  day: { color: C.text, fontFamily: Fonts.display, fontSize: 20, textTransform: 'uppercase' },
  chips: { flexDirection: 'row', flexWrap: 'wrap', gap: Space.sm },
});
