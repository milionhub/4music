# TrackDNA V5.5 — Cobertura musical real

Fecha: 2026-10-21. Piloto reproducible: `backend/eval/pilot_v55.py`. Resultados en `eval/pilot_v55_baseline.json` (antes) y `eval/pilot_v55_results.json` (después); las respuestas externas están en `eval/pilot_v55_cache.json`.

## 1. Método

- **Identidad fijada a mano** por MBID: título, crédito, versión y duración.
  - De «Music Sounds Better With You» hay radio edit, 12" club mix y remixes: se usa la **12" club mix** (`6e8b1a97`), la misma de las fases anteriores.
  - De «Dirty Cash» y «Crazy» se usa la **original**, no la extended.
- **Cruces solo por identificadores** que documenta MusicBrainz: ISRC, URL de la grabación o de sus ediciones propias, y enlace del artista a Discogs. Nunca por la primera coincidencia de un nombre.
- **Verificación de versión por duración:** cualquier candidato de otra fuente debe durar lo mismo que la grabación (±3 %).

## 2. Fuentes

| Fuente | Estado | Evidencia y motivo |
|---|---|---|
| MusicBrainz: géneros de grabación y de release-group | **Ya integrada** (sin cambios) | Desire y Crazy no tienen géneros ni etiquetas en grabación, release ni release-group (consultado el 2026-10-21). En Hoodlum, la grabación dice *house* y el grupo *techno*: no se traslada uno al otro. |
| MusicBrainz → enlaces Discogs (release y master) | Medida | Los releases enlazados (Lovelee, MSBWY, Dirty Cash) dan los **mismos estilos** que MusicBrainz: ganancia 0. **Falso positivo detectado:** la edición de 2024 de Dirty Cash apunta al master de **1989** (la canción original de Adventures of Stevie V: *Breakbeat, Hip-House*). Regla: nunca estilos de un master salvo que MusicBrainz enlace ese master al release-group, y nunca de bandas sonoras (Double C → master del álbum F1: *Alt-Pop, Country*). |
| Discogs por discografía del artista (artista enlazado por MusicBrainz) | Medida (API pública sin token, solo investigación) | **Breather:** la edición coincide al segundo (7:45) y confirma *Deep House/House* (ya lo teníamos). **Desire:** Discogs solo tiene la edición de **6:14**; la de MusicBrainz dura **2:52**, así que es **otra versión** y se rechaza. **Crazy:** vinilo de *Withness* (NO ART, 2026), con estilos de álbum *House, Deep House, Breaks* y sin duración: **confianza media**. **Playground** no aparece en la discografía de Arapu. Ganancia: +1 grabación de MusicBrainz, de confianza media. |
| Volcado CC0 de *releases* de Discogs | **No descargado: requiere autorización** | 11,3 GB y 2–3 h de proceso; índice electrónico estimado en 2–5 GB (fase 1.3B). Es la única vía legítima a estilos por edición sin las condiciones de la API (en disco hay 211 GB libres). |
| **ReccoBeats** (nueva) | **Aceptada solo para BPM** | Sin clave, «free to use for both personal and commercial projects». Métricas de análisis propio; metadatos de Spotify, que no usamos. **Acepta el ISRC como id**, que identifica la grabación exacta. Tempo frente a AcousticBrainz: **6/7 dentro de ±1 BPM**, más un error de octava (Nabi: 196 frente a 98). Tonalidad: **solo 2/6 coinciden**; el resto, a una quinta o en el modo relativo (MSBWY: Reb mayor frente a Sib menor; Hoodlum: Mib mayor frente a Sol# menor). **La tonalidad se descarta.** |
| AcousticBrainz | Ya integrada, prioritaria | Datos hasta 2022. Se mantiene por delante de ReccoBeats. |
| Deezer | Solo evidencia, **no integrable** | Condiciones «strictly limited for a non-commercial purpose». BPM ≠ 0 solo en 1 de 8 (Hoodlum). Confirma que Playground y Vinotinto existen fuera de MusicBrainz, con su ISRC. |
| GetSongBPM | No evaluada | Requiere cuenta y clave (no se piden credenciales); su web devuelve 403 a clientes automáticos. Sigue pendiente. |
| Spotify, Beatport, Musicstax, Tunebat | Descartadas (sin cambios) | Sin API abierta o con scraping prohibido. |

## 3. Piloto: antes y después

C = confirmado en la grabación · L = del lanzamiento · E = estimado por análisis · — = desconocido.

| # | Canción | Catálogo e identidad | Género | Estilo | BPM antes → después | Tonalidad (Camelot) | Sello | Año |
|---|---|---|---|---|---|---|---|---|
| 1 | Desire — Chris Stussy | MB `9d619150`, single de 2:52 | — | — | — → **134 E** (ReccoBeats, ISRC QM4TW2437510, 171 953 ms exactos) | — | — (Discogs: CSS (4), pero en la edición de 6:14) | 2024 |
| 2 | Double C — PAWSA | MB `df73a61d` | — (el *Pop* de la banda sonora se excluye) | — | — → **129 E** (ISRC USAT22503038) | — | — | 2025 |
| 3 | Hoodlum — Traumer | MB `98e34bc2`, original mix | House C | — | 123 E (AB) | Sol# menor (1A) E (AB) | Desolat | 2014 |
| 4 | Lovelee Dae — Blaze | MB `8edae321` | House L | Deep House L | 124 E (AB) | — | Urban Tracks · Classic | 1997 |
| 5 | Music Sounds Better With You — Stardust | MB `6e8b1a97`, 12" club mix | House C | Electro, French House C | 124 E (AB) | Sib menor (3A) E (AB) | Virgin · Roulé | 1998 |
| 6 | Dirty Cash (Money Talks) — PAWSA | MB `f2399817`, original | House C | — | — → **132 E** (ISRC NLML62400170, ±0,4 %) | — | Altra Moda Music | 2024 |
| 7 | Crazy — ANOTR | MB `4358ddcc`, original | — (Discogs: House/Deep House/Breaks del álbum, confianza media: no integrado) | — | — (ReccoBeats no la tiene) | — | NO ART | 2026 |
| 8 | Breather — Chris Stussy | MB `e0ee17b8` | House L | Deep House L (Discogs lo confirma) | — (sin ISRC en MB) | — | Up the Stuss | 2021 |
| 9 | Playground — Arapu | **Ausente en MB**; existe en Deezer (ISRC GBKQU2654262) | — | — | — | — | — | — |
| 10 | Vinotinto — Luciano | **Ausente en MB**; Discogs release 29565955, 9:19, *From The South* FTSR001 | (Tech House L en Discogs, fuera de MB) | — | — (el ISRC de Deezer corresponde a una pista de **2:23**, otra versión: descartado) | — | — | 2022 |

Cobertura sobre las 8 grabaciones de MusicBrainz:

| Campo | Antes | Después |
|---|---|---|
| Género (sin artista ni banda sonora) | 5/8 | 5/8 |
| Estilo específico | 3/8 | 3/8 |
| **BPM** | **3/8** | **6/8** |
| Tonalidad y Camelot | 2/8 | 2/8 |
| Sello | 6/8 | 6/8 |
| Año | 8/8 | 8/8 |
| Catálogo (10 canciones) | 8/10 | 8/10 |

## 4. Implementado

- **`backend/app/reccobeats.py`:** tempo por ISRC, aceptado solo si el ISRC es de la grabación y la duración coincide (±3 %). Si hay varias ediciones válidas, deben concordar (±2 %). Solo valores entre 70 y 180 BPM; fuera de ese margen no se corrige la octava, se descarta. **Nunca se publica la tonalidad.**
- **`api._measured_dna`:** prioridad AcousticBrainz > ReccoBeats. ReccoBeats solo se consulta si falta el tempo. El rasgo `bpm` queda como `measured`, con procedencia «ReccoBeats» y detalle; la app ya lo muestra como «estimado».
- **Sin cambios** en el contrato de la API, en los MBID, en la app móvil ni en el diseño.

## 5. Rendimiento

- **Peticiones:** 2 por grabación como máximo (pistas y audio-features), solo la primera vez y solo si AcousticBrainz no tiene el tempo. Si no hay pistas, solo 1.
- **Caché:** 90 días con dato y 30 sin él. Los fallos de red no se guardan.
- **Latencia:** el primer acceso añadió de 1,1 a 4,4 s en el piloto; los siguientes salen de la caché. Tiempo máximo de 4 s por petición. Un fallo deja el ADN como estaba.
- **Disco:** unos cientos de bytes por grabación.

## 6. Propuestas para la siguiente fase (no ejecutadas)

### Índice compacto de *releases* de Discogs (requiere autorización: 11,3 GB)

- **Una sola pasada** en flujo por el `.gz`, sin guardarlo descomprimido. Solo los lanzamientos `Electronic`, con: id, master_id, título, fecha, sellos y catálogo, ids de los artistas principales, estilos y tracklist (posición, título y duración).
- **Correspondencias:**
  - Alta: release enlazado por MusicBrainz, o artista enlazado + título de pista + duración ±3 %.
  - Media: artista + título de pista + sello/catálogo o título del lanzamiento + año, sin duración.
  - Sin artista enlazado: ninguna.
- **Salida:** estilos marcados como `scope="release"` y nunca como análisis del audio.
- **Coste:** 2–3 h al mes. El índice ocuparía 2–5 GB, por lo que conviene un subconjunto limitado a artistas enlazados desde MusicBrainz.
- **Beneficio esperado:** el piloto solo demuestra +1 de 8. Merece la pena si el objetivo es el catálogo underground amplio, no por estas 10 canciones.

### Canciones fuera de MusicBrainz

- **Identidad canónica propia, sin MBID inventado:** `isrc:<ISRC>` cuando haya un ISRC verificado y, si no, `discogs:<release>:<posición>`.
- **Ruta nueva:** `GET /v1/tracks/ext/{id}`, con procedencia por campo y el mismo contrato de `TrackResponse`. Exige campos opcionales y `mbid` nulo, así que es un cambio de contrato.
- **App:** una ruta aparte; los Guardados se mantienen por MBID. Se migran solo cuando una canción externa aparece en MusicBrainz, por ISRC.
- **Riesgo demostrado:** el ISRC de Vinotinto en Deezer es una edición de 2:23, distinta de la de 9:19 de Discogs. La versión debe confirmarse siempre por duración.

## 7. V5.7 — Enriquecimiento del ADN (2026-10-21)

Piloto: `backend/eval/pilot_v57.py` (línea base y resultado en `eval/pilot_v57_*.json`, fuera de Git). 8 canciones con las identidades ya fijadas.

### Evaluado y descartado (sin ganancia verificable)

- **Enlaces MusicBrainz → Discogs (release):** Lovelee Dae, MSBWY y Dirty Cash dan los mismos estilos que MusicBrainz. Desire y Crazy no tienen enlace.
- **Artista enlazado + título + duración:**
  - Hoodlum está en el *Dedust EP* (Desolat, release 5925531): 8 canciones, sin duraciones y con *Techno, House, Tech House*. No hay un estilo atribuible a la pista.
  - Crazy está en el LP *Withness* (38632116): sin duraciones, con estilos de álbum y crédito «ANOTR, 3ddy».
  - Desire solo tiene la edición de 6:14.
  - Ninguna correspondencia de confianza alta: **no se integra** en la ruta interactiva, porque añadiría peticiones a Discogs, con la regla de las 6 h, sin ningún dato nuevo.
- **BPM de fichas externas:** Vinotinto y You Got The Groove no tienen ISRC en Discogs, y el de Deezer de Vinotinto es otra versión. Un ISRC tomado de los metadatos de ReccoBeats no es verificable de forma independiente: BPM desconocido.
- **Tonalidad:** sin evidencia nueva. ReccoBeats sigue descartado.

### Implementado

- **`tracks.release_genre_values`** (regla única para MusicBrainz y Discogs):
  - Nunca el género de un recopilatorio, DJ mix, mixtape o banda sonora, ahora también en la API, no solo en la app.
  - En un lanzamiento de varias canciones con géneros de familias distintas no se atribuye ninguno concreto, solo el amplio si consta.
  - Misma familia o una sola canción: se conservan familia y estilo.
- **Fichas de Discogs:** usan el normalizador de MusicBrainz (`genre_values`): *Tech House* pasa a mostrarse como «House · Tech House», en lugar de «Electronic · Tech House».
- `TRACK_CONTRACT_VERSION` 6: las fichas en caché se reconstruyen una vez, en la siguiente visita.

### Antes → después

| Canción | Género / estilo | BPM | Tonalidad | Cambio |
|---|---|---|---|---|
| Desire | — → — | 134 E | — | No |
| Double C | Pop (banda sonora, release) → **—** | 129 E | — | **Corrección** |
| Dirty Cash | House C | 132 E | — | No |
| Crazy | — → — | — | — | No |
| Hoodlum | House C | 123 E | 1A E | No |
| Lovelee Dae | House · Deep House L | 124 E | — | No |
| Vinotinto (Discogs) | Electronic · Tech House → House · Tech House L | — | — | Normalización |
| You Got The Groove (Discogs) | Electronic · Minimal Techno → Techno · Minimal Techno L | — | — | Normalización |

Cobertura: género 5/8 (la API daba 6/8 contando el «Pop» erróneo de Double C, que la app ya ocultaba), BPM 5/8 y tonalidad 1/8, sin cambios. Un error corregido (Double C). Las dos fichas externas ganan la familia, pero eso es normalización y no se cuenta como cobertura.

**Limitación conocida:** `genre_values` toma como familia la del primer estilo. Con estilos de familias distintas en una sola canción (p. ej. *Minimal, Tech House*), el segundo se presenta como estilo de la primera familia. Es el comportamiento de MusicBrainz desde V5.2 y no se ha cambiado para no alterar fichas aprobadas.
