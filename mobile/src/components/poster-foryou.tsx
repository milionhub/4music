/**
 * Carteles 4 · Para ti (V6.8): quién del cartel te encaja y por qué, con su hora y escenario si están impresos. Los
 * motivos salen de lib/poster-fit (tus Guardados, artistas de partida y estilos frente al sonido de cada artista).
 */
import { router } from 'expo-router';
import { useEffect, useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { C, Fonts, Space } from '@/constants/theme';
import type { EventArt } from '@/lib/poster-art';
import { timeLabel } from '@/lib/poster-explore';
import { type ArtistFit, FIT_MIN, type FitKind } from '@/lib/poster-fit';
import { linkedMbid } from '@/lib/poster-identity';
import { getEssentials } from '@/services/music';
import type { PosterEvent } from '@/types/poster';

import { EventCard } from './poster';
import { Snippet } from './poster-sound';

export const FIT_GLYPH: Record<FitKind, string> = { saved: '♥', favorite: '★', related: '≈', label: '◎', style: '✶' };
/** Pocos y legibles: el resto, con «Ver los N». */
const SHOWN = 3;
/** Motivos visibles por artista (todos en la etiqueta de accesibilidad). */
const REASONS = 2;
/** Extractos solo para los que más te encajan: el resto se escucha desde su perfil o TrackDNA. */
const WITH_SNIPPET = 3;

type Pick = { id: string; title: string } | null;
// Primer tema esencial con extracto de cada artista, por MBID: no se vuelve a pedir al volver a la pantalla.
const picks = new Map<string, Pick>();

function useSnippets(mbids: string[]): Map<string, Pick> {
  const [, setTick] = useState(0);
  const key = mbids.join(',');
  useEffect(() => {
    let active = true;
    (async () => {
      for (const mbid of key ? key.split(',') : []) {
        if (picks.has(mbid)) continue;
        const r = await getEssentials(mbid);
        if (!r.ok) continue; // sin red: se intenta en la próxima visita
        const t = r.data.tracks.find((x) => x.deezer_url);
        picks.set(mbid, t ? { id: t.id, title: t.title } : null);
        if (active) setTick((n) => n + 1);
      }
    })();
    return () => {
      active = false;
    };
  }, [key]);
  return picks;
}

export function ForYou({ event, fits, art, progress, running, hasTaste, onOpen }: {
  event: PosterEvent; fits: ArtistFit[]; art: EventArt; progress: { done: number; total: number }; running: boolean;
  hasTaste: boolean; onOpen: (setId: string | null, artistId: string, members: string[]) => void;
}) {
  const [all, setAll] = useState(false);
  const P = art.palette;
  const strong = fits.filter((f) => f.score >= FIT_MIN);
  const styleOnly = fits.filter((f) => f.score < FIT_MIN);
  const listening = running && progress.done < progress.total;
  const shown = all ? strong : strong.slice(0, SHOWN);
  const snippetFor = useSnippets(hasTaste ? strong.slice(0, WITH_SNIPPET).map((f) => linkedMbid(f.artist)).filter((m): m is string => !!m) : []);
  const open = (f: ArtistFit) => onOpen(f.sets[0]?.id ?? null, f.artist.id, f.sets[0]?.artistIds ?? [f.artist.id]);
  const where = (f: ArtistFit) => {
    const s = f.sets[0];
    if (!s) return null;
    const stage = s.stageId ? event.stages.find((x) => x.id === s.stageId)?.name : null;
    return [stage, timeLabel(s), f.sets.length > 1 ? `y ${f.sets.length - 1} más` : null].filter(Boolean).join(' · ') || null;
  };

  return (
    <EventCard title="Para ti" art={art} right={hasTaste && strong.length ? `${strong.length} de ${event.artists.length} te encajan` : null}>

      {!hasTaste ? (
        <View style={{ gap: Space.sm }}>
          <Text style={styles.body}>Guarda canciones o elige tus artistas y estilos, y aquí verás quién del cartel te encaja y por qué.</Text>
          <Pressable onPress={() => router.navigate('/profile')} accessibilityRole="button" hitSlop={8}>
            <Text style={[styles.mono, { color: P.glow }]}>Ir a tu pase ↗</Text>
          </Pressable>
        </View>
      ) : null}

      {hasTaste ? shown.map((f) => (
        <Pressable key={f.artist.id} onPress={() => open(f)} accessibilityRole="button"
          accessibilityLabel={[f.artist.name, where(f), ...f.reasons.map((r) => r.text), 'abrir vista rápida'].filter(Boolean).join(', ')}
          style={({ pressed }) => [styles.row, { borderBottomColor: art.surfaces.line }, pressed && { opacity: 0.7 }]}>
          <View style={{ flexDirection: 'row', alignItems: 'baseline', gap: Space.sm }}>
            <Text style={styles.name} numberOfLines={2}>{f.artist.name}</Text>
            <Text style={[styles.arrow, { color: P.glow }]}>↗</Text>
          </View>
          {where(f) ? <Text style={styles.where}>{where(f)}</Text> : null}
          {f.reasons.slice(0, REASONS).map((r) => (
            <Text key={r.kind} style={styles.reason}>
              <Text style={{ color: P.glow }}>{`${FIT_GLYPH[r.kind]}  `}</Text>{r.text}
            </Text>
          ))}
          {(() => {
            const pick = snippetFor.get(linkedMbid(f.artist) ?? '');
            return pick ? <Snippet id={pick.id} title={pick.title} accent={P.glow} onAccent={P.onGlow} /> : null;
          })()}
        </Pressable>
      )) : null}
      {hasTaste && strong.length > SHOWN ? (
        <Pressable onPress={() => setAll((x) => !x)} accessibilityRole="button" hitSlop={8}>
          <Text style={[styles.mono, { color: P.glow }]}>{all ? 'Ver menos' : `Ver los ${strong.length}`}</Text>
        </Pressable>
      ) : null}

      {hasTaste && styleOnly.length ? (
        <Text style={styles.body}>
          <Text style={[styles.mono, { color: C.muted }]}>{'En tus estilos  '}</Text>
          {styleOnly.map((f, i) => (
            <Text key={f.artist.id} onPress={() => open(f)} accessibilityRole="link" style={{ color: C.text, fontFamily: Fonts.sansBold }}>
              {f.artist.name}{i < styleOnly.length - 1 ? ' · ' : ''}
            </Text>
          ))}
        </Text>
      ) : null}

      {hasTaste && !fits.length && !listening ? (
        <Text style={styles.body}>
          {progress.total ? 'Nadie del cartel cruza todavía con tus gustos. Explora el line-up: cada artista lleva a su perfil y a TrackDNA.'
            : 'Cuando se identifiquen los artistas, aquí aparecerán los que te encajan.'}
        </Text>
      ) : null}
      {listening ? (
        <Text style={styles.note} accessibilityLiveRegion="polite">
          {`Escuchando el line-up · ${progress.done} de ${progress.total}${strong.length ? '' : ' · pueden aparecer más'}`}
        </Text>
      ) : null}
    </EventCard>
  );
}

const styles = StyleSheet.create({
  mono: { fontFamily: Fonts.monoBold, fontSize: 11, letterSpacing: 1.3, textTransform: 'uppercase' },
  body: { color: C.muted, fontFamily: Fonts.sans, fontSize: 15, lineHeight: 22 },
  note: { color: C.faint, fontFamily: Fonts.mono, fontSize: 11, lineHeight: 16 },
  row: { gap: 6, paddingBottom: Space.lg, borderBottomWidth: StyleSheet.hairlineWidth },
  name: { color: C.text, fontFamily: Fonts.display, fontSize: 24, lineHeight: 28, textTransform: 'uppercase', includeFontPadding: false, flexShrink: 1 },
  arrow: { fontFamily: Fonts.monoBold, fontSize: 16 },
  where: { color: C.muted, fontFamily: Fonts.monoBold, fontSize: 12, letterSpacing: 0.6, textTransform: 'uppercase' },
  reason: { color: C.muted, fontFamily: Fonts.sans, fontSize: 14, lineHeight: 20 },
});
