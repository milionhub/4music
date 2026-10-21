/**
 * Sistema común de fichas (V5.4): el mismo encabezado y la misma sección para TrackDNA y los perfiles de artista, sobre
 * la base `SHEET` (lib/track-art.ts). Lo que cambia entre fichas es el color de acento, nunca la estructura.
 */
import type { ReactNode } from 'react';
import { StyleSheet, Text, View } from 'react-native';

import { Fonts, Space } from '@/constants/theme';
import { SHEET } from '@/lib/track-art';

export const SHEET_GUTTER = Space.lg;

/** Número de sección en mono con el acento y título en Anton: un único tratamiento para todas las fichas. */
export function SheetHead({ index, title, accent, right }: { index?: string; title: string; accent: string; right?: ReactNode }) {
  return (
    <View style={[styles.head, { borderBottomColor: SHEET.base.line }]}>
      {index ? <Text style={[styles.index, { color: accent }]}>{index}</Text> : null}
      <Text accessibilityRole="header" numberOfLines={2} style={styles.title}>{title}</Text>
      {right}
    </View>
  );
}

/** Sección sobre la base común; `bleed` la extiende a todo el ancho con su propio margen interior. */
export function SheetSection({ index, title, accent, children, last, bleed = true }: {
  index?: string; title: string; accent: string; children: ReactNode; last?: boolean; bleed?: boolean;
}) {
  return (
    <View style={[{ gap: Space.lg, paddingTop: Space.xxl }, bleed && { paddingHorizontal: SHEET_GUTTER }, last && { paddingBottom: Space.xxxl * 2 }]}>
      <SheetHead index={index} title={title} accent={accent} />
      {children}
    </View>
  );
}

const styles = StyleSheet.create({
  head: { flexDirection: 'row', alignItems: 'baseline', gap: Space.md, borderBottomWidth: StyleSheet.hairlineWidth, paddingBottom: Space.sm },
  index: { fontFamily: Fonts.monoBold, fontSize: 13, letterSpacing: 1 },
  title: { flex: 1, color: SHEET.base.ink, fontFamily: Fonts.display, fontSize: 26, lineHeight: 31, letterSpacing: 0.6, textTransform: 'uppercase', includeFontPadding: false },
});
