/**
 * Carteles 3.5: portada editorial del evento. Cuatro familias propias (billboard, ticket, stamp, column), elegidas de
 * forma estable por la huella del cartel; la paleta sale de sus colores (lib/poster-art). Solo datos guardados: sin
 * fechas, lugares ni cabezas de cartel deducidos; el line-up se resume en recuentos y en el orden impreso.
 * Textos sobre `palette.bg` con `palette.ink` y sobre superficies oscuras con texto claro o `glow` (contraste ≥ 4,5).
 */
import { Image } from 'expo-image';
import { useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { C, Fonts, Radius, Space } from '@/constants/theme';
import { display, fitSize, nameLines } from '@/lib/artist-identity';
import { type EventArt, inkOn } from '@/lib/poster-art';
import { lineupSummary } from '@/lib/poster-explore';
import { posterThumbUri } from '@/storage/poster-library';
import type { PosterEvent } from '@/types/poster';

const MAX_NAMES = 10;

/** Nombres en el orden del cartel (primera aparición en las actuaciones), sin jerarquía inventada. */
function orderedNames(e: PosterEvent): string[] {
  const ids = [...new Set([...e.sets].sort((a, b) => a.order - b.order).flatMap((s) => s.artistIds))];
  return ids.map((id) => e.artists.find((a) => a.id === id)?.name).filter((n): n is string => !!n);
}

export function EventCover({ event, art, width, onOpenPoster }: { event: PosterEvent; art: EventArt; width: number; onOpenPoster: () => void }) {
  const P = art.palette;
  const S = art.surfaces;
  const name = event.name ?? 'Sin nombre';
  const facts = [event.dateText, event.location].filter((x): x is string => !!x);
  const summary = lineupSummary(event).join(' · ');
  const names = orderedNames(event);
  const inner = width - Space.lg * 2;

  const title = (color: string, box: number, max: number) => {
    const lines = nameLines(name, 3);
    const size = Math.min(...lines.map((l) => fitSize(display(l, art.type), box, art.type, max, 26)));
    return (
      <View accessibilityRole="header" accessibilityLabel={name}>
        {lines.map((l, i) => (
          <Text key={i} style={{ color, fontFamily: art.type.family, fontSize: size, lineHeight: Math.round(size * art.type.lineFactor * 1.04),
            letterSpacing: art.type.tracking, includeFontPadding: false }}>
            {display(l, art.type)}
          </Text>
        ))}
      </View>
    );
  };
  const meta = (color: string, accent: string) => (
    <View style={{ gap: 3 }}>
      {facts.map((f) => <Text key={f} style={[styles.fact, { color }]}>{f}</Text>)}
      <Text style={[styles.summary, { color: accent }]}>{summary}</Text>
    </View>
  );
  const thumb = (frame: string) => <PosterThumb id={event.id} frame={frame} onPress={onOpenPoster} />;
  const lineup = (color: string, soft: string) => names.length ? (
    <View style={{ gap: 4 }}>
      <Text style={[styles.kicker, { color: soft }]}>Line-up · orden del cartel</Text>
      <Text style={[styles.names, { color }]} numberOfLines={3}>
        {names.slice(0, MAX_NAMES).join('  /  ')}{names.length > MAX_NAMES ? `  /  +${names.length - MAX_NAMES}` : ''}
      </Text>
    </View>
  ) : null;

  if (art.kind === 'billboard') {
    return (
      <View style={{ backgroundColor: P.bg, overflow: 'hidden' }}>
        <View style={{ padding: Space.lg, paddingTop: Space.xl, gap: Space.lg }}>
          <View style={styles.topRow}>
            <Text style={[styles.kicker, { color: P.ink }]}>Carteles · evento</Text>
            {thumb(P.ink)}
          </View>
          {title(P.ink, inner, 78)}
        </View>
        {/* Banda de color entre el nombre y los datos: nunca hay texto encima de `pop` (decorativo). */}
        <View style={[styles.band, { backgroundColor: P.pop }]} />
        <View style={{ backgroundColor: S.deep, padding: Space.lg, gap: Space.md }}>
          {meta(C.text, P.glow)}
          {lineup(C.text, C.muted)}
        </View>
      </View>
    );
  }
  if (art.kind === 'ticket') {
    return (
      <View style={{ padding: Space.lg, backgroundColor: S.screen }}>
        <View style={[styles.ticket, { backgroundColor: S.raised, borderColor: S.line }]}>
          <View style={[styles.stub, { backgroundColor: P.bg }]}>
            <Text style={[styles.stubFigure, { color: P.ink }]}>{String(event.artists.length).padStart(2, '0')}</Text>
            <Text style={[styles.stubLabel, { color: P.ink }]}>artistas</Text>
          </View>
          <View style={styles.perforation}>
            {Array.from({ length: 9 }, (_, i) => <View key={i} style={[styles.hole, { backgroundColor: S.screen }]} />)}
          </View>
          <View style={{ flex: 1, padding: Space.lg, gap: Space.md }}>
            <View style={styles.topRow}>
              <Text style={[styles.kicker, { color: P.glow }]}>Admite uno · Carteles</Text>
              {thumb(P.glow)}
            </View>
            {title(P.glow, inner - 88 - 16 - Space.lg * 2, 60)}
            {meta(C.text, P.glow)}
          </View>
        </View>
        <View style={{ paddingTop: Space.md }}>{lineup(C.text, C.muted)}</View>
      </View>
    );
  }
  if (art.kind === 'stamp') {
    const disc = Math.round(width * 0.62);
    return (
      <View style={{ backgroundColor: P.bg, overflow: 'hidden' }}>
        <View style={[styles.disc, { width: disc, height: disc, borderRadius: disc / 2, backgroundColor: P.pop, right: -disc * 0.28, top: -disc * 0.45 }]} />
        <View style={{ padding: Space.lg, paddingTop: Space.xl, gap: Space.lg }}>
          <View style={styles.topRow}>
            <View style={[styles.seal, { borderColor: P.ink }]}>
              <Text style={[styles.sealText, { color: P.ink }]}>{event.sets.length}{'\n'}sets</Text>
            </View>
            {thumb(P.ink)}
          </View>
          <View style={{ height: Space.xl }} />
          {title(P.ink, inner, 72)}
          {meta(P.ink, P.ink)}
        </View>
        <View style={{ backgroundColor: S.deep, padding: Space.lg }}>{lineup(C.text, C.muted)}</View>
      </View>
    );
  }
  // column: rejilla suiza con una columna de color y el nombre en el acento de la paleta.
  return (
    <View style={{ backgroundColor: S.screen }}>
      <View style={{ height: 10, backgroundColor: P.bg }} />
      <View style={{ flexDirection: 'row' }}>
        <View style={{ width: 14, backgroundColor: P.pop }} />
        <View style={{ flex: 1, padding: Space.lg, gap: Space.lg }}>
          <View style={styles.topRow}>
            <Text style={[styles.kicker, { color: P.glow }]}>Carteles · evento</Text>
            {thumb(P.glow)}
          </View>
          {title(P.glow, inner - 14, 70)}
          <View style={[styles.rule, { backgroundColor: S.line }]} />
          {meta(C.text, P.glow)}
          {lineup(C.text, C.muted)}
        </View>
      </View>
    </View>
  );
}

/** Miniatura enmarcada del cartel original: abre el cartel completo. */
function PosterThumb({ id, frame, onPress }: { id: string; frame: string; onPress: () => void }) {
  const [failed, setFailed] = useState(false);
  return (
    <Pressable onPress={onPress} accessibilityRole="imagebutton" accessibilityLabel="Ver el cartel original completo" hitSlop={8}
      style={({ pressed }) => [styles.thumb, { borderColor: frame }, pressed && { opacity: 0.8 }]}>
      {failed ? <Text style={[styles.thumbFallback, { color: frame }]}>▦</Text>
        : <Image source={{ uri: posterThumbUri(id) }} style={StyleSheet.absoluteFill} contentFit="cover" onError={() => setFailed(true)} />}
      <View style={[styles.thumbTag, { backgroundColor: frame }]}><Text style={[styles.thumbTagText, { color: inkOn(frame) }]}>⤢</Text></View>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  band: { height: 22, marginHorizontal: -Space.xl, marginTop: Space.sm, marginBottom: -Space.sm, transform: [{ rotate: '-2.5deg' }] },
  topRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'flex-start', gap: Space.md },
  kicker: { fontFamily: Fonts.monoBold, fontSize: 11, letterSpacing: 1.6, textTransform: 'uppercase' },
  fact: { fontFamily: Fonts.monoBold, fontSize: 14, letterSpacing: 0.5, textTransform: 'uppercase' },
  summary: { fontFamily: Fonts.mono, fontSize: 13 },
  names: { fontFamily: Fonts.sansBold, fontSize: 15, lineHeight: 22 },
  ticket: { flexDirection: 'row', borderRadius: Radius.lg, borderWidth: 1, overflow: 'hidden' },
  stub: { width: 88, alignItems: 'center', justifyContent: 'center', paddingVertical: Space.lg, gap: 2 },
  stubFigure: { fontFamily: Fonts.display, fontSize: 40, lineHeight: 44 },
  stubLabel: { fontFamily: Fonts.monoBold, fontSize: 10, letterSpacing: 1.2, textTransform: 'uppercase' },
  perforation: { width: 16, justifyContent: 'space-evenly', alignItems: 'center', marginLeft: -8 },
  hole: { width: 10, height: 10, borderRadius: 5 },
  disc: { position: 'absolute' },
  seal: { width: 64, height: 64, borderRadius: 32, borderWidth: 2, alignItems: 'center', justifyContent: 'center', transform: [{ rotate: '12deg' }] },
  sealText: { fontFamily: Fonts.monoBold, fontSize: 12, lineHeight: 14, textAlign: 'center', textTransform: 'uppercase' },
  rule: { height: StyleSheet.hairlineWidth },
  thumb: { width: 60, height: 76, borderWidth: 2, borderRadius: Radius.sm, overflow: 'hidden', backgroundColor: '#000', alignItems: 'center', justifyContent: 'center' },
  thumbFallback: { fontSize: 22 },
  thumbTag: { position: 'absolute', right: 0, bottom: 0, paddingHorizontal: 4, borderTopLeftRadius: Radius.sm },
  thumbTagText: { fontSize: 11, fontWeight: '800' },
});
