/** Piezas de Guardados y Perfil (V6.7): tira de cifras de cartel y selector de orden, con la paleta de la pantalla. */
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { Fonts, Space } from '@/constants/theme';
import type { Palette } from '@/lib/artist-identity';

export type Stat = { label: string; value: string };

/** Cifras de cartel: valor grande en display y rótulo en mono, separadas por filetes de tinta. */
export function StatStrip({ stats, ink, size = 30 }: { stats: Stat[]; ink: string; size?: number }) {
  if (!stats.length) return null;
  return (
    <View style={[styles.strip, { borderTopColor: ink }]}>
      {stats.map((s, i) => (
        <View key={s.label} accessible accessibilityLabel={`${s.label}: ${s.value}`}
          style={[styles.cell, i > 0 && { borderLeftWidth: 2, borderLeftColor: ink, paddingLeft: Space.md }]}>
          <Text numberOfLines={1} adjustsFontSizeToFit minimumFontScale={0.6}
            style={{ fontFamily: Fonts.display, fontSize: size, lineHeight: Math.round(size * 1.1), color: ink, includeFontPadding: false }}>
            {s.value}
          </Text>
          <Text numberOfLines={1} style={[styles.label, { color: ink }]}>{s.label}</Text>
        </View>
      ))}
    </View>
  );
}

/** Selector de una opción: píldoras en mono, la activa rellena con el acento. */
export function Segmented<T extends string>({ options, value, onChange, palette, label }: {
  options: Record<T, string>; value: T; onChange: (v: T) => void; palette: Palette; label: string;
}) {
  return (
    <View style={styles.segmented} accessibilityRole="radiogroup" accessibilityLabel={label}>
      {(Object.keys(options) as T[]).map((k) => {
        const on = k === value;
        return (
          <Pressable key={k} onPress={() => onChange(k)} accessibilityRole="radio" accessibilityState={{ selected: on }}
            hitSlop={6} style={({ pressed }) => [styles.pill, { borderColor: palette.glow, backgroundColor: on ? palette.glow : 'transparent' },
              pressed && { opacity: 0.75 }]}>
            <Text style={[styles.pillText, { color: on ? palette.onGlow : palette.glow }]}>{options[k]}</Text>
          </Pressable>
        );
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  strip: { flexDirection: 'row', borderTopWidth: 2, paddingTop: Space.sm, marginTop: Space.sm },
  cell: { flex: 1, gap: 2, paddingRight: Space.sm },
  label: { fontFamily: Fonts.monoBold, fontSize: 10, letterSpacing: 1.2, textTransform: 'uppercase' },
  segmented: { flexDirection: 'row', gap: Space.sm, flexWrap: 'wrap' },
  pill: { borderWidth: 1.5, borderRadius: 999, paddingHorizontal: Space.md, paddingVertical: 6 },
  pillText: { fontFamily: Fonts.monoBold, fontSize: 11, letterSpacing: 1, textTransform: 'uppercase' },
});
