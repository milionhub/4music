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
import { Body, Button, Chip, Display, GradientBox, Meta, Notice, Screen, Section } from '@/components/ui';
import { C, Fonts, MaxContentWidth, Radius, Space } from '@/constants/theme';
import { EDITORIAL_STYLES } from '@/constants/styles';
import { fixedIdentity, surfaces } from '@/lib/artist-identity';
import { useLibrary } from '@/state/library';

/** La misma identidad que «Tu pase» (Perfil): editar es parte de él. */
const PASS = fixedIdentity('Ultravioleta', 'anton');
const PP = PASS.palette;
const PS = surfaces(PP);

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

  if (editing) return <EditArtists onDone={() => leave('completed')} />;

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
            Es una lista editorial de Chromatic Underground, no una clasificación de MusicBrainz ni de ningún artista. Tu
            frecuencia, en Inicio, la usa para proponerte canciones.
          </Notice>
        </View>
      ) : null}
    </Screen>
  );
}

/** Editar artistas de partida (desde el Perfil): cartel de «Tu pase», elegidos como fichas y buscador con su color. */
function EditArtists({ onDone }: { onDone: () => void }) {
  const lib = useLibrary();
  const { width } = useWindowDimensions();
  const n = lib.favorites.length;
  const footer = (
    <Pressable onPress={onDone} accessibilityRole="button" style={({ pressed }) => [s.done, pressed && { opacity: 0.85 }]}>
      <Text style={s.doneLabel}>{n ? `Listo · ${n} ${n === 1 ? 'artista' : 'artistas'}` : 'Listo'}</Text>
    </Pressable>
  );
  return (
    <Screen withTabBar={false} footer={footer} background={PS.screen} topTint={PP.bg}>
      <View style={{ marginHorizontal: -Space.lg, marginTop: -Space.lg }}>
        <ScreenPoster id={PASS} width={Math.min(width, MaxContentWidth)} word="Tus artistas" kicker="Artistas de partida"
          figure={n ? String(n).padStart(2, '0') : undefined}
          subtitle="Inicio parte de ellos para proponerte artistas y canciones conectados, siempre con el motivo." />
      </View>

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
    </Screen>
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
  topBar: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  skip: { color: C.muted, fontWeight: '800', fontSize: 15, textTransform: 'uppercase', letterSpacing: 1 },
  poster: { borderRadius: Radius.lg, padding: Space.xl, minHeight: 300, justifyContent: 'space-between', gap: Space.lg },
  posterTitle: { color: C.text, fontFamily: Fonts.display, fontWeight: Fonts.displayWeight ?? '900', fontSize: 58, lineHeight: 56, letterSpacing: -1 },
  posterStripe: { flexDirection: 'row' },
  wrap: { flexDirection: 'row', flexWrap: 'wrap', gap: Space.sm },
});
