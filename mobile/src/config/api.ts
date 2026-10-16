/**
 * URL base del backend. Se inyecta en el bundle desde EXPO_PUBLIC_API_URL
 * (mobile/.env); no guardes aquí secretos: es visible en la app compilada.
 * Debe leerse con notación de punto para que Expo la sustituya.
 */
const rawApiUrl = process.env.EXPO_PUBLIC_API_URL;

export type ApiConfig = { ok: true; baseUrl: string } | { ok: false; reason: string };

export function getApiConfig(): ApiConfig {
  const value = rawApiUrl?.trim();
  if (!value) {
    return { ok: false, reason: 'EXPO_PUBLIC_API_URL no está definida (revisa mobile/.env).' };
  }
  if (!/^https?:\/\/[^/\s]+/i.test(value)) {
    return { ok: false, reason: `EXPO_PUBLIC_API_URL no es una URL http(s) válida: "${value}"` };
  }
  return { ok: true, baseUrl: value.replace(/\/+$/, '') };
}
