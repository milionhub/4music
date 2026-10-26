# V6 — Fuentes de uso no comercial

Fecha: 2026-10-25. El proyecto es una **demo de portfolio sin ánimo de lucro**. Hasta V5 se descartaban las fuentes cuyas
condiciones solo permiten uso no comercial (Deezer, Last.fm, tags de MusicBrainz, AcoustID…), aunque eran las que más
cobertura aportaban al underground. V6 las incorpora **detrás de un único interruptor**, con su procedencia visible.

## 1. Interruptor

- `DATA_USE` en `backend/.env` (`config.noncommercial_sources()`):
  - `noncommercial` (por defecto): fuentes no comerciales activas.
  - `commercial`: ninguna petición a esas fuentes y no se sirve nada que se haya guardado antes (las fotos de Deezer en
    caché se ignoran y se vuelven a resolver sin ellas).
- Si el proyecto pasara a ser comercial, basta con `DATA_USE=commercial`; los datos de licencia libre (CC0, Commons) no
  cambian.

## 2. Qué sigue fuera, aunque sea no comercial

El límite ya no es el uso comercial, sino las condiciones de cada servicio y los controles de acceso:

- Beatport (API solo para socios; usar el client ID de su documentación sería eludir el acceso).
- Scraping de Tunebat o Musicstax, o esquivar sus 403.
- *audio-features* de Spotify (cerrado a apps nuevas desde 2024).
- Descargar audio de YouTube o SoundCloud, o **guardar en local el audio de Deezer** (prohibido expresamente en sus
  guidelines: «Local Storage/Offline Storage of audio data is strictly forbidden»). Esto condiciona V6.2.

## 3. Condiciones de Deezer (leídas el 2026-10-25)

- https://developers.deezer.com/termsofuse: «the use of the Services is strictly limited for a non-commercial purpose».
  Las fotos, imágenes y biografías pertenecen a Deezer o a sus titulares (sección VII). No hay ninguna cláusula
  específica sobre mostrar imágenes de la API.
- https://developers.deezer.com/guidelines: solo extractos de 30 s accesibles al usuario y nunca audio guardado en local.
- Las fotos se muestran como dato de Deezer, **sin licencia libre**: crédito «Foto · Deezer», con enlace a la ficha del
  artista en Deezer y la licencia «© titulares de derechos · Deezer API (uso no comercial)» en «Fuentes».

## 4. V6.0 — Fotos de artista

### Prioridad (sin cambios en las tres primeras)

1. Catálogo editorial (permiso documentado).
2. Wikimedia Commons con licencia libre (relación «image» de MusicBrainz, P18 de Wikidata, P180 de Commons).
3. **Deezer**, solo si no hay ninguna de las anteriores.

### Identidad en Deezer (`app/deezer.py`): nunca por la primera coincidencia de un nombre

1. Enlace de MusicBrainz a `deezer.com/artist/<id>` (si hay un único ID).
2. **ISRC**: grabaciones acreditadas solo a ese artista → `track/isrc:<ISRC>` → artista principal. Dos ISRC que coinciden,
   o uno si además coincide el nombre. Así sobrevive a los cambios de nombre: Chris Stassy figura en Deezer como
   «CHRIS STASSY», y por nombre no se encontraría.
3. **Nombre exacto** (o alias de MusicBrainz) **y discografía en común**: al menos dos títulos de MusicBrainz en Deezer
   (uno si MusicBrainz solo tiene uno). Si pasan dos candidatos, ninguno.

La silueta genérica de Deezer (hash vacío) no cuenta como foto. Peticiones: 1–4 a Deezer por artista y solo la primera
vez (caché propia de 30 días con ID y 7 sin él). Las grabaciones de MusicBrainz ya traen el ISRC en la misma petición
de la ficha (`inc=artist-credits+isrcs`), así que no hay peticiones extra a MusicBrainz por el ISRC; la discografía solo
se pide en el tercer paso. `IMAGE_RESOLVER_VERSION` 3: los «sin foto» guardados se resuelven de nuevo una vez.

### App

- La ficha de artista muestra la foto (antes era solo tipográfica): foto arriba y, debajo, una banda con la paleta del
  artista y el nombre. Sin foto verificable, o si no carga, el cartel tipográfico de siempre.
- Crédito breve sobre la foto y completo en «Fuentes». La vista rápida de Carteles acepta también las fotos de Deezer.

### Piloto (`backend/eval/pilot_v6_images.py`, 2026-10-25)

Todos los MBID de la caché de fotos real (168), resueltos de nuevo con las fuentes reales en un almacén temporal.

| Conjunto | Con foto antes (Commons/editorial) | Con foto después | Vía Deezer |
|---|---|---|---|
| **Artistas cuya ficha se ha abierto** (34, con biografía, historias o expediente en caché) | 19 (56 %) | **31 (91 %)** | Jamie Jones, Bicep, PAWSA, Traumer, Arapu, ANOTR, 3DDY, Franky Rizardo, Cloonee, Josh Baker, East End Dubs, Arnold Jarvis |
| Todos los MBID de la caché (168, con muchos homónimos que entraron por Carteles: 4 «Josh Baker», 3 «Tini»…) | 58 (35 %) | **118 (70 %)** | 60: 37 por enlace de MusicBrainz, 7 por ISRC, 16 por discografía |

- Sin foto entre los visitados: Inner City (fallo temporal; tiene enlace a Deezer), Priku y Pig&Dan.
- Revisión manual de los 23 cruces por ISRC o discografía: ninguno erróneo. Dos homónimos no electrónicos (*Paw*, banda
  de rock de EE. UU., y *TraumeR*, de metal) se cruzan con su ficha correcta de Deezer, porque la discografía coincide.
- Corregido durante el piloto: Stardust tiene **dos** fichas de Deezer enlazadas («Daft Punk - Stardust», sin foto, y
  «Stardust»). Ahora se elige la que tiene foto y más seguidores, en lugar de descartar las dos.

## 5. V6.1 — TrackDNA con Deezer

### Misma grabación (`deezer.track_match`)

- Solo por un ISRC de la grabación y con la misma duración (±3 %, mínimo 1 s porque Deezer redondea a segundos). Sin
  ISRC o sin duración no se pregunta.
- **Extracto de 30 s:** `GET /v1/tracks/{mbid}/preview` (y `/v1/tracks/ext/deezer:<id>/preview`). La URL la firma Deezer y
  caduca en unos 15 minutos, así que se pide al pulsar «Escuchar extracto». Nunca se guarda, y el audio se reproduce en
  streaming en el móvil (`expo-audio`), sin pasar por el backend.
- **Sello:** solo si MusicBrainz no documenta ninguno (ni autoedición), y solo de un lanzamiento propio del artista
  (single, EP o álbum, nunca un recopilatorio) del **mismo año** que la edición original. Así se evita el sello de una
  reedición (Villalobos figura en Deezer con «EAMS», de 2017).
- La ficha gana `deezer_url` y la fuente «Deezer (extracto y sello)». La caché de la ficha (`TRACK_CONTRACT_VERSION`) no
  cambia: Deezer se aplica fuera, como AcousticBrainz y ReccoBeats.

### Catálogo de reserva

- Solo si ni MusicBrainz ni Discogs encuentran nada, con dos palabras significativas o más y el mismo filtro estricto de
  palabras. Dos resultados con el mismo ISRC son una sola grabación; un edit o un remix es otra canción.
- Identidad `deezer:<id>`, ficha en `GET /v1/tracks/ext/deezer:<id>` (`catalog: "deezer"`): lanzamiento, sello, fecha,
  ISRC, portada, extracto y tempo de ReccoBeats para ese ISRC y duración. Sin género (Deezer solo da uno amplio, como
  «Dance») ni interpretación con IA. El artista solo se enlaza si MusicBrainz enlaza esa ficha de Deezer.
- App: etiqueta «Deezer» en la búsqueda y pie «Datos de Deezer ↗» con el aviso de no afiliación. Como las de Discogs,
  estas canciones aún no se pueden guardar.

### Piloto (`backend/eval/pilot_v61_tracks.py`, 2026-10-25)

| Canción | Extracto | Sello | Cambio |
|---|---|---|---|
| Desire — Chris Stassy | Sí | — → **CSS** (Deezer) | Sello nuevo |
| Double C — PAWSA | Sí | — (álbum de banda sonora: no se atribuye) | Extracto |
| Hoodlum — Traumer | Sí | Desolat (MB) | Extracto |
| Lovelee Dae — Blaze | No: Deezer la tiene sin extracto | MB | — |
| Music Sounds Better With You — Stardust | Sí | MB | Extracto |
| Dirty Cash — PAWSA | Sí | MB | Extracto |
| Crazy — ANOTR | Sí | MB | Extracto |
| Breather — Chris Stassy | No: sin ISRC en MusicBrainz | MB | — |
| **Playground — Arapu** (búsqueda «arapu playground») | Sí | **Solid Grooves Records** | **Antes no se encontraba en ningún catálogo** |
| Vinotinto — Luciano | — | — | Sigue saliendo de Discogs (Deezer no se consulta) |

Extracto en 6 de 8 grabaciones de MusicBrainz, +1 sello y +1 canción encontrada. El BPM no cambia en este bloque.

## 6. Pendiente

- **V6.2 — BPM y tonalidad propios:** analizar el extracto de 30 s en memoria con librosa (licencia ISC), sin guardar el
  audio, y medir la precisión frente a AcousticBrainz antes de mostrarlo. Hay que confirmar antes que procesar el
  extracto en memoria no choca con las condiciones de Deezer (prohíben guardarlo, no analizarlo, pero no lo dicen
  expresamente).
- **V6.3 — Tags y artistas similares:** tags de MusicBrainz (CC BY-NC-SA) y Last.fm (requiere clave; las páginas públicas
  piden aprobación por escrito).
- Guardar canciones de los catálogos externos (Discogs y Deezer): exige migrar Guardados, que van por MBID.
- Probar en el dispositivo la cabecera con foto y el reproductor: solo se han comprobado los tipos y las pruebas.

## 7. Perfil de artista (2026-10-25)

Piloto con fuentes reales: `backend/eval/pilot_profiles.py` (Traumer, PAWSA, Chris Stassy, Priku y Arapu).

- **Tracks esenciales** (`GET /v1/artists/{mbid}/essentials`, `app/essentials.py`), al final de «Más allá de la
  cabina»: 3–4 canciones del ranking del artista en Deezer, solo propias (sin remixes de otros ni versiones repetidas:
  la original antes que su edit). Cada fila abre su TrackDNA: el MBID si MusicBrainz tiene ese ISRC acreditado al
  artista y con la misma duración, o la ficha `deezer:<id>`. El criterio (popularidad en Deezer) se dice debajo. Caché
  de 7 días; se pide aparte del perfil. Piloto: 4 de 5 artistas con esenciales (Priku, sin ficha verificada en Deezer).
- **«Más allá de la cabina» v6** (`stories.VERSION` 6: las historias guardadas se regeneran una vez):
  - Títulos concretos: el prompt pide nombrar algo del hecho, y la validación rechaza los genéricos («Primer
    lanzamiento», «Su propio universo», «Estilo musical»…) y las historias que solo cuentan géneros (todos sus hechos
    son de estilo). Las plantillas sin IA usan «Todo empezó con «E-Bird»», «El universo Gettraum», «En el cartel de Dour».
  - Corregido: el primer lanzamiento ya no puede ser un DJ mix o un recopilatorio («Amnesia Ibiza Underground #4»), y
    los eventos sin nombre (solo una fecha, «1987‐12‐13») no salen en «En el cartel de».
- **«Escuchar»**: solo Spotify, Apple Music, SoundCloud y Discogs, en ese orden y en una rejilla de 2×2. El perfil
  directo si MusicBrainz lo enlaza; si no, una búsqueda por nombre marcada «Búsqueda». El resto de webs sigue en
  «Información técnica».
- **Carteles, «Sobre el artista»**: si el texto del perfil es pobre (sin Wikipedia, o con menos de 30 palabras), la vista
  pide la biografía (redactada por el backend a partir de fuentes y validada); si no hay fuentes descriptivas
  suficientes (`insufficient_sources`, lo habitual en el underground), usa las historias verificadas de «Más allá de la
  cabina». Piloto: sin biografía posible para Traumer, Priku ni Arapu, pero los tres tienen historias.
- Corregido de paso en `mobile/src/lib/format.ts`: la expresión `\bcd\b` de los formatos físicos se había guardado
  con caracteres de retroceso, así que las ediciones en CD nunca se reconocían.
- Pendiente: probar en el dispositivo los esenciales, el dock 2×2 y la vista rápida.
- **Pulido (tras probar en el iPhone):**
  - Vista rápida de Carteles: la foto va arriba (encuadrada desde arriba) y el nombre debajo, en su banda; antes, la
    franja del nombre iba encima de la foto y tapaba las caras.
  - Perfil sin «Su música» ni «Temas más escuchados» (los esenciales ya llevan a la música con su TrackDNA), sin el
    bloque «Información técnica y fuentes» y sin la línea de fuentes de cada historia. El crédito de la foto, que su
    licencia exige (CC BY-SA en Commons), sigue sobre la foto y ahora abre su página de origen.

## 8. Inicio: islas de color y afines en «Tu frecuencia»

- **Lectura**: la portada sigue a sangre; En el radar, Tu frecuencia y Detrás del sonido son islas de color sobre la
  noche de la edición (nunca en `night`), separadas por 48 px. Encabezados de sección a cuerpo fijo (34 px) en la
  tipografía titular; texto corrido en sans 16–17; mono desde 12 px. El pie ya no lista fuentes.
- **Afines** (`GET /v1/tracks/{mbid}/affinity`, `app/affinity.py`): artistas que Deezer relaciona con el de cada
  Guardado y su tema propio más escuchado (sin remixes, dubs ni edits; nunca el mismo título que la canción de
  partida). Partida: la grabación en Deezer por ISRC y duración o, si no está, la ficha de Deezer de su artista.
  MBID por ISRC (mismo nombre de artista y duración ±3 %) cuando MusicBrainz lo tiene; si no, `deezer:<id>`. Caché
  de 7 días. Motivos en la app: «Cerca de «X»» y «Afín a {artista}».
- **Sin versiones de lo guardado**: además de grabación, relaciones de MusicBrainz y familia (título + artista), Tu
  frecuencia bloquea cualquier propuesta con el mismo título base que un Guardado (`songTitle`), aunque la firme el
  remezclador.

## 9. V6.2 — TrackDNA, Inicio breve y fotos como láminas (2026-10-25)

- **ADN musical con más cobertura**:
  - **Género**: si MusicBrainz y Wikidata no lo dan, el del lanzamiento propio en Discogs que contiene la misma pista
    (título igual sin «(Original Mix)», mismo artista, duración ±3 % si consta; nunca un remix, un DJ mix ni un
    recopilatorio). `discogs_tracks.genre_for`; se guarda 30 días solo el número del lanzamiento (las condiciones de
    la API limitan su contenido a 6 h). También para las canciones de Deezer.
  - **BPM**: el de Deezer (`bpm` de la pista identificada por ISRC y duración) cuando AcousticBrainz y ReccoBeats no
    lo tienen; 0 = sin calcular y fuera de 70–180 se descarta.
  - Piloto con 16 esenciales underground (Traumer, PAWSA, Chris Stassy, Arapu, Kerri Chandler, Dam Swindle): género
    2 → 7 (4 con estilo concreto, 3 solo «Electrónica» porque el EP mezcla familias); BPM 13/16 (ReccoBeats; Deezer
    da 0 en todas). Tonalidad: ninguna fuente fiable; seguiría requiriendo analizar el audio (pendiente de confirmar
    las condiciones de Deezer).
- **Guardar canciones de Discogs y Deezer**: la ficha ya muestra «Guardar»; se guardan con su id externo y Tu
  frecuencia pide sus afines (`GET /v1/tracks/ext/{id}/affinity`, solo Deezer).
- **Extracto**: reproducir/pausar dibujados con formas (los caracteres se veían como emoji en iOS).
- **Inicio**: datos sin repetir el título, intros de una línea, En el radar sin intro y con el dato como nota bajo la
  canción, portadas más grandes; Detrás del sonido nombra la canción antes del dato.
- **Perfil de artista**: la foto como lámina cuadrada con bloque de color desfasado (como la portada en TrackDNA).
- **Afines de artistas pequeños**: si Deezer no relaciona a nadie (p. ej. Arapu), otros artistas del mismo sello que la
  canción de partida (búsqueda de Deezer por sello, confirmada con el sello de cada álbum; nunca recopilatorios ni
  autoediciones). Motivos: «Mismo sello que «X»: {sello}» y «En {sello}, como {artista}».

## 10. V6.3 — TrackDNA como análisis del track (2026-10-25)

Piloto `backend/eval/pilot_v63_analysis.py`: los clasificadores de alto nivel de AcousticBrainz no son publicables
(«trance» para Strings of Life, «no bailable» para el mismo tema); el perfil de ReccoBeats sí es coherente (separa
bien voz e instrumental: Good Life, Dirty Cash ≈ 0 de instrumentalidad; Hoodlum, Desire ≈ 0,9). Etiquetas libres de
MusicBrainz: casi nunca hay (2/16), no se usan.

- **Géneros y subgéneros**: una fuente que solo dice «Electrónica» cede ante la siguiente que concreta (grabación →
  Wikidata → lanzamiento → Discogs). «Minimal» es comodín (convive con house y techno) y ya no convierte un EP
  «Minimal, Tech House» en «Electrónica». Vocabulario ampliado con estilos habituales de Discogs. Wikidata
  normalizado (familia y estilo, mayúscula inicial). EP que mezclan familias: «Estilos del lanzamiento», nunca
  como género de la pista. `TRACK_CONTRACT_VERSION = 8`.
- **Perfil sonoro** (ReccoBeats, por ISRC y duración; cada rasgo solo si sus ediciones concuerdan ±0,15): energía,
  bailabilidad, ánimo (0–100) y voz/instrumental. Tonalidad: sigue sin publicarse.
- **En la ficha**: el BPM situado en el rango habitual de su género (orientativo) y una «Lectura» que solo junta esos
  datos (voz, estilo, tempo, energía, ánimo y duración); con menos de dos datos, no hay lectura.
- Resultado en 18 temas (5 clásicos y 13 esenciales underground): género 11 (10 concretos; antes 2 de los 13
  underground y los clásicos en «Electrónica»), BPM 15, perfil sonoro 11.

## 11. V6.4 — Fichas sin datos y nombre actual de Chris Stassy (2026-10-25)

Diagnóstico de las fichas «secas» (Shinjuku de Franky Rizardo, Ride On Me de PAWSA, Playground de Arapu): son
lanzamientos de 2025–2026 que ReccoBeats, AcousticBrainz (cerrado en 2022) y Discogs aún no tienen; Ride On Me además no
tiene ISRC en MusicBrainz.

- **Sin ISRC → búsqueda verificada en Deezer** (`deezer.track_match`, `matched_by: "search"`): mismo artista, título
  igual sin «(Original Mix)» y misma duración; búsqueda avanzada y, si no da nada, simple. Aporta extracto, ISRC (para
  ReccoBeats cuando lo tenga), BPM de Deezer y sello.
- **Contexto del sonido** (`discogs_tracks.context_traits`, solo si nadie clasifica la pista): estilos presentes en al
  menos el 20 % de los lanzamientos de su sello y de su artista en Discogs (mínimo 5). Cada resultado confirma el
  sello o el artista, y el sello solo cuenta si el artista ha publicado en él (el «CSS» de Desire coincidía con un
  sello homónimo de calipso). En la ficha: «Contexto del sonido · no clasifican esta pista» y en la lectura
  («Aún sin clasificación propia: su sello, Solid Grooves Records, publica sobre todo tech house y minimal techno, y
  PAWSA se mueve en el tech house»).
- **Límite**: para lo recién salido no hay BPM, tonalidad ni perfil sonoro en ninguna fuente abierta. La única vía
  sería analizar el extracto de 30 s; las condiciones de Deezer no lo contemplan («reproduction… in total or
  partially» y otros usos «beforehand reviewed and approved by DEEZER»): pendiente de decisión.
- **Chris Stassy** (antes Chris Stussy; MusicBrainz aún tiene el nombre antiguo): `app/renames.py` corrige por MBID
  las respuestas de MusicBrainz, traduce la búsqueda («Chris Stassy» encuentra al artista) y un middleware cambia el
  nombre en todo JSON de la API (historias, títulos de remixes, cachés). Repo, pruebas y documentos, actualizados.

## 12. V6.5 — Género en todas las fichas (2026-10-26)

Decisión: no se analiza el extracto de Deezer (BPM, tonalidad y perfil sonoro de lo recién salido siguen sin publicarse).

- **Género deducido** (`discogs_tracks.with_inferred_genre`, último paso del ADN en MusicBrainz y Deezer): si ninguna
  fuente clasifica la pista (o solo dice «Electrónica»), el género sale de los estilos habituales que comparten su
  artista y su sello en Discogs; si no, los del artista (Discogs, luego Wikidata); si no, los del sello. Una sola
  familia (estilo principal y los de su familia o comodín). Va con `scope` «artist» o «label» y nunca pisa un género
  propio.
- **En la app**: «Género · por su artista» / «Género · por su sello»; el contexto que lo explica sigue visible y la
  lectura no lo toma como clasificación propia. No se usa como dato de Inicio («Se etiqueta como…»); sí en Tu
  frecuencia.
- Comprobado con el backend en marcha: Shinjuku y Ride On Me → House, Tech House (por su sello); Playground (Deezer) →
  House, Minimal, Tech House (por su artista). Sin artista ni sello con estilos en Discogs o Wikidata, sigue sin género.

## 13. V6.6 — Fichas de Discogs completas y cartel de TrackDNA (2026-10-26)

Caso: «Coco Feel And Love Shonk» (Shonky, Contexterrior, 2008) salía del catálogo de Discogs sin duración, sin
extracto y solo con «Electrónica».

- **Discogs × Deezer** (`api._discogs_with_deezer`, `deezer.track_match(..., release_title=)`): la misma pista en
  Deezer por artista, título (sin «(Original Mix)») y lanzamiento con el mismo título (sin «EP»/«Single»); si las
  candidatas no tienen todas la misma duración, ninguna. Aporta duración, ISRC (→ perfil sonoro y tempo de
  ReccoBeats), tempo de Deezer y extracto (`/tracks/ext/discogs:…/preview`, por la coincidencia guardada). Después,
  contexto de sello y artista (nunca el sello de un recopilatorio) y género deducido (V6.5).
- Vocabulario: «Tribal» de Discogs → familia House.
- **Formato**: tipo de lanzamiento y soporte («Single · Vinilo de 12"»); en Discogs a menudo solo consta el soporte.
- Resultado con el backend en marcha: 7:40, 125 BPM, energía 71, bailabilidad 80, instrumental, House · Tribal ·
  Minimal y extracto.
- **Cartel de TrackDNA** (`components/trackdna-poster.tsx`, `lib/trackdna-home.ts`): edición del día como un flyer
  (paleta del día, «Nº 299 · 26.10.26»), código de barras de ADN que late, disco girando en la banda «DNA» y una cinta
  con lo que lee una ficha; sugerencias como line-up con horas. Con «reducir movimiento», quieto.

## 14. V6.7 — Guardados y Perfil con personalidad (2026-10-26)

Sin cuenta: todo sale de lo guardado en el dispositivo (`lib/library-stats.ts`; solo cuenta lo que consta y, en «tu
sonido», lo que se repite en dos o más canciones).

- **Guardados («tu cajón»)**: cartel con tiempo total de música, época y sello que más se repite; la última guardada
  destacada (portada grande con bloque de color desfasado) y el resto como tracklist numerado; orden Recientes, A–Z o
  Año.
- **Perfil («Tu pase»)**: cifras (canciones, artistas, tiempo), «Tu sonido» (artista, sello y época que más se
  repiten), artistas de partida con su marca, estilos como pegatinas (Tu frecuencia ya los usa; el aviso de que no
  influían estaba desfasado) y una «Sala de máquinas» plegada con conexión, descartados y fuentes actualizadas.
