"""Fuentes para biografías: datos verificados y recopilados ANTES de llamar al modelo.

- MusicBrainz (CC0): identidad, origen, lanzamientos propios recientes, sellos y colaboradores.
- Wikidata (CC0): ocupaciones y géneros del ítem verificado por MBID.
- MusicBrainz, relaciones (CC0): sellos fundados («label founder»), alias, proyectos conjuntos y eventos en los que
  actuó (incluidos B2B documentados como evento). Relaciones explícitas, no deducidas.
- Wikipedia (CC BY-SA): artículos en español e inglés enlazados desde ese ítem (se usan como dato, no se copian).
- Web oficial: solo la URL «official homepage» que MusicBrainz documenta para ese MBID; una página, respetando
  robots.txt, con un extracto acotado (meta descripción y primeros párrafos). Nunca búsquedas ni rastreo.
Cada fuente lleva un id (S1, S2…): el modelo solo puede citar esos ids, así no puede inventar URLs.
"""

from __future__ import annotations

import ipaddress
import re
import socket
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser
from dataclasses import dataclass
from html.parser import HTMLParser

from app import schemas
from app.musicbrainz import ProviderError, WikimediaClient
from app.wikidata import WikidataInfo

MAX_SOURCE_CHARS = 1800
DESCRIPTIVE_MIN_CHARS = 150  # texto descriptivo mínimo (Wikipedia, web oficial o notas de Discogs) para llamar al modelo
MAX_TOTAL_CHARS = 6000
# Biografías de artista: al modelo solo llegan los hechos seleccionados (facts.py), así que las fuentes se recopilan
# completas. El recorte a 1800 caracteres dejaba fuera lo que cuenta la segunda mitad del artículo (Metamorfosi,
# Redimension e Ibiza en Joseph Capriati; Zenit y Question en Marco Carola).
MAX_ARTICLE_CHARS = 12000
BIO_MAX_TOTAL_CHARS = 40000
MAX_EVENTS = 4
WIKI_EXTEND_BELOW = 900  # introducción corta: se usa el comienzo del artículo (TextExtracts devuelve ~1200 car.)
SECTION_RE = re.compile(r"^(={2,})\s*(.+?)\s*=+$")
NON_NARRATIVE_RE = re.compile(
    r"discograf|discography|filmograf|filmography|videograf|referencias|references|notas|notes|citas|enlaces|links|"
    r"v[eé]ase|see also|bibliograf|further reading|lecturas|track ?list|listado de canciones|fuentes|sources|"
    # Otros idiomas (artículo de respaldo, ver OTHER_WIKIS): de, fr, nl, it, pt.
    r"diskografie|discografie|discographie|einzelnachweise|weblinks|literatur|siehe auch|externe links|"
    r"referenties|bronnen|zie ook|liens externes|voir aussi|r[eé]f[eé]rences|collegamenti|voci correlate|"
    r"refer[eê]ncias|liga[cç][oõ]es externas|ver tamb[eé]m",
    re.IGNORECASE)
OFFICIAL_TIMEOUT_S = 6.0
OFFICIAL_MAX_BYTES = 400_000


@dataclass
class SourceDoc:
    id: str
    label: str
    url: str
    license: str | None
    text: str

    def ref(self) -> schemas.SourceRef:
        return schemas.SourceRef(label=self.label, url=self.url, license=self.license)


class _TextExtractor(HTMLParser):
    """Meta descripciones y texto de <p>/<h1>/<h2> visibles (sin scripts ni estilos)."""

    def __init__(self):
        super().__init__()
        self.meta: list[str] = []
        self.paragraphs: list[str] = []
        self.jsonld: list[str] = []
        self._stack: list[str] = []
        self._buffer: list[str] = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "meta" and (a.get("name") or a.get("property") or "").lower() in ("description", "og:description"):
            if a.get("content"):
                self.meta.append(a["content"])
        if tag == "script" and (a.get("type") or "").lower() == "application/ld+json":
            self._stack.append("jsonld")
            self._buffer = []
            return
        if tag in ("p", "h1", "h2", "script", "style", "noscript"):
            self._stack.append(tag)
            self._buffer = []

    def handle_endtag(self, tag):
        if tag == "script" and self._stack and self._stack[-1] == "jsonld":
            self._stack.pop()
            self.jsonld.append("".join(self._buffer))
            return
        if self._stack and self._stack[-1] == tag:
            self._stack.pop()
            if tag in ("p", "h1", "h2"):
                text = " ".join("".join(self._buffer).split())
                if len(text) > 40:
                    self.paragraphs.append(text)

    def handle_data(self, data):
        if self._stack and self._stack[-1] in ("p", "h1", "h2", "jsonld"):
            self._buffer.append(data)


def _jsonld_descriptions(blocks: list[str]) -> list[str]:
    """Campos «description» de datos estructurados (schema.org) de tipo persona, grupo o artista musical."""
    import json
    out = []
    for block in blocks:
        try:
            data = json.loads(block)
        except ValueError:
            continue
        items = data if isinstance(data, list) else data.get("@graph", [data]) if isinstance(data, dict) else []
        for item in items:
            if not isinstance(item, dict):
                continue
            kind = item.get("@type")
            kinds = kind if isinstance(kind, list) else [kind]
            if any(k in ("Person", "MusicGroup", "PerformingGroup", "Organization", "WebSite", "WebPage") for k in kinds):
                desc = item.get("description")
                if isinstance(desc, str) and len(desc) > 40:
                    out.append(desc)
    return out


def _clip(text: str, limit: int = MAX_SOURCE_CHARS) -> str:
    """Recorta al final de la última frase completa que quepa (si no queda muy corto); si no, por palabras."""
    text = " ".join(text.split())
    if len(text) <= limit:
        return text
    ends = [m.end() for m in re.finditer(r"[.!?](?=\s)", text[:limit + 1])]
    if ends and ends[-1] >= limit * 0.6:
        return text[:ends[-1]]
    return text[:limit].rsplit(" ", 1)[0] + "…"


def _public_url(url: str) -> bool:
    """http(s) hacia un host cuyas direcciones son todas públicas. La URL viene de datos editables por cualquiera
    (MusicBrainz/Wikidata): sin esto, el backend podría leer servicios de la red local o de la propia máquina (SSRF)."""
    parts = urllib.parse.urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        return False
    try:
        infos = socket.getaddrinfo(parts.hostname, parts.port or (443 if parts.scheme == "https" else 80),
                                   proto=socket.IPPROTO_TCP)
    except (socket.gaierror, UnicodeError, ValueError, OSError):
        return False
    addresses = [ipaddress.ip_address(str(info[4][0]).split("%", 1)[0]) for info in infos]
    return bool(addresses) and all(
        (a.ipv4_mapped or a).is_global if isinstance(a, ipaddress.IPv6Address) else a.is_global for a in addresses)


class _PublicRedirects(urllib.request.HTTPRedirectHandler):
    """Cada redirección se valida igual que la URL inicial."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not _public_url(newurl):
            raise urllib.error.URLError("redirección a un destino no público")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


_official_opener = urllib.request.build_opener(_PublicRedirects)


def official_site_text(url: str, user_agent: str) -> str | None:
    """Extracto de la web oficial si robots.txt lo permite. None ante cualquier problema (nunca bloquea)."""
    parts = urllib.parse.urlsplit(url)
    if not _public_url(url):
        return None
    robots = urllib.robotparser.RobotFileParser(f"{parts.scheme}://{parts.netloc}/robots.txt")
    try:
        robots_req = urllib.request.Request(robots.url, headers={"User-Agent": user_agent})
        with _official_opener.open(robots_req, timeout=OFFICIAL_TIMEOUT_S) as r:
            robots.parse(r.read(50_000).decode("utf-8", "replace").splitlines())
    except urllib.error.HTTPError as exc:
        if exc.code in (401, 403):
            return None  # robots.txt restringido: se respeta como «no permitido»
        robots.parse([])  # sin robots.txt: permitido
    except (urllib.error.URLError, TimeoutError, OSError, ValueError):
        return None
    if not robots.can_fetch(user_agent, url):
        return None
    try:
        req = urllib.request.Request(url, headers={"User-Agent": user_agent, "Accept": "text/html"})
        with _official_opener.open(req, timeout=OFFICIAL_TIMEOUT_S) as r:
            if "html" not in (r.headers.get("Content-Type") or ""):
                return None
            html = r.read(OFFICIAL_MAX_BYTES).decode("utf-8", "replace")
    except (urllib.error.URLError, TimeoutError, OSError, ValueError):
        return None
    parser = _TextExtractor()
    try:
        parser.feed(html)
    except Exception:  # HTML imposible de analizar: se ignora la fuente
        return None
    text = " ".join(dict.fromkeys(_jsonld_descriptions(parser.jsonld) + parser.meta + parser.paragraphs[:6]))
    return _clip(text) if len(text) >= 80 else None


def _wiki_extract(wiki: WikimediaClient, lang: str, title: str, intro: bool, full: bool = False) -> str:
    params = {"action": "query", "prop": "extracts", "explaintext": "1", "redirects": "1", "titles": title,
              "format": "json"}
    if full:  # artículo completo con marcas «== Sección ==» para descartar las secciones no narrativas
        params["exsectionformat"] = "wiki"
    else:
        params.update({"exintro": "1"} if intro else {"exchars": "1200", "exsectionformat": "plain"})
    data = wiki.get(f"https://{lang}.wikipedia.org/w/api.php", params).data
    pages = (data.get("query") or {}).get("pages") or {}
    extract = next((p.get("extract") for p in pages.values() if isinstance(p, dict) and p.get("extract")), "") \
        if isinstance(pages, dict) else ""
    return extract if isinstance(extract, str) else ""


def _narrative(extract: str) -> str:
    """Introducción y secciones narrativas, sin títulos de sección ni discografías, referencias o enlaces (con sus
    subsecciones): esas listas desplazaban del recorte la trayectoria, las residencias o los premios."""
    out, skip_level = [], 0
    for line in extract.replace("​", "").splitlines():
        heading = SECTION_RE.match(line.strip())
        if heading:
            level = len(heading.group(1))
            if skip_level and level > skip_level:
                continue
            skip_level = level if NON_NARRATIVE_RE.search(heading.group(2)) else 0
        elif not skip_level and line.strip():
            out.append(line.strip())
    return "\n".join(out)


def wikipedia_summary(wiki: WikimediaClient, wd: WikidataInfo, full_article: bool = False) -> SourceDoc | None:
    """Introducción del artículo (API oficial TextExtracts, texto plano). Español primero. Si la introducción es
    corta (p. ej. Bicep: una frase), el comienzo del artículo, donde suelen estar inicios, sellos e hitos.
    Con `full_article` (biografías de artista), el texto narrativo del artículo completo en una sola petición."""
    for site, lang in (("eswiki", "es"), ("enwiki", "en")):
        title = wd.wikipedia.get(site)
        if not title:
            continue
        try:
            if full_article:
                extract = _narrative(_wiki_extract(wiki, lang, title, intro=False, full=True))
            else:
                extract = _wiki_extract(wiki, lang, title, intro=True)
            if not full_article and len(extract) < WIKI_EXTEND_BELOW:
                longer = _wiki_extract(wiki, lang, title, intro=False)
                extract = longer if len(longer) > len(extract) else extract
        except ProviderError:
            continue
        extract = re.sub(r"\n{2,}", "\n", extract).strip()
        page = f"https://{lang}.wikipedia.org/wiki/{urllib.parse.quote(title.replace(' ', '_'))}"
        if isinstance(extract, str) and len(extract) >= 80:
            return SourceDoc("", f"Wikipedia ({lang}): {title}", page, "CC BY-SA 4.0", _clip(extract))
    return None


def wikipedia_lead(wiki: WikimediaClient, wd: WikidataInfo) -> tuple[str, SourceDoc] | None:
    """(idioma, introducción) tal cual, con sus párrafos: es la misma petición que hace `wikipedia_summary` (en
    caché), sin el recorte del comienzo del artículo, cuyos títulos de sección se pegarían a las frases."""
    for site, lang in (("eswiki", "es"), ("enwiki", "en")):
        title = wd.wikipedia.get(site)
        if not title:
            continue
        try:
            extract = _wiki_extract(wiki, lang, title, intro=True)
        except ProviderError:
            continue
        paragraphs = [" ".join(p.split()) for p in extract.replace("​", "").splitlines() if p.strip()]
        text = "\n".join(paragraphs)[:MAX_SOURCE_CHARS]
        page = f"https://{lang}.wikipedia.org/wiki/{urllib.parse.quote(title.replace(' ', '_'))}"
        if len(text) >= 80:
            return lang, SourceDoc("", f"Wikipedia ({lang})", page, "CC BY-SA 4.0", text)
    return None


def wikipedia_articles(wiki: WikimediaClient, wd: WikidataInfo) -> list[SourceDoc]:
    """Texto narrativo de los artículos en español Y en inglés (si existen): a menudo uno tiene lo que falta en el
    otro (Marco Carola: el español no menciona Music On ni Amnesia; el inglés, sí). Una petición por idioma."""
    out = []
    for site, lang in (("eswiki", "es"), ("enwiki", "en")):
        title = wd.wikipedia.get(site)
        if not title:
            continue
        try:
            extract = _narrative(_wiki_extract(wiki, lang, title, intro=False, full=True))
        except ProviderError:
            continue
        extract = re.sub(r"\n{2,}", "\n", extract).strip()
        if len(extract) >= 80:
            page = f"https://{lang}.wikipedia.org/wiki/{urllib.parse.quote(title.replace(' ', '_'))}"
            out.append(SourceDoc("", f"Wikipedia ({lang}): {title}", page, "CC BY-SA 4.0",
                                 _clip(extract, MAX_ARTICLE_CHARS)))
    return out or [doc for doc in [other_language_article(wiki, wd)] if doc]


def other_language_article(wiki: WikimediaClient, wd: WikidataInfo) -> SourceDoc | None:
    """Sin artículo en español ni en inglés: el primero disponible en otro idioma (OTHER_WIKIS), por el sitelink del
    ítem verificado. Se comprueba además que la página enlaza al mismo ítem (`wikibase_item`) y que no es una
    desambiguación. Un único artículo: no se suman versiones del mismo texto en varios idiomas."""
    for site, title in wd.other_wikipedia.items():
        lang = site.removesuffix("wiki")
        try:
            data = wiki.get(f"https://{lang}.wikipedia.org/w/api.php", {
                "action": "query", "prop": "extracts|pageprops", "explaintext": "1", "exsectionformat": "wiki",
                "ppprop": "wikibase_item|disambiguation", "redirects": "1", "titles": title, "format": "json"}).data
        except ProviderError:
            continue
        pages = (data.get("query") or {}).get("pages") or {}
        page = next((p for p in pages.values() if isinstance(p, dict)), {}) if isinstance(pages, dict) else {}
        props = page.get("pageprops") or {}
        if props.get("wikibase_item") != wd.qid or "disambiguation" in props:
            continue  # otro ítem (homónimo, redirección a otra página) o página de desambiguación
        extract = re.sub(r"\n{2,}", "\n", _narrative(page.get("extract") or "")).strip()
        if len(extract) >= 80:
            url = f"https://{lang}.wikipedia.org/wiki/{urllib.parse.quote(title.replace(' ', '_'))}"
            return SourceDoc("", f"Wikipedia ({lang}): {title}", url, "CC BY-SA 4.0", _clip(extract, MAX_ARTICLE_CHARS))
    return None


# Relaciones artista → sello de MusicBrainz que significan fundación (no basta con publicar en él).
FOUNDER_LABEL_RELATIONS = {"label founder"}
B2B_RE = re.compile(r"\bb2b\b|\bback ?to ?back\b", re.IGNORECASE)


def _event_name(name: str) -> str:
    """«Glastonbury Festival 2019, Friday: Arcadia’s Pangea» → «Glastonbury Festival 2019» (sin escenario ni día)."""
    return re.split(r",\s|:\s|\s[-–]\s", name, 1)[0].strip()


def founded_labels(mb_artist: dict) -> list[tuple[str, str | None]]:
    """(sello, año de inicio) de las relaciones «label founder» de MusicBrainz para ese artista."""
    out = []
    for rel in mb_artist.get("relations") or []:
        name = (rel.get("label") or {}).get("name")
        if rel.get("target-type") == "label" and rel.get("type") in FOUNDER_LABEL_RELATIONS and name:
            out.append((name, (rel.get("begin") or "")[:4] or None))
    return list(dict.fromkeys(out))


def musicbrainz_relations(mb_artist: dict, name: str) -> SourceDoc | None:
    """Relaciones explícitas de MusicBrainz (CC0) que no aparecen en la ficha básica: sellos fundados, alias,
    proyectos conjuntos, B2B (eventos «X b2b Y») y eventos en los que actuó como intérprete principal."""
    lines = []
    for label, year in founded_labels(mb_artist):
        lines.append(f"Sello fundado por el artista: {label}" + (f" (desde {year})" if year else "") + ".")
    aliases, joint, b2b, events = [], [], [], []
    for rel in mb_artist.get("relations") or []:
        kind, target = rel.get("type"), rel.get("target-type")
        other = (rel.get(target) or {}).get("name") if target in ("artist", "event") else None
        if not other:
            continue
        if target == "artist" and kind == "is person" and rel.get("direction") != "backward":
            aliases.append(other)
        elif target == "artist" and kind == "collaboration" and rel.get("direction") != "backward":
            joint.append(other)
        elif target == "event" and kind == "main performer":
            (b2b if B2B_RE.search(other) else events).append(other if B2B_RE.search(other) else _event_name(other))
    if aliases:
        lines.append("Otros alias del mismo artista: " + ", ".join(dict.fromkeys(aliases[:4])) + ".")
    if joint:
        lines.append("Proyecto conjunto: " + ", ".join(dict.fromkeys(joint[:3])) + ".")
    for event in list(dict.fromkeys(b2b))[:2]:
        lines.append(f"B2B documentado: {event}.")
    if events:
        lines.append("Actuaciones documentadas en eventos (no implica cabeza de cartel ni residencia): "
                     + ", ".join(list(dict.fromkeys(events))[:MAX_EVENTS]) + ".")
    if not lines:
        return None
    mbid = mb_artist.get("id") or ""
    return SourceDoc("", "MusicBrainz (relaciones)", f"https://musicbrainz.org/artist/{mbid}/relationships", "CC0",
                     " ".join(lines))


def musicbrainz_facts(artist: schemas.Artist, recent: list[schemas.RecentRelease], labels: list[str],
                      collaborators: list[str], identity: schemas.Identity | None = None,
                      members: list[str] | None = None, groups: list[str] | None = None) -> SourceDoc:
    """Hechos de MusicBrainz con su significado exacto (para no confundir publicar con fundar, ni área con
    residencia o nacimiento)."""
    identity = identity or schemas.Identity()
    lines = [f"Nombre artístico: {artist.name}."]
    if artist.disambiguation:
        lines.append(f"Descripción breve: {artist.disambiguation}.")
    if artist.type:
        lines.append(f"Tipo: {'persona' if artist.type == 'Person' else 'grupo' if artist.type == 'Group' else artist.type}.")
    if identity.country_name or artist.country:
        lines.append(f"País: {identity.country_name or artist.country}.")
    if identity.area:
        lines.append(f"Área asociada (no indica residencia ni nacimiento): {identity.area}.")
    if identity.origin:
        lines.append(f"Lugar de {'nacimiento' if identity.origin_kind == 'birth' else 'formación'}: {identity.origin}.")
    if identity.formed_year:
        lines.append(f"Año de formación: {identity.formed_year}.")
    if members:
        lines.append("Integrantes: " + ", ".join(members[:6]) + ".")
    if groups:
        lines.append("Miembro de: " + ", ".join(groups[:3]) + ".")
    if labels:
        lines.append("Sellos que han publicado su música (no implica que los haya fundado): " + ", ".join(labels[:4]) + ".")
    if collaborators:
        lines.append("Colaboradores habituales: " + ", ".join(collaborators[:3]) + ".")
    if recent:  # contexto secundario: el modelo no debe enumerarlo
        lines.append("Contexto secundario (no enumerar): algunos lanzamientos recientes son "
                     + "; ".join(f"«{r.title}» ({r.first_release_date[:4]})" for r in recent[:3]) + ".")
    return SourceDoc("", "MusicBrainz", artist.source.url, "CC0", _clip(" ".join(lines)))


def wikidata_facts(wd: WikidataInfo, labels: dict[str, str]) -> SourceDoc | None:
    def named(ids, n):
        return [labels[q] for q in ids[:n] if q in labels]
    occupations, genres = named(wd.occupation_ids, 3), named(wd.genre_ids, 3)
    rec_labels, countries = named(wd.label_ids, 3), named(wd.country_ids, 2)
    groups, awards, members = named(wd.member_of_ids, 2), named(wd.award_ids, 3), named(wd.has_part_ids, 6)
    description = wd.descriptions.get("es") or wd.descriptions.get("en")
    if not wd.qid or not (description or occupations or genres or rec_labels or countries or groups or awards
                          or members):
        return None
    parts = [f"Descripción breve: {description}."] if description else []
    for title, values in (("Ocupaciones", occupations), ("Géneros", genres),
                          ("Sellos discográficos con los que ha trabajado (no implica fundación)", rec_labels),
                          ("País", countries), ("Integrantes", members), ("Miembro o parte de", groups),
                          ("Premios", awards)):
        if values:
            parts.append(f"{title}: {', '.join(values)}.")
    if wd.active_since:
        parts.append(f"Activo desde: {wd.active_since}.")
    return SourceDoc("", f"Wikidata {wd.qid}", f"https://www.wikidata.org/wiki/{wd.qid}", "CC0", " ".join(parts))


def number(docs: list[SourceDoc | None], max_total: int = MAX_TOTAL_CHARS) -> list[SourceDoc]:
    """Asigna ids S1… y recorta el total para limitar lo que se envía al modelo."""
    out, total = [], 0
    for doc in (d for d in docs if d and d.text):
        if total + len(doc.text) > max_total:
            doc.text = _clip(doc.text, max(200, max_total - total))
        doc.id = f"S{len(out) + 1}"
        out.append(doc)
        total += len(doc.text)
        if total >= max_total:
            break
    return out


def descriptive_chars(docs: list[SourceDoc]) -> int:
    """Caracteres de texto realmente descriptivo (Wikipedia, web oficial o notas de Discogs), no discografía ni
    metadatos."""
    return sum(len(d.text) for d in docs if d.label.startswith(("Wikipedia", "Web oficial", "Discogs (perfil)")))


def sufficient(docs: list[SourceDoc]) -> bool:
    """Solo se genera con IA si hay texto descriptivo suficiente. Con discografía y metadatos no basta: el modelo
    acabaría enumerando lanzamientos (causa de los textos deficientes diagnosticada en T1.4)."""
    return descriptive_chars(docs) >= DESCRIPTIVE_MIN_CHARS


YEAR_RE = re.compile(r"\b(19|20)\d{2}\b")
QUOTED_RE = re.compile(r"«([^»]+)»|\"([^\"]+)\"")
