/**
 * Sistema visual compartido (v5), extraído de Artist Experience v4: cartel tipográfico de pantalla, portada o placa
 * tipográfica determinista, marca de artista sin foto, etiquetas, botón de guardar y estados vacíos. Usa las mismas
 * paletas y tipografías que las fichas de artista (lib/artist-identity.ts): un solo sistema, no uno paralelo.
 */
import { Image } from 'expo-image';
import { type ReactNode, useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { C, Fonts, Radius, Space } from '@/constants/theme';
import { alpha, type ArtistIdentity, display, DM_SERIF_ITALIC, fitSize, identityFor, surfaces } from '@/lib/artist-identity';

export const decorative = { accessibilityElementsHidden: true, importantForAccessibility: 'no-hide-descendants' as const };

/** Rótulo pequeño en mono (kicker de revista). */
export function Kicker({ children, color = C.faint, size = 11, style }: { children: ReactNode; color?: string; size?: number; style?: object }) {
  return (
    <Text numberOfLines={1} style={[{ fontFamily: Fonts.monoBold, fontSize: size, letterSpacing: 1.4, textTransform: 'uppercase', color }, style]}>
      {children}
    </Text>
  );
}

/**
 * Cartel de cabecera de una pantalla de pestaña: palabra gigante ajustada al ancho real de sus letras y, si hay,
 * una cifra en serif cursiva (contraste de dos voces). La decoración vive en la esquina superior, recortada a
 * propósito por el borde, y nunca pasa por detrás del titular (en V5, un círculo encima de la «D» se leía «UNA»).
 */
export function ScreenPoster({ id, word, kicker, subtitle, width, figure, children }: {
  id: ArtistIdentity; word: string; kicker?: string; subtitle?: string; width: number; figure?: string; children?: ReactNode;
}) {
  const P = id.palette;
  const T = id.type;
  const inner = width - Space.lg * 2;
  const text = display(word, T);
  const size = fitSize(text, inner, T, 132, 28);
  const ring = width * 0.42;
  return (
    <View style={{ width, backgroundColor: P.bg, overflow: 'hidden', paddingHorizontal: Space.lg, paddingTop: Space.md, paddingBottom: Space.xl, gap: Space.sm }}>
      <View {...decorative} style={{ position: 'absolute', right: -ring * 0.3, top: -ring * 0.62, width: ring, height: ring, borderRadius: ring / 2,
        borderWidth: 3, borderColor: alpha(P.ink, 0.5) }} />
      <View {...decorative} style={{ position: 'absolute', right: ring * 0.38, top: -ring * 0.16, width: ring * 0.34, height: ring * 0.34,
        borderRadius: ring * 0.17, backgroundColor: P.pop }} />
      <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'flex-end', minHeight: 56 }}>
        {kicker ? <Kicker color={P.ink} style={{ flexShrink: 1, marginBottom: 6 }}>{kicker}</Kicker> : <View />}
        {figure ? <Text {...decorative} style={{ fontFamily: Fonts.serifItalic, fontSize: 52, lineHeight: 58, color: P.ink }}>{figure}</Text> : null}
      </View>
      <Text accessibilityRole="header" accessibilityLabel={word} numberOfLines={1}
        style={{ fontFamily: T.family, fontSize: size, lineHeight: Math.round(size * T.lineFactor), letterSpacing: T.tracking, color: P.ink, includeFontPadding: false }}>
        {text}
      </Text>
      {subtitle ? <Text style={[styles.posterSub, { color: P.ink }]}>{subtitle}</Text> : null}
      {children}
    </View>
  );
}

/**
 * Cabecera de TrackDNA: «TRACK» en display condensada a todo ancho y «DNA» en serif cursiva sobre una banda de tinta,
 * como en un cartel de club. Las formas quedan arriba y a la derecha de la banda: nunca tapan una letra.
 */
export function TrackDnaPoster({ id, width, subtitle }: { id: ArtistIdentity; width: number; subtitle: string }) {
  const P = id.palette;
  const inner = width - Space.lg * 2;
  const anton = id.type;
  const track = fitSize('TRACK', inner, anton, 170, 40);
  const dna = fitSize('DNA', inner * 0.62, DM_SERIF_ITALIC, 150, 40);
  const ring = width * 0.46;
  return (
    <View accessible accessibilityRole="header" accessibilityLabel="TrackDNA" style={{ width, backgroundColor: P.bg, overflow: 'hidden', paddingBottom: Space.lg }}>
      <View {...decorative} style={{ position: 'absolute', right: -ring * 0.28, top: -ring * 0.58, width: ring, height: ring, borderRadius: ring / 2,
        borderWidth: 3, borderColor: P.ink }} />
      <View {...decorative} style={[styles.posterRule, { top: Space.lg + 4, backgroundColor: P.ink }]} />
      <Text {...decorative} numberOfLines={1}
        style={{ marginTop: Space.xl + Space.md, paddingHorizontal: Space.lg, fontFamily: anton.family, fontSize: track, lineHeight: Math.round(track * 0.98),
          color: P.ink, includeFontPadding: false }}>
        TRACK
      </Text>
      <View {...decorative} style={{ backgroundColor: P.ink, paddingHorizontal: Space.lg, flexDirection: 'row', alignItems: 'center', overflow: 'hidden' }}>
        <Text numberOfLines={1} style={{ fontFamily: Fonts.serifItalic, fontSize: dna, lineHeight: Math.round(dna * 1.12), color: P.bg, includeFontPadding: false }}>
          DNA
        </Text>
        <View style={{ flex: 1, alignItems: 'flex-end', justifyContent: 'center' }}>
          <View style={{ width: dna * 0.62, height: dna * 0.62, borderRadius: dna * 0.31, backgroundColor: P.pop }} />
        </View>
      </View>
      <Text style={[styles.posterSub, { color: P.ink, marginTop: Space.md, paddingHorizontal: Space.lg }]}>{subtitle}</Text>
    </View>
  );
}

/**
 * Portada del lanzamiento o, si no hay (o falla), una placa tipográfica estable para esa grabación: inicial gigante
 * sobre su paleta y una forma. Nunca simula ser la portada real.
 */
export function CoverPlate({ uri, seed, title, size, radius = Radius.sm, border, onFail }: {
  uri: string | null; seed: string; title: string; size: number; radius?: number; border?: string;
  /** Aviso de que la imagen no carga (Tu frecuencia descarta ese candidato); el respaldo tipográfico no cambia. */
  onFail?: (uri: string) => void;
}) {
  const [failedUri, setFailedUri] = useState<string | null>(null);
  const frame = border ? { borderWidth: 2, borderColor: border } : null;
  if (uri && failedUri !== uri) {
    return (
      <Image source={{ uri }} style={[{ width: size, height: size, borderRadius: radius, backgroundColor: C.surfaceHigh }, frame]}
        contentFit="cover" cachePolicy="disk" transition={150} onError={() => {
          setFailedUri(uri);
          onFail?.(uri);
        }} accessibilityIgnoresInvertColors />
    );
  }
  const id = identityFor(seed);
  const P = id.palette;
  const initial = display([...title.replace(/^[^\p{L}\p{N}]+/u, '')][0] ?? '♪', id.type);
  return (
    <View {...decorative} style={[{ width: size, height: size, borderRadius: radius, backgroundColor: P.bg, overflow: 'hidden' }, frame]}>
      <View style={{ position: 'absolute', right: -size * 0.18, bottom: -size * 0.18, width: size * 0.7, height: size * 0.7, borderRadius: size * 0.35, backgroundColor: P.pop }} />
      <Text style={{ position: 'absolute', left: size * 0.08, top: -size * 0.04, fontFamily: id.type.family, fontSize: size * 0.78, lineHeight: size * 0.92, color: P.ink }}>
        {initial}
      </Text>
      {size >= 120 ? (
        <Text numberOfLines={2} style={{ position: 'absolute', left: size * 0.08, right: size * 0.08, bottom: size * 0.07, fontFamily: Fonts.monoBold,
          fontSize: Math.max(10, size * 0.065), letterSpacing: 1, textTransform: 'uppercase', color: P.ink }}>
          {title}
        </Text>
      ) : null}
    </View>
  );
}

/** Marca tipográfica de un artista (sin foto): iniciales con la paleta y la tipografía de su identidad. */
export function ArtistMark({ mbid, name, size = 48 }: { mbid: string; name: string; size?: number }) {
  const id = identityFor(mbid);
  const initials = name.replace(/[^\p{L}\p{N} ]/gu, ' ').split(/\s+/).filter(Boolean).slice(0, 2).map((w) => [...w][0]).join('') || '?';
  const text = display(initials, id.type);
  return (
    <View {...decorative} style={{ width: size, height: size, borderRadius: Radius.sm, backgroundColor: id.palette.bg, alignItems: 'center',
      justifyContent: 'center', overflow: 'hidden' }}>
      <View style={{ position: 'absolute', right: -size * 0.25, top: -size * 0.25, width: size * 0.6, height: size * 0.6, borderRadius: size * 0.3, backgroundColor: id.palette.pop }} />
      <Text style={{ fontFamily: id.type.family, fontSize: fitSize(text, size * 0.86, id.type, size * 0.5, 10), color: id.palette.ink }}>{text}</Text>
    </View>
  );
}

/** Etiqueta de versión o tipo («Remix de…», «Extended Mix»): rellena con el acento de la identidad. */
export function TagPill({ label, color, ink }: { label: string; color: string; ink: string }) {
  return (
    <Text numberOfLines={1} style={[styles.tag, { backgroundColor: color, color: ink }]}>{label}</Text>
  );
}

/** Guardar/desguardar una canción: botón principal muy visible con el acento de la identidad. */
export function SaveButton({ saved, onPress, id }: { saved: boolean; onPress: () => void; id: ArtistIdentity }) {
  const P = id.palette;
  return (
    <Pressable onPress={onPress} accessibilityRole="button" accessibilityState={{ selected: saved }}
      accessibilityLabel={saved ? 'Canción guardada' : 'Guardar canción'} accessibilityHint={saved ? 'Pulsa para quitarla de Guardados' : undefined}
      style={({ pressed }) => [styles.save, saved ? { borderColor: P.glow, backgroundColor: 'transparent' } : { backgroundColor: P.glow, borderColor: P.glow },
        pressed && { opacity: 0.8 }]}>
      <Text style={[styles.saveLabel, { color: saved ? P.glow : P.onGlow }]}>{saved ? '♥ Guardada' : '♡ Guardar canción'}</Text>
    </Pressable>
  );
}

/** Estado vacío editorial: glifo gigante, titular y una acción clara. */
export function EmptyPoster({ id, glyph, title, message, actionLabel, onAction }: {
  id: ArtistIdentity; glyph: string; title: string; message: string; actionLabel?: string; onAction?: () => void;
}) {
  const P = id.palette;
  const S = surfaces(P);
  return (
    <View style={[styles.empty, { backgroundColor: S.raised, borderColor: S.line }]} accessibilityLiveRegion="polite">
      <Text {...decorative} style={{ fontFamily: id.type.family, fontSize: 96, lineHeight: 100, color: P.glow }}>{glyph}</Text>
      <Text accessibilityRole="header" style={styles.emptyTitle}>{title}</Text>
      <Text style={styles.emptyText}>{message}</Text>
      {actionLabel && onAction ? (
        <Pressable onPress={onAction} accessibilityRole="button"
          style={({ pressed }) => [styles.save, { backgroundColor: P.glow, borderColor: P.glow, alignSelf: 'stretch' }, pressed && { opacity: 0.8 }]}>
          <Text style={[styles.saveLabel, { color: P.onGlow }]}>{actionLabel}</Text>
        </Pressable>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  posterRule: { position: 'absolute', left: Space.lg, width: 72, height: 3 },
  posterSub: { fontFamily: Fonts.sansBold, fontSize: 16, lineHeight: 22, maxWidth: 420 },
  tag: {
    alignSelf: 'flex-start', fontFamily: Fonts.monoBold, fontSize: 10, letterSpacing: 1, textTransform: 'uppercase', maxWidth: 220,
    paddingHorizontal: 8, paddingVertical: 2, borderRadius: Radius.pill, overflow: 'hidden',
  },
  save: { minHeight: 54, borderRadius: Radius.pill, borderWidth: 2, alignItems: 'center', justifyContent: 'center', paddingHorizontal: Space.xl },
  saveLabel: { fontFamily: Fonts.sansBold, fontSize: 17, letterSpacing: 0.4 },
  empty: { alignItems: 'flex-start', gap: Space.md, padding: Space.xl, borderRadius: Radius.md, borderWidth: 1 },
  emptyTitle: { color: C.text, fontFamily: Fonts.serifDisplay, fontSize: 32, lineHeight: 36 },
  emptyText: { color: C.muted, fontFamily: Fonts.sans, fontSize: 16, lineHeight: 23 },
});
