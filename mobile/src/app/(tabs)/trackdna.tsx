/** TrackDNA: el buscador de canciones de la app. Cartel de club con la edición del día (V6.6) y buscador protagonista. */
import { useState } from 'react';
import { useWindowDimensions, View } from 'react-native';

import { TrackSearch } from '@/components/track';
import { TrackDnaPoster } from '@/components/trackdna-poster';
import { Screen } from '@/components/ui';
import { MaxContentWidth, Space } from '@/constants/theme';
import { surfaces } from '@/lib/artist-identity';
import { dailyEdition } from '@/lib/trackdna-home';

export default function TrackDnaScreen() {
  const { width } = useWindowDimensions();
  const [edition] = useState(() => dailyEdition(new Date()));
  const S = surfaces(edition.id.palette);
  return (
    <Screen background={S.screen} topTint={edition.id.palette.bg}>
      <View style={{ marginHorizontal: -Space.lg, marginTop: -Space.lg }}>
        <TrackDnaPoster edition={edition} width={Math.min(width, MaxContentWidth)} subtitle="De dónde viene una canción, quién la firma y dónde escucharla." />
      </View>
      <TrackSearch id={edition.id} />
    </Screen>
  );
}
