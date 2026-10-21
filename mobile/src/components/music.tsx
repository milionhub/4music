/**
 * Componentes de Inicio y de la elección de artistas de partida: buscador de artistas, filas y tarjetas de
 * descubrimiento. Sin fotos de artistas (v5): marca tipográfica con su identidad.
 */
import { type ReactNode, useEffect, useState } from 'react';
import { Pressable, StyleSheet, Text, TextInput, View } from 'react-native';
import Animated, { FadeInDown, ReduceMotion } from 'react-native-reanimated';

import { ArtistMark } from '@/components/editorial';
import { Meta, StateView } from '@/components/ui';
import { C, Fonts, Radius, Space } from '@/constants/theme';
import { artistFacts, withUniqueKeys } from '@/lib/format';
import { describeError } from '@/services/api-client';
import { searchArtists } from '@/services/music';
import type { ArtistRef, ArtistSummary, Recommendation, SearchResult } from '@/types/music';

const SEARCH_DEBOUNCE_MS = 450;

export { artistFacts };

export function ArtistRow({
  artist,
  onPress,
  trailing,
}: {
  artist: ArtistRef & Partial<Pick<ArtistSummary, 'type' | 'country' | 'area'>>;
  onPress?: () => void;
  trailing?: ReactNode;
}) {
  const facts = artistFacts({ type: artist.type ?? null, country: artist.country ?? null, area: artist.area ?? null });
  return (
    <Pressable
      onPress={onPress}
      disabled={!onPress}
      accessibilityRole={onPress ? 'button' : undefined}
      accessibilityLabel={[artist.name, artist.disambiguation, facts].filter(Boolean).join(', ')}
      style={({ pressed }) => [styles.row, pressed && { backgroundColor: C.surfaceHigh }]}>
      <ArtistMark mbid={artist.mbid} name={artist.name} size={44} />
      <View style={{ flex: 1, gap: 2 }}>
        <Text style={styles.rowName} numberOfLines={1}>{artist.name}</Text>
        {artist.disambiguation ? <Text style={styles.rowSub} numberOfLines={2}>{artist.disambiguation}</Text> : null}
        {facts ? <Meta numberOfLines={1}>{facts}</Meta> : null}
      </View>
      {trailing}
    </Pressable>
  );
}

/**
 * Búsqueda real en MusicBrainz (vía backend). Muestra la desambiguación para que el usuario elija
 * explícitamente a qué artista se refiere; nunca se elige el primer resultado automáticamente.
 */
export function ArtistSearch({
  onPick,
  isSelected,
  placeholder = 'Busca un artista o DJ',
  autoFocus,
}: { onPick: (r: SearchResult) => void; isSelected?: (mbid: string) => boolean; placeholder?: string; autoFocus?: boolean }) {
  const [query, setQuery] = useState('');
  const [state, setState] = useState<
    { kind: 'idle' } | { kind: 'loading' } | { kind: 'done'; results: SearchResult[] } | { kind: 'error'; message: string }
  >({ kind: 'idle' });
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    const q = query.trim();
    if (q.length < 2) {
      setState({ kind: 'idle' });
      return;
    }
    let active = true;
    setState({ kind: 'loading' });
    const timer = setTimeout(async () => {
      const result = await searchArtists(q);
      if (!active) return;
      setState(result.ok ? { kind: 'done', results: result.data.results } : { kind: 'error', message: describeError(result.error) });
    }, SEARCH_DEBOUNCE_MS);
    return () => {
      active = false;
      clearTimeout(timer);
    };
  }, [query, attempt]);

  return (
    <View style={{ gap: Space.md }}>
      <TextInput
        value={query}
        onChangeText={setQuery}
        placeholder={placeholder}
        placeholderTextColor={C.faint}
        autoFocus={autoFocus}
        autoCorrect={false}
        autoCapitalize="none"
        returnKeyType="search"
        accessibilityLabel="Buscar artistas en MusicBrainz"
        style={styles.input}
      />
      {state.kind === 'idle' ? <Meta>Escribe al menos 2 letras · Datos de MusicBrainz</Meta> : null}
      {state.kind === 'loading' ? <Meta>Buscando en MusicBrainz…</Meta> : null}
      {state.kind === 'error' ? (
        <StateView kind="error" title="No se pudo buscar" message={state.message} actionLabel="Reintentar" onAction={() => setAttempt((n) => n + 1)} />
      ) : null}
      {state.kind === 'done' && state.results.length === 0 ? (
        <StateView kind="empty" title="Sin resultados" message={`MusicBrainz no tiene artistas para «${query.trim()}». Prueba con otra grafía o con el nombre completo.`} />
      ) : null}
      {state.kind === 'done' && state.results.length > 0 ? (
        <View style={styles.list}>
          {withUniqueKeys(state.results, (r) => r.mbid).map(({ key, item: r }) => {
            const selected = isSelected?.(r.mbid) ?? false;
            return (
              <ArtistRow
                key={key}
                artist={r}
                onPress={() => onPick(r)}
                trailing={isSelected ? <Text style={[styles.pick, selected && styles.pickOn]}>{selected ? '✓' : '+'}</Text> : <Text style={styles.chevron}>→</Text>}
              />
            );
          })}
        </View>
      ) : null}
    </View>
  );
}

const TAG_COLORS: Record<Recommendation['kind'], string> = {
  affinity: C.cyan,
  shared_label: C.acid,
  collaboration: C.orange,
  multiple_favorites: C.magenta,
};

/**
 * Tarjeta de recomendación: nombre con su marca tipográfica, etiqueta según la evidencia real
 * (afinidad, sello, colaboración, varios favoritos) y una sola línea de explicación.
 */
export function RecommendationCardView({
  card,
  index,
  saved,
  onExplore,
  onSave,
  onDiscard,
}: {
  card: Recommendation;
  index: number;
  saved: boolean;
  onExplore: () => void;
  onSave: () => void;
  onDiscard?: () => void;
}) {
  const tagColor = TAG_COLORS[card.kind];
  return (
    <Animated.View
      entering={FadeInDown.delay(Math.min(index, 6) * 50).duration(280).reduceMotion(ReduceMotion.System)}
      style={styles.card}>
      <Pressable onPress={onExplore} accessibilityRole="button" accessibilityLabel={`${card.artist.name}. ${card.tag}: ${card.headline}. Abrir ficha`}
        style={styles.cardMain}>
        <ArtistMark mbid={card.artist.mbid} name={card.artist.name} size={76} />
        <View style={{ flex: 1, gap: 4 }}>
          <Text style={[styles.tag, { color: tagColor, borderColor: tagColor }]}>{card.tag}</Text>
          <Text style={styles.cardName} numberOfLines={2}>{card.artist.name}</Text>
          {card.artist.disambiguation ? <Meta numberOfLines={1}>{card.artist.disambiguation}</Meta> : null}
          <Text style={styles.headline} numberOfLines={2}>{card.headline}</Text>
        </View>
      </Pressable>
      <View style={styles.actions}>
        <CardAction label="Explorar" onPress={onExplore} primary />
        <CardAction label={saved ? '✓ De partida' : '+ De partida'} onPress={onSave} />
        {onDiscard ? <CardAction label="✕ Descartar" onPress={onDiscard} /> : null}
      </View>
    </Animated.View>
  );
}

function CardAction({ label, onPress, primary }: { label: string; onPress: () => void; primary?: boolean }) {
  return (
    <Pressable
      onPress={onPress}
      accessibilityRole="button"
      style={({ pressed }) => [styles.action, primary && { backgroundColor: C.text, borderColor: C.text }, pressed && { opacity: 0.7 }]}>
      <Text style={[styles.actionLabel, primary && { color: C.onAccent }]}>{label}</Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  input: {
    minHeight: 54,
    borderRadius: Radius.md,
    borderWidth: 1.5,
    borderColor: C.line,
    backgroundColor: C.surface,
    color: C.text,
    paddingHorizontal: Space.lg,
    fontSize: 18,
    fontWeight: '600',
  },
  list: { borderRadius: Radius.lg, borderWidth: 1, borderColor: C.line, overflow: 'hidden', backgroundColor: C.bgRaised },
  row: { flexDirection: 'row', alignItems: 'center', gap: Space.md, padding: Space.md, borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: C.line },
  rowName: { color: C.text, fontSize: 17, fontWeight: '800' },
  rowSub: { color: C.muted, fontSize: 14 },
  pick: { width: 36, height: 36, borderRadius: 18, borderWidth: 1.5, borderColor: C.line, textAlign: 'center', lineHeight: 33, color: C.text, fontSize: 20, fontWeight: '800', overflow: 'hidden' },
  pickOn: { backgroundColor: C.acid, borderColor: C.acid, color: C.onAccent },
  chevron: { color: C.faint, fontSize: 20 },
  card: { backgroundColor: C.surface, borderRadius: Radius.lg, borderWidth: 1, borderColor: C.line, padding: Space.md, gap: Space.md },
  cardMain: { flexDirection: 'row', gap: Space.md, alignItems: 'flex-start' },
  tag: { alignSelf: 'flex-start', fontSize: 10, fontWeight: '900', letterSpacing: 1, textTransform: 'uppercase', borderWidth: 1, borderRadius: Radius.pill, paddingHorizontal: Space.sm, paddingVertical: 2, overflow: 'hidden' },
  cardName: { color: C.text, fontFamily: Fonts.display, fontWeight: Fonts.displayWeight ?? '900', fontSize: 24, lineHeight: 26, textTransform: 'uppercase' },
  headline: { color: C.muted, fontSize: 13, lineHeight: 18 },
  actions: { flexDirection: 'row', flexWrap: 'wrap', gap: Space.sm },
  action: { minHeight: 40, paddingHorizontal: Space.lg, borderRadius: Radius.pill, borderWidth: 1.5, borderColor: C.line, justifyContent: 'center' },
  actionLabel: { color: C.text, fontWeight: '800', fontSize: 14 },
});
