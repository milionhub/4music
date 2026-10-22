/**
 * Carteles 3.4: identidad musical de los artistas de un evento. Lógica pura (sin red ni almacenamiento), probada en
 * tests/posters.test.ts.
 *
 * Reglas: el backend solo enlaza lo inequívoco (POST /v1/posters/resolve); aquí se guarda el resultado con su
 * evidencia. Lo que el usuario elige o deja sin identificar (`origin: 'user'`) nunca lo cambia una resolución
 * automática. Un B2B no tiene identidad propia: cada artista de la actuación se resuelve por separado.
 */
import { normName } from './poster-model.ts';
import type { ArtistLink, LinkCandidate, PosterArtist, PosterEvent } from '../types/poster.ts';

/** Nombres por petición: lotes pequeños para que el artista que abre el usuario no espere a todo el festival. */
export const RESOLVE_BATCH = 4;

export type ApiCandidate = {
  mbid: string;
  name: string;
  disambiguation: string | null;
  type: string | null;
  country: string | null;
  score: number | null;
  match: 'name' | 'alias' | 'similar';
  alias: string | null;
  scene: boolean;
};

export type Resolution = {
  name: string;
  status: 'linked' | 'ambiguous' | 'none' | 'error';
  mbid: string | null;
  canonical: string | null;
  candidates: ApiCandidate[];
  evidence: string | null;
  source: string | null;
};

export const pendingLink = (): ArtistLink => ({ status: 'pending', catalog: null, refId: null });

const isObj = (v: unknown): v is Record<string, unknown> => typeof v === 'object' && v !== null && !Array.isArray(v);
const str = (v: unknown): string | null => (typeof v === 'string' && v ? v : null);
const STATUSES = ['pending', 'linked', 'ambiguous', 'none'] as const;

/** Lectura tolerante de un enlace guardado (eventos de 3.3 o datos dañados): ante la duda, `pending`. */
export function parseLink(raw: unknown): ArtistLink {
  if (!isObj(raw) || !STATUSES.includes(raw.status as ArtistLink['status'])) return pendingLink();
  const status = raw.status as ArtistLink['status'];
  const refId = str(raw.refId);
  if (status === 'pending' || (status === 'linked' && !refId)) return pendingLink();
  const candidates = Array.isArray(raw.candidates)
    ? raw.candidates.filter((c): c is LinkCandidate => isObj(c) && !!str(c.refId) && !!str(c.name))
    : [];
  return {
    status,
    catalog: raw.catalog === 'musicbrainz' || raw.catalog === 'discogs' ? raw.catalog : null,
    refId: status === 'linked' ? refId : null,
    name: str(raw.name),
    candidates,
    evidence: str(raw.evidence),
    origin: raw.origin === 'user' ? 'user' : 'ai',
    query: str(raw.query),
  };
}

/** MBID enlazado (solo MusicBrainz abre perfil y TrackDNA). */
export function linkedMbid(a: Pick<PosterArtist, 'link'>): string | null {
  return a.link.status === 'linked' && a.link.catalog === 'musicbrainz' ? a.link.refId : null;
}

export function needsResolution(a: PosterArtist): boolean {
  return a.link.status === 'pending' && a.link.origin !== 'user';
}

/** Orden de resolución: primero los pedidos (el artista abierto), después el orden del cartel; sin repetir. */
export function resolutionQueue(e: PosterEvent, first: string[] = []): string[] {
  const bySet = [...e.sets].sort((x, y) => x.order - y.order).flatMap((s) => s.artistIds);
  const ids = [...new Set([...first, ...bySet, ...e.artists.map((a) => a.id)])];
  return ids.filter((id) => {
    const a = e.artists.find((x) => x.id === id);
    return !!a && needsResolution(a);
  });
}

const fromApi = (c: ApiCandidate): LinkCandidate => ({
  refId: c.mbid, name: c.name, disambiguation: c.disambiguation, country: c.country, type: c.type, match: c.match, scene: c.scene,
});

/**
 * Aplica una resolución del backend. No hace nada si el usuario ya decidió, si el nombre cambió mientras tanto o si
 * MusicBrainz falló (`error`: sigue pendiente). No cambia `updatedAt`: no es una edición del usuario.
 */
export function applyResolution(e: PosterEvent, artistId: string, r: Resolution): PosterEvent {
  const a = e.artists.find((x) => x.id === artistId);
  if (!a || a.link.origin === 'user' || r.status === 'error' || normName(a.name) !== normName(r.name)) return e;
  const linked = r.status === 'linked' && !!r.mbid;
  const link: ArtistLink = {
    status: linked ? 'linked' : r.status === 'linked' ? 'none' : r.status,
    catalog: linked ? 'musicbrainz' : null,
    refId: linked ? r.mbid : null,
    name: linked ? r.canonical : null,
    candidates: r.candidates.map(fromApi),
    evidence: r.evidence,
    origin: 'ai',
    query: normName(a.name),
  };
  return { ...e, artists: e.artists.map((x) => (x.id === artistId ? { ...x, link } : x)) };
}

function setLink(e: PosterEvent, artistId: string, now: string, f: (l: ArtistLink) => ArtistLink): PosterEvent {
  if (!e.artists.some((a) => a.id === artistId)) return e;
  return { ...e, artists: e.artists.map((a) => (a.id === artistId ? { ...a, link: f(a.link) } : a)), updatedAt: now };
}

/** El usuario elige la identidad (candidato o búsqueda manual). Queda protegida frente a la resolución automática. */
export function chooseIdentity(e: PosterEvent, artistId: string, c: LinkCandidate, now: string): PosterEvent {
  return setLink(e, artistId, now, (l) => ({
    ...l, status: 'linked', catalog: 'musicbrainz', refId: c.refId, name: c.name, origin: 'user',
    evidence: 'Identidad elegida por ti', candidates: l.candidates?.length ? l.candidates : [c],
  }));
}

/** El usuario lo deja sin identificar: el nombre sigue en el line-up y no se vuelve a buscar solo. */
export function leaveUnidentified(e: PosterEvent, artistId: string, now: string): PosterEvent {
  return setLink(e, artistId, now, (l) => ({
    ...l, status: 'none', catalog: null, refId: null, name: null, origin: 'user', evidence: 'Dejado sin identificar por ti',
  }));
}

/** Deshace la decisión del usuario y vuelve a la resolución automática. */
export function resetIdentity(e: PosterEvent, artistId: string, now: string): PosterEvent {
  return setLink(e, artistId, now, () => pendingLink());
}

/** Nota corta para la fila de una actuación (solo lo que necesita atención). */
export function linkNote(a: PosterArtist): string | null {
  if (a.link.status === 'ambiguous') return 'varios candidatos';
  if (a.link.status === 'none') return 'sin identificar';
  return null;
}

export function identityCounts(e: PosterEvent): { linked: number; ambiguous: number; none: number; pending: number } {
  const n = { linked: 0, ambiguous: 0, none: 0, pending: 0 };
  for (const a of e.artists) n[a.link.status] += 1;
  return n;
}
