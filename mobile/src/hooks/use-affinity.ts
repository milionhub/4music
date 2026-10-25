import { useEffect, useState } from 'react';

import { type ApiResult } from '@/services/api-client';
import { getAffinity } from '@/services/music';
import type { AffinityResponse } from '@/types/music';

/** Afines pedidos en esta sesión, por MBID (el backend los guarda una semana). Los fallos no se recuerdan. */
const session = new Map<string, Promise<ApiResult<AffinityResponse>>>();

function fetchOnce(mbid: string): Promise<ApiResult<AffinityResponse>> {
  let p = session.get(mbid);
  if (!p) {
    p = getAffinity(mbid).then((r) => {
      if (!r.ok) session.delete(mbid);
      return r;
    });
    session.set(mbid, p);
  }
  return p;
}

/**
 * Canciones afines de cada Guardado (Tu frecuencia), pedidas en paralelo y pintadas al llegar.
 * Por MBID: undefined = aún no ha llegado; null = no se pudo cargar o no hay afines.
 */
export function useAffinity(mbids: string[]): Record<string, AffinityResponse | null | undefined> {
  const [results, setResults] = useState<Record<string, AffinityResponse | null>>({});
  const key = [...new Set(mbids)].join(',');

  useEffect(() => {
    if (!key) return;
    let active = true;
    for (const mbid of key.split(',')) {
      fetchOnce(mbid).then((r) => {
        if (active) setResults((prev) => ({ ...prev, [mbid]: r.ok && r.data.status === 'ready' ? r.data : null }));
      });
    }
    return () => {
      active = false;
    };
  }, [key]);

  return results;
}
