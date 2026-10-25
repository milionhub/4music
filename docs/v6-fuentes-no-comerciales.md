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
   o uno si además coincide el nombre. Así sobrevive a los cambios de nombre: Chris Stussy figura en Deezer como
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
| Desire — Chris Stussy | Sí | — → **CSS** (Deezer) | Sello nuevo |
| Double C — PAWSA | Sí | — (álbum de banda sonora: no se atribuye) | Extracto |
| Hoodlum — Traumer | Sí | Desolat (MB) | Extracto |
| Lovelee Dae — Blaze | No: Deezer la tiene sin extracto | MB | — |
| Music Sounds Better With You — Stardust | Sí | MB | Extracto |
| Dirty Cash — PAWSA | Sí | MB | Extracto |
| Crazy — ANOTR | Sí | MB | Extracto |
| Breather — Chris Stussy | No: sin ISRC en MusicBrainz | MB | — |
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

Piloto con fuentes reales: `backend/eval/pilot_profiles.py` (Traumer, PAWSA, Chris Stussy, Priku y Arapu).

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
