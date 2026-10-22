/**
 * Carteles 3.4: vista rápida de artista dentro del evento. Es una hoja superpuesta (no un Modal nativo): al abrir el
 * perfil o TrackDNA la pantalla del evento sigue montada debajo y, al volver, la hoja, los filtros y el scroll siguen
 * igual. Solo datos reales de GET /v1/artists/{mbid}; sin identidad fiable no hay perfil, solo el nombre leído.
 */
import { Image } from 'expo-image';
import { router } from 'expo-router';
import { useEffect, useState } from 'react';
import { ActivityIndicator, BackHandler, Pressable, ScrollView, StyleSheet, Text, TextInput, useWindowDimensions, View } from 'react-native';
import Animated, { FadeIn, FadeOut, ReduceMotion, SlideInDown, SlideOutDown } from 'react-native-reanimated';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { PS } from '@/components/poster';
import { Button, Chip, Meta, Notice } from '@/components/ui';
import { C, Fonts, Radius, Space } from '@/constants/theme';
import { useRemote } from '@/hooks/use-remote';
import { display, fitSize, identityFor } from '@/lib/artist-identity';
import { artistFacts, uniqueBy } from '@/lib/format';
import { linkedMbid } from '@/lib/poster-identity';
import { describeError } from '@/services/api-client';
import { getArtist, searchArtists } from '@/services/music';
import { getPosterArtistTracks } from '@/services/posters';
import type { ArtistProfileResponse } from '@/types/music';
import type { LinkCandidate, PosterArtist, PosterEvent } from '@/types/poster';

const MAX_TRACKS = 5;

export type IdentityAction =
  | { kind: 'choose'; candidate: LinkCandidate }
  | { kind: 'unidentified' }
  | { kind: 'reset' };

export function ArtistQuickView({ event, setId, artistId, resolveError, onSelect, onAction, onRetry, onClose }: {
  event: PosterEvent;
  setId: string | null;
  artistId: string;
  resolveError: string | null;
  onSelect: (artistId: string) => void;
  onAction: (artistId: string, action: IdentityAction) => void;
  onRetry: () => void;
  onClose: () => void;
}) {
  const { height } = useWindowDimensions();
  const insets = useSafeAreaInsets();
  const set = setId ? event.sets.find((s) => s.id === setId) : undefined;
  const artist = event.artists.find((a) => a.id === artistId);
  const members = (set?.artistIds ?? [artistId]).map((id) => event.artists.find((a) => a.id === id)).filter((a): a is PosterArtist => !!a);

  useEffect(() => {
    const sub = BackHandler.addEventListener('hardwareBackPress', () => {
      onClose();
      return true;
    });
    return () => sub.remove();
  }, [onClose]);

  return (
    <View style={StyleSheet.absoluteFill} pointerEvents="box-none">
      <Animated.View entering={FadeIn.duration(180).reduceMotion(ReduceMotion.System)} exiting={FadeOut.duration(160)} style={[StyleSheet.absoluteFill, styles.backdrop]}>
        <Pressable style={{ flex: 1 }} onPress={onClose} accessibilityRole="button" accessibilityLabel="Cerrar vista rápida" />
      </Animated.View>
      <Animated.View entering={SlideInDown.duration(260).reduceMotion(ReduceMotion.System)} exiting={SlideOutDown.duration(200)}
        style={[styles.sheet, { maxHeight: height * 0.88, paddingBottom: insets.bottom + Space.md }]} accessibilityViewIsModal>
        <View style={styles.handle} />
        <View style={styles.head}>
          <Meta>{members.length > 1 ? `Actuación conjunta · ${set?.connector ?? 'B2B'}` : 'Artista del cartel'}</Meta>
          <Pressable onPress={onClose} accessibilityRole="button" accessibilityLabel="Cerrar" hitSlop={12}><Text style={styles.close}>✕</Text></Pressable>
        </View>
        {members.length > 1 ? (
          <View style={styles.chips}>
            {members.map((m) => <Chip key={m.id} label={m.name} selected={m.id === artistId} onPress={() => onSelect(m.id)} />)}
          </View>
        ) : null}
        <ScrollView contentContainerStyle={{ gap: Space.lg, paddingTop: Space.md }} keyboardShouldPersistTaps="handled">
          {artist ? (
            <ArtistBody key={`${artist.id}:${artist.link.status}:${artist.link.refId}`} artist={artist} resolveError={resolveError}
              onAction={(a) => onAction(artist.id, a)} onRetry={onRetry} />
          ) : <Notice tone="warn">Este artista ya no está en el evento.</Notice>}
        </ScrollView>
      </Animated.View>
    </View>
  );
}

function ArtistBody({ artist, resolveError, onAction, onRetry }: {
  artist: PosterArtist; resolveError: string | null; onAction: (a: IdentityAction) => void; onRetry: () => void;
}) {
  const [picking, setPicking] = useState(false);
  const mbid = linkedMbid(artist);
  const printed = artist.meta.printed && artist.meta.printed !== artist.name ? artist.meta.printed : null;

  if (artist.link.status === 'pending') {
    return (
      <View style={{ gap: Space.md }}>
        <Text style={styles.name}>{artist.name}</Text>
        {resolveError ? (
          <>
            <Notice tone="warn">{resolveError}</Notice>
            <Button label="Reintentar" onPress={onRetry} />
          </>
        ) : (
          <View style={styles.row} accessibilityLiveRegion="polite">
            <ActivityIndicator color={C.acid} />
            <Meta>Buscando su identidad en MusicBrainz…</Meta>
          </View>
        )}
      </View>
    );
  }
  if (mbid && !picking) return <LinkedArtist artist={artist} mbid={mbid} printed={printed} onWrong={() => setPicking(true)} />;
  return <IdentityPicker artist={artist} printed={printed} onAction={onAction} onCancel={mbid ? () => setPicking(false) : undefined} />;
}

/** Artista enlazado: identidad, estilos y descripción documentados, 3–5 canciones reales y acceso al perfil. */
function LinkedArtist({ artist, mbid, printed, onWrong }: { artist: PosterArtist; mbid: string; printed: string | null; onWrong: () => void }) {
  const { state, reload } = useRemote(`poster-artist:${mbid}`, () => getArtist(mbid));
  const data = state.status === 'success' ? state.data : state.status === 'loading' ? state.previous : null;
  const name = data?.artist.name ?? artist.link.name ?? artist.name;
  return (
    <View style={{ gap: Space.lg }}>
      <Hero mbid={mbid} name={name} data={data} />
      <View style={{ gap: Space.xs }}>
        {data ? <Meta>{artistFacts(data.artist) || 'Artista'}</Meta> : null}
        {printed || normalizedDiffers(artist.name, name) ? <Meta>En el cartel: «{printed ?? artist.name}»</Meta> : null}
        {artist.link.evidence ? <Meta style={{ color: C.cyan }}>{artist.link.evidence}</Meta> : null}
      </View>
      {state.status === 'error' && !data ? (
        <View style={{ gap: Space.sm }}>
          <Notice tone="warn">No se pudo cargar su ficha: {describeError(state.error)}</Notice>
          <Button label="Reintentar" variant="ghost" onPress={reload} />
        </View>
      ) : !data ? (
        <View style={styles.row}><ActivityIndicator color={C.acid} /><Meta>Cargando su ficha…</Meta></View>
      ) : (
        <>
          {data.styles.length ? (
            <View style={styles.chips}>
              {[...new Set(data.styles.map((s) => s.label.replace(/^música /i, '')))].slice(0, 4).map((s) => <Chip key={s} label={s} />)}
            </View>
          ) : null}
          {data.bio ? <Text style={styles.bio} numberOfLines={5}>{data.bio.text}</Text> : null}
          <Tracks data={data} />
        </>
      )}
      <View style={{ gap: Space.sm }}>
        <Button label="Perfil completo" onPress={() => router.push(`/artist/${mbid}`)} />
        <Button label="No es este artista" variant="ghost" onPress={onWrong} />
      </View>
    </View>
  );
}

const normalizedDiffers = (a: string, b: string) => a.trim().toLowerCase() !== b.trim().toLowerCase();

/** Foto real solo si el perfil la trae con licencia (Commons/editorial); si no, el cartel tipográfico del artista. */
function Hero({ mbid, name, data }: { mbid: string; name: string; data: ArtistProfileResponse | null }) {
  const { width } = useWindowDimensions();
  const id = identityFor(mbid);
  const [failed, setFailed] = useState(false);
  const image = data?.image && !failed ? data.image : null;
  const box = Math.min(width, 640) - Space.lg * 2;
  return (
    <View style={{ gap: Space.xs }}>
      <View style={[styles.hero, { backgroundColor: id.palette.bg }]}>
        {image ? (
          <Image source={{ uri: image.url }} style={StyleSheet.absoluteFill} contentFit="cover" onError={() => setFailed(true)}
            accessibilityLabel={`Foto de ${name}`} />
        ) : (
          <View style={[styles.heroBand, { backgroundColor: id.palette.pop }]} />
        )}
        <Text numberOfLines={2} adjustsFontSizeToFit
          style={[styles.heroName, image ? styles.heroNameOnPhoto : null, {
            color: image ? C.text : id.palette.ink, fontFamily: id.type.family, fontSize: fitSize(name, box - Space.lg * 2, id.type, 46, 24),
            letterSpacing: id.type.tracking,
          }]}>
          {display(name, id.type)}
        </Text>
      </View>
      {image ? <Meta numberOfLines={1}>Foto: {[image.author, image.license].filter(Boolean).join(' · ')}</Meta> : null}
    </View>
  );
}

type TrackItem = { id: string; title: string; reason: string };

/** Hasta 5 canciones con MBID de grabación (abren TrackDNA): las más escuchadas si hay datos de ListenBrainz y, si no,
 *  las propias documentadas por fecha. Nunca se rellena hasta cinco. */
function Tracks({ data }: { data: ArtistProfileResponse }) {
  const mbid = data.artist.mbid;
  const top = uniqueBy(data.top_tracks, (t) => t.recording_mbid).slice(0, MAX_TRACKS);
  const fallback = useRemote(top.length ? null : `poster-tracks:${mbid}`, () => getPosterArtistTracks(mbid));
  let items: TrackItem[] = top.map((t) => ({ id: t.recording_mbid, title: t.title, reason: 'Más escuchada · ListenBrainz' }));
  let title = 'Canciones destacadas';
  if (!top.length) {
    title = 'Su música, por fecha';
    const tracks = fallback.state.status === 'success' ? fallback.state.data.tracks : [];
    items = tracks.slice(0, MAX_TRACKS).map((t) => ({
      id: t.recording_mbid, title: t.title,
      reason: t.first_release_date ? `Publicada en ${t.first_release_date.slice(0, 4)} · MusicBrainz` : 'MusicBrainz',
    }));
  }
  const loading = !top.length && (fallback.state.status === 'loading' || fallback.state.status === 'idle');
  return (
    <View style={{ gap: Space.sm }}>
      <Text style={styles.section}>{title}</Text>
      {loading ? <View style={styles.row}><ActivityIndicator color={C.acid} /><Meta>Buscando sus canciones…</Meta></View> : null}
      {fallback.state.status === 'error' ? (
        <Notice tone="warn">
          No se pudieron cargar sus canciones.
          <Text style={styles.inline} onPress={fallback.reload} accessibilityRole="button">{'  '}Reintentar</Text>
        </Notice>
      ) : null}
      {!loading && fallback.state.status !== 'error' && !items.length ? <Meta>Sin canciones documentadas en MusicBrainz para este artista.</Meta> : null}
      {items.map((t, i) => (
        <Pressable key={t.id} onPress={() => router.push(`/track/${t.id}`)} accessibilityRole="button"
          accessibilityLabel={`${t.title}. ${t.reason}. Abrir en TrackDNA`}
          style={({ pressed }) => [styles.track, pressed && { opacity: 0.75 }]}>
          <Text style={styles.trackIndex}>{String(i + 1).padStart(2, '0')}</Text>
          <View style={{ flex: 1, gap: 2 }}>
            <Text style={styles.trackTitle} numberOfLines={2}>{t.title}</Text>
            <Meta numberOfLines={1}>{t.reason}</Meta>
          </View>
          <Text style={styles.trackGo}>DNA →</Text>
        </Pressable>
      ))}
    </View>
  );
}

const MATCH_LABEL: Record<NonNullable<LinkCandidate['match']>, string> = {
  name: 'Mismo nombre', alias: 'Alias en MusicBrainz', similar: 'Nombre parecido', manual: 'Búsqueda',
};

/** Sin identidad fiable: candidatos con su desambiguación, búsqueda manual y la opción de dejarlo sin identificar. */
function IdentityPicker({ artist, printed, onAction, onCancel }: {
  artist: PosterArtist; printed: string | null; onAction: (a: IdentityAction) => void; onCancel?: () => void;
}) {
  const [query, setQuery] = useState(artist.name);
  const [search, setSearch] = useState<string | null>(null);
  const results = useRemote(search, () => searchArtists(search ?? ''));
  const link = artist.link;
  const candidates = link.candidates ?? [];
  const similarOnly = candidates.length > 0 && candidates.every((c) => c.match === 'similar');
  const userNone = link.status === 'none' && link.origin === 'user';
  const found: LinkCandidate[] = results.state.status === 'success'
    ? results.state.data.results.map((r) => ({ refId: r.mbid, name: r.name, disambiguation: r.disambiguation, country: r.country, type: r.type, match: 'manual' }))
    : [];

  return (
    <View style={{ gap: Space.lg }}>
      <View style={{ gap: Space.xs }}>
        <Text style={styles.name}>{artist.name}</Text>
        {printed ? <Meta>En el cartel: «{printed}»</Meta> : null}
        <Notice tone={link.status === 'ambiguous' ? 'info' : 'warn'}>
          {onCancel ? 'Elige la identidad correcta o déjalo sin identificar.'
            : userNone ? 'Lo dejaste sin identificar: sigue en el line-up, sin perfil.'
              : link.status === 'ambiguous' ? 'Hay varios artistas con este nombre. Elige el correcto: no se enlaza ninguno por defecto.'
                : 'Sin identidad fiable en MusicBrainz: no se muestra ningún perfil para no confundirlo con otro artista.'}
        </Notice>
        {link.evidence && !userNone ? <Meta>{link.evidence}</Meta> : null}
      </View>

      {candidates.length ? (
        <View style={{ gap: Space.sm }}>
          <Text style={styles.section}>{similarOnly ? '¿Quizá…?' : 'Candidatos'}</Text>
          {similarOnly ? <Meta>Nombres parecidos en MusicBrainz: puede ser una errata del cartel. El nombre impreso no se cambia.</Meta> : null}
          {candidates.map((c) => <CandidateRow key={c.refId} c={c} chosen={link.refId === c.refId} onPress={() => onAction({ kind: 'choose', candidate: c })} />)}
        </View>
      ) : null}

      <View style={{ gap: Space.sm }}>
        <Text style={styles.section}>Buscar en MusicBrainz</Text>
        <View style={styles.row}>
          <TextInput value={query} onChangeText={setQuery} onSubmitEditing={() => query.trim() && setSearch(query.trim())} returnKeyType="search"
            placeholder="Nombre del artista" placeholderTextColor={C.faint} accessibilityLabel="Buscar artista en MusicBrainz" style={[styles.input, { flex: 1 }]} />
          <Button label="Buscar" variant="ghost" onPress={() => query.trim() && setSearch(query.trim())} />
        </View>
        {results.state.status === 'loading' ? <View style={styles.row}><ActivityIndicator color={C.acid} /><Meta>Buscando…</Meta></View> : null}
        {results.state.status === 'error' ? <Notice tone="warn">{describeError(results.state.error)}</Notice> : null}
        {results.state.status === 'success' && !found.length ? <Meta>Sin resultados.</Meta> : null}
        {found.map((c) => <CandidateRow key={c.refId} c={c} chosen={link.refId === c.refId} onPress={() => onAction({ kind: 'choose', candidate: c })} />)}
      </View>

      <View style={{ gap: Space.sm }}>
        {onCancel ? <Button label="Mantener la identidad actual" variant="ghost" onPress={onCancel} /> : null}
        {!userNone ? <Button label="Dejar sin identificar" variant="ghost" onPress={() => onAction({ kind: 'unidentified' })} /> : null}
        {link.origin === 'user' ? <Button label="Volver a la identificación automática" variant="ghost" onPress={() => onAction({ kind: 'reset' })} /> : null}
      </View>
    </View>
  );
}

function CandidateRow({ c, chosen, onPress }: { c: LinkCandidate; chosen: boolean; onPress: () => void }) {
  const facts = [c.disambiguation, c.type, c.country].filter(Boolean).join(' · ');
  return (
    <Pressable onPress={onPress} accessibilityRole="button" accessibilityState={{ selected: chosen }}
      accessibilityLabel={`Elegir ${c.name}${facts ? `, ${facts}` : ''}`}
      style={({ pressed }) => [styles.candidate, chosen && { borderColor: C.acid }, pressed && { opacity: 0.75 }]}>
      <View style={{ flex: 1, gap: 2 }}>
        <Text style={styles.trackTitle}>{c.name}</Text>
        {facts ? <Meta numberOfLines={2}>{facts}</Meta> : <Meta>Sin desambiguación en MusicBrainz</Meta>}
        <Text style={styles.badge}>{[c.match ? MATCH_LABEL[c.match] : null, c.scene ? 'Escena electrónica' : null].filter(Boolean).join(' · ')}</Text>
      </View>
      <Text style={styles.trackGo}>{chosen ? '✓' : 'Elegir'}</Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  backdrop: { backgroundColor: 'rgba(7,6,11,0.72)' },
  sheet: { position: 'absolute', left: 0, right: 0, bottom: 0, paddingHorizontal: Space.lg, backgroundColor: PS.screen,
    borderTopLeftRadius: Radius.lg, borderTopRightRadius: Radius.lg, borderTopWidth: 2, borderColor: PS.line },
  handle: { alignSelf: 'center', width: 44, height: 4, borderRadius: 2, backgroundColor: PS.line, marginTop: Space.sm },
  head: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', paddingTop: Space.md },
  close: { color: C.text, fontSize: 22 },
  chips: { flexDirection: 'row', flexWrap: 'wrap', gap: Space.sm, paddingTop: Space.sm },
  row: { flexDirection: 'row', alignItems: 'center', gap: Space.md },
  name: { color: C.text, fontFamily: Fonts.display, fontSize: 32, lineHeight: 36, textTransform: 'uppercase' },
  hero: { height: 168, borderRadius: Radius.md, overflow: 'hidden', justifyContent: 'flex-end', padding: Space.lg },
  heroBand: { position: 'absolute', top: Space.lg, right: -Space.xl, width: '55%', height: 26, transform: [{ rotate: '-8deg' }] },
  heroName: { includeFontPadding: false },
  heroNameOnPhoto: { textShadowColor: 'rgba(0,0,0,0.85)', textShadowRadius: 10, textShadowOffset: { width: 0, height: 1 } },
  bio: { color: C.text, fontFamily: Fonts.sans, fontSize: 15, lineHeight: 22 },
  section: { color: C.text, fontFamily: Fonts.monoBold, fontSize: 12, letterSpacing: 1.4, textTransform: 'uppercase' },
  inline: { color: C.acid, fontWeight: '800' },
  track: { flexDirection: 'row', alignItems: 'center', gap: Space.md, minHeight: 56, padding: Space.md, borderRadius: Radius.md,
    borderWidth: 1, borderColor: PS.line, backgroundColor: PS.raised },
  trackIndex: { color: C.acid, fontFamily: Fonts.display, fontSize: 22, width: 30 },
  trackTitle: { color: C.text, fontFamily: Fonts.sansBold, fontSize: 16, lineHeight: 21 },
  trackGo: { color: C.cyan, fontFamily: Fonts.monoBold, fontSize: 12 },
  candidate: { flexDirection: 'row', alignItems: 'center', gap: Space.md, padding: Space.md, borderRadius: Radius.md,
    borderWidth: 1.5, borderColor: PS.line, backgroundColor: PS.raised },
  badge: { color: C.cyan, fontFamily: Fonts.mono, fontSize: 11 },
  input: { minHeight: 48, borderWidth: 1.5, borderColor: C.line, borderRadius: Radius.md, backgroundColor: C.surface, color: C.text,
    fontFamily: Fonts.sans, fontSize: 16, paddingHorizontal: Space.md },
});
