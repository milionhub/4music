/**
 * Inicio V6 de Chromatic Underground: revista underground con edición diaria (lib/home-edition.ts) y descubrimiento
 * de música real (lib/home-picks.ts). Portada con la canción del día, En el radar, Tu frecuencia (a partir de tus
 * Guardados) y Detrás del sonido. Todo sale de fichas TrackDNA (GET /v1/tracks/{mbid}, en caché en el backend):
 * como mucho tres fichas editoriales, las de tus cuatro Guardados más recientes y hasta cuatro de candidatos de Tu
 * frecuencia (para su portada real); cada una se pinta al llegar.
 */
import { router } from 'expo-router';
import { useEffect, useMemo, useState } from 'react';
import { AppState, ScrollView, useWindowDimensions, View } from 'react-native';
import Animated, { FadeIn, ReduceMotion } from 'react-native-reanimated';
import { SafeAreaView } from 'react-native-safe-area-context';

import {
  BehindBody, EditionCover, EditionFooter, FrequencyBody, HomeSection, type LoadState, Masthead, type Protagonist, RadarBody,
} from '@/components/home';
import { openTrack } from '@/components/track';
import { MaxContentWidth } from '@/constants/theme';
import { type TrackState, useTracks } from '@/hooks/use-tracks';
import { duration } from '@/lib/format';
import type { EditorialPick } from '@/lib/home-catalog';
import { editionFor, localDayKey } from '@/lib/home-edition';
import { behindFact, dailySlots, FREQUENCY_SEEDS, frequency, radarFact } from '@/lib/home-picks';
import { useLibrary } from '@/state/library';
import type { TrackResponse } from '@/types/music';

/** Fecha local; se revisa al volver la app a primer plano. La edición cambia a medianoche, nunca entre renders. */
function useDayKey() {
  const [key, setKey] = useState(() => localDayKey(new Date()));
  useEffect(() => {
    const sub = AppState.addEventListener('change', (s) => {
      if (s === 'active') setKey(localDayKey(new Date()));
    });
    return () => sub.remove();
  }, []);
  return key;
}

const loadOf = (st: TrackState | null): LoadState => (!st || st.status === 'loading' ? 'loading' : st.status === 'ok' ? 'ok' : 'error');
const dataOf = (st: TrackState | null): TrackResponse | undefined => (st?.status === 'ok' ? st.data : undefined);

/** La ficha manda (título y portada canónicos); mientras carga, los datos verificados de la selección. */
function protagonist(pick: EditorialPick | undefined, data: TrackResponse | undefined): Protagonist | null {
  if (!pick) return null;
  return {
    mbid: data?.mbid ?? pick.mbid,
    title: data?.title ?? pick.title,
    artist: data?.artist_name || pick.artist,
    cover: data ? data.cover_url : pick.cover,
    year: data ? data.first_release_date?.slice(0, 4) ?? null : pick.year,
  };
}

export default function Home() {
  const lib = useLibrary();
  const { width } = useWindowDimensions();
  const pageWidth = Math.min(width, MaxContentWidth);
  const dayKey = useDayKey();
  const ed = useMemo(() => editionFor(dayKey), [dayKey]);
  const P = ed.palette;

  // Huecos del día sin lo que ya tenías guardado al abrir la edición: guardar la canción de portada no la cambia
  // a mitad del día (Tu frecuencia, en cambio, sí se recalcula con cada cambio en Guardados).
  const [daySaved, setDaySaved] = useState(() => ({ day: ed.dayIndex, ids: lib.savedTracks.map((t) => t.mbid) }));
  if (daySaved.day !== ed.dayIndex) setDaySaved({ day: ed.dayIndex, ids: lib.savedTracks.map((t) => t.mbid) });
  const slots = useMemo(() => dailySlots(daySaved.day, daySaved.ids), [daySaved]);
  const seeds = lib.savedTracks.slice(0, FREQUENCY_SEEDS);
  const tracks = useTracks([
    slots.cover.map((p) => p.mbid),
    slots.radar.map((p) => p.mbid),
    slots.behind.map((p) => p.mbid),
    ...seeds.map((s) => [s.mbid]),
  ]);
  const pickOf = (list: EditorialPick[]) => {
    const mbid = tracks.chosen(list.map((p) => p.mbid));
    return list.find((p) => p.mbid === mbid);
  };

  const coverPick = pickOf(slots.cover);
  const coverState = tracks.stateOf(coverPick?.mbid ?? null);
  const radarPick = pickOf(slots.radar);
  const radarState = tracks.stateOf(radarPick?.mbid ?? null);
  const radarData = dataOf(radarState);
  const behindPick = pickOf(slots.behind);
  const behindData = dataOf(tracks.stateOf(behindPick?.mbid ?? null));
  const coverTrack = protagonist(coverPick, dataOf(coverState));
  const radarTrack = protagonist(radarPick, radarData);

  // Tu frecuencia: sin nada de lo que ya está en la portada o en el radar (ni la canción de Detrás del sonido).
  const details = Object.fromEntries(seeds.map((s) => [s.mbid, dataOf(tracks.stateOf(s.mbid))]));
  const onCover = [coverTrack?.mbid, radarTrack?.mbid, coverPick?.mbid, radarPick?.mbid].filter((m): m is string => !!m);
  const freqInput = {
    saved: lib.savedTracks,
    details,
    favorites: lib.favorites,
    declaredStyles: lib.preferences.declared_styles,
    exclude: [...onCover, ...(behindPick ? [behindPick.mbid] : [])],
    dayIndex: ed.dayIndex,
  };
  // Candidatos por relación: su ficha (en caché) da la portada real y confirma que no es una versión de un Guardado.
  // Como mucho FREQUENCY_LOOKUPS peticiones; una portada que no carga en el dispositivo saca al candidato.
  const lookups = frequency(freqInput).lookups;
  const lookupTracks = useTracks(lookups.map((m) => [m]));
  const [failedCovers, setFailedCovers] = useState<string[]>([]);
  const candidates = Object.fromEntries(lookups.map((m) => {
    const st = lookupTracks.stateOf(m);
    return [m, st?.status === 'ok' ? st.data : st?.status === 'error' ? null : undefined];
  }));
  const freq = frequency({ ...freqInput, candidates, failedCovers });
  const onCoverError = (url: string) => setFailedCovers((prev) => (prev.includes(url) ? prev : [...prev, url]));
  const seedsLoading = seeds.some((s) => loadOf(tracks.stateOf(s.mbid)) === 'loading');
  // Detrás del sonido: primero tus Guardados, luego la selección del día; nunca algo que ya se ve en Inicio.
  const shown = new Set([...onCover, ...freq.items.map((i) => i.mbid)]);
  const behind = behindFact([...seeds.map((s) => details[s.mbid]), behindData], shown);
  const behindPersonal = !!behind && seeds.some((s) => details[s.mbid]?.mbid === behind.track.mbid);

  const radarMeta = radarData ? [radarData.first_release_date?.slice(0, 4), duration(radarData.length_ms)].filter(Boolean).join(' · ') : radarPick?.year ?? null;
  const [radarS, freqS, behindS] = ed.rhythm.map((k) => P[k]);

  let intro: string;
  if (!lib.savedTracks.length) {
    intro = freq.personal
      ? 'Aún no tienes canciones en Guardados: partimos de los artistas y estilos que elegiste. Guarda canciones en TrackDNA y esta frecuencia aprenderá de ti.'
      : 'Aún no tienes canciones en Guardados: aquí va una selección variada de la redacción. Guarda lo que te guste en TrackDNA y esta frecuencia se afinará contigo.';
  } else if (seedsLoading && !freq.personal) {
    intro = 'Sintonizando con tus Guardados…';
  } else {
    intro = freq.personal
      ? `A partir de ${lib.savedTracks.length === 1 ? 'tu canción guardada' : `tus ${lib.savedTracks.length} canciones guardadas`} y tus gustos. Cada propuesta dice por qué aparece.`
      : 'Tus Guardados aún no tienen conexiones documentadas con otras canciones. Mientras tanto, la selección de la redacción.';
  }

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: P.night.bg }} edges={['top', 'left', 'right']}>
      <ScrollView style={{ backgroundColor: P.night.bg }} contentInsetAdjustmentBehavior="never">
        <View style={{ width: pageWidth, alignSelf: 'center' }}>
          <Masthead ed={ed} />
          <EditionCover ed={ed} width={pageWidth} track={coverTrack} state={coverTrack ? loadOf(coverState) : 'error'}
            onOpen={() => coverTrack && openTrack(coverTrack.mbid)} onSearch={() => router.navigate('/trackdna')} />

          <Animated.View entering={FadeIn.duration(250).reduceMotion(ReduceMotion.System)}>
            <HomeSection ed={ed} s={radarS} index={1} title="En el radar" width={pageWidth}
              intro="Una canción de la selección de la redacción para descubrir hoy, con un dato documentado.">
              <RadarBody ed={ed} s={radarS} width={pageWidth} track={radarTrack} state={radarTrack ? loadOf(radarState) : 'error'}
                meta={radarMeta || null} fact={radarData ? radarFact(radarData) : null}
                onOpen={() => radarTrack && openTrack(radarTrack.mbid)} onRetry={tracks.retry} />
            </HomeSection>

            <HomeSection ed={ed} s={freqS} index={2} title="Tu frecuencia" width={pageWidth} intro={intro}>
              <FrequencyBody s={freqS} items={freq.items} onOpen={openTrack} onCoverError={onCoverError} />
            </HomeSection>

            {behind ? (
              <HomeSection ed={ed} s={behindS} index={3} title="Detrás del sonido" width={pageWidth}>
                <BehindBody ed={ed} s={behindS} width={pageWidth} fact={behind} personal={behindPersonal} onOpen={openTrack} />
              </HomeSection>
            ) : null}
          </Animated.View>
          <EditionFooter ed={ed} />
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}
