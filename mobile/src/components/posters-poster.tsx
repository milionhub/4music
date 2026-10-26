/**
 * Cabecera de Carteles (V6.8), como un cartel pegado en la calle: papeles superpuestos, «CARTELES» a todo ancho, una
 * parrilla de horarios en miniatura que recorre un cabezal (la hora de la noche), la banda «line-up» con un sello
 * «Para ti» y una cinta con lo que hace la sección. Decoración, no datos: el número es el de eventos guardados.
 * Con «reducir movimiento», todo quieto.
 */
import type { ReactNode } from 'react';
import { useEffect } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import Animated, {
  cancelAnimation, Easing, useAnimatedStyle, useReducedMotion, useSharedValue, withRepeat, withTiming,
} from 'react-native-reanimated';

import { decorative } from '@/components/editorial';
import { Ticker } from '@/components/trackdna-poster';
import { Fonts, Space } from '@/constants/theme';
import { type ArtistIdentity, DM_SERIF_ITALIC, fitSize } from '@/lib/artist-identity';

const TICKER = ['Line-up', 'Horarios', 'Para ti', 'El sonido del cartel', 'Hoja de ruta', 'Extractos de 30 s'] as const;
const HOURS = ['20', '22', '00', '02', '04', '06'];
/** Actuaciones de la parrilla de adorno: [inicio, duración] en fracción de la noche. La marcada es «para ti». */
const LANES: [number, number][][] = [
  [[0, 0.18], [0.2, 0.22], [0.44, 0.16]],
  [[0.1, 0.2], [0.32, 0.18], [0.52, 0.22], [0.76, 0.24]],
  [[0.08, 0.16], [0.26, 0.22], [0.5, 0.2], [0.72, 0.28]],
];
const LOVED = [1, 2];
const LABEL_W = 26;
const LANE_H = 16;

export function PostersPoster({ id, width, count, subtitle, children }: {
  id: ArtistIdentity; width: number; count: number; subtitle: string; children?: ReactNode;
}) {
  const P = id.palette;
  const inner = width - Space.lg * 2;
  const word = fitSize('CARTELES', inner, id.type, 150, 40);
  const lineup = fitSize('line-up', inner * 0.6, DM_SERIF_ITALIC, 96, 36);
  const laneW = inner - LABEL_W - 4;
  const reduce = useReducedMotion();
  const head = useSharedValue(reduce ? 0.58 : 0);
  useEffect(() => {
    if (reduce) {
      head.value = 0.58;
      return;
    }
    head.value = withRepeat(withTiming(1, { duration: 7000, easing: Easing.linear }), -1);
    return () => cancelAnimation(head);
  }, [reduce, head]);
  const sweep = useAnimatedStyle(() => ({ transform: [{ translateX: head.value * laneW }] }));
  const stamp = Math.min(lineup * 1.2, 92);

  return (
    <View style={{ width, backgroundColor: P.bg, overflow: 'hidden' }}>
      {/* Papeles pegados encima unos de otros. */}
      <View {...decorative} style={[styles.paper, { right: -width * 0.12, top: -width * 0.1, width: width * 0.5, height: width * 0.42,
        backgroundColor: P.pop, transform: [{ rotate: '7deg' }] }]} />
      <View {...decorative} style={[styles.paper, { right: width * 0.05, top: -width * 0.16, width: width * 0.34, height: width * 0.36,
        borderWidth: 2, borderColor: P.ink, transform: [{ rotate: '-5deg' }] }]} />

      <View {...decorative} style={[styles.flyerHead, { borderBottomColor: P.ink }]}>
        <Text style={[styles.flyerText, { color: P.ink }]}>{`Nº ${String(count).padStart(2, '0')}`}</Text>
        <Text style={[styles.flyerText, { color: P.ink }]}>Del cartel a la música</Text>
      </View>
      <Text accessibilityRole="header" accessibilityLabel="Carteles" numberOfLines={1}
        style={{ marginTop: Space.md, paddingHorizontal: Space.lg, fontFamily: id.type.family, fontSize: word, lineHeight: Math.round(word * 0.98),
          color: P.ink, includeFontPadding: false }}>
        CARTELES
      </Text>

      {/* Parrilla en miniatura: escenarios en filas, horas arriba y un cabezal que recorre la noche. */}
      <View {...decorative} style={[styles.grid, { borderColor: P.ink, marginHorizontal: Space.lg }]}>
        <View style={{ flexDirection: 'row', paddingLeft: LABEL_W, justifyContent: 'space-between', paddingRight: 2 }}>
          {HOURS.map((h) => <Text key={h} style={[styles.hour, { color: P.ink }]}>{h}</Text>)}
        </View>
        <View>
          {LANES.map((lane, li) => (
            <View key={li} style={{ flexDirection: 'row', alignItems: 'center', height: LANE_H, marginTop: 4 }}>
              <Text style={[styles.hour, { width: LABEL_W, color: P.ink }]}>{`0${li + 1}`}</Text>
              <View style={{ width: laneW, height: LANE_H }}>
                {lane.map(([a, b], bi) => {
                  const loved = LOVED[0] === li && LOVED[1] === bi;
                  return (
                    <View key={bi} style={[styles.block, { left: a * laneW, width: b * laneW - 3, backgroundColor: loved ? P.pop : P.ink }]}>
                      {loved ? <Text style={[styles.heart, { color: P.ink }]}>♥</Text> : null}
                    </View>
                  );
                })}
              </View>
            </View>
          ))}
          <Animated.View style={[styles.playhead, { left: LABEL_W, backgroundColor: P.pop, borderColor: P.ink }, sweep]} />
        </View>
      </View>

      <View {...decorative} style={[styles.band, { backgroundColor: P.ink }]}>
        <Text numberOfLines={1} style={{ fontFamily: Fonts.serifItalic, fontSize: lineup, lineHeight: Math.round(lineup * 1.15), color: P.bg,
          includeFontPadding: false, flexShrink: 1 }}>
          line-up
        </Text>
        <View style={[styles.stamp, { width: stamp, height: stamp, borderRadius: stamp / 2, borderColor: P.pop }]}>
          <Text style={[styles.stampText, { color: P.pop }]}>{'Para ti\n♥'}</Text>
        </View>
      </View>
      <Text style={[styles.sub, { color: P.ink }]}>{subtitle}</Text>
      {children ? <View style={{ paddingHorizontal: Space.lg }}>{children}</View> : null}
      <Ticker items={TICKER} color={P.ink} ink={P.bg} width={width} reduce={reduce} />
    </View>
  );
}

/**
 * Cabecera de las pantallas de Carteles (analizar, revisar): banda a sangre con la paleta de la sección, volver redondo
 * (como en el evento), rótulo en mono y título en display. Va dentro de `Screen` con `topTint={POSTER_ID.palette.bg}`.
 */
export function PosterBar({ id, title, kicker, backLabel, onBack, children }: {
  id: ArtistIdentity; title: string; kicker: string; backLabel: string; onBack: () => void; children?: ReactNode;
}) {
  const P = id.palette;
  return (
    <View style={[styles.bar, { backgroundColor: P.bg }]}>
      <View {...decorative} style={[styles.paper, { right: -40, top: -50, width: 150, height: 120, backgroundColor: P.pop, transform: [{ rotate: '8deg' }] }]} />
      <View style={styles.barTop}>
        <Pressable onPress={onBack} accessibilityRole="button" accessibilityLabel={backLabel} hitSlop={10}
          style={({ pressed }) => [styles.back, { borderColor: P.ink }, pressed && { opacity: 0.7 }]}>
          <Text style={[styles.backArrow, { color: P.ink }]}>←</Text>
        </Pressable>
        <Text style={[styles.flyerText, { color: P.ink, flexShrink: 1 }]} numberOfLines={1}>{kicker}</Text>
      </View>
      <Text accessibilityRole="header" style={[styles.barTitle, { color: P.ink }]}>{title}</Text>
      {children}
    </View>
  );
}

const styles = StyleSheet.create({
  bar: { marginHorizontal: -Space.lg, marginTop: -Space.lg, padding: Space.lg, paddingTop: Space.md, gap: Space.sm, overflow: 'hidden' },
  barTop: { flexDirection: 'row', alignItems: 'center', gap: Space.md },
  back: { width: 44, height: 44, borderRadius: 22, borderWidth: 2, alignItems: 'center', justifyContent: 'center' },
  backArrow: { fontSize: 20, fontWeight: '800' },
  barTitle: { fontFamily: Fonts.display, fontSize: 44, lineHeight: 46, textTransform: 'uppercase', includeFontPadding: false, marginTop: Space.sm },
  paper: { position: 'absolute' },
  flyerHead: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'baseline', marginTop: Space.lg, marginHorizontal: Space.lg,
    paddingBottom: 6, borderBottomWidth: 2 },
  flyerText: { fontFamily: Fonts.monoBold, fontSize: 11, letterSpacing: 1.4, textTransform: 'uppercase' },
  grid: { borderWidth: 2, padding: 6, paddingTop: 4, marginTop: Space.sm, marginBottom: Space.md },
  hour: { fontFamily: Fonts.monoBold, fontSize: 9, letterSpacing: 0.6 },
  block: { position: 'absolute', top: 0, bottom: 0, borderRadius: 1, alignItems: 'center', justifyContent: 'center' },
  heart: { fontSize: 10, lineHeight: 12, fontWeight: '900' },
  playhead: { position: 'absolute', top: -2, bottom: -2, width: 4, borderWidth: 1 },
  band: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: Space.lg, paddingVertical: Space.sm,
    gap: Space.md, overflow: 'hidden' },
  stamp: { borderWidth: 2, alignItems: 'center', justifyContent: 'center', transform: [{ rotate: '-12deg' }] },
  stampText: { fontFamily: Fonts.monoBold, fontSize: 11, lineHeight: 14, letterSpacing: 1.2, textTransform: 'uppercase', textAlign: 'center' },
  sub: { fontFamily: Fonts.sansBold, fontSize: 16, lineHeight: 22, maxWidth: 420, marginTop: Space.md, marginBottom: Space.sm, paddingHorizontal: Space.lg },
});
