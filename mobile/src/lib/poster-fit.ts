/**
 * Carteles 4 · Para ti (V6.8): qué artistas del cartel te encajan y por qué. Se cruza en el móvil lo que vive en este
 * dispositivo (Guardados, artistas de partida, estilos que te gustan) con el sonido de cada artista (Discogs y Deezer,
 * `ArtistSound`). Cada motivo es un dato comprobable; sin motivo, el artista no aparece. Lógica pura.
 */
import { joinEs } from './format.ts';
import { linkedMbid } from './poster-identity.ts';
import type { SavedTrack } from './preferences.ts';
import type { ArtistSound, PosterArtist, PosterEvent, PosterSet } from '../types/poster.ts';

export type Taste = {
  favorites: { mbid: string; name: string }[];
  saved: SavedTrack[];
  styles: string[];
};

export type FitKind = 'saved' | 'favorite' | 'related' | 'label' | 'style';
export type FitReason = { kind: FitKind; text: string };
export type ArtistFit = { artist: PosterArtist; reasons: FitReason[]; score: number; sets: PosterSet[] };

/** Peso de cada motivo: lo que has guardado o elegido pesa más que un estilo en común. */
const WEIGHT: Record<FitKind, number> = { saved: 5, favorite: 5, related: 3, label: 2, style: 1 };
/** Desde aquí, «te encaja»; por debajo (solo un estilo en común), «en tus estilos». */
export const FIT_MIN = 2;

export function fold(text: string | null | undefined): string {
  return (text ?? '').normalize('NFD').replace(/\p{M}/gu, '').toLowerCase().replace(/&/g, ' and ')
    .replace(/[^\p{L}\p{N}]+/gu, ' ').trim();
}

/** Sonido guardado del artista, solo si es de su identidad actual. */
export function soundOf(a: PosterArtist): ArtistSound | null {
  const mbid = linkedMbid(a);
  return mbid && a.sound?.mbid === mbid ? a.sound : null;
}

const quote = (t: SavedTrack) => `«${t.title}»`;

export function fitReasons(a: PosterArtist, taste: Taste): FitReason[] {
  const mbid = linkedMbid(a);
  const names = new Set([fold(a.name), fold(a.link.name)].filter(Boolean));
  const sound = soundOf(a);
  const out: FitReason[] = [];

  const own = taste.saved.filter((t) => t.artists.some((c) => (mbid && c.mbid === mbid) || names.has(fold(c.name))));
  if (own.length) {
    out.push({ kind: 'saved', text: own.length === 1 ? `Tienes guardada ${quote(own[0])}`
      : `Tienes guardadas ${quote(own[0])} y ${own.length - 1} más` });
  }
  if (mbid && taste.favorites.some((f) => f.mbid === mbid)) out.push({ kind: 'favorite', text: 'Es uno de tus artistas de partida' });
  if (!sound) return out;

  // Afines de Deezer que están entre tus artistas (de partida o de tus canciones guardadas), sin contarse a sí mismo.
  const yours = new Map<string, string>();
  for (const f of taste.favorites) yours.set(fold(f.name), f.name);
  for (const t of taste.saved) for (const c of t.artists) yours.set(fold(c.name), c.name);
  const related = [...new Set(sound.related.map(fold))].filter((r) => yours.has(r) && !names.has(r)).map((r) => yours.get(r)!);
  if (related.length) out.push({ kind: 'related', text: `Deezer lo relaciona con ${joinEs(related.slice(0, 2))}` });

  const labels = new Map(sound.labels.map((l) => [fold(l), l]));
  const onLabel = taste.saved.find((t) => t.label && labels.has(fold(t.label)) && !own.includes(t));
  if (onLabel) out.push({ kind: 'label', text: `Publica en ${labels.get(fold(onLabel.label))}, como ${quote(onLabel)}` });

  const heard = new Set([...sound.genre, ...sound.styles, ...(a.styles ?? [])].map(fold));
  const style = taste.styles.find((s) => heard.has(fold(s)));
  if (style) out.push({ kind: 'style', text: `${style}, uno de tus estilos` });
  return out;
}

/** Artistas del cartel con algún motivo, del que más encaja al que menos (empate: orden del cartel). */
export function eventFits(e: PosterEvent, taste: Taste): ArtistFit[] {
  const order = new Map(e.artists.map((a, i) => [a.id, i]));
  return e.artists
    .map((artist) => {
      const reasons = fitReasons(artist, taste);
      return { artist, reasons, score: reasons.reduce((n, r) => n + WEIGHT[r.kind], 0),
        sets: e.sets.filter((s) => s.artistIds.includes(artist.id)).sort((x, y) => x.order - y.order) };
    })
    .filter((f) => f.reasons.length)
    .sort((x, y) => y.score - x.score || order.get(x.artist.id)! - order.get(y.artist.id)!);
}

/** Cuántos artistas enlazados tienen ya su sonido (progreso de «Para ti»). */
export function soundProgress(e: PosterEvent): { done: number; total: number } {
  const linked = e.artists.filter((a) => linkedMbid(a));
  return { done: linked.filter((a) => soundOf(a)).length, total: linked.length };
}

/** Guarda el sonido de un artista (si sigue siendo esa identidad). Sin estilos del perfil, el género sirve de filtro. */
export function setArtistSound(e: PosterEvent, artistId: string, sound: ArtistSound): PosterEvent {
  const a = e.artists.find((x) => x.id === artistId);
  if (!a || linkedMbid(a) !== sound.mbid) return e;
  return { ...e, artists: e.artists.map((x) => (x.id === artistId
    ? { ...x, sound, ...(x.styles?.length || !sound.genre.length ? {} : { styles: sound.genre.slice(0, 6) }) } : x)) };
}
