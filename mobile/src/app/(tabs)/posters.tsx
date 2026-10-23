/**
 * Carteles (3.1–3.5): portada editorial → Analizar cartel → biblioteca local. La portada es la cabecera común de las
 * pestañas con una franja de los colores de los carteles guardados (cada evento conserva su paleta). Los borradores
 * van primero, en «Por revisar»; cada tarjeta tiene acciones de editar y eliminar.
 */
import { router, useFocusEffect } from 'expo-router';
import { useCallback, useState } from 'react';
import { Alert, StyleSheet, Text, useWindowDimensions, View } from 'react-native';

import { EmptyPoster, ScreenPoster } from '@/components/editorial';
import { PS, POSTER_ID, PosterCard } from '@/components/poster';
import { Button, Meta, Notice, Screen } from '@/components/ui';
import { C, Fonts, MaxContentWidth, Radius, Space } from '@/constants/theme';
import { eventArt } from '@/lib/poster-art';
import { cleanupOrphans, deleteEvent, loadIndex } from '@/storage/poster-library';
import type { PosterIndexEntry } from '@/types/poster';

const STEPS = [
  ['01', 'Elige o fotografía un cartel', 'Fiesta o festival: galería o cámara.'],
  ['02', 'Revisa lo que propone la IA', 'Solo se marcan los datos dudosos.'],
  ['03', 'Explora su música', 'Artistas, perfiles y TrackDNA.'],
] as const;

export default function Posters() {
  const { width } = useWindowDimensions();
  const [index, setIndex] = useState<PosterIndexEntry[]>([]);
  const [bytes, setBytes] = useState(0);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(() => {
    const items = loadIndex();
    setIndex(items);
    setBytes(cleanupOrphans(items));
  }, []);
  useFocusEffect(refresh);

  function remove(entry: PosterIndexEntry) {
    Alert.alert(`¿Eliminar «${entry.name ?? 'cartel sin nombre'}»?`, 'Se borrarán el evento, tus correcciones y la imagen guardada en este dispositivo.', [
      { text: 'Cancelar', style: 'cancel' },
      { text: 'Eliminar', style: 'destructive', onPress: () => {
        const r = deleteEvent(entry.id);
        setError(r.ok ? null : r.message);
        refresh();
      } },
    ]);
  }

  function actions(entry: PosterIndexEntry) {
    Alert.alert(entry.name ?? 'Cartel sin nombre', undefined, [
      { text: 'Cancelar', style: 'cancel' },
      { text: 'Editar', onPress: () => router.push(`/poster/${entry.id}/review`) },
      { text: 'Eliminar', style: 'destructive', onPress: () => remove(entry) },
    ]);
  }

  const full = Math.min(width, MaxContentWidth);
  const cardWidth = (full - Space.lg * 2 - Space.md) / 2;
  const pending = index.filter((x) => x.status !== 'confirmed');
  const done = index.filter((x) => x.status === 'confirmed');
  const open = (entry: PosterIndexEntry) => router.push(entry.status === 'confirmed' ? `/poster/${entry.id}` : `/poster/${entry.id}/review`);
  const grid = (items: PosterIndexEntry[]) => (
    <View style={styles.grid}>
      {items.map((entry) => <PosterCard key={entry.id} entry={entry} width={cardWidth} onPress={() => open(entry)} onActions={() => actions(entry)} />)}
    </View>
  );

  return (
    <Screen background={PS.screen} topTint={POSTER_ID.palette.bg}>
      <View style={{ marginHorizontal: -Space.lg, marginTop: -Space.lg }}>
        <ScreenPoster id={POSTER_ID} width={full} word="Carteles" kicker="Del cartel a la música"
          figure={index.length ? String(index.length).padStart(2, '0') : undefined}
          subtitle={index.length ? `${index.length} ${index.length === 1 ? 'evento' : 'eventos'} · solo en este dispositivo` : 'Fotografía un cartel y explora su line-up'}>
          {index.length ? (
            <View style={styles.wall} accessibilityElementsHidden importantForAccessibility="no-hide-descendants">
              {index.slice(0, 12).map((x) => <View key={x.id} style={[styles.swatch, { backgroundColor: eventArt(x).palette.bg, borderColor: POSTER_ID.palette.ink }]} />)}
            </View>
          ) : null}
        </ScreenPoster>
      </View>

      <View style={{ gap: Space.sm }}>
        <Button label="Analizar cartel" onPress={() => router.push('/poster/new')} />
        <Meta style={{ textAlign: 'center' }}>Galería o cámara · la IA propone, tú revisas</Meta>
      </View>
      {error ? <Notice tone="warn">{error}</Notice> : null}

      {index.length === 0 ? (
        <View style={{ gap: Space.lg }}>
          <EmptyPoster id={POSTER_ID} glyph="▦" title="Tu biblioteca de carteles está vacía"
            message="Cada cartel que analices se guarda aquí, con sus colores, tus correcciones y sus artistas." />
          <View style={{ gap: Space.sm }}>
            {STEPS.map(([n, title, detail]) => (
              <View key={n} style={styles.step}>
                <Text style={styles.stepNumber}>{n}</Text>
                <View style={{ flex: 1, gap: 2 }}>
                  <Text style={styles.stepTitle}>{title}</Text>
                  <Meta>{detail}</Meta>
                </View>
              </View>
            ))}
          </View>
        </View>
      ) : (
        <>
          {pending.length ? (
            <View style={{ gap: Space.md }}>
              <SectionTitle title="Por revisar" note={`${pending.length} · termina de revisarlos para explorarlos`} />
              {grid(pending)}
            </View>
          ) : null}
          {done.length ? (
            <View style={{ gap: Space.md }}>
              <SectionTitle title="Biblioteca" note={`${done.length} · ••• o mantén pulsado para editar o eliminar`} />
              {grid(done)}
            </View>
          ) : null}
          {bytes ? <Meta>Espacio usado en el dispositivo: {(bytes / 1024 / 1024).toFixed(1)} MB</Meta> : null}
        </>
      )}
    </Screen>
  );
}

function SectionTitle({ title, note }: { title: string; note: string }) {
  return (
    <View style={{ gap: 2 }} accessibilityRole="header">
      <Text style={styles.section}>{title}</Text>
      <Meta>{note}</Meta>
    </View>
  );
}

const styles = StyleSheet.create({
  wall: { flexDirection: 'row', gap: 4, marginTop: Space.sm },
  swatch: { flex: 1, maxWidth: 34, height: 14, borderWidth: 1.5, borderRadius: 2 },
  grid: { flexDirection: 'row', flexWrap: 'wrap', gap: Space.md },
  section: { color: C.text, fontFamily: Fonts.display, fontSize: 26, lineHeight: 30, textTransform: 'uppercase' },
  step: { flexDirection: 'row', alignItems: 'center', gap: Space.md, padding: Space.md, borderRadius: Radius.md, borderWidth: 1, borderColor: PS.line,
    backgroundColor: PS.raised },
  stepNumber: { color: POSTER_ID.palette.glow, fontFamily: Fonts.display, fontSize: 28, width: 40 },
  stepTitle: { color: C.text, fontFamily: Fonts.sansBold, fontSize: 15 },
});
