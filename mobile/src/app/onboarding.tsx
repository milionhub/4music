/**
 * Bienvenida opcional: artistas favoritos (prioritario) y estilos declarados (opcionales). Desde el Perfil
 * (`mode=edit`), solo los artistas de partida, con el estilo de «Tu pase» (V6.7); los estilos se marcan en el Perfil.
 */
import { router, useLocalSearchParams } from 'expo-router';
import { useEffect, useState } from 'react';
import { Pressable, StyleSheet, Text, useWindowDimensions, View } from 'react-native';
import Animated, { FadeIn, ReduceMotion } from 'react-native-reanimated';

import { ArtistMark, decorative, Kicker, ScreenPoster } from '@/components/editorial';
import { ArtistSearch } from '@/components/music';
import { Screen } from '@/components/ui';
import { WelcomePoster } from '@/components/welcome-poster';
import { C, Fonts, MaxContentWidth, Radius, Space } from '@/constants/theme';
import { EDITORIAL_STYLES } from '@/constants/styles';
import { fixedIdentity, SECTION_PALETTES, surfaces } from '@/lib/artist-identity';
import { useLibrary } from '@/state/library';

/** La misma identidad que «Tu pase» (Perfil): editar es parte de él. */
const PASS = fixedIdentity(SECTION_PALETTES.profile, 'anton');
const PP = PASS.palette;
const PS = surfaces(PP);

/** Inclinación fija de cada pegatina de estilo, como en el Perfil. */
const TILTS = [-3, 2, -1.5, 3, -2.5, 1, -3.5, 2.5, -1, 1.5];

type Step = 'welcome' | 'artists' | 'styles';
const STEPS: Step[] = ['welcome', 'artists', 'styles'];

export default function Onboarding() {
  const { mode } = useLocalSearchParams<{ mode?: string }>();
  const editing = mode === 'edit';
  const lib = useLibrary();
  const [step, setStep] = useState<Step>(editing ? 'artists' : 'welcome');
  const [styles, setStyles] = useState<string[]>(lib.preferences.declared_styles);
  const [leaving, setLeaving] = useState(false);

  // Se navega cuando el estado ya refleja que la bienvenida terminó; si no, la pestaña volvería a redirigir aquí.
  useEffect(() => {
    if (!leaving || lib.preferences.onboarding === 'pending') return;
    if (router.canGoBack()) router.back();
    else router.replace('/');
  }, [leaving, lib.preferences.onboarding]);

  function leave(state: 'completed' | 'skipped') {
    lib.completeOnboarding(state, styles); // una sola actualización: estado + estilos (favoritos intactos)
    setLeaving(true);
  }

  const next = () => setStep(STEPS[STEPS.indexOf(step) + 1] ?? 'styles');
  const toggleStyle = (s: string) => setStyles((prev) => (prev.includes(s) ? prev.filter((x) => x !== s) : [...prev, s]));

  const { width } = useWindowDimensions();
  if (editing) return <EditArtists onDone={() => leave('completed')} />;

  const n = lib.favorites.length;
  const index = STEPS.indexOf(step);
  const footer =
    step === 'welcome' ? (
      <PassButton label="Empezar →" onPress={next} />
    ) : step === 'artists' ? (
      <PassButton label={n ? `Siguiente · ${n} ${n === 1 ? 'elegido' : 'elegidos'}` : 'Seguir sin artistas'} ghost={!n} onPress={next} />
    ) : (
      <PassButton label={styles.length ? `Terminar · ${styles.length} ${styles.length === 1 ? 'estilo' : 'estilos'}` : 'Terminar'} onPress={() => leave('completed')} />
    );
  // La cifra del cartel cuenta lo elegido (como al editar desde el Perfil); el paso lo dice la barra de progreso.
  const poster = step === 'artists'
    ? { word: 'Tus artistas', kicker: 'Paso 2 de 3 · artistas de partida', count: n,
      subtitle: 'Inicio parte de ellos para proponerte artistas y canciones conectados.' }
    : { word: 'Tus estilos', kicker: 'Paso 3 de 3 · opcional', count: styles.length,
      subtitle: 'Afinan Tu frecuencia, en Inicio. Puedes cambiarlos cuando quieras en tu Perfil.' };

  return (
    <Screen withTabBar={false} footer={footer} background={PS.screen} topTint={PP.bg}>
      <View style={{ marginHorizontal: -Space.lg, marginTop: -Space.lg }}>
        <View style={[s.topBar, { backgroundColor: PP.bg }]}>
          <View {...decorative} style={s.progress}>
            {STEPS.map((st, i) => <View key={st} style={[s.progressStep, { backgroundColor: PP.ink, opacity: i <= index ? 1 : 0.3 }]} />)}
          </View>
          <Pressable onPress={() => leave('skipped')} accessibilityRole="button" accessibilityLabel="Omitir la bienvenida" hitSlop={12}>
            <Text style={[s.mono, { color: PP.ink }]}>Omitir</Text>
          </Pressable>
        </View>
        {step === 'welcome' ? (
          <WelcomePoster width={Math.min(width, MaxContentWidth)} screen={PS.screen} />
        ) : (
          <ScreenPoster key={step} id={PASS} width={Math.min(width, MaxContentWidth)} word={poster.word} kicker={poster.kicker}
            figure={poster.count ? String(poster.count).padStart(2, '0') : undefined} subtitle={poster.subtitle} />
        )}
      </View>

      {step === 'artists' ? <ArtistsPicker /> : null}

      {step === 'styles' ? (
        <View style={{ gap: Space.md }}>
          <View style={[s.blockHead, { borderTopColor: PP.glow }]}>
            <Text accessibilityRole="header" style={[s.mono, { color: PP.glow }]}>{styles.length ? `Marcados · ${styles.length}` : 'Toca los que te gustan'}</Text>
          </View>
          <View style={s.stickers}>
            {EDITORIAL_STYLES.map((st, i) => {
              const on = styles.includes(st);
              return (
                <Pressable key={st} onPress={() => toggleStyle(st)} accessibilityRole="checkbox" accessibilityState={{ checked: on }} accessibilityLabel={st}
                  hitSlop={4} style={({ pressed }) => [s.sticker, { transform: [{ rotate: `${TILTS[i % TILTS.length]}deg` }] },
                    on ? { backgroundColor: PP.pop, borderColor: PP.pop } : { borderColor: PS.line }, pressed && { opacity: 0.8 }]}>
                  <Text style={[s.stickerText, { color: on ? PP.onGlow : C.muted }]}>{st}</Text>
                </Pressable>
              );
            })}
          </View>
          <Text style={s.note}>
            Es una lista editorial de #4MUSIC, no una clasificación de MusicBrainz ni de ningún artista.
          </Text>
        </View>
      ) : null}
    </Screen>
  );
}

/** Botón ancho de «Tu pase» (el mismo que en el Perfil); `ghost` cuando la acción es seguir sin elegir. */
function PassButton({ label, onPress, ghost }: { label: string; onPress: () => void; ghost?: boolean }) {
  return (
    <Pressable onPress={onPress} accessibilityRole="button" style={({ pressed }) => [s.done, ghost && s.doneGhost, pressed && { opacity: 0.85 }]}>
      <Text style={[s.doneLabel, ghost && { color: PP.glow }]}>{label}</Text>
    </Pressable>
  );
}

/** Editar artistas de partida (desde el Perfil): cartel de «Tu pase», elegidos como fichas y buscador con su color. */
function EditArtists({ onDone }: { onDone: () => void }) {
  const lib = useLibrary();
  const { width } = useWindowDimensions();
  const n = lib.favorites.length;
  const footer = <PassButton label={n ? `Listo · ${n} ${n === 1 ? 'artista' : 'artistas'}` : 'Listo'} onPress={onDone} />;
  return (
    <Screen withTabBar={false} footer={footer} background={PS.screen} topTint={PP.bg}>
      <View style={{ marginHorizontal: -Space.lg, marginTop: -Space.lg }}>
        <ScreenPoster id={PASS} width={Math.min(width, MaxContentWidth)} word="Tus artistas" kicker="Artistas de partida"
          figure={n ? String(n).padStart(2, '0') : undefined}
          subtitle="Inicio parte de ellos para proponerte artistas y canciones conectados, siempre con el motivo." />
      </View>
      <ArtistsPicker />
    </Screen>
  );
}

/** Elegidos como fichas (toca para quitar) y buscador de MusicBrainz con el color de «Tu pase». */
function ArtistsPicker() {
  const lib = useLibrary();
  const n = lib.favorites.length;
  return (
    <>
      <View style={{ gap: Space.md }}>
        <View style={[s.blockHead, { borderTopColor: PP.glow }]}>
          <Text accessibilityRole="header" style={[s.mono, { color: PP.glow }]}>{n ? 'Elegidos · toca para quitar' : 'Elegidos'}</Text>
        </View>
        {n ? (
          <View style={s.grid}>
            {lib.favorites.map((f, i) => (
              <Animated.View key={f.mbid} entering={FadeIn.delay(Math.min(i, 10) * 30).duration(200).reduceMotion(ReduceMotion.System)}>
                <Pressable onPress={() => lib.toggleFavorite(f)} accessibilityRole="button" accessibilityLabel={`Quitar ${f.name}`}
                  style={({ pressed }) => [s.tile, pressed && { opacity: 0.6 }]}>
                  <View>
                    <ArtistMark mbid={f.mbid} name={f.name} size={64} />
                    <View {...decorative} style={[s.remove, { backgroundColor: PP.pop, borderColor: PS.screen }]}>
                      <Text style={[s.removeLabel, { color: PP.onGlow }]}>✕</Text>
                    </View>
                  </View>
                  <Text style={s.tileName} numberOfLines={2}>{f.name}</Text>
                </Pressable>
              </Animated.View>
            ))}
          </View>
        ) : (
          <Text style={s.note}>Aún ninguno. Sin artistas, Inicio sigue funcionando con su selección editorial.</Text>
        )}
      </View>

      <View style={{ gap: Space.md }}>
        <View style={[s.blockHead, { borderTopColor: PP.glow }]}>
          <Text accessibilityRole="header" style={[s.mono, { color: PP.glow }]}>Añadir</Text>
        </View>
        <Kicker>La descripción distingue nombres repetidos · datos de MusicBrainz</Kicker>
        <ArtistSearch isSelected={lib.isFavorite} onPick={(r) => lib.toggleFavorite(r)}
          theme={{ glow: PP.glow, onGlow: PP.onGlow, raised: PS.raised, line: PS.line }} />
      </View>
    </>
  );
}

const s = StyleSheet.create({
  mono: { fontFamily: Fonts.monoBold, fontSize: 11, letterSpacing: 1.3, textTransform: 'uppercase' },
  note: { color: C.faint, fontFamily: Fonts.mono, fontSize: 12, lineHeight: 17 },
  blockHead: { borderTopWidth: 2, paddingTop: Space.sm, marginTop: Space.md },
  grid: { flexDirection: 'row', flexWrap: 'wrap', gap: Space.md },
  tile: { width: 76, gap: 6 },
  tileName: { color: C.text, fontFamily: Fonts.sansBold, fontSize: 12, lineHeight: 15 },
  remove: { position: 'absolute', right: -6, top: -6, width: 24, height: 24, borderRadius: 12, borderWidth: 2, alignItems: 'center', justifyContent: 'center' },
  removeLabel: { fontSize: 11, fontWeight: '900' },
  done: { minHeight: 56, borderRadius: Radius.md, backgroundColor: PP.glow, alignItems: 'center', justifyContent: 'center' },
  doneLabel: { color: PP.onGlow, fontFamily: Fonts.monoBold, fontSize: 14, letterSpacing: 1.4, textTransform: 'uppercase' },
  doneGhost: { backgroundColor: 'transparent', borderWidth: 2, borderColor: PP.glow },
  topBar: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', gap: Space.lg, paddingHorizontal: Space.lg, paddingTop: Space.md },
  progress: { flex: 1, flexDirection: 'row', gap: 6 },
  progressStep: { flex: 1, height: 4, borderRadius: 2 },
  stickers: { flexDirection: 'row', flexWrap: 'wrap', gap: Space.sm, paddingVertical: Space.xs },
  sticker: { borderWidth: 2, borderRadius: Radius.sm, paddingHorizontal: Space.md, paddingVertical: Space.sm },
  stickerText: { fontFamily: Fonts.display, fontSize: 20, lineHeight: 24, letterSpacing: 0.4, textTransform: 'uppercase', includeFontPadding: false },
});
