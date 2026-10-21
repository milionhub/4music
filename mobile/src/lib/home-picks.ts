/**
 * Contenido de Inicio (V6), lógica pura probada en tests/home.test.ts:
 * - `dailySlots`: canciones editoriales del día para la portada, En el radar y Detrás del sonido (con reservas).
 * - `soundFacts`: datos verdaderos de una ficha TrackDNA (samples, versiones, créditos, edición original…).
 * - `frequency`: Tu frecuencia, recomendaciones explicables a partir de Guardados, artistas y estilos declarados.
 *
 * Reglas: solo grabaciones con MBID (TrackDNA las abre); ningún motivo sin el dato que lo respalda (no se habla de
 * género si la ficha no lo documenta); originales y versiones oficiales antes que remezclas, y lo no oficial (bootlegs,
 * mashups) al final y dicho así; nada guardado, repetido ni ya mostrado en otra sección.
 */
import { splitTitle } from './artist-identity.ts';
import { creditParts, joinEs } from './format.ts';
import { EDITORIAL_PICKS, type EditorialPick } from './home-catalog.ts';
import { mixed } from './track-art.ts';
import type { SavedTrack } from './preferences.ts';
import type { TrackLink, TrackRelease, TrackResponse } from '@/types/music';

/** Guardados más recientes cuya ficha se consulta para Tu frecuencia (una petición cada uno, en caché). */
export const FREQUENCY_SEEDS = 4;
export const FREQUENCY_SIZE = 8;
/** Reservas por hueco si una ficha no carga. */
const SLOT_CANDIDATES = 3;

export const norm = (s: string) => s.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase().replace(/[^a-z0-9]+/g, ' ').trim();

function rotated<T>(list: T[], start: number): T[] {
  if (!list.length) return [];
  const i = ((start % list.length) + list.length) % list.length;
  return [...list.slice(i), ...list.slice(0, i)];
}

// --- Versiones y créditos -------------------------------------------------------------------------------------------
/**
 * Qué es una grabación, solo por lo que dicen su título y su crédito (los enlaces de la ficha no traen más):
 * original (sin versión, o con un subtítulo), version (variante oficial: original mix, radio edit, extended, club mix,
 * dub…), remix (remezcla o edit firmado) y unofficial (bootleg, mashup o «A vs. B»). Ante la duda, remix: nada se
 * presenta como original sin indicio. La selección editorial puede fijarlo (`EditorialPick.version`).
 */
export type VersionClass = 'original' | 'version' | 'remix' | 'unofficial';
const OFFICIAL_VERSION = /^(original( mix| version)?|radio (edit|mix|version)|extended( mix| version)?|club mix|12["”″]?( club)? (mix|version)|album version|single version|instrumental|vocal( mix)?|dub|short mix|full length)$/i;
const VERSION_MARK = /\b(remix|rmx|mix|edit|dub|rework|refix|version|bootleg|mashup|vip)\b/i;
const UNOFFICIAL = /\b(bootleg|mashup|unofficial)\b/i;

export function versionClass(l: { title: string; artist_name: string }): VersionClass {
  if (UNOFFICIAL.test(l.title) || /\s(vs\.?|versus)\s/i.test(l.artist_name)) return 'unofficial';
  const { aside } = splitTitle(l.title);
  if (!aside) return 'original';
  if (OFFICIAL_VERSION.test(aside.trim())) return 'version';
  return VERSION_MARK.test(aside) ? 'remix' : 'original';
}

const CLASS_ORDER: Record<VersionClass, number> = { original: 0, version: 1, remix: 2, unofficial: 3 };
/** Orden estable: originales, versiones oficiales, remezclas y, al final, lo no oficial. */
const byClass = (links: TrackLink[]) => links.map((l, i) => ({ l, i, c: CLASS_ORDER[versionClass(l)] }))
  .sort((a, b) => a.c - b.c || a.i - b.i).map((x) => x.l);

/**
 * Artista principal de un crédito en texto: lo anterior a «feat.», «ft.», «featuring», «with», «con» o «vs.». Sirve
 * para agrupar (diversidad); en pantalla se muestra siempre el crédito completo, con sus invitados.
 */
export function mainArtist(credit: string): string {
  return credit.split(/\s+(?:feat\.?|ft\.?|featuring|with|con|vs\.?|versus)\s+/i)[0].trim() || credit;
}

const pickClass = (p: EditorialPick) => p.version ?? versionClass({ title: p.title, artist_name: p.artist });

// --- Huecos editoriales del día -----------------------------------------------------------------------------------
export type DailySlots = { cover: EditorialPick[]; radar: EditorialPick[]; behind: EditorialPick[] };

/**
 * Candidatas (la primera y sus reservas) de cada hueco editorial del día: estables durante el día, distintas entre
 * huecos (canción y artista) y sin canciones que el usuario ya ha guardado (Inicio es para descubrir). En portada y
 * radar van primero originales y versiones oficiales; una remezcla o un bootleg de la selección solo entra si no
 * quedan (no se excluyen: van identificados como tales).
 */
export function dailySlots(dayIndex: number, savedIds: string[], pool: EditorialPick[] = EDITORIAL_PICKS): DailySlots {
  const saved = new Set(savedIds);
  const available = pool.filter((p) => !saved.has(p.mbid));
  const used = new Set<string>();
  const take = (list: EditorialPick[], start: number) => {
    const ordered = rotated(list, start).map((p, i) => ({ p, i, c: Math.max(0, CLASS_ORDER[pickClass(p)] - 1) }))
      .sort((a, b) => a.c - b.c || a.i - b.i).map((x) => x.p);
    const out: EditorialPick[] = [];
    for (const p of ordered) {
      if (out.length >= SLOT_CANDIDATES) break;
      if (used.has(p.mbid) || used.has(p.artist_mbid)) continue;
      out.push(p);
    }
    out.forEach((p) => used.add(p.mbid).add(p.artist_mbid));
    return out;
  };
  const off = (trait: string) => mixed(`home:${trait}`);
  const cover = take(available, dayIndex * 5 + off('cover'));
  const radar = take(available, dayIndex * 7 + off('radar'));
  const behind = take(available.filter((p) => p.connections), dayIndex * 3 + off('behind'));
  return { cover, radar, behind };
}

// --- Datos verdaderos de una ficha ---------------------------------------------------------------------------------
export type FactKind = 'sample' | 'sampled' | 'original' | 'cover' | 'producer' | 'mashup' | 'remixes' | 'release' | 'mixes' | 'genre';
/** Conexiones con otra música (Detrás del sonido); el resto son datos de la propia grabación. */
export const CONNECTION_KINDS: FactKind[] = ['sample', 'original', 'cover', 'producer', 'sampled', 'remixes', 'mashup'];
/** Interés de cada dato, de más a menos singular; lo que pasa por una versión no oficial se desplaza al final. */
const KIND_ORDER: FactKind[] = ['sample', 'original', 'cover', 'producer', 'sampled', 'release', 'remixes', 'mixes', 'mashup', 'genre'];
const CLASS_PENALTY: Record<VersionClass, number> = { original: 0, version: 0, remix: 2, unofficial: 6 };

export type SoundFact = {
  kind: FactKind;
  /** Palabra gigante (gráfica) y rótulo pequeño. */
  word: string;
  kicker: string;
  text: string;
  track: { mbid: string; title: string; artist: string };
  /** La otra grabación de la conexión, si tiene ficha, y qué es (original, versión oficial, remezcla, no oficial). */
  other?: TrackLink;
  otherClass?: VersionClass;
  /** Menor = más interesante. */
  rank: number;
};

const FORMATS: [RegExp, string][] = [[/^12" vinyl$/i, 'vinilo de 12"'], [/^7" vinyl$/i, 'vinilo de 7"'], [/^10" vinyl$/i, 'vinilo de 10"'],
  [/vinyl/i, 'vinilo'], [/^(enhanced )?cd$/i, 'CD'], [/^cd-r$/i, 'CD-R'], [/cassette/i, 'casete'], [/^digital media$/i, 'digital']];

/** Formatos documentados, traducidos y sin repetir, en el orden de la fuente (ninguno se considera mejor). */
export function formatsEs(formats: string[]): string[] {
  const out: string[] = [];
  for (const f of formats) {
    const hit = FORMATS.find(([re]) => re.test(f.trim()))?.[1];
    if (hit && !out.includes(hit)) out.push(hit);
  }
  return out;
}

/** Cuánta información verificable aporta un grupo de lanzamientos (sin año, ninguna). Ningún formato puntúa más. */
const releaseInfo = (r: TrackRelease) =>
  r.date ? 1 + (r.labels.length || r.self_released ? 2 : 0) + (r.labels.length === 1 && r.catalog_number ? 1 : 0) + (r.formats.length ? 1 : 0) : 0;

/**
 * Edición original. La ficha la da como grupo de lanzamientos: su fecha es la más antigua documentada, pero sus sellos
 * y formatos reúnen todas sus ediciones (reediciones incluidas). Por eso solo se afirma lo inequívoco: un sello único
 * (con su catálogo); con varios, que sus ediciones salieron en ellos; y los formatos, como formatos de sus ediciones.
 * Entre la original y los otros lanzamientos propios del mismo año se usa el que más información verificable aporta.
 */
export function releaseFact(t: Pick<TrackResponse, 'original_release' | 'releases'>): { year: string; text: string } | null {
  const o = t.original_release;
  if (!o?.date) return null;
  const year = o.date.slice(0, 4);
  const best = [o, ...t.releases.filter((r) => r.own && !r.secondary_types.length && r.date?.slice(0, 4) === year)]
    .reduce((a, b) => (releaseInfo(b) > releaseInfo(a) ? b : a));
  const formats = formatsEs(best.formats).slice(0, 3);
  if (best.labels.length > 1) {
    const labels = best.labels.length > 3 ? `${best.labels.slice(0, 3).join(', ')} y otros sellos` : joinEs(best.labels);
    return { year, text: `Se publicó en ${year}; sus ediciones salieron en ${labels}${formats.length ? `, en ${joinEs(formats)}` : ''}.` };
  }
  const where = best.labels.length === 1 ? ` en ${best.labels[0]}${best.catalog_number ? ` (${best.catalog_number})` : ''}`
    : best.self_released ? ' como autoedición' : '';
  const fmt = formats.length === 1 ? `, en ${formats[0]}` : formats.length > 1 ? `; sus ediciones, en ${joinEs(formats)}` : '';
  if (!where && !fmt) return { year, text: `Se publicó por primera vez en ${year}, según MusicBrainz.` };
  return { year, text: `Se publicó en ${year}${where}${fmt}.` };
}

const by = (l: { title: string; artist_name: string }) => `«${l.title}»${l.artist_name ? `, de ${l.artist_name}` : ''}`;

/** Datos documentados de una ficha, ordenados por interés: originales y versiones oficiales antes que lo no oficial. */
export function soundFacts(t: TrackResponse): SoundFact[] {
  const track = { mbid: t.mbid, title: t.title, artist: t.artist_name };
  const r = t.relations;
  const out: SoundFact[] = [];
  const add = (f: Omit<SoundFact, 'track' | 'rank' | 'otherClass'>) => {
    const otherClass = f.other ? versionClass(f.other) : undefined;
    out.push({ ...f, track, otherClass, rank: KIND_ORDER.indexOf(f.kind) + (otherClass ? CLASS_PENALTY[otherClass] : 0) });
  };
  const sample = byClass(r.samples ?? [])[0];
  if (sample) add({ kind: 'sample', word: 'Sample', kicker: 'Un sample confirmado', text: `«${t.title}» incluye un sample de ${by(sample)}.`, other: sample });
  const original = byClass(r.remix_of)[0];
  if (original) add({ kind: 'original', word: 'Origen', kicker: 'La original', text: `«${t.title}» es una versión de ${by(original)}.`, other: original });
  if (r.cover_of) {
    const writers = r.cover_writers ?? [];
    add({ kind: 'cover', word: 'Versión', kicker: 'Una versión', text: `«${t.title}» es una versión de «${r.cover_of}»${writers.length ? `, escrita por ${joinEs(writers)}` : ''}.` });
  }
  const credited = norm(t.artist_name);
  const producers = (t.credits.find((c) => c.role === 'Producción')?.artists ?? []).map((a) => a.name)
    .filter((n) => !credited.includes(norm(n)));
  if (producers.length) {
    add({ kind: 'producer', word: 'Cabina', kicker: 'Quién está detrás',
      text: `En los créditos de «${t.title}», de ${t.artist_name}, la producción es de ${joinEs(producers.slice(0, 3))}.` });
  }
  const sampled = byClass(r.sampled_by ?? [])[0];
  if (sampled) {
    const cls = versionClass(sampled);
    add({ kind: 'sampled', word: 'Eco', kicker: cls === 'unofficial' ? 'Sampleada en un bootleg' : cls === 'remix' ? 'Sampleada en un edit o remezcla' : 'Sampleada después',
      text: `«${sampled.title}»${sampled.artist_name ? `, de ${sampled.artist_name},` : ''} samplea «${t.title}».`, other: sampled });
  }
  // Remezclas: se destaca una con firma (más interesante que un radio edit), nunca una no oficial si hay otra.
  const remixes = byClass(r.remixes);
  const remix = remixes.find((l) => versionClass(l) === 'remix') ?? remixes[0];
  if (remix) {
    const count = Math.max(r.remix_count, r.remixes.length);
    add({ kind: 'remixes', word: 'Remix', kicker: 'Remezclas y versiones', other: remix,
      text: count > 1
        ? `MusicBrainz documenta al menos ${count} remezclas, edits o versiones de «${t.title}»; entre ellas, ${by(remix)}.`
        : `«${t.title}» tiene una versión documentada: ${by(remix)}.` });
  }
  const mashup = byClass(r.mashups ?? [])[0];
  if (mashup) {
    const bootleg = /bootleg/i.test(mashup.title);
    add({ kind: 'mashup', word: bootleg ? 'Bootleg' : 'Mashup', kicker: bootleg ? 'Un bootleg (no oficial)' : 'Un mashup',
      text: `«${t.title}» aparece en el mashup ${by(mashup)}${bootleg ? ', que su propio título identifica como bootleg' : ''}.`, other: mashup });
  }
  const release = releaseFact(t);
  if (release) add({ kind: 'release', word: release.year, kicker: 'La edición original', text: release.text });
  if (r.dj_mix_count > 0) {
    add({ kind: 'mixes', word: 'Mix', kicker: 'En cabina',
      text: `Aparece en al menos ${r.dj_mix_count} ${r.dj_mix_count === 1 ? 'DJ mix publicado' : 'DJ mixes publicados'}, según MusicBrainz.` });
  }
  const genre = t.dna.traits.find((x) => x.key === 'genre' && x.status !== 'unavailable' && x.values.length > 0);
  if (genre) {
    add({ kind: 'genre', word: genre.values[0], kicker: 'Etiqueta de la comunidad',
      text: `La comunidad de MusicBrainz ${genre.scope === 'release' ? 'etiqueta su lanzamiento' : 'la etiqueta'} como ${joinEs(genre.values.slice(0, 2))}.` });
  }
  return out.sort((a, b) => a.rank - b.rank);
}

/** Dato de En el radar: el más singular, prefiriendo lo que se refiere a originales y versiones oficiales. */
export function radarFact(t: TrackResponse): SoundFact | null {
  return soundFacts(t)[0] ?? null;
}

/**
 * Detrás del sonido: la conexión documentada de más interés (originales y versiones oficiales primero); a igualdad,
 * la de tus Guardados (van antes en `sources`). Nunca una conexión con algo ya mostrado en Inicio. null → se oculta.
 */
export function behindFact(sources: (TrackResponse | undefined)[], shown: Set<string>): SoundFact | null {
  const all = sources.flatMap((t, i) => (t && !shown.has(t.mbid)
    ? soundFacts(t).filter((f) => CONNECTION_KINDS.includes(f.kind) && !(f.other && shown.has(f.other.mbid))).map((f) => ({ f, i }))
    : []));
  all.sort((a, b) => a.f.rank - b.f.rank || a.i - b.i);
  return all[0]?.f ?? null;
}

// --- Tu frecuencia -------------------------------------------------------------------------------------------------
export type FrequencyKind = 'relation' | 'artist' | 'label' | 'genre' | 'style' | 'editorial';
export type FrequencyItem = {
  mbid: string;
  title: string;
  /** Crédito completo (con invitados), tal como lo da MusicBrainz. */
  artist: string;
  /** Portada real (Cover Art Archive): nunca null en el carrusel. */
  cover: string;
  reason: string;
  kind: FrequencyKind;
};

/** Géneros demasiado amplios para justificar una recomendación. */
const GENERIC_GENRES = new Set(['electronica', 'electronic', 'pop', 'dance']);
/** Diversidad: un artista principal por carrusel y como mucho dos propuestas (una por relación) de cada Guardado. */
const MAX_PER_ARTIST = 1;
const MAX_PER_SEED = 2;
const MAX_RELATIONS_PER_SEED = 1;
/** Fichas de candidatos por relación que se piden para conocer su portada: por Guardado y en total (caché en sesión y servidor). */
const LOOKUPS_PER_SEED = 2;
export const FREQUENCY_LOOKUPS = 4;

export type FrequencyInput = {
  saved: SavedTrack[];
  /** Fichas de los Guardados (clave: MBID guardado); las que aún no han cargado no aportan relaciones. */
  details: Record<string, TrackResponse | undefined>;
  /**
   * Fichas de candidatos por relación (clave: MBID del enlace), pedidas según `lookups`: dan su portada real y permiten
   * comprobar que no son una versión de un Guardado. undefined = aún no ha llegado; null = no se pudo cargar.
   */
  candidates?: Record<string, TrackResponse | null | undefined>;
  /** Portadas que no se pudieron mostrar en el dispositivo (URL): el candidato sale del carrusel. */
  failedCovers?: string[];
  favorites?: { mbid: string; name: string }[];
  declaredStyles?: string[];
  /** Canciones ya presentes en otras secciones de Inicio. */
  exclude?: string[];
  dayIndex: number;
  size?: number;
  pool?: EditorialPick[];
};

export type Frequency = {
  items: FrequencyItem[];
  personal: number;
  /** Candidatos por relación cuya ficha hay que pedir (ordenados, como mucho FREQUENCY_LOOKUPS). */
  lookups: string[];
  /** Candidatos descartados por ser la misma canción que un Guardado u otra propuesta, o por no tener portada real. */
  discarded: { duplicates: number; noCover: number };
};

/** Portada real y utilizable: una imagen de Cover Art Archive (la fuente que ya usan la API y la selección editorial). */
export function isRealCover(url: string | null | undefined): url is string {
  if (!url) return false;
  try {
    const u = new URL(url);
    return u.protocol === 'https:' && (u.hostname === 'coverartarchive.org' || u.hostname.endsWith('.archive.org'))
      && /^\/release(-group)?\/[0-9a-f-]{36}\//i.test(u.pathname);
  } catch {
    return false;
  }
}

/**
 * Identidad de la canción subyacente, solo por título y artista principal: el título sin su marca de versión
 * («(radio edit)», «(12” club mix)», «(X remix)»…) y el crédito sin invitados. Un subtítulo que no es una versión se
 * conserva, y artistas distintos nunca comparten canción (una cover de otro artista es otra grabación con identidad
 * propia). La equivalencia por relaciones (remezcla, edit de MusicBrainz) se añade aparte.
 */
export function songFamily(title: string, artist: string): string {
  const { main, aside } = splitTitle(title);
  const versioned = !!aside && (OFFICIAL_VERSION.test(aside.trim()) || VERSION_MARK.test(aside) || UNOFFICIAL.test(aside));
  return `${norm(versioned ? main : title)}|${norm(mainArtist(artist))}`;
}

type Candidate = { mbid: string; title: string; artist: string; cover: string | null; reason: string; kind: FrequencyKind; seed?: string; pending?: boolean };

const fromPick = (p: EditorialPick, reason: string, kind: FrequencyKind, seed?: string): Candidate =>
  ({ mbid: p.mbid, title: p.title, artist: p.artist, cover: p.cover, reason, kind, seed });

/** Misma canción que una ficha: ella, sus remezclas/edits y su original enlazados en MusicBrainz, y su familia. */
function sameSong(t: TrackResponse): { ids: string[]; families: string[] } {
  const links = [...t.relations.remix_of, ...t.relations.remixes];
  return { ids: [t.mbid, ...links.map((l) => l.mbid)], families: [songFamily(t.title, t.artist_name), ...links.map((l) => songFamily(l.title, l.artist_name))] };
}

/**
 * Recomendaciones explicables y variadas, en orden de evidencia: samples documentados de tus canciones (una por
 * Guardado; un sample une dos canciones distintas, no las fusiona), mismo artista principal, mismo sello, género
 * compartido según MusicBrainz y estilos que declaraste; si faltan, la selección de la redacción (dicho así).
 *
 * Nunca entra la misma canción que un Guardado o que otra propuesta: ni la grabación, ni sus remezclas, edits,
 * extended u original enlazados en MusicBrainz, ni otra versión con el mismo título base y artista principal. Tampoco
 * bootlegs ni mashups. Cada propuesta lleva portada real; sin ella se descarta y entra la siguiente. Con pocos
 * candidatos válidos el carrusel es más corto: nunca se rellena con variantes.
 */
export function frequency(input: FrequencyInput): Frequency {
  const { saved, details, dayIndex } = input;
  const candidates = input.candidates ?? {};
  const failed = new Set(input.failedCovers ?? []);
  const size = input.size ?? FREQUENCY_SIZE;
  const pool = rotated(input.pool ?? EDITORIAL_PICKS, dayIndex * 3 + mixed('home:frequency'));
  const discarded = { duplicates: 0, noCover: 0 };
  const rejected = new Set<string>(); // cada candidato descartado cuenta una vez
  const reject = (mbid: string, why: keyof Frequency['discarded']) => {
    if (rejected.has(mbid)) return;
    rejected.add(mbid);
    discarded[why] += 1;
  };

  // Identidad musical de lo guardado (y de lo ya mostrado en Inicio): grabaciones y familias de canción bloqueadas.
  const shownElsewhere = new Set(input.exclude ?? []);
  const blockedIds = new Set(saved.map((s) => s.mbid));
  const blockedFamilies = new Set(saved.map((s) => songFamily(s.title, s.artist_name)));
  for (const s of saved) {
    const d = details[s.mbid];
    if (!d) continue;
    const same = sameSong(d); // MBID canónico (fusiones), remezclas, edits y original
    same.ids.forEach((m) => blockedIds.add(m));
    same.families.forEach((f) => blockedFamilies.add(f));
  }
  const isDuplicate = (c: { mbid: string; title: string; artist: string }) => {
    if (blockedIds.has(c.mbid) || blockedFamilies.has(songFamily(c.title, c.artist))) return true;
    const d = candidates[c.mbid]; // su ficha confirma que no es una versión de un Guardado
    return !!d && (blockedIds.has(d.mbid) || sameSong(d).ids.some((m) => blockedIds.has(m)));
  };

  // Relaciones documentadas de cada Guardado: samples en ambos sentidos (canciones distintas). Las remezclas, edits y
  // la original son la misma canción y no se recomiendan; bootlegs y mashups, tampoco.
  const seeds = saved.slice(0, FREQUENCY_SEEDS);
  const lookups: string[] = [];
  const relations: Candidate[] = [];
  const perSeedLinks = seeds.map((s) => {
    const r = details[s.mbid]?.relations;
    if (!r) return [];
    const rows = [
      ...(r.samples ?? []).map((l) => ({ l, reason: `Sampleada en «${s.title}»` })),
      ...(r.sampled_by ?? []).map((l) => ({ l, reason: `Samplea «${s.title}»` })),
    ];
    [...r.remix_of, ...r.remixes].forEach((l) => reject(l.mbid, 'duplicates')); // antes se recomendaban
    return rows.filter(({ l }) => {
      if (versionClass(l) === 'unofficial' || shownElsewhere.has(l.mbid)) return false;
      if (isDuplicate({ mbid: l.mbid, title: l.title, artist: l.artist_name })) {
        reject(l.mbid, 'duplicates');
        return false;
      }
      return true;
    }).slice(0, LOOKUPS_PER_SEED).map(({ l, reason }) => ({ l, reason, seed: s.mbid }));
  });
  // Petición de fichas alternando Guardados (nunca todas las de uno): el límite total acota Inicio.
  for (let round = 0; round < LOOKUPS_PER_SEED; round++) {
    for (const rows of perSeedLinks) {
      const row = rows[round];
      if (!row || lookups.length >= FREQUENCY_LOOKUPS || lookups.includes(row.l.mbid)) continue;
      lookups.push(row.l.mbid);
      const d = candidates[row.l.mbid];
      relations.push({ mbid: row.l.mbid, title: row.l.title, artist: row.l.artist_name, cover: d?.cover_url ?? null, pending: d === undefined,
        reason: row.reason, kind: 'relation', seed: row.seed });
    }
  }

  // Coincidencias con la selección editorial, con el dato que las respalda. Artista principal e invitado («feat.») se
  // distinguen por el crédito de MusicBrainz guardado; los dos conservan su crédito.
  const mains = new Map<string, string>();
  const guests = new Map<string, SavedTrack>();
  for (const s of saved) {
    for (const p of creditParts(s.artists, s.artist_name)) {
      if (!p.mbid) continue;
      if (p.guest) {
        if (!guests.has(p.mbid)) guests.set(p.mbid, s);
      } else if (!mains.has(p.mbid)) mains.set(p.mbid, s.mbid);
    }
  }
  const favoriteArtists = new Set((input.favorites ?? []).map((f) => f.mbid));
  const byArtist = pool.flatMap((p) => {
    if (mains.has(p.artist_mbid)) return [fromPick(p, `Más de ${p.artist}`, 'artist', mains.get(p.artist_mbid))];
    const g = guests.get(p.artist_mbid);
    if (g) return [fromPick(p, `${p.artist}, invitado en «${g.title}»`, 'artist', g.mbid)];
    if (favoriteArtists.has(p.artist_mbid)) return [fromPick(p, `${p.artist}, en tus artistas`, 'artist')];
    return [];
  });
  const byLabel: Candidate[] = [];
  for (const p of pool) {
    for (const s of saved) {
      if (p.label && s.label && norm(s.label) === norm(p.label)) byLabel.push(fromPick(p, `Mismo sello que «${s.title}»: ${p.label}`, 'label', s.mbid));
    }
  }
  // Género: cada selección con cada Guardado que lo comparte (alternando Guardados), para no repetir el mismo motivo.
  const byGenre: Candidate[] = [];
  for (const s of seeds) {
    const g = details[s.mbid]?.dna.traits.find((x) => x.key === 'genre' && x.status !== 'unavailable');
    for (const p of pool) {
      const shared = g?.values.find((v) => !GENERIC_GENRES.has(norm(v)) && p.genres.some((pg) => norm(pg) === norm(v)));
      if (shared) byGenre.push(fromPick(p, `${shared}, como «${s.title}»`, 'genre', s.mbid));
    }
  }
  const styles = (input.declaredStyles ?? []).filter((st) => !GENERIC_GENRES.has(norm(st)));
  const byStyle = pool.flatMap((p) => {
    const st = styles.find((x) => p.genres.some((g) => norm(g) === norm(x)));
    return st ? [fromPick(p, `${st}, uno de tus estilos`, 'style')] : [];
  });

  const items: FrequencyItem[] = [];
  const used = new Set<string>();
  const reasons = new Set<string>();
  const perArtist = new Map<string, number>();
  const perSeed = new Map<string, number>();
  const perSeedRelations = new Map<string, number>();
  const accept = (c: Candidate) => {
    if (items.length >= size || c.pending || used.has(c.mbid) || shownElsewhere.has(c.mbid)) return; // pending: su ficha aún no ha llegado
    if (c.kind !== 'editorial' && reasons.has(c.reason)) return; // nunca dos propuestas por el mismo motivo
    const family = songFamily(c.title, c.artist);
    if (isDuplicate(c) || used.has(family)) return reject(c.mbid, 'duplicates');
    if (!isRealCover(c.cover) || failed.has(c.cover)) return reject(c.mbid, 'noCover');
    const artist = norm(mainArtist(c.artist));
    if ((perArtist.get(artist) ?? 0) >= MAX_PER_ARTIST) return;
    if (c.seed && (perSeed.get(c.seed) ?? 0) >= MAX_PER_SEED) return;
    if (c.kind === 'relation' && c.seed && (perSeedRelations.get(c.seed) ?? 0) >= MAX_RELATIONS_PER_SEED) return;
    items.push({ mbid: c.mbid, title: c.title, artist: c.artist, cover: c.cover, reason: c.reason, kind: c.kind });
    used.add(c.mbid).add(family);
    reasons.add(c.reason);
    perArtist.set(artist, (perArtist.get(artist) ?? 0) + 1);
    if (c.seed) {
      perSeed.set(c.seed, (perSeed.get(c.seed) ?? 0) + 1);
      if (c.kind === 'relation') perSeedRelations.set(c.seed, (perSeedRelations.get(c.seed) ?? 0) + 1);
    }
  };
  for (const c of [...relations, ...byArtist, ...byLabel, ...byGenre, ...byStyle]) accept(c);
  const personal = items.length;
  for (const p of pool) accept(fromPick(p, 'Selección de la redacción', 'editorial'));
  return { items, personal, lookups, discarded };
}
