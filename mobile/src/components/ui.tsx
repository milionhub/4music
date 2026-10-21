/** Primitivas visuales de Chromatic Underground (sin dependencias externas). */
import type { ReactNode } from 'react';
import {
  ActivityIndicator,
  KeyboardAvoidingView,
  Platform,
  Pressable,
  type PressableProps,
  ScrollView,
  type ScrollViewProps,
  StyleSheet,
  Text,
  type TextProps,
  View,
  type ViewStyle,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { type AccentPair, C, Fonts, gradient, MaxContentWidth, Radius, Space } from '@/constants/theme';

/**
 * Pantalla base. `footer` queda fijo abajo y sube con el teclado (KeyboardAvoidingView), para que las acciones
 * principales no se oculten. Las pantallas sin barra inferior (`withTabBar=false`) respetan el área segura inferior.
 */
export function Screen({
  children,
  scroll = true,
  footer,
  withTabBar = true,
  background,
  topTint,
  ...rest
}: {
  children: ReactNode; scroll?: boolean; footer?: ReactNode; withTabBar?: boolean;
  /** Fondo de la pantalla (superficie teñida de su identidad). */
  background?: string;
  /** Color bajo la barra de estado: continúa el cartel de cabecera (que va a sangre con `marginHorizontal: -Space.lg`). */
  topTint?: string;
} & ScrollViewProps) {
  return (
    <SafeAreaView style={[styles.screen, { backgroundColor: topTint ?? background ?? C.bg }]}
      edges={withTabBar ? ['top', 'left', 'right'] : ['top', 'left', 'right', 'bottom']}>
      <KeyboardAvoidingView style={{ flex: 1, backgroundColor: background ?? C.bg }} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
        {scroll ? (
          <ScrollView
            contentContainerStyle={[styles.screenContent, footer ? { paddingBottom: Space.xl } : null]}
            keyboardShouldPersistTaps="handled"
            keyboardDismissMode="on-drag"
            {...rest}>
            {children}
          </ScrollView>
        ) : (
          <View style={[styles.screenContent, { flex: 1 }]}>{children}</View>
        )}
        {footer ? <View style={styles.footer}>{footer}</View> : null}
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

export function Display({ style, ...rest }: TextProps) {
  return <Text accessibilityRole="header" style={[styles.display, style]} {...rest} />;
}

export function Title({ style, ...rest }: TextProps) {
  return <Text accessibilityRole="header" style={[styles.title, style]} {...rest} />;
}

export function Body({ style, muted, ...rest }: TextProps & { muted?: boolean }) {
  return <Text style={[styles.body, muted && { color: C.muted }, style]} {...rest} />;
}

/** Texto técnico pequeño en mayúsculas (rótulos, procedencia). */
export function Meta({ style, ...rest }: TextProps) {
  return <Text style={[styles.meta, style]} {...rest} />;
}

export function GradientBox({ pair, angle = 135, style, children }: { pair: AccentPair; angle?: number; style?: ViewStyle; children?: ReactNode }) {
  return <View style={[{ experimental_backgroundImage: gradient(pair, angle), backgroundColor: pair[0] }, style]}>{children}</View>;
}

export function Button({
  label,
  variant = 'primary',
  style,
  ...rest
}: { label: string; variant?: 'primary' | 'ghost' | 'danger'; style?: ViewStyle } & Omit<PressableProps, 'style'>) {
  return (
    <Pressable
      accessibilityRole="button"
      style={({ pressed }) => [
        styles.button,
        variant === 'primary' && styles.buttonPrimary,
        variant === 'ghost' && styles.buttonGhost,
        variant === 'danger' && styles.buttonDanger,
        pressed && { opacity: 0.75 },
        rest.disabled && { opacity: 0.4 },
        style,
      ]}
      {...rest}>
      <Text style={[styles.buttonLabel, variant === 'primary' ? { color: C.onAccent } : { color: C.text }]}>{label}</Text>
    </Pressable>
  );
}

export function Chip({ label, selected, onPress, accessibilityLabel }: { label: string; selected?: boolean; onPress?: () => void; accessibilityLabel?: string }) {
  return (
    <Pressable
      onPress={onPress}
      accessibilityRole={onPress ? 'button' : 'text'}
      accessibilityState={{ selected: !!selected }}
      accessibilityLabel={accessibilityLabel ?? label}
      style={({ pressed }) => [styles.chip, selected && styles.chipSelected, pressed && { opacity: 0.7 }]}>
      <Text style={[styles.chipLabel, selected && { color: C.onAccent }]}>{label}</Text>
    </Pressable>
  );
}

export function StateView({
  kind,
  title,
  message,
  actionLabel,
  onAction,
}: { kind: 'loading' | 'empty' | 'error'; title: string; message?: string; actionLabel?: string; onAction?: () => void }) {
  return (
    <View style={[styles.state, kind === 'error' && { borderColor: C.danger }]} accessibilityLiveRegion="polite">
      {kind === 'loading' ? <ActivityIndicator color={C.acid} /> : <Text style={styles.stateGlyph}>{kind === 'error' ? '!' : '∅'}</Text>}
      <Title style={{ textAlign: 'center' }}>{title}</Title>
      {message ? <Body muted style={{ textAlign: 'center' }}>{message}</Body> : null}
      {actionLabel && onAction ? <Button label={actionLabel} variant={kind === 'error' ? 'primary' : 'ghost'} onPress={onAction} /> : null}
    </View>
  );
}

export function Notice({ tone = 'info', children }: { tone?: 'info' | 'warn'; children: ReactNode }) {
  return (
    <View style={[styles.notice, tone === 'warn' && { borderLeftColor: C.orange }]}>
      <Body muted style={{ fontSize: 14, lineHeight: 20 }}>{children}</Body>
    </View>
  );
}

export function Section({ label, children, right }: { label: string; children: ReactNode; right?: ReactNode }) {
  return (
    <View style={{ gap: Space.md }}>
      <View style={styles.sectionHeader}>
        <Meta>{label}</Meta>
        {right}
      </View>
      {children}
    </View>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: C.bg },
  screenContent: { padding: Space.lg, paddingBottom: Space.xxxl * 2, gap: Space.xl, width: '100%', maxWidth: MaxContentWidth, alignSelf: 'center' },
  display: {
    color: C.text,
    fontFamily: Fonts.display,
    fontWeight: Fonts.displayWeight ?? '900',
    fontSize: 44,
    lineHeight: 44,
    letterSpacing: -0.5,
    textTransform: 'uppercase',
  },
  title: { color: C.text, fontFamily: Fonts.display, fontWeight: Fonts.displayWeight ?? '800', fontSize: 24, lineHeight: 28, textTransform: 'uppercase' },
  body: { color: C.text, fontFamily: Fonts.sans, fontSize: 16, lineHeight: 23 },
  meta: { color: C.faint, fontFamily: Fonts.mono, fontSize: 11, letterSpacing: 1.1, textTransform: 'uppercase' },
  button: { minHeight: 48, paddingHorizontal: Space.xl, borderRadius: Radius.pill, alignItems: 'center', justifyContent: 'center' },
  buttonPrimary: { backgroundColor: C.acid },
  buttonGhost: { borderWidth: 1.5, borderColor: C.line, backgroundColor: C.surface },
  buttonDanger: { borderWidth: 1.5, borderColor: C.danger },
  buttonLabel: { fontFamily: Fonts.display, fontWeight: Fonts.displayWeight ?? '800', fontSize: 16, letterSpacing: 1, textTransform: 'uppercase' },
  chip: { minHeight: 40, paddingHorizontal: Space.lg, borderRadius: Radius.pill, borderWidth: 1.5, borderColor: C.line, backgroundColor: C.surface, justifyContent: 'center' },
  chipSelected: { backgroundColor: C.acid, borderColor: C.acid },
  chipLabel: { color: C.text, fontFamily: Fonts.sansBold, fontSize: 14 },
  state: { alignItems: 'center', gap: Space.md, padding: Space.xl, borderRadius: Radius.lg, borderWidth: 1, borderColor: C.line, backgroundColor: C.bgRaised },
  stateGlyph: { color: C.acid, fontFamily: Fonts.display, fontWeight: Fonts.displayWeight ?? '900', fontSize: 40 },
  notice: { backgroundColor: C.bgRaised, borderLeftWidth: 3, borderLeftColor: C.cyan, borderRadius: Radius.sm, padding: Space.md },
  sectionHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  footer: {
    paddingHorizontal: Space.lg,
    paddingTop: Space.md,
    paddingBottom: Space.md,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: C.line,
    backgroundColor: C.bg,
    width: '100%',
    maxWidth: MaxContentWidth,
    alignSelf: 'center',
  },
});
