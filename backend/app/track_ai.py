"""Interpretación musical de una canción con Groq (T2.0), a partir de fuentes recopiladas ANTES de llamar al modelo.

Qué es y qué no es:
- El modelo NO escucha el audio: solo redacta a partir de datos de MusicBrainz, Wikidata y Wikipedia.
- Nunca produce rasgos del ADN (BPM, tonalidad, energía, géneros): su texto va aparte y se rechaza si los menciona
  o si atribuye rasgos sonoros que ninguna fuente respalda.
- Sin texto descriptivo suficiente sobre la canción o su lanzamiento (Wikipedia) no se genera nada: la del artista
  solo sirve de contexto. La ficha muestra entonces solo los datos verificados.
Flujo y caducidades como las biografías (biography.py): caché persistente por MBID, candado por canción, pausa
global tras un 429 y fallos guardados con caducidad corta.
"""

from __future__ import annotations

import re
import threading
from datetime import datetime, timezone
from typing import Callable

from pydantic import BaseModel, ValidationError

from app import biography, schemas, sources, store, tracks
from app.groq_client import GroqClient, GroqError
from app.musicbrainz import WikimediaClient
from app.sources import QUOTED_RE, YEAR_RE, SourceDoc
from app.wikidata import WikidataInfo

KIND = "track_interpretation"
TTL_OK_S = 90 * 24 * 3600
TTL_INSUFFICIENT_S = 14 * 24 * 3600
TTL_REJECTED_S = 7 * 24 * 3600
TTL_ERROR_S = 3600
WORDS = (35, 115)
MAX_QUOTED = 3  # canción + lanzamiento + uno más (p. ej. la original de un remix); más sería una lista
MAX_YEARS = 2
PROMPT_VERSION = 2  # v2: exige fuentes de la canción o del lanzamiento y rechaza el relleno

SCHEMA = {
    "type": "object",
    "properties": {"interpretation": {"type": "string"}, "source_ids": {"type": "array", "items": {"type": "string"}}},
    "required": ["interpretation", "source_ids"],
    "additionalProperties": False,
}

SYSTEM = (
    "Eres editor musical de una app para aficionados a la música electrónica y DJs. Escribes en español una "
    "interpretación breve (un párrafo) de la identidad de UNA canción: qué es, en qué lanzamiento y sello aparece, "
    "su contexto de estilo o escena y cómo encaja con el sonido habitual del artista, solo si las fuentes lo dicen. "
    "Reglas obligatorias:\n"
    "1. Usa EXCLUSIVAMENTE los hechos de las FUENTES. No uses tu conocimiento propio.\n"
    "2. NO has escuchado la canción. Nunca describas cómo suena (ritmo, tempo, melodía, bajo, voces, atmósfera, "
    "energía) salvo que una fuente lo diga de ESTA canción; en ese caso parafraséalo sin exagerar.\n"
    "3. Prohibido mencionar BPM, tempo, tonalidad, escalas, porcentajes o mediciones.\n"
    "4. Las fuentes marcadas como CONTEXTO DEL ARTISTA describen al artista, no la canción: si las usas, deja claro "
    "que hablas del artista (p. ej. «en la línea del sonido que se asocia a…» solo si la fuente describe ese sonido).\n"
    "5. Un género de Wikidata del lanzamiento o del artista no es necesariamente el de la pista: dilo con prudencia.\n"
    "6. Nombra la canción entre comillas latinas «». Como mucho TRES títulos entre comillas y DOS años en total.\n"
    "7. No menciones bases de datos ni fuentes («MusicBrainz», «Wikidata», «según…»), ni recuentos técnicos.\n"
    "8. No copies frases literales: redacta un texto original. Sin valoraciones vacías («icónica», «imprescindible»).\n"
    "9. Si las fuentes no describen algo, no lo rellenes ni comentes su ausencia: escribe solo lo que sí consta. "
    "Nada de «mantiene su estilo habitual» o «encaja con su sonido» sin una fuente que lo diga de esta canción.\n"
    "Devuelve JSON con 'interpretation' y 'source_ids' (ids S1, S2… de las fuentes usadas)."
)

# Mediciones acústicas o afirmaciones de escucha: nunca en un texto que no procede del audio.
ACOUSTIC_RE = re.compile(r"\bbpm\b|pulsaciones|\btempo\b|tonalidad|\d+\s*%|\bkhz\b|\bdecibel", re.IGNORECASE)
# Notas con modo («La menor», «F# minor»), sensible a mayúsculas para no confundir «la mayor parte de…».
KEY_RE = re.compile(r"\b([A-G][#♯b♭]?|Do|Re|Mi|Fa|Sol|La|Si)\s+(sostenido\s+|bemol\s+)?(menor|mayor|minor|major)\b"
                    r"(?!\s+(parte|medida|cantidad|influencia|difusión|éxito|repercusión|de|del)\b)")
EMPHASIS_RE = re.compile(r"(?<!\w)[*_]{1,2}([^*_]+?)[*_]{1,2}(?!\w)")
LISTENING_RE = re.compile(r"al escuchar|se escucha|escuchamos|se oye|\bsuena\b|\bsonar[aá]\b|a mi juicio|en mi opinión",
                          re.IGNORECASE)
# Rasgos sonoros que solo se admiten si alguna fuente usa un término equivalente (español o inglés).
# Relleno: comentarios sobre las fuentes o continuidad de estilo afirmada sin evidencia (observado en T2.0).
FILLER_RE = re.compile(
    r"\bfuentes?\b|no (se )?(detalla|especifica|menciona|indica)|no hay (más )?(datos|información)|"
    r"estilo habitual|sonido habitual|coherencia con su|fiel a su (estilo|sonido)|mantiene (la|su) (esencia|línea|estilo)",
    re.IGNORECASE)
STATIC_CHECKS = (ACOUSTIC_RE, KEY_RE, LISTENING_RE, FILLER_RE)
DESCRIPTIVE_SCOPES = ("track", "release")  # la Wikipedia del artista sola no basta para hablar de una canción
SONIC_TERMS: dict[str, tuple[str, ...]] = {
    "hipnótic": ("hipnótic", "hypnot"), "oscur": ("oscur", "dark"), "melancól": ("melancól", "melanchol"),
    "eufóric": ("eufóric", "euphor"), "atmosféric": ("atmosfér", "atmospher"), "etére": ("etére", "ethereal"),
    "melódic": ("melódic", "melod"), "contundente": ("contundente", "punchy", "pounding"),
    "ácid": ("ácid", "acid"), "industrial": ("industrial",), "épic": ("épic", "epic"),
    "minimalista": ("minimal",), "progresiv": ("progresiv", "progressive"), "oníric": ("oníric", "dream"),
    "groove": ("groove",), "percusi": ("percusi", "percuss"), "sintetizador": ("sintetizador", "synth"),
    "bajo profundo": ("bajo profundo", "deep bass", "sub-bass", "bassline"), "vocal": ("vocal", "voz", "voice"),
}


class TrackInterpretationRecord(BaseModel):
    recording_mbid: str
    text: str | None
    source_urls: list[str]
    source_labels: list[str] = []
    source_licenses: list[str | None] = []
    generated_at: str
    model: str | None
    status: str                    # ok | insufficient_sources | rejected | error
    error_code: str | None = None
    prompt_version: int = PROMPT_VERSION


_locks: dict[str, threading.Lock] = {}
_locks_guard = threading.Lock()


def _lock_for(mbid: str) -> threading.Lock:
    with _locks_guard:
        return _locks.setdefault(mbid, threading.Lock())


def cached(mbid: str) -> TrackInterpretationRecord | None:
    raw = store.get(KIND, mbid)
    if not raw:
        return None
    try:
        record = TrackInterpretationRecord.model_validate(raw)
    except ValidationError:
        return None
    if record.prompt_version != PROMPT_VERSION:
        # Versiones anteriores: fallos y rechazos se reintentan; los textos válidos, solo si pasan las reglas actuales.
        if record.status != "ok" or not record.text or any(r.search(record.text) for r in STATIC_CHECKS):
            return None
    return record


def public(record: TrackInterpretationRecord | None) -> schemas.TrackInterpretation | None:
    if not record or record.status != "ok" or not record.text:
        return None
    refs = [schemas.SourceRef(label=label, url=url, license=lic) for label, url, lic in
            zip(record.source_labels, record.source_urls, record.source_licenses or [None] * len(record.source_urls))]
    return schemas.TrackInterpretation(text=record.text, sources=refs, generated_at=record.generated_at)


def status_for(mbid: str, groq: GroqClient) -> tuple[schemas.TrackInterpretation | None, str]:
    """Estado para la ficha sin llamar al modelo: ready, pending (se puede generar ahora), insufficient_sources
    o unavailable (sin Groq, en pausa tras un 429 o texto rechazado: la ficha queda solo con datos)."""
    record = cached(mbid)
    if record and record.status == "ok":
        return public(record), "ready"
    if record and record.status == "insufficient_sources":
        return None, "insufficient_sources"
    if record is None and groq.configured and not biography.in_cooldown():
        return None, "pending"
    return None, "unavailable"


# --- Fuentes ------------------------------------------------------------------------------------------------------
def _join(items: list[str]) -> str:
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " y " + items[-1]


def musicbrainz_facts(track: schemas.TrackResponse) -> SourceDoc:
    lines = [f"Canción: «{track.title}», de {track.artist_name}."]
    if track.version:
        lines.append(f"Versión indicada en el título: {track.version}.")
    for original in track.relations.remix_of[:1]:
        lines.append(f"Es una remezcla o edit de «{original.title}» ({original.artist_name}).")
    if track.original_release:
        r = track.original_release
        kind = {"Album": "álbum", "Single": "single", "EP": "EP"}.get(r.primary_type or "", "lanzamiento")
        when = f", {r.date[:4]}" if r.date else ""
        lines.append(f"Publicada originalmente en el {kind} «{r.title}»{when}.")
    labels = next((t.values for t in track.dna.traits if t.key == "label" and t.status == "verified"), [])
    if labels == [tracks.SELF_RELEASED]:
        lines.append("Publicada como autoedición, sin sello discográfico.")
    elif labels:
        lines.append(f"Sellos de sus lanzamientos: {_join(labels)}.")
    for credit in track.credits:
        if credit.role in ("Producción", "Remezcla", "Composición", "Voz"):
            lines.append(f"{credit.role}: {_join([a.name for a in credit.artists[:3]])}.")
    if track.relations.remix_count:
        lines.append(f"Tiene remezclas o edits de otros artistas ({track.relations.remix_count} documentadas).")
    if track.relations.dj_mix_count:
        lines.append(f"Aparece en DJ mixes publicados (al menos {track.relations.dj_mix_count}).")
    return SourceDoc("", "MusicBrainz", f"https://musicbrainz.org/recording/{track.mbid}", "CC0", " ".join(lines))


def wikidata_facts(track: schemas.TrackResponse) -> SourceDoc | None:
    parts, ref = [], None
    for trait in track.dna.traits:
        if trait.status != "community" or not trait.values or not trait.sources:
            continue
        scope = {"track": "de la canción", "release": "del lanzamiento original", "artist": "del artista (contexto)"}[trait.scope]
        parts.append(f"{trait.label} {scope}: {_join(trait.values)}.")
        ref = ref or trait.sources[0]
    if not parts or not ref:
        return None
    return SourceDoc("", "Wikidata", ref.url, "CC0", " ".join(parts))


def collect(track: schemas.TrackResponse, wiki_context: list[dict], wiki: WikimediaClient) -> tuple[list[SourceDoc], dict[str, str]]:
    """Fuentes numeradas (S1…) y su ámbito («canción», «lanzamiento», «artista») para marcar el contexto."""
    docs: list[SourceDoc | None] = [musicbrainz_facts(track), wikidata_facts(track)]
    scopes: dict[int, str] = {}
    for entry in wiki_context:  # orden: canción, lanzamiento, artista
        sites = entry.get("sites") or {}
        if not sites:
            continue
        doc = sources.wikipedia_summary(wiki, WikidataInfo(qid=entry.get("qid"), wikipedia=sites))
        if doc:
            scopes[id(doc)] = entry.get("scope") or ""
            docs.append(doc)
    numbered = sources.number(docs)
    return numbered, {d.id: scopes.get(id(d), "") for d in numbered}


def sufficient(docs: list[SourceDoc], scopes: dict[str, str]) -> bool:
    """Texto descriptivo (Wikipedia) sobre la canción o su lanzamiento; el del artista solo sirve de contexto."""
    return sources.sufficient([d for d in docs if scopes.get(d.id) in DESCRIPTIVE_SCOPES])


def _user_prompt(track: schemas.TrackResponse, docs: list[SourceDoc], scopes: dict[str, str]) -> str:
    def header(d: SourceDoc) -> str:
        note = {"artist": " — CONTEXTO DEL ARTISTA (no describe esta canción)",
                "release": " — sobre el lanzamiento que la contiene"}.get(scopes.get(d.id, ""), "")
        return f"[{d.id}] {d.label} ({d.url}){note}"
    blocks = "\n\n".join(f"{header(d)}\n{d.text}" for d in docs)
    return (f"Canción: «{track.title}» de {track.artist_name}\n\nFUENTES:\n{blocks}\n\n"
            f"Escribe la interpretación de «{track.title}». Extensión: entre {WORDS[0] + 10} y {WORDS[1] - 15} palabras.")


def validate(text: str, track: schemas.TrackResponse, docs: list[SourceDoc]) -> str | None:
    words = len(text.split())
    if not WORDS[0] <= words <= WORDS[1]:
        return f"longitud fuera de rango ({words} palabras)"
    if ACOUSTIC_RE.search(text) or KEY_RE.search(text):
        return "menciona mediciones acústicas"
    if LISTENING_RE.search(text):
        return "finge haber escuchado la canción"
    if FILLER_RE.search(text):
        return "relleno sin respaldo"
    if biography.BANNED.search(text):
        return "menciona fuentes, registros o recuentos"
    if len(QUOTED_RE.findall(text)) > MAX_QUOTED:
        return "enumera títulos"
    if len({m.group(0) for m in YEAR_RE.finditer(text)}) > MAX_YEARS:
        return "enumera años"
    folded = text.casefold()
    base = re.sub(r"\s*[\(\[].*$", "", track.title).strip().casefold()
    if base and base not in folded:
        return "no nombra la canción"
    corpus = " ".join(d.text for d in docs).casefold()
    for year in {m.group(0) for m in YEAR_RE.finditer(text)}:
        if year not in corpus:
            return f"año sin respaldo ({year})"
    for m in QUOTED_RE.finditer(text):
        quoted = (m.group(1) or m.group(2) or "").strip().casefold()
        if quoted and quoted not in corpus:
            return "título entre comillas sin respaldo"
    for term, equivalents in SONIC_TERMS.items():
        if term in folded and not any(e in corpus for e in equivalents):
            return f"rasgo sonoro sin respaldo ({term})"
    return None


def generate(track: schemas.TrackResponse, collect_docs: Callable[[], tuple[list[SourceDoc], dict[str, str]]],
             groq: GroqClient,
             now: Callable[[], str] = lambda: datetime.now(timezone.utc).isoformat(timespec="seconds")
             ) -> TrackInterpretationRecord:
    """Interpretación desde caché o generada. Nunca lanza: los fallos se devuelven con su estado."""
    mbid = track.mbid
    hit = cached(mbid)
    if hit:
        return hit
    with _lock_for(mbid):
        hit = cached(mbid)
        if hit:
            return hit

        def record(status: str, text: str | None = None, used: list[SourceDoc] | None = None,
                   ttl: float = TTL_ERROR_S, error_code: str | None = None) -> TrackInterpretationRecord:
            used = used or []
            rec = TrackInterpretationRecord(
                recording_mbid=mbid, text=text, source_urls=[d.url for d in used], source_labels=[d.label for d in used],
                source_licenses=[d.license for d in used], generated_at=now(), model=groq.model if text else None,
                status=status, error_code=error_code)
            store.put(KIND, mbid, rec.model_dump(), ttl)
            return rec

        def transient(code: str) -> TrackInterpretationRecord:  # no se guarda: se reintenta en la próxima visita
            return TrackInterpretationRecord(recording_mbid=mbid, text=None, source_urls=[], generated_at=now(),
                                             model=None, status="error", error_code=code)

        if not groq.configured:
            return transient("not_configured")
        if biography.in_cooldown():
            return transient("cooldown")
        docs, scopes = collect_docs()
        if not sufficient(docs, scopes):
            return record("insufficient_sources", ttl=TTL_INSUFFICIENT_S)
        try:
            out = groq.structured(SYSTEM, _user_prompt(track, docs, scopes), "track_interpretation", SCHEMA, max_tokens=2000)
        except GroqError as exc:
            if exc.code == "rate_limited":
                return record("error", ttl=biography.start_cooldown(exc.retry_after), error_code=exc.code)
            return record("error", ttl=TTL_ERROR_S, error_code=exc.code)
        text = " ".join(str(out.get("interpretation") or "").split())
        text = EMPHASIS_RE.sub(r"«\1»", text)  # cursivas Markdown (*título*) → comillas latinas
        refs = {d.id: d for d in docs}
        ids = [i for i in out.get("source_ids") or [] if isinstance(i, str)]
        used = [refs[i] for i in dict.fromkeys(ids) if i in refs]
        if not used or any(i not in refs for i in ids):
            return record("rejected", ttl=TTL_REJECTED_S, error_code="unknown_source")
        problem = validate(text, track, docs)
        if problem:
            return record("rejected", ttl=TTL_REJECTED_S, error_code=problem[:60])
        return record("ok", text, used, ttl=TTL_OK_S)
