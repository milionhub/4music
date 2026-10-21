/** Bienvenida opcional: artistas favoritos (prioritario) y estilos declarados (opcionales). */
import { router, useLocalSearchParams } from 'expo-router';
import { useEffect, useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import Animated, { FadeIn, ReduceMotion } from 'react-native-reanimated';

import { ArtistSearch } from '@/components/music';
import { Body, Button, Chip, Display, GradientBox, Meta, Notice, Screen, Section } from '@/components/ui';
import { C, Fonts, Radius, Space } from '@/constants/theme';
import { EDITORIAL_STYLES } from '@/constants/styles';
import { useLibrary } from '@/state/library';

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

  const footer =
    step === 'welcome' ? (
      <Button label="Empezar" onPress={next} />
    ) : step === 'artists' ? (
      <Button label={lib.favorites.length ? `Siguiente · ${lib.favorites.length} elegidos` : 'Seguir sin artistas'} variant={lib.favorites.length ? 'primary' : 'ghost'} onPress={next} />
    ) : (
      <Button label={editing ? 'Guardar' : 'Terminar'} onPress={() => leave('completed')} />
    );

  return (
    <Screen withTabBar={false} footer={footer}>
      <View style={s.topBar}>
        <Meta>{editing ? 'Editar gustos' : `Paso ${STEPS.indexOf(step) + 1} de 3`}</Meta>
        <Pressable onPress={() => leave(editing ? 'completed' : 'skipped')} accessibilityRole="button" hitSlop={12}>
          <Text style={s.skip}>{editing ? 'Cerrar' : 'Omitir'}</Text>
        </Pressable>
      </View>

      {step === 'welcome' ? (
        <Animated.View entering={FadeIn.duration(400).reduceMotion(ReduceMotion.System)} style={{ gap: Space.xl }}>
          <GradientBox pair={[C.magenta, C.violet]} angle={160} style={s.poster}>
            <Meta style={{ color: C.text }}>Chromatic Underground</Meta>
            <Text style={s.posterTitle}>{'DESCUBRE\nPOR\nCONEXIONES'}</Text>
            <View style={s.posterStripe}>
              <GradientBox pair={[C.acid, C.cyan]} angle={90} style={{ flex: 1, height: 10, borderRadius: Radius.pill }} />
            </View>
          </GradientBox>
          <Body>
            Elige artistas que te gustan. A partir de ellos te mostraremos otros artistas con los que tienen una conexión
            documentada en MusicBrainz, siempre con el motivo.
          </Body>
          <Body muted>Sin registro: tus gustos se guardan solo en este dispositivo. Puedes omitir este paso.</Body>
        </Animated.View>
      ) : null}

      {step === 'artists' ? (
        <View style={{ gap: Space.xl }}>
          <Display>Tus artistas</Display>
          <Body muted>Busca y elige a qué artista te refieres: la descripción ayuda a distinguir nombres repetidos.</Body>
          {lib.favorites.length > 0 ? (
            <Section label={`Elegidos · ${lib.favorites.length}`}>
              <View style={s.wrap}>
                {lib.favorites.map((f) => (
                  <Chip key={f.mbid} label={`${f.name}  ✕`} selected onPress={() => lib.toggleFavorite(f)} accessibilityLabel={`Quitar ${f.name}`} />
                ))}
              </View>
            </Section>
          ) : null}
          <ArtistSearch autoFocus={!editing} isSelected={lib.isFavorite} onPick={(r) => lib.toggleFavorite(r)} />
        </View>
      ) : null}

      {step === 'styles' ? (
        <View style={{ gap: Space.xl }}>
          <Display>Estilos</Display>
          <Body muted>Opcional. Marca los estilos que te gustan.</Body>
          <View style={s.wrap}>
            {EDITORIAL_STYLES.map((st) => (
              <Chip key={st} label={st} selected={styles.includes(st)} onPress={() => toggleStyle(st)} />
            ))}
          </View>
          <Notice>
            Es una lista editorial de Chromatic Underground, no una clasificación de MusicBrainz ni de ningún artista. Por ahora
            guardamos tu elección, pero todavía no cambia las recomendaciones.
          </Notice>
        </View>
      ) : null}
    </Screen>
  );
}

const s = StyleSheet.create({
  topBar: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  skip: { color: C.muted, fontWeight: '800', fontSize: 15, textTransform: 'uppercase', letterSpacing: 1 },
  poster: { borderRadius: Radius.lg, padding: Space.xl, minHeight: 300, justifyContent: 'space-between', gap: Space.lg },
  posterTitle: { color: C.text, fontFamily: Fonts.display, fontWeight: Fonts.displayWeight ?? '900', fontSize: 58, lineHeight: 56, letterSpacing: -1 },
  posterStripe: { flexDirection: 'row' },
  wrap: { flexDirection: 'row', flexWrap: 'wrap', gap: Space.sm },
});
