/**
 * Icono de una plataforma musical (Simple Icons, CC0; marcas de sus titulares). Sin icono libre disponible
 * (Deezer, Traxsource, Qobuz, Juno…), una insignia tipográfica neutra con sus iniciales: nunca un logotipo inventado.
 */
import { Text, View } from 'react-native';
import Svg, { Path } from 'react-native-svg';

import { BRAND_ICONS } from '@/constants/platform-icons';
import { contrast } from '@/lib/artist-identity';

/** Etiqueta del backend (links.py) → icono de Simple Icons. */
const ICON_BY_LABEL: Record<string, string> = {
  Spotify: 'spotify', SoundCloud: 'soundcloud', Beatport: 'beatport', 'Apple Music': 'applemusic', Bandcamp: 'bandcamp',
  TIDAL: 'tidal', 'YouTube Music': 'youtubemusic', YouTube: 'youtube', Mixcloud: 'mixcloud', 'Amazon Music': 'amazonmusic',
  iTunes: 'itunes', Discogs: 'discogs',
};

export function hasBrandIcon(label: string): boolean {
  return label in ICON_BY_LABEL;
}

export function PlatformIcon({ label, size, background, fallbackColor }: {
  label: string; size: number; background: string; fallbackColor: string;
}) {
  const icon = BRAND_ICONS[ICON_BY_LABEL[label]];
  if (!icon) {
    const initials = label.replace(/[^A-Za-z0-9 ]/g, '').split(/\s+/).filter(Boolean).slice(0, 2).map((w) => w[0]).join('').toUpperCase();
    return (
      <View style={{ width: size, height: size, borderRadius: size / 2, borderWidth: 2, borderColor: fallbackColor, alignItems: 'center', justifyContent: 'center' }}>
        <Text style={{ color: fallbackColor, fontFamily: 'SpaceMono-Bold', fontSize: size * 0.36 }}>{initials || '♪'}</Text>
      </View>
    );
  }
  // Color de marca si se distingue del fondo; si no (TIDAL negro, Discogs gris, Spotify sobre lima), blanco o negro
  // según el fondo: las superficies claras de TrackDNA (V5.3) no pueden llevar un icono blanco.
  const fill = contrast(icon.hex, background) >= 2.2 ? icon.hex
    : contrast('#FFFFFF', background) >= contrast('#000000', background) ? '#FFFFFF' : '#000000';
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" accessibilityElementsHidden importantForAccessibility="no">
      <Path d={icon.path} fill={fill} />
    </Svg>
  );
}
