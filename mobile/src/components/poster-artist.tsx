/**
 * Carteles 3.4–3.5: vista rápida de artista dentro del evento. Es una hoja superpuesta (no un Modal nativo): al abrir
 * el perfil o TrackDNA la pantalla del evento sigue montada debajo y, al volver, la hoja, los filtros y el scroll
 * siguen igual. Solo datos reales de GET /v1/artists/{mbid}; sin identidad fiable no hay perfil, solo el nombre leído.
 *
 * 3.5B (Artist Spotlight): foto (solo con derechos verificables; si no, el cartel tipográfico), estilos documentados,
 * «Sobre el artista» (lib/poster-quick.ts: texto existente, nunca redactado al abrir) y «Explorar perfil y música».
 * Canciones y lanzamientos, solo en el perfil completo. Colores de la paleta del evento.
 *
 * 3.5C: los créditos (foto y texto) están completos tras el botón ⓘ «Fuentes y créditos». La animación de entrada va
 * en un marco de tamaño fijo (de la zona segura superior al borde inferior) y la tarjeta interior, sin animación de
 * layout, se ajusta al contenido: si la ficha llega durante la animación (caché caliente al reabrir), la hoja ya no
 * se queda con la altura que tenía al empezar a animarse.
 */
import { Image } from 'expo-image';
import { router, useFocusEffect } from 'expo-router';
import { openBrowserAsync } from 'expo-web-browser';
import { useCallback, useEffect, useState } from 'react';
import { ActivityIndicator, BackHandler, Pressable, ScrollView, StyleSheet, Text, TextInput, useWindowDimensions, View } from 'react-native';
import Animated, { FadeIn, FadeOut, ReduceMotion, SlideInDown, SlideOutDown } from 'react-native-reanimated';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { Button, Chip, Meta, Notice } from '@/components/ui';
import { C, Fonts, Radius, Space } from '@/constants/theme';
import { useRemote } from '@/hooks/use-remote';
import { display, fitSize, identityFor } from '@/lib/artist-identity';
import type { EventArt } from '@/lib/poster-art';
import { linkedMbid } from '@/lib/poster-identity';
import { artistSpotlight, type PhotoInfo, type Spotlight, spotlightCredits, verifiablePhoto } from '@/lib/poster-quick';
import { describeError } from '@/services/api-client';
import { getArtist, searchArtists } from '@/services/music';
import type { LinkCandidate, PosterArtist, PosterEvent } from '@/types/poster';

export type IdentityAction =
  | { kind: 'choose'; candidate: LinkCandidate }
  | { kind: 'unidentified' }
  | { kind: 'reset' };

type Ctx = { art: EventArt };

export function ArtistQuickView({ event, setId, artistId, resolveError, art, onSelect, onAction, onStyles, onRetry, onClose }: {
  event: PosterEvent;
  setId: string | null;
  artistId: string;
  resolveError: string | null;
  art: EventArt;
  onSelect: (artistId: string) => void;
  onAction: (artistId: string, action: IdentityAction) => void;
  onStyles: (artistId: string, mbid: string, styles: string[]) => void;
  onRetry: () => void;
  onClose: () => void;
}) {
  const insets = useSafeAreaInsets();
  const set = setId ? event.sets.find((s) => s.id === setId) : undefined;
  const artist = event.artists.find((a) => a.id === artistId);
  const members = (set?.artistIds ?? [artistId]).map((id) => event.artists.find((a) => a.id === id)).filter((a): a is PosterArtist => !!a);
  const S = art.surfaces;

  // Atrás en Android cierra la hoja solo con el evento en primer plano: con el perfil o TrackDNA encima, vuelve atrás.
  useFocusEffect(useCallback(() => {
    const sub = BackHandler.addEventListener('hardwareBackPress', () => {
      onClose();
      return true;
    });
    return () => sub.remove();
  }, [onClose]));

  return (
    <View style={StyleSheet.absoluteFill} pointerEvents="box-none">
      <Animated.View entering={FadeIn.duration(180).reduceMotion(ReduceMotion.System)} exiting={FadeOut.duration(160)} style={[StyleSheet.absoluteFill, styles.backdrop]}>
        <Pressable style={{ flex: 1 }} onPress={onClose} accessibilityRole="button" accessibilityLabel="Cerrar vista rápida" />
      </Animated.View>
      {/* Marco fijo (nunca cambia de tamaño) para la animación; la tarjeta crece dentro hasta el 100 % y luego desplaza. */}
      <Animated.View entering={SlideInDown.duration(260).reduceMotion(ReduceMotion.System)} exiting={SlideOutDown.duration(200)}
        style={[styles.frame, { top: insets.top + Space.xl }]} pointerEvents="box-none">
        <View style={[styles.sheet, { paddingBottom: insets.bottom + Space.md, backgroundColor: S.screen, borderColor: art.palette.glow }]}
          accessibilityViewIsModal>
          <View style={[styles.handle, { backgroundColor: S.line }]} />
          <View style={styles.head}>
            <Text style={[styles.kicker, { color: art.palette.glow }]}>
              {members.length > 1 ? `${set?.connector ?? 'B2B'} · actuación conjunta` : 'En el cartel'}
            </Text>
            <Pressable onPress={onClose} accessibilityRole="button" accessibilityLabel="Cerrar" hitSlop={12}
              style={[styles.closeBtn, { borderColor: S.line }]}>
              <Text style={styles.close}>✕</Text>
            </Pressable>
          </View>
          {members.length > 1 ? (
            <View style={styles.tabs} accessibilityRole="tablist">
              {members.map((m) => {
                const on = m.id === artistId;
                return (
                  <Pressable key={m.id} onPress={() => onSelect(m.id)} accessibilityRole="tab" accessibilityState={{ selected: on }}
                    style={[styles.tab, { borderColor: on ? art.palette.glow : S.line, backgroundColor: on ? art.palette.glow : S.raised }]}>
                    <Text style={[styles.tabLabel, { color: on ? art.palette.onGlow : C.text }]} numberOfLines={1}>{m.name}</Text>
                  </Pressable>
                );
              })}
            </View>
          ) : null}
          <ScrollView key={artistId} style={styles.scroll} contentContainerStyle={{ gap: Space.lg, paddingTop: Space.md }} keyboardShouldPersistTaps="handled">
            {artist ? (
              <ArtistBody key={`${artist.id}:${artist.link.status}:${artist.link.refId}`} artist={artist} resolveError={resolveError} art={art}
                onAction={(a) => onAction(artist.id, a)} onStyles={(mbid, st) => onStyles(artist.id, mbid, st)} onRetry={onRetry} />
            ) : <Notice tone="warn">Este artista ya no está en el evento.</Notice>}
          </ScrollView>
        </View>
      </Animated.View>
    </View>
  );
}

function ArtistBody({ artist, resolveError, art, onAction, onStyles, onRetry }: Ctx & {
  artist: PosterArtist; resolveError: string | null; onAction: (a: IdentityAction) => void;
  onStyles: (mbid: string, styles: string[]) => void; onRetry: () => void;
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
            <ActivityIndicator color={art.palette.glow} />
            <Meta>Buscando su identidad en MusicBrainz…</Meta>
          </View>
        )}
      </View>
    );
  }
  if (mbid && !picking) return <LinkedArtist artist={artist} mbid={mbid} printed={printed} art={art} onStyles={onStyles} onWrong={() => setPicking(true)} />;
  return <IdentityPicker artist={artist} printed={printed} art={art} onAction={onAction} onCancel={mbid ? () => setPicking(false) : undefined} />;
}

/** Artista enlazado: foto o cartel, estilos, «Sobre el artista» y acceso al perfil completo (con su música). */
function LinkedArtist({ artist, mbid, printed, art, onStyles, onWrong }: Ctx & {
  artist: PosterArtist; mbid: string; printed: string | null; onStyles: (mbid: string, styles: string[]) => void; onWrong: () => void;
}) {
  const { state, reload } = useRemote(`poster-artist:${mbid}`, () => getArtist(mbid));
  const data = state.status === 'success' ? state.data : state.status === 'loading' ? state.previous : null;
  const name = data?.artist.name ?? artist.link.name ?? artist.name;
  const styleLabels = data ? [...new Set(data.styles.map((s) => s.label.replace(/^música /i, '')))] : [];
  const spotlight = data ? artistSpotlight(data) : null;
  const [photoFailed, setPhotoFailed] = useState(false);
  const photo = data?.image && verifiablePhoto(data.image) && !photoFailed ? data.image : null;
  const onPoster = printed || differs(artist.name, name) ? `En el cartel: «${printed ?? artist.name}»` : null;

  // Los estilos documentados se guardan con el evento para el filtro de estilo (no hay búsquedas extra).
  const loadedStyles = state.status === 'success' ? state.data.styles.map((s) => s.label) : null;
  const stylesKey = loadedStyles?.join('|') ?? null;
  useEffect(() => {
    if (loadedStyles) onStyles(mbid, loadedStyles);
    // Solo cuando llegan estilos nuevos de este perfil.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mbid, stylesKey]);

  return (
    <View style={{ gap: Space.lg }}>
      <Hero mbid={mbid} name={name} photo={photo} onPhotoError={() => setPhotoFailed(true)} />
      {styleLabels.length ? (
        <View style={styles.chips} accessibilityLabel={`Estilos documentados: ${styleLabels.join(', ')}`}>
          {styleLabels.slice(0, 4).map((s) => <Chip key={s} label={s} />)}
        </View>
      ) : null}
      {state.status === 'error' && !data ? (
        <View style={{ gap: Space.sm }}>
          <Notice tone="warn">No se pudo cargar su ficha: {describeError(state.error)}</Notice>
          <Button label="Reintentar" variant="ghost" onPress={reload} />
        </View>
      ) : !spotlight ? (
        <View style={styles.row}><ActivityIndicator color={art.palette.glow} /><Meta>Cargando su ficha…</Meta></View>
      ) : (
        <About spotlight={spotlight} photo={photo} name={name} art={art} />
      )}
      <View style={{ gap: Space.sm }}>
        <Pressable onPress={() => router.push(`/artist/${mbid}`)} accessibilityRole="button"
          accessibilityLabel={`Explorar perfil y música de ${name}`}
          style={({ pressed }) => [styles.primary, { backgroundColor: art.palette.glow }, pressed && { opacity: 0.8 }]}>
          <Text style={[styles.primaryLabel, { color: art.palette.onGlow }]}>Explorar perfil y música  →</Text>
        </Pressable>
        <Button label="No es este artista" variant="ghost" onPress={onWrong} />
      </View>
      {onPoster ? <Meta>{onPoster}</Meta> : null}
    </View>
  );
}

/** «Sobre el artista». Los créditos de foto y texto, completos, tras ⓘ «Fuentes y créditos» (a un toque). */
function About({ spotlight, photo, name, art }: Ctx & { spotlight: Spotlight; photo: PhotoInfo | null; name: string }) {
  const [open, setOpen] = useState(false);
  const P = art.palette;
  const credits = spotlightCredits(photo, spotlight);
  return (
    <View style={{ gap: Space.sm }}>
      <View style={styles.aboutHead}>
        <Text style={[styles.section, { color: P.glow }]} accessibilityRole="header">Sobre el artista</Text>
        {credits.length ? (
          <Pressable onPress={() => setOpen((v) => !v)} accessibilityRole="button" accessibilityState={{ expanded: open }}
            accessibilityLabel={open ? 'Ocultar fuentes y créditos' : 'Fuentes y créditos de la foto y el texto'} hitSlop={10}
            style={[styles.infoBtn, { borderColor: open ? P.glow : art.surfaces.line }]}>
            <Text style={[styles.infoIcon, { color: open ? P.glow : C.muted }]}>i</Text>
          </Pressable>
        ) : null}
      </View>
      {open ? (
        <View style={[styles.credits, { borderColor: P.glow }]}>
          <Text style={styles.creditsTitle}>Fuentes y créditos</Text>
          {credits.map((c) => (
            <View key={c.title} style={{ gap: 2 }}>
              <Text style={styles.creditText} selectable><Text style={styles.creditLabel}>{c.title}. </Text>{c.detail}</Text>
              {c.links.map((l) => (
                <Text key={l.url + l.label} style={[styles.link, { color: P.glow }]} onPress={() => openBrowserAsync(l.url)} accessibilityRole="link">
                  {l.label}
                </Text>
              ))}
            </View>
          ))}
        </View>
      ) : null}
      {spotlight.paragraphs.length ? (
        spotlight.paragraphs.map((p, i) => <Text key={i} style={styles.bio}>{p}</Text>)
      ) : (
        <Text style={styles.bioEmpty}>Aún no hay información biográfica verificada sobre {name}. Su música y los datos documentados están en su perfil.</Text>
      )}
    </View>
  );
}

const differs = (a: string, b: string) => a.trim().toLowerCase() !== b.trim().toLowerCase();

/** Foto solo con derechos verificables (licencia, fuente y autor si hace falta); si no, el cartel tipográfico. */
function Hero({ mbid, name, photo, onPhotoError }: { mbid: string; name: string; photo: PhotoInfo | null; onPhotoError: () => void }) {
  const { width } = useWindowDimensions();
  const id = identityFor(mbid);
  const box = Math.min(width, 640) - Space.lg * 4;
  const size = fitSize(display(name, id.type), box, id.type, 52, 26);
  return (
    <View>
      <View style={[styles.hero, { backgroundColor: photo ? '#000' : id.palette.bg }]}>
        {photo ? (
          <Image source={{ uri: photo.url }} style={StyleSheet.absoluteFill} contentFit="cover" onError={onPhotoError}
            accessibilityLabel={`Foto de ${name}`} />
        ) : (
          <>
            <View style={[styles.heroShape, { backgroundColor: id.palette.pop }]} />
            <Text style={[styles.heroIssue, { color: id.palette.ink }]}>Nº {id.issue}</Text>
          </>
        )}
        <View style={[styles.heroNameBox, photo && styles.heroNameOnPhoto]}>
          <Text numberOfLines={2} adjustsFontSizeToFit
            style={{ color: photo ? C.text : id.palette.ink, fontFamily: id.type.family, fontSize: size, lineHeight: Math.round(size * 1.05),
              letterSpacing: id.type.tracking, includeFontPadding: false }}>
            {display(name, id.type)}
          </Text>
        </View>
      </View>
    </View>
  );
}

const MATCH_LABEL: Record<NonNullable<LinkCandidate['match']>, string> = {
  name: 'Mismo nombre', alias: 'Alias en MusicBrainz', similar: 'Nombre parecido', manual: 'Búsqueda',
};

/** Sin identidad fiable: candidatos con su desambiguación, búsqueda manual y la opción de dejarlo sin identificar. */
function IdentityPicker({ artist, printed, art, onAction, onCancel }: Ctx & {
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
  const P = art.palette;

  return (
    <View style={{ gap: Space.lg }}>
      <View style={{ gap: Space.xs }}>
        <Text style={styles.name}>{artist.name}</Text>
        {printed ? <Meta>En el cartel: «{printed}»</Meta> : null}
        <Notice tone={link.status === 'ambiguous' ? 'info' : 'warn'}>
          {onCancel ? 'Elige la identidad correcta o déjalo sin identificar.'
            : userNone ? 'Lo dejaste sin identificar: sigue en el line-up, sin perfil.'
              : link.status === 'ambiguous' ? `Hay ${candidates.length} artistas con este nombre. Elige el correcto: no se enlaza ninguno por defecto.`
                : 'Sin identidad fiable en MusicBrainz: no se muestra ningún perfil para no confundirlo con otro artista.'}
        </Notice>
        {link.evidence && !userNone ? <Meta>{link.evidence}</Meta> : null}
      </View>

      {candidates.length ? (
        <View style={{ gap: Space.sm }}>
          <Text style={[styles.section, { color: P.glow }]}>{similarOnly ? '¿Quizá…?' : 'Candidatos'}</Text>
          {similarOnly ? <Meta>Nombres parecidos en MusicBrainz: puede ser una errata del cartel. El nombre impreso no se cambia.</Meta> : null}
          {candidates.map((c) => <CandidateRow key={c.refId} c={c} chosen={link.refId === c.refId} art={art} onPress={() => onAction({ kind: 'choose', candidate: c })} />)}
        </View>
      ) : null}

      <View style={{ gap: Space.sm }}>
        <Text style={[styles.section, { color: P.glow }]}>Buscar en MusicBrainz</Text>
        <View style={styles.row}>
          <TextInput value={query} onChangeText={setQuery} onSubmitEditing={() => query.trim() && setSearch(query.trim())} returnKeyType="search"
            placeholder="Nombre del artista" placeholderTextColor={C.faint} accessibilityLabel="Buscar artista en MusicBrainz"
            style={[styles.input, { flex: 1, borderColor: art.surfaces.line, backgroundColor: art.surfaces.raised }]} />
          <Button label="Buscar" variant="ghost" onPress={() => query.trim() && setSearch(query.trim())} />
        </View>
        {results.state.status === 'loading' ? <View style={styles.row}><ActivityIndicator color={P.glow} /><Meta>Buscando…</Meta></View> : null}
        {results.state.status === 'error' ? <Notice tone="warn">{describeError(results.state.error)}</Notice> : null}
        {results.state.status === 'success' && !found.length ? <Meta>Sin resultados.</Meta> : null}
        {found.map((c) => <CandidateRow key={c.refId} c={c} chosen={link.refId === c.refId} art={art} onPress={() => onAction({ kind: 'choose', candidate: c })} />)}
      </View>

      <View style={{ gap: Space.sm }}>
        {onCancel ? <Button label="Mantener la identidad actual" variant="ghost" onPress={onCancel} /> : null}
        {!userNone ? <Button label="Dejar sin identificar" variant="ghost" onPress={() => onAction({ kind: 'unidentified' })} /> : null}
        {link.origin === 'user' ? <Button label="Volver a la identificación automática" variant="ghost" onPress={() => onAction({ kind: 'reset' })} /> : null}
      </View>
    </View>
  );
}

function CandidateRow({ c, chosen, art, onPress }: Ctx & { c: LinkCandidate; chosen: boolean; onPress: () => void }) {
  const facts = [c.disambiguation, c.type, c.country].filter(Boolean).join(' · ');
  return (
    <Pressable onPress={onPress} accessibilityRole="button" accessibilityState={{ selected: chosen }}
      accessibilityLabel={`Elegir ${c.name}${facts ? `, ${facts}` : ''}`}
      style={({ pressed }) => [styles.candidate, { borderColor: chosen ? art.palette.glow : art.surfaces.line, backgroundColor: art.surfaces.raised },
        pressed && { opacity: 0.75 }]}>
      <View style={{ flex: 1, gap: 2 }}>
        <Text style={styles.trackTitle}>{c.name}</Text>
        {facts ? <Meta numberOfLines={2}>{facts}</Meta> : <Meta>Sin desambiguación en MusicBrainz</Meta>}
        <Text style={[styles.badge, { color: art.palette.glow }]}>{[c.match ? MATCH_LABEL[c.match] : null, c.scene ? 'Escena electrónica' : null].filter(Boolean).join(' · ')}</Text>
      </View>
      <Text style={[styles.trackGo, { color: art.palette.glow }]}>{chosen ? '✓' : 'Elegir'}</Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  backdrop: { backgroundColor: 'rgba(7,6,11,0.72)' },
  // La tarjeta mide lo que su contenido hasta el 100 % del marco; a partir de ahí, desplaza el ScrollView.
  scroll: { flexGrow: 0, flexShrink: 1 },
  frame: { position: 'absolute', left: 0, right: 0, bottom: 0, justifyContent: 'flex-end' },
  sheet: { maxHeight: '100%', flexShrink: 1, paddingHorizontal: Space.lg, borderTopLeftRadius: Radius.lg, borderTopRightRadius: Radius.lg,
    borderTopWidth: 2 },
  handle: { alignSelf: 'center', width: 44, height: 4, borderRadius: 2, marginTop: Space.sm },
  head: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', paddingTop: Space.sm },
  kicker: { fontFamily: Fonts.monoBold, fontSize: 11, letterSpacing: 1.4, textTransform: 'uppercase' },
  closeBtn: { width: 44, height: 44, borderRadius: 22, borderWidth: 1, alignItems: 'center', justifyContent: 'center' },
  close: { color: C.text, fontSize: 18 },
  tabs: { flexDirection: 'row', gap: Space.sm, paddingTop: Space.sm },
  tab: { flex: 1, minHeight: 44, borderRadius: Radius.pill, borderWidth: 1.5, alignItems: 'center', justifyContent: 'center', paddingHorizontal: Space.md },
  tabLabel: { fontFamily: Fonts.sansBold, fontSize: 14 },
  chips: { flexDirection: 'row', flexWrap: 'wrap', gap: Space.sm },
  row: { flexDirection: 'row', alignItems: 'center', gap: Space.md },
  name: { color: C.text, fontFamily: Fonts.display, fontSize: 32, lineHeight: 36, textTransform: 'uppercase' },
  hero: { height: 176, borderRadius: Radius.md, overflow: 'hidden', justifyContent: 'flex-end' },
  heroShape: { position: 'absolute', top: -40, right: -30, width: 150, height: 150, borderRadius: 75 },
  heroIssue: { position: 'absolute', top: Space.md, left: Space.lg, fontFamily: Fonts.monoBold, fontSize: 11, letterSpacing: 1.2 },
  heroNameBox: { padding: Space.lg },
  heroNameOnPhoto: { backgroundColor: 'rgba(7,6,11,0.72)' },
  aboutHead: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  infoBtn: { width: 28, height: 28, borderRadius: 14, borderWidth: 1.5, alignItems: 'center', justifyContent: 'center' },
  infoIcon: { fontFamily: Fonts.monoBold, fontSize: 14 },
  credits: { borderLeftWidth: 2, paddingLeft: Space.md, gap: Space.sm },
  creditsTitle: { color: C.text, fontFamily: Fonts.monoBold, fontSize: 11, letterSpacing: 1.2, textTransform: 'uppercase' },
  creditLabel: { fontFamily: Fonts.sansBold },
  creditText: { color: C.text, fontFamily: Fonts.sans, fontSize: 13, lineHeight: 19 },
  link: { fontFamily: Fonts.monoBold, fontSize: 12, textDecorationLine: 'underline' },
  bio: { color: C.text, fontFamily: Fonts.sans, fontSize: 15, lineHeight: 23 },
  bioEmpty: { color: C.muted, fontFamily: Fonts.sans, fontSize: 15, lineHeight: 22 },
  section: { fontFamily: Fonts.monoBold, fontSize: 12, letterSpacing: 1.4, textTransform: 'uppercase' },
  primary: { minHeight: 52, borderRadius: Radius.md, alignItems: 'center', justifyContent: 'center' },
  primaryLabel: { fontFamily: Fonts.sansBold, fontSize: 16 },
  trackTitle: { color: C.text, fontFamily: Fonts.sansBold, fontSize: 16, lineHeight: 21 },
  trackGo: { fontFamily: Fonts.monoBold, fontSize: 12 },
  candidate: { flexDirection: 'row', alignItems: 'center', gap: Space.md, padding: Space.md, borderRadius: Radius.md, borderWidth: 1.5 },
  badge: { fontFamily: Fonts.mono, fontSize: 11 },
  input: { minHeight: 48, borderWidth: 1.5, borderRadius: Radius.md, color: C.text, fontFamily: Fonts.sans, fontSize: 16, paddingHorizontal: Space.md },
});
