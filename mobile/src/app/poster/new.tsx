/**
 * Carteles 3.1: elegir imagen → vista previa → análisis → borrador guardado → revisión.
 * El borrador se guarda en cuanto llega la respuesta de la IA; un fallo antes no deja nada a medias. Sin reintentos
 * automáticos: cada intento lo pide el usuario. Si el cartel ya está en la biblioteca se ofrece abrirlo primero.
 */
import { Image } from 'expo-image';
import { router } from 'expo-router';
import { useState } from 'react';
import { ActivityIndicator, Linking, StyleSheet, Text, View } from 'react-native';

import { POSTER_ID, POSTER_TONE, PS } from '@/components/poster';
import { PosterBar } from '@/components/posters-poster';
import { Body, Button, Meta, Notice, Screen, ToneProvider } from '@/components/ui';
import { C, Fonts, Radius, Space } from '@/constants/theme';
import { fromExtraction, MAX_CALLS, mergeExtraction } from '@/lib/poster-model';
import { findDuplicate, newPosterId } from '@/lib/poster-store';
import { normalizeImage, type NormalizedImage, type PickedImage, pickImage, readBase64 } from '@/services/poster-image';
import { analyzePoster, describePosterError } from '@/services/posters';
import { loadEvent, loadIndex, saveEvent, saveNewEvent } from '@/storage/poster-library';
import type { PosterEvent, PosterIndexEntry } from '@/types/poster';

type Phase =
  | { kind: 'pick'; notice?: string }
  | { kind: 'preview' }
  | { kind: 'working'; step: string }
  | { kind: 'failed'; message: string }
  | { kind: 'unsaved'; event: PosterEvent; message: string };

export default function NewPoster() {
  const [phase, setPhase] = useState<Phase>({ kind: 'pick' });
  const [picked, setPicked] = useState<PickedImage | null>(null);
  const [rotation, setRotation] = useState(0);
  const [normalized, setNormalized] = useState<NormalizedImage | null>(null);
  const [duplicate, setDuplicate] = useState<PosterIndexEntry | null>(null);

  async function choose(source: 'library' | 'camera') {
    const r = await pickImage(source);
    if (!r.ok) {
      if (r.reason === 'denied') setPhase({ kind: 'pick', notice: 'Sin permiso para usar la cámara. Puedes activarlo en Ajustes o elegir una imagen de la galería.' });
      else if (r.reason === 'error') setPhase({ kind: 'pick', notice: `No se pudo abrir la imagen: ${r.message ?? 'error desconocido'}` });
      return;
    }
    setPicked(r.image);
    setRotation(0);
    setNormalized(null);
    setDuplicate(findDuplicate(loadIndex(), r.image.fingerprint, r.image.assetId));
    setPhase({ kind: 'preview' });
  }

  function persist(event: PosterEvent, image: NormalizedImage, existing: boolean) {
    const saved = existing ? saveEvent(event) : saveNewEvent(event, image.uri, image.thumbUri);
    if (!saved.ok) return setPhase({ kind: 'unsaved', event, message: saved.message });
    router.replace(`/poster/${event.id}/review`);
  }

  async function analyze() {
    if (!picked) return;
    const existing = duplicate ? loadEvent(duplicate.id) : null;
    try {
      setPhase({ kind: 'working', step: 'Preparando la imagen…' });
      const image = normalized ?? await normalizeImage(picked, rotation);
      setNormalized(image);
      const base64 = await readBase64(image.uri);
      setPhase({ kind: 'working', step: 'La IA está leyendo el cartel…' });
      const result = await analyzePoster({ image: base64, mode: 'full' });
      if (!result.ok) return setPhase({ kind: 'failed', message: describePosterError(result.error) });
      const now = new Date().toISOString();
      if (existing) return persist(mergeExtraction(existing, result.data, now), image, true);
      const event = fromExtraction(result.data, {
        id: newPosterId(), now, fingerprint: picked.fingerprint, assetId: picked.assetId,
        image: { width: image.width, height: image.height, bytes: image.bytes },
      });
      persist(event, image, false);
    } catch (error) {
      setPhase({ kind: 'failed', message: `No se pudo preparar la imagen: ${error instanceof Error ? error.message : String(error)}` });
    }
  }

  async function rotate() {
    if (!picked) return;
    const next = (rotation + 90) % 360;
    setPhase({ kind: 'working', step: 'Girando…' });
    try {
      setNormalized(await normalizeImage(picked, next));
      setRotation(next);
      setPhase({ kind: 'preview' });
    } catch (error) {
      setPhase({ kind: 'failed', message: `No se pudo girar la imagen: ${error instanceof Error ? error.message : String(error)}` });
    }
  }

  const existingCalls = duplicate ? (loadEvent(duplicate.id)?.analysis.calls ?? MAX_CALLS) : 0;

  return (
    <ToneProvider value={POSTER_TONE}>
    <Screen withTabBar={false} background={PS.screen} topTint={POSTER_ID.palette.bg}>
      <PosterBar id={POSTER_ID} title="Analizar cartel" kicker="Carteles · la IA propone, tú revisas" backLabel="Volver" onBack={() => router.back()} />

      {phase.kind === 'pick' ? (
        <View style={{ gap: Space.md }}>
          <Body muted>Elige una foto nítida y completa del cartel. La IA solo propone lo que lee: después podrás revisarlo y corregirlo.</Body>
          {phase.notice ? <Notice tone="warn">{phase.notice}</Notice> : null}
          {phase.notice?.includes('Ajustes') ? <Button label="Abrir Ajustes" variant="ghost" onPress={() => Linking.openSettings()} /> : null}
          <Button label="Elegir de la galería" onPress={() => choose('library')} />
          <Button label="Hacer una foto" variant="ghost" onPress={() => choose('camera')} />
        </View>
      ) : null}

      {picked && phase.kind !== 'pick' ? (
        <View style={[styles.preview, { aspectRatio: normalized ? normalized.width / normalized.height : picked.width / picked.height }]}>
          <Image source={{ uri: normalized?.uri ?? picked.uri }} contentFit="contain" accessibilityLabel="Vista previa del cartel" style={StyleSheet.absoluteFill} />
        </View>
      ) : null}

      {phase.kind === 'preview' && picked ? (
        <View style={{ gap: Space.md }}>
          {duplicate ? (
            <>
              <Notice tone="warn">Este cartel ya está en tu biblioteca{duplicate.name ? ` («${duplicate.name}»)` : ''}. Ábrelo para no gastar otro análisis.</Notice>
              <Button label="Abrir evento guardado" onPress={() => router.replace(duplicate.status === 'confirmed' ? `/poster/${duplicate.id}` : `/poster/${duplicate.id}/review`)} />
              <Button label={existingCalls >= MAX_CALLS ? 'Sin análisis disponibles para este cartel' : 'Analizar de nuevo (conserva tus correcciones)'}
                variant="ghost" disabled={existingCalls >= MAX_CALLS} onPress={analyze} />
            </>
          ) : (
            <Button label="Analizar con IA" onPress={analyze} />
          )}
          <Button label="Girar 90°" variant="ghost" onPress={rotate} />
          <Button label="Elegir otra imagen" variant="ghost" onPress={() => setPhase({ kind: 'pick' })} />
        </View>
      ) : null}

      {phase.kind === 'working' ? (
        <View style={styles.working} accessibilityLiveRegion="polite">
          <ActivityIndicator color={POSTER_ID.palette.glow} />
          <Text style={styles.step}>{phase.step}</Text>
          <Meta>Un cartel grande puede tardar unos segundos</Meta>
        </View>
      ) : null}

      {phase.kind === 'failed' ? (
        <View style={{ gap: Space.md }}>
          <Notice tone="warn">{phase.message}</Notice>
          <Button label="Reintentar análisis" onPress={analyze} />
          <Button label="Elegir otra imagen" variant="ghost" onPress={() => setPhase({ kind: 'pick' })} />
        </View>
      ) : null}

      {phase.kind === 'unsaved' && normalized ? (
        <View style={{ gap: Space.md }}>
          <Notice tone="warn">{phase.message} El análisis no se ha perdido: vuelve a intentarlo sin gastar otra llamada.</Notice>
          <Button label="Reintentar guardado" onPress={() => persist(phase.event, normalized, !!duplicate)} />
        </View>
      ) : null}
    </Screen>
    </ToneProvider>
  );
}

const styles = StyleSheet.create({
  preview: { width: '100%', maxHeight: 520, borderRadius: Radius.md, overflow: 'hidden', backgroundColor: PS.deep, borderWidth: 1, borderColor: PS.line },
  working: { alignItems: 'center', gap: Space.md, padding: Space.xl, borderRadius: Radius.lg, borderWidth: 1, borderColor: PS.line, backgroundColor: PS.raised },
  step: { color: C.text, fontFamily: Fonts.sansBold, fontSize: 16 },
});
