export const HEALTH_TIMEOUT_MS = 5000;

export type HealthResult = { ok: true } | { ok: false; message: string };

export async function checkHealth(baseUrl: string): Promise<HealthResult> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), HEALTH_TIMEOUT_MS);

  try {
    const response = await fetch(`${baseUrl}/health`, {
      headers: { Accept: 'application/json' },
      signal: controller.signal,
    });
    if (!response.ok) {
      return { ok: false, message: `Respuesta HTTP ${response.status}` };
    }

    let body: unknown;
    try {
      body = await response.json();
    } catch {
      return { ok: false, message: 'La respuesta no es JSON válido' };
    }
    if (
      typeof body !== 'object' ||
      body === null ||
      (body as { status?: unknown }).status !== 'ok'
    ) {
      return { ok: false, message: 'Respuesta inesperada (se esperaba {"status":"ok"})' };
    }
    return { ok: true };
  } catch (error) {
    if (controller.signal.aborted) {
      return { ok: false, message: `Sin respuesta en ${HEALTH_TIMEOUT_MS / 1000} s (timeout)` };
    }
    const detail = error instanceof Error ? error.message : String(error);
    return { ok: false, message: `No se pudo conectar: ${detail}` };
  } finally {
    clearTimeout(timer);
  }
}
