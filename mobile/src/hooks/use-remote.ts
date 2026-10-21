import { useCallback, useEffect, useState } from 'react';

import type { ApiError, ApiResult } from '@/services/api-client';

export type Remote<T> =
  | { status: 'idle' }
  | { status: 'loading'; previous: T | null }
  | { status: 'success'; data: T }
  | { status: 'error'; error: ApiError };

/**
 * Carga datos del backend cuando cambia `key` (null = no cargar). Ignora respuestas de cargas anteriores.
 * Al recargar conserva los datos previos en `previous` para no vaciar la pantalla.
 */
export function useRemote<T>(key: string | null, load: () => Promise<ApiResult<T>>) {
  const [state, setState] = useState<Remote<T>>({ status: 'idle' });
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    if (key === null) {
      setState({ status: 'idle' });
      return;
    }
    let active = true;
    setState((prev) => ({ status: 'loading', previous: prev.status === 'success' ? prev.data : prev.status === 'loading' ? prev.previous : null }));
    load().then((result) => {
      if (!active) return;
      setState(result.ok ? { status: 'success', data: result.data } : { status: 'error', error: result.error });
    });
    return () => {
      active = false;
    };
    // `load` cambia en cada render; la carga depende solo de `key` y de los reintentos.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, attempt]);

  const reload = useCallback(() => setAttempt((n) => n + 1), []);
  return { state, reload };
}
