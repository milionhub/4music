/**
 * Persistencia local (sin cuenta) con expo-sqlite/kv-store. Claves versionadas (las mismas desde T1: no se
 * migran ni se borran datos). Lecturas y escrituras SÍNCRONAS: el orden de escritura queda garantizado.
 * v5: las canciones guardadas van en su propia clave; los artistas favoritos de T1 siguen en la suya, intactos.
 */
import Storage from 'expo-sqlite/kv-store';

import {
  type Discarded,
  type Favorite,
  parseDiscarded,
  parseFavorites,
  parsePreferences,
  parseSavedTracks,
  type Preferences,
  type SavedTrack,
  serializeList,
  serializePreferences,
} from '@/lib/preferences';

export type { Discarded, Favorite, OnboardingState, Preferences, SavedTrack } from '@/lib/preferences';

const KEYS = {
  preferences: 'md.preferences.v1',
  favorites: 'md.favorites.v1',
  discarded: 'md.discarded.v1',
  savedTracks: 'md.saved_tracks.v1',
} as const;

function read(key: string): string | null {
  try {
    return Storage.getItemSync(key);
  } catch {
    return null;
  }
}

function write(key: string, value: string): void {
  try {
    Storage.setItemSync(key, value);
  } catch {
    // Sin almacenamiento la app sigue funcionando en memoria durante la sesión.
  }
}

export const loadPreferences = () => parsePreferences(read(KEYS.preferences));
export const loadFavorites = () => parseFavorites(read(KEYS.favorites));
export const loadDiscarded = () => parseDiscarded(read(KEYS.discarded));
export const loadSavedTracks = () => parseSavedTracks(read(KEYS.savedTracks));

export const savePreferences = (p: Preferences) => write(KEYS.preferences, serializePreferences(p));
export const saveFavorites = (items: Favorite[]) => write(KEYS.favorites, serializeList(items));
export const saveDiscarded = (items: Discarded[]) => write(KEYS.discarded, serializeList(items));
export const saveSavedTracks = (items: SavedTrack[]) => write(KEYS.savedTracks, serializeList(items));
