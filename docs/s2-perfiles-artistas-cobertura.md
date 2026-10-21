# Sesión 2 — Perfiles de artistas: cobertura de fuentes, permisos y cambios

Fecha: 2026-10-19. Ámbito: flujo de perfiles de artista (identidad, hechos, biografía, foto y géneros). No es una auditoría general.

## 1. Por qué faltaban hechos importantes (auditoría del pipeline v7)

Flujo: `api.artist_biography` → `collect()` (MusicBrainz, Wikidata, Wikipedia, web oficial) → `facts.extract/select` → Groq → `biography.validate` → SQLite.

| # | Pérdida | Dónde | Efecto comprobado |
|---|---|---|---|
| P1 | **Wikipedia recortada a 1800 caracteres** (`sources._clip`) aunque al modelo solo llegan los hechos seleccionados | `sources.wikipedia_summary(full_article=True)` | Capriati: se perdían Metamorfosi, Redimension, Ibiza y Amnesia (artículo de 4685 car.). Carola (es): Zenit, Question y Plus 8. Bicep: Chroma |
| P2 | **Solo un idioma** (español si existe, si no inglés) | idem | Carola: el artículo en español (4508 car.) no menciona Music On ni Amnesia; el inglés (838 car.), sí |
| P3 | **Relaciones de MusicBrainz no pedidas**: `inc=aliases+url-rels+artist-rels`, sin sellos ni eventos | `MusicBrainzClient.artist` | Se ignoraba «label founder» (Capriati → REDIMENSION; Jones → Hot Creations; Carola → 2M, Design Music, Question, Zenit), los eventos y los B2B registrados como evento (Josh Baker b2b Max Dean) |
| P4 | **Wikidata solo por enlace MB o P434** | `wikidata.resolve` | ANOTR tiene ítem (Q139681094) sin P434: no se encontraba |
| P5 | **Clasificación gruesa**: «proyecto propio» mezclaba sello, fiesta y tienda; sin «escena», «proyecto paralelo» ni «festival»; selección por orden de aparición | `facts.py` | Se elegía la primera frase de cada tipo, no la más representativa |
| P6 | **Géneros: Wikidata P136 tal cual** | `profile.styles` | Jones: «música electrónica» y «pop» |
| P7 | Validador sin control de **sonido, géneros, gentilicios ni relevancia** | `biography.validate` | Detectado en la prueba real con Groq (§5): textos con sonido inventado, «deep house y soul», «el sueco Adam Beyer», «su propio club» |

No se confundían fundar y publicar: la etiqueta «Sellos que han publicado su música (no implica que los haya fundado)» y las reglas de `CLAIMS` ya lo impedían. El contenido en inglés se usa como dato (frases literales) y el modelo redacta en español.

## 2. Cobertura de los 10 artistas (piloto sin Groq, datos reales del 2026-10-19)

Hechos = tamaño del expediente v8 (todo lo extraído). «Bio» = si hay texto descriptivo suficiente para una presentación editorial.

| Artista | Fuentes disponibles | Hechos relevantes obtenidos (v8) | Falta | Bio | Por qué faltaba antes |
|---|---|---|---|---|---|
| Joseph Capriati | MB (label founder), Wikidata, Wikipedia en, foto P18 | 46 hechos: Redimension (Wikipedia + MB), fiesta y residencia Metamorfosi en Amnesia (Ibiza), Drumcode, colaboración con Adam Beyer, Monegros y Sunwaves | Descripción del sonido: la fuente apenas la tiene | Sí, 2 párrafos | P1 y P3 |
| Jamie Jones | MB (label founder, member of Hot Natured, alias J-Mode, eventos), Wikidata, Wikipedia en (815 car.) | 23: Hot Creations (dirige; fundación según MB), Hot Natured, fiesta Paradise en DC10 y después en Amnesia, The House of Hot, RA top DJ 2011 | **B2B con The Martinez Brothers: no aparece en ninguna fuente abierta comprobada** (ni en Wikipedia ni en los eventos de MB). Sonido | Sí | P3 y P6 |
| Marco Carola | MB (4 sellos fundados, alias, grupos), Wikidata, Wikipedia es + en, foto P18 | 45: Music On, residencias en Amnesia, Design Music, Zenit, Question, giro al minimal en 2004 | — | Sí | P1, P2 y P3 |
| Paco Osuna | Wikidata (P434), Wikipedia es, foto P18 | 24: residencia en Amnesia (1999), Shake Records / Mind Shake, inicios en Valencia, Vicious Awards | Géneros: no hay P136 ni género en la frase de presentación | Sí | — (el registro anterior estaba rechazado por copia) |
| Priku | Solo MB: sin tipo, desambiguación «Adrian Niculae, Techno Producer», enlace a Discogs | 1 | Todo: escena minimal rumana, Sunrise, Sunwaves y Atipic **no están en ninguna fuente abierta comprobada** | No | Sin Wikidata (ni por P434 ni por Discogs) ni Wikipedia |
| ANOTR | MB (grupo, Ámsterdam, eventos), **Wikidata vía ID de Discogs** (nuevo) | 7: «Dutch house duo», género house, evento NoArt | NO ART como sello o fiesta propia (MB solo registra «actuó en NoArt»), funk/soul, integrantes | No | P4 y sin Wikipedia |
| Traumer | MB (París, web oficial, Discogs) | 4: house/techno; publica en GETTRAUM | Que get-traum sea su sello: **solo consta que publica en él**, no se afirma. Evolución sonora | No | Sin Wikidata ni Wikipedia; la web oficial no da texto |
| Cloonee | MB, Wikidata (tech house, «musician») | 7 | Todo lo biográfico | No | Sin Wikipedia; la web oficial no da texto |
| Bicep | MB (integrantes, eventos, 2 webs oficiales), Wikidata, Wikipedia en | 39: blog y sello Feel My Bicep, Ninja Tune, Isles, UK Albums Chart, premio de DJ Mag, formación en 2009 en Londres, Belfast | — | Sí | P1 (Chroma) |
| Josh Baker | MB (eventos: b2b con Max Dean), Wikidata (P434), Wikipedia en | 24: cofundador de You&Me y de Hide & Seek, residencia en Amnesia en 2026, B2B en Coachella, premio de DJ Mag | Géneros | Sí | P1 (artículo de 2131 car.) |

**Resultado:** 6 de 10 tienen material para una biografía editorial. Los otros 4 (Priku, ANOTR, Traumer y Cloonee) siguen sin texto descriptivo en fuentes abiertas, y no se rellenan.

## 3. Fuentes comprobadas y permisos

| Fuente | Uso en el perfil | Licencia / condición | Estado |
|---|---|---|---|
| MusicBrainz, datos centrales: artistas, sellos, eventos, **relaciones**, URL y comentarios de desambiguación | Identidad, sellos fundados, alias, B2B, eventos y desambiguación para géneros | **CC0**: verificado hoy en musicbrainz.org/doc/MusicBrainz_Database | Integrado |
| MusicBrainz, tags y **asociaciones de géneros** | — | **CC BY-NC-SA 3.0** (suplementario): verificado hoy | **Excluido** (incompatible con uso comercial) |
| Wikidata | Identidad, géneros P136, P18 e ID de Discogs (P1953) | CC0 | Integrado |
| Wikipedia (es/en) | Frases como hechos; el texto final es una redacción propia, con control de copia (12 palabras) y la fuente atribuida | CC BY-SA 4.0. Parafrasear no elimina la obligación: se conserva la atribución en las fuentes de la ficha | Integrado |
| Wikimedia Commons | Fotos (P18 y, nuevo, archivos que «representan» (P180) solo a ese artista) | Licencia **por archivo**: solo CC0/PD/CC BY/CC BY-SA con autor. Los datos estructurados se usan solo para identificar el archivo | Integrado |
| Discogs | Solo el **ID** que MusicBrainz documenta en su URL (dato CC0 de MB). No se consulta Discogs | — | Integrado (solo el ID) |
| Web oficial | Solo la URL «official homepage» de MB, una página, respetando robots.txt | Sin licencia de reutilización: solo hechos breves, nunca texto copiado | Integrado; 5 de 6 webs probadas no dieron texto (JS o bloqueo) |
| Volcados de Discogs (géneros/estilos) | — | CC0 según data.discogs.com (`docs/fase-1-discogs-dumps.md`); pendientes legales anotados allí | Candidata, no integrada |
| Resident Advisor, Bandcamp, Beatport, Spotify, Instagram, webs de clubes y medios | — | **No verificado** en esta sesión. Sin API pública conocida para estos datos o con términos restrictivos | **No integrar** |
| Last.fm | — | No comercial y con aprobación previa (`docs/t2-1-auditoria-fuentes-musicales.md`) | No integrar |

## 4. Cambios implementados

- **Recopilación** (`sources.py`, `musicbrainz.py`): artículos completos de Wikipedia en español e inglés (hasta 12 000 car. cada uno; el límite de 1800 se mantiene para TrackDNA); `inc=label-rels+event-rels` en la misma petición del artista; nuevo documento «MusicBrainz (relaciones)».
- **Identidad** (`wikidata.py`): cruce por ID de Discogs cuando ningún ítem declara el MBID. Requisitos: un único ítem, que declare ese ID y que no declare otro MBID.
- **Expediente** (`facts.py`): categorías identidad, estilo, origen, inicios, sello propio, fiesta propia, proyecto propio, residencia, proyecto paralelo, colaboración, escena, hito, festival, música destacada y publica en. Cada hecho guarda entidades, periodo y base («relación estructurada» o «frase de la fuente»). Se descartan residencias geográficas, «The Residency» (programa de radio) y frases que dependen de la anterior. El expediente completo se guarda en SQLite (`kind = dossier`).
- **Selección**: relevancia por categoría, más peso a las entidades que señalan las relaciones estructuradas y a las que más se repiten en las fuentes. Sin hechos redundantes (mismas entidades o >50 % de palabras) y un solo dato de origen. Sin medida de popularidad.
- **Groq** (`biography.py`, prompt v8): presentación en 2 párrafos (100–150 palabras) o un texto breve si hay pocos hechos. Se indica al modelo cuándo no hay hechos de sonido y se le dan equivalencias para evitar calcos («label» → sello).
- **Validador v5**: géneros y gentilicios deben estar en los hechos; las descripciones del sonido, la relevancia o influencia y el «club propio» necesitan respaldo. «Fundó» se acepta con la relación «label founder» de MB. Se suman unos pocos clichés (revolucionario, «uno de los más influyentes»…).
- **Caché**: `PROMPT_VERSION 8` y `VALIDATOR_VERSION 5`. Renovación progresiva con el mecanismo existente: la biografía válida anterior se muestra como heredada hasta que hay una nueva válida. Fotos: `IMAGE_RESOLVER_VERSION 2` vuelve a resolver una vez **solo** los «sin foto»; las fotos encontradas no se tocan.
- **Géneros** (`profile.styles`): primero Wikidata específico; «pop» y similares solo si el texto lo confirma; después los estilos escritos en la desambiguación de MB (CC0) y en la primera frase de Wikipedia (vocabulario cerrado); el genérico, solo si no hay nada mejor. Cada género lleva su fuente.
- **Identidad en la ficha**: sellos fundados, proyectos e integrantes (relaciones explícitas de MB).

## 5. Limitaciones abiertas

1. **Fotos: sin mejora en la muestra.** Siguen 3 de 10 (Capriati, Carola, Osuna). Jones, ANOTR, Bicep, Josh Baker y Cloonee no tienen P18 ni archivos con P180 en Commons. Priku y Traumer no tienen ítem. El código nuevo solo ayudará cuando Commons o Wikidata tengan la foto. La vía legal restante es el catálogo editorial con permiso documentado.
2. **Artistas sin Wikipedia** (Priku, ANOTR, Traumer, Cloonee): sin biografía editorial. Las fuentes que podrían cubrirlos (RA, prensa, webs de clubes) no tienen una vía de reutilización verificada.
3. **Géneros**: Paco Osuna y Josh Baker sin géneros, y Bicep solo con «jazz house» (Wikidata). Una fuente CC0 más rica serían los volcados de Discogs, ya evaluados pero no integrados.
4. **Datos de MB**: algunos dudosos, como «BDB» como integrante de Bicep. Se muestran tal como los declara la fuente.
5. **Prueba real con Groq** (2 llamadas, Capriati y Jones): con el validador v4 ambas pasaron, pero contenían invenciones. Por eso se añadió el v5, que las rechaza (comprobado sin red). Se restauró la biografía v7 previa de esos dos artistas. **La calidad final del prompt v8 con el validador v5 no se ha medido con Groq**: queda para la próxima visita a cada ficha.
