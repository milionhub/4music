/**
 * TrackDNA: buscador de canciones y navegación a fichas y perfiles. Las piezas de la ficha viven en
 * components/track-art.tsx (dirección artística V5.3).
 */
import { router } from 'expo-router';
import { useEffect, useState } from 'react';
import { Pressable, StyleSheet, Text, TextInput, View } from 'react-native';
import Animated, { FadeInDown, ReduceMotion } from 'react-native-reanimated';

import { CoverPlate, decorative, EmptyPoster, Kicker, TagPill } from '@/components/editorial';
import { StateView } from '@/components/ui';
import { C, Fonts, Radius, Space } from '@/constants/theme';
import { alpha, type ArtistIdentity, identityFor, surfaces } from '@/lib/artist-identity';
import { trackFacts, withUniqueKeys } from '@/lib/format';
import { describeError } from '@/services/api-client';
import { searchTracks } from '@/services/music';
import type { TrackSearchResult } from '@/types/music';

const SEARCH_DEBOUNCE_MS = 500;
/** Búsquedas reales de canciones concretas (ejecutan la búsqueda; no abren fichas). */
const SUGGESTIONS = [
  { title: 'Dirty Cash', artist: 'PAWSA', query: 'PAWSA Dirty Cash' },
  { title: 'Desire', artist: 'Chris Stussy', query: 'Chris Stussy Desire' },
  { title: 'Crazy', artist: 'ANOTR', query: 'ANOTR Crazy' },
];

export function openTrack(mbid: string) {
  router.push({ pathname: '/track/[mbid]', params: { mbid } });
}

export function openArtist(mbid: string) {
  router.push({ pathname: '/artist/[mbid]', params: { mbid } });
}

// --- Búsqueda -----------------------------------------------------------------------------------------------------
export function TrackSearch({ id }: { id: ArtistIdentity }) {
  const P = id.palette;
  const S = surfaces(P);
  const [query, setQuery] = useState('');
  // Respuesta de la última búsqueda, con la consulta (y el intento) a los que corresponde: idle y «buscando» se
  // derivan de ella, sin estados intermedios escritos desde el efecto.
  const [answer, setAnswer] = useState<{ key: string } & ({ kind: 'done'; results: TrackSearchResult[] } | { kind: 'error'; message: string }) | null>(null);
  const [attempt, setAttempt] = useState(0);
  const q = query.trim();
  const key = `${attempt}:${q}`;
  const state = q.length < 2 ? { kind: 'idle' as const } : answer?.key === key ? answer : { kind: 'loading' as const };

  useEffect(() => {
    if (q.length < 2) return;
    let active = true;
    const timer = setTimeout(async () => {
      const result = await searchTracks(q);
      if (!active) return;
      setAnswer(result.ok ? { key, kind: 'done', results: result.data.results } : { key, kind: 'error', message: describeError(result.error) });
    }, SEARCH_DEBOUNCE_MS);
    return () => {
      active = false;
      clearTimeout(timer);
    };
  }, [q, key]);

  return (
    <View style={{ gap: Space.lg }}>
      <View style={[styles.inputWrap, { borderColor: P.glow, backgroundColor: S.raised }]}>
        <Text style={[styles.inputGlyph, { color: P.glow }]} {...decorative}>⌕</Text>
        <TextInput
          value={query}
          onChangeText={setQuery}
          placeholder="Título, o artista y título"
          placeholderTextColor={C.faint}
          autoCorrect={false}
          autoCapitalize="none"
          returnKeyType="search"
          accessibilityLabel="Buscar canciones por título o artista"
          style={styles.input}
        />
        {state.kind === 'loading' ? <Text style={[styles.searching, { color: P.glow }]}>···</Text> : null}
        {query ? (
          <Pressable onPress={() => setQuery('')} accessibilityRole="button" accessibilityLabel="Borrar búsqueda" hitSlop={10}>
            <Text style={styles.clear}>✕</Text>
          </Pressable>
        ) : null}
      </View>

      {state.kind === 'idle' ? (
        <View style={{ gap: Space.sm }}>
          <Kicker>Prueba con</Kicker>
          {SUGGESTIONS.map((s) => (
            <Pressable key={s.query} onPress={() => setQuery(s.query)} accessibilityRole="button" accessibilityLabel={`Buscar ${s.title}, de ${s.artist}`}
              style={({ pressed }) => [styles.suggestion, { borderBottomColor: S.line }, pressed && { opacity: 0.7 }]}>
              <Text style={styles.suggestionTitle} numberOfLines={1}>{s.title}</Text>
              <Text style={[styles.suggestionArtist, { color: P.glow }]} numberOfLines={1}>{s.artist}</Text>
              <Text style={[styles.chevron, { color: P.glow }]}>↗</Text>
            </Pressable>
          ))}
        </View>
      ) : null}
      {state.kind === 'loading' ? <SearchSkeleton id={id} /> : null}
      {state.kind === 'error' ? (
        <StateView kind="error" title="No se pudo buscar" message={state.message} actionLabel="Reintentar" onAction={() => setAttempt((n) => n + 1)} />
      ) : null}
      {state.kind === 'done' && state.results.length === 0 ? (
        <EmptyPoster id={id} glyph="?" title="Sin resultados" message={`No encontramos canciones para «${q}». Prueba con el artista y el título, o revisa la grafía.`} />
      ) : null}
      {state.kind === 'done' && state.results.length > 0 ? (
        <View>
          {withUniqueKeys(state.results, (r) => r.mbid).map(({ key: k, item }, i) => (
            <TrackResultRow key={k} item={item} index={i} line={S.line} />
          ))}
        </View>
      ) : null}
    </View>
  );
}

function SearchSkeleton({ id }: { id: ArtistIdentity }) {
  const S = surfaces(id.palette);
  return (
    <View style={{ gap: Space.md }} accessibilityLabel="Buscando canciones" accessibilityLiveRegion="polite">
      {[0, 1, 2].map((i) => (
        <View key={i} style={{ flexDirection: 'row', gap: Space.md, alignItems: 'center' }}>
          <View style={{ width: 60, height: 60, borderRadius: Radius.sm, backgroundColor: S.raised }} />
          <View style={{ flex: 1, gap: 8 }}>
            <View style={{ height: 15, width: '70%', borderRadius: 4, backgroundColor: S.raised }} />
            <View style={{ height: 11, width: '45%', borderRadius: 4, backgroundColor: S.raised }} />
          </View>
        </View>
      ))}
    </View>
  );
}

function TrackResultRow({ item, index, line }: { item: TrackSearchResult; index: number; line: string }) {
  const P = identityFor(item.mbid).palette;
  const facts = trackFacts({ first_release_date: item.first_release_date, length_ms: item.length_ms });
  return (
    <Animated.View entering={FadeInDown.delay(Math.min(index, 6) * 35).duration(220).reduceMotion(ReduceMotion.System)}>
      <Pressable
        onPress={() => openTrack(item.mbid)}
        accessibilityRole="button"
        accessibilityLabel={[item.title, item.artist_name, item.version, facts].filter(Boolean).join(', ')}
        style={({ pressed }) => [styles.result, { borderBottomColor: line }, pressed && { backgroundColor: alpha(P.glow, 0.08) }]}>
        <CoverPlate uri={item.cover_url} seed={item.mbid} title={item.title} size={60} />
        <View style={{ flex: 1, gap: 3 }}>
          <Text style={styles.resultTitle} numberOfLines={2}>{item.title}</Text>
          <Text style={styles.resultArtist} numberOfLines={1}>
            {item.artist_name}
            {item.artist_disambiguation ? <Text style={{ color: C.faint, fontFamily: Fonts.sans }}>{`  ·  ${item.artist_disambiguation}`}</Text> : null}
          </Text>
          <View style={styles.resultMeta}>
            {item.version ? <TagPill label={item.version} color={P.glow} ink={P.onGlow} /> : null}
            {facts ? <Text style={styles.mono} numberOfLines={1}>{facts}</Text> : null}
          </View>
        </View>
        <Text style={[styles.chevron, { color: P.glow }]}>→</Text>
      </Pressable>
    </Animated.View>
  );
}

const styles = StyleSheet.create({
  inputWrap: { minHeight: 62, flexDirection: 'row', alignItems: 'center', gap: Space.sm, paddingHorizontal: Space.lg, borderRadius: Radius.md, borderWidth: 2 },
  inputGlyph: { fontSize: 26, fontWeight: '800' },
  input: { flex: 1, color: C.text, fontFamily: Fonts.sansBold, fontSize: 18, paddingVertical: Space.md },
  searching: { fontFamily: Fonts.monoBold, fontSize: 16 },
  clear: { color: C.faint, fontSize: 16, fontWeight: '800', padding: Space.xs },
  suggestion: { flexDirection: 'row', alignItems: 'baseline', gap: Space.md, paddingVertical: Space.sm, borderBottomWidth: StyleSheet.hairlineWidth },
  suggestionTitle: { color: C.text, fontFamily: Fonts.serifItalic, fontSize: 26, lineHeight: 32, flexShrink: 1 },
  suggestionArtist: { flex: 1, fontFamily: Fonts.monoBold, fontSize: 11, letterSpacing: 1.2, textTransform: 'uppercase' },
  result: { flexDirection: 'row', alignItems: 'center', gap: Space.md, paddingVertical: Space.md, borderBottomWidth: StyleSheet.hairlineWidth },
  resultTitle: { color: C.text, fontFamily: Fonts.sansBold, fontSize: 17, lineHeight: 22 },
  resultArtist: { color: C.muted, fontFamily: Fonts.sansBold, fontSize: 14 },
  resultMeta: { flexDirection: 'row', alignItems: 'center', gap: Space.sm, flexWrap: 'wrap' },
  mono: { color: C.faint, fontFamily: Fonts.mono, fontSize: 11, letterSpacing: 0.3 },
  chevron: { fontSize: 20, fontWeight: '800' },
});
