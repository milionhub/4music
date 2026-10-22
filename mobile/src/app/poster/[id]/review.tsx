/**
 * Carteles 3.2: revisión inteligente y editor. Solo se piden revisar los datos con avisos; el resto queda plegado.
 * Cada cambio se guarda al momento y protege el campo (`meta.locked`). Recuperación: «Continuar análisis» (respuesta
 * cortada) y «Reanalizar una zona» (franjas fijas), con un máximo de MAX_CALLS llamadas por cartel en total.
 */
import { router, useLocalSearchParams } from 'expo-router';
import { useState } from 'react';
import { ActivityIndicator, Pressable, StyleSheet, Text, TextInput, View } from 'react-native';

import { Field, PS, SetEditor, SetRow, STATUS_LABEL } from '@/components/poster';
import { Body, Button, Chip, Meta, Notice, Screen, Section, StateView, Title } from '@/components/ui';
import { C, Fonts, Radius, Space } from '@/constants/theme';
import {
  addArtist, applySuggestion, confirmArtist, confirmEvent, confirmEventField, confirmSet, dismissSuggestion,
  eventFieldNeedsCheck, groupByDay, joinSets, knownContext, MAX_CALLS, mergeExtraction, recordError, removeSet,
  reviewFlags, updateEvent,
} from '@/lib/poster-model';
import { cropRegionBase64, readBase64, REGIONS, type RegionKey } from '@/services/poster-image';
import { analyzePoster, describePosterError } from '@/services/posters';
import { loadEvent, posterImageUri, saveEvent } from '@/storage/poster-library';
import type { Flag, PosterEvent } from '@/types/poster';

const now = () => new Date().toISOString();

export default function ReviewPoster() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const [event, setEvent] = useState<PosterEvent | null>(() => (id ? loadEvent(id) : null));
  const [saveError, setSaveError] = useState<string | null>(null);
  const [editing, setEditing] = useState<string | null>(null);
  const [selecting, setSelecting] = useState<string[] | null>(null);
  const [showAll, setShowAll] = useState(false);
  const [newArtist, setNewArtist] = useState('');
  const [regions, setRegions] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);

  if (!event) {
    return (
      <Screen withTabBar={false}>
        <StateView kind="error" title="Evento no encontrado" message="Puede que se haya eliminado." actionLabel="Volver" onAction={() => router.back()} />
      </Screen>
    );
  }
  const e = event;

  function apply(next: PosterEvent) {
    setEvent(next);
    const r = saveEvent(next);
    setSaveError(r.ok ? null : r.message);
  }

  const callsLeft = MAX_CALLS - e.analysis.calls;

  async function recover(kind: 'continue' | RegionKey) {
    if (callsLeft <= 0 || busy) return;
    setRegions(false);
    setBusy(kind === 'continue' ? 'Buscando lo que falta…' : `Reanalizando: ${REGIONS[kind].label.toLowerCase()}…`);
    try {
      const uri = posterImageUri(e.id);
      const result = kind === 'continue'
        ? await analyzePoster({ image: await readBase64(uri), mode: 'continue', ...knownContext(e) })
        : await analyzePoster({ image: await cropRegionBase64(uri, e.image.width, e.image.height, kind), mode: 'region' });
      // Se relee el evento guardado: la fusión parte siempre de las últimas correcciones.
      const base = loadEvent(e.id) ?? e;
      apply(result.ok ? mergeExtraction(base, result.data, now()) : recordError(base, describePosterError(result.error), now()));
    } catch (error) {
      apply(recordError(loadEvent(e.id) ?? e, `No se pudo preparar la imagen: ${error instanceof Error ? error.message : String(error)}`, now()));
    } finally {
      setBusy(null);
    }
  }

  const flags = reviewFlags(e);
  const setFlags = (setId: string): Flag[] => {
    const s = e.sets.find((x) => x.id === setId);
    return s ? [...new Set([...(flags.get(s.id) ?? []), ...s.artistIds.flatMap((a) => flags.get(a) ?? [])])] : [];
  };
  const doubtful = [...e.sets].sort((a, b) => a.order - b.order).filter((s) => setFlags(s.id).length);
  const groups = groupByDay(e);

  function confirmDoubt(setId: string) {
    const s = e.sets.find((x) => x.id === setId);
    if (!s) return;
    apply(confirmSet(s.artistIds.reduce((acc, a) => confirmArtist(acc, a, now()), e), setId, now()));
  }

  function toggleSelect(setId: string) {
    setSelecting((cur) => (cur ? (cur.includes(setId) ? cur.filter((x) => x !== setId) : [...cur, setId]) : cur));
  }

  return (
    <Screen withTabBar={false} background={PS.screen}
      footer={
        selecting ? (
          <View style={{ flexDirection: 'row', gap: Space.md }}>
            <Button label="Cancelar" variant="ghost" style={{ flex: 1 }} onPress={() => setSelecting(null)} />
            <Button label={`Unir en B2B (${selecting.length})`} style={{ flex: 1.4 }} disabled={selecting.length < 2}
              onPress={() => { apply(joinSets(e, selecting, now())); setSelecting(null); }} />
          </View>
        ) : (
          <Button label={e.status === 'confirmed' ? 'Guardar y ver evento' : 'Confirmar evento'} disabled={!!busy || e.sets.length === 0}
            onPress={() => { apply(confirmEvent(e, now())); router.replace(`/poster/${e.id}`); }} />
        )
      }>
      <View style={{ gap: Space.md }}>
        <Button label="← Biblioteca" variant="ghost" onPress={() => router.back()} style={{ alignSelf: 'flex-start' }} />
        <Title>Revisar cartel</Title>
        <Meta>{[STATUS_LABEL[e.status], `${e.artists.length} artistas`, `${e.sets.length} actuaciones`, `análisis ${e.analysis.calls}/${MAX_CALLS}`].join(' · ')}</Meta>
        <Body muted>Comprueba lo señalado; lo demás se ha leído sin dudas. Tus cambios se guardan al momento y un nuevo análisis no los sobrescribe.</Body>
      </View>

      {saveError ? <Notice tone="warn">{saveError} Tus cambios siguen en pantalla: vuelve a intentarlo.</Notice> : null}
      {e.analysis.lastError ? <Notice tone="warn">Último intento: {e.analysis.lastError}</Notice> : null}

      {busy ? (
        <View style={styles.busy} accessibilityLiveRegion="polite"><ActivityIndicator color={C.acid} /><Text style={styles.busyText}>{busy}</Text></View>
      ) : null}

      {e.analysis.incomplete ? (
        <View style={{ gap: Space.md }}>
          <Notice tone="warn">La respuesta de la IA se cortó: se ha conservado todo lo leído hasta ese punto. Puede faltar parte del line-up.</Notice>
          <Button label={callsLeft > 0 ? 'Continuar análisis' : 'Sin análisis disponibles: completa a mano'} disabled={callsLeft <= 0 || !!busy} onPress={() => recover('continue')} />
        </View>
      ) : null}

      {e.suggestions.length ? (
        <Section label={`Sugerencias del nuevo análisis · ${e.suggestions.length}`}>
          {e.suggestions.map((s) => (
            <View key={s.id} style={styles.suggestion}>
              <Text style={styles.suggestionText}>{s.label}</Text>
              <View style={{ flexDirection: 'row', gap: Space.sm }}>
                <Chip label="Aplicar" onPress={() => apply(applySuggestion(e, s.id, now()))} />
                <Chip label="Descartar" onPress={() => apply(dismissSuggestion(e, s.id, now()))} />
              </View>
            </View>
          ))}
        </Section>
      ) : null}

      <Section label="Evento">
        <Field label="Nombre" value={e.name} check={eventFieldNeedsCheck(e, 'name')} onConfirm={() => apply(confirmEventField(e, 'name', now()))}
          onCommit={(v) => apply(updateEvent(e, { name: v }, now()))} />
        <Field label="Fecha" value={e.dateText} check={eventFieldNeedsCheck(e, 'dateText')} onConfirm={() => apply(confirmEventField(e, 'dateText', now()))}
          onCommit={(v) => apply(updateEvent(e, { dateText: v }, now()))} />
        <Field label="Lugar" value={e.location} check={eventFieldNeedsCheck(e, 'location')} onConfirm={() => apply(confirmEventField(e, 'location', now()))}
          onCommit={(v) => apply(updateEvent(e, { location: v }, now()))} />
      </Section>

      <Section label={doubtful.length ? `Por comprobar · ${doubtful.length}` : 'Por comprobar'}>
        {doubtful.length === 0 ? <Notice>No se han detectado nombres ni actuaciones dudosas.</Notice> : doubtful.map((s) => (
          <View key={s.id} style={{ gap: Space.sm }}>
            <SetRow event={e} set={s} flags={setFlags(s.id)} selected={selecting?.includes(s.id)}
              onPress={() => (selecting ? toggleSelect(s.id) : setEditing(s.id))} />
            {selecting ? null : (
              <View style={{ flexDirection: 'row', gap: Space.sm, flexWrap: 'wrap' }}>
                <Chip label="✓ Es correcto" onPress={() => confirmDoubt(s.id)} />
                <Chip label="Corregir" onPress={() => setEditing(s.id)} />
                <Chip label="Eliminar" onPress={() => apply(removeSet(e, s.id, now()))} />
              </View>
            )}
          </View>
        ))}
      </Section>

      <Section label={`Line-up · ${e.sets.length} actuaciones`}
        right={selecting ? null : <Pressable onPress={() => { setShowAll(true); setSelecting([]); }} accessibilityRole="button" hitSlop={8}>
          <Text style={styles.link}>UNIR EN B2B</Text></Pressable>}>
        {selecting ? <Notice>Toca las actuaciones que forman un B2B y pulsa «Unir».</Notice> : null}
        {showAll || selecting ? groups.map((g) => (
          <View key={g.day?.id ?? 'none'} style={{ gap: Space.sm }}>
            {groups.length > 1 || g.day ? <Text style={styles.day}>{g.day?.label ?? 'Sin día confirmado'}</Text> : null}
            {g.sets.map((s) => (
              <SetRow key={s.id} event={e} set={s} flags={setFlags(s.id)} selected={selecting?.includes(s.id)}
                onPress={() => (selecting ? toggleSelect(s.id) : setEditing(s.id))} />
            ))}
          </View>
        )) : (
          <Pressable onPress={() => setShowAll(true)} accessibilityRole="button" style={styles.collapsed}>
            <Text style={styles.collapsedText}>Ver las {e.sets.length - doubtful.length} actuaciones sin dudas</Text>
            <Meta>Toca una para corregirla, cambiar su día, escenario u horario</Meta>
          </Pressable>
        )}
      </Section>

      <Section label="Añadir artista">
        <View style={{ flexDirection: 'row', gap: Space.sm }}>
          <TextInput value={newArtist} onChangeText={setNewArtist} placeholder="Nombre que falta" placeholderTextColor={C.faint}
            accessibilityLabel="Nombre del artista que falta" style={styles.input}
            onSubmitEditing={() => { apply(addArtist(e, newArtist, { dayId: null, stageId: null }, now())); setNewArtist(''); }} />
          <Button label="Añadir" variant="ghost" disabled={!newArtist.trim()}
            onPress={() => { apply(addArtist(e, newArtist, { dayId: null, stageId: null }, now())); setNewArtist(''); }} />
        </View>
      </Section>

      <Section label={`Recuperación · ${Math.max(callsLeft, 0)} de ${MAX_CALLS - 1} análisis extra`}>
        {regions ? (
          <View style={{ gap: Space.sm }}>
            <Body muted>¿Qué parte del cartel quieres volver a leer? Lo nuevo se añade sin tocar tus correcciones.</Body>
            <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: Space.sm }}>
              {(Object.keys(REGIONS) as RegionKey[]).map((k) => <Chip key={k} label={REGIONS[k].label} onPress={() => recover(k)} />)}
            </View>
            <Button label="Cancelar" variant="ghost" onPress={() => setRegions(false)} />
          </View>
        ) : (
          <Button label="Reanalizar una zona del cartel" variant="ghost" disabled={callsLeft <= 0 || !!busy} onPress={() => setRegions(true)} />
        )}
        {e.analysis.review.length ? (
          <View style={{ gap: 4 }}>
            <Meta>Ajustes automáticos de la lectura</Meta>
            {e.analysis.review.map((r) => <Text key={r} style={styles.note}>· {r}</Text>)}
          </View>
        ) : null}
      </Section>

      {editing ? <SetEditor event={e} setId={editing} onChange={apply} onClose={() => setEditing(null)} /> : null}
    </Screen>
  );
}

const styles = StyleSheet.create({
  busy: { flexDirection: 'row', alignItems: 'center', gap: Space.md, padding: Space.md, borderRadius: Radius.md, backgroundColor: PS.raised },
  busyText: { color: C.text, fontFamily: Fonts.sansBold, fontSize: 15 },
  suggestion: { gap: Space.sm, padding: Space.md, borderRadius: Radius.md, borderWidth: 1, borderColor: C.cyan, backgroundColor: PS.raised },
  suggestionText: { color: C.text, fontFamily: Fonts.sans, fontSize: 15 },
  link: { color: C.acid, fontFamily: Fonts.monoBold, fontSize: 11 },
  day: { color: C.text, fontFamily: Fonts.display, fontSize: 20, textTransform: 'uppercase', marginTop: Space.sm },
  collapsed: { gap: 4, padding: Space.lg, borderRadius: Radius.md, borderWidth: 1, borderStyle: 'dashed', borderColor: PS.line },
  collapsedText: { color: C.text, fontFamily: Fonts.sansBold, fontSize: 15 },
  input: { flex: 1, minHeight: 48, borderWidth: 1.5, borderColor: C.line, borderRadius: Radius.md, backgroundColor: C.surface, color: C.text,
    fontFamily: Fonts.sans, fontSize: 16, paddingHorizontal: Space.md },
  note: { color: C.muted, fontFamily: Fonts.sans, fontSize: 13, lineHeight: 18 },
});
