/**
 * Carteles 3.1: elegir imagen (galería o cámara), normalizarla y prepararla para el análisis.
 * - Normalizada: JPEG de 2048 px como máximo en el lado mayor (calidad 0,85; si pasa de 4 MB, 1600 px y 0,7).
 *   HEIC, PNG o WebP de la galería salen siempre como JPEG. Miniatura: 480 px.
 * - Huella: MD5 del archivo elegido (antes de normalizar) para detectar el mismo cartel sin gastar una llamada.
 * El original de la galería no se toca; la app guarda solo la copia normalizada.
 */
import { File } from 'expo-file-system';
import { ImageManipulator, SaveFormat } from 'expo-image-manipulator';
import * as ImagePicker from 'expo-image-picker';

export const MAX_UPLOAD_BYTES = 4 * 1024 * 1024;

export type PickedImage = { uri: string; width: number; height: number; assetId: string | null; fingerprint: string | null };
export type PickResult = { ok: true; image: PickedImage } | { ok: false; reason: 'canceled' | 'denied' | 'error'; message?: string };
export type NormalizedImage = { uri: string; thumbUri: string; width: number; height: number; bytes: number };

export async function pickImage(source: 'library' | 'camera'): Promise<PickResult> {
  try {
    if (source === 'camera') {
      const perm = await ImagePicker.requestCameraPermissionsAsync();
      if (!perm.granted) return { ok: false, reason: 'denied' };
    }
    const options: ImagePicker.ImagePickerOptions = { mediaTypes: ['images'], quality: 1, exif: false, allowsEditing: false };
    const result = source === 'camera' ? await ImagePicker.launchCameraAsync(options) : await ImagePicker.launchImageLibraryAsync(options);
    if (result.canceled || !result.assets?.length) return { ok: false, reason: 'canceled' };
    const a = result.assets[0];
    return { ok: true, image: { uri: a.uri, width: a.width, height: a.height, assetId: a.assetId ?? null, fingerprint: fingerprintOf(a.uri) } };
  } catch (error) {
    return { ok: false, reason: 'error', message: error instanceof Error ? error.message : String(error) };
  }
}

function fingerprintOf(uri: string): string | null {
  try {
    return new File(uri).info({ md5: true }).md5 ?? null;
  } catch {
    return null;
  }
}

async function render(uri: string, rotation: number, width: number, height: number, maxSide: number, compress: number) {
  let ctx = ImageManipulator.manipulate(uri);
  if (rotation) ctx = ctx.rotate(rotation);
  const [w, h] = rotation % 180 ? [height, width] : [width, height];
  if (Math.max(w, h) > maxSide) ctx = ctx.resize(w >= h ? { width: maxSide } : { height: maxSide });
  const ref = await ctx.renderAsync();
  return ref.saveAsync({ format: SaveFormat.JPEG, compress });
}

export async function normalizeImage(img: PickedImage, rotation: number): Promise<NormalizedImage> {
  let out = await render(img.uri, rotation, img.width, img.height, 2048, 0.85);
  let bytes = new File(out.uri).size;
  if (bytes > MAX_UPLOAD_BYTES) {
    out = await render(img.uri, rotation, img.width, img.height, 1600, 0.7);
    bytes = new File(out.uri).size;
  }
  if (bytes > MAX_UPLOAD_BYTES) throw new Error('La imagen sigue ocupando más de 4 MB tras reducirla');
  const thumb = await render(out.uri, 0, out.width, out.height, 480, 0.75);
  return { uri: out.uri, thumbUri: thumb.uri, width: out.width, height: out.height, bytes };
}

export const readBase64 = (uri: string) => new File(uri).base64();

/** Zonas fijas con solape (sin recortador manual): cubren el cartel en franjas para reanalizar lo dudoso. */
export const REGIONS = {
  top: { label: 'Parte superior', x: 0, y: 0, w: 1, h: 0.4 },
  middle: { label: 'Centro', x: 0, y: 0.3, w: 1, h: 0.4 },
  bottom: { label: 'Parte inferior', x: 0, y: 0.6, w: 1, h: 0.4 },
  left: { label: 'Mitad izquierda', x: 0, y: 0, w: 0.55, h: 1 },
  right: { label: 'Mitad derecha', x: 0.45, y: 0, w: 0.55, h: 1 },
} as const;
export type RegionKey = keyof typeof REGIONS;

export async function cropRegionBase64(uri: string, width: number, height: number, region: RegionKey): Promise<string> {
  const r = REGIONS[region];
  const rect = {
    originX: Math.round(r.x * width), originY: Math.round(r.y * height),
    width: Math.round(r.w * width), height: Math.round(r.h * height),
  };
  const ref = await ImageManipulator.manipulate(uri).crop(rect).renderAsync();
  const saved = await ref.saveAsync({ format: SaveFormat.JPEG, compress: 0.85, base64: true });
  if (!saved.base64) throw new Error('No se pudo recortar la imagen');
  return saved.base64;
}
