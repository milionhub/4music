import { DarkTheme, Stack, ThemeProvider } from 'expo-router';
import { useFonts } from 'expo-font';
import * as SplashScreen from 'expo-splash-screen';
import { StatusBar } from 'expo-status-bar';
import { useEffect } from 'react';
import { useReducedMotion } from 'react-native-reanimated';

import { C } from '@/constants/theme';
import { LibraryProvider } from '@/state/library';

SplashScreen.preventAutoHideAsync();

const theme = {
  ...DarkTheme,
  colors: { ...DarkTheme.colors, background: C.bg, card: C.bg, primary: C.acid, text: C.text, border: C.line },
};

// Tipografías de la app (SIL Open Font License; licencias en assets/fonts/licenses y en cada paquete @expo-google-fonts).
const FONTS = {
  Anton: require('../../assets/fonts/Anton-Regular.ttf'),
  ArchivoBlack: require('../../assets/fonts/ArchivoBlack-Regular.ttf'),
  RubikMonoOne: require('../../assets/fonts/RubikMonoOne-Regular.ttf'),
  'InstrumentSerif-Italic': require('../../assets/fonts/InstrumentSerif-Italic.ttf'),
  SpaceMono: require('../../assets/fonts/SpaceMono-Regular.ttf'),
  'SpaceMono-Bold': require('../../assets/fonts/SpaceMono-Bold.ttf'),
  // v5.1 (OFL, paquetes @expo-google-fonts): serif expresiva y sans de interfaz.
  DMSerifDisplay: require('@expo-google-fonts/dm-serif-display/400Regular/DMSerifDisplay_400Regular.ttf'),
  'DMSerifDisplay-Italic': require('@expo-google-fonts/dm-serif-display/400Regular_Italic/DMSerifDisplay_400Regular_Italic.ttf'),
  'SpaceGrotesk-Medium': require('@expo-google-fonts/space-grotesk/500Medium/SpaceGrotesk_500Medium.ttf'),
  'SpaceGrotesk-Bold': require('@expo-google-fonts/space-grotesk/700Bold/SpaceGrotesk_700Bold.ttf'),
  // v5.3: serif fat display y sans geométrica ancha para la dirección artística de TrackDNA.
  AbrilFatface: require('@expo-google-fonts/abril-fatface/400Regular/AbrilFatface_400Regular.ttf'),
  'Syne-ExtraBold': require('@expo-google-fonts/syne/800ExtraBold/Syne_800ExtraBold.ttf'),
};

export default function RootLayout() {
  const reduceMotion = useReducedMotion();
  const [fontsLoaded, fontError] = useFonts(FONTS);
  const ready = fontsLoaded || !!fontError; // sin fuentes propias, la app sigue con las del sistema

  // Las preferencias se leen de forma síncrona en LibraryProvider: al montar ya se sabe qué pantalla mostrar.
  useEffect(() => {
    if (ready) SplashScreen.hideAsync();
  }, [ready]);

  if (!ready) return null;

  return (
    <LibraryProvider>
      <ThemeProvider value={theme}>
        <StatusBar style="light" />
        <Stack
          screenOptions={{
            headerShown: false,
            contentStyle: { backgroundColor: C.bg },
            animation: reduceMotion ? 'none' : 'default',
          }}>
          <Stack.Screen name="(tabs)" />
          <Stack.Screen name="onboarding" options={{ gestureEnabled: false, animation: reduceMotion ? 'none' : 'fade' }} />
          <Stack.Screen name="artist/[mbid]" />
          <Stack.Screen name="track/[mbid]" />
          <Stack.Screen name="poster/new" />
          <Stack.Screen name="poster/[id]" />
          <Stack.Screen name="poster/[id]/review" />
          <Stack.Screen name="poster/[id]/route" />
        </Stack>
      </ThemeProvider>
    </LibraryProvider>
  );
}
