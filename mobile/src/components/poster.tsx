/**
 * Carteles 3.1–3.3: piezas de interfaz funcionales (biblioteca, revisión y evento básico) sobre el sistema actual
 * (Anton, Space Grotesk/Mono, superficies teñidas). La portada editorial definitiva y el explorador son de 3.5.
 */
import { Image } from 'expo-image';
import { useState } from 'react';
import { Modal, Pressable, ScrollView, StyleSheet, Text, TextInput, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { Button, Chip, Meta } from '@/components/ui';
import { C, Fonts, Radius, Space } from '@/constants/theme';
import { fixedIdentity, surfaces } from '@/lib/artist-identity';
import { eventArt } from '@/lib/poster-art';
import {
  addDay, addStage, FLAG_TEXT, removeSet, renameArtist, setContext, setLabel, splitSet, updateSet, userTime,
} from '@/lib/poster-model';
import { posterThumbUri } from '@/storage/poster-library';
import type { Flag, PosterEvent, PosterIndexEntry, PosterSet } from '@/types/poster';

export const POSTER_ID = fixedIdentity('Infrarrojo', 'anton');
export const PS = surfaces(POSTER_ID.palette);

export const STATUS_LABEL: Record<PosterEvent['status'], string> = { draft: 'Por revisar', partial: 'Incompleto', confirmed: 'Confirmado' };

const now = () => new Date().toISOString();

/** Tarjeta de la biblioteca: miniatura del cartel enmarcada con la paleta del evento (la misma de su portada),
 *  estado si está por revisar y un botón de acciones (editar, eliminar) además de la pulsación larga. */
export function PosterCard({ entry, width, onPress, onActions }: {
  entry: PosterIndexEntry; width: number; onPress: () => void; onActions: () => void;
}) {
  const P = eventArt(entry).palette;
  const [failed, setFailed] = useState(false);
  return (
    <Pressable onPress={onPress} onLongPress={onActions} delayLongPress={450} accessibilityRole="button"
      accessibilityLabel={[entry.name ?? 'Cartel sin nombre', entry.dateText, STATUS_LABEL[entry.status], 'Abrir'].filter(Boolean).join(', ')}
      accessibilityActions={[{ name: 'actions', label: 'Editar o eliminar' }]}
      onAccessibilityAction={(e) => e.nativeEvent.actionName === 'actions' && onActions()}
      style={({ pressed }) => [styles.card, { width, borderColor: P.bg, backgroundColor: P.bg }, pressed && { opacity: 0.85 }]}>
      <View style={{ width: '100%', aspectRatio: 0.8, backgroundColor: PS.deep }}>
        {failed ? <Text style={[styles.cardGlyph, { color: P.glow }]}>▦</Text>
          : <Image source={{ uri: posterThumbUri(entry.id) }} style={StyleSheet.absoluteFill} contentFit="cover" onError={() => setFailed(true)} />}
        {entry.status !== 'confirmed' ? (
          <View style={[styles.badge, { backgroundColor: entry.status === 'partial' ? C.orange : C.acid }]}>
            <Text style={styles.badgeLabel}>{STATUS_LABEL[entry.status]}</Text>
          </View>
        ) : null}
        <Pressable onPress={onActions} accessibilityRole="button" accessibilityLabel={`Acciones de ${entry.name ?? 'este cartel'}`} hitSlop={6}
          style={({ pressed }) => [styles.more, pressed && { opacity: 0.7 }]}>
          <Text style={styles.moreLabel}>•••</Text>
        </Pressable>
      </View>
      <View style={{ padding: Space.sm, paddingBottom: Space.md, gap: 2 }}>
        <Text style={[styles.cardTitle, { color: P.ink }]} numberOfLines={2}>{entry.name ?? 'Sin nombre'}</Text>
        <Text style={[styles.cardMeta, { color: P.ink }]} numberOfLines={1}>{[entry.dateText, `${entry.artists} artistas`].filter(Boolean).join(' · ')}</Text>
      </View>
    </Pressable>
  );
}

export function Field({ label, value, onCommit, placeholder, check, onConfirm }: {
  label: string; value: string | null; onCommit: (v: string) => void; placeholder?: string; check?: boolean; onConfirm?: () => void;
}) {
  const [text, setText] = useState(value ?? '');
  const [prev, setPrev] = useState(value);
  if (prev !== value) {
    setPrev(value);
    setText(value ?? '');
  }
  return (
    <View style={{ gap: 6 }}>
      <View style={styles.fieldHead}>
        <Meta>{label}</Meta>
        {check ? (
          <Pressable onPress={onConfirm} accessibilityRole="button" accessibilityLabel={`Confirmar ${label}`} hitSlop={8}>
            <Text style={styles.check}>COMPRUÉBALO · ✓ OK</Text>
          </Pressable>
        ) : null}
      </View>
      <TextInput value={text} onChangeText={setText} onEndEditing={() => text !== (value ?? '') && onCommit(text)}
        placeholder={placeholder ?? 'No aparece en el cartel'} placeholderTextColor={C.faint} accessibilityLabel={label}
        style={[styles.input, check && { borderColor: C.orange }]} />
    </View>
  );
}

export function FlagNote({ flags }: { flags: Flag[] }) {
  if (!flags.length) return null;
  return <Text style={styles.flag}>{flags.map((f) => FLAG_TEXT[f]).join(' · ')}</Text>;
}

export function SetRow({ event, set, flags, note, selected, onPress, onLongPress }: {
  event: PosterEvent; set: PosterSet; flags?: Flag[]; note?: string | null; selected?: boolean; onPress?: () => void; onLongPress?: () => void;
}) {
  const ctx = setContext(event, set);
  const b2b = set.artistIds.length > 1;
  return (
    <Pressable onPress={onPress} onLongPress={onLongPress} disabled={!onPress} accessibilityRole={onPress ? 'button' : 'text'}
      accessibilityState={{ selected: !!selected }}
      accessibilityLabel={[setLabel(event, set), b2b ? 'actuación conjunta' : null, ctx].filter(Boolean).join(', ')}
      style={({ pressed }) => [styles.row, selected && { borderColor: C.acid, backgroundColor: C.surfaceHigh }, pressed && { opacity: 0.8 }]}>
      <View style={[styles.edge, { backgroundColor: flags?.length ? C.orange : b2b ? C.cyan : PS.line }]} />
      <View style={{ flex: 1, gap: 2 }}>
        <Text style={styles.rowTitle}>{setLabel(event, set)}</Text>
        {ctx ? <Meta>{ctx}</Meta> : null}
        {flags ? <FlagNote flags={flags} /> : null}
        {note ? <Meta style={{ color: C.cyan }}>{note}</Meta> : null}
      </View>
      {b2b ? <Text style={styles.b2b}>{set.connector ?? 'B2B'}</Text> : null}
    </Pressable>
  );
}

/** Editor de una actuación: nombres, día, escenario, hora, separar B2B y eliminar. Cada cambio se guarda al momento. */
export function SetEditor({ event, setId, onChange, onClose }: {
  event: PosterEvent; setId: string; onChange: (e: PosterEvent) => void; onClose: () => void;
}) {
  const set = event.sets.find((s) => s.id === setId);
  const [newDay, setNewDay] = useState('');
  const [newStage, setNewStage] = useState('');
  const [timeError, setTimeError] = useState<string | null>(null);
  if (!set) return null;

  const commitTime = (field: 'start' | 'end', text: string) => {
    const t = userTime(text);
    if (t === undefined) return setTimeError('Usa el formato HH:MM, por ejemplo 23:30');
    setTimeError(null);
    if (t !== set[field]) onChange(updateSet(event, set.id, { [field]: t }, now()));
  };

  return (
    <Modal animationType="slide" presentationStyle="pageSheet" onRequestClose={onClose}>
      <SafeAreaView style={{ flex: 1, backgroundColor: C.bg }}>
        <ScrollView contentContainerStyle={{ padding: Space.lg, gap: Space.xl }} keyboardShouldPersistTaps="handled">
          <View style={styles.fieldHead}>
            <Text style={styles.sheetTitle}>{set.artistIds.length > 1 ? 'Actuación conjunta' : 'Actuación'}</Text>
            <Pressable onPress={onClose} accessibilityRole="button" accessibilityLabel="Cerrar" hitSlop={10}><Text style={styles.close}>✕</Text></Pressable>
          </View>
          {set.meta.printed ? <Meta>Leído en el cartel: {set.meta.printed}</Meta> : null}

          {set.artistIds.map((id, i) => {
            const a = event.artists.find((x) => x.id === id);
            return a ? <Field key={id} label={set.artistIds.length > 1 ? `Artista ${i + 1}` : 'Artista'} value={a.name}
              onCommit={(v) => onChange(renameArtist(event, id, v, now()))} placeholder="Nombre del artista" /> : null;
          })}

          <View style={{ gap: Space.sm }}>
            <Meta>Día</Meta>
            <View style={styles.chips}>
              <Chip label="Sin día" selected={set.dayId === null} onPress={() => onChange(updateSet(event, set.id, { dayId: null }, now()))} />
              {event.days.map((d) => <Chip key={d.id} label={d.label} selected={set.dayId === d.id} onPress={() => onChange(updateSet(event, set.id, { dayId: d.id }, now()))} />)}
            </View>
            <TextInput value={newDay} onChangeText={setNewDay} placeholder="Añadir día (p. ej. «Sábado 12»)" placeholderTextColor={C.faint} style={styles.input}
              accessibilityLabel="Añadir día" onSubmitEditing={() => {
                const e = addDay(event, newDay, now());
                const day = e.days.find((d) => d.label === newDay.trim());
                onChange(day ? updateSet(e, set.id, { dayId: day.id }, now()) : e);
                setNewDay('');
              }} />
          </View>

          <View style={{ gap: Space.sm }}>
            <Meta>Escenario</Meta>
            <View style={styles.chips}>
              <Chip label="Sin escenario" selected={set.stageId === null} onPress={() => onChange(updateSet(event, set.id, { stageId: null }, now()))} />
              {event.stages.map((s) => <Chip key={s.id} label={s.name} selected={set.stageId === s.id} onPress={() => onChange(updateSet(event, set.id, { stageId: s.id }, now()))} />)}
            </View>
            <TextInput value={newStage} onChangeText={setNewStage} placeholder="Añadir escenario" placeholderTextColor={C.faint} style={styles.input}
              accessibilityLabel="Añadir escenario" onSubmitEditing={() => {
                const e = addStage(event, newStage, now());
                const stage = e.stages.find((s) => s.name === newStage.trim());
                onChange(stage ? updateSet(e, set.id, { stageId: stage.id }, now()) : e);
                setNewStage('');
              }} />
          </View>

          <View style={{ gap: Space.sm }}>
            <Meta>{set.timeScope === 'block' ? 'Horario (impreso para el bloque, no para cada artista)' : 'Horario'}</Meta>
            <View style={{ flexDirection: 'row', gap: Space.md }}>
              <View style={{ flex: 1 }}><Field label="Inicio" value={set.start} placeholder="HH:MM" onCommit={(v) => commitTime('start', v)} /></View>
              <View style={{ flex: 1 }}><Field label="Fin" value={set.end} placeholder="HH:MM" onCommit={(v) => commitTime('end', v)} /></View>
            </View>
            {set.endsNextDay ? <Meta style={{ color: C.cyan }}>Termina al día siguiente</Meta> : null}
            {timeError ? <Text style={styles.flag}>{timeError}</Text> : null}
          </View>

          <View style={{ gap: Space.md }}>
            {set.artistIds.length > 1 ? <Button label="Separar en actuaciones individuales" variant="ghost" onPress={() => { onChange(splitSet(event, set.id, now())); onClose(); }} /> : null}
            <Button label="Eliminar actuación" variant="danger" onPress={() => { onChange(removeSet(event, set.id, now())); onClose(); }} />
          </View>
        </ScrollView>
      </SafeAreaView>
    </Modal>
  );
}

const styles = StyleSheet.create({
  card: { borderWidth: 2, borderRadius: Radius.md, overflow: 'hidden', backgroundColor: PS.raised },
  badge: { position: 'absolute', top: Space.sm, left: Space.sm, paddingHorizontal: Space.sm, paddingVertical: 3, borderRadius: Radius.pill },
  badgeLabel: { color: C.onAccent, fontFamily: Fonts.monoBold, fontSize: 10, textTransform: 'uppercase' },
  cardTitle: { fontFamily: Fonts.display, fontSize: 18, lineHeight: 21, textTransform: 'uppercase' },
  cardMeta: { fontFamily: Fonts.mono, fontSize: 11 },
  cardGlyph: { fontSize: 40, textAlign: 'center', marginTop: '40%' },
  more: { position: 'absolute', top: Space.xs, right: Space.xs, width: 40, height: 40, borderRadius: 20, alignItems: 'center', justifyContent: 'center',
    backgroundColor: 'rgba(7,6,11,0.78)' },
  moreLabel: { color: C.text, fontSize: 12, fontWeight: '800', letterSpacing: 1 },
  fieldHead: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', gap: Space.md },
  check: { color: C.orange, fontFamily: Fonts.monoBold, fontSize: 11 },
  input: { minHeight: 48, borderWidth: 1.5, borderColor: C.line, borderRadius: Radius.md, backgroundColor: C.surface, color: C.text,
    fontFamily: Fonts.sans, fontSize: 16, paddingHorizontal: Space.md },
  flag: { color: C.orange, fontFamily: Fonts.sans, fontSize: 13, lineHeight: 18 },
  row: { flexDirection: 'row', alignItems: 'center', gap: Space.md, minHeight: 56, paddingVertical: Space.sm, paddingRight: Space.md,
    borderRadius: Radius.md, borderWidth: 1, borderColor: PS.line, backgroundColor: PS.raised, overflow: 'hidden' },
  edge: { width: 4, alignSelf: 'stretch' },
  rowTitle: { color: C.text, fontFamily: Fonts.sansBold, fontSize: 16, lineHeight: 21 },
  b2b: { color: C.cyan, fontFamily: Fonts.monoBold, fontSize: 12 },
  chips: { flexDirection: 'row', flexWrap: 'wrap', gap: Space.sm },
  sheetTitle: { color: C.text, fontFamily: Fonts.display, fontSize: 28, textTransform: 'uppercase' },
  close: { color: C.text, fontSize: 22 },
});
