"""«Más allá de la cabina» (Artist Intelligence v4): de una a tres historias breves y verificables por artista.

- Evidencia: los mismos documentos que la biografía (MusicBrainz, Wikidata, Wikipedia en es/en u otro idioma, web
  oficial y notas CC0 de Discogs) más una trayectoria estructurada de MusicBrainz (primer lanzamiento propio y su
  sello, sellos donde más publica, lanzamientos conjuntos) y los perfiles CC0 de los sellos que el propio perfil
  de Discogs enlaza. De todo ello, el selector editorial (facts.py) elige los hechos.
- Redacción: Groq escribe a partir de esos hechos numerados y cada historia cita los suyos. Groq no es una fuente:
  cada historia se valida contra los hechos que cita (biography.story_issue) y se descarta si algo no consta.
- Sin Groq, o si ninguna historia supera la validación: historias deterministas con datos estructurados.
- Caché propia (kind «stories», versionada): la ficha nunca espera a esta investigación.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Callable

from app import biography, facts, schemas, store
from app.groq_client import GroqClient, GroqError
from app.profile import EXCLUDED_SECONDARY, OWN_PRIMARY_TYPES, base_title
from app.sources import SourceDoc

KIND = "stories"
VERSION = 6  # v6: títulos concretos (sin genéricos), sin historias de solo géneros, primer lanzamiento sin DJ mixes
# v5: nombres civiles que incluyen el artístico; sin autopromoción («esencia», «tradición»)
TTL_GENERATED_S = 60 * 24 * 3600   # historias validadas: dos meses
TTL_STRUCTURED_S = 24 * 3600       # solo estructuradas (sin Groq o rechazadas): se reintenta al día siguiente
MAX_EVIDENCE = 16
MIN_EVIDENCE = 3                   # con menos hechos no se pide redacción: bastan las estructuradas
KEYS = ("inicios", "universo", "momento")
TRAJECTORY_LABEL = "MusicBrainz (trayectoria)"

SYSTEM = (
    "Eres editor de una revista de música electrónica underground y escribes en español de España, con frases "
    "concretas y naturales. Escribes historias breves sobre un artista usando EXCLUSIVAMENTE los HECHOS numerados; "
    "cada historia cita en fact_ids los hechos que usa. Prohibido añadir algo que no esté en ellos: causas, "
    "valoraciones, importancia, éxito, influencia, géneros, nacionalidades, lugares o fechas que no aparezcan. No "
    "menciones fuentes ni bases de datos, ni recuentos de lanzamientos. Distingue con cuidado fundar, dirigir, publicar "
    "en un sello, actuar, colaborar y ser residente: «label» es «sello», «run by» es «dirigido por». Si un hecho está "
    "en otro idioma, tradúcelo con fidelidad sin añadir nada. No uses el nombre civil de una persona. No expliques "
    "significados, motivos ni consecuencias (nada de «consolidando», «marcando», «refleja su visión», «se inspira», "
    "«gracias a»), ni deduzcas nada de un lugar asociado: cuenta solo lo que pasó, con sus nombres y fechas. "
    "Tipos de historia: «inicios» (cómo y dónde empezó, primeros proyectos o lanzamientos), «universo» (sellos, "
    "fiestas, colectivos, residencias o proyectos propios; integrantes de un dúo o grupo) y «momento» (un hito "
    "concreto, un cambio de sonido, un lanzamiento señalado o una curiosidad documentada). Escribe solo las que los "
    "hechos respalden de verdad: mejor una historia sólida que tres pobres, y nunca dos historias con el mismo dato. "
    "No marques el género de la persona si los hechos no lo indican: usa construcciones neutras («nació en», «su primer "
    "EP», «se dedica a la producción»). No describas funciones ni actividades que no consten (qué hace en su sello, para quién publica, cómo trabaja). "
    "Cada frase debe poder señalarse en un hecho concreto. Cada historia: un título de 2 a 5 palabras, sin dos puntos, "
    "con gancho de revista y concreto: nombra algo del propio hecho (un sello, un club, una ciudad, un título, un año), "
    "como «Desde Detroit, a los 17», «El nacimiento de Plus 8» o «Una noche en Warehouse '92». Nunca títulos genéricos "
    "(«Primer lanzamiento», «Primeros pasos», «Estilo musical», «Su propio universo», «Sello y proyecto», «Colaboraciones»). "
    "No escribas una historia que solo diga sus géneros o estilos: eso ya está en la ficha. El texto, de 15 a 50 "
    "palabras en un solo párrafo, sin listas ni preguntas; si los hechos dan para menos, escribe menos.")

SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {"stories": {"type": "array", "items": {
        "type": "object",
        "properties": {"key": {"type": "string", "enum": list(KEYS)}, "title": {"type": "string"},
                       "text": {"type": "string"}, "fact_ids": {"type": "array", "items": {"type": "string"}}},
        "required": ["key", "title", "text", "fact_ids"], "additionalProperties": False}}},
    "required": ["stories"], "additionalProperties": False,
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# --- Evidencia estructurada de MusicBrainz -------------------------------------------------------------------
def trajectory_doc(mbid: str, groups_raw: list[dict], total: int | None, releases_raw: list[dict],
                   joint_titles: dict[str, set[str]], names: dict[str, str]) -> SourceDoc | None:
    """Trayectoria con datos de MusicBrainz (CC0): primer lanzamiento propio (solo con la discografía completa) y su
    sello, sellos donde más ha publicado (sin implicar fundación) y artistas con varios lanzamientos conjuntos."""
    own = [g for g in groups_raw if g.get("first-release-date") and g.get("primary-type") in OWN_PRIMARY_TYPES
           and not EXCLUDED_SECONDARY & set(g.get("secondary-types") or [])  # sin DJ mixes ni recopilatorios
           and mbid in {(c.get("artist") or {}).get("id") for c in g.get("artist-credit") or []}]
    lines = []
    if own and total is not None and total <= len(groups_raw):
        first = min(own, key=lambda g: g["first-release-date"])
        label = _release_label(first, releases_raw)
        kind = {"Album": "álbum", "EP": "EP", "Single": "single"}.get(first.get("primary-type"), "lanzamiento")
        lines.append(f"Primer lanzamiento propio: «{first['title']}» ({kind}, {first['first-release-date'][:4]})"
                     + (f", publicado por el sello {label}." if label else "."))
    counts: dict[str, set[str]] = {}
    for r in releases_raw:
        if mbid not in {(c.get("artist") or {}).get("id") for c in r.get("artist-credit") or []}:
            continue
        for li in r.get("label-info") or []:
            name = ((li or {}).get("label") or {}).get("name")
            if name and not name.startswith("["):  # «[no label]»
                counts.setdefault(name, set()).add(base_title(r.get("title") or ""))
    top = sorted(counts.items(), key=lambda kv: (-len(kv[1]), kv[0]))[:3]
    if top and len(top[0][1]) >= 2:
        lines.append("Sellos con más lanzamientos suyos (no implica que los fundara): "
                     + ", ".join(name for name, titles in top if len(titles) >= 2) + ".")
    partners = sorted(((names.get(k, ""), len(v)) for k, v in joint_titles.items() if len(v) >= 2 and names.get(k)),
                      key=lambda x: -x[1])[:3]
    if partners:
        lines.append("Lanzamientos conjuntos con: " + ", ".join(n for n, _ in partners) + ".")
    if not lines:
        return None
    return SourceDoc("", TRAJECTORY_LABEL, f"https://musicbrainz.org/artist/{mbid}", "CC0", " ".join(lines))


def _release_label(group: dict, releases_raw: list[dict]) -> str | None:
    title, date = base_title(group.get("title") or ""), (group.get("first-release-date") or "")[:4]
    for r in releases_raw:
        if base_title(r.get("title") or "") == title and (r.get("date") or "")[:4] == date:
            names = [((li or {}).get("label") or {}).get("name") for li in r.get("label-info") or []]
            names = [n for n in names if n and not n.startswith("[")]
            if names:
                return names[0]
    return None


# --- Caché ---------------------------------------------------------------------------------------------------
def cached(mbid: str) -> schemas.StoriesResponse | None:
    raw = store.get(KIND, mbid)
    if not raw or raw.get("version") != VERSION:
        return None
    try:
        return schemas.StoriesResponse.model_validate(raw["response"])
    except Exception:  # registro antiguo o corrupto: se regenera
        return None


def _save(mbid: str, response: schemas.StoriesResponse, ttl: float) -> schemas.StoriesResponse:
    store.put(KIND, mbid, {"version": VERSION, "response": response.model_dump()}, ttl)
    return response


# --- Generación ----------------------------------------------------------------------------------------------
def _prompt(name: str, kind: str, chosen: list[facts.Fact], problems: list[str] | None = None) -> str:
    lines = "\n".join(f"[{f.id}] ({f.kind}; fuente: {f.source.label}) {f.text}" for f in chosen)
    retry = ("\n\nEn el intento anterior se descartaron historias por: " + "; ".join(problems)
             + ". Corrígelo usando solo lo que dicen los hechos.") if problems else ""
    return f"Artista: {name} ({kind})\n\nHECHOS:\n{lines}\n\nEscribe las historias.{retry}"


ROLE_WORDS_RE = re.compile(r"\b(producer|dj|artist|musician|electronic|techno|house|band|duo|rapper|singer|composer|"
                           r"label|remixer|producteur|productor)\b", re.IGNORECASE)


def civil_names(mb_artist: dict, name: str) -> list[str]:
    """Nombres civiles de un solista que MusicBrainz documenta (alias «Legal name» o la desambiguación «Nombre
    Apellido, …»): las historias no los usan. En dúos y grupos los nombres de sus integrantes sí son parte del hecho."""
    if mb_artist.get("type") == "Group":
        return []
    out = [a["name"] for a in mb_artist.get("aliases") or [] if a.get("type") == "Legal name" and a.get("name")]
    for seg in re.split(r"[,;/(]", mb_artist.get("disambiguation") or ""):
        seg = seg.strip()
        if (re.fullmatch(r"[A-ZÀ-Ý][\w'’-]+(\s+[A-ZÀ-Ý][\w'’.-]+){1,3}", seg) and not ROLE_WORDS_RE.search(seg)
                and seg.casefold() != name.casefold()):
            out.append(seg)
    return [n for n in dict.fromkeys(out) if n.casefold() != name.casefold()]


# Títulos de plantilla que no cuentan nada (vistos en las historias reales de V5) y textos que solo enumeran géneros.
GENERIC_TITLE_RE = re.compile(
    r"^(los )?primer(os)? (pasos|lanzamiento|single|sencillo|ep|álbum|album|remix)( propio| destacado)?( (en )?(19|20)\d{2})?$|"
    r"^(estilo|sonido|género)s?( musical(es)?)?$|^su propio universo$|^sellos?( y proyectos?| que publican)?$|"
    r"^colaboraciones?( y reconocimientos)?$|^sobre el escenario$|^trayectoria$", re.IGNORECASE)
GENRE_ONLY_RE = re.compile(r"\b(trabaja|se mueve|se centra|produce|pincha)\b.{0,40}\b(dentro del?|entre|en)\b.{0,40}"
                           r"\b(house|techno|electro|trance|ambient|minimal|disco)\b", re.IGNORECASE)


def _valid(out: dict, name: str, refs: dict[str, facts.Fact], avoid: list[str] = ()) -> tuple[list[schemas.Story], list[str]]:
    stories, problems, seen = [], [], set()
    for item in out.get("stories") or []:
        key, title, text = item.get("key"), " ".join(str(item.get("title") or "").split()), " ".join(str(item.get("text") or "").split())
        ids = [i for i in item.get("fact_ids") or [] if isinstance(i, str)]
        cited = [refs[i] for i in dict.fromkeys(ids) if i in refs]
        if key not in KEYS or key in seen or not cited or any(i not in refs for i in ids):
            problems.append(f"{key}: hechos citados no válidos")
            continue
        issue = biography.story_issue(title, text, name, facts.as_docs(cited))
        civil = next((n for n in avoid if n.casefold() in f"{title} {text}".casefold()), None)
        issue = issue or (f"usa el nombre civil ({civil})" if civil else None)
        if not issue and GENERIC_TITLE_RE.match(title.rstrip(".")):
            issue = f"título genérico («{title}»): nombra algo concreto del hecho"
        if not issue and (all(f.kind == "estilo" for f in cited) or GENRE_ONLY_RE.search(text) and len(text.split()) < 16):
            issue = "solo cuenta sus géneros o estilos (eso ya está en la ficha)"
        if issue:
            problems.append(f"{key}: {issue}")
            continue
        seen.add(key)
        sources = list({f.source.url: schemas.SourceRef(label=f.source.label, url=f.source.url, license=f.source.license)
                        for f in cited}.values())
        stories.append(schemas.Story(key=key, title=title.rstrip("."), text=text, sources=sources))
    stories.sort(key=lambda s: KEYS.index(s.key))
    return stories, problems


def generate(mbid: str, name: str, kind: str, collect: Callable[[], list[SourceDoc]],
             structured: Callable[[], list[schemas.Story]], groq: GroqClient, avoid: list[str] = ()) -> schemas.StoriesResponse:
    """Historias desde caché, generadas y validadas, o estructuradas. Nunca lanza."""
    hit = cached(mbid)
    if hit:
        return hit
    fallback = structured()
    docs = collect()
    # «Label run by Adrian Niculae»: MusicBrainz documenta que ese nombre civil es el del propio artista; en la
    # evidencia (y por tanto en la validación) pasa a ser el nombre artístico.
    for doc in docs:
        for civil in avoid:
            doc.text = re.sub(re.escape(civil), name, doc.text, flags=re.IGNORECASE)
    # Área asociada y país no cuentan nada de su trayectoria y el modelo tendía a deducir de ellos («raíces
    # parisinas», «se inspira en la cultura local»): fuera de la evidencia de las historias.
    found = [f for f in facts.extract(docs, name) if not re.match(r"(Área asociada|País)\b", f.text)]
    chosen = facts.select(found, limit=MAX_EVIDENCE)
    stories: list[schemas.Story] = []
    if groq.configured and not biography.in_cooldown() and facts.descriptive_count(chosen) + len(chosen) >= MIN_EVIDENCE:
        refs = {f.id: f for f in chosen}
        problems: list[str] | None = None
        for _attempt in range(2):  # una petición y, si no sale ninguna válida, un único reintento
            try:
                out = groq.structured(SYSTEM, _prompt(name, kind, chosen, problems), "artist_stories", SCHEMA)
            except GroqError as exc:
                if exc.code == "rate_limited":
                    biography.start_cooldown(exc.retry_after)
                break
            stories, problems = _valid(out, name, refs, avoid)
            if stories:
                break
    if stories:
        # Lo que las historias generadas no cubren lo completan las estructuradas (sin repetir tipo).
        keys = {s.key for s in stories}
        merged = sorted(stories + [s for s in fallback if s.key not in keys], key=lambda s: KEYS.index(s.key))
        mode = "generated" if all(s.key in keys for s in merged) else "mixed"
        return _save(mbid, schemas.StoriesResponse(artist_mbid=mbid, status="ready", mode=mode, stories=merged[:3],
                                                   generated_at=_now()), TTL_GENERATED_S)
    response = schemas.StoriesResponse(artist_mbid=mbid, status="ready" if fallback else "unavailable",
                                       mode="structured" if fallback else None, stories=fallback, generated_at=_now())
    return _save(mbid, response, TTL_STRUCTURED_S)


# --- Historias estructuradas (sin IA) --------------------------------------------------------------------------
def structured_stories(name: str, plural: bool, identity: schemas.Identity, mb_artist: dict, mbid: str,
                       trajectory: SourceDoc | None, sources: dict[str, schemas.SourceRef]) -> list[schemas.Story]:
    """Plantillas deterministas con datos estructurados y verificados. Frases sin marca de género y concordancia en
    plural para dúos y grupos. Solo las historias con contenido; nunca relleno."""
    v = (lambda one, many: many if plural else one)
    out = []
    first = re.search(r"Primer lanzamiento propio: «([^»]+)» \(([^,]+), (\d{4})\)(?:, publicado por el sello ([^.]+))?",
                      trajectory.text) if trajectory else None
    if first:
        title, kind, year, label = first.groups()
        text = (f"Su primer lanzamiento propio conocido es «{title}», un {kind} de {year}"
                + (f" que salió en el sello {label}." if label else "."))
        partners = re.search(r"Lanzamientos conjuntos con: ([^.]+)\.", trajectory.text)
        if partners:
            text += f" Desde entonces {v('ha', 'han')} firmado varios trabajos junto a {_join(partners.group(1).split(', '))}."
        out.append(schemas.Story(key="inicios", title=f"Todo empezó con «{title}»" if len(title) <= 28 else f"El arranque, en {year}",
                                 text=text, sources=[sources["musicbrainz"]]))
    parts, refs = [], []
    founded = identity.founded_labels
    if founded:
        years = identity.label_years
        labels = _join([f"{l} ({years[l]})" if l in years else l for l in founded])
        parts.append(f"{v('Fundó', 'Fundaron')} {'el sello' if len(founded) == 1 else 'los sellos'} {labels}.")
    if identity.run_labels:
        parts.append(f"{v('Está', 'Están')} al frente {'del sello' if len(identity.run_labels) == 1 else 'de los sellos'} "
                     f"{_join(identity.run_labels)}.")
    if identity.members:
        parts.append(f"El proyecto lo forman {_join(identity.members)}.")
    elif identity.projects:
        parts.append(f"También forma parte de {_join(identity.projects)}.")
    if parts:
        refs = [sources["musicbrainz"]] + ([sources["discogs"]] if "discogs" in sources else [])
        own_labels = founded or identity.run_labels
        heading = (f"El universo {own_labels[0]}" if own_labels else
                   "Quiénes están detrás" if identity.members else f"Más allá de {name}")
        out.append(schemas.Story(key="universo", title=heading, text=" ".join(parts), sources=refs))
    # Ediciones de festivales y eventos con año; sin etiquetas («#VEGASRAVE») ni eventos con su propio nombre.
    events = [_event(rel) for rel in mb_artist.get("relations") or []
              if rel.get("target-type") == "event" and rel.get("type") == "main performer"
              and not re.search(r"\bb2b\b|back ?to ?back", ((rel.get("event") or {}).get("name") or ""), re.IGNORECASE)]
    # Con año y con nombre: «1987‐12‐13» (un evento sin nombre, solo la fecha) no es un festival que contar.
    events = [e for e in dict.fromkeys(events) if re.search(r"\b(19|20)\d{2}\b", e) and not e.startswith("#")
              and re.search(r"[^\W\d_]{3}", e) and name.casefold() not in e.casefold()][:3]
    if len(events) >= 2:
        festival = re.sub(r"\s*(19|20)\d{2}$", "", events[0])
        out.append(schemas.Story(key="momento", title=f"En el cartel de {festival}",
                                 text=f"Su nombre figura entre los artistas de {_join(events)}.", sources=[sources["musicbrainz"]]))
    return out


def _event(rel: dict) -> str:
    return re.split(r",\s|:\s|\s[-–]\s", ((rel.get("event") or {}).get("name") or ""), maxsplit=1)[0].strip()


def _join(items: list[str]) -> str:
    items = [i for i in items if i]
    return items[0] if len(items) == 1 else f"{', '.join(items[:-1])} y {items[-1]}" if items else ""
