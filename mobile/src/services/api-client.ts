import { getApiConfig } from '@/config/api';

export type ApiError = {
  kind: 'config' | 'network' | 'timeout' | 'http' | 'invalid';
  /** Código del contrato (`provider_unavailable`, `not_found`…) cuando el backend lo envía. */
  code: string | null;
  status: number | null;
  message: string;
};

export type ApiResult<T> = { ok: true; data: T } | { ok: false; error: ApiError };

/** GET JSON al backend con timeout; nunca lanza: devuelve un error tipado. */
export function getJson<T>(path: string, timeoutMs: number): Promise<ApiResult<T>> {
  return request<T>(path, timeoutMs);
}

/** POST JSON (Carteles: análisis de imagen). Mismo contrato de errores que getJson. */
export function postJson<T>(path: string, body: unknown, timeoutMs: number): Promise<ApiResult<T>> {
  return request<T>(path, timeoutMs, { method: 'POST', body: JSON.stringify(body), headers: { 'Content-Type': 'application/json' } });
}

async function request<T>(path: string, timeoutMs: number, init?: { method: string; body: string; headers: Record<string, string> }): Promise<ApiResult<T>> {
  const config = getApiConfig();
  if (!config.ok) {
    return { ok: false, error: { kind: 'config', code: null, status: null, message: config.reason } };
  }
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(`${config.baseUrl}${path}`, {
      method: init?.method ?? 'GET',
      body: init?.body,
      headers: { Accept: 'application/json', ...init?.headers },
      signal: controller.signal,
    });
    let body: unknown = null;
    try {
      body = await response.json();
    } catch {
      body = null;
    }
    if (!response.ok) {
      const err = (body as { error?: { code?: unknown; message?: unknown } } | null)?.error;
      return {
        ok: false,
        error: {
          kind: 'http',
          code: typeof err?.code === 'string' ? err.code : null,
          status: response.status,
          message: typeof err?.message === 'string' ? err.message : `Respuesta HTTP ${response.status}`,
        },
      };
    }
    if (body === null || typeof body !== 'object') {
      return { ok: false, error: { kind: 'invalid', code: null, status: response.status, message: 'Respuesta no válida del servidor' } };
    }
    return { ok: true, data: body as T };
  } catch (error) {
    if (controller.signal.aborted) {
      return { ok: false, error: { kind: 'timeout', code: null, status: null, message: `Sin respuesta en ${Math.round(timeoutMs / 1000)} s` } };
    }
    const detail = error instanceof Error ? error.message : String(error);
    return { ok: false, error: { kind: 'network', code: null, status: null, message: `No se pudo conectar: ${detail}` } };
  } finally {
    clearTimeout(timer);
  }
}

/** Mensaje comprensible para la interfaz. */
export function describeError(error: ApiError): string {
  switch (error.code) {
    case 'provider_unavailable':
      return 'MusicBrainz no responde ahora mismo. Inténtalo de nuevo en unos segundos.';
    case 'provider_not_configured':
      return 'El servidor no tiene configurado el contacto para MusicBrainz (MUSICBRAINZ_CONTACT).';
    case 'not_found':
      return 'MusicBrainz no tiene este artista.';
    case 'provider_bad_response':
      return 'MusicBrainz devolvió una respuesta inesperada.';
  }
  if (error.kind === 'config') return error.message;
  if (error.kind === 'network') return 'No hay conexión con el servidor de Chromatic Underground. Comprueba que está arrancado y la URL en Perfil.';
  if (error.kind === 'timeout') return `${error.message}. La primera consulta a MusicBrainz puede tardar; vuelve a intentarlo.`;
  return error.message;
}
