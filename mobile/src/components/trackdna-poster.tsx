/**
 * Cartel de inicio de TrackDNA (V6.6), como el flyer de una sesión: cabecera con número de edición y fecha, «TRACK» en
 * display a todo ancho, un código de barras de ADN que late, la banda «DNA» con un disco girando y una cinta con lo que
 * lee cada ficha. La paleta es la del día (lib/trackdna-home.ts). Con «reducir movimiento», todo quieto.
 */
import { useEffect, useState } from 'react';
import { StyleSheet, Text, View } from 'react-native';
import Animated, {
  cancelAnimation, Easing, type SharedValue, useAnimatedStyle, useReducedMotion, useSharedValue, withRepeat, withSequence,
  withTiming,
} from 'react-native-reanimated';

import { decorative } from '@/components/editorial';
import { Fonts, Space } from '@/constants/theme';
import { DM_SERIF_ITALIC, fitSize } from '@/lib/artist-identity';
import { type DailyEdition, TICKER } from '@/lib/trackdna-home';

const BAR_GAP = 3;
const BARCODE_H = 46;

export function TrackDnaPoster({ edition, width, subtitle }: { edition: DailyEdition; width: number; subtitle: string }) {
  const P = edition.id.palette;
  const inner = width - Space.lg * 2;
  const anton = edition.id.type;
  const track = fitSize('TRACK', inner, anton, 170, 40);
  const dna = fitSize('DNA', inner * 0.62, DM_SERIF_ITALIC, 150, 40);
  const ring = width * 0.46;
  const reduce = useReducedMotion();
  // Un solo reloj para todas las barras: cada una lo lee con su fase.
  const beat = useSharedValue(0);
  const spin = useSharedValue(0);
  useEffect(() => {
    if (reduce) return;
    beat.value = withRepeat(withSequence(withTiming(1, { duration: 480, easing: Easing.out(Easing.quad) }),
      withTiming(0, { duration: 480, easing: Easing.in(Easing.quad) })), -1);
    spin.value = withRepeat(withTiming(360, { duration: 5400, easing: Easing.linear }), -1);
    return () => {
      cancelAnimation(beat);
      cancelAnimation(spin);
    };
  }, [reduce, beat, spin]);
  const disc = useAnimatedStyle(() => ({ transform: [{ rotate: `${spin.value}deg` }] }));
  const discSize = dna * 0.66;

  return (
    <View accessible accessibilityRole="header" accessibilityLabel={`TrackDNA, edición ${edition.issue}, ${edition.date}`}
      style={{ width, backgroundColor: P.bg, overflow: 'hidden' }}>
      <View {...decorative} style={{ position: 'absolute', right: -ring * 0.28, top: -ring * 0.58, width: ring, height: ring, borderRadius: ring / 2,
        borderWidth: 3, borderColor: P.ink }} />
      <View {...decorative} style={[styles.flyerHead, { borderBottomColor: P.ink }]}>
        <Text style={[styles.flyerText, { color: P.ink }]}>{edition.issue}</Text>
        <Text style={[styles.flyerText, { color: P.ink }]}>{`Lectura de canciones · ${edition.date}`}</Text>
      </View>
      <Text {...decorative} numberOfLines={1}
        style={{ marginTop: Space.md, paddingHorizontal: Space.lg, fontFamily: anton.family, fontSize: track, lineHeight: Math.round(track * 0.98),
          color: P.ink, includeFontPadding: false }}>
        TRACK
      </Text>
      <View {...decorative} style={{ flexDirection: 'row', alignItems: 'flex-end', gap: BAR_GAP, height: BARCODE_H, paddingHorizontal: Space.lg, marginBottom: Space.sm }}>
        {edition.bars.map((h, i) => (
          <Bar key={i} height={h} phase={(i * 7) % 11 / 11} beat={beat} color={i % 6 === 4 ? P.pop : P.ink} />
        ))}
      </View>
      <View {...decorative} style={{ backgroundColor: P.ink, paddingHorizontal: Space.lg, flexDirection: 'row', alignItems: 'center', overflow: 'hidden' }}>
        <Text numberOfLines={1} style={{ fontFamily: Fonts.serifItalic, fontSize: dna, lineHeight: Math.round(dna * 1.12), color: P.bg, includeFontPadding: false }}>
          DNA
        </Text>
        <View style={{ flex: 1, alignItems: 'flex-end', justifyContent: 'center' }}>
          {/* Disco: galletas concéntricas y una marca que deja ver el giro. */}
          <Animated.View style={[{ width: discSize, height: discSize, borderRadius: discSize / 2, backgroundColor: P.pop,
            alignItems: 'center', justifyContent: 'center' }, disc]}>
            <View style={{ position: 'absolute', width: discSize * 0.78, height: discSize * 0.78, borderRadius: discSize, borderWidth: 1, borderColor: P.ink, opacity: 0.35 }} />
            <View style={{ width: discSize * 0.34, height: discSize * 0.34, borderRadius: discSize, backgroundColor: P.bg, alignItems: 'center', justifyContent: 'center' }}>
              <View style={{ width: discSize * 0.08, height: discSize * 0.08, borderRadius: discSize, backgroundColor: P.ink }} />
            </View>
            <View style={{ position: 'absolute', top: discSize * 0.1, width: discSize * 0.07, height: discSize * 0.07, borderRadius: discSize, backgroundColor: P.ink }} />
          </Animated.View>
        </View>
      </View>
      <Text style={[styles.sub, { color: P.ink }]}>{subtitle}</Text>
      <Ticker color={P.pop} ink={P.ink} width={width} reduce={reduce} />
    </View>
  );
}

function Bar({ height, phase, beat, color }: { height: number; phase: number; beat: SharedValue<number>; color: string }) {
  const style = useAnimatedStyle(() => {
    // Cada barra se mueve con el mismo pulso, desfasada: una ola, no un parpadeo.
    const t = (beat.value + phase) % 1;
    const wave = 0.82 + 0.18 * Math.sin(t * Math.PI);
    return { height: Math.max(4, BARCODE_H * height * wave) };
  });
  return <Animated.View style={[{ flex: 1, borderRadius: 1, backgroundColor: color }, style]} />;
}

/** Cinta que corre en bucle: el texto dos veces seguidas, desplazado lo que mide una copia. */
function Ticker({ color, ink, width, reduce }: { color: string; ink: string; width: number; reduce: boolean }) {
  const [copy, setCopy] = useState(0);
  const x = useSharedValue(0);
  useEffect(() => {
    if (reduce || !copy) return;
    x.value = 0;
    x.value = withRepeat(withTiming(-copy, { duration: copy * 28, easing: Easing.linear }), -1);
    return () => cancelAnimation(x);
  }, [copy, reduce, x]);
  const move = useAnimatedStyle(() => ({ transform: [{ translateX: x.value }] }));
  const text = `${TICKER.join('  ✶  ')}  ✶  `;
  return (
    <View {...decorative} style={{ width, backgroundColor: color, overflow: 'hidden', paddingVertical: 7, marginTop: Space.lg }}>
      <Animated.View style={[{ flexDirection: 'row', width: 4000 }, move]}>
        {[0, 1, 2].map((i) => (
          <Text key={i} onLayout={i === 0 ? (e) => setCopy(Math.round(e.nativeEvent.layout.width)) : undefined}
            numberOfLines={1} style={[styles.ticker, { color: ink }]}>
            {text}
          </Text>
        ))}
      </Animated.View>
    </View>
  );
}

const styles = StyleSheet.create({
  flyerHead: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'baseline', marginTop: Space.lg, marginHorizontal: Space.lg,
    paddingBottom: 6, borderBottomWidth: 2 },
  flyerText: { fontFamily: Fonts.monoBold, fontSize: 11, letterSpacing: 1.4, textTransform: 'uppercase' },
  sub: { fontFamily: Fonts.sansBold, fontSize: 16, lineHeight: 22, maxWidth: 420, marginTop: Space.md, paddingHorizontal: Space.lg },
  ticker: { fontFamily: Fonts.monoBold, fontSize: 12, letterSpacing: 1.6, textTransform: 'uppercase' },
});
