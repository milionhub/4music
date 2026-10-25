/** Formato puro de datos musicales para la interfaz (probado con `node --test`). Nunca inventa valores. */
import type { ArtistIdentity, CreditedArtist, Link, RecentRelease, SectionStatus } from '@/types/music';

/** Elementos sin repetir según su identidad real (MBID, URL…): el primero gana. Para listas que no deben duplicar. */
export function uniqueBy<T>(items: T[], keyOf: (item: T) => string): T[] {
  const seen = new Set<string>();
  return items.filter((item) => {
    const key = keyOf(item);
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

/** Claves estables y únicas para listas de React, aunque la fuente repita valores (p. ej. la misma URL). */
export function withUniqueKeys<T>(items: T[], keyOf: (item: T) => string): { key: string; item: T }[] {
  const used = new Map<string, number>();
  return items.map((item) => {
    const base = keyOf(item) || 'item';
    const n = used.get(base) ?? 0;
    used.set(base, n + 1);
    return { key: n === 0 ? base : `${base}#${n}`, item };
  });
}

/** Línea de contexto solo con los datos que existen (nunca «desconocido» ni «undefined»). */
export function artistFacts(a: { type: string | null; country: string | null; area: string | null; begin_date?: string | null }): string {
  const place = a.area && a.country && a.area !== a.country ? `${a.area} (${a.country})` : (a.area ?? a.country);
  return [a.type, place, a.begin_date ? `desde ${a.begin_date}` : null].filter(Boolean).join(' · ');
}

const GROUP_TYPES: Record<string, string> = { Group: 'Grupo', Orchestra: 'Orquesta', Choir: 'Coro' };

/** Línea de identidad de la ficha: cada lugar con su significado (nacimiento ≠ formación ≠ área asociada).
 *  La fecha de inicio de una persona en MusicBrainz es su nacimiento: nunca se muestra como «desde». */
export function identityFacts(a: { type: string | null; country: string | null }, id: ArtistIdentity | null | undefined): string {
  if (!id) return artistFacts({ type: a.type, country: a.country, area: null });
  const place = [id.area, id.country_name ?? a.country].filter(Boolean).join(', ');
  let origin: string | null = null;
  if (id.origin_kind === 'birth' && id.origin) origin = `Nacimiento: ${id.origin}`;
  else if (id.origin || id.formed_year) {
    origin = `Formación: ${[id.origin, id.formed_year].filter(Boolean).join(', ')}`;
  }
  const active = id.active_since && id.active_since !== id.formed_year ? `En activo desde ${id.active_since}` : null;
  return [a.type ? GROUP_TYPES[a.type] : null, place, origin, active].filter(Boolean).join(' · ');
}

/** Sellos fundados, proyectos e integrantes documentados, una línea por tipo (vacío si no hay ninguno). */
export function sceneFacts(id: ArtistIdentity | null | undefined): string[] {
  if (!id) return [];
  const line = (label: string, items?: string[]) => (items?.length ? `${label}: ${items.join(', ')}` : null);
  return [
    line(id.founded_labels?.length === 1 ? 'Sello fundado' : 'Sellos fundados', id.founded_labels),
    line('Proyectos', id.projects),
    line('Integrantes', id.members),
  ].filter((x): x is string => Boolean(x));
}

/** Separa los enlaces destacados (plataformas musicales) del resto, sin repetir URL. */
export function splitLinks(links: Link[]): { primary: Link[]; more: Link[] } {
  const seen = new Set<string>();
  const unique = links.filter((l) => {
    const key = l.url.replace(/\/+$/, '').toLowerCase();
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
  return { primary: unique.filter((l) => l.primary), more: unique.filter((l) => !l.primary) };
}

const PRIMARY_TYPES: Record<string, string> = { Album: 'Álbum', EP: 'EP', Single: 'Single', Broadcast: 'Emisión', Other: 'Otro' };
const SECONDARY_TYPES: Record<string, string> = {
  Compilation: 'Recopilatorio', Remix: 'Remezclas', 'DJ-mix': 'DJ mix', Live: 'Directo', 'Mixtape/Street': 'Mixtape',
  Soundtrack: 'Banda sonora', Demo: 'Demo', Interview: 'Entrevista', Spokenword: 'Palabra hablada',
};

/** A qué lleva un enlace de TrackDNA: «Canción» solo si abre la pista; si no, el tipo de lanzamiento. */
export function linkTarget(l: Pick<Link, 'target' | 'release_type'>): string | null {
  if (l.target === 'track') return 'Canción';
  if (l.target !== 'release') return null;
  return (l.release_type && PRIMARY_TYPES[l.release_type]) || 'Lanzamiento';
}

/** «Single · Remezclas», «Álbum»… según los tipos que documenta MusicBrainz (null si no hay ninguno). */
export function releaseKind(r: Pick<RecentRelease, 'primary_type' | 'secondary_types'>): string | null {
  const parts = [r.primary_type ? (PRIMARY_TYPES[r.primary_type] ?? r.primary_type) : null,
    ...r.secondary_types.map((t) => SECONDARY_TYPES[t] ?? t)];
  return parts.filter(Boolean).join(' · ') || null;
}

/** Mensaje honesto para una sección vacía o con error (null si la sección tiene datos). */
export function sectionMessage(status: SectionStatus, what: string): { tone: 'info' | 'warn'; text: string; retry: boolean } | null {
  if (status.status === 'ok') return null;
  if (status.status === 'empty') return { tone: 'info', text: `MusicBrainz no documenta ${what} para este artista.`, retry: false };
  if (status.error_code === 'provider_bad_response') {
    return { tone: 'warn', text: `MusicBrainz devolvió ${what} con un formato inesperado; no se muestran.`, retry: false };
  }
  return { tone: 'warn', text: `MusicBrainz no respondió al pedir ${what} (error temporal).`, retry: true };
}

export function duration(ms: number | null): string | null {
  if (!ms) return null;
  const s = Math.round(ms / 1000);
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`;
}

/** Recuento compacto para la interfaz: 950 → «950», 1234 → «1,2 K», 15 400 → «15 K». */
export function formatCount(n: number): string {
  if (n < 1000) return String(n);
  if (n < 10000) return `${(n / 1000).toFixed(1).replace('.', ',').replace(',0', '')} K`;
  return `${Math.round(n / 1000)} K`;
}

/** Búsqueda (no enlace exacto) en una plataforma, para cuando no hay URL verificada de la canción. */
export function platformSearchUrl(platform: 'spotify' | 'soundcloud', query: string): string {
  const q = encodeURIComponent(query);
  return platform === 'spotify' ? `https://open.spotify.com/search/${q}` : `https://soundcloud.com/search?q=${q}`;
}

/** «Escuchar» del perfil de artista: siempre estas cuatro, en este orden. */
const ARTIST_PLATFORMS = [
  { label: 'Spotify', search: (q: string) => `https://open.spotify.com/search/${q}/artists` },
  { label: 'Apple Music', search: (q: string) => `https://music.apple.com/search?term=${q}` },
  { label: 'SoundCloud', search: (q: string) => `https://soundcloud.com/search/people?q=${q}` },
  { label: 'Discogs', search: (q: string) => `https://www.discogs.com/search/?q=${q}&type=artist` },
] as const;

/**
 * Plataformas del perfil: Spotify, Apple Music, SoundCloud y Discogs. El enlace directo si MusicBrainz lo documenta
 * (el perfil del artista, no una canción); si no, una búsqueda por nombre, marcada como tal (`detail: 'Búsqueda'`) para
 * no presentarla como su perfil. El resto de webs sigue en «Información técnica».
 */
export function artistPlatforms(links: Link[], name: string): Link[] {
  const q = encodeURIComponent(name.trim());
  return ARTIST_PLATFORMS.flatMap((p): Link[] => {
    const direct = links.find((l) => l.platform === p.label || l.label === p.label);
    if (direct) return [{ ...direct, label: p.label, detail: null }];
    return q ? [{ url: p.search(q), label: p.label, platform: p.label, kinds: [], detail: 'Búsqueda', primary: true }] : [];
  });
}

// --- TrackDNA de canciones (T2.0) ---

/** «2009 · 10:34 · Álbum»: solo con los datos que existen. */
export function trackFacts(t: { first_release_date: string | null; length_ms: number | null; release_type?: string | null }): string {
  const type = t.release_type ? (PRIMARY_TYPES[t.release_type] ?? t.release_type) : null;
  return [t.first_release_date?.slice(0, 4) || null, duration(t.length_ms), type].filter(Boolean).join(' · ');
}

/** Sellos de un lanzamiento tal como se muestran; la autoedición documentada se nombra como tal. */
export function releaseLabels(r: { labels: string[]; self_released?: boolean }): string[] {
  return r.labels.length ? r.labels : r.self_released ? ['Autoedición'] : [];
}

/** «A», «A y B», «A, B y C». */
export function joinEs(items: string[]): string {
  if (items.length <= 1) return items[0] ?? '';
  return `${items.slice(0, -1).join(', ')} y ${items[items.length - 1]}`;
}

export type CardRow = { label: string; value: string };

/**
 * Filas de «Conoce al artista»: solo datos que constan, con su significado exacto (nacimiento ≠ formación ≠ ciudad
 * asociada; fundar ≠ estar al frente). Nada vacío, «desconocido» ni repetido.
 */
export function artistCardRows(a: { type: string | null; identity?: ArtistIdentity }): CardRow[] {
  const id = a.identity;
  if (!id) return [];
  const rows: CardRow[] = [];
  const members = id.members ?? [];
  if (a.type === 'Group') rows.push({ label: 'Formato', value: members.length === 2 ? 'Dúo' : 'Grupo' });
  if (id.country_name) rows.push({ label: 'País', value: id.country_name });
  if (id.origin && id.origin_kind) {
    const year = id.origin_kind === 'formation' && id.formed_year ? `, ${id.formed_year}` : '';
    rows.push({ label: id.origin_kind === 'birth' ? 'Lugar de nacimiento' : 'Formación', value: `${id.origin}${year}` });
  }
  if (id.area && id.area !== id.origin && id.area !== id.country_name) rows.push({ label: 'Ciudad asociada', value: id.area });
  const withYear = (label: string) => (id.label_years?.[label] ? `${label} (${id.label_years[label]})` : label);
  const founded = id.founded_labels ?? [];
  if (founded.length) rows.push({ label: founded.length === 1 ? 'Sello fundado' : 'Sellos fundados', value: founded.map(withYear).join(' · ') });
  const run = id.run_labels ?? [];
  if (run.length) rows.push({ label: run.length === 1 ? 'Al frente del sello' : 'Al frente de los sellos', value: run.map(withYear).join(' · ') });
  if (members.length) rows.push({ label: 'Integrantes', value: joinEs(members) });
  if (id.projects?.length) rows.push({ label: 'Proyectos', value: id.projects.join(' · ') });
  if (id.active_since && id.active_since !== id.formed_year) rows.push({ label: 'En activo desde', value: id.active_since });
  return rows;
}

// --- TrackDNA v5 --------------------------------------------------------------------------------------------------

/** Artistas especiales de MusicBrainz («Various Artists», «[unknown]»): no son una persona ni tienen ficha. */
const SPECIAL_ARTISTS = new Set(['89ad4ac3-39f7-470e-963a-56509c546377', '125ec42a-7229-4250-afc5-e057484327fe']);
const MBID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

/** Canción fuera de MusicBrainz: `discogs:<release>:<posición>` (V5.6) o `deezer:<id>` (V6.1). Tiene ruta propia y no
 * se guarda (aún). */
export function externalTrack(id: string | null | undefined): boolean {
  return externalCatalog(id) !== null;
}

/** Catálogo externo de una canción, o null si es de MusicBrainz. */
export function externalCatalog(id: string | null | undefined): 'Discogs' | 'Deezer' | null {
  if (!id) return null;
  return id.startsWith('discogs:') ? 'Discogs' : id.startsWith('deezer:') ? 'Deezer' : null;
}

/** Solo se enlaza un artista con MBID válido (identidad de MusicBrainz), nunca por coincidencia de nombre. */
export function linkableArtist(mbid: string | null | undefined): boolean {
  return !!mbid && MBID_RE.test(mbid) && !SPECIAL_ARTISTS.has(mbid.toLowerCase());
}

const FEAT_RE = /\b(feat\.?|ft\.?|featuring|con)\s*$/i;

/**
 * Créditos para pintar: nombre, si es navegable, la frase de unión («&», « feat. ») y si es artista invitado
 * (aparece tras «feat.» en el crédito de MusicBrainz: dato del crédito, no una deducción sobre su papel).
 */
export function creditParts(credit: CreditedArtist[], fallback: string): { name: string; mbid: string | null; join: string; guest: boolean }[] {
  if (!credit.length) return fallback ? [{ name: fallback, mbid: null, join: '', guest: false }] : [];
  let guest = false;
  return credit.map((a, i) => {
    if (i > 0 && FEAT_RE.test(credit[i - 1].join_phrase.trim())) guest = true;
    return { name: a.name, mbid: linkableArtist(a.mbid) ? a.mbid : null, join: a.join_phrase, guest };
  });
}

export type ListenOption = { key: string; label: string; url: string; target: string; direct: boolean };

const LISTEN_PLATFORMS: { key: string; label: string; aliases: string[]; search: 'spotify' | 'soundcloud' | null }[] = [
  { key: 'spotify', label: 'Spotify', aliases: ['Spotify'], search: 'spotify' },
  { key: 'apple', label: 'Apple Music', aliases: ['Apple Music', 'iTunes'], search: null },
  { key: 'soundcloud', label: 'SoundCloud', aliases: ['SoundCloud'], search: 'soundcloud' },
];
const PHYSICAL: [RegExp, string][] = [[/vinyl/i, 'vinilo'], [/\bcd\b/i, 'CD'], [/cassette/i, 'casete']];

/**
 * «Escuchar» (v5.1): solo Spotify, Apple Music, SoundCloud y Discogs. Primero el enlace documentado a la pista; si no,
 * el del lanzamiento (dicho así); si no hay ninguno, una búsqueda explícita en Spotify y SoundCloud. Discogs solo
 * aparece con una edición física documentada (vinilo, CD, casete), y nunca como venta o disponibilidad.
 */
export function listenOptions(links: Link[], query: string): ListenOption[] {
  const out: ListenOption[] = [];
  for (const p of LISTEN_PLATFORMS) {
    const own = links.filter((l) => p.aliases.includes(l.label));
    const best = own.find((l) => l.target === 'track') ?? own.find((l) => l.target === 'release') ?? own[0];
    if (best) out.push({ key: p.key, label: p.label, url: best.url, target: linkTarget(best) ?? 'Enlace', direct: true });
    else if (p.search && query.trim()) out.push({ key: p.key, label: p.label, url: platformSearchUrl(p.search, query), target: 'Búsqueda', direct: false });
  }
  for (const l of links) {
    if (l.label !== 'Discogs' || !/discogs\.com\/(?:[a-z-]+\/)?release\//i.test(l.url)) continue;
    const physical = PHYSICAL.find(([re]) => (l.formats ?? []).some((f) => re.test(f)));
    if (physical) {
      out.push({ key: 'discogs', label: 'Discogs', url: l.url, target: `Edición en ${physical[1]}`, direct: true });
      break;
    }
  }
  return out;
}
