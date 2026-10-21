/**
 * Ficha TrackDNA V5.4: qué se muestra de cada canción, decidido aquí y no en el JSX (lógica pura, probada con
 * `node --test`). Orden fijo: cabecera, ADN musical, la historia del track, artistas, versiones, escuchar. Cada bloque
 * vuelve vacío (y se oculta) si no hay nada real: nunca relleno, nunca un dato del artista o del álbum presentado como
 * dato de la canción. La API conserva todo lo demás (créditos completos, mashups, DJ mixes, procedencia).
 */
import type { TrackLink, TrackResponse } from '@/types/music';

import { creditParts, duration, linkableArtist, releaseKind } from './format.ts'; // relativo: también lo importan las pruebas de Node

const norm = (s: string) => s.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase().replace(/[^a-z0-9]+/g, ' ').trim();

// --- Versiones ----------------------------------------------------------------------------------------------------
export type VersionClass = 'original' | 'extended' | 'remix' | 'edit' | 'unofficial' | 'other';

/** Sufijo de versión al final del título: «(Bob Sinclar remix)», «[Extended Mix]», « - Radio Edit». */
const SUFFIX_RE = /\s*(?:[([]([^()[\]]+)[)\]]|\s[-–—]\s([^-–—]+))\s*$/;
const UNOFFICIAL_RE = /\b(bootleg|mash ?up|unofficial|flip)\b/i;
const EXTENDED_RE = /\b(extended|club mix|12["”″]|12 inch|long version|full length)\b/i;
const REMIX_RE = /\b(remix|rmx|rework|refix|reshape)\b/i;
const EDIT_RE = /\b(radio edit|edit|radio version|short version)\b/i;
const ORIGINAL_RE = /^(original( mix| version)?)$/i;
const VERSION_WORD_RE = /\b(mix|edit|remix|rmx|rework|version|dub|dubmix|bootleg|vip|live|instrumental|extended)\b/i;

/** Título sin el sufijo de versión, para saber si dos grabaciones son la misma canción. */
export function coreTitle(title: string): string {
  const m = title.match(SUFFIX_RE);
  return norm(m ? title.slice(0, m.index) : title);
}

/** Título tal como se nombra la canción en una frase: sin «(original mix)», «(12” club mix)»… (sí con subtítulos). */
export function plainTitle(title: string): string {
  const m = title.match(SUFFIX_RE);
  const v = m ? (m[1] ?? m[2] ?? '') : '';
  return m && VERSION_WORD_RE.test(v) ? title.slice(0, m.index).trim() : title;
}

function suffix(title: string): string | null {
  const m = title.match(SUFFIX_RE);
  return m ? (m[1] ?? m[2] ?? '').trim() || null : null;
}

/** Qué es una grabación según su título y crédito (no se deduce nada más): original, extended, remix, edit… */
export function versionClass(l: { title: string; artist_name?: string; version?: string | null }): VersionClass {
  const v = l.version ?? suffix(l.title) ?? '';
  if (UNOFFICIAL_RE.test(l.title) || /\bvs\.?\s/i.test(l.artist_name ?? '')) return 'unofficial';
  if (!v || ORIGINAL_RE.test(v)) return 'original';
  if (REMIX_RE.test(v)) return 'remix';
  if (EXTENDED_RE.test(v)) return 'extended';
  if (EDIT_RE.test(v)) return 'edit';
  return 'other';
}

const VERSION_LABEL: Record<VersionClass, string | null> = {
  original: 'Original', extended: 'Extended', remix: 'Remix', edit: 'Edit', unofficial: 'No oficial', other: null,
};

export type VersionRow = { item: TrackLink; kind: string };

/**
 * «Versiones»: pocas y verificadas. La original si esta es una versión; una extended de la misma canción (si esta no
 * lo es ya) y hasta dos remixes oficiales, todos enlazados como remezcla en MusicBrainz (no por título parecido).
 * Fuera: mashups, bootlegs, radio edits, dubs, la misma grabación reeditada y casi duplicados.
 */
export function trackVersions(t: Pick<TrackResponse, 'mbid' | 'title' | 'version' | 'relations'>): VersionRow[] {
  const own = versionClass(t);
  const core = coreTitle(t.title);
  const seen = new Set<string>([t.mbid, norm(t.title)]);
  const fresh = (l: TrackLink) => {
    if (seen.has(l.mbid) || seen.has(norm(l.title))) return false;
    seen.add(l.mbid).add(norm(l.title));
    return true;
  };
  const rows: VersionRow[] = [];
  const original = t.relations.remix_of.find((l) => versionClass(l) !== 'unofficial');
  if (original && own !== 'original' && fresh(original)) rows.push({ item: original, kind: 'Original' });
  const remixes = t.relations.remixes;
  if (own !== 'extended') {
    const ext = remixes.find((l) => versionClass(l) === 'extended' && coreTitle(l.title) === core && fresh(l));
    if (ext) rows.push({ item: ext, kind: 'Extended' });
  }
  for (const l of remixes) {
    if (rows.filter((r) => r.kind === 'Remix').length === 2) break;
    if (versionClass(l) === 'remix' && fresh(l)) rows.push({ item: l, kind: 'Remix' });
  }
  return rows;
}

// --- ADN musical --------------------------------------------------------------------------------------------------
export type DnaMeasure = { value: string; note: string };
export type DnaRow = { key: string; label: string; value: string };
export type SheetDna = {
  genre: { family: string; styles: string[]; note: string | null } | null;
  bpm: DnaMeasure | null;
  key: (DnaMeasure & { camelot: string | null }) | null;
  /** Producción y publicación: duración, sello, formato y versión (el año va en la cabecera). */
  rows: DnaRow[];
};

/** Clasificaciones de lanzamiento que no describen el género de cada pista que contienen. */
const NON_TRACK_RELEASES = new Set(['Soundtrack', 'Compilation', 'DJ-mix', 'Mixtape/Street']);

/**
 * ADN de esta grabación. Género: el de la grabación; el de su lanzamiento solo si este es un single, EP o álbum propio
 * (nunca el de una banda sonora o un recopilatorio, ni el del artista). BPM y tonalidad solo medidos, dichos
 * «estimado» (AcousticBrainz). Sin métricas inventadas.
 */
export function trackDna(t: Pick<TrackResponse, 'dna' | 'length_ms' | 'version' | 'title' | 'original_release' | 'relations'>): SheetDna {
  const trait = (key: string, ok: (s: string) => boolean) => t.dna.traits.find((x) => x.key === key && ok(x.status) && x.values.length > 0);
  const g = trait('genre', (s) => s !== 'unavailable');
  const releaseIsCollection = (t.original_release?.secondary_types ?? []).some((x) => NON_TRACK_RELEASES.has(x));
  const genre = g && !(g.scope === 'release' && releaseIsCollection) && g.scope !== 'artist'
    ? { family: g.values[0], styles: g.values.slice(1, 3), note: g.scope === 'release' ? 'del lanzamiento' : null }
    : null;
  const bpm = trait('bpm', (s) => s === 'measured');
  const key = trait('key', (s) => s === 'measured');

  const rows: DnaRow[] = [];
  const length = duration(t.length_ms);
  if (length) rows.push({ key: 'length', label: 'Duración', value: length });
  const label = trait('label', (s) => s !== 'unavailable');
  if (label) rows.push({ key: 'label', label: label.values.length > 1 ? 'Sellos' : 'Sello', value: label.values.slice(0, 2).join(' · ') });
  const format = t.original_release ? releaseKind(t.original_release) : null;
  if (format) rows.push({ key: 'format', label: 'Formato', value: format });
  const cls = versionClass(t);
  const versionLabel = t.relations.remix_of.length && cls === 'original' ? 'Remix o edit' : t.version ? VERSION_LABEL[cls] ?? t.version : null;
  if (versionLabel) rows.push({ key: 'version', label: 'Versión', value: versionLabel });

  return {
    genre,
    bpm: bpm ? { value: bpm.values[0], note: 'estimado' } : null,
    key: key ? { value: key.values[0], camelot: key.values[1] ?? null, note: 'estimado' } : null,
    rows,
  };
}

export function hasDna(d: SheetDna): boolean {
  return !!(d.genre || d.bpm || d.key || d.rows.length);
}

// --- La historia del track ----------------------------------------------------------------------------------------
/** `mbid`: la otra grabación de la que habla (la ficha la abre). */
export type TrackStory = { key: string; title: string; text: string; mbid?: string; linkLabel?: string };

const by = (l: { title: string; artist_name: string }) => `«${l.title}»${l.artist_name ? `, de ${l.artist_name}` : ''}`;

/**
 * Un solo hecho, el más singular y documentado: sample, versión de otra obra, producción acreditada a alguien que no
 * firma el tema, o una canción posterior que la samplea. Pertenecer a un álbum, el año, el género o una banda sonora son
 * metadatos, no historia: sin un hecho así, null (la sección se oculta). Nada redactado con IA.
 */
export function trackStory(t: Pick<TrackResponse, 'title' | 'artist_name' | 'credits' | 'relations'>): TrackStory | null {
  const r = t.relations;
  const sample = (r.samples ?? []).find((l) => versionClass(l) !== 'unofficial');
  if (sample) {
    return {
      key: 'sample', title: sample.artist_name ? `El sample de ${sample.artist_name}` : 'El sample',
      text: `«${plainTitle(t.title)}» toma un sample de ${by(sample)}. Abre su ficha para escuchar de dónde sale.`,
      mbid: sample.mbid, linkLabel: `Abrir «${sample.title}»`,
    };
  }
  if (r.cover_of) {
    const writers = r.cover_writers ?? [];
    return {
      key: 'cover', title: 'Una versión de otra obra',
      text: `«${plainTitle(t.title)}» es una versión de «${r.cover_of}»${writers.length ? `, obra escrita por ${joinNames(writers)}` : ''}.`,
    };
  }
  const credited = norm(t.artist_name);
  const producers = (t.credits.find((c) => c.role === 'Producción')?.artists ?? []).map((a) => a.name).filter((n) => !credited.includes(norm(n)));
  if (producers.length) {
    return {
      key: 'producer', title: 'Quién está detrás',
      text: `Aunque sale a nombre de ${t.artist_name}, la producción de «${plainTitle(t.title)}» está acreditada a ${joinNames(producers.slice(0, 3))}.`,
    };
  }
  const sampled = (r.sampled_by ?? []).find((l) => versionClass(l) !== 'unofficial');
  if (sampled) {
    return {
      key: 'sampled', title: 'Sampleada después',
      text: `${by(sampled)}, toma un sample de «${plainTitle(t.title)}».`,
      mbid: sampled.mbid, linkLabel: `Abrir «${sampled.title}»`,
    };
  }
  return null;
}

function joinNames(items: string[]): string {
  return items.length <= 1 ? items[0] ?? '' : `${items.slice(0, -1).join(', ')} y ${items[items.length - 1]}`;
}

// --- Artistas -----------------------------------------------------------------------------------------------------
export type SheetArtist = { key: string; name: string; mbid: string | null; role: string };

/**
 * Quién firma la canción, una vez cada uno: principal, colaboradores e invitados (según el crédito de MusicBrainz) y
 * el remezclador si esta grabación es un remix. Los créditos técnicos (producción, mezcla, autoría…) no se listan.
 */
export function trackArtists(t: Pick<TrackResponse, 'title' | 'version' | 'artist_credit' | 'artist_name' | 'credits' | 'relations'>): SheetArtist[] {
  const out: SheetArtist[] = [];
  const seen = new Set<string>();
  const add = (name: string, mbid: string | null, role: string) => {
    const key = mbid ?? `name:${norm(name)}`;
    if (!name.trim() || seen.has(key) || seen.has(`name:${norm(name)}`)) return;
    seen.add(key).add(`name:${norm(name)}`);
    out.push({ key, name, mbid, role });
  };
  creditParts(t.artist_credit, t.artist_name).forEach((p, i) =>
    add(p.name, p.mbid, p.guest ? 'Artista invitado' : i === 0 ? 'Artista principal' : 'Colaboración'));
  if (versionClass(t) === 'remix' || t.relations.remix_of.length) {
    for (const a of t.credits.find((c) => c.role === 'Remezcla')?.artists ?? []) add(a.name, linkableArtist(a.mbid) ? a.mbid : null, 'Remezcla');
  }
  return out;
}
