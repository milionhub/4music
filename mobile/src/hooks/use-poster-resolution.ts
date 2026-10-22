/**
 * Carteles 3.4: resolución progresiva de identidades mientras el evento está en pantalla.
 *
 * - Una petición de lote cada vez (RESOLVE_BATCH nombres), nunca el festival entero en paralelo; el backend espacia
 *   MusicBrainz a 1 petición/1,1 s y guarda cada resultado en caché.
 * - `prioritize(id)`: el artista que abre el usuario se resuelve en el momento, en una petición propia.
 * - Se detiene al salir de la pantalla (perfil, TrackDNA, editar), al pausar o ante un fallo de red. Lo ya resuelto
 *   queda guardado en el evento: al volver solo se piden los que faltan.
 * - Cada resultado se aplica sobre el evento recién leído del almacenamiento, para no pisar ediciones de otra pantalla.
 */
import { useFocusEffect } from 'expo-router';
import { useCallback, useRef, useState } from 'react';

import { applyResolution, needsResolution, RESOLVE_BATCH, resolutionQueue } from '@/lib/poster-identity';
import { describeError } from '@/services/api-client';
import { resolveArtists } from '@/services/posters';
import { loadEvent, saveEvent } from '@/storage/poster-library';
import type { PosterArtist, PosterEvent } from '@/types/poster';

export function usePosterResolution(eventId: string | undefined, onEvent: (e: PosterEvent) => void) {
  const [running, setRunning] = useState(false);
  const [paused, setPausedState] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const focused = useRef(false);
  const busy = useRef(false);
  const pausedRef = useRef(false);
  const failed = useRef(new Set<string>()); // fallaron en esta visita: no se reintentan solos
  const priority = useRef(new Set<string>()); // en curso por petición propia

  /** Pide `ids` y guarda lo que llegue. Devuelve false si hubo un fallo (red o MusicBrainz). */
  const resolveIds = useCallback(async (ids: string[]): Promise<boolean> => {
    if (!eventId) return false;
    const current = loadEvent(eventId);
    const artists = ids.map((id) => current?.artists.find((a) => a.id === id)).filter((a): a is PosterArtist => !!a);
    if (!artists.length) return true;
    const r = await resolveArtists(artists.map((a) => a.name));
    if (!r.ok) {
      artists.forEach((a) => failed.current.add(a.id));
      setError(describeError(r.error));
      return false;
    }
    let next = loadEvent(eventId);
    if (!next) return false;
    let ok = true;
    r.data.results.forEach((res, i) => {
      if (res.status === 'error') {
        ok = false;
        failed.current.add(artists[i].id);
      } else if (next) {
        next = applyResolution(next, artists[i].id, res);
      }
    });
    if (next) {
      const saved = saveEvent(next);
      onEvent(next);
      if (!saved.ok) setError(saved.message);
    }
    setError(ok ? null : 'MusicBrainz no responde ahora mismo. Lo ya identificado está guardado.');
    return ok;
  }, [eventId, onEvent]);

  const pump = useCallback(async () => {
    if (busy.current || !eventId) return;
    busy.current = true;
    setRunning(true);
    try {
      while (focused.current && !pausedRef.current) {
        const current = loadEvent(eventId);
        if (!current) break;
        const ids = resolutionQueue(current).filter((id) => !failed.current.has(id) && !priority.current.has(id)).slice(0, RESOLVE_BATCH);
        if (!ids.length || !(await resolveIds(ids))) break;
      }
    } finally {
      busy.current = false;
      setRunning(false);
    }
  }, [eventId, resolveIds]);

  useFocusEffect(useCallback(() => {
    focused.current = true;
    void pump();
    return () => {
      focused.current = false; // el lote en curso termina y se guarda; no se pide otro
    };
  }, [pump]));

  /** El usuario abre a este artista: se resuelve ya (aunque haya un lote en curso o esté en pausa). */
  const prioritize = useCallback((artistId: string) => {
    const e = eventId ? loadEvent(eventId) : null;
    const a = e?.artists.find((x) => x.id === artistId);
    if (!a || !needsResolution(a) || priority.current.has(artistId)) return;
    priority.current.add(artistId);
    failed.current.delete(artistId);
    void resolveIds([artistId]).finally(() => priority.current.delete(artistId));
  }, [eventId, resolveIds]);

  const setPaused = useCallback((value: boolean) => {
    pausedRef.current = value;
    setPausedState(value);
    if (!value) void pump();
  }, [pump]);

  /** Reintento manual tras un fallo: vuelve a pedir también los que fallaron. */
  const retry = useCallback(() => {
    failed.current.clear();
    setError(null);
    void pump();
  }, [pump]);

  return { running, paused, error, prioritize, setPaused, retry };
}
