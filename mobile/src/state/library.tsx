/**
 * Estado local del usuario: preferencias, canciones guardadas (Guardados, v5), artistas de partida y descartes.
 * Se lee de forma síncrona al arrancar (antes de decidir la navegación) y se persiste DESPUÉS de cada commit,
 * en un efecto, con escrituras síncronas y ordenadas. (T1 escribía dentro de los updaters de React, de forma
 * asíncrona: dos escrituras seguidas al terminar la bienvenida podían completarse en orden inverso y dejar
 * guardado `onboarding: 'pending'`.)
 */
import { createContext, type ReactNode, useContext, useEffect, useRef, useState } from 'react';

import { finishOnboarding, sameTrack, toggleFavorite, toggleSavedTrack } from '@/lib/preferences';
import {
  type Discarded,
  type Favorite,
  loadDiscarded,
  loadFavorites,
  loadPreferences,
  loadSavedTracks,
  type Preferences,
  type SavedTrack,
  saveDiscarded,
  saveFavorites,
  savePreferences,
  saveSavedTracks,
} from '@/storage/local-store';
import type { ArtistRef } from '@/types/music';

type Library = {
  preferences: Preferences;
  /** Guardados: canciones de TrackDNA, la más reciente primero. */
  savedTracks: SavedTrack[];
  isTrackSaved: (track: Pick<SavedTrack, 'mbid' | 'isrcs' | 'version'>) => boolean;
  toggleTrack: (track: SavedTrack) => void;
  removeTrack: (track: SavedTrack) => void;
  /** Artistas de partida de Inicio (no se muestran en Guardados). */
  favorites: Favorite[];
  discarded: Discarded[];
  isFavorite: (mbid: string) => boolean;
  toggleFavorite: (artist: ArtistRef) => void;
  removeFavorite: (mbid: string) => void;
  discard: (mbid: string) => void;
  resetDiscarded: () => void;
  setDeclaredStyles: (styles: string[]) => void;
  /** Termina la bienvenida y guarda los estilos en una única actualización. */
  completeOnboarding: (state: 'completed' | 'skipped', styles: string[]) => void;
};

const LibraryContext = createContext<Library | null>(null);

const now = () => new Date().toISOString();

/** Guarda `value` cada vez que cambia, salvo en el primer render (es lo que se acaba de leer). */
function usePersist<T>(value: T, save: (v: T) => void) {
  const first = useRef(true);
  useEffect(() => {
    if (first.current) {
      first.current = false;
      return;
    }
    save(value);
  }, [value, save]);
}

export function LibraryProvider({ children }: { children: ReactNode }) {
  const [preferences, setPreferences] = useState(loadPreferences);
  const [favorites, setFavorites] = useState(loadFavorites);
  const [discarded, setDiscarded] = useState(loadDiscarded);
  const [savedTracks, setSavedTracks] = useState(loadSavedTracks);

  usePersist(preferences, savePreferences);
  usePersist(favorites, saveFavorites);
  usePersist(discarded, saveDiscarded);
  usePersist(savedTracks, saveSavedTracks);

  const value: Library = {
    preferences,
    savedTracks,
    isTrackSaved: (track) => savedTracks.some((t) => sameTrack(t, track)),
    toggleTrack: (track) => setSavedTracks((prev) => toggleSavedTrack(prev, track)),
    removeTrack: (track) => setSavedTracks((prev) => prev.filter((t) => !sameTrack(t, track))),
    favorites,
    discarded,
    isFavorite: (mbid) => favorites.some((f) => f.mbid === mbid),
    toggleFavorite: (artist) => {
      const adding = !favorites.some((f) => f.mbid === artist.mbid);
      setFavorites((prev) => toggleFavorite(prev, artist, now()));
      // Guardar un artista descartado antes lo devuelve a la lista activa.
      if (adding) setDiscarded((prev) => prev.filter((d) => d.mbid !== artist.mbid));
    },
    removeFavorite: (mbid) => setFavorites((prev) => prev.filter((f) => f.mbid !== mbid)),
    discard: (mbid) =>
      setDiscarded((prev) => (prev.some((d) => d.mbid === mbid) ? prev : [...prev, { kind: 'artist', mbid, discarded_at: now() }])),
    resetDiscarded: () => setDiscarded([]),
    setDeclaredStyles: (styles) => setPreferences((prev) => ({ ...prev, declared_styles: [...new Set(styles)], updated_at: now() })),
    completeOnboarding: (state, styles) => setPreferences((prev) => finishOnboarding(prev, state, styles, now())),
  };

  return <LibraryContext.Provider value={value}>{children}</LibraryContext.Provider>;
}

export function useLibrary(): Library {
  const ctx = useContext(LibraryContext);
  if (!ctx) throw new Error('useLibrary debe usarse dentro de LibraryProvider');
  return ctx;
}
