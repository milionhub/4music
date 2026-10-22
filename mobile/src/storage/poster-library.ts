/**
 * Biblioteca de Carteles (3.3), solo en este dispositivo. Claves propias en expo-sqlite/kv-store (las de Guardados y
 * preferencias no se tocan) y archivos en Documents/posters/<id>/ (no en la caché, que el sistema puede vaciar).
 *
 * Orden de escritura: 1) imagen y miniatura, 2) evento, 3) índice. Las escrituras devuelven el error en lugar de
 * ignorarlo: la interfaz avisa y el evento sigue en memoria. Al abrir la biblioteca se reconcilian índice, claves y
 * carpetas (un cierre a medias no deja eventos invisibles ni archivos huérfanos).
 */
import { Directory, File, Paths } from 'expo-file-system';
import Storage from 'expo-sqlite/kv-store';

import {
  idsFromKeys, indexEntry, parseIndex, parsePosterEvent, POSTER_INDEX_KEY, posterKey, removeFromIndex,
  serializePosterEvent, upsertIndex,
} from '@/lib/poster-store';
import type { PosterEvent, PosterIndexEntry } from '@/types/poster';

export type WriteResult = { ok: true } | { ok: false; message: string };

const POSTER_FILE = 'poster.jpg';
const THUMB_FILE = 'thumb.jpg';

const root = () => new Directory(Paths.document, 'posters');
const folder = (id: string) => new Directory(Paths.document, 'posters', id);

/** URI actual de los archivos (la ruta de Documents puede cambiar entre actualizaciones en iOS: no se guarda). */
export const posterImageUri = (id: string) => new File(folder(id), POSTER_FILE).uri;
export const posterThumbUri = (id: string) => new File(folder(id), THUMB_FILE).uri;

function fail(error: unknown, what: string): WriteResult {
  const detail = error instanceof Error ? error.message : String(error);
  return { ok: false, message: `No se pudo guardar ${what} en el dispositivo (${detail}).` };
}

function writeIndex(index: PosterIndexEntry[]): void {
  Storage.setItemSync(POSTER_INDEX_KEY, JSON.stringify(index));
}

export function loadEvent(id: string): PosterEvent | null {
  try {
    return parsePosterEvent(Storage.getItemSync(posterKey(id)));
  } catch {
    return null;
  }
}

/** Índice reconciliado con las claves guardadas; reconstruye entradas perdidas y quita las que ya no existen. */
export function loadIndex(): PosterIndexEntry[] {
  try {
    const ids = new Set(idsFromKeys(Storage.getAllKeysSync()));
    let index = parseIndex(Storage.getItemSync(POSTER_INDEX_KEY));
    const known = new Set(index.map((x) => x.id));
    const stale = index.some((x) => !ids.has(x.id)) || [...ids].some((id) => !known.has(id));
    if (!stale) return index;
    index = index.filter((x) => ids.has(x.id));
    for (const id of ids) {
      if (known.has(id)) continue;
      const e = loadEvent(id);
      if (e) index = upsertIndex(index, indexEntry(e));
    }
    try {
      writeIndex(index);
    } catch {
      // se reintentará al próximo arranque
    }
    return index;
  } catch {
    return [];
  }
}

/** Guarda (o actualiza) el evento y su entrada del índice. */
export function saveEvent(e: PosterEvent): WriteResult {
  try {
    Storage.setItemSync(posterKey(e.id), serializePosterEvent(e));
  } catch (error) {
    return fail(error, 'el evento');
  }
  try {
    writeIndex(upsertIndex(parseIndex(Storage.getItemSync(POSTER_INDEX_KEY)), indexEntry(e)));
  } catch {
    // El evento ya está guardado: loadIndex() reconstruirá su entrada.
  }
  return { ok: true };
}

/** Primer guardado: copia imagen y miniatura a Documents y después guarda el evento. Si algo falla, no deja restos. */
export function saveNewEvent(e: PosterEvent, imageUri: string, thumbUri: string): WriteResult {
  const dir = folder(e.id);
  try {
    dir.create({ intermediates: true, idempotent: true });
    new File(imageUri).copySync(new File(dir, POSTER_FILE));
    new File(thumbUri).copySync(new File(dir, THUMB_FILE));
  } catch (error) {
    safeDelete(dir);
    return fail(error, 'la imagen');
  }
  const saved = saveEvent(e);
  if (!saved.ok) safeDelete(dir);
  return saved;
}

function safeDelete(dir: Directory): void {
  try {
    if (dir.exists) dir.delete();
  } catch {
    // limpieza en el siguiente cleanupOrphans()
  }
}

/** Elimina el evento, su entrada del índice y sus archivos. */
export function deleteEvent(id: string): WriteResult {
  try {
    Storage.removeItemSync(posterKey(id));
    writeIndex(removeFromIndex(parseIndex(Storage.getItemSync(POSTER_INDEX_KEY)), id));
  } catch (error) {
    return { ok: false, message: `No se pudo eliminar el evento (${error instanceof Error ? error.message : String(error)}).` };
  }
  safeDelete(folder(id));
  return { ok: true };
}

/** Borra carpetas sin evento (p. ej., un cierre entre la copia de la imagen y el guardado). Devuelve los bytes en uso. */
export function cleanupOrphans(index: PosterIndexEntry[]): number {
  try {
    const dir = root();
    if (!dir.exists) return 0;
    const ids = new Set(index.map((x) => x.id));
    let bytes = 0;
    for (const child of dir.list()) {
      if (!(child instanceof Directory)) continue;
      if (!ids.has(child.name)) safeDelete(child);
      else bytes += child.size ?? 0;
    }
    return bytes;
  } catch {
    return 0;
  }
}
