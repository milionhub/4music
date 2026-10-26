/**
 * Carteles 3.5: explorador del line-up. Una fila por actuación (un B2B es una sola fila con cada nombre pulsable por
 * separado), datos solo si existen (escenario, bloque, hora) y filtros que solo aparecen si separan algo.
 * El estado de identidad se marca con un signo de ancho fijo: resolver artistas no mueve las filas.
 */
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';

import { C, Fonts, Radius, Space } from '@/constants/theme';
import type { EventArt } from '@/lib/poster-art';
import { type ExploreFilter, type Facets, NO_FILTER, timeLabel } from '@/lib/poster-explore';
import type { PosterArtist, PosterEvent, PosterSet } from '@/types/poster';

const MARK: Record<PosterArtist['link']['status'], { glyph: string; label: string }> = {
  pending: { glyph: '…', label: 'identificando' },
  linked: { glyph: '↗', label: 'identificado' },
  ambiguous: { glyph: '?', label: 'varios candidatos' },
  none: { glyph: '–', label: 'sin identificar' },
};

function FilterChip({ label, selected, onPress, art }: { label: string; selected: boolean; onPress: () => void; art: EventArt }) {
  const P = art.palette;
  return (
    <Pressable onPress={onPress} accessibilityRole="button" accessibilityState={{ selected }} hitSlop={4}
      style={({ pressed }) => [styles.chip, { borderColor: selected ? P.glow : art.surfaces.line, backgroundColor: selected ? P.glow : art.surfaces.raised },
        pressed && { opacity: 0.75 }]}>
      <Text style={[styles.chipLabel, { color: selected ? P.onGlow : C.text }]} numberOfLines={1}>{label}</Text>
    </Pressable>
  );
}

function Group<K extends string>({ label, all, items, value, onPick, art }: {
  label: string; all: string; items: { id: K; label: string; count: number }[]; value: K | null; onPick: (v: K | null) => void; art: EventArt;
}) {
  if (!items.length) return null;
  return (
    <View style={{ gap: 6 }}>
      <Text style={styles.groupLabel}>{label}</Text>
      <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.chips}>
        <FilterChip label={all} selected={value === null} onPress={() => onPick(null)} art={art} />
        {items.map((x) => <FilterChip key={x.id} label={`${x.label} · ${x.count}`} selected={value === x.id} onPress={() => onPick(value === x.id ? null : x.id)} art={art} />)}
      </ScrollView>
    </View>
  );
}

export function FilterBar({ facets, filter, onChange, shown, total, art }: {
  facets: Facets; filter: ExploreFilter; onChange: (f: ExploreFilter) => void; shown: number; total: number; art: EventArt;
}) {
  const active = filter.day !== null || filter.stage !== null || filter.band !== null || filter.style !== null;
  const any = facets.days.length || facets.stages.length || facets.bands.length || facets.styles.length;
  return (
    <View style={[styles.bar, { backgroundColor: art.surfaces.screen, borderBottomColor: art.surfaces.line }]}>
      {any ? (
        <>
          <Group label="Día" all="Todos" items={facets.days} value={filter.day} onPick={(day) => onChange({ ...filter, day })} art={art} />
          <Group label="Escenario" all="Todos" items={facets.stages} value={filter.stage} onPick={(stage) => onChange({ ...filter, stage })} art={art} />
          <Group label="Horario (horas impresas por artista)" all="Cualquiera" items={facets.bands} value={filter.band} onPick={(band) => onChange({ ...filter, band })} art={art} />
          <Group label="Estilo documentado" all="Todos" items={facets.styles} value={filter.style} onPick={(style) => onChange({ ...filter, style })} art={art} />
        </>
      ) : null}
      <View style={styles.countRow}>
        <Text style={styles.count} accessibilityLiveRegion="polite">
          {active ? `${shown} de ${total} actuaciones` : `${total} ${total === 1 ? 'actuación' : 'actuaciones'} · orden del cartel`}
        </Text>
        {active ? (
          <Pressable onPress={() => onChange(NO_FILTER)} accessibilityRole="button" hitSlop={10}>
            <Text style={[styles.clear, { color: art.palette.glow }]}>Quitar filtros</Text>
          </Pressable>
        ) : null}
      </View>
    </View>
  );
}

export function DayHeader({ label, count, art }: { label: string; count: number; art: EventArt }) {
  return (
    <View style={styles.dayHead} accessibilityRole="header">
      <Text style={[styles.day, { color: art.palette.glow }]}>{label}</Text>
      <View style={[styles.dayRule, { backgroundColor: art.surfaces.line }]} />
      <Text style={styles.dayCount}>{count}</Text>
    </View>
  );
}

/** `fits`: artistas que te encajan (Carteles 4): llevan un ♥ con el acento. */
export function LineupRow({ event, set, art, fits, onOpen }: {
  event: PosterEvent; set: PosterSet; art: EventArt; fits?: Set<string>; onOpen: (artistId: string) => void;
}) {
  const P = art.palette;
  const S = art.surfaces;
  const members = set.artistIds.map((id) => event.artists.find((a) => a.id === id)).filter((a): a is PosterArtist => !!a);
  const b2b = members.length > 1;
  const stage = set.stageId ? event.stages.find((s) => s.id === set.stageId)?.name : null;
  const time = timeLabel(set);
  const facts = [stage, set.block, time].filter((x): x is string => !!x);
  const partners = (a: PosterArtist) => members.filter((m) => m.id !== a.id).map((m) => m.name).join(' y ');
  return (
    <View style={[styles.row, { backgroundColor: S.raised, borderColor: b2b ? P.glow : S.line }]}>
      <View style={[styles.edge, { backgroundColor: b2b ? P.glow : S.line }]} />
      <View style={{ flex: 1, paddingVertical: Space.sm, gap: 4 }}>
        {b2b ? (
          <View style={[styles.b2bTag, { backgroundColor: P.glow }]}>
            <Text style={[styles.b2bText, { color: P.onGlow }]}>{set.connector ?? 'B2B'} · actuación conjunta</Text>
          </View>
        ) : null}
        <View style={styles.names}>
          {members.map((a, i) => (
            <View key={a.id} style={styles.nameWrap}>
              {i > 0 ? <Text style={[styles.connector, { color: P.glow }]}>{set.connector ?? 'B2B'}</Text> : null}
              <Pressable onPress={() => onOpen(a.id)} hitSlop={6} accessibilityRole="button"
                accessibilityLabel={[a.name, fits?.has(a.id) ? 'te encaja' : null, b2b ? `con ${partners(a)}` : null, MARK[a.link.status].label, 'abrir vista rápida'].filter(Boolean).join(', ')}
                style={({ pressed }) => [styles.nameBtn, pressed && { opacity: 0.7 }]}>
                {fits?.has(a.id) ? <Text style={[styles.fit, { color: P.glow }]}>♥</Text> : null}
                <Text style={[styles.name, a.link.status === 'none' && { color: C.muted }]}>{a.name}</Text>
                <Text style={[styles.mark, { color: a.link.status === 'linked' ? P.glow : a.link.status === 'ambiguous' ? C.orange : C.faint }]}>
                  {MARK[a.link.status].glyph}
                </Text>
              </Pressable>
            </View>
          ))}
        </View>
        {facts.length ? <Text style={styles.facts} numberOfLines={2}>{facts.join('  ·  ')}</Text> : null}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  bar: { paddingTop: Space.sm, paddingBottom: Space.md, gap: Space.md, borderBottomWidth: StyleSheet.hairlineWidth },
  groupLabel: { color: C.muted, fontFamily: Fonts.monoBold, fontSize: 10, letterSpacing: 1.4, textTransform: 'uppercase' },
  chips: { gap: Space.sm, paddingRight: Space.lg },
  chip: { minHeight: 40, justifyContent: 'center', paddingHorizontal: Space.md, borderRadius: Radius.pill, borderWidth: 1.5, maxWidth: 260 },
  chipLabel: { fontFamily: Fonts.sansBold, fontSize: 14 },
  countRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', gap: Space.md },
  count: { color: C.muted, fontFamily: Fonts.mono, fontSize: 12 },
  clear: { fontFamily: Fonts.monoBold, fontSize: 12, textDecorationLine: 'underline' },
  dayHead: { flexDirection: 'row', alignItems: 'center', gap: Space.md, paddingTop: Space.lg, paddingBottom: Space.sm },
  day: { fontFamily: Fonts.display, fontSize: 24, lineHeight: 28, textTransform: 'uppercase', flexShrink: 1 },
  dayRule: { flex: 1, height: 1 },
  dayCount: { color: C.muted, fontFamily: Fonts.mono, fontSize: 12 },
  row: { flexDirection: 'row', gap: Space.md, paddingRight: Space.md, borderRadius: Radius.md, borderWidth: 1, overflow: 'hidden', marginBottom: Space.sm },
  edge: { width: 4 },
  b2bTag: { alignSelf: 'flex-start', paddingHorizontal: Space.sm, paddingVertical: 2, borderRadius: Radius.pill },
  b2bText: { fontFamily: Fonts.monoBold, fontSize: 10, letterSpacing: 0.8, textTransform: 'uppercase' },
  names: { flexDirection: 'row', flexWrap: 'wrap', alignItems: 'center', columnGap: Space.sm },
  nameWrap: { flexDirection: 'row', alignItems: 'center', gap: Space.sm },
  nameBtn: { flexDirection: 'row', alignItems: 'center', gap: 6, minHeight: 40 },
  name: { color: C.text, fontFamily: Fonts.sansBold, fontSize: 17, lineHeight: 22 },
  fit: { fontSize: 14, fontWeight: '900' },
  mark: { width: 14, fontFamily: Fonts.monoBold, fontSize: 13, textAlign: 'center' },
  connector: { fontFamily: Fonts.monoBold, fontSize: 12 },
  facts: { color: C.muted, fontFamily: Fonts.mono, fontSize: 12, lineHeight: 17 },
});
