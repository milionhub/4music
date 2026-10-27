/**
 * Bienvenida como el cartel de un festival: «#4MUSIC» de cabeza de cartel, un disco que gira, la cinta con
 * lo que conecta la app y el line-up de sus secciones, cada una con su color. Cierra con una entrada troquelada (sin
 * registro). Con «reducir movimiento», todo quieto y sin entradas animadas.
 */
import { useEffect } from 'react';
import { StyleSheet, Text, View } from 'react-native';
import Animated, {
  cancelAnimation, Easing, FadeInDown, ReduceMotion, useAnimatedStyle, useReducedMotion, useSharedValue, withRepeat, withTiming,
} from 'react-native-reanimated';

import { decorative } from '@/components/editorial';
import { Ticker } from '@/components/trackdna-poster';
import { C, Fonts, Space } from '@/constants/theme';
import { DM_SERIF_ITALIC, fitSize, fixedIdentity, PALETTES, SECTION_PALETTES } from '@/lib/artist-identity';

const PASS = fixedIdentity(SECTION_PALETTES.profile, 'anton');
const ANTON = PASS.type;
const TICKER = ['Conexiones', 'Samples', 'Sellos', 'Remezclas', 'Line-ups', 'B2B', 'Siempre con el motivo'];

/** El line-up: cada sección con su color de la app, de mayor a menor como en un cartel. */
const LINEUP = [
  { name: 'Inicio', note: 'La edición del día', palette: 'Infrarrojo', size: 60 },
  { name: 'TrackDNA', note: 'El ADN de cada canción', palette: 'Limón', size: 54 },
  { name: 'Carteles', note: 'Del cartel a tu ruta', palette: SECTION_PALETTES.posters, size: 50 },
  { name: 'Guardados', note: 'Tu cajón, sin conexión', palette: SECTION_PALETTES.saved, size: 46 },
  { name: 'Tu pase', note: 'Tus gustos, solo aquí', palette: 'Ácido', size: 42 },
].map((row) => ({ ...row, p: PALETTES.find((x) => x.name === row.palette) ?? PALETTES[0] }));

export function WelcomePoster({ width, screen }: { width: number; screen: string }) {
  const P = PASS.palette;
  const inner = width - Space.lg * 2;
  const head = fitSize('#4MUSIC', inner, ANTON, 170, 40);
  const tail = fitSize('por conexiones', inner * 0.7, DM_SERIF_ITALIC, 96, 32);
  const disc = Math.round(Math.min(inner * 0.24, tail * 1.6));
  const reduce = useReducedMotion();
  const spin = useSharedValue(0);
  useEffect(() => {
    if (reduce) return;
    spin.value = withRepeat(withTiming(360, { duration: 6000, easing: Easing.linear }), -1);
    return () => cancelAnimation(spin);
  }, [reduce, spin]);
  const rotate = useAnimatedStyle(() => ({ transform: [{ rotate: `${spin.value}deg` }] }));
  const enter = (i: number) => FadeInDown.delay(160 + i * 90).duration(420).reduceMotion(ReduceMotion.System);

  return (
    <View style={{ width }}>
      <View accessible accessibilityRole="header" accessibilityLabel="Bienvenido a #4MUSIC"
        style={{ backgroundColor: P.bg, overflow: 'hidden' }}>
        <View {...decorative} style={[styles.ring, { width: width * 0.9, height: width * 0.9, borderRadius: width, right: -width * 0.45, top: -width * 0.2, borderColor: P.glow }]} />
        <View {...decorative} style={[styles.flyerHead, { borderBottomColor: P.ink }]}>
          <Text style={[styles.mono, { color: P.ink }]}>Nº 001 · Bienvenida</Text>
          <Text style={[styles.mono, { color: P.ink }]}>Música electrónica</Text>
        </View>
        <Text {...decorative} numberOfLines={1}
          style={{ marginTop: Space.lg, paddingHorizontal: Space.lg, fontFamily: ANTON.family, fontSize: head, lineHeight: Math.round(head * 1.0),
            color: P.ink, includeFontPadding: false }}>
          #4MUSIC
        </Text>
        <View {...decorative} style={{ flexDirection: 'row', alignItems: 'center', paddingHorizontal: Space.lg, gap: Space.md }}>
          <Text numberOfLines={1} style={{ flexShrink: 1, fontFamily: Fonts.serifItalic, fontSize: tail, lineHeight: Math.round(tail * 1.15),
            color: P.pop, includeFontPadding: false }}>
            por conexiones
          </Text>
          <Animated.View style={[{ width: disc, height: disc, borderRadius: disc / 2, backgroundColor: P.ink, alignItems: 'center', justifyContent: 'center' }, rotate]}>
            <View style={{ position: 'absolute', width: disc * 0.8, height: disc * 0.8, borderRadius: disc, borderWidth: 1, borderColor: P.bg, opacity: 0.35 }} />
            <View style={{ position: 'absolute', width: disc * 0.6, height: disc * 0.6, borderRadius: disc, borderWidth: 1, borderColor: P.bg, opacity: 0.25 }} />
            <View style={{ width: disc * 0.34, height: disc * 0.34, borderRadius: disc, backgroundColor: P.pop, alignItems: 'center', justifyContent: 'center' }}>
              <View style={{ width: disc * 0.08, height: disc * 0.08, borderRadius: disc, backgroundColor: P.ink }} />
            </View>
            <View style={{ position: 'absolute', top: disc * 0.1, width: disc * 0.07, height: disc * 0.07, borderRadius: disc, backgroundColor: P.pop }} />
          </Animated.View>
        </View>
        <Text style={[styles.sub, { color: P.ink }]}>
          Descubre música electrónica por lo que la une: quién la firma, qué samplea, con quién comparte sello o cartel.
        </Text>
        <Ticker items={TICKER} color={P.pop} ink={P.onGlow} width={width} reduce={reduce} />
      </View>

      <View style={{ paddingHorizontal: Space.lg, paddingTop: Space.xl, gap: 6 }}>
        <View style={[styles.lineupHead, { borderTopColor: P.glow }]}>
          <Text accessibilityRole="header" style={[styles.mono, { color: P.glow }]}>El line-up</Text>
          <Text style={[styles.mono, { color: C.faint }]}>5 escenarios · 1 app</Text>
        </View>
        {LINEUP.map((row, i) => (
          <Animated.View key={row.name} entering={enter(i)} accessible accessibilityLabel={`${row.name}: ${row.note}`}
            style={[styles.band, { backgroundColor: row.p.bg, transform: [{ rotate: `${i % 2 ? 0.8 : -0.8}deg` }] }]}>
            <Text style={[styles.bandNum, { color: row.p.ink }]}>{String(i + 1).padStart(2, '0')}</Text>
            <View style={{ flex: 1 }}>
              <Text numberOfLines={1} adjustsFontSizeToFit
                style={{ fontFamily: ANTON.family, fontSize: row.size, lineHeight: Math.round(row.size * 1.02), color: row.p.ink, textTransform: 'uppercase', includeFontPadding: false }}>
                {row.name}
              </Text>
              <Text style={[styles.mono, { color: row.p.ink, opacity: 0.85 }]}>{row.note}</Text>
            </View>
          </Animated.View>
        ))}
      </View>

      <Animated.View entering={enter(LINEUP.length)} style={[styles.ticket, { borderColor: P.glow, marginHorizontal: Space.lg }]}>
        <View {...decorative} style={[styles.notch, { left: -12, backgroundColor: screen, borderColor: P.glow }]} />
        <View {...decorative} style={[styles.notch, { right: -12, backgroundColor: screen, borderColor: P.glow }]} />
        <View style={{ flex: 1, gap: 4 }}>
          <Text style={[styles.mono, { color: P.glow }]}>Entrada · admite 1</Text>
          <Text style={styles.ticketText}>Sin registro ni cuenta: tus gustos, guardados y carteles viven solo en este dispositivo.</Text>
        </View>
        <View {...decorative} style={[styles.stub, { borderLeftColor: P.glow }]}>
          <Text style={[styles.stubText, { color: P.glow }]}>FREE</Text>
        </View>
      </Animated.View>
    </View>
  );
}

const styles = StyleSheet.create({
  ring: { position: 'absolute', borderWidth: 3, opacity: 0.5 },
  flyerHead: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'baseline', marginTop: Space.lg, marginHorizontal: Space.lg,
    paddingBottom: 6, borderBottomWidth: 2 },
  mono: { fontFamily: Fonts.monoBold, fontSize: 11, letterSpacing: 1.4, textTransform: 'uppercase' },
  sub: { fontFamily: Fonts.sansBold, fontSize: 16, lineHeight: 22, maxWidth: 420, marginTop: Space.md, paddingHorizontal: Space.lg },
  lineupHead: { flexDirection: 'row', justifyContent: 'space-between', borderTopWidth: 2, paddingTop: Space.sm, marginBottom: Space.sm },
  band: { flexDirection: 'row', alignItems: 'center', gap: Space.md, paddingHorizontal: Space.lg, paddingVertical: Space.sm },
  bandNum: { fontFamily: Fonts.serifItalic, fontSize: 34, lineHeight: 40, width: 44 },
  ticket: { flexDirection: 'row', alignItems: 'stretch', marginTop: Space.xl, borderWidth: 2, borderStyle: 'dashed', borderRadius: 10,
    paddingVertical: Space.md, paddingLeft: Space.lg },
  notch: { position: 'absolute', top: '50%', marginTop: -12, width: 24, height: 24, borderRadius: 12, borderWidth: 2 },
  ticketText: { color: C.text, fontFamily: Fonts.sans, fontSize: 14, lineHeight: 20 },
  stub: { width: 64, marginLeft: Space.md, borderLeftWidth: 2, borderStyle: 'dashed', alignItems: 'center', justifyContent: 'center' },
  stubText: { fontFamily: ANTON.family, fontSize: 22, letterSpacing: 1, transform: [{ rotate: '-90deg' }], width: 80, textAlign: 'center' },
});
