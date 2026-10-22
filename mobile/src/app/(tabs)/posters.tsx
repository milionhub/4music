/** Carteles (3.1–3.3): portada provisional, acceso al análisis y biblioteca local de eventos y borradores. */
import { router, useFocusEffect } from 'expo-router';
import { useCallback, useState } from 'react';
import { Alert, useWindowDimensions, View } from 'react-native';

import { EmptyPoster, ScreenPoster } from '@/components/editorial';
import { PS, POSTER_ID, PosterCard } from '@/components/poster';
import { Button, Meta, Notice, Screen } from '@/components/ui';
import { MaxContentWidth, Space } from '@/constants/theme';
import { cleanupOrphans, deleteEvent, loadIndex } from '@/storage/poster-library';
import type { PosterIndexEntry } from '@/types/poster';

export default function Posters() {
  const { width } = useWindowDimensions();
  const [index, setIndex] = useState<PosterIndexEntry[]>([]);
  const [bytes, setBytes] = useState(0);
  const [error, setError] = useState<string | null>(null);

  useFocusEffect(useCallback(() => {
    const items = loadIndex();
    setIndex(items);
    setBytes(cleanupOrphans(items));
  }, []));

  function confirmDelete(entry: PosterIndexEntry) {
    Alert.alert(`¿Eliminar «${entry.name ?? 'cartel sin nombre'}»?`, 'Se borrarán el evento, tus correcciones y la imagen guardada en este dispositivo.', [
      { text: 'Cancelar', style: 'cancel' },
      { text: 'Eliminar', style: 'destructive', onPress: () => {
        const r = deleteEvent(entry.id);
        setError(r.ok ? null : r.message);
        const items = loadIndex();
        setIndex(items);
        setBytes(cleanupOrphans(items));
      } },
    ]);
  }

  const inner = Math.min(width, MaxContentWidth) - Space.lg * 2;
  const cardWidth = (inner - Space.md) / 2;
  const pending = index.filter((x) => x.status !== 'confirmed').length;

  return (
    <Screen background={PS.screen} topTint={POSTER_ID.palette.bg}>
      <View style={{ marginHorizontal: -Space.lg, marginTop: -Space.lg }}>
        <ScreenPoster id={POSTER_ID} width={Math.min(width, MaxContentWidth)} word="Carteles" kicker="Del cartel a la música"
          figure={index.length ? String(index.length).padStart(2, '0') : undefined}
          subtitle={index.length ? `${index.length} ${index.length === 1 ? 'evento' : 'eventos'}${pending ? ` · ${pending} por revisar` : ''} · solo en este dispositivo` : 'Fotografía un cartel y explora su line-up'} />
      </View>
      <Button label="Analizar cartel" onPress={() => router.push('/poster/new')} />
      {error ? <Notice tone="warn">{error}</Notice> : null}
      {index.length === 0 ? (
        <EmptyPoster id={POSTER_ID} glyph="▦" title="Tu biblioteca de carteles está vacía"
          message="Elige la foto de un cartel de fiesta o festival. La IA propone los artistas y tú revisas antes de guardar." />
      ) : (
        <View style={{ gap: Space.md }}>
          <Meta>Biblioteca · mantén pulsado para eliminar{bytes ? ` · ${(bytes / 1024 / 1024).toFixed(1)} MB` : ''}</Meta>
          <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: Space.md }}>
            {index.map((entry) => (
              <PosterCard key={entry.id} entry={entry} width={cardWidth}
                onPress={() => router.push(entry.status === 'confirmed' ? `/poster/${entry.id}` : `/poster/${entry.id}/review`)}
                onLongPress={() => confirmDelete(entry)} />
            ))}
          </View>
        </View>
      )}
    </Screen>
  );
}
