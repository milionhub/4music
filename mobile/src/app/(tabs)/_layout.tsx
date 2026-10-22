import { Redirect } from 'expo-router';
import { NativeTabs } from 'expo-router/unstable-native-tabs';

import { C, Fonts } from '@/constants/theme';
import { useLibrary } from '@/state/library';

/** Cuatro destinos (v5): la búsqueda de canciones vive solo en TrackDNA; los artistas se abren desde las canciones. */
export default function TabsLayout() {
  const { preferences } = useLibrary();
  // Primer arranque: bienvenida. Una vez completada u omitida, no se repite.
  if (preferences.onboarding === 'pending') return <Redirect href="/onboarding" />;

  return (
    <NativeTabs
      backgroundColor={C.bg}
      tintColor={C.acid}
      iconColor={{ default: C.faint, selected: C.acid }}
      indicatorColor={`${C.acid}26`}
      labelStyle={{ color: C.muted, fontFamily: Fonts.monoBold, fontSize: 11 }}>
      <NativeTabs.Trigger name="index">
        <NativeTabs.Trigger.Label>Inicio</NativeTabs.Trigger.Label>
        <NativeTabs.Trigger.Icon sf={{ default: 'waveform', selected: 'waveform' }} md="graphic_eq" />
      </NativeTabs.Trigger>
      <NativeTabs.Trigger name="trackdna">
        <NativeTabs.Trigger.Label>TrackDNA</NativeTabs.Trigger.Label>
        <NativeTabs.Trigger.Icon sf="waveform.path.ecg" md="genetics" />
      </NativeTabs.Trigger>
      <NativeTabs.Trigger name="posters">
        <NativeTabs.Trigger.Label>Carteles</NativeTabs.Trigger.Label>
        <NativeTabs.Trigger.Icon sf={{ default: 'photo.on.rectangle', selected: 'photo.on.rectangle.angled' }} md="photo_library" />
      </NativeTabs.Trigger>
      <NativeTabs.Trigger name="saved">
        <NativeTabs.Trigger.Label>Guardados</NativeTabs.Trigger.Label>
        <NativeTabs.Trigger.Icon sf={{ default: 'heart', selected: 'heart.fill' }} md="favorite" />
      </NativeTabs.Trigger>
      <NativeTabs.Trigger name="profile">
        <NativeTabs.Trigger.Label>Perfil</NativeTabs.Trigger.Label>
        <NativeTabs.Trigger.Icon sf={{ default: 'person', selected: 'person.fill' }} md="person" />
      </NativeTabs.Trigger>
    </NativeTabs>
  );
}
