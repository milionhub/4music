/**
 * Carteles 4 · Hoja de ruta (V6.8): solo para carteles con hora impresa por actuación (lib/poster-route).
 *
 * - «Tu ruta»: lo que marcas, en orden, con solapes y huecos libres. Sin nada marcado, la ruta que más te encaja sin
 *   solapes (pesos de «Para ti»), con un botón para usarla. Se guarda en el evento (`plan`), sin red.
 * - Parrilla: un escenario por columna sobre el eje de horas de la noche. Tocar marca o desmarca; mantener pulsado
 *   abre el perfil del artista si está identificado.
 */
import { router, useFocusEffect, useLocalSearchParams } from 'expo-router';
import { useCallback, useMemo, useState } from 'react';
import { Pressable, ScrollView, StyleSheet, Text, useWindowDimensions, View } from 'react-native';

import { decorative } from '@/components/editorial';
import { POSTER_TONE } from '@/components/poster';
import { Button, Screen, StateView, ToneProvider } from '@/components/ui';
import { C, Fonts, MaxContentWidth, Radius, Space } from '@/constants/theme';
import { display, fitSize, nameLines } from '@/lib/artist-identity';
import { eventArt } from '@/lib/poster-art';
import { eventFits, FIT_MIN } from '@/lib/poster-fit';
import { linkedMbid } from '@/lib/poster-identity';
import { clashes, clock, planOf, propose, routeItems, setPlan, type Slot, timeline, togglePlan } from '@/lib/poster-route';
import { useLibrary } from '@/state/library';
import { loadEvent, saveEvent } from '@/storage/poster-library';
import type { PosterEvent, PosterSet } from '@/types/poster';

const AXIS = 44;
const PX_PER_MIN = 1.1;
const MIN_COL = 96;
const MIN_BLOCK = 30;

export default function RouteScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const { width } = useWindowDimensions();
  const [event, setEvent] = useState<PosterEvent | null>(null);
  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [day, setDay] = useState<string | null>(null);
  useFocusEffect(useCallback(() => {
    setEvent(id ? loadEvent(id) : null);
    setLoaded(true);
  }, [id]));

  const lib = useLibrary();
  const taste = useMemo(() => ({ favorites: lib.favorites, saved: lib.savedTracks, styles: lib.preferences.declared_styles }),
    [lib.favorites, lib.savedTracks, lib.preferences.declared_styles]);
  const fits = useMemo(() => (event ? eventFits(event, taste) : []), [event, taste]);
  const slots = useMemo(() => (event ? timeline(event) : []), [event]);

  if (!loaded) return <Screen withTabBar={false}>{null}</Screen>;
  if (!event || slots.length < 2) {
    return (
      <Screen withTabBar={false}>
        <StateView kind="error" title="Sin hoja de ruta" message="Este cartel no tiene horas por actuación." actionLabel="Volver" onAction={() => router.back()} />
      </Screen>
    );
  }
  const e = event;
  const art = eventArt({ id: e.id, fingerprint: e.fingerprint, seeds: e.palette.seeds });
  const P = art.palette;
  const S = art.surfaces;
  const pageWidth = Math.min(width, MaxContentWidth);

  const score = new Map(fits.map((f) => [f.artist.id, f.score]));
  const weight = (s: PosterSet) => Math.max(0, ...s.artistIds.map((a) => score.get(a) ?? 0));
  const loves = (s: PosterSet) => s.artistIds.some((a) => (score.get(a) ?? 0) >= FIT_MIN);
  const plan = planOf(e);
  const proposal = plan.length ? [] : propose(slots, weight);
  const shown = plan.length ? plan : proposal;
  const items = routeItems(slots, shown);
  const clash = clashes(slots, plan);
  const clashing = new Set(clash.flatMap((c) => [c.a, c.b]));

  const days = [...new Set(slots.map((s) => s.day))];
  const currentDay = day && days.includes(day) ? day : days[0];
  const daySlots = slots.filter((s) => s.day === currentDay);
  const stageIds = [...new Set(e.sets.map((s) => s.stageId))].filter((x) => daySlots.some((s) => s.set.stageId === x));
  const first = Math.floor(Math.min(...daySlots.map((s) => s.start)) / 60) * 60;
  const last = Math.ceil(Math.max(...daySlots.map((s) => s.end)) / 60) * 60;

  const names = (s: PosterSet) => s.artistIds.map((a) => e.artists.find((x) => x.id === a)?.name).filter(Boolean)
    .join(s.artistIds.length > 1 ? ` ${s.connector ?? 'B2B'} ` : '');
  const stageName = (s: PosterSet) => (s.stageId ? e.stages.find((x) => x.id === s.stageId)?.name ?? null : null);
  const dayLabel = (d: string) => e.days.find((x) => x.id === d)?.label ?? 'Día';

  function save(next: PosterEvent) {
    const r = saveEvent(next);
    setError(r.ok ? null : r.message);
    if (r.ok) setEvent(next);
  }
  const openArtist = (s: PosterSet) => {
    const mbid = s.artistIds.map((a) => e.artists.find((x) => x.id === a)).map((a) => (a ? linkedMbid(a) : null)).find(Boolean);
    if (mbid) router.push(`/artist/${mbid}`);
  };

  const title = e.name ?? 'Sin nombre';
  const lines = nameLines(title, 2);
  const size = Math.min(...lines.map((l) => fitSize(display(l, art.type), pageWidth - Space.lg * 2, art.type, 64, 26)));

  return (
    <ToneProvider value={POSTER_TONE}>
    <Screen withTabBar={false} background={S.screen} topTint={P.bg}>
      <View style={{ marginHorizontal: -Space.lg, marginTop: -Space.lg, backgroundColor: P.bg, padding: Space.lg, gap: Space.md }}>
        <View style={styles.topRow}>
          <Pressable onPress={() => router.back()} accessibilityRole="button" accessibilityLabel="Volver" hitSlop={10}
            style={[styles.back, { borderColor: P.ink }]}>
            <Text style={[styles.backLabel, { color: P.ink }]}>←</Text>
          </Pressable>
          <Text style={[styles.mono, { color: P.ink }]}>Hoja de ruta</Text>
        </View>
        <View accessibilityRole="header" accessibilityLabel={`Hoja de ruta de ${title}`}>
          {lines.map((l, i) => (
            <Text key={i} style={{ color: P.ink, fontFamily: art.type.family, fontSize: size, lineHeight: Math.round(size * art.type.lineFactor * 1.04),
              letterSpacing: art.type.tracking, includeFontPadding: false }}>{display(l, art.type)}</Text>
          ))}
        </View>
        <Text style={[styles.mono, { color: P.ink }]}>
          {[`${slots.length} actuaciones con hora`, stageIds.length > 1 ? `${stageIds.length} escenarios` : null,
            `${clock(first)}–${clock(last)}`].filter(Boolean).join(' · ')}
        </Text>
      </View>

      {days.length > 1 ? (
        <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: Space.sm }}>
          {days.map((d) => (
            <Pressable key={d} onPress={() => setDay(d)} accessibilityRole="button" accessibilityState={{ selected: d === currentDay }}
              style={[styles.pill, { borderColor: P.glow, backgroundColor: d === currentDay ? P.glow : 'transparent' }]}>
              <Text style={[styles.mono, { color: d === currentDay ? P.onGlow : P.glow }]}>{dayLabel(d)}</Text>
            </Pressable>
          ))}
        </ScrollView>
      ) : null}

      {error ? <Text style={[styles.body, { color: C.danger }]}>{error}</Text> : null}

      <View style={{ gap: Space.md }}>
        <View style={[styles.head, { borderTopColor: P.glow }]}>
          <Text accessibilityRole="header" style={[styles.mono, { color: P.glow, flex: 1 }]}>{plan.length ? 'Tu ruta' : 'Ruta propuesta'}</Text>
          {plan.length ? (
            <Pressable onPress={() => save(setPlan(e, []))} accessibilityRole="button" hitSlop={8}>
              <Text style={[styles.mono, { color: C.muted }]}>Borrar</Text>
            </Pressable>
          ) : null}
        </View>
        {!plan.length && !proposal.length ? (
          <Text style={styles.body}>Toca en la parrilla las actuaciones que quieres ver: aquí verás tu ruta, sus solapes y los huecos libres.</Text>
        ) : null}
        {!plan.length && proposal.length ? (
          <Text style={styles.body}>Sin solapes y con lo que más te encaja de «Para ti». Úsala tal cual o toca la parrilla para hacer la tuya.</Text>
        ) : null}
        {items.map((it) => {
          if (it.kind === 'gap') {
            return <Text key={`gap-${it.from}`} style={[styles.gap, { borderColor: S.line }]}>{`Libre ${clock(it.from)}–${clock(it.to)}`}</Text>;
          }
          const s = it.slot.set;
          const other = clash.filter((c) => c.a === s.id || c.b === s.id);
          return (
            <View key={s.id} style={[styles.stop, { borderLeftColor: clashing.has(s.id) ? P.pop : P.glow }]}
              accessible accessibilityLabel={[`${clock(it.slot.start)} a ${clock(it.slot.end)}`, stageName(s), names(s),
                ...other.map((c) => `se solapa de ${clock(c.from)} a ${clock(c.to)}`)].filter(Boolean).join(', ')}>
              <Text style={[styles.mono, { color: C.muted }]}>
                {[`${clock(it.slot.start)}–${it.slot.endKnown ? clock(it.slot.end) : '…'}`, stageName(s)].filter(Boolean).join(' · ')}
              </Text>
              <Text style={styles.stopName} numberOfLines={2}>{names(s)}</Text>
              {other.map((c) => {
                const mate = slots.find((x) => x.set.id === (c.a === s.id ? c.b : c.a))!.set;
                return <Text key={`${c.a}-${c.b}`} style={[styles.clash, { color: P.pop }]}>{`⚠  Se solapa con ${names(mate)} (${clock(c.from)}–${clock(c.to)})`}</Text>;
              })}
            </View>
          );
        })}
        {!plan.length && proposal.length ? (
          <Button label="Usar esta ruta" onPress={() => save(setPlan(e, proposal))} />
        ) : null}
      </View>

      <View style={{ gap: Space.sm }}>
        <View style={[styles.head, { borderTopColor: P.glow }]}>
          <Text accessibilityRole="header" style={[styles.mono, { color: P.glow, flex: 1 }]}>Parrilla</Text>
          <Text style={[styles.mono, { color: C.muted }]}>Toca para marcar</Text>
        </View>
        <Grid slots={daySlots} stageIds={stageIds} first={first} last={last} width={pageWidth - Space.lg * 2} event={e}
          plan={plan} clashing={clashing} loves={loves} names={names} art={art}
          onToggle={(s) => save(togglePlan(e, s.id))} onLong={openArtist} />
        <Text style={styles.note}>♥ te encaja · ⚠ se solapa con otra que has marcado · mantén pulsado para abrir el perfil.</Text>
      </View>
    </Screen>
    </ToneProvider>
  );
}

function Grid({ slots, stageIds, first, last, width, event, plan, clashing, loves, names, art, onToggle, onLong }: {
  slots: Slot[]; stageIds: (string | null)[]; first: number; last: number; width: number; event: PosterEvent; plan: string[];
  clashing: Set<string>; loves: (s: PosterSet) => boolean; names: (s: PosterSet) => string; art: ReturnType<typeof eventArt>;
  onToggle: (s: PosterSet) => void; onLong: (s: PosterSet) => void;
}) {
  const P = art.palette;
  const S = art.surfaces;
  const col = Math.max(MIN_COL, (width - AXIS) / Math.max(1, stageIds.length));
  const height = (last - first) * PX_PER_MIN;
  const hours = Array.from({ length: (last - first) / 60 + 1 }, (_, i) => first + i * 60);
  return (
    <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ paddingRight: Space.sm }}>
      <View>
        <View style={{ flexDirection: 'row', marginLeft: AXIS }}>
          {stageIds.map((st) => (
            <Text key={st ?? 'none'} numberOfLines={1} style={[styles.stageHead, { width: col, color: C.text, borderBottomColor: P.glow }]}>
              {(st ? event.stages.find((x) => x.id === st)?.name : null) ?? 'Escenario'}
            </Text>
          ))}
        </View>
        <View style={{ flexDirection: 'row', height: height + 12 }}>
          <View style={{ width: AXIS }} {...decorative}>
            {hours.map((h) => (
              <Text key={h} style={[styles.hour, { top: (h - first) * PX_PER_MIN }]}>{clock(h)}</Text>
            ))}
          </View>
          {stageIds.map((st) => (
            <View key={st ?? 'none'} style={{ width: col, height, borderLeftWidth: StyleSheet.hairlineWidth, borderLeftColor: S.line }}>
              {hours.map((h) => <View key={h} {...decorative} style={[styles.rule, { top: (h - first) * PX_PER_MIN, backgroundColor: S.line }]} />)}
              {slots.filter((s) => s.set.stageId === st).map((s) => {
                const on = plan.includes(s.set.id);
                const warn = clashing.has(s.set.id);
                const h = Math.max(MIN_BLOCK, (s.end - s.start) * PX_PER_MIN - 3);
                const fg = on ? P.onGlow : C.text;
                return (
                  <Pressable key={s.set.id} onPress={() => onToggle(s.set)} onLongPress={() => onLong(s.set)} delayLongPress={400}
                    accessibilityRole="button" accessibilityState={{ selected: on }}
                    accessibilityLabel={[names(s.set), `${clock(s.start)} a ${clock(s.end)}`, loves(s.set) ? 'te encaja' : null,
                      on ? 'en tu ruta' : 'tocar para añadir', warn ? 'se solapa' : null].filter(Boolean).join(', ')}
                    style={({ pressed }) => [styles.block, {
                      top: (s.start - first) * PX_PER_MIN + 1, height: h, backgroundColor: on ? P.glow : S.raised,
                      borderColor: warn ? P.pop : loves(s.set) ? P.glow : S.line, borderWidth: warn || loves(s.set) ? 2 : 1,
                    }, pressed && { opacity: 0.75 }]}>
                    <Text style={[styles.blockName, { color: fg }]} numberOfLines={h > 60 ? 3 : 1}>
                      {loves(s.set) ? <Text style={{ color: on ? fg : P.glow }}>♥ </Text> : null}{names(s.set)}
                    </Text>
                    {h > 44 ? <Text style={[styles.blockTime, { color: on ? fg : C.muted }]}>{`${clock(s.start)}–${s.endKnown ? clock(s.end) : '…'}${warn ? '  ⚠' : ''}`}</Text> : null}
                  </Pressable>
                );
              })}
            </View>
          ))}
        </View>
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  topRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  back: { width: 44, height: 44, borderRadius: 22, borderWidth: 1.5, alignItems: 'center', justifyContent: 'center' },
  backLabel: { fontSize: 20, fontWeight: '800' },
  mono: { fontFamily: Fonts.monoBold, fontSize: 11, letterSpacing: 1.3, textTransform: 'uppercase' },
  body: { color: C.muted, fontFamily: Fonts.sans, fontSize: 15, lineHeight: 22 },
  note: { color: C.faint, fontFamily: Fonts.mono, fontSize: 11, lineHeight: 16 },
  head: { flexDirection: 'row', alignItems: 'center', borderTopWidth: 2, paddingTop: Space.sm, marginTop: Space.md },
  pill: { borderWidth: 1.5, borderRadius: 999, paddingHorizontal: Space.md, paddingVertical: 6 },
  stop: { borderLeftWidth: 4, paddingLeft: Space.md, gap: 2 },
  stopName: { color: C.text, fontFamily: Fonts.display, fontSize: 26, lineHeight: 30, textTransform: 'uppercase', includeFontPadding: false },
  clash: { fontFamily: Fonts.sansBold, fontSize: 13, lineHeight: 18 },
  gap: { color: C.muted, fontFamily: Fonts.monoBold, fontSize: 11, letterSpacing: 1, textTransform: 'uppercase', borderWidth: 1,
    borderStyle: 'dashed', borderRadius: Radius.sm, paddingVertical: 6, paddingHorizontal: Space.md, alignSelf: 'flex-start' },
  stageHead: { fontFamily: Fonts.monoBold, fontSize: 11, letterSpacing: 1, textTransform: 'uppercase', paddingHorizontal: 4, paddingBottom: 6,
    borderBottomWidth: 2, marginBottom: 6 },
  hour: { position: 'absolute', left: 0, color: C.faint, fontFamily: Fonts.mono, fontSize: 10, marginTop: -6 },
  rule: { position: 'absolute', left: 0, right: 0, height: StyleSheet.hairlineWidth },
  block: { position: 'absolute', left: 3, right: 3, borderRadius: Radius.sm, paddingHorizontal: 6, paddingVertical: 4, overflow: 'hidden', gap: 2 },
  blockName: { fontFamily: Fonts.sansBold, fontSize: 12, lineHeight: 15 },
  blockTime: { fontFamily: Fonts.mono, fontSize: 10 },
});

