/**
 * Carteles 4: sonido de los artistas del cartel, poco a poco mientras el evento está en pantalla (como la resolución
 * de identidades). De uno en uno y solo los enlazados que aún no lo tienen; se guarda en el evento para verlo sin red.
 * Se detiene al salir de la pantalla o ante un fallo (el siguiente intento, al volver). `kick`: hay artistas recién
 * enlazados (la pantalla lo llama cuando la resolución avanza).
 */
import { useFocusEffect } from 'expo-router';
import { useCallback, useRef, useState } from 'react';

import { linkedMbid } from '@/lib/poster-identity';
import { setArtistSound, soundOf } from '@/lib/poster-fit';
import { getPosterArtistSound } from '@/services/posters';
import { loadEvent, saveEvent } from '@/storage/poster-library';
import type { PosterEvent } from '@/types/poster';

export function usePosterSound(eventId: string | undefined, onEvent: (e: PosterEvent) => void) {
  const [running, setRunning] = useState(false);
  const focused = useRef(false);
  const busy = useRef(false);
  const failed = useRef(new Set<string>());

  const pump = useCallback(async () => {
    if (busy.current || !eventId) return;
    busy.current = true;
    setRunning(true);
    try {
      while (focused.current) {
        const current = loadEvent(eventId);
        const next = current?.artists.find((a) => linkedMbid(a) && !soundOf(a) && !failed.current.has(a.id));
        if (!current || !next) break;
        const mbid = linkedMbid(next)!;
        const r = await getPosterArtistSound(mbid);
        if (!r.ok || r.data.status !== 'ok') {
          failed.current.add(next.id); // un fallo no frena al resto; se reintenta en la próxima visita
          if (!r.ok && r.error.kind === 'network') break;
          continue;
        }
        const fresh = loadEvent(eventId);
        if (!fresh) break;
        const updated = setArtistSound(fresh, next.id, {
          mbid, genre: r.data.genre, styles: r.data.styles, labels: r.data.labels,
          related: r.data.related.map((x) => x.name), at: new Date().toISOString(),
        });
        if (updated === fresh) {
          failed.current.add(next.id); // la identidad cambió mientras tanto
          continue;
        }
        if (!saveEvent(updated).ok) break;
        onEvent(updated);
      }
    } finally {
      busy.current = false;
      setRunning(false);
    }
  }, [eventId, onEvent]);

  useFocusEffect(useCallback(() => {
    focused.current = true;
    void pump();
    return () => {
      focused.current = false;
    };
  }, [pump]));

  return { running, kick: pump };
}
