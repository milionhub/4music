"""Expediente de hechos verificables para las biografías (T1.4 v8): se extraen de las fuentes ya recopiladas y se
seleccionan ANTES de llamar al modelo, que solo redacta a partir de ellos.

- MusicBrainz y Wikidata: un hecho por campo («Lugar de nacimiento: Barcelona»), con el significado exacto que ya
  declaran las fuentes (publicar en un sello no es fundarlo; el área asociada no es residencia ni nacimiento).
- MusicBrainz (relaciones): sellos fundados («label founder»), alias, proyectos conjuntos, B2B y eventos.
- Wikipedia y web oficial: una frase por hecho, clasificada por la relación que afirma (sello, fiesta propia,
  residencia, proyecto paralelo…). La clasificación orienta la selección y al modelo; la verificación posterior sigue
  exigiendo que cada afirmación y cada nombre estén en los hechos enviados.

El expediente (`extract`) guarda más de lo que se usa; `select` elige por relevancia editorial: primero lo que
distingue al artista (sellos, fiestas, proyectos, sonido), sin hechos redundantes ni cuotas iguales para todos.
Sin llamadas externas: todo sale de los SourceDoc que ya recopila la API.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

from app.sources import YEAR_RE, SourceDoc

MAX_FACTS = 9
MIN_CORE_SCORE = 3.5  # relevancia mínima para ocupar el cupo de su tipo en la primera pasada
OWN_KINDS = ("sello propio", "sello que dirige", "fiesta propia", "proyecto propio")
GENERIC_GENRES = {"musica electronica", "electronic music", "electronica", "musica dance", "dance music"}
MIN_SENTENCE_CHARS, MAX_SENTENCE_CHARS = 25, 420
# Las notas del perfil de Discogs (CC0) son texto descriptivo; sus integrantes y grupos, campos estructurados.
DESCRIPTIVE = ("Wikipedia", "Web oficial", "Discogs (perfil)", "Discogs (sello)")
STRUCTURED = ("MusicBrainz", "Wikidata", "Discogs (relaciones)")
# Orden editorial del expediente: quién es y cómo suena, de dónde viene y cómo empezó, lo que ha construido (sellos,
# fiestas, proyectos), sus conexiones y su escena, y por último hitos y lanzamientos.
PRIORITY = ("identidad", "estilo", "origen", "inicios", "sello propio", "sello que dirige", "fiesta propia",
            "proyecto propio", "residencia", "proyecto paralelo", "alias", "colaboración", "escena", "hito",
            "festival", "música destacada", "otro", "publica en")
# Orden de la primera pasada (cupo de cada tipo): identidad y sonido, trayectoria, lo que ha construido (fiestas,
# proyectos, residencias, sellos), conexiones e hitos; los datos secundarios (escena genérica, origen, alias) solo
# si queda sitio, para que no desplacen proyectos importantes. El texto se presenta después en orden de PRIORITY.
SELECTION_ORDER = ("identidad", "estilo", "inicios", "fiesta propia", "proyecto propio", "residencia", "sello propio",
                   "sello que dirige", "proyecto paralelo", "colaboración", "hito", "música destacada", "escena",
                   "origen", "alias", "festival", "otro", "publica en")
# Origen, escena genérica, eventos y alias no tienen plaza reservada: solo entran si queda sitio y lo merecen.
QUOTA = {"identidad": 1, "estilo": 1, "origen": 0, "inicios": 1, "sello propio": 2, "sello que dirige": 0,
         "fiesta propia": 1, "proyecto propio": 1, "residencia": 1, "proyecto paralelo": 1, "alias": 0,
         "colaboración": 1, "escena": 0, "hito": 1, "festival": 0, "música destacada": 1, "otro": 0, "publica en": 0}
# Campos estructurados de relleno (colaboradores frecuentes calculados, «Activo desde», país, eventos): nunca ocupan
# una plaza reservada. Las relaciones explícitas de MusicBrainz (B2B, sello fundado, miembro de) sí pueden.
FILLER_FIELDS = ("colaboración", "inicios", "origen", "festival", "publica en")
WEAK_KINDS = ("otro", "publica en", "festival")  # solo si apenas hay nada más
MIN_FILL_SCORE = 2.0  # por debajo, el hecho no aporta lo suficiente ni para completar
# Máximo total por tipo: un solo dato de origen (lugar o fecha, no ambos) y nada de listas de lanzamientos.
PER_KIND = {"identidad": 2, "estilo": 2, "origen": 1, "inicios": 2, "sello propio": 3, "sello que dirige": 1,
            "fiesta propia": 2, "alias": 1, "colaboración": 2, "escena": 2, "hito": 2, "festival": 1,
            "música destacada": 1, "otro": 1, "publica en": 1}
# Campos de MusicBrainz y Wikidata (tal como los escribe sources.py) → tipo de hecho. None: no es un hecho útil.
FIELDS = {
    "nombre artistico": None, "tipo": None, "descripcion breve": "identidad", "ocupaciones": "identidad",
    "integrantes": "identidad", "miembro de": "proyecto paralelo", "miembro o parte de": "proyecto paralelo",
    "lugar de nacimiento": "origen", "lugar de formacion": "origen", "ano de formacion": "origen", "pais": "origen",
    "area asociada (no indica residencia ni nacimiento)": "origen", "activo desde": "inicios",
    "generos": "estilo", "premios": "hito", "colaboradores habituales": "colaboración",
    "sellos que han publicado su musica (no implica que los haya fundado)": "publica en",
    "sellos discograficos con los que ha trabajado (no implica fundacion)": "publica en",
    "contexto secundario (no enumerar)": None,  # lanzamientos recientes: ya tienen su sección en la ficha
    # MusicBrainz (relaciones)
    "sello fundado por el artista": "sello propio", "otros alias del mismo artista": "alias",
    "proyecto conjunto": "proyecto paralelo", "b2b documentado": "colaboración",
    "actuaciones documentadas en eventos (no implica cabeza de cartel ni residencia)": "festival",
    # MusicBrainz (trayectoria), para «Más allá de la cabina» (stories.py)
    "primer lanzamiento propio": "inicios",
    "sellos con mas lanzamientos suyos (no implica que los fundara)": "publica en",
    "lanzamientos conjuntos con": "colaboración",
}
# Residencias en clubes o fiestas (no «Resident Advisor», la revista).
RESIDENCY_RX = (r"\bresiden(cy|cies|cia|cias)\b|\b(dj )?resident(e|es)? (at|in|of|en|de|del)\b|\bresident dj\b|"
                r"\bdj resident\b")
# Lo que se ha fundado, creado o dirigido; después se distingue si es un sello, una fiesta u otro proyecto.
OWN_PROJECT_RX = (r"\b(co-?)?found(ed|er|ers|ing)?\b|\b(owner|propietari[oa]) (of|de)( the| el)?( record)? "
                  r"(label|imprint|sello)|\b(established|set up|created|launched|started|began) (a|an|the|"
                  r"his|her|their)( own)? [\w&' ]{0,30}(label|imprint|party|parties|club|collective|festival|event|"
                  r"series|blog|platform|brand|shop|show|podcast)|\blaunched (the|his|her|their)\b|\bown (record )?label|"
                  r"\bown [\w ]{0,20}(party|night)|\bhost(s|ed)? (his|her|their) own|\b(co)?fund(o|aron|ador|adora|"
                  r"adores)\b|\bcre(o|aron) su|\bsus? propi[oa]s? (sello|fiesta|festival|evento)|"
                  r"\bhead of the (record )?label|\bdirige|\b(runs|ran|curates?|curated) (the |his |her |their )?"
                  r"[\w&' ]{0,30}(label|imprint|party|parties|night|series)|\b(launched|founded|created|established|"
                  r"started) (in \d{4} )?by\b|\bhost(s|ed)? (the|a) series of\b|\bheld (his|her|their) [\w ]{0,25}"
                  r"part(y|ies)\b")
# Dirigir no es fundar: «head of the label», «dirige», «runs» sin un verbo de creación → «sello que dirige».
# Con las raíces de otros idiomas (de/nl/fr/it/pt) de los artículos de respaldo: «leitet/betreibt» es dirigir;
# «gründete», «opgericht», «fondé», «fondato», «fundou», «eigenes Label» es fundar o crear.
FOREIGN_DIRECTS = r"|\b(leitet|leiten|betreibt|betreiben|runt|runnen)\b"
FOREIGN_FOUNDS = (r"|\bgr[uü]nde(te|ten|t)\b|\bgegr[uü]ndet\b|\bopgericht\b|\boprichters?\b|\bfonde(e|es|rent)?\b|"
                  r"\bfondat(eur|rice|ore|o|a)\b|\bfundou\b")
DIRECTS_RX = re.compile(r"\bdirige\b|\bhead of the (record )?label|\b(runs|ran|curates?|curated)\b|\bowner of\b|"
                        r"\bpropietari[oa] de\b" + FOREIGN_DIRECTS, re.IGNORECASE)
CREATES_RX = re.compile(r"\b(co-?)?found|\bestablish|\bset up\b|\bcreat(e|ed|es|ing)\b|\blaunch|\bstart|\bbegan\b|\bown\b|\bhost|"
                        r"\bheld\b|\b(co)?fund(o|aron|ador)|\bcre(o|aron|ar)\b|\bsus? propi[oa]s?\b|\beigene?[nms]?\b"
                        + FOREIGN_FOUNDS, re.IGNORECASE)
FOUNDING_RX = re.compile(r"\b(co-?)?found(ed|er|ing)?\b|\bestablish|\bset up\b|\bcreat(e|ed|es|ing)\b|\blaunch|"
                         r"\b(co)?fund(o|aron|ador|adora)\b|\bcre(o|aron|ar)\b|\bpuso en marcha\b" + FOREIGN_FOUNDS,
                         re.IGNORECASE)
# Géneros nombrados en una frase: sin otra clasificación, la frase habla de su sonido o de su evolución.
GENRE_RX = re.compile(r"\b(techno|tech[- ]house|deep house|house|minimal|minimalista|electro|trance|ambient|acid|"
                      r"breakbeat|drum and bass|dubstep|disco|garage|jungle|italo[- ]house|hardcore|progressive)\b",
                      re.IGNORECASE)
# Un género solo hace de una frase un hecho de sonido si la frase habla de cómo suena («specialises in house»,
# «exponente del tech house», «known for…») o de su evolución musical («ritmos», «transición», «moved from house
# to techno»). Nombrarlo de pasada («cuando la escena del House italiana…», «varios temas House») no basta.
SOUND_CUE_RX = re.compile(r"\bspeciali[sz]|\bespecializ|\bknown for\b|\bconocid[oa]s? por\b|\bexponent|"
                          r"\bgustos musicales\b|\bsound\b|\bsonidos?\b|\bstyle\b|\bestilo\b|\bgenres?\b|\bgeneros?\b",
                          re.IGNORECASE)
EVOLUTION_CUE_RX = re.compile(r"\bmusic\b|\bmusica\b|\britmos?\b|\brhythms?\b|\btransici|\btransition|\bgiro\b|"
                              r"\bshift|\bmoved? (from|to|towards)\b|\bevoluc|\bevolv|\bcentrarse\b|\bfocus",
                              re.IGNORECASE)
# Elogios sin contenido verificable («uno de los DJs más influyentes»): no describen al artista.
PUFFERY_RX = re.compile(r"\b(sin duda|uno de los|una de las|one of the|el mejor|la mejor|the best|most influential|"
                        r"mas influyentes|legendar(y|io|ia))\b", re.IGNORECASE)
# Frases que arrancan desde la anterior («From that point on…», «Following his debut…»): fuera de contexto se
# entienden mal; pesan menos, aunque nombren al artista.
CONTEXT_OPENER_RX = re.compile(r"^(from that point|following|after that|years later|almost a year later|later that|"
                               r"posteriormente|tras (eso|ello)|a partir de entonces|dos anos mas tarde)\b",
                               re.IGNORECASE)
# Un alias solo se confirma con texto que lo presente como tal; si una fuente descriptiva nombra ese alias sin
# decirlo (p. ej. como otro DJ o como un sello), la relación es ambigua y no se usa.
ALIAS_WORDS = re.compile(r"\balias\b|\bunder the (name|alias|moniker)\b|\bbajo el (nombre|alias|seudonimo)\b|"
                         r"\bpseudonym|\bseudonimo\b|\bartistic name\b|\bnombre artistico\b|\bmoniker\b", re.IGNORECASE)
# Nombres seguidos en una enumeración («Design, Zenit, Question y Music On»).
LIST_GAP_RE = re.compile(r"^[\s,]*((and|y|e|&)\s+)?$")
# Residencias que no lo son:dónde vive (geográfica) o el título de un programa («The Residency» de BBC Radio 1).
NOT_RESIDENCY_RX = re.compile(r"\b(tiene|fijo|fija|establecio|traslado) su residencia\b|\bresidencia en la ciudad\b|"
                              r"\bThe Residency\b")
# Frases que dependen de la anterior («It aims…», «But after eleven years, the series…»): fuera de contexto no
# dicen de quién hablan. Solo cuentan si nombran al artista.
DANGLING_RX = re.compile(r"^(it|this|that|these|those|but|however|throughout|based on|esto|este|esta|pero|"
                         r"sin embargo)\b", re.IGNORECASE)
MONTHS = {"january", "february", "march", "april", "may", "june", "july", "august", "september", "october",
          "november", "december", "enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
          "septiembre", "octubre", "noviembre", "diciembre", "summer", "spring", "winter", "autumn"}
LABEL_WORDS = re.compile(r"\blabels?\b|\bimprints?\b|\brecords\b|\bsellos?\b|\brecordings\b|\bplattenlabel\b|"
                         r"\bplatenlabel\b|\betichetta\b|\beigenlabel\b|\bplattenfirma\b", re.IGNORECASE)
PARTY_WORDS = re.compile(r"\bpart(y|ies)\b|\bnights?\b|\bevents?\b|\bseries\b|\bfestival\b|\bfiestas?\b|"
                         r"\beventos?\b|\bciclos?\b|\bclub nights?\b|\bpartys\b|\bpartyreihe\b|\bveranstaltungs|"
                         r"\bfeest(en)?\b|\bsoirees?\b|\bfesta\b", re.IGNORECASE)
# Frases descriptivas: la primera regla que encaja decide el tipo (sin tildes ni mayúsculas, salvo «from X»).
SENTENCE_KINDS = [(kind, re.compile(rx, re.IGNORECASE)) for kind, rx in (
    ("proyecto propio", OWN_PROJECT_RX),
    ("residencia", RESIDENCY_RX),
    ("hito", r"award|prize|\bwon\b|\bvoted\b|\bnamed\b|nominat|premi|galardon|nominad|\bchart|number \d|"
             r"\bnumero \d|\btop \d|\bexito|\blista|headlin|mainstream success|\bnon-?stop\b|"
             r"\b\d+([- ]and[- ]a[- ]half)?[- ]hours?\b|\b\d+ horas\b"),
    ("proyecto paralelo", r"\bside[- ]project|\bmember of\b|\bmiembro de\b|\bproyecto paralelo|\bformed (the |a )?"
                          r"(duo|group|band|trio|project)|\balongside [\w ]{1,40} (as|in) (the )?(duo|group|band)|"
                          r"\bunder the (alias|moniker)|\bbajo el alias|\balias\b"),
    ("origen", r"\bborn\b|\bnaci(o|da|do|eron)\b|\b(is|are|was|were|comes?|hails?|originally) from\b|\bnatural de\b|"
               r"\bgrew up\b|\bcreci(o|eron)\b|\boriginari"),
    ("inicios", r"\bbegan (his|her|their|to|djing|playing|producing|as)\b|\bstarted (djing|playing|producing|his|her|"
                r"their|out|to|as)\b|\bearly (career|years|life)|\bdebut|\bse inicio\b|\binicio su\b|"
                r"\b(comenz|empez)(o|aron) (a|su)\b|\bprimer[oa]s? (pasos|sesion|actuacion|disco|bateria|ep)\b|"
                r"\bformed in\b|\bse form(o|aron)\b|\bat the age of\b|\ba la edad de\b"),
    ("estilo", r"\bsound\b|\bstyle\b|\bgenres?\b|\bknown for\b|\bspeciali[sz]|\binfluenc|\binspir|\bsonido\b|"
               r"\bestilo\b|\bespecializ|\bgustos musicales\b|\binspiraciones\b|\bevolv|\bevoluc|\bshift(ed)? "
               r"(towards|to)\b|\bgiro hacia\b"),
    ("colaboración", r"collaborat|colabor|back-to-back|\bb2b\b"),
    ("escena", r"\bfestivals?\b|\bclubs?\b|\bclubes\b|\bnightclub|\bibiza\b|\bwarehouse\b|\bsala\b|\bdiscoteca"),
    ("música destacada", r"\balbum\b|\bsingle\b|\bep\b|\btrack\b|\balbumes?\b|\bsencillo|\bremix"),
)]
IDENTITY_RE = re.compile(r"\b(is|are|was|were) (a|an|the)\b|\b(es|son|fue|fueron) (un|una|el|la)\b")
# Artículos de Wikipedia en otros idiomas (sources.other_language_article: de, fr, nl, it, pt). Reglas aparte, que
# nunca se aplican a textos en español o inglés: solo las relaciones esenciales (fundar o dirigir un sello o una
# fiesta, residencias, inicios, origen, colaboraciones, hitos). La frase se envía tal cual, con su idioma en la fuente.
OTHER_LANG_RE = re.compile(r"^Wikipedia \((?!es\)|en\))[a-z]{2,3}\)")
OTHER_SENTENCE_KINDS = [(kind, re.compile(rx, re.IGNORECASE)) for kind, rx in (
    ("proyecto propio", r"\bgr[uü]nde(te|ten|t)\b|\bgegr[uü]ndet\b|\bopgericht\b|\boprichters?\b|"
                        r"\b(richtte|richtten)\b.{0,60}\bop\b|\bfonde(e|es|rent)?\b|\bfondat(eur|rice|ore|o|a)\b|"
                        r"\bfundou\b|\beigene[nms]? (label|plattenlabel|partyreihe|party|veranstaltungsreihe)\b|"
                        r"\beigen (label|platenlabel|feest)\b|\b(son|leur) propre label\b|\bpropria etichetta\b|"
                        r"\b(leitet|leiten|betreibt|betreiben|runt|runnen)\b"),
    ("residencia", r"\bresident(en|in)?\b|\bresidenz\b|\bresidentie\b|\bresidenza\b"),
    ("hito", r"\bpreis|\bauszeichnung|\bprijs\b|\bprix\b|\bpremio\b|\bnominier|\bgenomineerd\b|\bcharts?\b|"
             r"\bhitparade\b|\btop ?\d+\b|\b(platz|plaats|nummer|numero) \d"),
    ("origen", r"\bgeboren\b|\bstamm(t|en) aus\b|\bafkomstig uit\b|\bnat[oa] a\b|\bnascid[oa]\b"),
    ("inicios", r"\bbegann(en)?\b|\bbegon(nen)?\b|\bcommenc|\bdeb[uü]t|\bcomec"),
    ("colaboración", r"\bzusammenarbeit\b|\bzusammen mit\b|\bsamenwerking\b|\bsamen met\b|collabor|\bb2b\b"),
    ("escena", r"\bfestivals?\b|\bclubs?\b|\bklub\b|\bibiza\b"),
    ("música destacada", r"\balbum\b|\bsingle\b|\bep\b|\bremix"),
)]
OTHER_IDENTITY_RE = re.compile(r"\b(ist|sind|war|waren) (ein|eine|einer|der|die|das)\b|\b(is|was|zijn|waren) "
                               r"(een|de|het)\b|\b(est|etait|sont) (un|une|le|la)\b|\b(e|era|sono) (un|una|uno|il|la)\b"
                               r"|\b(e|era|sao) (um|uma|o|a)\b")
OTHER_SOUND_CUE_RX = re.compile(r"\bstil\b|\bstijl\b|\bstile\b|\bstyle\b|\bklang\b|\bsound\b|\bgeluid\b|\bmusik\b|"
                                r"\bmuziek\b|\bmusique\b|\bmusica\b", re.IGNORECASE)
LIST_LIKE_RE = re.compile(r"^\s*\d{4}\s*[-–]|\(\d{4}\)\s*[,;]?\s*\S+.*\(\d{4}\)")  # «2008 - Orbeat», «A (2009) B (2012)»
ENTITY_RE = re.compile(r"\b[A-Z][\w&'’.-]*(?:\s+(?:[A-Z0-9][\w&'’.-]*|of|de|del|the|&))*")
ENTITY_STOP = {"he", "she", "they", "his", "her", "their", "in", "on", "at", "the", "a", "an", "it", "this", "after",
               "during", "since", "from", "with", "as", "el", "la", "los", "las", "en", "su", "sus", "tras", "desde",
               "con", "un", "una", "dj", "djs", "ep", "lp", "nombre artistico", "tipo", "pais", "generos",
               "ocupaciones", "integrantes", "descripcion breve", "activo desde", "premios", "lugar de nacimiento",
               "miembro de", "sello fundado por el artista", "proyecto conjunto", "b2b documentado",
               "otros alias del mismo artista", "actuaciones documentadas en eventos", "lugar de formacion",
               "ano de formacion", "however", "also", "later", "sin embargo", "ademas", "de", "of", "and", "y",
               "dos", "tres", "sin", "cuando", "mientras", "durante", "actualmente", "two", "three"}
CONNECTORS = {"de", "del", "of", "the", "&", "and", "y"}  # no abren ni cierran un nombre propio
# Valor editorial: lo que ha construido o define su sonido pesa más que los datos biográficos genéricos.
KIND_WEIGHT = {"sello propio": 6, "fiesta propia": 6, "proyecto propio": 5, "residencia": 5, "sello que dirige": 5,
               "proyecto paralelo": 4, "estilo": 4, "colaboración": 3, "escena": 3, "inicios": 3, "hito": 3,
               "identidad": 3, "origen": 2, "alias": 1, "festival": 1, "música destacada": 1, "otro": 0,
               "publica en": 0}


@dataclass
class Fact:
    id: str          # H1, H2… (lo que cita el modelo)
    kind: str        # categoría editorial / relación que afirma (ver PRIORITY)
    text: str        # dato o frase de la fuente, sin modificar
    source: SourceDoc
    entities: list[str] = field(default_factory=list)  # nombres propios implicados (sellos, clubes, personas…)
    period: str | None = None                           # año o periodo que menciona («2012» o «2012–2022»)
    # Estado de verificación: «relación estructurada» (campo explícito de MusicBrainz/Wikidata) o «frase de la
    # fuente» (texto literal de Wikipedia o la web oficial). Nunca hay inferencias: lo deducido no entra.
    basis: str = "frase de la fuente"
    names_artist: bool = False  # la frase nombra al artista (nombre o apellido): habla de él, no del contexto

    def as_dict(self) -> dict:
        return {"id": self.id, "kind": self.kind, "text": self.text, "source": self.source.label,
                "url": self.source.url, "license": self.source.license, "entities": self.entities,
                "period": self.period, "basis": self.basis}


def _plain(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c))


def _fold(text: str) -> str:
    return _plain(text).casefold()


def _clean_entity(raw: str, at_start: bool = False) -> str:
    """«In March 2004 Marco Carola» → «Marco Carola»: sin palabras de arranque, fechas ni conectores en los extremos.
    Una sola palabra al inicio de la frase terminada en «-mente» o «-ly» es un adverbio, no un nombre."""
    tokens = raw.strip(" .,'’").split()
    while tokens and (_fold(tokens[0]) in ENTITY_STOP or _fold(tokens[0]) in MONTHS or tokens[0].isdigit()
                      or _fold(tokens[0]) in CONNECTORS):
        tokens = tokens[1:]  # «In March», «On September 4»: el inicio de frase y la fecha no son entidades
    while tokens and _fold(tokens[-1]) in CONNECTORS:
        tokens = tokens[:-1]
    if at_start and len(tokens) == 1 and re.search(r"(mente|ly)$", _fold(tokens[0])):
        return ""
    return " ".join(tokens).strip(" .,'’")


def _entities(text: str, name: str) -> list[str]:
    """Nombres propios de un hecho (sin el artista ni palabras de arranque): sirven para medir su relevancia y para
    detectar hechos redundantes (el mismo sello contado por dos fuentes)."""
    body = text.split(":", 1)[1] if re.match(r"^[A-ZÁÉÍÓÚ][^:]{0,90}:\s", text) else text
    skip = {_fold(name)} | {_fold(w) for w in name.split()}
    out = []
    for m in ENTITY_RE.finditer(body):
        value = _clean_entity(m.group(0), at_start=m.start() == 0 or body[:m.start()].rstrip().endswith((".", ":")))
        if (_fold(value) not in ENTITY_STOP and _fold(value) not in skip and _fold(value) not in MONTHS
                and not value.isdigit() and len(value) > 1):
            out.append(value)
    return list(dict.fromkeys(out))


def _name_runs(text: str, name: str, start: int = 0) -> list[list[str]]:
    """Nombres propios desde `start`, agrupados en enumeraciones («Design, Zenit, Question y Music On» es una)."""
    skip = {_fold(name)} | {_fold(w) for w in name.split()}
    runs: list[list[str]] = []
    last_end = None
    for m in ENTITY_RE.finditer(text, start):
        value = _clean_entity(m.group(0), at_start=m.start() == 0)
        if not value or _fold(value) in skip or _fold(value) in ENTITY_STOP or value.isdigit():
            continue
        if runs and last_end is not None and LIST_GAP_RE.match(text[last_end:m.start()]):
            runs[-1].append(value)
        else:
            runs.append([value])
        last_end = m.end()
    return runs


# Palabras de rol o de acción que, con mayúscula al inicio de frase («Founded his own label…»), no son un nombre.
ROLE_WORDS = (r"(co-?)?(founders?|founded|owners?|head|runs?|ran|established|launched|started|created|"
              r"fundador(a|es)?|fund[oó]|propietari[oa]s?|dirige)")
ROLE_PREFIX_RE = re.compile(rf"^{ROLE_WORDS}\s+(of|de)\s+((the|el|la)\s+)?((record )?label\s+)?", re.IGNORECASE)
ROLE_WORD_RE = re.compile(ROLE_WORDS, re.IGNORECASE)


def own_names(fact: Fact, name: str) -> list[str]:
    """Lo que el artista ha fundado, creado o dirige: el primer nombre (o la enumeración) tras la expresión.
    «hosted his own Paradise party at Ibiza's DC10» → Paradise (DC10 es el club, no es suyo)."""
    if fact.basis == "relación estructurada":
        return fact.entities
    plain = _plain(fact.text)
    m = re.search(OWN_PROJECT_RX, plain, re.IGNORECASE)
    runs = _name_runs(plain, name, m.start()) if m else []
    # «Owner of record label Gettraum», «Founder of Shake Records»: la expresión con mayúscula inicial no es el nombre.
    for run in runs:
        names = [ROLE_PREFIX_RE.sub("", n).strip() for n in run]
        names = [n for n in dict.fromkeys(names) if n and not ROLE_WORD_RE.fullmatch(n)]
        if names:
            return names
    return []


def _is_enumeration(fact: Fact, name: str) -> bool:
    """Cuatro o más nombres seguidos: una lista (de sellos, alias, eventos), poco útil para redactar."""
    return any(len(run) >= 4 for run in _name_runs(_plain(fact.text), name))


def _first_entity(fact: Fact, name: str) -> str | None:
    runs = _name_runs(_plain(fact.text), name)
    return _fold(runs[0][0]) if runs else None


def _period(text: str) -> str | None:
    years = sorted({m.group(0) for m in YEAR_RE.finditer(text)})
    return None if not years else years[0] if len(years) == 1 else f"{years[0]}–{years[-1]}"


def _structured(doc: SourceDoc) -> list[tuple[str, str, int]]:
    """(tipo, «Campo: valor.», rango): el rango ordena los campos de un mismo tipo (nacimiento antes que país)."""
    out, fields = [], list(FIELDS)
    for chunk in re.split(r"(?<=\.)\s+(?=[A-ZÁÉÍÓÚÑ][^:]{0,90}:\s)", doc.text):
        field_name = _fold(chunk.split(":", 1)[0].strip()) if ":" in chunk else ""
        kind = FIELDS.get(field_name)
        if kind:
            out.append((kind, chunk.strip(), 1 + fields.index(field_name)))
    return out


def _own_kind(plain: str) -> str:
    """Un proyecto propio es un sello, una fiesta/serie u otra cosa (blog, tienda, plataforma)."""
    if LABEL_WORDS.search(plain):
        return "sello propio"
    if PARTY_WORDS.search(plain):
        return "fiesta propia"
    return "proyecto propio"


def _descriptive(doc: SourceDoc, name: str) -> list[tuple[str, str]]:
    if OTHER_LANG_RE.match(doc.label):
        return _descriptive_other_language(doc, name)
    out, folded_name = [], _fold(name)
    for i, sentence in enumerate(re.split(r"(?<=[.!?])\s+(?=[A-Z0-9«\"“(])", doc.text)):
        sentence = sentence.strip()
        if not MIN_SENTENCE_CHARS <= len(sentence) <= MAX_SENTENCE_CHARS or sentence.endswith("…"):
            continue  # demasiado corta, demasiado larga o cortada por el recorte de la fuente
        if LIST_LIKE_RE.search(sentence) or len(YEAR_RE.findall(sentence)) > 3:
            continue  # restos de discografía o listas de fechas
        folded, plain = _fold(sentence), _plain(sentence)
        kind = next((k for k, rx in SENTENCE_KINDS if rx.search(plain)), None)
        if kind == "proyecto propio":
            kind = _own_kind(plain)
            if kind == "sello propio" and DIRECTS_RX.search(plain) and not CREATES_RX.search(plain):
                kind = "sello que dirige"
        elif kind == "residencia" and NOT_RESIDENCY_RX.search(plain):
            kind = "otro"
        elif kind in (None, "escena", "origen", "inicios") and GENRE_RX.search(plain) and SOUND_CUE_RX.search(plain):
            kind = "estilo"  # «is from Manchester and specialises in house music», «exponente del tech house»
        elif kind in (None, "escena") and GENRE_RX.search(plain) and EVOLUTION_CUE_RX.search(plain):
            kind = "estilo"  # «decide dejar atrás los ritmos más duros… música más minimalista»
        if DANGLING_RX.search(plain) and folded_name not in folded:
            kind = "otro"
        if i == 0 and folded_name in folded and IDENTITY_RE.search(folded):
            kind = "identidad" if kind in (None, "estilo", "origen", "escena") else kind  # la frase de presentación
        out.append((kind or "otro", sentence))
    return out


def _descriptive_other_language(doc: SourceDoc, name: str) -> list[tuple[str, str]]:
    """Artículo en otro idioma: mismas reglas de longitud y forma, pero solo las relaciones esenciales; lo demás queda
    como «otro» (no ocupa plazas). El sonido, solo con un género y una palabra de estilo o música."""
    out, folded_name = [], _fold(name)
    for i, sentence in enumerate(re.split(r"(?<=[.!?])\s+(?=[A-Z0-9«\"“(])", doc.text)):
        sentence = sentence.strip()
        if not MIN_SENTENCE_CHARS <= len(sentence) <= MAX_SENTENCE_CHARS or LIST_LIKE_RE.search(sentence) \
                or len(YEAR_RE.findall(sentence)) > 3:
            continue
        folded, plain = _fold(sentence), _plain(sentence)
        kind = next((k for k, rx in OTHER_SENTENCE_KINDS if rx.search(plain)), None)
        if kind == "proyecto propio":
            kind = _own_kind(plain)
            if kind == "sello propio" and DIRECTS_RX.search(plain) and not CREATES_RX.search(plain):
                kind = "sello que dirige"
        elif kind in (None, "escena") and GENRE_RX.search(plain) and OTHER_SOUND_CUE_RX.search(plain):
            kind = "estilo"
        if i == 0 and folded_name in folded and OTHER_IDENTITY_RE.search(folded):
            kind = "identidad" if kind in (None, "estilo", "origen", "escena") else kind
        out.append((kind or "otro", sentence))
    return out


def _corroborated_genres(text: str, docs: list[SourceDoc]) -> str | None:
    """«Géneros: …» de Wikidata solo con los géneros que otra fuente también menciona (la clasificación de Wikidata
    puede ser discutible: «pop» para un DJ de house). Se compara la raíz de la palabra distintiva del género."""
    others = _fold(" ".join(d.text for d in docs if not d.label.startswith("Wikidata")))
    kept = []
    for genre in text.split(":", 1)[1].rstrip(".").split(","):
        if _fold(genre.strip()) in GENERIC_GENRES:
            continue  # «música electrónica» no dice nada del estilo de un artista de electrónica
        words = [w for w in re.findall(r"\w+", _fold(genre)) if w not in ("musica", "music", "de", "del")]
        if words and all(re.search(rf"\b{re.escape(w[:6])}", others) for w in words):
            kept.append(genre.strip())
    return f"Géneros: {', '.join(kept)}." if kept else None


def extract(docs: list[SourceDoc], name: str) -> list[Fact]:
    """Expediente completo: todos los hechos disponibles, en el orden de las fuentes (descriptivas primero dentro de
    cada tipo), con sus entidades, periodo y base de verificación."""
    raw: list[tuple[str, str, int, SourceDoc]] = []
    for doc in docs:
        items = ([(k, t, 0) for k, t in _descriptive(doc, name)] if doc.label.startswith(DESCRIPTIVE)
                 else _structured(doc))
        if doc.label.startswith("Wikidata"):
            items = [(k, _corroborated_genres(t, docs) if t.startswith("Géneros:") else t, r) for k, t, r in items]
            items = [(k, t, r) for k, t, r in items if t]
        raw.extend((kind, text, rank, doc) for kind, text, rank in items)
    raw.sort(key=lambda r: r[2])  # estable: las frases (rango 0) antes que los campos, y estos por su rango
    surname = re.compile(rf"\b({re.escape(_fold(name))}|{re.escape(_fold(name.split()[-1]))})\b") if name.split() else None
    found = [Fact("", kind, text, doc, entities=_entities(text, name), period=_period(text),
                  basis="relación estructurada" if doc.label.startswith(STRUCTURED) else "frase de la fuente",
                  names_artist=bool(surname and surname.search(_fold(text))))
             for kind, text, _rank, doc in raw]
    # Frases sobre un proyecto propio ya identificado («Music On was launched in 2011…», «In 2022 the Paradise party
    # moved to Amnesia»): son parte de ese proyecto, no un dato suelto de escena.
    own = {_fold(n) for f in found if f.kind in OWN_KINDS for n in own_names(f, name)}
    for f in found:
        first = _first_entity(f, name) if f.kind in ("otro", "escena") and f.basis == "frase de la fuente" else None
        if first and any(o == first or (len(o) > 3 and o in first) for o in own):
            f.kind = _own_kind(_plain(f.text))
    # Una descripción breve con géneros («UK techno/house DJ & producer») dice cómo suena: es un hecho de estilo.
    # La identidad la da la frase de presentación (o la otra descripción).
    for f in found:
        if f.kind == "identidad" and f.text.startswith("Descripción breve:") and GENRE_RX.search(_plain(f.text)):
            f.kind = "estilo"
    return found


def _relevance(fact: Fact, key_entities: set[str], mentions: dict[str, int]) -> float:
    """Relevancia dentro de su tipo: nombres propios implicados (sellos, clubes, proyectos), los que las relaciones
    estructuradas señalan como propios del artista (sello fundado, grupo) y los que reaparecen en muchos hechos del
    expediente (Metamorfosi en Joseph Capriati): lo que las fuentes cuentan una y otra vez define al artista. Sin
    medidas de popularidad: no hay datos que las respalden."""
    folded = {_fold(e) for e in fact.entities}
    score = KIND_WEIGHT.get(fact.kind, 0)
    if fact.kind == "estilo":
        # El sonido se cuenta con géneros, no con referencias: una comparación con varios títulos o artistas
        # («el Dynamic Syncopation de Surgeon, el Cavernous Walls de Lost…») es difícil de contextualizar.
        score += 2 * bool(GENRE_RX.search(_plain(fact.text))) - max(len(folded) - 2, 0)
        # Su evolución con fecha («En 2004 Marco Carola… música más minimalista») antes que el contexto de época.
        score += fact.names_artist + 0.5 * bool(fact.period)
    else:
        score += min(len(folded), 3) * 0.5
    # Basta con que aparezca un nombre propio confirmado: una lista de sellos no vale más por ser larga.
    score += 2 * any(k in e or e in k for k in key_entities for e in folded)
    score += min(sum(min(mentions.get(e, 1) - 1, 4) for e in folded), 6) * 0.5
    if fact.basis == "frase de la fuente":
        score += 0.5  # una frase cuenta la relación con contexto; el campo estructurado la respalda igualmente
    if fact.kind in OWN_KINDS and FOUNDING_RX.search(_plain(fact.text)):
        score += 1.5  # la frase que cuenta cómo nació el proyecto antes que una de sus fechas
    if fact.kind != "identidad" and _is_enumeration(fact, ""):
        score -= 2  # enumeraciones (sellos, alias, eventos)
    praise = len(PUFFERY_RX.findall(_plain(fact.text)))
    if praise and fact.kind == "estilo" and GENRE_RX.search(_plain(fact.text)):
        score -= 1.5 * praise  # el elogio pesa, pero no hace perder el género («exponente del tech house»)
    elif praise:
        score -= 3
    if CONTEXT_OPENER_RX.search(_plain(fact.text)):
        score -= 2
    if fact.source.label.startswith("Discogs"):
        score -= 1  # notas breves y sin fecha de una fuente complementaria: ceden ante Wikipedia y MusicBrainz
    if fact.kind == "origen" and re.match(r"(País|Área asociada)", fact.text):
        score -= 1  # el lugar de nacimiento dice más que el país
    return score


def alias_status(fact: Fact, sentences: list[str]) -> str | None:
    """Alias de MusicBrainz: «confirmado» si una frase descriptiva lo presenta como alias, «ambiguo» si alguna lo
    nombra sin decirlo (otro DJ, un sello con el mismo nombre…) y None si ninguna lo menciona."""
    if fact.kind != "alias":
        return None
    names = [n.strip() for n in fact.text.split(":", 1)[-1].rstrip(".").split(",") if n.strip()]
    status = None
    for alias in names:
        words = re.findall(r"\w+", _fold(alias))
        if not words:
            continue
        rx = re.compile(r"\b" + r"\W*".join(map(re.escape, words)) + r"\b")
        hits = [s for s in sentences if rx.search(_fold(s))]
        if any(not ALIAS_WORDS.search(_plain(s)) for s in hits):
            return "ambiguo"
        if hits:
            status = "confirmado"
    return status


def _words(text: str) -> set[str]:
    return {w for w in re.findall(r"\w{4,}", _fold(text))}


def _covered(a: set[str], b: set[str]) -> bool:
    """«Design Music» ya está en «Design, Zenit…» (y al revés)."""
    return all(any(x in y or y in x for y in b) for x in a)


def _said_by_sentence(fact: Fact, chosen: list[Fact]) -> bool:
    """Un campo estructurado que una frase elegida ya cuenta con contexto («Miembro de: Hot Natured» frente a «He is
    a member of… Hot Natured and the head of…»). «Sello fundado» no: aporta el significado de la fundación."""
    mine = {_fold(e) for e in fact.entities}
    return (fact.basis == "relación estructurada" and fact.kind not in ("sello propio", "estilo") and bool(mine)
            and any(o is not fact and o.basis == "frase de la fuente"
                    and _covered(mine, {_fold(e) for e in o.entities}) for o in chosen))


def _years(fact: Fact) -> set[str]:
    return {m.group(0) for m in YEAR_RE.finditer(fact.text)}


def _genres(fact: Fact) -> set[str]:
    return {g.casefold().replace("-", " ") for g in GENRE_RX.findall(_plain(fact.text))}


def _adds_detail(fact: Fact, other: Fact) -> bool:
    """Una frase concreta aporta algo frente a otra que ya nombra lo mismo: una fecha que la otra no tiene, o es
    concreta frente a una enumeración («co-founded You&Me in 2015, initially as a student club night» frente a
    «co-founder of You&Me, Hide & Seek and Syntho»)."""
    if _years(fact) - _years(other):
        return True
    return fact.basis == "frase de la fuente" and _is_enumeration(other, "") and not _is_enumeration(fact, "")


def _redundant(fact: Fact, chosen: list[Fact]) -> bool:
    """Ya está dicho: mismas entidades (el sello contado por Wikipedia y por MusicBrainz, o en dos idiomas) o casi
    las mismas palabras."""
    mine = {_fold(e) for e in fact.entities}
    for other in chosen:
        theirs = {_fold(e) for e in other.entities}
        # En un hecho de sonido lo que cuenta es el género, no los nombres que lo acompañan («UK», «Manchester»).
        if (fact.kind != "estilo" and mine and theirs and _covered(mine, theirs)
                and (_covered(theirs, mine) or not _adds_detail(fact, other))):
            return True
        # El mismo acontecimiento contado dos veces: mismo tipo, algún nombre en común y ninguna fecha nueva.
        if (fact.kind == other.kind and mine & theirs and fact.kind not in ("identidad", "estilo")
                and not _adds_detail(fact, other)):
            return True
        if fact.kind == other.kind == "estilo" and _genres(fact) and _genres(fact) <= _genres(other) \
                and not _adds_detail(fact, other):
            return True  # «Descripción breve: tech house» y «Géneros: tech house»
        if fact.kind == "origen" and other.kind == "identidad" and any(e in _fold(other.text) for e in mine):
            return True  # «nació en Barcelona en 1974» cuando la presentación ya dice «(Barcelona, 1974)»
        a, b = _words(fact.text), _words(other.text)
        if a and b and len(a & b) / len(a | b) > 0.5:
            return True
    return False


def select(facts: list[Fact], limit: int = MAX_FACTS) -> list[Fact]:
    """Entre 1 y `limit` hechos por relevancia editorial: primero el cupo de cada tipo (lo más relevante de cada
    uno) y luego se completa sin pasar de los límites por tipo ni repetir lo ya dicho. «Publica en» solo si hay muy
    pocos hechos más. Sin relleno: si hay pocos, pocos."""
    key_entities = {_fold(e) for f in facts if f.kind in ("sello propio", "proyecto paralelo")
                    and f.basis == "relación estructurada" for e in f.entities}
    mentions: dict[str, int] = {}
    for f in facts:
        for e in {_fold(x) for x in f.entities}:
            mentions[e] = mentions.get(e, 0) + 1
    sentences = [f.text for f in facts if f.basis == "frase de la fuente"]
    # Alias ambiguos fuera; los confirmados por una frase pesan como un proyecto paralelo.
    usable = [f for f in facts if f.kind != "alias" or alias_status(f, sentences) != "ambiguo"]
    score = {id(f): _relevance(f, key_entities, mentions) + 3 * (alias_status(f, sentences) == "confirmado")
             for f in usable}
    ranked = sorted(usable, key=lambda f: -score[id(f)])  # estable: a igualdad, el orden de las fuentes
    chosen: list[Fact] = []

    def fits(fact: Fact, upto: int) -> bool:
        return (len(chosen) < limit and fact not in chosen
                and sum(f.kind == fact.kind for f in chosen) < min(upto, PER_KIND.get(fact.kind, limit))
                and not _redundant(fact, chosen))

    # Primera pasada: el cupo de cada tipo, solo con hechos de peso (un «Activo desde» no ocupa el sitio de un
    # proyecto); la presentación siempre entra.
    for kind in SELECTION_ORDER:
        for fact in (f for f in ranked if f.kind == kind):
            # Los grupos de Discogs completan, no ocupan plazas reservadas (los integrantes son identidad).
            filler = ((fact.kind in FILLER_FIELDS and fact.basis == "relación estructurada"
                       and fact.source.label != "MusicBrainz (relaciones)")
                      or fact.source.label == "Discogs (relaciones)")
            if (kind == "identidad" or (score[id(fact)] >= MIN_CORE_SCORE and not filler)) and fits(fact, QUOTA[kind]):
                chosen.append(fact)
    # Si sobra sitio: lo más relevante de cualquier tipo, con un mínimo de calidad. Lo débil (sin clasificar, dónde
    # publica, eventos) solo si apenas hay nada más. Los campos que ya cuenta una frase elegida dejan su sitio (una
    # vez) a lo siguiente.
    dropped: list[Fact] = []
    for _round in range(2):
        for fact in ranked:
            if fact in dropped or (fact.kind in WEAK_KINDS and sum(f.kind not in WEAK_KINDS for f in chosen) >= 3):
                continue
            if fact.kind != "identidad" and score[id(fact)] < MIN_FILL_SCORE:
                continue
            if fits(fact, limit):
                chosen.append(fact)
        dropped = [f for f in chosen if _said_by_sentence(f, chosen)]
        if not dropped:
            break
        chosen = [f for f in chosen if f not in dropped]
    chosen.sort(key=lambda f: PRIORITY.index(f.kind))
    for i, fact in enumerate(chosen, 1):
        fact.id = f"H{i}"
    return chosen


def dossier(facts: list[Fact], chosen: list[Fact]) -> dict:
    """Expediente para diagnóstico: hechos por categoría (con fuente, entidades, periodo y base) y cuáles se usaron."""
    used = {id(f) for f in chosen}
    groups: dict[str, list[dict]] = {}
    for f in facts:
        groups.setdefault(f.kind, []).append({**f.as_dict(), "selected": id(f) in used})
    return {"total": len(facts), "selected": len(chosen),
            "by_kind": {k: groups[k] for k in PRIORITY if k in groups}}


def descriptive_count(facts: list[Fact]) -> int:
    return sum(1 for f in facts if f.source.label.startswith(DESCRIPTIVE))


def artist_kind(docs: list[SourceDoc]) -> str:
    """solista | dúo | grupo, según MusicBrainz (tipo e integrantes): cambia la concordancia del texto."""
    mb = next((d.text for d in docs if d.label == "MusicBrainz"), "")
    if "Tipo: grupo" not in mb:
        return "solista" if "Tipo: persona" in mb else "artista"
    members = re.search(r"Integrantes: ([^.]+)\.", mb)
    count = len(members.group(1).split(",")) if members else 0
    return "dúo" if count == 2 or re.search(r"\bduo\b", _fold(" ".join(d.text for d in docs))) else "grupo"


def as_docs(facts: list[Fact]) -> list[SourceDoc]:
    """Los hechos como documentos para el validador: cada uno conserva la etiqueta de su fuente (las fundaciones,
    residencias y éxitos solo los respalda texto descriptivo o una relación explícita de MusicBrainz)."""
    return [SourceDoc(f.id, f.source.label, f.source.url, f.source.license, f.text) for f in facts]
