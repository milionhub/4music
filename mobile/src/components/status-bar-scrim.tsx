/**
 * Protección de la barra de estado para pantallas de borde a borde (Android dibuja la app bajo la hora y los iconos;
 * en iOS, bajo la isla o el notch). Se usa solo cuando el contenido desplazable pasa por detrás de la barra.
 *
 * ¿Hace falta? Las pantallas montadas con `<Screen>` (components/ui) NO lo necesitan: su SafeAreaView aplica el
 * margen superior fuera del ScrollView y el contenido se recorta antes de la barra. Sí lo necesitan las fichas con
 * cabecera a sangre (ScrollView a pantalla completa y el inset superior dentro de la cabecera), como Artista y
 * TrackDNA, y cualquier pantalla futura con ese patrón (fichas de Carteles, SetLab…):
 *
 *   <View style={{ flex: 1 }}>
 *     <ScrollView>…cabecera con <SafeAreaView edges={['top']}>…</ScrollView>
 *     <StatusBarScrim tint={…} />                       // cabecera de color: franja fija opaca
 *     <StatusBarScrim scrollY={offset} revealAt={…} />  // cabecera fotográfica: discreta en reposo, opaca al desplazar
 *   </View>
 *
 * Va después del ScrollView (encima), no intercepta toques y mide el inset real (0 en dispositivos sin barra).
 */
import { StyleSheet, View } from 'react-native';
import Animated, { interpolate, type SharedValue, useAnimatedStyle } from 'react-native-reanimated';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { C, Space } from '@/constants/theme';

const REVEAL_RAMP = 72; // px de scroll en los que la franja pasa de transparente a opaca
const SHADE = `linear-gradient(180deg, rgba(7,6,11,0.55), rgba(7,6,11,0))`; // C.bg con transparencia

export function StatusBarScrim({ tint, scrollY, revealAt = 0 }: {
  /** Tono sobre `C.bg` que continúa la cabecera (p. ej. el arranque de su degradado). Solo en modo fijo. */
  tint?: string;
  /** Desplazamiento del ScrollView (useScrollOffset). Activa el modo inmersivo. */
  scrollY?: SharedValue<number>;
  /** Desplazamiento a partir del cual la franja es totalmente opaca (antes de que el contenido llegue a la barra). */
  revealAt?: number;
}) {
  const { top } = useSafeAreaInsets();
  if (!top) return null;
  if (!scrollY) {
    return (
      <View pointerEvents="none" style={[styles.bar, { height: top }]}>
        {tint ? <View style={{ flex: 1, backgroundColor: tint }} /> : null}
      </View>
    );
  }
  return <ImmersiveScrim top={top} scrollY={scrollY} revealAt={revealAt} />;
}

function ImmersiveScrim({ top, scrollY, revealAt }: { top: number; scrollY: SharedValue<number>; revealAt: number }) {
  const solid = useAnimatedStyle(() => ({
    opacity: interpolate(scrollY.value, [revealAt - REVEAL_RAMP, revealAt], [0, 1], 'clamp'),
  }));
  return (
    <View pointerEvents="none" style={styles.overlay}>
      {/* En reposo: sombra suave que da contraste a los iconos sobre la foto sin cortarla. */}
      <View style={{ height: top + Space.xl, experimental_backgroundImage: SHADE }} />
      {/* Al desplazar: fondo opaco del alto exacto de la barra; el contenido ya no se ve tras los iconos. */}
      <Animated.View style={[styles.bar, { height: top }, solid]} />
    </View>
  );
}

const styles = StyleSheet.create({
  overlay: { position: 'absolute', top: 0, left: 0, right: 0 },
  bar: { position: 'absolute', top: 0, left: 0, right: 0, backgroundColor: C.bg },
});
