/**
 * Piezas editoriales de Inicio (V6, lib/home-edition.ts): cabecera de revista, portada del día a sangre en cinco
 * composiciones (no recoloreadas: cambia la distribución) y secciones como islas de color sobre la noche de la edición,
 * separadas por aire (V6.1: cada color se lee por separado).
 *
 * Jerarquía (V6.1): la tipografía gigante solo en la portada; los encabezados de sección van a cuerpo fijo; el texto
 * corrido en sans 16–17 con interlineado amplio y en la tinta principal; la mono solo en rótulos cortos, desde 12 px.
 * Espacios: SECTION_GAP entre secciones, HEAD_GAP del encabezado al contenido, GROUP_GAP dentro de un grupo.
 *
 * Reglas (las de TrackDNA V5.3): el texto va siempre en la tinta de su superficie (contraste ≥ 4,5:1 comprobado en
 * las pruebas); los acentos solo pintan formas y bandas; los textos gigantes se ajustan al ancho real de sus letras
 * (`fitSize`) y no crecen con el tamaño de letra del sistema, y lo funcional (títulos, botones) nunca se recorta.
 */
import type { ReactNode } from 'react';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';

import { CoverPlate, decorative } from '@/components/editorial';
import { Fonts, Space } from '@/constants/theme';
import { ABRIL, display, DM_SERIF, DM_SERIF_ITALIC, fitSize, nameLines, splitTitle, type Typeface } from '@/lib/artist-identity';
import { type Edition, fitLines } from '@/lib/home-edition';
import type { FrequencyItem, SoundFact } from '@/lib/home-picks';
import type { Surface } from '@/lib/track-art';

export const GUTTER = Space.lg;
/** Margen lateral de las islas de color sobre el fondo de la edición. */
export const ISLAND = Space.md;
const SECTION_GAP = Space.xxxl;
const HEAD_GAP = Space.xl;
const GROUP_GAP = Space.md;
const SERIFS = new Set([ABRIL.key, DM_SERIF.key, DM_SERIF_ITALIC.key, 'serif']);

/** Estilo de una tipografía medida (cada peso es una familia: nunca `fontWeight`). */
function type(face: Typeface, size: number, color: string, line = face.lineFactor) {
  return { fontFamily: face.family, fontSize: size, lineHeight: Math.round(size * line), letterSpacing: face.tracking, color, includeFontPadding: false };
}

const MONO = { fontFamily: Fonts.mono, fontSize: 12, letterSpacing: 0.4 };
const MONO_B = { fontFamily: Fonts.monoBold, fontSize: 12, letterSpacing: 1, textTransform: 'uppercase' as const };
/** Los textos ya ajustados al ancho no crecen con la letra del sistema (se saldrían); el resto sí. */
const FIXED = { maxFontSizeMultiplier: 1, allowFontScaling: false } as const;
/** Cuerpo de los encabezados de sección. */
const HEAD_SIZE = 34;

/** Canción protagonista: datos de la selección editorial mientras carga su ficha; nunca inventados. */
export type Protagonist = { mbid: string; title: string; artist: string; cover: string | null; year: string | null };
export type LoadState = 'loading' | 'ok' | 'error';

// --- Piezas comunes ----------------------------------------------------------------------------------------------
/** Título de canción ajustado a un ancho: nombre en líneas con la tipografía titular y la versión en la de contraste. */
function FitTitle({ title, face, voice, width, color, max = 44, min = 20 }: {
  title: string; face: Typeface; voice: Typeface; width: number; color: string; max?: number; min?: number;
}) {
  const { main, aside } = splitTitle(title);
  const lines = nameLines(main, 3).map((l) => display(l, face));
  const size = Math.min(...lines.map((l) => fitSize(l, width, face, max, min)));
  return (
    <View accessible accessibilityRole="header" accessibilityLabel={title}>
      {lines.map((l, i) => (
        <Text key={i} {...FIXED} numberOfLines={1} adjustsFontSizeToFit minimumFontScale={0.6} style={type(face, size, color)}>{l}</Text>
      ))}
      {aside ? <Text numberOfLines={2} style={[type(voice, Math.max(15, Math.round(size * 0.45)), color, 1.2), { marginTop: 2 }]}>{display(aside, voice)}</Text> : null}
    </View>
  );
}

/** Acción principal: bloque recto en la tinta de la superficie (máximo contraste, sin píldoras). */
export function OpenButton({ s, label, onPress, disabled, hint }: { s: Surface; label: string; onPress: () => void; disabled?: boolean; hint?: string }) {
  return (
    <Pressable onPress={onPress} disabled={disabled} accessibilityRole="button" accessibilityState={{ disabled: !!disabled }} accessibilityHint={hint}
      style={({ pressed }) => [styles.open, { backgroundColor: s.ink }, (pressed || disabled) && { opacity: disabled ? 0.55 : 0.82 }]}>
      <Text style={[styles.openLabel, { color: s.bg }]} numberOfLines={1}>{label}</Text>
      <Text {...decorative} style={[styles.openLabel, { color: s.bg }]}>→</Text>
    </Pressable>
  );
}

function ctaLabel(state: LoadState) {
  return state === 'loading' ? 'Preparando la ficha…' : 'Abrir en TrackDNA';
}

/** Franja de cinta: acento fino y banda de tinta con un texto que se repite (decorativa, recortada a propósito). */
function Ticker({ text, s, accent }: { text: string; s: Surface; accent: string }) {
  return (
    <View {...decorative}>
      <View style={{ height: 6, backgroundColor: accent }} />
      <View style={{ backgroundColor: s.ink, paddingVertical: 6, overflow: 'hidden' }}>
        <Text {...FIXED} numberOfLines={1} ellipsizeMode="clip" style={[MONO_B, { color: s.bg, width: 2000 }]}>{`${text}   ✶   `.repeat(8)}</Text>
      </View>
    </View>
  );
}

/** Texto de la canción del día (kicker, título, artista y año) para cualquier composición. */
function SongText({ track, s, ed, width, max, face }: { track: Protagonist; s: Surface; ed: Edition; width: number; max?: number; face?: Typeface }) {
  return (
    <View style={{ gap: Space.sm, width }}>
      <Text style={[MONO_B, { color: s.soft }]} numberOfLines={1}>La canción del día</Text>
      <FitTitle title={track.title} face={face ?? ed.trio.title} voice={ed.trio.voice} width={width} color={s.ink} max={max} />
      <Text style={[styles.artist, { color: s.ink }]} numberOfLines={2}>{track.artist}</Text>
      {track.year ? <Text style={[MONO, { color: s.soft }]}>{track.year}</Text> : null}
    </View>
  );
}

// --- Cabecera ----------------------------------------------------------------------------------------------------
/** Cabecera fija de la revista (superficie noche: los iconos claros de la barra de estado siempre se leen). */
export function Masthead({ ed }: { ed: Edition }) {
  const N = ed.palette.night;
  return (
    <View style={{ backgroundColor: N.bg }}>
      <View style={styles.mast}>
        <Text accessibilityRole="header" style={[MONO_B, { color: N.ink, flexShrink: 1 }]} numberOfLines={1}>#4MUSIC</Text>
        <Text style={[MONO, { color: N.soft }]} numberOfLines={1}>{ed.dateLabel}</Text>
      </View>
      <View {...decorative} style={{ height: 4, backgroundColor: ed.palette.accent }} />
    </View>
  );
}

// --- Portada: cinco composiciones --------------------------------------------------------------------------------
type CoverProps = { ed: Edition; width: number; track: Protagonist | null; state: LoadState; onOpen: () => void; onSearch: () => void };

export function EditionCover(props: CoverProps) {
  switch (props.ed.layout) {
    case 'cross': return <CoverCross {...props} />;
    case 'asym': return <CoverAsym {...props} />;
    case 'serif': return <CoverSerif {...props} />;
    case 'blocks': return <CoverBlocks {...props} />;
    default: return <CoverStack {...props} />;
  }
}

/** Sin canción disponible (fallaron todas las candidatas): la portada lleva a buscar, nunca a una ficha rota. */
function CoverAction({ s, track, state, onOpen, onSearch }: { s: Surface } & Omit<CoverProps, 'ed' | 'width'>) {
  if (!track) return <OpenButton s={s} label="Buscar canciones en TrackDNA" onPress={onSearch} />;
  return <OpenButton s={s} label={ctaLabel(state)} disabled={state !== 'ok'} onPress={onOpen} hint={`Abre la ficha de ${track.title}`} />;
}

function headlineLabel(ed: Edition) {
  return `${ed.headline.word} ${ed.headline.voice}. Edición ${ed.palette.name}`;
}

/** Tipografía gigante apilada: la palabra a todo ancho, la frase de contraste montada encima y una cinta. */
function CoverStack({ ed, width, track, state, onOpen, onSearch }: CoverProps) {
  const P = ed.palette;
  const S = P.hero;
  const T = ed.trio.title;
  const V = ed.trio.voice;
  const inner = width - GUTTER * 2;
  const word = display(ed.headline.word, T);
  const big = fitSize(word, inner, T, 230, 28);
  const voice = fitLines(display(ed.headline.voice, V), inner, V, 54);
  const cover = Math.round(Math.min(inner * 0.42, 210));
  return (
    <View style={{ backgroundColor: S.bg }}>
      <View accessible accessibilityRole="header" accessibilityLabel={headlineLabel(ed)} style={{ paddingHorizontal: GUTTER, paddingTop: Space.lg }}>
        <Text style={[MONO_B, { color: S.ink }]}>Edición {P.name}</Text>
        <Text {...FIXED} numberOfLines={1} adjustsFontSizeToFit style={[type(T, big, S.ink, 0.92), { marginTop: Space.sm }]}>{word}</Text>
        <View {...decorative} style={{ marginTop: -Math.round(big * 0.06) }}>
          {voice.lines.map((l, i) => (
            <Text key={i} {...FIXED} numberOfLines={1} adjustsFontSizeToFit style={[type(V, voice.size, S.ink, 1.1), { textAlign: 'right' }]}>{l}</Text>
          ))}
        </View>
      </View>
      <View style={{ marginTop: Space.lg }}><Ticker text={`${ed.headline.word} ${ed.headline.voice}`} s={S} accent={P.accent} /></View>
      {track ? (
        <View style={{ flexDirection: 'row', gap: Space.lg, padding: GUTTER, alignItems: 'flex-end' }}>
          <CoverPlate uri={track.cover} seed={track.mbid} title={track.title} size={cover} radius={0} />
          <SongText track={track} s={S} ed={ed} width={inner - cover - Space.lg} max={40} />
        </View>
      ) : null}
      <View style={{ paddingHorizontal: GUTTER, paddingBottom: Space.xl, paddingTop: track ? 0 : Space.lg }}>
        <CoverAction s={S} track={track} state={state} onOpen={onOpen} onSearch={onSearch} />
      </View>
    </View>
  );
}

/** Titulares cruzados: dos bandas inclinadas que se cortan (palabra y frase) y la portada con un bloque desplazado. */
function CoverCross({ ed, width, track, state, onOpen, onSearch }: CoverProps) {
  const P = ed.palette;
  const S = P.paper;
  const T = ed.trio.title;
  const V = ed.trio.voice;
  const inner = width - GUTTER * 2;
  const word = display(ed.headline.word, T);
  const voice = display(ed.headline.voice, V);
  const a = fitSize(word, width * 0.5, T, 120, 28);
  const b = fitSize(voice, width * 0.62, V, 64, 26);
  const field = Math.round(a * 1.25 + b * 1.4 + 70);
  const cover = Math.round(Math.min(inner * 0.5, 240));
  return (
    <View style={{ backgroundColor: S.bg }}>
      <View accessible accessibilityRole="header" accessibilityLabel={headlineLabel(ed)} style={{ height: field + Space.xl, overflow: 'hidden' }}>
        <Text style={[MONO_B, { color: S.ink, paddingHorizontal: GUTTER, paddingTop: Space.lg }]}>Edición {P.name}</Text>
        <View {...decorative} style={[styles.band, { top: Space.xl + 18, width: width * 1.5, left: -width * 0.12, backgroundColor: P.hero.bg, transform: [{ rotate: '-7deg' }] }]}>
          <Text {...FIXED} numberOfLines={1} ellipsizeMode="clip" style={[type(T, a, P.hero.ink, 1.1), { width: width * 1.5 }]}>{`${word}  ${word}  ${word}`}</Text>
        </View>
        <View {...decorative} style={[styles.band, { top: Space.xl + 18 + a * 1.1 + 6, width: width * 1.5, left: -width * 0.3, backgroundColor: P.alt.bg, transform: [{ rotate: '5deg' }] }]}>
          <Text {...FIXED} numberOfLines={1} ellipsizeMode="clip" style={[type(V, b, P.alt.ink, 1.3), { width: width * 1.5, textAlign: 'right' }]}>{`${voice}  ·  ${voice}`}</Text>
        </View>
      </View>
      {track ? (
        <View style={{ paddingHorizontal: GUTTER, gap: Space.lg }}>
          <View style={{ flexDirection: 'row', gap: Space.lg + 8, alignItems: 'flex-start' }}>
            <View>
              <View {...decorative} style={{ position: 'absolute', left: 10, top: 10, width: cover, height: cover, backgroundColor: P.accent }} />
              <CoverPlate uri={track.cover} seed={track.mbid} title={track.title} size={cover} radius={0} />
            </View>
            <View style={{ flex: 1, gap: 4, paddingTop: Space.sm }}>
              <Text style={[MONO_B, { color: S.soft }]} numberOfLines={2}>La canción del día</Text>
              {track.year ? <Text {...FIXED} style={type(V, fitSize(track.year, inner - cover - Space.xl, V, 72, 28), S.ink, 1.05)}>{track.year}</Text> : null}
            </View>
          </View>
          <View style={{ gap: 4, marginTop: Space.sm }}>
            <FitTitle title={track.title} face={T} voice={V} width={inner} color={S.ink} max={58} />
            <Text style={[styles.artist, { color: S.ink }]}>{track.artist}</Text>
          </View>
        </View>
      ) : null}
      <View style={{ padding: GUTTER, paddingBottom: Space.xl }}>
        <CoverAction s={S} track={track} state={state} onOpen={onOpen} onSearch={onSearch} />
      </View>
    </View>
  );
}

/** Asimétrica: la frase en columna estrecha frente a una portada grande que sale por el borde; texto sangrado. */
function CoverAsym({ ed, width, track, state, onOpen, onSearch }: CoverProps) {
  const P = ed.palette;
  const S = P.alt;
  const T = ed.trio.title;
  const V = ed.trio.voice;
  const inner = width - GUTTER * 2;
  const col = Math.round(inner * 0.36);
  const cover = Math.round(width - GUTTER - col - Space.md);
  const voice = fitLines(display(ed.headline.voice, V), col, V, 46);
  const word = display(ed.headline.word, T);
  const indent = Math.round(inner * 0.24);
  return (
    <View style={{ backgroundColor: S.bg, paddingTop: Space.lg }}>
      <View accessible accessibilityRole="header" accessibilityLabel={headlineLabel(ed)}>
        <View style={{ flexDirection: 'row', gap: Space.md }}>
          <View style={{ width: col, marginLeft: GUTTER, justifyContent: 'space-between', paddingBottom: Space.sm }}>
            <Text style={[MONO_B, { color: S.ink }]} numberOfLines={3}>Edición {P.name}</Text>
            <View {...decorative}>
              {voice.lines.map((l, i) => <Text key={i} {...FIXED} numberOfLines={1} adjustsFontSizeToFit style={type(V, voice.size, S.ink, 1.05)}>{l}</Text>)}
            </View>
          </View>
          {track ? (
            <CoverPlate uri={track.cover} seed={track.mbid} title={track.title} size={cover} radius={0} />
          ) : (
            <View {...decorative} style={{ width: cover, height: cover, backgroundColor: P.accent }} />
          )}
        </View>
        <Text {...FIXED} numberOfLines={1} adjustsFontSizeToFit style={[type(T, fitSize(word, inner, T, 200, 28), S.ink, 0.95), { paddingHorizontal: GUTTER, marginTop: Space.md }]}>{word}</Text>
      </View>
      <View {...decorative} style={{ height: 10, marginLeft: indent, backgroundColor: P.accent, marginVertical: Space.md }} />
      <View style={{ paddingLeft: GUTTER + indent, paddingRight: GUTTER, paddingBottom: Space.xl, gap: Space.lg }}>
        {track ? <SongText track={track} s={S} ed={ed} width={inner - indent} max={40} /> : null}
        <CoverAction s={S} track={track} state={state} onOpen={onOpen} onSearch={onSearch} />
      </View>
    </View>
  );
}

/** Serif protagonista: palabra en serif enorme, filetes de revista y la frase en la voz de contraste espaciada. */
function CoverSerif({ ed, width, track, state, onOpen, onSearch }: CoverProps) {
  const P = ed.palette;
  const S = P.paper;
  const inner = width - GUTTER * 2;
  const serif = SERIFS.has(ed.trio.title.key) ? ed.trio.title : SERIFS.has(ed.trio.voice.key) ? ed.trio.voice : DM_SERIF_ITALIC;
  const sans = serif === ed.trio.title ? ed.trio.voice : ed.trio.title;
  const word = display(ed.headline.word, serif);
  const voice = fitLines(ed.headline.voice.toUpperCase(), inner * 0.9, sans, 30);
  const cover = Math.round(Math.min(inner * 0.42, 220));
  return (
    <View style={{ backgroundColor: S.bg, paddingHorizontal: GUTTER, paddingTop: Space.lg, paddingBottom: Space.xl }}>
      <View accessible accessibilityRole="header" accessibilityLabel={headlineLabel(ed)}>
        <View {...decorative} style={{ height: 6, backgroundColor: S.ink }} />
        <View style={styles.ruleRow}>
          <Text style={[MONO_B, { color: S.ink }]} numberOfLines={1}>Edición {P.name}</Text>
          <View {...decorative} style={{ width: 14, height: 14, borderRadius: 7, backgroundColor: P.accent }} />
        </View>
        <Text {...FIXED} numberOfLines={1} adjustsFontSizeToFit style={[type(serif, fitSize(word, inner, serif, 210, 28), S.ink, 1.08), { textAlign: 'center' }]}>{word}</Text>
        <View {...decorative} style={{ height: 2, backgroundColor: S.ink, marginTop: Space.sm }} />
        <View {...decorative} style={{ paddingVertical: Space.sm }}>
          {voice.lines.map((l, i) => (
            <Text key={i} {...FIXED} numberOfLines={1} adjustsFontSizeToFit style={[type(sans, voice.size, S.ink, 1.25), { textAlign: 'center' }]}>{l}</Text>
          ))}
        </View>
        <View {...decorative} style={{ height: 2, backgroundColor: S.ink }} />
      </View>
      {track ? (
        <View style={{ flexDirection: 'row', gap: Space.lg, marginTop: Space.xl, alignItems: 'flex-start' }}>
          <View style={{ flex: 1 }}>
            <SongText track={track} s={S} ed={ed} width={inner - cover - Space.lg} max={44} face={serif} />
          </View>
          <CoverPlate uri={track.cover} seed={track.mbid} title={track.title} size={cover} radius={0} border={S.ink} />
        </View>
      ) : null}
      <View style={{ marginTop: Space.xl }}>
        <CoverAction s={S} track={track} state={state} onOpen={onOpen} onSearch={onSearch} />
      </View>
    </View>
  );
}

/** Bloques geométricos: rejilla de superficies de la paleta (palabra, día, portada, frase) y espacio negativo. */
function CoverBlocks({ ed, width, track, state, onOpen, onSearch }: CoverProps) {
  const P = ed.palette;
  const S = P.night;
  const T = ed.trio.title;
  const V = ed.trio.voice;
  const inner = width - GUTTER * 2;
  const g = 6;
  const wide = Math.round((inner - g) * 0.62);
  const narrow = inner - g - wide;
  const half = Math.round((inner - g) / 2);
  const word = display(ed.headline.word, T);
  const day = ed.key.slice(8).replace(/^0/, '');
  const voice = fitLines(display(ed.headline.voice, V), inner - g - half - Space.lg * 2, V, 44);
  return (
    <View style={{ backgroundColor: S.bg, padding: GUTTER, paddingBottom: Space.xl, gap: g }}>
      <View accessible accessibilityRole="header" accessibilityLabel={headlineLabel(ed)} style={{ gap: g }}>
        <View style={{ flexDirection: 'row', gap: g, height: Math.round(inner * 0.46) }}>
          <View style={[styles.block, { width: wide, backgroundColor: P.hero.bg, justifyContent: 'flex-end' }]}>
            <Text {...FIXED} numberOfLines={1} adjustsFontSizeToFit style={type(T, fitSize(word, wide - Space.lg * 2, T, 150, 20), P.hero.ink, 0.95)}>{word}</Text>
          </View>
          <View {...decorative} style={[styles.block, { width: narrow, backgroundColor: P.paper.bg, alignItems: 'center', justifyContent: 'center' }]}>
            <Text {...FIXED} numberOfLines={1} adjustsFontSizeToFit style={type(V, fitSize(day, narrow - Space.lg, V, 110, 30), P.paper.ink, 1.0)}>{day}</Text>
            <Text style={[MONO_B, { color: P.paper.ink }]}>{ed.dateLabel.split(' ').pop()}</Text>
          </View>
        </View>
        <View style={{ flexDirection: 'row', gap: g }}>
          {track ? (
            <CoverPlate uri={track.cover} seed={track.mbid} title={track.title} size={half} radius={0} />
          ) : (
            <View {...decorative} style={{ width: half, height: half, backgroundColor: P.accent }} />
          )}
          <View style={[styles.block, { flex: 1, height: half, backgroundColor: P.alt.bg, justifyContent: 'space-between' }]}>
            <Text style={[MONO_B, { color: P.alt.ink }]} numberOfLines={2}>Edición {P.name}</Text>
            <View {...decorative}>
              {voice.lines.map((l, i) => <Text key={i} {...FIXED} numberOfLines={1} adjustsFontSizeToFit style={type(V, voice.size, P.alt.ink, 1.05)}>{l}</Text>)}
            </View>
          </View>
        </View>
      </View>
      <View style={{ flexDirection: 'row', gap: Space.lg, marginTop: Space.lg, alignItems: 'flex-start' }}>
        {track ? <View style={{ flex: 1 }}><SongText track={track} s={S} ed={ed} width={inner - 48 - Space.lg} max={40} /></View> : <View style={{ flex: 1 }} />}
        <View {...decorative} style={{ width: 48, height: 48, backgroundColor: P.accent }} />
      </View>
      <View style={{ marginTop: Space.md }}>
        <CoverAction s={S} track={track} state={state} onOpen={onOpen} onSearch={onSearch} />
      </View>
    </View>
  );
}

// --- Secciones ---------------------------------------------------------------------------------------------------
/**
 * Isla de color con el encabezado de la edición: banda de tinta, filete editorial o bloque de acento. El encabezado va
 * a cuerpo fijo (HEAD_SIZE; solo encoge si no cabe) en la tipografía titular: no compite con la portada. `width` es
 * el de la isla (ver ISLAND).
 */
export function HomeSection({ ed, s, index, title, intro, width, children }: {
  ed: Edition; s: Surface; index: number; title: string; intro?: string; width: number; children: ReactNode;
}) {
  const inner = width - GUTTER * 2;
  const T = ed.trio.title;
  const num = String(index).padStart(2, '0');
  let head: ReactNode;
  if (ed.head === 'band') {
    const text = display(title, T);
    head = (
      <View style={[styles.bandHead, { backgroundColor: s.ink }]}>
        <Text {...FIXED} accessibilityRole="header" numberOfLines={1} adjustsFontSizeToFit style={[type(T, fitSize(text, inner - 40, T, HEAD_SIZE, 18), s.bg, 1.1), { flex: 1 }]}>{text}</Text>
        <Text {...decorative} style={[MONO_B, { color: s.bg }]}>{num}</Text>
      </View>
    );
  } else if (ed.head === 'rule') {
    const text = display(title, T);
    head = (
      <View style={{ paddingHorizontal: GUTTER, paddingTop: Space.xl, gap: Space.sm }}>
        <View {...decorative} style={{ height: 5, backgroundColor: s.ink }} />
        <Text {...decorative} style={[MONO_B, { color: s.soft }]}>{`Sección ${num}`}</Text>
        <Text {...FIXED} accessibilityRole="header" numberOfLines={1} adjustsFontSizeToFit style={type(T, fitSize(text, inner, T, HEAD_SIZE, 18), s.ink, 1.1)}>{text}</Text>
      </View>
    );
  } else {
    const text = display(title, T);
    const mark = 28;
    head = (
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: Space.md, paddingHorizontal: GUTTER, paddingTop: Space.xl }}>
        <View {...decorative} style={{ width: mark, height: mark, backgroundColor: ed.palette.accent }} />
        <Text {...FIXED} accessibilityRole="header" numberOfLines={1} adjustsFontSizeToFit
          style={[type(T, fitSize(text, inner - mark - Space.md, T, HEAD_SIZE, 18), s.ink, 1.05), { flex: 1 }]}>{text}</Text>
      </View>
    );
  }
  return (
    <View style={[styles.island, { backgroundColor: s.bg }]}>
      {head}
      {intro ? <Text style={[styles.intro, { color: s.ink, paddingHorizontal: GUTTER }]}>{intro}</Text> : null}
      {children}
    </View>
  );
}

/** Líneas de carga con los colores de la superficie (sin saltos de color al llegar los datos). */
function Skeleton({ s, widths }: { s: Surface; widths: `${number}%`[] }) {
  return (
    <View style={{ gap: Space.sm }} accessibilityLabel="Cargando" accessibilityLiveRegion="polite">
      {widths.map((w, i) => <View key={i} style={{ width: w, height: 14, backgroundColor: s.line }} />)}
    </View>
  );
}

/** Dato de una canción: palabra decorativa (por debajo del encabezado de la portada), rótulo y la frase documentada. */
function FactBlock({ fact, s, face, width, heading, subject }: {
  fact: SoundFact; s: Surface; face: Typeface; width: number; heading?: string; subject?: string;
}) {
  const word = display(fact.word, face);
  return (
    <View style={{ gap: Space.sm }}>
      <Text {...decorative} {...FIXED} numberOfLines={1} style={type(face, fitSize(word, width, face, 52, 28), s.ink, 1.05)}>{word}</Text>
      <Text style={[MONO_B, { color: s.soft }]}>{heading ?? fact.kicker}</Text>
      {subject ? <Text style={[styles.artist, { color: s.ink }]} numberOfLines={2}>{subject}</Text> : null}
      <Text style={[styles.factText, { color: s.ink }]}>{fact.text}</Text>
    </View>
  );
}

// --- En el radar ---------------------------------------------------------------------------------------------------
export function RadarBody({ ed, s, width, track, state, meta, fact, onOpen, onRetry }: {
  ed: Edition; s: Surface; width: number; track: Protagonist | null; state: LoadState; meta: string | null;
  fact: SoundFact | null; onOpen: () => void; onRetry: () => void;
}) {
  const inner = width - GUTTER * 2;
  if (!track) {
    return (
      <View style={{ paddingHorizontal: GUTTER, gap: Space.md }}>
        <Text style={[styles.factText, { color: s.ink }]}>Hoy no hemos podido cargar la canción del radar. Suele ser un fallo temporal del servidor o de MusicBrainz.</Text>
        <OpenButton s={s} label="Reintentar" onPress={onRetry} />
      </View>
    );
  }
  const cover = Math.round(Math.min(inner * 0.56, 260));
  const column = inner - cover - Space.lg;
  return (
    <View style={{ paddingHorizontal: GUTTER, gap: HEAD_GAP }}>
      <Pressable onPress={onOpen} disabled={state !== 'ok'} accessibilityRole="button" accessibilityLabel={`${track.title}, ${track.artist}. Abrir en TrackDNA`}
        style={({ pressed }) => [{ flexDirection: 'row', gap: Space.lg, alignItems: 'flex-end' }, pressed && { opacity: 0.85 }]}>
        <CoverPlate uri={track.cover} seed={track.mbid} title={track.title} size={cover} radius={0} />
        <View style={{ width: column, gap: Space.sm }}>
          <FitTitle title={track.title} face={ed.trio.title} voice={ed.trio.voice} width={column} color={s.ink} max={42} min={18} />
          <Text style={[styles.artist, { color: s.ink }]} numberOfLines={2}>{track.artist}</Text>
          {meta ? <Text style={[MONO, { color: s.soft }]}>{meta}</Text> : null}
        </View>
      </Pressable>
      {state === 'loading' ? <Skeleton s={s} widths={['40%', '95%', '70%']} /> : null}
      {fact ? (
        <View style={{ gap: 4 }}>
          <Text style={[MONO_B, { color: s.soft }]}>{fact.kicker}</Text>
          <Text style={[styles.factText, { color: s.ink }]}>{fact.text}</Text>
        </View>
      ) : null}
      <OpenButton s={s} label={ctaLabel(state)} disabled={state !== 'ok'} onPress={onOpen} />
    </View>
  );
}

// --- Tu frecuencia -------------------------------------------------------------------------------------------------
const CARD = 168;

export function FrequencyBody({ s, items, onOpen, onCoverError }: {
  s: Surface; items: FrequencyItem[]; onOpen: (mbid: string) => void; onCoverError?: (url: string) => void;
}) {
  return (
    <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ paddingHorizontal: GUTTER, gap: Space.lg }}>
      {items.map((it) => (
        <Pressable key={it.mbid} onPress={() => onOpen(it.mbid)} accessibilityRole="button"
          accessibilityLabel={`${it.title}, ${it.artist}. ${it.reason}. Abrir en TrackDNA`}
          style={({ pressed }) => [{ width: CARD, gap: Space.sm }, pressed && { opacity: 0.8 }]}>
          <CoverPlate uri={it.cover} seed={it.mbid} title={it.title} size={CARD} radius={0} onFail={onCoverError} />
          <Text numberOfLines={2} style={[styles.reason, it.kind === 'editorial' ? { color: s.ink, borderColor: s.ink, borderWidth: 1.5 } : { color: s.bg, backgroundColor: s.ink }]}>
            {it.reason}
          </Text>
          <Text numberOfLines={2} style={[styles.cardTitle, { color: s.ink }]}>{it.title}</Text>
          <Text numberOfLines={1} style={[styles.cardArtist, { color: s.soft }]}>{it.artist || 'Artista sin datos'}</Text>
        </Pressable>
      ))}
    </ScrollView>
  );
}

// --- Detrás del sonido ---------------------------------------------------------------------------------------------
export function BehindBody({ ed, s, width, fact, personal, onOpen }: {
  ed: Edition; s: Surface; width: number; fact: SoundFact; personal: boolean; onOpen: (mbid: string) => void;
}) {
  const inner = width - GUTTER * 2;
  const links = [{ mbid: fact.track.mbid, title: fact.track.title }, ...(fact.other ? [{ mbid: fact.other.mbid, title: fact.other.title }] : [])];
  return (
    <View style={{ paddingHorizontal: GUTTER, gap: HEAD_GAP }}>
      <FactBlock fact={fact} s={s} face={ed.trio.title} width={inner} heading={personal ? `${fact.kicker} · de tus Guardados` : fact.kicker}
        subject={`«${fact.track.title}» · ${fact.track.artist}`} />
      <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: Space.sm }}>
        {links.map((l) => (
          <Pressable key={l.mbid} onPress={() => onOpen(l.mbid)} accessibilityRole="button" accessibilityLabel={`Abrir ${l.title} en TrackDNA`}
            style={({ pressed }) => [styles.link, { borderColor: s.ink }, pressed && { backgroundColor: s.line }]}>
            <Text numberOfLines={1} style={[styles.linkLabel, { color: s.ink }]}>{`«${l.title}» →`}</Text>
          </Pressable>
        ))}
      </View>
    </View>
  );
}

/** Pie de la edición: su nombre y fecha (sin fuentes ni metadatos, V6.1). */
export function EditionFooter({ ed }: { ed: Edition }) {
  const N = ed.palette.night;
  return (
    <View style={{ backgroundColor: N.bg, padding: GUTTER, paddingBottom: Space.xxxl }}>
      <Text style={[MONO_B, { color: N.soft }]}>Edición {ed.palette.name} · {ed.dateLabel}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  mast: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', gap: Space.md, paddingHorizontal: GUTTER, paddingVertical: Space.md },
  open: { minHeight: 52, flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: Space.md, paddingHorizontal: Space.lg, borderRadius: 2 },
  openLabel: { fontFamily: Fonts.sansBold, fontSize: 17, flexShrink: 1 },
  artist: { fontFamily: Fonts.sansBold, fontSize: 17, lineHeight: 22 },
  band: { position: 'absolute', paddingHorizontal: Space.lg, overflow: 'hidden' },
  ruleRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', paddingVertical: Space.sm },
  block: { padding: Space.lg, overflow: 'hidden' },
  island: { marginHorizontal: ISLAND, marginTop: SECTION_GAP, paddingBottom: Space.xl, gap: HEAD_GAP, borderRadius: 4, overflow: 'hidden' },
  bandHead: { flexDirection: 'row', alignItems: 'center', gap: Space.md, paddingHorizontal: GUTTER, paddingVertical: Space.md },
  intro: { fontFamily: Fonts.sans, fontSize: 16, lineHeight: 24, marginTop: -Space.sm },
  factText: { fontFamily: Fonts.sans, fontSize: 17, lineHeight: 26 },
  reason: { alignSelf: 'flex-start', fontFamily: Fonts.sansBold, fontSize: 12, lineHeight: 16, paddingHorizontal: 6, paddingVertical: 3 },
  cardTitle: { fontFamily: Fonts.sansBold, fontSize: 15, lineHeight: 19 },
  cardArtist: { fontFamily: Fonts.sans, fontSize: 13, lineHeight: 17 },
  link: { borderWidth: 2, paddingHorizontal: Space.md, minHeight: 44, justifyContent: 'center', maxWidth: '100%' },
  linkLabel: { fontFamily: Fonts.sansBold, fontSize: 15 },
});
