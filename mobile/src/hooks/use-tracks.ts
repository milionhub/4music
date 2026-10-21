import { useCallback, useEffect, useState } from 'react';

import { type ApiError, type ApiResult } from '@/services/api-client';
import { getTrack } from '@/services/music';
import type { TrackResponse } from '@/types/music';

export type TrackState = { status: 'loading' } | { status: 'ok'; data: TrackResponse } | { status: 'error'; error: ApiError };

/**
 * Fichas pedidas en esta sesión, por MBID: Inicio no repite peticiones al volver a la pestaña ni al cambiar los
 * Guardados (el backend ya las guarda una semana). Los fallos no se recuerdan: se reintentan.
 */
const session = new Map<string, Promise<ApiResult<TrackResponse>>>();

function fetchOnce(mbid: string): Promise<ApiResult<TrackResponse>> {
  let p = session.get(mbid);
  if (!p) {
    p = getTrack(mbid).then((r) => {
      if (!r.ok) session.delete(mbid);
      return r;
    });
    session.set(mbid, p);
  }
  return p;
}

/**
 * Carga progresiva de fichas TrackDNA por grupos: cada grupo es una canción y sus reservas, y solo se pide la primera
 * que no ha fallado (si falla, entra la siguiente; nunca todas a la vez). Cada ficha se pinta al llegar y un fallo no
 * bloquea las demás. `chosen(grupo)`: la candidata vigente (null si fallaron todas); `retry` vuelve a las primeras.
 */
export function useTracks(groups: string[][]) {
  const [results, setResults] = useState<Record<string, TrackState>>({});
  const [attempt, setAttempt] = useState(0);
  const chosen = useCallback((group: string[]) => group.find((m) => results[m]?.status !== 'error') ?? null, [results]);
  const key = [...new Set(groups.map(chosen).filter((m): m is string => !!m))].join(',');

  useEffect(() => {
    if (!key) return;
    let active = true;
    for (const mbid of key.split(',')) {
      fetchOnce(mbid).then((r) => {
        if (!active) return;
        setResults((prev) => ({ ...prev, [mbid]: r.ok ? { status: 'ok', data: r.data } : { status: 'error', error: r.error } }));
      });
    }
    return () => {
      active = false;
    };
  }, [key, attempt]);

  const stateOf = useCallback((mbid: string | null): TrackState | null => (mbid ? results[mbid] ?? { status: 'loading' } : null), [results]);
  const retry = useCallback(() => {
    setResults((prev) => Object.fromEntries(Object.entries(prev).filter(([, v]) => v.status !== 'error')));
    setAttempt((n) => n + 1);
  }, []);
  return { chosen, stateOf, retry };
}
