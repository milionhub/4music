/** TrackDNA: el buscador de canciones de la app. Cartel de club (TRACK en display, DNA en serif cursiva) y buscador protagonista. */
import { useWindowDimensions, View } from 'react-native';

import { TrackDnaPoster } from '@/components/editorial';
import { TrackSearch } from '@/components/track';
import { Screen } from '@/components/ui';
import { MaxContentWidth, Space } from '@/constants/theme';
import { fixedIdentity, surfaces } from '@/lib/artist-identity';

const ID = fixedIdentity('Cielo químico', 'anton');

export default function TrackDnaScreen() {
  const { width } = useWindowDimensions();
  const S = surfaces(ID.palette);
  return (
    <Screen background={S.screen} topTint={ID.palette.bg}>
      <View style={{ marginHorizontal: -Space.lg, marginTop: -Space.lg }}>
        <TrackDnaPoster id={ID} width={Math.min(width, MaxContentWidth)} subtitle="De dónde viene una canción, quién la firma y dónde escucharla." />
      </View>
      <TrackSearch id={ID} />
    </Screen>
  );
}
