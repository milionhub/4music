/**
 * Artist Experience v4: cabecera-cartel tipográfica (sin fotos) y piezas de la ficha con la identidad visual de cada
 * artista (lib/artist-identity.ts) en el cartel y los acentos, sobre la base común de las fichas (V5.4): historias de «Más allá de la cabina» como
 * protagonistas, banda tipográfica, música con criterio explícito y plataformas con iconos. El nombre principal
 * siempre se ve entero (anchos reales de cada glifo); lo decorativo se oculta a los lectores de pantalla.
 */
import { Image } from 'expo-image';
import { openBrowserAsync } from 'expo-web-browser';
import { type ReactNode, useState } from 'react';
import { Platform, Pressable, StyleSheet, Text, View } from 'react-native';

import { PlatformIcon } from '@/components/platform-icon';
import { SheetHead } from '@/components/sheet';
import { Fonts, Radius, Space } from '@/constants/theme';
import { alpha, type ArtistIdentity, display, fitSize, nameLines } from '@/lib/artist-identity';
import { openTrack } from '@/components/track';
import { type CardRow, duration, formatCount, platformSearchUrl, releaseKind, uniqueBy } from '@/lib/format';
import { SHEET } from '@/lib/track-art';
import type { EssentialTrack, Link, RecentRelease, SourceRef, Story, TopTrack } from '@/types/music';

export const GUTTER = Space.lg;
const MONO = 'SpaceMono';
const MONO_BOLD = 'SpaceMono-Bold';
/** Superficies comunes (V5.4): la misma base que TrackDNA; la paleta del artista queda en el cartel y los acentos. */
export const ARTIST_SURFACES = { screen: SHEET.base.bg, raised: SHEET.raised.bg, deep: SHEET.deep.bg, line: SHEET.raised.line };
const INK = SHEET.base.ink;
const SOFT = SHEET.raised.soft;
const decorative = { accessibilityElementsHidden: true, importantForAccessibility: 'no-hide-descendants' as const };
// Android: el Custom Tab se abre en la tarea de la app; al cerrarlo se vuelve a la ficha (BUG-02). iOS sin cambios.
const BROWSER_OPTIONS = Platform.OS === 'android' ? { createTask: false } : undefined;

type HeroProps = {
  name: string; id: ArtistIdentity; width: number; height: number;
  /** Géneros verificados. */
  tags: string[];
  /** Datos verificados breves para el cartel («Rumanía», «Sello Atipic»): nunca inventados. */
  credits: string[];
  /** Foto con derechos verificados (Commons, catálogo editorial o Deezer) y su crédito breve; sin ella, cartel tipográfico. */
  photo?: { url: string; credit: string; sourceUrl?: string } | null;
  onPhotoError?: () => void;
};

/** Nombre en líneas ajustadas al ancho real de sus letras, con la tipografía de la identidad. */
export function NameStack({ name, id, width, maxSize, color, maxLines = 3 }: {
  name: string; id: ArtistIdentity; width: number; maxSize: number; color: string; maxLines?: number;
}) {
  const T = id.type;
  return (
    <View accessible accessibilityRole="header" accessibilityLabel={name}>
      {nameLines(name, maxLines).map((line, i) => {
        const text = display(line, T);
        const size = fitSize(text, width, T, maxSize, 16);
        return (
          <Text key={i} numberOfLines={1} adjustsFontSizeToFit minimumFontScale={0.6}
            style={{ fontFamily: T.family, fontSize: size, lineHeight: Math.round(size * T.lineFactor), letterSpacing: T.tracking,
              color, includeFontPadding: false, paddingTop: Platform.OS === 'ios' ? size * 0.04 : 0 }}>
            {text}
          </Text>
        );
      })}
    </View>
  );
}

function Shape({ id, size, style }: { id: ArtistIdentity; size: number; style: object }) {
  const pop = id.palette.pop;
  switch (id.shape) {
    case 'circle':
      return <View style={[{ position: 'absolute', width: size, height: size, borderRadius: size / 2, backgroundColor: pop }, style]} />;
    case 'ring':
      return <View style={[{ position: 'absolute', width: size, height: size, borderRadius: size / 2, borderWidth: size * 0.12, borderColor: pop }, style]} />;
    case 'bars':
      return (
        <View style={[{ position: 'absolute', width: size, gap: size * 0.1 }, style]}>
          {[1, 0.75, 0.5].map((w) => <View key={w} style={{ height: size * 0.13, width: size * w, backgroundColor: pop }} />)}
        </View>
      );
    default:
      return <View style={[{ position: 'absolute', width: size * 0.9, height: size * 0.9, backgroundColor: pop, transform: [{ rotate: '12deg' }] }, style]} />;
  }
}

function Tags({ tags, color, border }: { tags: string[]; color: string; border: string }) {
  if (!tags.length) return null;
  return (
    <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 6 }}>
      {uniqueBy(tags, (t) => t).map((t) => (
        <Text key={t} style={{ fontFamily: MONO_BOLD, fontSize: 11, letterSpacing: 1.2, textTransform: 'uppercase', color,
          borderWidth: 1.5, borderColor: border, paddingHorizontal: 10, paddingVertical: 3, borderRadius: Radius.pill }}>
          {t}
        </Text>
      ))}
    </View>
  );
}

function Mono({ children, color, size = 11, style }: { children: ReactNode; color: string; size?: number; style?: object }) {
  return (
    <Text numberOfLines={1} style={[{ fontFamily: MONO_BOLD, fontSize: size, letterSpacing: 1.6, textTransform: 'uppercase', color }, style]}>
      {children}
    </Text>
  );
}

/**
 * Cabecera-cartel. Cuatro composiciones con recursos propios (no una plantilla con el color cambiado): torre con
 * repetición vertical del nombre, marquesina de filas, diagonal con doble trazo y rejilla de cartel con datos.
 */
export function ArtistHero({ name, id, width: W, height: H, tags, credits, photo, onPhotoError }: HeroProps) {
  const P = id.palette;
  const T = id.type;
  const inner = W - GUTTER * 2;
  const shown = display(name, T);
  const top = Platform.OS === 'ios' ? 104 : 84; // bajo la barra de estado y el botón de volver
  let body: ReactNode;

  if (photo) {
    // Foto arriba y, debajo, una banda con la paleta del artista: el nombre nunca se superpone a la cara.
    return (
      <View style={{ width: W, height: H, overflow: 'hidden', backgroundColor: P.bg }}>
        <View style={{ flex: 1 }}>
          <Image source={{ uri: photo.url }} style={StyleSheet.absoluteFill} contentFit="cover" contentPosition="top"
            transition={200} onError={onPhotoError} accessibilityIgnoresInvertColors {...decorative} />
          <View style={{ position: 'absolute', top: 0, left: 0, right: 0, height: top + 24, backgroundColor: alpha(P.bg, 0.35) }} {...decorative} />
          <Pressable disabled={!photo.sourceUrl} onPress={() => photo.sourceUrl && openBrowserAsync(photo.sourceUrl, BROWSER_OPTIONS)}
            accessibilityRole="link" accessibilityLabel={`${photo.credit}. Ver la foto en su fuente original`} hitSlop={8}
            style={{ position: 'absolute', right: GUTTER, bottom: Space.sm, backgroundColor: alpha(P.bg, 0.75), paddingHorizontal: 6, paddingVertical: 2 }}>
            <Mono color={P.ink} size={9}>{photo.sourceUrl ? `${photo.credit} ↗` : photo.credit}</Mono>
          </Pressable>
        </View>
        <View style={{ height: 6, backgroundColor: P.pop }} />
        <View style={{ paddingHorizontal: GUTTER, paddingTop: Space.lg, paddingBottom: Space.xl, gap: Space.md }}>
          {credits.length ? <Mono color={P.ink}>{credits.join(' · ')}</Mono> : null}
          <NameStack name={name} id={id} width={inner} maxSize={56} color={P.ink} maxLines={2} />
          <Tags tags={tags} color={P.ink} border={P.ink} />
        </View>
      </View>
    );
  }

  if (id.composition === 'marquee') {
    // El nombre repetido en filas, cada una entera; la última más presente, las demás como textura.
    const size = fitSize(shown, inner, T, H / 5.6, 16);
    body = (
      <>
        <Shape id={id} size={W * 0.7} style={{ right: -W * 0.2, top: H * 0.06 }} />
        <View style={{ position: 'absolute', top: H * 0.13, left: GUTTER, right: GUTTER, gap: 2 }} {...decorative}>
          {[0, 1, 2, 3].map((i) => (
            <Text key={i} numberOfLines={1} style={{ fontFamily: T.family, fontSize: size, lineHeight: size * T.lineFactor, color: P.ink,
              opacity: [0.1, 0.18, 0.3, 0.55][i], letterSpacing: T.tracking, textAlign: i % 2 ? 'right' : 'left' }}>
              {shown}
            </Text>
          ))}
        </View>
        {tags.length || credits.length ? (
          <View style={[styles.band, { top: H * 0.6, backgroundColor: P.ink, transform: [{ rotate: `${id.tilt || -3}deg` }] }]} {...decorative}>
            <Mono color={P.bg}>{Array(4).fill([...tags, ...credits].join('  ✶  ')).join('  ✶  ')}</Mono>
          </View>
        ) : null}
        <View style={[styles.footer, { left: GUTTER, right: GUTTER }]}>
          <NameStack name={name} id={id} width={inner} maxSize={72} color={P.ink} maxLines={2} />
          <Tags tags={tags} color={P.ink} border={P.ink} />
        </View>
      </>
    );
  } else if (id.composition === 'slash') {
    // Nombre gigante en diagonal (girado sigue dentro del cartel) sobre una barra con doble trazo.
    const angle = id.tilt || -6;
    const span = inner / Math.cos((Math.abs(angle) * Math.PI) / 180) - 24;
    const size = fitSize(shown, span, T, H * 0.3, 28);
    body = (
      <>
        <View style={[styles.slashBar, { top: H * 0.4, width: W * 1.8, left: -W * 0.4, backgroundColor: P.pop, transform: [{ rotate: `${angle}deg` }] }]} />
        <View style={[styles.slashLine, { top: H * 0.4 + 104, width: W * 1.8, left: -W * 0.4, backgroundColor: P.ink, transform: [{ rotate: `${angle}deg` }] }]} />
        <View style={{ position: 'absolute', right: GUTTER, top: top - 8, width: W * 0.3, height: W * 0.3, borderRadius: W * 0.15, borderWidth: 2, borderColor: alpha(P.ink, 0.45) }} />
        <View style={{ position: 'absolute', top: H * 0.26, left: GUTTER, right: GUTTER, transform: [{ rotate: `${angle}deg` }] }} {...decorative}>
          <Text numberOfLines={1} style={{ fontFamily: T.family, fontSize: size, lineHeight: size * T.lineFactor, color: P.ink, letterSpacing: T.tracking, textAlign: 'center' }}>
            {shown}
          </Text>
        </View>
        {credits.length ? <Mono color={P.ink} style={{ position: 'absolute', top, left: GUTTER, maxWidth: W * 0.55 }}>{credits.join(' · ')}</Mono> : null}
        <View style={[styles.footer, { left: GUTTER, right: GUTTER }]}>
          <View style={{ backgroundColor: P.ink, alignSelf: 'flex-start', paddingHorizontal: Space.md, paddingVertical: Space.sm, maxWidth: inner }}>
            <NameStack name={name} id={id} width={inner - Space.md * 2} maxSize={44} color={P.bg} maxLines={2} />
          </View>
          <Tags tags={tags} color={P.ink} border={P.ink} />
        </View>
      </>
    );
  } else if (id.composition === 'grid') {
    // Cartel en rejilla: inicial gigante, celda con datos verificados al estilo de un cartel de club y nombre abajo.
    const initial = display([...name.trim()][0] ?? '?', T);
    const big = Math.round(H * 0.46);
    const line = alpha(P.ink, 0.35);
    body = (
      <>
        <View style={[styles.hLine, { top: H * 0.12, backgroundColor: line }]} />
        <View style={[styles.hLine, { top: H * 0.58, backgroundColor: line }]} />
        <View style={[styles.vLine, { left: W * 0.56, top: H * 0.12, height: H * 0.46, backgroundColor: line }]} />
        <Shape id={id} size={W * 0.28} style={{ left: W * 0.64, top: H * 0.34 }} />
        <Text {...decorative} style={{ position: 'absolute', top: H * 0.1, left: GUTTER - 4, fontFamily: T.family, fontSize: big, lineHeight: big * 1.02, color: P.ink }}>
          {initial}
        </Text>
        <View style={{ position: 'absolute', left: W * 0.6, right: GUTTER, top: H * 0.15, gap: 4 }} {...decorative}>
          {uniqueBy([...tags, ...credits], (c) => c).slice(0, 4).map((c) => <Mono key={c} color={P.ink} size={10}>{c}</Mono>)}
        </View>
        <View style={[styles.footer, { left: GUTTER, right: GUTTER }]}>
          <NameStack name={name} id={id} width={inner} maxSize={80} color={P.ink} />
        </View>
      </>
    );
  } else {
    // tower: nombre apilado a toda anchura y repetición parcial vertical del nombre en el borde izquierdo.
    const lines = nameLines(name);
    const railSize = fitSize(shown, H * 0.5, T, 40, 14);
    body = (
      <>
        <Shape id={id} size={W * 0.62} style={{ right: -W * 0.16, top: H * 0.06 }} />
        <View style={[styles.hLine, { top: top + 26, left: GUTTER, right: W * 0.45, backgroundColor: alpha(P.ink, 0.5) }]} />
        {credits.length ? <Mono color={P.ink} style={{ position: 'absolute', top, left: GUTTER, maxWidth: W * 0.5 }}>{credits.join(' · ')}</Mono> : null}
        <Text {...decorative} numberOfLines={1}
          style={{ position: 'absolute', left: GUTTER - H * 0.25 + railSize * 0.5, top: H * 0.38, width: H * 0.5, textAlign: 'center',
            fontFamily: T.family, fontSize: railSize, color: alpha(P.ink, 0.2), transform: [{ rotate: '-90deg' }] }}>
          {shown}
        </Text>
        <View style={[styles.footer, { left: GUTTER, right: GUTTER }]}>
          <NameStack name={name} id={id} width={inner} maxSize={Math.min(W * 0.42, (H * 0.5) / lines.length)} color={P.ink} />
          <Tags tags={tags} color={P.ink} border={P.ink} />
        </View>
      </>
    );
  }
  return <View style={{ width: W, height: H, overflow: 'hidden', backgroundColor: P.bg }}>{body}</View>;
}

/** Título de sección: el mismo tratamiento que TrackDNA (components/sheet.tsx), con el acento del artista. */
export function SectionHead({ index, title, id, right }: { index: string; title: string; id: ArtistIdentity; right?: ReactNode }) {
  return <SheetHead index={index} title={title} accent={id.palette.glow} right={right} />;
}

/** «Conoce al artista»: ficha de revista con datos verificados en celdas (solo los que constan). */
export function ArtistCard({ name, id, rows, genres }: { name: string; id: ArtistIdentity; rows: CardRow[]; genres: string[] }) {
  const P = id.palette;
  const S = ARTIST_SURFACES;
  return (
    <View style={[styles.card, { backgroundColor: S.raised, borderColor: S.line }]}>
      <View style={[styles.cardStrip, { backgroundColor: P.glow }]}>
        <Mono color={P.onGlow}>Ficha</Mono>
        {genres[0] ? <Mono color={P.onGlow}>{genres[0]}</Mono> : null}
      </View>
      <View style={{ padding: Space.lg, gap: Space.md }}>
        <Text style={{ fontFamily: id.type.family, fontSize: 32, lineHeight: 36, color: INK, letterSpacing: id.type.tracking,
          textTransform: id.type.upper ? 'uppercase' : 'none' }} numberOfLines={2} adjustsFontSizeToFit minimumFontScale={0.6}>
          {name}
        </Text>
        {genres.length ? (
          <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 6 }}>
            {uniqueBy(genres, (g) => g).map((g) => <Text key={g} style={[styles.genre, { backgroundColor: P.glow, color: P.onGlow }]}>{g}</Text>)}
          </View>
        ) : null}
        {rows.length ? (
          <View style={styles.cells}>
            {rows.map((r) => (
              <View key={r.label} style={[styles.cell, { backgroundColor: S.deep, borderColor: S.line },
                r.value.length > 22 && { width: '100%' }]}>
                <Mono color={P.glow} size={10}>{r.label}</Mono>
                <Text style={styles.cellValue}>{r.value}</Text>
              </View>
            ))}
          </View>
        ) : null}
      </View>
    </View>
  );
}

const STORY_KICKER: Record<Story['key'], string> = { inicios: 'Los inicios', universo: 'Su universo', momento: 'El momento clave' };

/**
 * «Más allá de la cabina»: tarjetas sobre la superficie común con el acento del artista; la primera, destacada.
 * Titulares en serif editorial (nunca la tipografía ultraancha del cartel en varias líneas). Cada historia enlaza las
 * fuentes de los hechos que cita.
 */
export function StoryBlocks({ stories, id, loading }: { stories: Story[]; id: ArtistIdentity; loading: boolean }) {
  const P = id.palette;
  const S = ARTIST_SURFACES;
  if (loading) {
    return (
      <View style={{ gap: Space.md }} accessibilityLabel="Investigando su trayectoria" accessibilityLiveRegion="polite">
        <View style={{ height: 150, borderRadius: Radius.sm, backgroundColor: S.raised }} />
        {[0.9, 0.7].map((w, i) => <View key={i} style={{ height: 14, width: `${w * 100}%`, borderRadius: 7, backgroundColor: S.raised }} />)}
      </View>
    );
  }
  return (
    <View style={{ gap: Space.md }}>
      {stories.map((s, i) => (
        <View key={s.key} style={[styles.storyCard, { backgroundColor: S.raised, borderTopColor: P.glow }]}>
          <Mono color={P.glow} size={10}>{`${String(i + 1).padStart(2, '0')} · ${STORY_KICKER[s.key]}`}</Mono>
          <Text accessibilityRole="header" style={[styles.storyTitle, i === 0 && { fontSize: 28, lineHeight: 33 }]}>{s.title}</Text>
          <Text style={styles.storyText}>{s.text}</Text>
        </View>
      ))}
    </View>
  );
}

/** Banda tipográfica decorativa con el nombre repetido: separa secciones con la voz del cartel. */
export function NameBand({ name, id, width }: { name: string; id: ArtistIdentity; width: number }) {
  const text = Array(6).fill(display(name, id.type)).join('  ✶  ');
  return (
    <View {...decorative} style={{ marginHorizontal: -GUTTER, width, paddingVertical: Space.md, backgroundColor: ARTIST_SURFACES.deep,
      borderTopWidth: 2, borderBottomWidth: 2, borderColor: id.palette.glow, overflow: 'hidden' }}>
      <Text numberOfLines={1} style={{ fontFamily: id.type.family, fontSize: 40, lineHeight: 44, color: alpha(id.palette.glow, 0.5), width: width * 4 }}>
        {text}
      </Text>
    </View>
  );
}

/** Temas más escuchados con escuchas reales de ListenBrainz: ranking numerado, portada y búsqueda para escuchar. */
export function TopTrackList({ tracks, id }: { tracks: TopTrack[]; id: ArtistIdentity }) {
  const S = ARTIST_SURFACES;
  return (
    <View style={{ gap: Space.sm }}>
      {tracks.map((t, i) => (
        <View key={t.recording_mbid} style={[styles.trackRow, { backgroundColor: i === 0 ? S.raised : 'transparent', borderColor: S.line }]}>
          <Text style={{ width: 34, fontFamily: id.type.family, fontSize: 28, lineHeight: 30, color: id.palette.glow }}>{i + 1}</Text>
          <Cover uri={t.cover_url} size={56} id={id} title={t.title} />
          <View style={{ flex: 1, gap: 2 }}>
            <Text style={styles.trackTitle} numberOfLines={2}>{t.title}</Text>
            <Text style={styles.monoMeta} numberOfLines={1}>{formatCount(t.listen_count)} escuchas en ListenBrainz</Text>
          </View>
          <SearchButton query={t.search_query} title={t.title} id={id} />
        </View>
      ))}
    </View>
  );
}

/**
 * Tracks esenciales (cierre de «Más allá de la cabina»): 3–4 canciones propias con su TrackDNA. El criterio es la
 * popularidad en Deezer y se dice debajo; toda la fila abre la ficha de la canción.
 */
export function EssentialTracks({ tracks, id, basis }: { tracks: EssentialTrack[]; id: ArtistIdentity; basis: string | null }) {
  const S = ARTIST_SURFACES;
  const P = id.palette;
  return (
    <View style={{ gap: Space.sm }}>
      <Mono color={P.glow} size={10}>Para empezar · sus esenciales</Mono>
      {tracks.map((t, i) => (
        <Pressable key={t.id} onPress={() => openTrack(t.id)} accessibilityRole="button"
          accessibilityLabel={`${t.title}${t.year ? `, ${t.year}` : ''}. Abrir su TrackDNA`}
          style={({ pressed }) => [styles.trackRow, { backgroundColor: i === 0 ? S.raised : 'transparent', borderColor: S.line },
            pressed && { borderColor: P.glow }]}>
          <Text style={{ width: 34, fontFamily: id.type.family, fontSize: 28, lineHeight: 30, color: P.glow }}>{i + 1}</Text>
          <Cover uri={t.cover_url} size={56} id={id} title={t.title} />
          <View style={{ flex: 1, gap: 2 }}>
            <Text style={styles.trackTitle} numberOfLines={2}>{t.title}</Text>
            <Text style={styles.monoMeta} numberOfLines={1}>{[t.year, duration(t.length_ms)].filter(Boolean).join(' · ')}</Text>
          </View>
          <View style={[styles.dnaPill, { borderColor: P.glow }]}>
            <Text style={[styles.monoMeta, { color: P.glow, fontSize: 10 }]}>TrackDNA →</Text>
          </View>
        </Pressable>
      ))}
      {basis ? <Text style={[styles.monoMeta, { color: SOFT }]}>{basis}</Text> : null}
    </View>
  );
}

/** Música documentada sin datos de escuchas: lista por fecha (nunca un ranking), con portada y búsqueda. */
export function ReleaseList({ releases, id }: { releases: RecentRelease[]; id: ArtistIdentity }) {
  const S = ARTIST_SURFACES;
  return (
    <View style={{ gap: Space.sm }}>
      {releases.map((r) => {
        const kind = releaseKind(r);
        return (
          <View key={r.mbid} style={[styles.trackRow, { borderColor: S.line }]}>
            <Pressable onPress={() => openBrowserAsync(r.url, BROWSER_OPTIONS)} accessibilityRole="link"
              accessibilityLabel={`${r.title}, ${kind ?? 'lanzamiento'}, ${r.first_release_date}. Abrir en MusicBrainz`}
              style={({ pressed }) => [{ flex: 1, flexDirection: 'row', alignItems: 'center', gap: Space.md }, pressed && { opacity: 0.75 }]}>
              <Cover uri={r.cover_url} size={64} id={id} title={r.title} />
              <View style={{ flex: 1, gap: 3 }}>
                <Text style={styles.trackTitle} numberOfLines={2}>{r.title}</Text>
                <Text style={styles.monoMeta} numberOfLines={1}>{[kind, r.first_release_date.slice(0, 4)].filter(Boolean).join(' · ')}</Text>
                {r.with_artists.length ? <Text style={[styles.monoMeta, { color: SOFT }]} numberOfLines={1}>con {r.with_artists.join(', ')}</Text> : null}
              </View>
            </Pressable>
            <SearchButton query={`${r.title} ${r.with_artists.join(' ')}`.trim()} title={r.title} id={id} />
          </View>
        );
      })}
    </View>
  );
}

function SearchButton({ query, title, id }: { query: string; title: string; id: ArtistIdentity }) {
  return (
    <Pressable onPress={() => openBrowserAsync(platformSearchUrl('spotify', query), BROWSER_OPTIONS)} accessibilityRole="link"
      accessibilityLabel={`Buscar ${title} en Spotify (búsqueda, no enlace directo)`} hitSlop={8}
      style={({ pressed }) => [styles.searchBtn, { borderColor: ARTIST_SURFACES.line }, pressed && { opacity: 0.6 }]}>
      <PlatformIcon label="Spotify" size={18} background={SHEET.base.bg} fallbackColor={INK} />
      <Text style={styles.searchLabel}>Buscar</Text>
    </Pressable>
  );
}

function Cover({ uri, size, id, title }: { uri: string | null; size: number; id: ArtistIdentity; title: string }) {
  const [failed, setFailed] = useState(false);
  if (uri && !failed) {
    return (
      <Image source={{ uri }} style={{ width: size, height: size, borderRadius: 4, backgroundColor: ARTIST_SURFACES.raised }}
        contentFit="cover" cachePolicy="disk" transition={150} onError={() => setFailed(true)} accessibilityIgnoresInvertColors />
    );
  }
  return (
    <View style={{ width: size, height: size, borderRadius: 4, backgroundColor: ARTIST_SURFACES.raised, alignItems: 'center', justifyContent: 'center' }}>
      <Text style={{ fontFamily: id.type.family, fontSize: size * 0.42, color: alpha(id.palette.glow, 0.6) }}>{display([...title][0] ?? '♪', id.type)}</Text>
    </View>
  );
}

/**
 * Plataformas: muelle de iconos reconocibles con nombre pequeño; abre el perfil verificado del artista o, en TrackDNA,
 * el enlace documentado de la canción. `detail` dice a qué lleva cada enlace («Canción», «Álbum»).
 */
export function PlatformDock({ links, id, width, detail, cols = 3 }: {
  links: Link[]; id: ArtistIdentity; width: number; detail?: (l: Link) => string | null; cols?: number;
}) {
  const S = ARTIST_SURFACES;
  const cell = Math.floor((width - Space.sm * (cols - 1)) / cols);
  return (
    <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: Space.sm }}>
      {links.map((l) => {
        const sub = detail?.(l) ?? null;
        return (
          <Pressable key={l.url} onPress={() => openBrowserAsync(l.url, BROWSER_OPTIONS)} accessibilityRole="link"
            accessibilityLabel={`Abrir en ${l.label}${sub ? `, ${sub}` : ''}`}
            style={({ pressed }) => [styles.dockCell, { width: cell, backgroundColor: S.raised, borderColor: S.line }, pressed && { borderColor: id.palette.glow }]}>
            <PlatformIcon label={l.label} size={30} background={S.raised} fallbackColor={id.palette.glow} />
            <Text style={styles.dockLabel} numberOfLines={1}>{l.label}</Text>
            {sub ? <Text style={[styles.monoMeta, { color: id.palette.glow, fontSize: 10 }]} numberOfLines={1}>{sub}</Text> : null}
          </Pressable>
        );
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  footer: { position: 'absolute', bottom: Space.xl, gap: Space.md },
  band: { position: 'absolute', left: -40, right: -40, paddingVertical: 8, paddingHorizontal: 40 },
  slashBar: { position: 'absolute', height: 86 },
  slashLine: { position: 'absolute', height: 3 },
  hLine: { position: 'absolute', left: 0, right: 0, height: StyleSheet.hairlineWidth * 2 },
  vLine: { position: 'absolute', width: StyleSheet.hairlineWidth * 2 },
  card: { borderRadius: Radius.md, borderWidth: 1, overflow: 'hidden' },
  cardStrip: { flexDirection: 'row', justifyContent: 'space-between', paddingHorizontal: Space.lg, paddingVertical: 7 },
  genre: { fontFamily: MONO_BOLD, fontSize: 12, letterSpacing: 1.2, textTransform: 'uppercase', paddingHorizontal: 12, paddingVertical: 5, borderRadius: Radius.pill, overflow: 'hidden' },
  cells: { flexDirection: 'row', flexWrap: 'wrap', gap: Space.sm },
  cell: { width: '48.5%', borderRadius: Radius.sm, borderWidth: 1, padding: Space.md, gap: 4 },
  cellValue: { color: INK, fontSize: 17, lineHeight: 22, fontFamily: Fonts.sansBold },
  storyText: { color: INK, fontFamily: Fonts.sans, fontSize: 17, lineHeight: 26 },
  storyCard: { gap: Space.sm, borderRadius: Radius.sm, borderTopWidth: 4, padding: Space.lg },
  storyTitle: { color: INK, fontFamily: Fonts.serifDisplay, fontSize: 24, lineHeight: 29 },
  trackRow: { flexDirection: 'row', alignItems: 'center', gap: Space.md, padding: Space.sm, borderRadius: Radius.md, borderWidth: 1 },
  dnaPill: { borderWidth: 1.5, borderRadius: Radius.pill, paddingHorizontal: 10, paddingVertical: 6 },
  trackTitle: { color: INK, fontSize: 16, fontFamily: Fonts.sansBold, lineHeight: 20 },
  monoMeta: { color: SOFT, fontFamily: MONO, fontSize: 11, letterSpacing: 0.4 },
  searchBtn: { flexDirection: 'row', alignItems: 'center', gap: 6, minHeight: 40, paddingHorizontal: Space.md, borderRadius: Radius.pill, borderWidth: 1.5 },
  searchLabel: { color: INK, fontSize: 13, fontFamily: Fonts.sansBold },
  dockCell: { minHeight: 84, borderRadius: Radius.md, borderWidth: 1.5, alignItems: 'center', justifyContent: 'center', gap: 8, paddingHorizontal: 6 },
  dockLabel: { color: INK, fontSize: 12, fontFamily: Fonts.sansBold },
});
