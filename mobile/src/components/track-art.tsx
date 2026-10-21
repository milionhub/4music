/**
 * Piezas de TrackDNA. V5.4: misma marca, distintas canciones. El cartel (cuatro composiciones con la paleta y el trío
 * tipográfico de la canción) concentra la variedad; el interior usa el sistema común `SHEET` (lib/track-art.ts) con
 * las mismas tarjetas en todas las fichas y el color de la canción solo como acento.
 *
 * Reglas: el texto siempre va en la tinta de su superficie (contraste comprobado); los acentos pintan formas, cifras
 * grandes y etiquetas con contraste ≥ 4,5:1; lo funcional nunca se recorta.
 */
import { openBrowserAsync } from 'expo-web-browser';
import type { ReactNode } from 'react';
import { Platform, Pressable, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { ArtistMark, CoverPlate, decorative } from '@/components/editorial';
import { PlatformIcon } from '@/components/platform-icon';
import { openArtist, openTrack } from '@/components/track';
import { Fonts, Radius, Space } from '@/constants/theme';
import { contrast, display, fitSize, nameLines, splitTitle, type Typeface, TYPEFACES } from '@/lib/artist-identity';
import { creditParts, duration, type ListenOption } from '@/lib/format';
import { SHEET, type Surface, type TrackArt } from '@/lib/track-art';
import type { SheetArtist, SheetDna, TrackStory, VersionRow } from '@/lib/track-sheet';
import type { TrackResponse } from '@/types/music';

export const GUTTER = Space.lg;
const BROWSER_OPTIONS = Platform.OS === 'android' ? { createTask: false } : undefined;

/** Estilo de texto de una tipografía medida (cada peso es una familia: nunca `fontWeight`). */
function type(face: Typeface, size: number, color: string, line = face.lineFactor) {
  return { fontFamily: face.family, fontSize: size, lineHeight: Math.round(size * line), letterSpacing: face.tracking, color, includeFontPadding: false };
}

/** Color legible sobre un acento (para textos decorativos de bandas). */
function inkOn(bg: string, a: string, b: string) {
  return contrast(a, bg) >= contrast(b, bg) ? a : b;
}

const MONO = { fontFamily: Fonts.mono, fontSize: 11, letterSpacing: 0.6 };
const MONO_B = { fontFamily: Fonts.monoBold, fontSize: 11, letterSpacing: 1.4, textTransform: 'uppercase' as const };

// --- Título en dos voces ------------------------------------------------------------------------------------------
/** Nombre en líneas ajustadas a su ancho real (titular) y subtítulo o versión en la voz de contraste. */
function ArtTitle({ title, art, width, color, align = 'left', max = 96 }: {
  title: string; art: TrackArt; width: number; color: string; align?: 'left' | 'center'; max?: number;
}) {
  const T = art.trio.title;
  const V = art.trio.voice;
  const { main, aside } = splitTitle(title);
  const asideText = aside ? display(aside, V) : null;
  const asideSize = asideText ? fitSize(asideText, width, V, 34, 16) : 0;
  return (
    <View accessible accessibilityRole="header" accessibilityLabel={title} style={{ gap: 2 }}>
      {nameLines(main, 3).map((line, i) => {
        const text = display(line, T);
        const size = fitSize(text, width, T, max, 18);
        return (
          <Text key={i} numberOfLines={1} adjustsFontSizeToFit minimumFontScale={0.6} style={[type(T, size, color), { textAlign: align }]}>
            {text}
          </Text>
        );
      })}
      {asideText ? (
        <Text numberOfLines={2} style={[type(V, asideSize, color, 1.15), { textAlign: align, marginTop: 4 }]}>{asideText}</Text>
      ) : null}
    </View>
  );
}

/** Créditos de la cabecera: cada artista con MBID abre su perfil; las uniones («&», «feat.») en la voz de contraste. */
function Credits({ data, art, color, align = 'left' }: { data: TrackResponse; art: TrackArt; color: string; align?: 'left' | 'center' }) {
  return (
    <Text style={{ color, fontFamily: Fonts.sansBold, fontSize: 19, lineHeight: 25, textAlign: align }}>
      {creditParts(data.artist_credit, data.artist_name).map((p, i) => (
        <Text key={`${p.mbid ?? p.name}-${i}`}>
          {p.mbid ? (
            <Text accessibilityRole="link" accessibilityHint="Abre el perfil del artista" onPress={() => openArtist(p.mbid!)} style={{ textDecorationLine: 'underline' }}>
              {p.name}
            </Text>
          ) : p.name}
          {p.join ? <Text style={{ fontFamily: art.trio.voice.family, fontSize: 20 }}>{p.join}</Text> : null}
        </Text>
      ))}
    </Text>
  );
}

/** Año y versión de la cabecera; duración, sello y formato van en el ADN (nada se repite entre secciones). */
function heroMeta(data: TrackResponse) {
  return {
    year: data.first_release_date?.slice(0, 4) ?? null,
    version: data.version && data.version !== splitTitle(data.title).aside ? data.version : null,
  };
}

function VersionTag({ label, bg, ink }: { label: string; bg: string; ink: string }) {
  return <Text numberOfLines={1} style={[MONO_B, styles.tag, { backgroundColor: bg, color: ink }]}>{label}</Text>;
}

/** Guardar: píldora en la tinta del cartel (máximo contraste); guardada, solo el contorno. */
export function ArtSave({ saved, onPress, s }: { saved: boolean; onPress: () => void; s: Surface }) {
  return (
    <Pressable onPress={onPress} accessibilityRole="button" accessibilityState={{ selected: saved }}
      accessibilityLabel={saved ? 'Canción guardada' : 'Guardar canción'} accessibilityHint={saved ? 'Pulsa para quitarla de Guardados' : undefined}
      style={({ pressed }) => [styles.save, saved ? { borderColor: s.ink } : { backgroundColor: s.ink, borderColor: s.ink }, pressed && { opacity: 0.8 }]}>
      <Text style={{ fontFamily: Fonts.sansBold, fontSize: 17, color: saved ? s.ink : s.bg }}>{saved ? '♥ Guardada' : '♡ Guardar canción'}</Text>
    </Pressable>
  );
}

// --- Cartel: cuatro composiciones ---------------------------------------------------------------------------------
type HeroProps = { data: TrackResponse; art: TrackArt; width: number; back: ReactNode; footer: ReactNode };

/** Superficie bajo la barra de estado (el cartel «partido» empieza en papel). */
export function heroTop(art: TrackArt): string {
  return art.hero === 'split' ? art.palette.paper.bg : art.palette.hero.bg;
}

export function ArtHero(props: HeroProps) {
  switch (props.art.hero) {
    case 'band': return <HeroBand {...props} />;
    case 'orbit': return <HeroOrbit {...props} />;
    case 'split': return <HeroSplit {...props} />;
    default: return <HeroStack {...props} />;
  }
}

/** Apilado: el título a toda anchura arriba; debajo, el año gigante en la voz de contraste frente a la portada. */
function HeroStack({ data, art, width, back, footer }: HeroProps) {
  const S = art.palette.hero;
  const inner = width - GUTTER * 2;
  const cover = Math.round(Math.min(inner * 0.48, 220));
  const m = heroMeta(data);
  return (
    <View style={{ width, backgroundColor: S.bg, paddingBottom: Space.xl, overflow: 'hidden' }}>
      <SafeAreaView edges={['top']} style={styles.top}>{back}</SafeAreaView>
      <View style={{ paddingHorizontal: GUTTER, gap: Space.lg }}>
        {m.version ? <VersionTag label={m.version} bg={S.ink} ink={S.bg} /> : null}
        <ArtTitle title={data.title} art={art} width={inner} color={S.ink} max={112} />
        <View style={{ flexDirection: 'row', alignItems: 'flex-end', gap: Space.lg }}>
          <View style={{ flex: 1, gap: 6 }}>
            {m.year ? <Text style={type(art.trio.voice, 64, S.ink, 1.05)}>{m.year}</Text> : null}
          </View>
          <View>
            <View {...decorative} style={{ position: 'absolute', right: -cover * 0.22, top: -cover * 0.22, width: cover * 0.8, height: cover * 0.8,
              borderRadius: cover * 0.4, backgroundColor: art.palette.accent }} />
            <CoverPlate uri={data.cover_url} seed={data.mbid} title={data.title} size={cover} radius={2} />
          </View>
        </View>
        <Credits data={data} art={art} color={S.ink} />
        {footer}
      </View>
    </View>
  );
}

/** Bandas: portada protagonista con un desfase de impresión; el título, línea a línea, sobre bandas de color. */
function HeroBand({ data, art, width, back, footer }: HeroProps) {
  const P = art.palette;
  const S = P.hero;
  const inner = width - GUTTER * 2;
  const cover = Math.round(Math.min(inner * 0.66, 280));
  const m = heroMeta(data);
  const { main, aside } = splitTitle(data.title);
  const bands = [P.night, P.alt];
  const T = art.trio.title;
  return (
    <View style={{ width, backgroundColor: S.bg, paddingBottom: Space.xl, overflow: 'hidden' }}>
      <SafeAreaView edges={['top']} style={styles.top}>{back}</SafeAreaView>
      <View style={{ alignItems: 'center', paddingVertical: Space.lg }}>
        <View>
          <View {...decorative} style={{ position: 'absolute', left: 12, top: 12, width: cover, height: cover, backgroundColor: P.accent }} />
          <CoverPlate uri={data.cover_url} seed={data.mbid} title={data.title} size={cover} radius={0} />
        </View>
      </View>
      <View accessible accessibilityRole="header" accessibilityLabel={data.title}>
        {nameLines(main, 3).map((line, i) => {
          const b = bands[i % 2];
          const text = display(line, T);
          const size = fitSize(text, inner, T, 92, 18);
          return (
            <View key={i} style={{ backgroundColor: b.bg, paddingHorizontal: GUTTER, paddingVertical: 4, alignSelf: i % 2 ? 'flex-end' : 'flex-start', maxWidth: width }}>
              <Text numberOfLines={1} adjustsFontSizeToFit minimumFontScale={0.6} style={type(T, size, b.ink)}>{text}</Text>
            </View>
          );
        })}
      </View>
      <View style={{ paddingHorizontal: GUTTER, gap: Space.md, marginTop: Space.lg }}>
        {aside ? <Text style={type(art.trio.voice, fitSize(display(aside, art.trio.voice), inner, art.trio.voice, 32, 16), S.ink, 1.15)}>{display(aside, art.trio.voice)}</Text> : null}
        <View style={{ flexDirection: 'row', alignItems: 'baseline', gap: Space.md, flexWrap: 'wrap' }}>
          {m.year ? <Text style={type(art.trio.voice, 40, S.ink, 1.1)}>{m.year}</Text> : null}
          {m.version ? <VersionTag label={m.version} bg={S.ink} ink={S.bg} /> : null}
        </View>
        <Credits data={data} art={art} color={S.ink} />
        {footer}
      </View>
    </View>
  );
}

/** Órbita: la portada centrada dentro de un anillo y un disco de acento; todo el texto centrado debajo. */
function HeroOrbit({ data, art, width, back, footer }: HeroProps) {
  const P = art.palette;
  const S = P.hero;
  const inner = width - GUTTER * 2;
  const cover = Math.round(Math.min(inner * 0.56, 240));
  const ring = Math.min(width * 0.9, cover * 1.6);
  const m = heroMeta(data);
  return (
    <View style={{ width, backgroundColor: S.bg, paddingBottom: Space.xl, overflow: 'hidden' }}>
      <SafeAreaView edges={['top']} style={styles.top}>{back}</SafeAreaView>
      <View style={{ height: ring, alignItems: 'center', justifyContent: 'center' }}>
        <View {...decorative} style={{ position: 'absolute', width: ring, height: ring, borderRadius: ring / 2, borderWidth: 5, borderColor: P.accent }} />
        <View {...decorative} style={{ position: 'absolute', width: cover * 0.9, height: cover * 0.9, borderRadius: cover * 0.45, backgroundColor: P.accent2,
          transform: [{ translateX: cover * 0.3 }, { translateY: cover * 0.2 }] }} />
        <CoverPlate uri={data.cover_url} seed={data.mbid} title={data.title} size={cover} radius={cover / 2} />
      </View>
      <View style={{ paddingHorizontal: GUTTER, gap: Space.md, alignItems: 'center' }}>
        <ArtTitle title={data.title} art={art} width={inner} color={S.ink} align="center" max={88} />
        <Text style={[MONO, { color: S.soft, textAlign: 'center' }]}>{m.year}</Text>
        {m.version ? <VersionTag label={m.version} bg={S.ink} ink={S.bg} /> : null}
        <Credits data={data} art={art} color={S.ink} align="center" />
        <View style={{ alignSelf: 'stretch' }}>{footer}</View>
      </View>
    </View>
  );
}

/** Partido: el título sobre papel claro; la portada cruza el corte hacia un bloque saturado con el año. */
function HeroSplit({ data, art, width, back, footer }: HeroProps) {
  const P = art.palette;
  const inner = width - GUTTER * 2;
  const cover = Math.round(Math.min(inner * 0.5, 220));
  const m = heroMeta(data);
  return (
    <View style={{ width, overflow: 'hidden' }}>
      <View style={{ backgroundColor: P.paper.bg, paddingBottom: cover * 0.45 + Space.lg }}>
        <SafeAreaView edges={['top']} style={styles.top}>{back}</SafeAreaView>
        <View style={{ paddingHorizontal: GUTTER, gap: Space.sm }}>
          {m.version ? <VersionTag label={m.version} bg={P.paper.ink} ink={P.paper.bg} /> : null}
          <ArtTitle title={data.title} art={art} width={inner} color={P.paper.ink} max={104} />
        </View>
      </View>
      <View style={{ backgroundColor: P.alt.bg, paddingHorizontal: GUTTER, paddingBottom: Space.xl, gap: Space.md }}>
        <View style={{ flexDirection: 'row', gap: Space.lg, marginTop: -cover * 0.45 }}>
          <CoverPlate uri={data.cover_url} seed={data.mbid} title={data.title} size={cover} radius={2} />
          <View style={{ flex: 1, justifyContent: 'flex-end', gap: 6, paddingBottom: 2 }}>
            {m.year ? <Text style={type(art.trio.voice, 56, P.alt.ink, 1.05)}>{m.year}</Text> : null}
          </View>
        </View>
        <Credits data={data} art={art} color={P.alt.ink} />
        {footer}
      </View>
    </View>
  );
}

// --- Separadores y secciones --------------------------------------------------------------------------------------
/** Separador tipográfico o geométrico entre el cartel y la ficha; decorativo. */
export function ArtDivider({ art, width, word }: { art: TrackArt; width: number; word: string }) {
  const P = art.palette;
  if (art.divider === 'stripes') {
    return (
      <View {...decorative}>
        {[[P.accent, 8], [P.accent2, 14], [P.alt.bg, 5]].map(([c, h], i) => <View key={i} style={{ height: h as number, backgroundColor: c as string }} />)}
      </View>
    );
  }
  if (art.divider === 'dots') {
    const n = Math.ceil(width / 28);
    return (
      <View {...decorative} style={{ flexDirection: 'row', gap: 8, paddingVertical: 10, paddingLeft: 6, backgroundColor: P.night.bg, overflow: 'hidden' }}>
        {Array.from({ length: n }).map((_, i) => <View key={i} style={{ width: 20, height: 20, borderRadius: 10, backgroundColor: i % 3 === 2 ? P.accent2 : P.accent }} />)}
      </View>
    );
  }
  const V = art.trio.voice;
  return (
    <View {...decorative} style={{ backgroundColor: P.accent, paddingVertical: 6, overflow: 'hidden' }}>
      <Text numberOfLines={1} style={[type(V, 30, inkOn(P.accent, P.night.bg, P.paper.bg), 1.2), { width: width * 4 }]}>
        {Array(8).fill(display(word, V)).join('   ✶   ')}
      </Text>
    </View>
  );
}

// --- ADN musical --------------------------------------------------------------------------------------------------
const ANTON = TYPEFACES.find((t) => t.key === 'anton')!;
const R = SHEET.raised;
const B = SHEET.base;
export type Accent = { color: string; ink: string };

/**
 * Tarjeta de ADN, la misma en todas las canciones: género y estilo arriba, BPM y tonalidad (con Camelot) como cifras,
 * y debajo producción y publicación en filas. Lo que no consta no deja hueco: la tarjeta se compone con lo que hay.
 */
export function DnaCard({ dna, accent, width }: { dna: SheetDna; accent: Accent; width: number }) {
  const inner = width - GUTTER * 2 - Space.lg * 2;
  const half = (inner - Space.lg) / 2;
  const g = dna.genre;
  const word = g ? display(g.family, ANTON) : null;
  const hasMeasures = !!(dna.bpm || dna.key);
  const rule = { borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: R.line, paddingTop: Space.lg };
  return (
    <View style={[styles.card, { backgroundColor: R.bg, borderTopColor: accent.color }]}>
      {g && word ? (
        <View accessible accessibilityLabel={`Género: ${g.family}${g.styles.length ? `. Estilo: ${g.styles.join(', ')}` : ''}${g.note ? `, ${g.note}` : ''}`} style={{ gap: 4 }}>
          <Text style={[MONO_B, { color: R.soft }]}>{g.note ? `Género · ${g.note}` : 'Género'}</Text>
          <Text numberOfLines={1} adjustsFontSizeToFit minimumFontScale={0.5} style={type(ANTON, fitSize(word, inner, ANTON, 60, 26), accent.color, 1.05)}>{word}</Text>
          {g.styles.length ? <Text style={styles.styleLine}>{g.styles.join(' · ')}</Text> : null}
        </View>
      ) : null}
      {hasMeasures ? (
        <View style={[{ flexDirection: 'row', gap: Space.lg }, g && rule]}>
          {dna.bpm ? (
            <View style={{ flex: 1, gap: 2 }} accessible accessibilityLabel={`BPM: ${dna.bpm.value}, ${dna.bpm.note}`}>
              <Text style={[MONO_B, { color: R.soft }]}>BPM</Text>
              <Text numberOfLines={1} style={type(ANTON, 52, R.ink, 1.05)}>{dna.bpm.value}</Text>
              <Text style={[MONO, { color: R.soft }]}>{dna.bpm.note}</Text>
            </View>
          ) : null}
          {dna.key ? (
            <View style={{ flex: 1, gap: 2 }} accessible
              accessibilityLabel={`Tonalidad: ${dna.key.value}${dna.key.camelot ? `, Camelot ${dna.key.camelot}` : ''}, ${dna.key.note}`}>
              <Text style={[MONO_B, { color: R.soft }]}>Tonalidad</Text>
              <Text numberOfLines={1} adjustsFontSizeToFit minimumFontScale={0.6} style={type(ANTON, fitSize(dna.key.value, half, ANTON, 36, 20), R.ink, 1.2)}>
                {dna.key.value}
              </Text>
              <View style={{ flexDirection: 'row', alignItems: 'center', gap: Space.sm, flexWrap: 'wrap' }}>
                {dna.key.camelot ? <Text style={[MONO_B, styles.camelot, { backgroundColor: accent.color, color: accent.ink }]}>{`Camelot ${dna.key.camelot}`}</Text> : null}
                <Text style={[MONO, { color: R.soft }]}>{dna.key.note}</Text>
              </View>
            </View>
          ) : null}
        </View>
      ) : null}
      {dna.rows.length ? (
        <View style={[{ gap: Space.sm }, (g || hasMeasures) && rule]}>
          {dna.rows.map((r) => (
            <View key={r.key} style={styles.dnaRow} accessible accessibilityLabel={`${r.label}: ${r.value}`}>
              <Text style={[MONO_B, { color: R.soft, width: 92, fontSize: 10 }]}>{r.label}</Text>
              <Text style={styles.rowValue}>{r.value}</Text>
            </View>
          ))}
        </View>
      ) : null}
    </View>
  );
}

// --- La historia del track ----------------------------------------------------------------------------------------
/** Un solo hecho: titular corto, una frase y, si habla de otra grabación del catálogo, el enlace a su ficha. */
export function StoryCard({ story, accent }: { story: TrackStory; accent: Accent }) {
  const mbid = story.mbid;
  return (
    <View style={[styles.story, { borderLeftColor: accent.color }]}>
      <Text style={styles.storyTitle}>{story.title}</Text>
      <Text style={styles.body}>{story.text}</Text>
      {mbid ? (
        <Pressable onPress={() => openTrack(mbid)} accessibilityRole="link" accessibilityHint="Abre la ficha de esa grabación"
          style={({ pressed }) => [styles.pill, { borderColor: accent.color }, pressed && { opacity: 0.7 }]}>
          <Text numberOfLines={1} style={[MONO_B, { color: accent.color }]}>{`${story.linkLabel ?? 'Abrir ficha'}  →`}</Text>
        </Pressable>
      ) : null}
    </View>
  );
}

// --- Artistas -----------------------------------------------------------------------------------------------------
/** Cada artista una vez, con su papel en el crédito; los que tienen ficha la abren. */
export function ArtistList({ artists }: { artists: SheetArtist[] }) {
  return (
    <View>
      {artists.map((a, i) => {
        const body = (
          <>
            <ArtistMark mbid={a.mbid ?? a.key} name={a.name} size={40} />
            <View style={{ flex: 1, gap: 2 }}>
              <Text numberOfLines={2} style={styles.name}>{a.name}</Text>
              <Text style={[MONO_B, { color: B.soft, fontSize: 10 }]}>{a.role}</Text>
            </View>
            {a.mbid ? <Text style={styles.arrow}>→</Text> : null}
          </>
        );
        const row = [styles.listRow, i > 0 && { borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: B.line }];
        const mbid = a.mbid;
        return mbid ? (
          <Pressable key={a.key} onPress={() => openArtist(mbid)} accessibilityRole="link" accessibilityLabel={`${a.name}, ${a.role}. Abrir perfil`}
            style={({ pressed }) => [...row, pressed && { opacity: 0.7 }]}>{body}</Pressable>
        ) : <View key={a.key} style={row} accessible accessibilityLabel={`${a.name}, ${a.role}`}>{body}</View>;
      })}
    </View>
  );
}

// --- Versiones ----------------------------------------------------------------------------------------------------
/** Original, extended y remixes seleccionados (lib/track-sheet.ts): cada fila abre la ficha de esa grabación. */
export function VersionList({ rows, accent }: { rows: VersionRow[]; accent: Accent }) {
  return (
    <View style={{ gap: Space.sm }}>
      {rows.map(({ item, kind }) => (
        <Pressable key={item.mbid} onPress={() => openTrack(item.mbid)} accessibilityRole="button"
          accessibilityLabel={`${kind}: ${item.title}, ${item.artist_name}. Abrir ficha`}
          style={({ pressed }) => [styles.version, { backgroundColor: R.bg }, pressed && { opacity: 0.75 }]}>
          <View style={{ flex: 1, gap: 4 }}>
            <Text style={[MONO_B, styles.kind, { backgroundColor: accent.color, color: accent.ink }]}>{kind}</Text>
            <Text numberOfLines={2} style={styles.versionTitle}>{item.title}</Text>
            <Text numberOfLines={1} style={[MONO, { color: R.soft }]}>{[item.artist_name, duration(item.length_ms)].filter(Boolean).join(' · ')}</Text>
          </View>
          <Text style={styles.arrow}>→</Text>
        </Pressable>
      ))}
    </View>
  );
}

// --- Escuchar -----------------------------------------------------------------------------------------------------
/** Enlace directo («Canción», «EP»…) o búsqueda explícita; nunca una búsqueda presentada como la canción. */
/** Canción de Discogs (V5.6): atribución obligatoria junto a los datos y aviso de no afiliación (API Terms of Use). */
export function SourceNote({ url }: { url: string }) {
  const S = SHEET.base;
  return (
    <View style={{ paddingHorizontal: GUTTER, paddingBottom: Space.xxxl, gap: Space.xs }}>
      <Text onPress={() => openBrowserAsync(url, BROWSER_OPTIONS)} accessibilityRole="link" style={[MONO_B, { color: S.ink, textDecorationLine: 'underline' }]}>
        Data provided by Discogs ↗
      </Text>
      <Text style={[MONO, { color: S.soft }]}>Canción fuera de MusicBrainz. Chromatic Underground no está afiliado a Discogs.</Text>
    </View>
  );
}

export function ListenList({ options }: { options: ListenOption[] }) {
  return (
    <View>
      {options.map((o, i) => (
        <Pressable key={o.key} onPress={() => openBrowserAsync(o.url, BROWSER_OPTIONS)} accessibilityRole="link"
          accessibilityLabel={o.direct ? `Abrir en ${o.label}: ${o.target}` : `Buscar en ${o.label} (búsqueda, no enlace directo)`}
          style={({ pressed }) => [styles.listen, i > 0 && { borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: B.line }, pressed && { opacity: 0.7 }]}>
          <PlatformIcon label={o.label} size={28} background={B.bg} fallbackColor={B.ink} />
          <Text style={styles.listenLabel} numberOfLines={1}>{o.direct ? o.label : `Buscar en ${o.label}`}</Text>
          <Text style={[MONO_B, { color: o.direct ? B.ink : B.soft, fontSize: 10, maxWidth: 150 }]} numberOfLines={1}>{o.target}</Text>
          <Text style={{ color: o.direct ? B.ink : B.soft, fontSize: 16 }}>↗</Text>
        </Pressable>
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  top: { paddingHorizontal: GUTTER, paddingTop: Space.sm, paddingBottom: Space.md, zIndex: 2 },
  tag: { alignSelf: 'flex-start', paddingHorizontal: 8, paddingVertical: 3, borderRadius: Radius.pill, overflow: 'hidden', maxWidth: 240, fontSize: 10 },
  save: { minHeight: 54, borderRadius: Radius.pill, borderWidth: 2, alignItems: 'center', justifyContent: 'center', paddingHorizontal: Space.xl },
  card: { padding: Space.lg, gap: Space.lg, borderRadius: Radius.sm, borderTopWidth: 4 },
  styleLine: { color: SHEET.raised.ink, fontFamily: Fonts.sansBold, fontSize: 18, lineHeight: 24 },
  camelot: { paddingHorizontal: 8, paddingVertical: 2, borderRadius: Radius.pill, overflow: 'hidden', fontSize: 10 },
  dnaRow: { flexDirection: 'row', alignItems: 'baseline', gap: Space.md },
  rowValue: { flex: 1, color: SHEET.raised.ink, fontFamily: Fonts.sansBold, fontSize: 16, lineHeight: 22 },
  story: { gap: Space.sm, borderLeftWidth: 4, paddingLeft: Space.lg, paddingVertical: 2 },
  storyTitle: { color: SHEET.base.ink, fontFamily: Fonts.serifDisplay, fontSize: 26, lineHeight: 31 },
  body: { color: SHEET.base.ink, fontFamily: Fonts.sans, fontSize: 17, lineHeight: 26 },
  pill: { alignSelf: 'flex-start', borderWidth: 1.5, borderRadius: Radius.pill, paddingHorizontal: Space.md, paddingVertical: 8, marginTop: Space.xs, maxWidth: '100%' },
  listRow: { flexDirection: 'row', alignItems: 'center', gap: Space.md, paddingVertical: Space.md },
  name: { color: SHEET.base.ink, fontFamily: Fonts.sansBold, fontSize: 18, lineHeight: 23 },
  arrow: { color: SHEET.base.ink, fontSize: 20 },
  version: { flexDirection: 'row', alignItems: 'center', gap: Space.md, padding: Space.md, borderRadius: Radius.sm },
  kind: { alignSelf: 'flex-start', paddingHorizontal: 8, paddingVertical: 2, borderRadius: Radius.pill, overflow: 'hidden', fontSize: 10 },
  versionTitle: { color: SHEET.raised.ink, fontFamily: Fonts.sansBold, fontSize: 16, lineHeight: 21 },
  listen: { flexDirection: 'row', alignItems: 'center', gap: Space.md, minHeight: 58 },
  listenLabel: { flex: 1, color: SHEET.base.ink, fontFamily: Fonts.sansBold, fontSize: 17 },
});
