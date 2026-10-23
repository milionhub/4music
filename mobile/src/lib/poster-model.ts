/**
 * Carteles 3.2: de la extracción de la IA al evento editable, y las ediciones del usuario. Lógica pura (sin React ni
 * almacenamiento), probada en tests/posters.test.ts.
 *
 * Reglas: un artista aparece una sola vez por evento y puede estar en varias actuaciones; un B2B es UNA actuación
 * con varios artistas; lo ausente es null; lo editado o confirmado a mano (`meta.locked`) nunca lo cambia un
 * reanálisis; lo eliminado (`discarded`) no vuelve; lo que contradice al evento entra como sugerencia.
 */
import type {
  Flag, Meta, PosterArtist, PosterEvent, PosterExtraction, PosterImage, PosterSet, PosterSuggestion,
} from '../types/poster.ts';

export const MAX_CALLS = 3; // 1 análisis inicial + 2 recuperaciones pedidas por el usuario

// --- Utilidades -------------------------------------------------------------------------------------------------

/** Clave de comparación: sin acentos, mayúsculas, puntuación final ni espacios repetidos. La grafía se conserva aparte. */
export function normName(s: string | null | undefined): string {
  return (s ?? '')
    .normalize('NFKD')
    .replace(/[̀-ͯ]/g, '')
    .toLowerCase()
    .replace(/[.,;:!]+$/g, '')
    .replace(/\s+/g, ' ')
    .trim();
}

function clean(s: string | null | undefined): string | null {
  const v = (s ?? '').replace(/\s+/g, ' ').trim();
  return v ? v : null;
}

const meta = (origin: PosterEvent['meta']['origin'], printed: string | null = null, flags: Flag[] = []): Meta =>
  ({ origin, flags, locked: [], printed });

const lock = (m: Meta, ...fields: string[]): Meta => ({ ...m, locked: [...new Set([...m.locked, ...fields])] });

function nextId(ids: string[], prefix: string): string {
  let max = 0;
  for (const id of ids) {
    const n = id.startsWith(prefix) ? Number(id.slice(prefix.length)) : NaN;
    if (Number.isFinite(n) && n > max) max = n;
  }
  return `${prefix}${max + 1}`;
}

function touch(e: PosterEvent, now: string): PosterEvent {
  return { ...e, updatedAt: now };
}

/** «22:00», «22h», «22.30», «10PM» y rangos «22:00 - 06:00». Devuelve null si no hay una hora reconocible. */
export function parseTime(text: string | null | undefined): { start: string; end: string | null } | null {
  if (!text) return null;
  const re = /(\d{1,2})(?:[:.h](\d{2}))?\s*(am|pm|h)?/gi;
  const found: string[] = [];
  for (const m of text.matchAll(re)) {
    let h = Number(m[1]);
    const min = m[2] ? Number(m[2]) : 0;
    const suffix = m[3]?.toLowerCase();
    if (!m[2] && !suffix) continue; // un número suelto (día, escenario) no es una hora
    if (suffix === 'pm' && h < 12) h += 12;
    if (suffix === 'am' && h === 12) h = 0;
    if (h > 23 || min > 59) continue;
    found.push(`${String(h).padStart(2, '0')}:${String(min).padStart(2, '0')}`);
    if (found.length === 2) break;
  }
  return found.length ? { start: found[0], end: found[1] ?? null } : null;
}

/** Hora válida «HH:MM» escrita por el usuario (o null si está vacía). undefined = inválida. */
export function userTime(text: string): string | null | undefined {
  const v = text.trim();
  if (!v) return null;
  const m = /^(\d{1,2})[:.h]?(\d{2})$/.exec(v);
  if (!m || Number(m[1]) > 23 || Number(m[2]) > 59) return undefined;
  return `${m[1].padStart(2, '0')}:${m[2]}`;
}

const endsNextDay = (start: string | null, end: string | null) => !!(start && end && end < start);

const B2B_SPLIT = /\s+(b2b|b3b|b4b|vs\.?)\s+/i;

function connectorOf(text: string | null, size: number): string {
  const m = text ? /\b(b2b|b3b|b4b|vs)\b/i.exec(text) : null;
  return m ? m[1].toUpperCase() : size > 2 ? `B${size}B` : 'B2B';
}

// --- Extracción → borrador ----------------------------------------------------------------------------------------

type DraftSet = {
  names: string[]; connector: string | null; day: string | null; dayIso: string | null; stage: string | null;
  block: string | null; start: string | null; end: string | null; timeScope: PosterSet['timeScope']; printed: string;
};

function draftOf(ext: PosterExtraction): DraftSet[] {
  const groups = ext.b2b.map((b) => ({ names: b.artists, keys: b.artists.map(normName), text: b.text, used: false }));
  const times = new Map(ext.individual_times.map((t) => [normName(t.name), parseTime(t.time)]));
  const out: DraftSet[] = [];
  const emitted = new Set<string>();

  type Ctx = Pick<DraftSet, 'day' | 'dayIso' | 'stage' | 'block'> & { time: string | null };
  function emit(rawNames: string[], ctxOf: (i: number) => Ctx) {
    // Un nombre «A B2B B» que la IA no separó se trata como el B2B que es.
    const names: { name: string; i: number; joined?: string[]; text?: string }[] = [];
    rawNames.forEach((name, i) => {
      const parts = name.split(B2B_SPLIT).filter((p, k) => k % 2 === 0).map((p) => p.trim()).filter(Boolean);
      names.push(parts.length > 1 ? { name, i, joined: parts, text: name } : { name, i });
    });
    const keys = new Set(names.map((n) => normName(n.name)));
    const used = new Set<string>();
    for (const n of names) {
      const k = normName(n.name);
      if (used.has(k)) continue;
      const ctx = ctxOf(n.i);
      const block = parseTime(ctx.time);
      const base = { day: ctx.day, dayIso: ctx.dayIso, stage: ctx.stage, block: ctx.block };
      const g = n.joined ? null : groups.find((g) => g.keys.includes(k) && g.keys.every((x) => keys.has(x)));
      const members = n.joined ?? g?.names;
      if (members) {
        if (g) {
          g.used = true;
          g.keys.forEach((x) => used.add(x));
        }
        used.add(k);
        members.forEach((m) => emitted.add(normName(m)));
        out.push({ ...base, names: members, connector: connectorOf(n.text ?? g?.text ?? null, members.length),
          start: block?.start ?? null, end: block?.end ?? null, timeScope: block ? 'block' : null,
          printed: n.text ?? g?.text ?? members.join(' B2B ') });
        continue;
      }
      used.add(k);
      emitted.add(k);
      const own = times.get(k);
      const t = own ?? block;
      out.push({ ...base, names: [n.name], connector: null, start: t?.start ?? null, end: t?.end ?? null,
        timeScope: own ? 'set' : block ? 'block' : null, printed: n.name });
    }
  }

  for (const s of ext.sessions) {
    emit(s.artists, () => ({ day: s.date?.text ?? null, dayIso: s.date?.iso ?? null, stage: s.stage, block: s.label, time: s.time }));
  }
  if (ext.artists.length) {
    // El día de un artista solo lleva fecha ISO si coincide con una fecha impresa que la tiene (año visible).
    const isoOf = (day: string | null) => ext.dates.find((d) => day !== null && normName(d.text) === normName(day))?.iso ?? null;
    emit(ext.artists.map((a) => a.name), (i) => ({ day: ext.artists[i].day, dayIso: isoOf(ext.artists[i].day), stage: ext.artists[i].stage, block: null, time: null }));
  }
  // B2B cuyos miembros no aparecieron en ningún bloque: se conserva la actuación conjunta tal cual.
  for (const g of groups) {
    if (!g.used && g.keys.every((k) => !emitted.has(k))) {
      out.push({ names: g.names, connector: connectorOf(g.text, g.names.length), day: null, dayIso: null, stage: null,
        block: null, start: null, end: null, timeScope: null, printed: g.text ?? g.names.join(' B2B ') });
    }
  }
  return out;
}

// --- Crear y fusionar ----------------------------------------------------------------------------------------------

export type EventInit = { id: string; now: string; image: PosterImage; fingerprint: string | null; assetId: string | null };

function emptyEvent(init: EventInit, model: string): PosterEvent {
  return {
    schema: 1, id: init.id, fingerprint: init.fingerprint, assetId: init.assetId, status: 'draft',
    name: null, dateText: null, location: null, meta: meta('ai'), image: init.image,
    days: [], stages: [], artists: [], sets: [], palette: { source: 'fallback', seeds: [] }, discarded: [], suggestions: [],
    analysis: { model, calls: 0, incomplete: false, lastError: null, review: [], at: init.now },
    createdAt: init.now, updatedAt: init.now,
  };
}

export function fromExtraction(ext: PosterExtraction, init: EventInit): PosterEvent {
  const e = mergeExtraction(emptyEvent(init, ext.model), ext, init.now);
  const seeds = ext.colors.filter((c) => /^#[0-9A-F]{6}$/i.test(c));
  return { ...e, palette: seeds.length >= 2 ? { source: 'poster', seeds } : { source: 'fallback', seeds: [] } };
}

/**
 * Añade una extracción (inicial, continuación o región) sin tocar lo protegido: rellena lo que está vacío, añade lo
 * nuevo, ignora lo descartado y convierte cualquier contradicción en sugerencia. Nunca borra nada.
 */
export function mergeExtraction(event: PosterEvent, ext: PosterExtraction, now: string): PosterEvent {
  const e: PosterEvent = JSON.parse(JSON.stringify(event)); // copia profunda (Hermes no garantiza structuredClone)
  const discarded = new Set(e.discarded);
  const suggest = (s: Omit<PosterSuggestion, 'id'>) => {
    if (e.suggestions.some((x) => x.target === s.target && x.targetId === s.targetId && x.field === s.field && normName(x.value) === normName(s.value))) return;
    e.suggestions.push({ ...s, id: nextId(e.suggestions.map((x) => x.id), 'g') });
  };

  const dateText = ext.dates.length ? ext.dates.map((d) => d.text).join(' · ') : null;
  for (const [field, value] of [['name', ext.event_name], ['dateText', dateText], ['location', ext.location]] as const) {
    const v = clean(value);
    if (!v) continue;
    if (e[field] === null && !e.meta.locked.includes(field)) e[field] = v;
    else if (normName(e[field]) !== normName(v)) {
      suggest({ target: 'event', targetId: null, field, value: v, label: `${FIELD_LABEL[field]}: «${v}»` });
    }
  }

  const stageId = (name: string | null): string | null => {
    const v = clean(name);
    if (!v) return null;
    const found = e.stages.find((s) => normName(s.name) === normName(v));
    if (found) return found.id;
    const id = nextId(e.stages.map((s) => s.id), 'st');
    e.stages.push({ id, name: v, meta: meta('ai', v) });
    return id;
  };
  const dayId = (label: string | null, iso: string | null): string | null => {
    const v = clean(label);
    if (!v) return null;
    const found = e.days.find((d) => normName(d.label) === normName(v));
    if (found) {
      if (found.date === null && iso && !found.meta.locked.includes('date')) found.date = iso;
      return found.id;
    }
    const id = nextId(e.days.map((d) => d.id), 'd');
    e.days.push({ id, label: v, date: iso, order: e.days.length, meta: meta('ai', v) });
    return id;
  };
  ext.stages.forEach((s) => stageId(s));

  const uncertain = new Set(ext.uncertain.map(normName));
  const artistId = (name: string): string | null => {
    const k = normName(name);
    if (!k || discarded.has(k)) return null;
    const found = e.artists.find((a) => normName(a.name) === k || normName(a.meta.printed) === k);
    if (found) return found.id;
    const id = nextId(e.artists.map((a) => a.id), 'a');
    const flags: Flag[] = uncertain.has(k) ? ['model_uncertain'] : [];
    e.artists.push({ id, name: name.trim(), meta: meta('ai', name.trim(), flags), link: { status: 'pending', catalog: null, refId: null } });
    return id;
  };

  const sameCtx = (a: string | null, b: string | null) => a === null || b === null || a === b;
  let order = e.sets.reduce((m, s) => Math.max(m, s.order + 1), 0);
  for (const d of draftOf(ext)) {
    const ids = [...new Set(d.names.map(artistId).filter((x): x is string => x !== null))];
    if (!ids.length) continue;
    const ctx = { dayId: dayId(d.day, d.dayIso), stageId: stageId(d.stage), block: clean(d.block) };
    const key = [...ids].sort().join('|');
    const same = e.sets.find((s) => [...s.artistIds].sort().join('|') === key && sameCtx(s.dayId, ctx.dayId)
      && sameCtx(s.stageId, ctx.stageId) && sameCtx(s.block, ctx.block));
    if (same) {
      for (const f of ['dayId', 'stageId', 'block'] as const) {
        if (same[f] === null && ctx[f] !== null && !same.meta.locked.includes(f)) same[f] = ctx[f];
      }
      if (d.start && !same.meta.locked.includes('start')) {
        if (same.start === null) Object.assign(same, { start: d.start, end: d.end, timeScope: d.timeScope, endsNextDay: endsNextDay(d.start, d.end) });
        else if (same.start !== d.start) suggest({ target: 'set', targetId: same.id, field: 'start', value: d.start, label: `Hora ${d.start} para ${setLabel(e, same)}` });
      }
      continue;
    }
    if (ids.length > 1) {
      // B2B nuevo sobre actuaciones individuales ya existentes: no se reestructura solo, se sugiere.
      const solos = ids.map((id) => e.sets.find((s) => s.artistIds.length === 1 && s.artistIds[0] === id && sameCtx(s.dayId, ctx.dayId) && sameCtx(s.stageId, ctx.stageId)));
      if (solos.every(Boolean)) {
        suggest({ target: 'set', targetId: null, field: 'b2b', value: ids.join(','),
          label: `Unir en B2B: ${ids.map((id) => e.artists.find((a) => a.id === id)?.name).join(' + ')}` });
        continue;
      }
    }
    e.sets.push({
      id: nextId(e.sets.map((s) => s.id), 's'), artistIds: ids, connector: ids.length > 1 ? d.connector : null,
      ...ctx, start: d.start, end: d.end, timeScope: d.timeScope, endsNextDay: endsNextDay(d.start, d.end),
      order: order++, meta: meta('ai', d.printed),
    });
  }

  const reviewNotes = ext.review.map((r) => (r.value ? `${r.reason}: ${r.value}` : r.reason));
  const incomplete = ext.mode === 'region' ? e.analysis.incomplete : !ext.complete;
  e.analysis = {
    ...e.analysis, model: ext.model, calls: e.analysis.calls + 1, incomplete, lastError: null,
    review: [...new Set([...e.analysis.review, ...reviewNotes])], at: now,
  };
  if (e.status !== 'confirmed') e.status = incomplete ? 'partial' : 'draft';
  return touch(e, now);
}

const FIELD_LABEL = { name: 'Nombre', dateText: 'Fecha', location: 'Lugar' } as const;

// --- Avisos de revisión (deterministas) ----------------------------------------------------------------------------

export const FLAG_TEXT: Record<Flag, string> = {
  similar_name: 'Se parece a otro nombre del cartel',
  odd_spelling: 'Grafía poco habitual: compruébala',
  possible_brand: 'Puede ser una marca, el lugar o un escenario',
  collective: 'Colectivo con miembros: ¿un solo artista?',
  possible_merge: 'Bloque con demasiados artistas: puede mezclar dos bloques',
  model_uncertain: 'La IA no lo leyó con claridad',
  block_time: 'Hora del bloque, no de cada artista',
  year_not_printed: 'Año no impreso',
  incomplete: 'Análisis incompleto',
  suspicious_name: 'No parece un nombre de artista: compruébalo',
};

/**
 * Nombre manifiestamente anómalo (3.4): solo es un aviso, nunca se elimina. Prudente con los nombres reales de la
 * electrónica: «999999999», «2562», «808 State», «Future.666», «Âme» o «&ME» no se señalan.
 * - Solo cifras y 10 o más (p. ej. «9999999999»: parece un teléfono o un código, no un artista).
 * - Mayoría de símbolos (menos de la mitad de los caracteres son letras o cifras).
 * - Longitud de frase: más de 48 caracteres o más de 7 palabras (varias líneas leídas como un nombre).
 */
export function suspiciousName(name: string): boolean {
  const compact = name.replace(/\s+/g, '');
  if (!compact) return false;
  const letters = (compact.match(/\p{L}/gu) ?? []).length;
  const digits = (compact.match(/\p{N}/gu) ?? []).length;
  if (!letters && digits >= 10) return true;
  if (letters + digits < compact.length / 2) return true;
  return name.trim().length > 48 || name.trim().split(/\s+/).length > 7;
}

function similarity(a: string, b: string): number {
  if (a === b) return 1;
  const m = a.length, n = b.length;
  if (!m || !n) return 0;
  let prev = Array.from({ length: n + 1 }, (_, j) => j);
  for (let i = 1; i <= m; i++) {
    const cur = [i];
    for (let j = 1; j <= n; j++) cur[j] = Math.min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (a[i - 1] === b[j - 1] ? 0 : 1));
    prev = cur;
  }
  return 1 - prev[n] / Math.max(m, n);
}

const NOISE = /\b(presents?|tickets?|line ?up|www|https?|\.com|entradas|info)\b|@/i;

function artistFlags(e: PosterEvent, a: PosterArtist): Flag[] {
  if (a.meta.locked.includes('name')) return [];
  const flags = new Set<Flag>(a.meta.flags);
  const k = normName(a.name);
  if (e.artists.some((o) => o.id !== a.id && similarity(normName(o.name), k) >= 0.85)) flags.add('similar_name');
  const words = a.name.split(/\s+/);
  if (k.length <= 2 || words.some((w) => (/\d/.test(w) && /\p{L}/u.test(w)) || /[A-Z]{2,}[a-z]+/.test(w))
    || /[^\p{L}\p{N}\s.&'’\-:!+()[\]/*]/u.test(a.name)) flags.add('odd_spelling');
  // El cabeza de cartel suele dar nombre al evento («NOW HERE BY PACO OSUNA»): ahí solo cuenta la coincidencia exacta.
  const places = [e.location, ...e.stages.map((s) => s.name)].map(normName).filter(Boolean);
  if (NOISE.test(a.name) || /^\p{L}+\d{2}$/u.test(k) || normName(e.name) === k
    || places.some((c) => c === k || (k.length > 3 && c.includes(k)))) flags.add('possible_brand');
  if (/[([].+[)\]]/.test(a.name)) flags.add('collective');
  if (suspiciousName(a.name)) flags.add('suspicious_name');
  return [...flags];
}

/** Avisos actuales por id (artistas, actuaciones y 'event'). Lo confirmado o editado a mano ya no se señala. */
export function reviewFlags(e: PosterEvent): Map<string, Flag[]> {
  const out = new Map<string, Flag[]>();
  for (const a of e.artists) {
    const f = artistFlags(e, a);
    if (f.length) out.set(a.id, f);
  }
  const groups = new Map<string, PosterSet[]>();
  for (const s of e.sets) {
    const key = `${s.dayId}|${s.stageId}|${s.block}`;
    groups.set(key, [...(groups.get(key) ?? []), s]);
  }
  const sizes = [...groups.values()].map((g) => g.length).sort((x, y) => x - y);
  const median = sizes.length ? sizes[Math.floor(sizes.length / 2)] : 0;
  for (const g of groups.values()) {
    if (groups.size >= 3 && g.length >= 6 && g.length >= median * 2) {
      for (const s of g) if (!s.meta.locked.includes('confirmed')) out.set(s.id, ['possible_merge']);
    }
  }
  const eventFlags: Flag[] = [];
  if (e.analysis.incomplete) eventFlags.push('incomplete');
  if (eventFlags.length) out.set('event', eventFlags);
  return out;
}

/** Nombre, fecha o lugar sin revisar: la IA falló aquí en Fase 1.4, así que siempre se piden confirmar. */
export const eventFieldNeedsCheck = (e: PosterEvent, field: 'name' | 'dateText' | 'location') =>
  e[field] !== null && !e.meta.locked.includes(field);

// --- Ediciones del usuario -------------------------------------------------------------------------------------------

export function updateEvent(e: PosterEvent, patch: Partial<Record<'name' | 'dateText' | 'location', string>>, now: string): PosterEvent {
  const next = { ...e, meta: lock(e.meta, ...Object.keys(patch)) };
  for (const [k, v] of Object.entries(patch) as ['name' | 'dateText' | 'location', string][]) next[k] = clean(v);
  return touch(next, now);
}

export function confirmEventField(e: PosterEvent, field: 'name' | 'dateText' | 'location', now: string): PosterEvent {
  return touch({ ...e, meta: lock(e.meta, field) }, now);
}

/** Renombra; si el nuevo nombre ya es de otro artista del evento, se unifican (sin duplicar la identidad). */
export function renameArtist(e: PosterEvent, id: string, name: string, now: string): PosterEvent {
  const v = clean(name);
  if (!v) return e;
  const other = e.artists.find((a) => a.id !== id && normName(a.name) === normName(v));
  if (other) {
    const sets = e.sets.map((s) => ({ ...s, artistIds: [...new Set(s.artistIds.map((x) => (x === id ? other.id : x)))] }));
    return touch({ ...e, artists: e.artists.filter((a) => a.id !== id), sets }, now);
  }
  // Otro nombre, otra identidad: el enlace automático se vuelve a resolver; el elegido a mano se respeta.
  const relink = (a: PosterArtist) => normName(a.name) !== normName(v) && a.link.origin !== 'user';
  const renamed = (a: PosterArtist): PosterArtist => {
    if (!relink(a)) return { ...a, name: v, meta: lock(a.meta, 'name') };
    const next: PosterArtist = { ...a, name: v, meta: lock(a.meta, 'name'), link: { status: 'pending', catalog: null, refId: null } };
    delete next.styles; // eran los del perfil anterior
    return next;
  };
  return touch({ ...e, artists: e.artists.map((a) => (a.id === id ? renamed(a) : a)) }, now);
}

export function confirmArtist(e: PosterEvent, id: string, now: string): PosterEvent {
  return touch({ ...e, artists: e.artists.map((a) => (a.id === id ? { ...a, meta: lock(a.meta, 'name') } : a)) }, now);
}

/** Artista nuevo con su propia actuación (o reutiliza la identidad si ya existe en el evento). */
export function addArtist(e: PosterEvent, name: string, ctx: { dayId: string | null; stageId: string | null }, now: string): PosterEvent {
  const v = clean(name);
  if (!v) return e;
  const k = normName(v);
  const existing = e.artists.find((a) => normName(a.name) === k);
  const id = existing?.id ?? nextId(e.artists.map((a) => a.id), 'a');
  const artists = existing ? e.artists : [...e.artists, { id, name: v, meta: lock(meta('user', null), 'name'), link: { status: 'pending' as const, catalog: null, refId: null } }];
  const set: PosterSet = {
    id: nextId(e.sets.map((s) => s.id), 's'), artistIds: [id], connector: null, dayId: ctx.dayId, stageId: ctx.stageId,
    block: null, start: null, end: null, timeScope: null, endsNextDay: false,
    order: e.sets.reduce((m, s) => Math.max(m, s.order + 1), 0), meta: lock(meta('user'), 'artistIds', 'dayId', 'stageId'),
  };
  return touch({ ...e, artists, sets: [...e.sets, set], discarded: e.discarded.filter((d) => d !== k) }, now);
}

function discard(e: PosterEvent, ids: string[]): PosterEvent {
  const gone = e.artists.filter((a) => ids.includes(a.id));
  const keys = gone.flatMap((a) => [normName(a.name), normName(a.meta.printed)]).filter(Boolean);
  return { ...e, artists: e.artists.filter((a) => !ids.includes(a.id)), discarded: [...new Set([...e.discarded, ...keys])] };
}

/** Elimina al artista de todas sus actuaciones; un B2B que se queda con uno pasa a individual. No volverá a aparecer. */
export function removeArtist(e: PosterEvent, id: string, now: string): PosterEvent {
  const sets = e.sets
    .map((s) => (s.artistIds.includes(id) ? { ...s, artistIds: s.artistIds.filter((x) => x !== id), meta: lock(s.meta, 'artistIds') } : s))
    .filter((s) => s.artistIds.length > 0)
    .map((s) => (s.artistIds.length === 1 ? { ...s, connector: null } : s));
  return touch(discard({ ...e, sets }, [id]), now);
}

/** Elimina una actuación; sus artistas que no actúan en ninguna otra se eliminan también (y no vuelven). */
export function removeSet(e: PosterEvent, setId: string, now: string): PosterEvent {
  const set = e.sets.find((s) => s.id === setId);
  if (!set) return e;
  const sets = e.sets.filter((s) => s.id !== setId);
  const orphans = set.artistIds.filter((id) => !sets.some((s) => s.artistIds.includes(id)));
  return touch(discard({ ...e, sets }, orphans), now);
}

/** Une varias actuaciones en un único B2B (contexto y hora de la primera en el orden del cartel). */
export function joinSets(e: PosterEvent, setIds: string[], now: string): PosterEvent {
  const chosen = e.sets.filter((s) => setIds.includes(s.id)).sort((a, b) => a.order - b.order);
  if (chosen.length < 2) return e;
  const first = chosen[0];
  const artistIds = [...new Set(chosen.flatMap((s) => s.artistIds))];
  const joined: PosterSet = {
    ...first, artistIds, connector: artistIds.length > 2 ? `B${artistIds.length}B` : 'B2B',
    meta: lock({ ...first.meta, origin: 'user' }, 'artistIds'),
  };
  const sets = e.sets.filter((s) => !setIds.includes(s.id) || s.id === first.id).map((s) => (s.id === first.id ? joined : s));
  return touch({ ...e, sets }, now);
}

/** Separa un B2B en actuaciones individuales con el mismo día, escenario, bloque y hora. */
export function splitSet(e: PosterEvent, setId: string, now: string): PosterEvent {
  const set = e.sets.find((s) => s.id === setId);
  if (!set || set.artistIds.length < 2) return e;
  const ids = e.sets.map((s) => s.id);
  const parts: PosterSet[] = set.artistIds.map((artistId, i) => {
    const id = i === 0 ? set.id : nextId(ids, 's');
    ids.push(id);
    return { ...set, id, artistIds: [artistId], connector: null, order: set.order + i * 0.001, meta: lock({ ...set.meta, origin: 'user' }, 'artistIds') };
  });
  const sets = e.sets.flatMap((s) => (s.id === setId ? parts : [s]));
  return touch({ ...e, sets: sets.map((s, i) => ({ ...s, order: i })) }, now);
}

export type SetPatch = Partial<Pick<PosterSet, 'dayId' | 'stageId' | 'block' | 'start' | 'end'>>;

/** Cambia día, escenario, bloque u hora. Una hora escrita por el usuario es la de esa actuación. */
export function updateSet(e: PosterEvent, setId: string, patch: SetPatch, now: string): PosterEvent {
  const sets = e.sets.map((s) => {
    if (s.id !== setId) return s;
    const next = { ...s, ...patch, meta: lock(s.meta, ...Object.keys(patch)) };
    if ('start' in patch || 'end' in patch) next.timeScope = next.start || next.end ? 'set' : null;
    next.endsNextDay = endsNextDay(next.start, next.end);
    return next;
  });
  return touch({ ...e, sets }, now);
}

export function confirmSet(e: PosterEvent, setId: string, now: string): PosterEvent {
  return touch({ ...e, sets: e.sets.map((s) => (s.id === setId ? { ...s, meta: lock(s.meta, 'confirmed') } : s)) }, now);
}

export function addDay(e: PosterEvent, label: string, now: string): PosterEvent {
  const v = clean(label);
  if (!v || e.days.some((d) => normName(d.label) === normName(v))) return e;
  const day = { id: nextId(e.days.map((d) => d.id), 'd'), label: v, date: null, order: e.days.length, meta: lock(meta('user', null), 'label') };
  return touch({ ...e, days: [...e.days, day] }, now);
}

export function addStage(e: PosterEvent, name: string, now: string): PosterEvent {
  const v = clean(name);
  if (!v || e.stages.some((s) => normName(s.name) === normName(v))) return e;
  return touch({ ...e, stages: [...e.stages, { id: nextId(e.stages.map((s) => s.id), 'st'), name: v, meta: lock(meta('user', null), 'name') }] }, now);
}

export function applySuggestion(e: PosterEvent, id: string, now: string): PosterEvent {
  const s = e.suggestions.find((x) => x.id === id);
  if (!s) return e;
  const rest = { ...e, suggestions: e.suggestions.filter((x) => x.id !== id) };
  if (s.target === 'event' && (s.field === 'name' || s.field === 'dateText' || s.field === 'location')) {
    return updateEvent(rest, { [s.field]: s.value }, now);
  }
  if (s.field === 'start' && s.targetId) return updateSet(rest, s.targetId, { start: s.value }, now);
  if (s.field === 'b2b') {
    const ids = s.value.split(',');
    const solos = ids.map((aid) => rest.sets.find((x) => x.artistIds.length === 1 && x.artistIds[0] === aid)?.id).filter((x): x is string => !!x);
    return joinSets(rest, solos, now);
  }
  return touch(rest, now);
}

export const dismissSuggestion = (e: PosterEvent, id: string, now: string): PosterEvent =>
  touch({ ...e, suggestions: e.suggestions.filter((x) => x.id !== id) }, now);

export const confirmEvent = (e: PosterEvent, now: string): PosterEvent => touch({ ...e, status: 'confirmed' }, now);

export const recordError = (e: PosterEvent, message: string, now: string): PosterEvent =>
  touch({ ...e, analysis: { ...e.analysis, lastError: message } }, now);

// --- Lectura para la interfaz ----------------------------------------------------------------------------------------

export function setLabel(e: Pick<PosterEvent, 'artists'>, s: PosterSet): string {
  const names = s.artistIds.map((id) => e.artists.find((a) => a.id === id)?.name ?? '¿?');
  return names.join(` ${s.connector ?? 'B2B'} `);
}

export function setContext(e: PosterEvent, s: PosterSet): string {
  const stage = e.stages.find((x) => x.id === s.stageId)?.name;
  const time = s.start ? `${s.timeScope === 'block' ? 'bloque desde ' : ''}${s.start}${s.end ? `–${s.end}${s.endsNextDay ? ' (+1)' : ''}` : ''}` : null;
  return [s.block, stage ? `Escenario ${stage}` : null, time].filter(Boolean).join(' · ');
}

/** Actuaciones por día en el orden del cartel; las que no tienen día confirmado van aparte (day = null). */
export function groupByDay(e: PosterEvent): { day: PosterEvent['days'][number] | null; sets: PosterSet[] }[] {
  const sorted = [...e.sets].sort((a, b) => a.order - b.order);
  const days = [...e.days].sort((a, b) => a.order - b.order);
  const groups = days.map((day) => ({ day, sets: sorted.filter((s) => s.dayId === day.id) })).filter((g) => g.sets.length);
  const loose = sorted.filter((s) => !s.dayId || !e.days.some((d) => d.id === s.dayId));
  return loose.length ? [...groups, { day: null, sets: loose }] : groups;
}

/** Contexto para «Continuar análisis»: bloques y nombres ya leídos. */
export function knownContext(e: PosterEvent): { known_sessions: string[]; known_names: string[] } {
  const sessions = new Set<string>();
  for (const s of e.sets) {
    const day = e.days.find((d) => d.id === s.dayId)?.label;
    const stage = e.stages.find((x) => x.id === s.stageId)?.name;
    const label = [day, s.block, stage ? `stage ${stage}` : null].filter(Boolean).join(' ');
    if (label) sessions.add(label);
  }
  return { known_sessions: [...sessions], known_names: e.artists.map((a) => a.name) };
}
