/**
 * Carteles 3.5: qué enseña la vista rápida de un artista (Artist Spotlight). Lógica pura, probada en
 * tests/posters-explore.test.ts.
 *
 * - Foto: solo con derechos verificables (licencia libre conocida, página de origen y autor cuando la licencia exige
 *   atribución; o el catálogo editorial, con permiso documentado). Si falta algo, cartel tipográfico.
 * - «Sobre el artista»: solo texto que ya existe con su procedencia; nada se redacta al abrir la vista (sin LLM).
 *   Ver `artistSpotlight`. La música y la discografía están en el perfil completo.
 */
import type { ArtistIdentity, ArtistProfileResponse, SourceRef } from '@/types/music';

export type PhotoInfo = {
  url: string;
  page_url: string;
  author: string | null;
  license: string;
  license_url: string | null;
  source: 'wikimedia_commons' | 'editorial' | 'deezer';
};

// Misma lista que el backend (app/images.py): CC0, CC BY, CC BY-SA y dominio público; nunca NC ni ND.
const FREE_LICENSE = /^(CC0|CC[ -]BY(-SA)?( \d(\.\d)?)?|Public domain|PD\b)/i;
const NO_ATTRIBUTION = /^(CC0|Public domain|PD\b)/i;
const https = (u: string | null | undefined) => typeof u === 'string' && /^https:\/\/\S+$/.test(u);

export function verifiablePhoto(p: PhotoInfo | null | undefined): p is PhotoInfo {
  if (!p || !https(p.url) || !https(p.page_url)) return false;
  const license = (p.license ?? '').trim();
  const author = (p.author ?? '').trim();
  if (!license) return false;
  if (p.source === 'editorial') return !!author;
  // Deezer (V6, uso no comercial): sin licencia libre; se muestra como dato de Deezer, con enlace a su ficha.
  if (p.source === 'deezer') return /^https:\/\/(www\.)?deezer\.com\//.test(p.page_url);
  if (!FREE_LICENSE.test(license) || /\b(NC|ND)\b/i.test(license)) return false;
  return NO_ATTRIBUTION.test(license) || !!author;
}

/** Crédito completo (nunca truncado): autor, licencia y fuente. */
export function photoCredit(p: PhotoInfo): string {
  if (p.source === 'deezer') return `Foto: Deezer · ${p.license}`;
  const where = p.source === 'editorial' ? 'Catálogo editorial de Chromatic Underground' : 'Wikimedia Commons';
  return [p.author ? `Foto: ${p.author}` : 'Foto', p.license, where].join(' · ');
}

// Sin \b: en JavaScript no hay límite de palabra después de «ó».
/** Crédito breve sobre la foto (el completo va en «Fuentes»). */
export function photoShortCredit(p: PhotoInfo): string {
  if (p.source === 'deezer') return 'Foto · Deezer';
  return [p.author ? `Foto · ${p.author}` : 'Foto', p.source === 'editorial' ? null : p.license].filter(Boolean).join(' · ');
}

const BIRTH_WORD = String.raw`(?:naci(?:ó|da|do)|born|fallec\p{L}*|died|murió)(?!\p{L})`;
// «Capriati, nacido el 25 de julio de 1987 en Caserta, Italia, inició…» → «Capriati inició…»: sale la cláusula (con
// el país que la cierra), no la frase.
const BIRTH_CLAUSE = new RegExp(String.raw`,\s*${BIRTH_WORD}[^,.;]*\b\d{4}\b[^,.;]*(?:,\s*\p{Lu}[\p{L}-]*(?=,))*(?:,|(?=[.;]))`, 'giu');
const BIRTH_SENTENCE = new RegExp(String.raw`(?<!\p{L})${BIRTH_WORD}[^,.;]*\b\d{4}\b`, 'iu');
const DATED_PAREN = /\s*\([^()]*\b\d{4}\b[^()]*\)/g;
/** Extensión orientativa (~70–110 palabras con fuentes ricas). Es un techo, no un mínimo: nunca se rellena. */
export const SPOTLIGHT_MAX_WORDS = 110;

const words = (s: string) => s.split(/\s+/).filter(Boolean).length;
const fold = (s: string) => s.normalize('NFKD').replace(/[̀-ͯ]/g, '').toLowerCase().replace(/[^\p{L}\p{N}]+/gu, ' ').trim();
const mentions = (text: string, name: string) => !!fold(name) && ` ${fold(text)} `.includes(` ${fold(name)} `);
const join = (items: string[]) => (items.length < 2 ? items.join('') : `${items.slice(0, -1).join(', ')} y ${items[items.length - 1]}`);
const capitalize = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);

/** Párrafos del texto de origen sin fechas de nacimiento, cortados por frases completas hasta `max` palabras. */
export function fitText(text: string, max = SPOTLIGHT_MAX_WORDS): string[] {
  let total = 0;
  const out: string[] = [];
  for (const raw of text.split(/\n+/)) {
    const clean = raw.replace(DATED_PAREN, '').replace(BIRTH_CLAUSE, '').replace(/\s+/g, ' ').trim();
    const sentences = (clean.match(/[^.!?]+[.!?]+["»”)]*(?=\s|$)|[^.!?]+$/g) ?? [])
      .map((s) => s.trim())
      .filter((s) => s.length > 12 && /[.!?]["»”)]*$/.test(s) && !BIRTH_SENTENCE.test(s));
    const kept: string[] = [];
    for (const s of sentences) {
      if (total && total + words(s) > max) {
        if (kept.length) out.push(kept.join(' '));
        return out;
      }
      kept.push(s);
      total += words(s);
    }
    if (kept.length) out.push(kept.join(' '));
  }
  return out;
}

/** «Planet E» y «Planet E Communications» son el mismo sello: se queda el nombre completo. */
function distinctNames(names: string[]): string[][] {
  const groups: string[][] = [];
  for (const n of names) {
    const g = groups.find((x) => x.some((y) => fold(y).startsWith(fold(n)) || fold(n).startsWith(fold(y))));
    if (g) g.push(n);
    else groups.push([n]);
  }
  return groups;
}

/**
 * Una frase con relaciones documentadas (MusicBrainz: «label founder», «member of band», begin-area; Wikidata:
 * inicio de actividad; Discogs CC0: sellos que dirige). Omite lo que el texto ya menciona. null si no hay nada.
 * Formas neutras («natural de», «fundó», «ha formado parte»): no se presupone el género del artista. Con `subject`
 * (su nombre), un dato suelto es una frase completa: «Paco Osuna es natural de Barcelona.», no «Natural de Barcelona.».
 */
export function identityLine(id: ArtistIdentity | undefined, text = '', subject?: string): string | null {
  if (!id) return null;
  const fresh = (names: string[] = []) =>
    distinctNames(names).filter((g) => !g.some((n) => mentions(text, n))).map((g) => g.reduce((a, b) => (b.length > a.length ? b : a)));
  const lead: string[] = [];
  const verbs: string[] = [];
  if (id.origin && !mentions(text, id.origin)) {
    lead.push(id.origin_kind === 'birth' ? `natural de ${id.origin}` : `con origen en ${id.origin}`);
    verbs.push(id.origin_kind === 'birth' ? `es natural de ${id.origin}` : `tiene su origen en ${id.origin}`);
  }
  if (id.active_since && !text.includes(id.active_since)) {
    lead.push(`en activo desde ${id.active_since}`);
    verbs.push(`está en activo desde ${id.active_since}`);
  }
  const founded = fresh(id.founded_labels);
  const run = fresh((id.run_labels ?? []).filter((l) => !founded.includes(l)));
  const projects = fresh(id.projects).slice(0, 3);
  const members = fresh(id.members).slice(0, 4);
  const acts = [
    founded.length ? `fundó ${founded.length > 1 ? 'los sellos' : 'el sello'} ${join(founded.slice(0, 3))}` : null,
    run.length ? `dirige ${run.length > 1 ? 'los sellos' : 'el sello'} ${join(run.slice(0, 2))}` : null,
    projects.length ? `ha formado parte de ${join(projects)}` : null,
    members.length ? `sus integrantes son ${join(members)}` : null,
  ].filter((a): a is string => !!a);
  if (!lead.length && !acts.length) return null;
  if (lead.length && acts.length) return capitalize(`${join(lead)}, ${join(acts)}.`);
  const body = lead.length ? (subject ? join(verbs) : join(lead)) : join(acts);
  return subject ? `${subject} ${body}.` : `${capitalize(body)}.`;
}

export type Spotlight = {
  /** Párrafos listos para mostrar; vacío si no hay nada verificado que contar (nunca se inventa un relleno). */
  paragraphs: string[];
  /** De dónde sale el texto: biografía del perfil, introducción de Wikipedia, descripción de Wikidata o solo datos. */
  basis: 'editorial' | 'generated' | 'wikipedia' | 'wikidata' | 'facts' | null;
  sources: SourceRef[];
  /** El extracto literal se ha recortado (fechas o extensión): la atribución lo indica (CC BY-SA). */
  adapted: boolean;
};

type ProfileText = Pick<ArtistProfileResponse, 'artist' | 'bio' | 'summary' | 'identity' | 'sources'>;

/**
 * Presentación determinista, sin LLM ni peticiones extra (todo viene en GET /v1/artists/{mbid}, por MBID: un
 * homónimo elegido a mano trae su propio texto). Prioridad:
 * 1. Biografía del perfil, editorial revisada o generada y validada antes contra hechos con fuente (no al abrir).
 * 2. Introducción de Wikipedia en español del ítem verificado, literal y atribuida.
 * 3. Descripción de Wikidata en español.
 * En 2 y 3 se añade una frase con relaciones documentadas que el texto no menciona. Sin datos: vacío.
 */
export function artistSpotlight(p: ProfileText): Spotlight {
  const bio = p.bio && p.bio.language === 'es' ? p.bio : null;
  if (bio && bio.kind !== 'factual') {
    const paragraphs = fitText(bio.text);
    return { paragraphs, basis: paragraphs.length ? bio.kind : null, sources: bio.sources, adapted: false };
  }
  const summary = p.summary && p.summary.language === 'es' ? p.summary : null;
  const base = summary ? fitText(summary.text) : bio ? fitText(bio.text) : [];
  const facts = identityLine(p.identity, base.join(' '), p.artist.name);
  // Discogs (CC0) solo aporta sellos: se cita si la frase nombra alguno.
  const labels = [...(p.identity?.founded_labels ?? []), ...(p.identity?.run_labels ?? [])];
  const factRefs = !facts ? [] : p.sources.filter((s) => s.label === 'MusicBrainz' || (s.label.startsWith('Discogs') && labels.some((l) => facts.includes(l))));
  const sources = [...(summary ? [summary.source] : bio && base.length ? bio.sources : []), ...factRefs];
  const unique = sources.filter((s, i) => sources.findIndex((t) => t.url === s.url) === i);
  if (summary && base.length) {
    const adapted = base.join(' ') !== summary.text.replace(/\s+/g, ' ').trim();
    // Un dato suelto («Natural de Barcelona.») cierra el último párrafo; varias relaciones forman uno propio.
    const paragraphs = !facts ? base : words(facts) < 10 ? [...base.slice(0, -1), `${base[base.length - 1]} ${facts}`] : [...base, facts];
    return { paragraphs, basis: 'wikipedia', sources: unique, adapted };
  }
  if (bio && base.length) return { paragraphs: [[...base, facts].filter(Boolean).join(' ')], basis: 'wikidata', sources: unique, adapted: false };
  return facts ? { paragraphs: [facts], basis: 'facts', sources: unique, adapted: false } : { paragraphs: [], basis: null, sources: [], adapted: false };
}

/** Condiciones de la licencia: la URL que da la fuente o, para las Creative Commons conocidas, su página oficial. */
export function licenseUrl(license: string | null | undefined, given?: string | null): string | null {
  if (https(given)) return given!;
  const l = (license ?? '').trim();
  if (/^CC0\b/i.test(l)) return 'https://creativecommons.org/publicdomain/zero/1.0/';
  const m = l.match(/^CC[ -](BY(?:-SA)?)[ -](\d\.\d)\b/i);
  return m ? `https://creativecommons.org/licenses/${m[1].toLowerCase()}/${m[2]}/` : null;
}

export type CreditLink = { label: string; url: string };
export type Credit = { title: string; detail: string; links: CreditLink[] };

const BASIS_DETAIL: Record<NonNullable<Spotlight['basis']>, string> = {
  editorial: 'Texto editorial revisado, con estas fuentes',
  generated: 'Biografía elaborada a partir de estas fuentes',
  wikipedia: '',
  wikidata: 'Descripción breve de Wikidata y datos documentados',
  facts: 'Datos documentados',
};

const sourceLinks = (sources: SourceRef[]): CreditLink[] =>
  sources.flatMap((s) => {
    const terms = s.license && s.license !== 'CC0' ? licenseUrl(s.license) : null;
    return [{ label: s.license ? `${s.label} (${s.license})` : s.label, url: s.url },
      ...(terms ? [{ label: `Licencia ${s.license}`, url: terms }] : [])];
  });

/**
 * «Fuentes y créditos» de la vista rápida: todo lo que antes iba en líneas visibles, completo (autor, fuente,
 * licencia con sus condiciones, atribución del texto y si se ha adaptado). Sin foto acreditable no hay entrada de
 * foto (se muestra el cartel tipográfico).
 */
export function spotlightCredits(photo: PhotoInfo | null, spotlight: Spotlight | null): Credit[] {
  const out: Credit[] = [];
  if (photo && verifiablePhoto(photo)) {
    const terms = licenseUrl(photo.license, photo.license_url);
    out.push({ title: 'Fotografía', detail: photoCredit(photo), links: [
      { label: photo.source === 'editorial' ? 'Ver el permiso y la fuente' : 'Ver la fuente original', url: photo.page_url },
      ...(terms ? [{ label: `Licencia ${photo.license}`, url: terms }] : []),
    ] });
  }
  if (spotlight?.paragraphs.length && spotlight.basis) {
    if (spotlight.basis === 'wikipedia') {
      const [text, ...data] = spotlight.sources;
      out.push({ title: 'Texto', detail: `${spotlight.adapted ? 'Extracto adaptado (se han omitido fechas o frases para abreviarlo)' : 'Extracto literal'} de ${text.label}${text.license ? ` · ${text.license}` : ''}`,
        links: sourceLinks([text]) });
      if (data.length) out.push({ title: 'Datos añadidos', detail: 'Relaciones documentadas que el extracto no menciona', links: sourceLinks(data) });
    } else {
      out.push({ title: 'Texto', detail: BASIS_DETAIL[spotlight.basis], links: sourceLinks(spotlight.sources) });
    }
  }
  return out;
}
