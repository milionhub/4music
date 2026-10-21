"""Biografías editoriales generadas con Groq a partir de hechos verificados (T1.4, v7: 1 o 2 párrafos).

Flujo: caché persistente por MBID → (si no hay) fuentes → suficiencia → hechos extraídos y seleccionados
(facts.py) → el modelo redacta SOLO con esos hechos → validación contra los mismos hechos → almacén. Un candado por
MBID evita generaciones duplicadas simultáneas. Los fallos se guardan con caducidad para no reintentar en bucle;
nunca impiden abrir la ficha.

Validación contra los hechos enviados: identidad (nombra al artista), todo nombre propio, año y título del texto
debe estar en ellos; afirmaciones sensibles (sellos fundados, residencias, integrantes, nacimiento, éxitos,
premios…) necesitan un hecho que respalde ese tipo de relación con esos nombres; forma mínima (1 o 2 párrafos,
sin listas, preguntas, clichés, menciones a fuentes, referencias temporales caducadas ni textos excesivos).
"""

from __future__ import annotations

import re
import threading
import time
import unicodedata
from datetime import datetime, timezone
from typing import Callable

from pydantic import BaseModel, ValidationError

from app import facts, store
from app.groq_client import GroqClient, GroqError
from app.sources import QUOTED_RE, YEAR_RE, SourceDoc, sufficient

KIND = "biography"
DOSSIER_KIND = "dossier"
TTL_OK_S = 90 * 24 * 3600            # una biografía válida se reutiliza 90 días
TTL_INSUFFICIENT_S = 14 * 24 * 3600   # sin fuentes suficientes: se reintenta en 2 semanas
TTL_REJECTED_S = 7 * 24 * 3600        # contenido no válido (sin respaldo, fuente inventada): 1 semana
TTL_FORMAT_S = 24 * 3600              # forma no válida también tras el reintento: al día siguiente
TTL_ERROR_S = 3600                    # error temporal: 1 hora
MIN_RATE_LIMIT_S = 60                 # tras un 429, como mínimo 1 minuto (o lo que indique Retry-After)
BRIEF_FACTS = 3                       # con tan pocos hechos (o ≤2 descriptivos): un párrafo breve
# Extensión orientativa que se pide al modelo. El validador solo frena lo excesivo o lo vacío.
TARGETS = {"brief": (40, 80), "full": (100, 150)}
MIN_WORDS, MAX_WORDS = 20, 190  # ~25 % sobre el máximo pedido (150): margen, no relleno
COPY_NGRAM = 12                       # 12 palabras seguidas idénticas a una fuente = copia (no una fecha y un lugar)
# v4 (T1.5): solo con texto descriptivo; identidad y sonido primero; lanzamientos como contexto secundario.
# v5: un único reintento ante rechazos solo de forma.
# v6: presentación editorial de 1 o 2 párrafos y comprobación de afirmaciones. Las versiones anteriores se
# regeneran una vez; si la nueva generación falla, se sigue mostrando la biografía válida anterior (`previous`).
# v7: el modelo redacta a partir de hechos seleccionados (facts.py), no de fragmentos de las fuentes. Todas las
# biografías anteriores (también las válidas) se regeneran una vez, al visitar cada artista; mientras tanto se
# muestra la anterior válida, marcada como heredada (`previous`, con su versión).
# v8 (sesión 2): expediente ampliado (Wikipedia completa en español e inglés, relaciones de MusicBrainz: sellos
# fundados, alias, B2B, eventos), selección por relevancia editorial y presentación en dos párrafos (identidad,
# sonido y trayectoria; proyectos, conexiones y escena). Mismo mecanismo de renovación que la v7.
PROMPT_VERSION = 8
# Validador v2: equivalencias geográficas. v3: sin cuotas de forma (títulos, años, párrafos, longitud), solo
# listas, preguntas, clichés y textos excesivos; cualquier rechazo admite un reintento de reparación. Los rechazos
# guardados con un validador anterior se reintentan una vez; las biografías válidas no se tocan. v4: nombres
# artísticos («under the artistic name») y fiestas propias («hosted his own … party»). v5: géneros y gentilicios
# deben estar en los hechos; descripciones del sonido, relevancia/influencia y «club propio» necesitan respaldo.
# v6: no se parten frases en abreviaturas («Do.Mi.No. and Music On»), nacimiento solo con evidencia explícita (su
# cláusula o «Nombre (Lugar, 7 de febrero de 1975)»), «ganó» solo con premios y algo más de margen de longitud.
VALIDATOR_VERSION = 6
# Rechazos de contenido: tras el reintento siguen sin respaldo → una semana (los de forma, un día).
CONTENT_PROBLEMS = ("no nombra", "año sin respaldo", "título entre comillas", "afirmación sin respaldo",
                    "nombre sin respaldo", "género sin respaldo", "nacionalidad sin respaldo")

_cooldown_until = 0.0  # pausa global tras un 429 de Groq (respeta la cuota del plan gratuito)

BANNED = re.compile(
    r"musicbrainz|wikidata|wikipedia|base de datos|registrad|documentad|según (las|la|los) fuentes?|fuentes? consultadas|"
    r"\b\d+\s+lanzamientos|cuenta con \d+|su último registro|lanzamientos propios|publica desde|"
    r"(su|el) lanzamiento más reciente|entre sus álbumes figura",
    re.IGNORECASE)
CLICHES = re.compile(
    r"\b(imprescindibles?|referentes? indiscutibles?|no deja(n)? indiferente|leyenda viva|nombres? a seguir|"
    r"a tener en cuenta|sin duda|voz relevante|máximos? exponentes?|viaje sonoro|universo sonoro|"
    r"sello inconfundible|legendari[oa]s?|pura energía|referentes? (de|en) la escena|revolucionari[oa]s?|"
    r"inigualables?|incomparables?|uno de los (artistas|djs|productores|nombres) más (influyentes|importantes|"
    r"destacados|relevantes))\b", re.IGNORECASE)
# Enumeraciones: tres o más nombres entre comillas o tres o más años seguidos («2018, 2019 y 2020»).
QUOTED_LIST = re.compile(r"(«[^»]+»|\"[^\"]+\")(\s*\([^)]*\))?(\s*(,|\by\b|\be\b)\s*(«[^»]+»|\"[^\"]+\")"
                         r"(\s*\([^)]*\))?){2,}")
YEAR_LIST = re.compile(r"\b(19|20)\d{2}\b(\s*(,|\by\b|\be\b)\s*\b(19|20)\d{2}\b){2,}")
# Lo que precede a unas comillas indica si es un lanzamiento («su sencillo «Glue»») u otro proyecto («el blog
# «Feel My Bicep»», «el festival «Hide & Seek»»): cuenta la última palabra clave antes de las comillas.
QUOTE_CONTEXT_CHARS = 40
QUOTE_KIND_RE = re.compile(
    r"\b(?P<release>sencillos?|singles?|temas?|canci[oó]n(es)?|cortes?|pistas?|tracks?|[aá]lbum(es)?|discos?|eps?|lps?|"
    r"remix(es)?|mixtapes?|recopilatorios?)\b|"
    r"\b(?P<other>sellos?|blogs?|fiestas?|ciclos?|series?|eventos?|festival(es)?|premios?|galard[oó]n(es)?|marcas?|"
    r"plataformas?|clubs?|clubes|colectivos?|programas?|podcasts?|emisoras?|proyectos?|alias|agencias?|estudios?|"
    r"revistas?|academias?|escuelas?|residencias?|giras?|grupos?|d[uú]os?|bandas?)\b", re.IGNORECASE)
# Referencias temporales que caducan o futuros sobre hechos ya pasados.
STALE_TIME = re.compile(r"\bpr[oó]ximamente\b|\bse espera que\b|\b(est[aá]|estaba) previst[oa]\b|\bpr[oó]xim[oa]s? "
                        r"(mes|meses|año|años|semana|semanas|temporada)\b|\beste (año|mes|verano|invierno)\b|"
                        r"\ben la actualidad prepara\b|\bver[aá] la luz\b", re.IGNORECASE)
# Preguntas, viñetas, negritas o etiquetas al inicio de párrafo («Origen: …»): el usuario solo ve prosa.
LIST_FORMAT = re.compile(r"[¿?]|^\s*[-•*]|\*\*|^\s*\w+( \w+){0,2}:\s", re.MULTILINE)

SCHEMA = {
    "type": "object",
    "properties": {
        "paragraphs": {"type": "array", "items": {"type": "string"}},
        "fact_ids": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["paragraphs", "fact_ids"],
    "additionalProperties": False,
}

SYSTEM = (
    "Eres redactor de una revista de música electrónica underground y escribes la presentación de un artista («Sobre "
    "el artista») para la ficha de una app. No es una ficha enciclopédica ni una cronología: es una presentación "
    "editorial que explica qué distingue musicalmente al artista. Recibes HECHOS VERIFICADOS (H1, H2…), agrupados "
    "por categoría, con su fuente.\n"
    "Reglas obligatorias:\n"
    "1. Usa SOLO los hechos de la lista. No añadas nombres, fechas, lugares, relaciones ni acontecimientos que no "
    "estén en ellos; nada de conocimiento propio ni de datos deducidos o calculados (con «8 temporadas desde 2012» "
    "no se puede escribir otro año).\n"
    "2. Respeta la relación de cada hecho: fundar, dirigir, publicar en un sello, colaborar y actuar son cosas "
    "distintas («publica en» no es «fundó»; dirigir no es fundar); el «área asociada» no es nacimiento ni residencia; "
    "una residencia no es una actuación puntual; actuar en un festival no es encabezarlo; un B2B es una sesión "
    "conjunta, no un proyecto estable; un lanzamiento no es un éxito salvo que el hecho lo diga.\n"
    "3. Prioriza identidad artística, sonido y proyectos propios (sellos, fiestas, proyectos paralelos) sobre datos "
    "biográficos secundarios como la fecha de nacimiento. No hace falta usar todos los hechos. Nunca enumeres "
    "lanzamientos.\n"
    "4. Español natural de revista musical, fácil de leer; los nombres de géneros, sellos, fiestas y clubes se "
    "mantienen tal cual. Sin calcos del inglés: «label» es «sello» (nunca «etiqueta»), «sub-label» es «subsello», "
    "«party» es «fiesta» (no un club). Concordancia según sea solista, dúo o grupo. Países y ciudades pueden ir en "
    "español. No atribuyas nacionalidad, sonido ni géneros que no digan los hechos (tampoco a otros artistas).\n"
    "5. Sin preguntas, listas, clichés ni superlativos promocionales («legendario», «revolucionario», «uno de los "
    "más influyentes»): la relevancia solo se afirma si un hecho la respalda.\n"
    "6. Sin referencias temporales que caduquen («próximamente», «este año», «actualmente prepara»): cuenta los "
    "hechos como pasados o con su fecha.\n"
    "7. Prohibido mencionar fuentes, bases de datos, registros o recuentos.\n"
    "8. Parafrasea: no copies frases enteras de los hechos.\n"
    "9. La extensión es orientativa. Con pocos hechos, texto breve: no rellenes.\n"
    "Devuelve JSON con 'paragraphs' (1 o 2 párrafos de prosa, sin títulos, viñetas ni etiquetas) y 'fact_ids' "
    "(ids H1, H2… de los hechos que has usado)."
)


class BiographyRecord(BaseModel):
    """Lo que se guarda en el backend. `model` y `status` no se exponen tal cual al frontend."""
    artist_mbid: str
    biography: str | None             # párrafos separados por una línea en blanco
    source_urls: list[str]
    source_labels: list[str] = []
    source_licenses: list[str | None] = []
    generated_at: str
    model: str | None
    status: str          # ok | insufficient_sources | rejected | error
    error_code: str | None = None   # rate_limited | unavailable | bad_response | incomplete | motivo del rechazo
    prompt_version: int = PROMPT_VERSION
    validator_version: int = 1      # los registros anteriores a este campo se validaron con la v1
    previous: dict | None = None    # biografía válida anterior (texto y fuentes) mientras no haya una nueva válida
    rejected_draft: str | None = None  # último texto rechazado, solo para diagnóstico (nunca se publica)


_locks: dict[str, threading.Lock] = {}
_locks_guard = threading.Lock()


def _lock_for(mbid: str) -> threading.Lock:
    with _locks_guard:
        return _locks.setdefault(mbid, threading.Lock())


def stored(mbid: str) -> BiographyRecord | None:
    """Registro guardado de cualquier versión (para mostrar la biografía anterior mientras se renueva)."""
    raw = store.get(KIND, mbid)
    if not raw:
        return None
    try:
        return BiographyRecord.model_validate(raw)
    except ValidationError:
        return None


def cached(mbid: str) -> BiographyRecord | None:
    """Registro vigente de la versión actual. Los de versiones anteriores (también los válidos: el formato cambió)
    se regeneran una vez; su biografía válida pasa a `previous` por si la nueva generación falla. Un rechazo del
    validador anterior también se reintenta una vez, sin esperar a que caduque (las fuentes inventadas, no)."""
    record = stored(mbid)
    if not record or record.prompt_version != PROMPT_VERSION:
        return None
    if (record.status == "rejected" and record.validator_version < VALIDATOR_VERSION
            and record.error_code != "unknown_source"):
        return None
    return record


def _previous_of(record: BiographyRecord | None) -> dict | None:
    """Biografía válida que conviene conservar al regenerar: la del propio registro o la que ya arrastraba."""
    if record and record.status == "ok" and record.biography and not quality_issue(record.biography):
        return {"biography": record.biography, "source_urls": record.source_urls,
                "source_labels": record.source_labels, "source_licenses": record.source_licenses,
                "prompt_version": record.prompt_version}
    return record.previous if record else None


def paragraphs(text: str | None) -> list[str]:
    return [" ".join(p.split()) for p in re.split(r"\n\s*\n", text or "") if p.strip()]


def _release_titles(paragraph: str) -> list[str]:
    """Títulos entre comillas que son lanzamientos; los blogs, sellos, fiestas, premios o festivales no cuentan.
    Sin contexto que lo aclare se cuenta como lanzamiento (en caso de duda, más estricto)."""
    out = []
    for m in QUOTED_RE.finditer(paragraph):
        before = paragraph[max(0, m.start() - QUOTE_CONTEXT_CHARS):m.start()]
        before = re.split(r"[»\".;]", before)[-1]  # el contexto no cruza otro título ni otra frase
        kinds = list(QUOTE_KIND_RE.finditer(before))
        if not kinds or kinds[-1].group("release"):
            out.append(m.group(1) or m.group(2))
    return out


def _form_issue(paras: list[str]) -> str | None:
    """Solo enumeraciones seguidas: varios títulos o fechas documentados en la prosa no son un problema."""
    if any(QUOTED_LIST.search(p) for p in paras):
        return "enumera títulos de lanzamientos"
    if any(YEAR_LIST.search(p) for p in paras):
        return "enumera años"
    return None


def quality_issue(text: str | None) -> str | None:
    """Control editorial que no depende de las fuentes: menciones a bases de datos, recuentos, listas de títulos
    o años y clichés. Se aplica también a textos ya guardados y a los editoriales pendientes de revisión."""
    paras = paragraphs(text)
    if not paras:
        return "vacío"
    if BANNED.search(text):
        return "menciona fuentes, registros o recuentos"
    form = _form_issue(paras)
    if form:
        return form
    if CLICHES.search(text):
        return "cliché o lenguaje publicitario"
    return None


def in_cooldown() -> bool:
    return time.time() < _cooldown_until


def start_cooldown(retry_after: float | None) -> float:
    """Pausa global tras un 429 de Groq, compartida por biografías y TrackDNA (misma clave y cuota)."""
    global _cooldown_until
    wait = max(MIN_RATE_LIMIT_S, min(retry_after or 0, TTL_ERROR_S))
    _cooldown_until = time.time() + wait
    return wait


def invalidate(mbid: str) -> bool:
    """Regeneración selectiva: borra solo la biografía de ese MBID (nunca la caché completa)."""
    return store.delete(KIND, mbid)


def _plan(chosen: list[facts.Fact]) -> str:
    """Extensión pedida según los hechos seleccionados: pocos hechos, un párrafo breve; si no, uno o dos."""
    return "brief" if len(chosen) <= BRIEF_FACTS or facts.descriptive_count(chosen) <= 2 else "full"


def _length_instruction(chosen: list[facts.Fact]) -> str:
    plan = _plan(chosen)
    low, high = TARGETS[plan]
    if plan == "brief":
        return (f"Escribe UN párrafo breve (orientativo: unas {low} a {high} palabras): hay pocos hechos y no hay "
                "que rellenar.")
    return (f"Escribe DOS párrafos (orientativo: unas {low} a {high} palabras en total). Primero: quién es, su sonido "
            "y su trayectoria. Segundo: sus proyectos propios, conexiones y lugar en la escena. Si los hechos no dan "
            "para un segundo párrafo con contenido propio, escribe uno solo.")


KIND_NOTES = {"solista": "solista", "dúo": "dúo (concordancia en plural)", "grupo": "grupo (concordancia en plural)",
              "artista": "tipo no documentado (evita suponer si es persona o grupo)"}


def _user_prompt(name: str, chosen: list[facts.Fact], kind: str = "artista") -> str:
    lines = "\n".join(f"[{f.id}] ({f.kind}; {f.basis}; fuente: {f.source.label}) {f.text}" for f in chosen)
    # Sin hechos de estilo, el modelo tiende a inventar el sonido («líneas de bajo contundentes»): se le dice.
    sound = "" if any(f.kind == "estilo" for f in chosen) else (
        " No hay hechos sobre su sonido: no lo describas ni le atribuyas géneros.")
    return (f"Artista: {name} — {KIND_NOTES.get(kind, kind)}\n\nHECHOS VERIFICADOS:\n{lines}\n\n"
            f"Escribe la presentación de {name}. {_length_instruction(chosen)}{sound}")


# --- Comprobación de afirmaciones ---------------------------------------------------------------------------------
def _plain(text: str) -> str:
    """Sin tildes (conserva mayúsculas): «cofundó» y «Berlín» se comparan con «founded» y «Berlin»."""
    return "".join(c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c))


def _fold(text: str) -> str:
    return _plain(text).casefold()


DESCRIPTIVE = ("Wikipedia", "Web oficial")
# Una fundación la respalda texto descriptivo, la relación explícita «label founder» de MusicBrainz o las notas del
# perfil de Discogs (CC0) que la afirmen («founded their own label NO ART»). Residencias y éxitos, no.
FOUNDED_SCOPE = DESCRIPTIVE + ("MusicBrainz (relaciones)", "Discogs (perfil)")
# (tipo, expresión en el texto generado, evidencia necesaria en una frase de las fuentes, fuentes admitidas).
# Fundaciones, residencias y éxitos solo los respalda texto descriptivo: un sello de la discografía no prueba
# que el artista lo fundara. Se compara sin tildes y sin distinguir mayúsculas.
CLAIMS = [(label, re.compile(claim, re.IGNORECASE), re.compile(evidence), scope) for label, claim, evidence, scope in (
    ("sello o proyecto fundado",
     r"\b(co)?fund(o|aron|ar|ador|adora|adores|adoras)\b|\bcre(o|aron) (su|sus|el|la|los|las)\b|\bpusieron? en marcha"
     r"|\bsus? propi[oa]s? (sello|fiesta|festival|evento|plataforma|serie)",
     # Palabras completas: «Hot Creations» no es «created» ni «head of» es «founded».
     r"\b(co-?)?found(ed|er|ers|ing)?\b|\bestablish|\bset(ting)? up\b|\blaunch(ed|es|ing)?\b|\bcreat(e|ed|es|ing)\b"
     r"|\b(co)?fund(o|aron|ado|ada|ador|adora|adores)\b|\bcre(o|aron)\b|\bown (record )?label\b|puso en marcha"
     r"|\bown [\w' ]{0,20}(party|parties|night|event|festival|series)\b|\bhost(s|ed)? (his|her|their) own\b"
     # Artículos de respaldo en otros idiomas (de/nl/fr/it/pt): mismos verbos de fundación, mismo requisito de nombres.
     r"|\bgrunde(te|ten|t)\b|\bgegrundet\b|\bopgericht\b|\boprichters?\b|\bfonde(e|es|rent)?\b"
     r"|\bfondat(eur|rice|ore|o|a)\b|\bfundou\b|\beigenlabel\b|\beigene[nms]? (label|plattenlabel)\b",
     FOUNDED_SCOPE),
    ("residencia en club o fiesta", r"\bresidencias?\b|\bresidentes?\b", r"residen", DESCRIPTIVE),
    ("residencia geográfica",
     r"\bafincad[oa]s?\b|\breside(n)?\b|\bvive(n)? en\b|\bradicad[oa]s?\b|\bcon base en\b|\binstalad[oa]s? en\b"
     r"|\b(se )?traslad(o|aron|ad[oa]s?)\b|\bse mud(o|aron)\b|\bmudad[oa]s?\b|\bemigr(o|aron)\b",
     r"based|lives|living|resid|relocat|moved to|settled|afincad|vive|radicad|instalad", DESCRIPTIVE),
    ("nacimiento", r"\bnaci(o|eron)\b|\bnacid[oa]s?\b", r"\bborn\b|nacid|naci(o|eron)|nacimiento", None),
    ("origen", r"\boriginari[oa]s? de\b|\bprocedentes? de\b|\bnatural de\b",
     r"\bfrom\b|origin|natural de|procedente|nacimiento|\bborn\b", None),  # formarse en un sitio no es ser de allí
    ("formación del grupo", r"\bse form(o|aron)\b|\bformad[oa]s? en\b|\bsurgi(o|eron) en\b",  # «formado en X por A y B»:
     r"form|found|creat|began|started|origin|consist|member|compris|duo of|integra", None),  # también sus integrantes
    ("integrantes", r"\bintegrad[oa]s? por\b|\bformad[oa]s? por\b|\bcompuest[oa]s? por\b|\bintegrantes?\b|\bmiembros?\b",
     r"consist|member|formed by|compris|composed|duo of|integra|miembro", None),
    ("éxito o listas",
     r"\bexitos?\b|\bhits?\b|\bnumero (uno|1)\b|\blistas?\b|\btop ?\d+|\bhimnos?\b|\bsuperventas\b|\bcharts?\b"
     r"|\b(posicion|puesto) \d+",
     r"chart|\bhit|number (one|\d+)|no\. ?1|top ?\d|exito|lista|anthem|platinum|gold|best.?sell", DESCRIPTIVE),
    ("premio o reconocimiento", r"\bpremi|\bgalardon|\bnominad|\bnominacion|\bnombrad[oa]s?\b|\breconocid[oa]s? como\b"
     r"|\bgan(o|aron) (el|la|los|las|un|una|dos|tres|varios|varias)\b"  # «ganó un Grammy», no «ganó el apoyo»
     r"(?=\s+(\S+\s+){0,2}?(premio|galardon|grammy|award|trofeo|concurso|certamen|campeonato|titulo|distincion"
     r"|medalla|disco de (oro|platino)))",
     r"award|prize|\bwon\b|nominat|premi|galardon|named|voted|best of", None),
    ("nombre real", r"\bnombre real\b|\balias de\b|\bseudonimo\b|\bcuyo nombre\b|\bnombre artistico de\b",
     r"real name|\bborn\b|alias|known professionally|professionally known|stage name|pseudonym|nombre real|seudonimo"
     r"|artistic name|artist name|under the name|nombre artistico",
     None),
    # v5 (sesión 2): descripciones del sonido, relevancia/influencia y «club propio» también necesitan un hecho.
    ("descripción del sonido",
     r"\bsonido (caracterizado|marcado|definido|basado|que (fusiona|combina|mezcla))|\bcaracterizad[oa]s? por\b"
     r"|\bfusiona(n|ndo)?\b|\bcombina(n|ndo)? [\w ]{0,20}\bcon\b",
     r"sound|style|described|sonido|estilo|blend|fus|combin|mix", None),
    ("relevancia o influencia",
     r"\binfluencia\b|\binfluyentes?\b|\breconocid[oa]s?\b(?! como)|\bde alto perfil\b|\bprestigios[oa]s?\b"
     r"|\bmas (relevantes|importantes|destacad[oa]s)\b|\bpanorama (global|mundial|internacional)\b",
     r"influen|acclaim|renown|recogni|prestig|important|relevan|reconoc|award|voted|\bbest\b|premi", None),
    ("club propio", r"\b(su|sus) (propio|propios) (club|clubes|clubs|local)\b|\bsu club\b|\bpropietari[oa]s? de\b",
     r"\bown(s|ed)? (a |the |his |her |their )?(club|nightclub|venue)|club owner|\bowner of\b|propietari|duen[oa] de", None),
    ("colaboración", r"\bcolaboracion(es)? con\b|\bha colaborado con\b|\bcolabor(o|aron) con\b",
     r"collab|colabora|featur|feat\.|remix|joint|together|partner|b2b", None),
)]
# Exónimos habituales: «Londres» en el texto se compara con «London» en las fuentes (sin tildes).
EXONYMS = {"Londres": "London", "Reino Unido": "United Kingdom", "Irlanda del Norte": "Northern Ireland",
           "Nueva York": "New York", "Alemania": "Germany", "Paises Bajos": "Netherlands", "Belgica": "Belgium",
           "Francia": "France", "Escocia": "Scotland", "Inglaterra": "England", "Gales": "Wales",
           "Estados Unidos": "United States", "Irlanda": "Ireland", "Italia": "Italy", "Espana": "Spain",
           "Suecia": "Sweden", "Dinamarca": "Denmark", "Noruega": "Norway", "Japon": "Japan", "Brasil": "Brazil",
           "Sudafrica": "South Africa", "Colonia": "Cologne", "Bruselas": "Brussels", "Amberes": "Antwerp",
           "Gante": "Ghent", "Viena": "Vienna", "Lisboa": "Lisbon", "Copenhague": "Copenhagen",
           "Estocolmo": "Stockholm", "Praga": "Prague", "Varsovia": "Warsaw", "Edimburgo": "Edinburgh",
           "Tokio": "Tokyo", "Sidney": "Sydney", "Ciudad de Mexico": "Mexico City", "Marsella": "Marseille",
           "Napoles": "Naples", "Europa": "Europe", "Paises Bajos": "Netherlands", "Rumania": "Romania",
           "Bucarest": "Bucharest", "Amsterdam": "Amsterdam", "Berlin": "Berlin", "Suiza": "Switzerland", "Austria": "Austria",
           "Polonia": "Poland", "Portugal": "Portugal", "Hungria": "Hungary", "Grecia": "Greece", "Turquia": "Turkey",
           "Croacia": "Croatia", "Serbia": "Serbia", "Bulgaria": "Bulgaria", "Ucrania": "Ukraine", "Rusia": "Russia"}
# Una región forma parte de su país: «Belfast, Irlanda del Norte» respalda «Reino Unido», nunca al revés.
# «Irlanda» no se respalda con «Irlanda del Norte» (son países distintos).
# También el gentilicio y el nombre local: «Gales» se respalda con «Welsh»; «Nápoles», con «Napoli».
PLACE_PARTS = {"united kingdom": ("england", "scotland", "wales", "northern ireland", "great britain", "british"),
               "wales": ("welsh",), "england": ("english",), "scotland": ("scottish",), "ireland": ("irish",),
               "italy": ("italian", "italiano", "italiana"), "spain": ("spanish", "espanol", "espanola"),
               "france": ("french", "frances", "francesa"), "germany": ("german", "aleman", "alemana"),
               "netherlands": ("dutch", "neerlandes", "neerlandesa", "holandes", "holandesa"),
               "belgium": ("belgian", "belga"), "united states": ("american", "estadounidense"),
               "naples": ("napoli",), "romania": ("romanian", "rumano", "rumana"), "switzerland": ("swiss", "suizo", "suiza"),
               "austria": ("austrian", "austriaco", "austriaca"), "poland": ("polish", "polaco", "polaca"),
               "portugal": ("portuguese", "portugues", "portuguesa"), "hungary": ("hungarian", "hungaro", "hungara")}
PLACE_SHADOWS = {"ireland": "northern ireland", "york": "new york"}
MULTIWORD_PLACES = re.compile(r"\b(United Kingdom|Northern Ireland|Great Britain|United States|New York|South Africa"
                              r"|Mexico City)\b", re.IGNORECASE)
# Aclaraciones de las fuentes («Área asociada (no indica residencia ni nacimiento)»): no son evidencia.
DISCLAIMER_RE = re.compile(r"\([^)]*\bno (indica|implica)\b[^)]*\)", re.IGNORECASE)
NAME_RE = re.compile(r"\b[A-Z][\w&'’.-]*")
NAME_STOP = {"dj", "djs", "djing", "ep","eps", "lp", "el", "la", "los", "las", "su", "sus", "en", "con", "y", "de", "del", "un",
             "una", "ademas", "tras", "desde", "entre", "al", "a", "fue", "es", "ha", "han", "junto", "como", "tambien"}
# Tras un punto seguido de minúscula no empieza otra frase: es una abreviatura («Do.Mi.No. and Music On»).
SENTENCE_RE = re.compile(r"(?<=[.!?])\s+(?![a-záéíóúüñ])|(?<=;)\s+|\n+")
CLAUSE_END_RE = re.compile(r"[.;](\s|$)")
# La afirmación termina donde empieza otra oración coordinada o de relativo («…, y publicó…», «…, que en 2009
# formaron…») o, como mucho, a las 14 palabras.
# También acaba en una coma seguida de otra oración en minúscula («nacido en Barcelona en 1974, inició…»), salvo
# que siga un complemento («…, en el club X», «…, con su marca Y») o un nombre propio («Belfast, Irlanda»).
NEXT_CLAUSE_RE = re.compile(r",\s+(y|e|pero|mientras|aunque|donde|que|quien|quienes|cuando)\s+|\n"
                            r"|,\s+(?!(en|de|del|el|la|los|las|al|a|con|junto|sus?)\b)(?=[a-z])")
PREV_CLAUSE_RE = re.compile(r",\s+(y|e|pero|mientras|aunque)\s+")  # hacia atrás, el relativo sigue al título
CLAIM_WINDOW_WORDS = 14


def _exonyms(text: str) -> str:
    for es, en in EXONYMS.items():
        text = re.sub(rf"\b{es}\b", en, text, flags=re.IGNORECASE)
    return text


def _names(text: str, skip: set[str]) -> list[str]:
    """Nombres propios de un fragmento (palabras con mayúscula), sin artículos, siglas comunes ni el artista.
    Los lugares de varias palabras («Irlanda del Norte», «Reino Unido») son un único nombre."""
    joined = MULTIWORD_PLACES.sub(lambda m: m.group(0).title().replace(" ", "_"), _exonyms(_plain(text)))
    out = []
    for token in NAME_RE.findall(joined):
        t = _fold(token.strip(".-'’"))
        if t and t not in NAME_STOP and t not in skip and not t.isdigit():
            out.append(token.strip(".-'’").replace("_", " "))
    return out


def _source_sentence(sentence: str) -> str:
    """Frase de una fuente lista para comparar: sin tildes ni aclaraciones negativas, con exónimos en inglés."""
    return _fold(_exonyms(_plain(DISCLAIMER_RE.sub(" ", sentence))))


def _mentions(sentence: str, name: str) -> bool:
    key = _fold(name)
    if key in PLACE_SHADOWS:
        sentence = sentence.replace(PLACE_SHADOWS[key], " ")
    return any(k in sentence for k in (key, *PLACE_PARTS.get(key, ())))


# Nacimiento: solo lo que la fuente presenta como tal. «born»/«nacido» hasta el final de su cláusula («born in 1975,
# he moved to Berlin» no hace de Berlín su ciudad natal) o la convención de Wikipedia en español «Nombre (Lugar,
# 7 de febrero de 1975)»: lugar y fecha completa entre paréntesis tras el nombre. Frases ya sin tildes y en minúscula.
BIRTH_RE = re.compile(r"\bborn\b|\bnacid[oa]s?\b|\bnaci(o|eron)\b|\bnacimiento\b")
BIRTH_CLAUSE_END_RE = re.compile(
    r"[);]|,\s+(?=(he|she|they|it|who|which|where|and|but|el|ella|ellos|que|donde|y|pero|se)\b)"
    r"|\s(and|but|where|who|which|then|y|e|pero|donde|que|mientras)\s(?!raised|criad)")
LEAD_BIRTH_RE = re.compile(r"^[^()]{1,80}?\(([^()\d]*?[a-z][^()\d]*?)[,\s]+(el\s+)?\d{1,2}\s+de\s+[a-z]+\s+de\s+\d{3,4}\b")


def _birth_evidence(sentence: str) -> list[str]:
    out = []
    for m in BIRTH_RE.finditer(sentence):
        end = BIRTH_CLAUSE_END_RE.search(sentence, m.end())
        out.append(sentence[m.start():end.start() if end else len(sentence)])
    lead = LEAD_BIRTH_RE.match(sentence)
    if lead:
        out.append(f"born {lead.group(1)}")
    return out


def claim_issue(text: str, name: str, docs: list[SourceDoc]) -> str | None:
    """Cada afirmación de un tipo sensible necesita una frase de las fuentes con evidencia de ese tipo que contenga
    los nombres propios que la acompañan (desde la expresión hasta el final de la frase). Heurístico: rechaza en
    caso de duda y el rechazo admite un reintento."""
    plain = _plain(text)
    skip = {_fold(t) for t in re.findall(r"[\w&'’.-]+", name)}
    sentences = {scope: [_source_sentence(s) for d in docs if scope is None or d.label.startswith(scope)
                         for s in SENTENCE_RE.split(d.text) if s.strip()] for scope in (None, DESCRIPTIVE, FOUNDED_SCOPE)}
    prev_of = {}  # frase → la anterior de la misma fuente
    for d in docs:
        split = [_source_sentence(s) for s in SENTENCE_RE.split(d.text) if s.strip()]
        prev_of.update(zip(split[1:], split))
    # Cada afirmación abarca hasta el final de la frase o hasta donde empieza otra («cofundó X y tiene una
    # residencia en Y»: Y se comprueba como residencia, no como fundación).
    starts = sorted({m.start() for _l, claim_re, _e, _s in CLAIMS for m in claim_re.finditer(plain)})
    releases = set(_release_titles(plain))
    for label, claim_re, evidence_re, scope in CLAIMS:
        evidence = ([e for s in sentences[scope] for e in _birth_evidence(s)] if label == "nacimiento"
                    else [s for s in sentences[scope] if evidence_re.search(s)])
        for m in claim_re.finditer(plain):
            if not evidence:
                return f"afirmación sin respaldo ({label})"
            end = CLAUSE_END_RE.search(plain, m.end())
            stop = min([end.start() if end else len(plain)] + [x for x in starts if x > m.start()])
            window = plain[m.end():stop]  # sin la propia expresión («Fundaron…» no es un nombre)
            words = list(re.finditer(r"\S+", window))
            if len(words) > CLAIM_WINDOW_WORDS:
                window = window[:words[CLAIM_WINDOW_WORDS].start()]
            # Los títulos de lanzamientos se comprueban aparte; los demás nombres entre comillas forman parte de la
            # afirmación: «fundó el sello «X»» exige que X conste como fundado.
            window = QUOTED_RE.sub(lambda q: " " if (q.group(1) or q.group(2)) in releases else f" {q.group(0)[1:-1]} ",
                                   NEXT_CLAUSE_RE.split(window, 1)[0])
            if label == "éxito o listas":  # «su sencillo «X», su mayor éxito…»: el título va delante. La fuente
                # puede nombrarlo en la frase anterior («"Glue" was voted… It also reached number 1…»).
                start = max([0] + [e.end() for e in CLAUSE_END_RE.finditer(plain, 0, m.start())])
                before = _release_titles(PREV_CLAUSE_RE.split(plain[start:m.start()])[-1])
                if before and not any(_mentions(s, before[-1]) or _mentions(prev_of.get(s, ""), before[-1])
                                      for s in evidence):
                    return f"afirmación sin respaldo ({label}: {before[-1]})"
            for token in _names(window, skip):
                if not any(_mentions(s, token) for s in evidence):
                    return f"afirmación sin respaldo ({label}: {token})"
    return None


# Palabras que suelen abrir una frase en español: con mayúscula inicial no son nombres propios.
SENTENCE_STARTERS = {
    "su", "sus", "en", "tras", "desde", "ademas", "con", "entre", "durante", "hoy", "actualmente", "despues", "antes",
    "junto", "este", "esta", "estos", "estas", "ese", "esa", "ellos", "ellas", "ambos", "como", "por", "para",
    "aunque", "mientras", "cuando", "gracias", "nacido", "nacida", "nacidos", "nacidas", "formado", "formada",
    "formados", "formadas", "originario", "originaria", "conocido", "conocida", "conocidos", "bajo", "sobre", "hasta",
    "ya", "tambien", "asimismo", "posteriormente", "luego", "mas", "fue", "ha", "han", "era", "el", "la", "los", "las",
    "un", "una", "al", "del", "a", "de", "y", "e", "o", "lo", "sin", "segun", "paralelamente", "finalmente",
    "inicialmente", "alli", "aquel", "aquella", "dicho", "dicha", "sello", "fundo", "cofundo", "creo", "dirige",
    "lidera", "empezo", "comenzo", "inicio", "publico", "lanzo", "recibio", "obtuvo", "gano", "mantiene", "mantuvo",
    "tiene", "tuvo", "hizo", "pincho", "toco", "llego", "consiguio", "logro", "residente", "miembro", "integrante",
    "dj", "productor", "productora", "productores", "artista", "duo", "grupo", "colectivo", "todo", "toda", "todos",
    "todas", "cada", "otro", "otra", "otros", "otras", "solo", "gran", "varios", "varias", "algunos", "algunas",
    "ahora", "aquí", "aqui", "alli", "pronto", "primero", "primera", "tambien", "incluso", "sus", "nuestra", "ambas",
    "hijo", "hija", "amigos", "amigas", "esa", "eso", "esto", "aquello", "pero", "sino", "ni", "si", "no", "que",
    "quien", "donde", "nacio", "crecio", "vive", "trabaja", "trabajo", "debuto", "firmo", "fichado", "reconocido",
    "reconocida", "considerado", "considerada", "elegido", "elegida", "nombrado", "nombrada", "galardonado",
    "galardonada", "premiado", "premiada", "residente", "fundador", "fundadora", "cofundador", "cofundadora"}
SOURCE_NAMES = {"musicbrainz", "wikidata", "wikipedia"}  # las menciones a fuentes las rechaza BANNED


def _unsupported_name(text: str, name: str, docs: list[SourceDoc]) -> str | None:
    """Todo nombre propio del texto (personas, sellos, clubes, fiestas, lugares…) debe estar en algún hecho; los
    lugares se comparan con exónimos, regiones y gentilicios («Gales» ↔ «Welsh»)."""
    skip = {_fold(t) for t in re.findall(r"[\w&'’.-]+", name)} | SOURCE_NAMES
    corpus = [_source_sentence(d.text) for d in docs]
    for sentence in SENTENCE_RE.split(text):
        tokens = _names(sentence, skip)
        first = re.match(r"[\W_]*([\w&'’.-]+)\s*(\S?)", _plain(sentence))
        # «Tras…», «Publica…»: mayúscula de inicio de frase, no un nombre. Si la palabra siguiente también va en
        # mayúscula («Hot Creations acogió…»), es un nombre compuesto y se comprueba.
        starter = first and (_fold(first.group(1)) in SENTENCE_STARTERS or first.group(2).islower())
        if tokens and starter and _fold(tokens[0]) == _fold(first.group(1)):
            tokens = tokens[1:]
        for token in tokens:
            if not any(_mentions(c, token) for c in corpus):
                return f"nombre sin respaldo ({token})"
    return None


# Géneros y gentilicios: el modelo tiende a «completar» el sonido («deep house y soul») o la nacionalidad de otros
# artistas («el sueco» Adam Beyer). Cada uno debe estar en los hechos (sin tildes; gentilicio ↔ país o adjetivo).
GENRE_TERMS = ("deep house", "tech house", "minimal techno", "melodic techno", "progressive house", "afro house",
               "acid house", "jazz house", "uk garage", "drum and bass", "nu-disco", "microhouse", "breakbeat",
               "techno", "tecno", "house", "minimal", "trance", "disco", "electro", "ambient", "dubstep", "soul",
               "funk", "jazz", "pop", "rock", "hip hop", "garage", "idm")
GENRE_EQUIV = {"tecno": "techno"}
DEMONYMS = {"sueco": ("sweden", "swedish", "suec"), "italiano": ("italy", "italian", "itali"),
            "espanol": ("spain", "spanish", "espan"), "frances": ("france", "french", "franc"),
            "aleman": ("germany", "german", "aleman"), "britanico": ("united kingdom", "british", "brit", "england",
                                                                     "scotland", "wales", "northern ireland"),
            "ingles": ("england", "english", "ingl"), "gales": ("wales", "welsh", "gales"),
            "escoces": ("scotland", "scottish", "escoc"), "irlandes": ("ireland", "irish", "irland"),
            "norirlandes": ("northern ireland", "belfast"), "neerlandes": ("netherlands", "dutch", "neerland"),
            "holandes": ("netherlands", "dutch", "holand"), "belga": ("belgium", "belgian", "belg"),
            "rumano": ("romania", "romanian", "ruman"), "estadounidense": ("united states", "american"),
            "canadiense": ("canada", "canadian"), "australiano": ("australia", "australian"),
            "portugues": ("portugal", "portuguese", "portug"), "chileno": ("chile",), "argentino": ("argentin",),
            "danes": ("denmark", "danish", "danes"), "noruego": ("norway", "norwegian", "norueg"),
            "sudafricano": ("south africa",), "japones": ("japan", "japanese")}
DEMONYM_RE = re.compile(r"\b(" + "|".join(DEMONYMS) + r")(a|es|as)?\b")


def _unsupported_term(text: str, docs: list[SourceDoc]) -> str | None:
    corpus = _fold(" ".join(d.text for d in docs)).replace("-", " ")
    folded = _fold(text).replace("-", " ")
    for term in GENRE_TERMS:  # los compuestos primero: «deep house» no cuenta además como «house»
        key = term.replace("-", " ")
        if re.search(rf"\b{re.escape(key)}\b", folded):
            if not re.search(rf"\b{re.escape(GENRE_EQUIV.get(key, key))}", corpus):
                return f"género sin respaldo ({term})"
            folded = re.sub(rf"\b{re.escape(key)}\b", " ", folded)
    for m in DEMONYM_RE.finditer(folded):
        if not any(e in corpus for e in DEMONYMS[m.group(1)]):
            return f"nacionalidad sin respaldo ({m.group(0)})"
    return None


def _copied(text: str, docs: list[SourceDoc]) -> bool:
    def grams(t: str) -> set[tuple[str, ...]]:
        words = re.findall(r"\w+", _fold(t))
        return {tuple(words[i:i + COPY_NGRAM]) for i in range(len(words) - COPY_NGRAM + 1)}
    corpus = set().union(*(grams(d.text) for d in docs)) if docs else set()
    return bool(grams(text) & corpus)


def _years(text: str) -> set[str]:
    return {m.group(0) for m in YEAR_RE.finditer(text)}


def validate(text: str | list[str], name: str, docs: list[SourceDoc]) -> str | None:
    """Motivo de rechazo o None. Primero el contenido (identidad y respaldo de años y títulos), después las
    afirmaciones y por último la forma: un rechazo de forma garantiza que todo lo citado está respaldado."""
    paras = paragraphs(text) if isinstance(text, str) else [" ".join(p.split()) for p in text if p.strip()]
    full = "\n\n".join(paras)
    if name.casefold() not in full.casefold():
        return "no nombra al artista"
    corpus = " ".join(d.text for d in docs).casefold()
    for year in sorted(_years(full)):
        if year not in corpus:
            return f"año sin respaldo en las fuentes ({year})"
    for m in QUOTED_RE.finditer(full):
        title = (m.group(1) or m.group(2) or "").strip().casefold()
        if title and title not in corpus:
            return "título entre comillas sin respaldo en las fuentes"
    claim = claim_issue(full, name, docs) or _unsupported_term(full, docs)
    if claim:
        return claim
    if len(paras) > 2:
        return f"número de párrafos no admitido ({len(paras)})"
    words = len(full.split())
    if not MIN_WORDS <= words <= MAX_WORDS:
        return f"longitud fuera de rango ({words} palabras)"
    form = _form_issue(paras)
    if form:
        return form
    if BANNED.search(full):
        return "menciona fuentes, registros o recuentos"
    if LIST_FORMAT.search(full):
        return "formato de lista, etiquetas o preguntas"
    if CLICHES.search(full):
        return "cliché o lenguaje publicitario"
    if STALE_TIME.search(full):
        return "referencia temporal caducada"
    unsupported = _unsupported_name(full, name, docs)  # tras la forma: «Origen: …» es una etiqueta, no un nombre
    if unsupported:
        return unsupported
    if _copied(full, docs):
        return "copia literal de una fuente"
    return None


STORY_WORDS = (8, 55)
# Relleno valorativo o causal que los hechos no respaldan («consolidando su presencia», «se inspira en la cultura
# local», «refleja su visión»): en una historia breve no hay sitio para interpretaciones.
STORY_FLUFF = re.compile(
    r"\b(consolid\w*|reputaci[oó]n|visionari\w*|[uú]nic[oa]s?|de referencia|enriquec\w*|refleja\w*|marcando|"
    r"toma(ndo)? forma|se inspir\w*|inspirad[oa]s?|cultura local|su visi[oó]n|huella|emblem[aá]tic\w*|prestigi\w*|"
    r"aclamad\w*|exitos[oa]s?|innovador\w*|vanguardia|potente|ascenso|despeg\w*|catapult\w*|lleva su nombre|"
    r"gracias a|lo que (le|les) (permiti[oó]|llev[oó])|convirti[eé]ndo\w*|marc[oó] (su|el|la)|panorama|"
    r"controla\w*|gestiona\w*|aportando|preservando|esencia|tradici[oó]n|identidad sonora|sello personal|"
    r"(su|una) (entrada|presencia|lugar|posici[oó]n) en la escena|escena electr[oó]nica (local|internacional|mundial))\b",
    re.IGNORECASE)


def story_issue(title: str, text: str, name: str, docs: list[SourceDoc]) -> str | None:
    """Motivo de rechazo de una historia de «Más allá de la cabina» o None. Mismas comprobaciones de contenido que
    la biografía contra los hechos que la historia cita (años, títulos, afirmaciones sensibles, nombres propios,
    géneros y gentilicios, copia literal), y de forma para un texto breve. El título también se comprueba."""
    full = f"{title}. {text}"
    corpus = " ".join(d.text for d in docs).casefold()
    for year in sorted(_years(full)):
        if year not in corpus:
            return f"año sin respaldo en las fuentes ({year})"
    for m in QUOTED_RE.finditer(full):
        quoted = (m.group(1) or m.group(2) or "").strip().casefold()
        if quoted and quoted not in corpus:
            return "título entre comillas sin respaldo en las fuentes"
    problem = (claim_issue(text, name, docs) or _unsupported_term(full, docs) or _unsupported_name(full, name, docs))
    if problem:
        return problem
    words = len(text.split())
    if not STORY_WORDS[0] <= words <= STORY_WORDS[1]:
        return f"longitud fuera de rango ({words} palabras)"
    if len(title.split()) > 6 or not title.strip():
        return "título no válido"
    if BANNED.search(full) or LIST_FORMAT.search(text) or CLICHES.search(full) or STALE_TIME.search(full):
        return "forma no válida (fuentes, lista, cliché o tiempo)"
    fluff = STORY_FLUFF.search(full)
    if fluff:
        return f"valoración o causa sin respaldo («{fluff.group(0)}»)"
    if _copied(text, docs):
        return "copia literal de una fuente"
    return None


def content_problem(problem: str) -> bool:
    return problem.startswith(CONTENT_PROBLEMS)


def _retry_prompt(base: str, text: str, problem: str) -> str:
    return (f"{base}\n\nTu versión anterior se rechazó ({problem}):\n{text}\n\n"
            "Reescríbela solo con los HECHOS VERIFICADOS y cumpliendo todas las reglas. Si una afirmación, un nombre "
            "o una fecha no está tal cual en los hechos, elimínala o corrígela con ellos; no la sustituyas por otra.")


def generate(mbid: str, name: str, collect: Callable[[], list[SourceDoc]], groq: GroqClient,
             now: Callable[[], str] = lambda: datetime.now(timezone.utc).isoformat(timespec="seconds")
             ) -> BiographyRecord:
    """Biografía desde caché o generada. Nunca lanza: los fallos se devuelven con su estado."""
    hit = cached(mbid)
    if hit:
        return hit
    with _lock_for(mbid):  # una sola generación por artista; quien espere lee la caché
        hit = cached(mbid)
        if hit:
            return hit
        previous = _previous_of(stored(mbid))
        docs = collect()
        found = facts.extract(docs, name)
        chosen = facts.select(found)
        # Expediente completo (más de lo que se usa), para diagnóstico y futuras vistas. No afecta a otros datos.
        store.put(DOSSIER_KIND, mbid, facts.dossier(found, chosen), TTL_OK_S)
        refs = {f.id: f for f in chosen}

        def record(status: str, text: str | None = None, used: list[SourceDoc] | None = None,
                   ttl: float = TTL_ERROR_S, error_code: str | None = None, draft: str | None = None):
            used = used or []
            rec = BiographyRecord(artist_mbid=mbid, biography=text, source_urls=[d.url for d in used],
                                  source_labels=[d.label for d in used], source_licenses=[d.license for d in used],
                                  generated_at=now(), model=groq.model if text or draft else None, status=status,
                                  error_code=error_code, validator_version=VALIDATOR_VERSION,
                                  previous=None if status == "ok" else previous, rejected_draft=draft)
            store.put(KIND, mbid, rec.model_dump(), ttl)
            return rec

        def transient(code: str) -> BiographyRecord:  # no se guarda: se reintentará en la próxima visita
            return BiographyRecord(artist_mbid=mbid, biography=None, source_urls=[], generated_at=now(),
                                   model=None, status="error", error_code=code, previous=previous)

        if not sufficient(docs) or not facts.descriptive_count(chosen):
            return record("insufficient_sources", ttl=TTL_INSUFFICIENT_S)
        if not groq.configured:
            return transient("not_configured")
        if in_cooldown():
            return transient("cooldown")
        fact_docs = facts.as_docs(chosen)  # se valida contra lo enviado, no contra las fuentes completas
        base = prompt = _user_prompt(name, chosen, facts.artist_kind(docs))
        problem = ""
        for _attempt in range(2):  # como mucho una petición y un reintento por generación
            try:
                out = groq.structured(SYSTEM, prompt, "artist_biography", SCHEMA)
            except GroqError as exc:
                if exc.code == "rate_limited":
                    return record("error", ttl=start_cooldown(exc.retry_after), error_code=exc.code)
                return record("error", ttl=TTL_ERROR_S, error_code=exc.code)
            raw = out.get("paragraphs")
            # En modo json_object el modelo a veces devuelve el texto entero o separa párrafos con un solo salto.
            items = [raw] if isinstance(raw, str) else raw if isinstance(raw, list) else []
            paras = [" ".join(p.split()) for item in items  # también «\n» escrito como texto (barra + n)
                     for p in re.split(r"\n+", str(item).replace("\\n", "\n")) if p.strip()]
            text = "\n\n".join(paras)
            ids = [i for i in out.get("fact_ids") or out.get("source_ids") or [] if isinstance(i, str)]
            cited = [refs[i] for i in dict.fromkeys(ids) if i in refs]  # solo hechos realmente enviados
            if not cited or any(i not in refs for i in ids):
                return record("rejected", ttl=TTL_REJECTED_S, error_code="unknown_source")
            used = list({f.source.url: f.source for f in cited}.values())  # fuentes de esos hechos, sin repetir
            problem = validate(paras, name, fact_docs)
            if not problem:
                return record("ok", text, used, ttl=TTL_OK_S)
            prompt = _retry_prompt(base, text, problem)  # un único intento de reparación
        # Sigue sin cumplir tras el reintento: no se publica ni se reintenta en cada visita.
        return record("rejected", ttl=TTL_REJECTED_S if content_problem(problem) else TTL_FORMAT_S,
                      error_code=problem[:60], draft=text)


# --- Traducción de descripciones breves de Wikidata (respaldo) ----------------------------------------------------
DESC_KIND = "description_es"
TTL_DESC_OK_S = 180 * 24 * 3600
TRANSLATE_SCHEMA = {"type": "object", "properties": {"translation": {"type": "string"}}, "required": ["translation"],
                    "additionalProperties": False}
TRANSLATE_SYSTEM = (
    "Traduce al español la descripción breve de un artista musical. Traducción fiel y natural: no añadas, quites "
    "ni interpretes información y conserva los nombres propios. Devuelve JSON con 'translation' (una sola frase).")


def stored_translation(qid: str, text: str) -> tuple[bool, str | None]:
    """(hay registro para este texto exacto, traducción válida o None)."""
    hit = store.get(DESC_KIND, qid)
    if hit and hit.get("source") == text:
        return True, hit.get("text")
    return False, None


def translation_issue(source: str, translation: str) -> str | None:
    """Una traducción no puede añadir información: extensión acotada, sin cifras ni nombres propios nuevos."""
    if not translation:
        return "vacía"
    src_words, words = len(source.split()), len(translation.split())
    if words > max(2 * src_words, src_words + 4) or words > 25:
        return "longitud"
    if re.search(r"[.!?]\s|[¿?]", translation):
        return "más de una frase"
    if not set(re.findall(r"\d+", translation)) <= set(re.findall(r"\d+", source)):
        return "cifras nuevas"
    folded_source = _fold(_exonyms(source))
    for token in _names(translation.split(" ", 1)[1] if " " in translation else "", set()):  # sin la inicial
        if _fold(token) not in folded_source:
            return f"nombre nuevo ({token})"
    return None


def translate_description(qid: str, text: str, groq: GroqClient) -> str | None:
    """Traducción validada y guardada por ítem de Wikidata (una sola vez por texto). Nunca lanza."""
    known, value = stored_translation(qid, text)
    if known:
        return value
    if not groq.configured or in_cooldown():
        return None
    with _lock_for(f"desc:{qid}"):
        known, value = stored_translation(qid, text)
        if known:
            return value
        try:
            out = groq.structured(TRANSLATE_SYSTEM, text, "description_translation", TRANSLATE_SCHEMA)
        except GroqError as exc:
            ttl = start_cooldown(exc.retry_after) if exc.code == "rate_limited" else TTL_ERROR_S
            store.put(DESC_KIND, qid, {"source": text, "text": None, "error": exc.code}, ttl)
            return None
        translation = " ".join(str(out.get("translation") or "").split()).rstrip(".")
        problem = translation_issue(text.rstrip("."), translation)
        value = None if problem else translation[0].upper() + translation[1:] + "."
        store.put(DESC_KIND, qid, {"source": text, "text": value, "error": problem},
                  TTL_DESC_OK_S if value else TTL_FORMAT_S)
        return value
