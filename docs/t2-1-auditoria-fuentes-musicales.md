# T2.1 — Auditoría de APIs, cobertura musical y estrategia de datos

Investigación y auditoría del **2026-10-17**. **No implementa nada.** No se ha modificado código, `.env`, cachés ni favoritos; no se ha instalado nada; no se ha llamado a Groq. La caché SQLite (`backend/data/artist_intel.sqlite3`) se abrió **solo en modo lectura** (`mode=ro`).

**Pruebas realizadas.** 91 respuestas de lectura guardadas fuera del repositorio (directorio temporal de la sesión). Se usaron, con pausas de 1,2 s:

- MusicBrainz, con el User-Agent de contacto ya configurado.
- Deezer, iTunes Search, Wikidata (1 consulta SPARQL), AcousticBrainz, TheAudioDB (clave pública de prueba `123`, documentada por el propio servicio), ListenBrainz sin token y un lanzamiento público de Discogs sin token.

No se usaron credenciales nuevas ni ajenas, ni se hizo scraping. MusicBrainz devolvió 503 en 3 peticiones, que se repitieron una vez.

**Leyenda de estado:**

- **Observado**: resultado real de una consulta de hoy.
- **Documentado**: lo dice la documentación oficial, sin comprobarlo aquí.
- **Pendiente**: requiere una clave que no tenemos.
- **Requiere confirmación**: condición legal no clara.

---

## A. Diagnóstico actual

### A.1 DESIRE (Chris Stussy): por qué sale 0 de 5

| Rasgo | Qué ocurre realmente | Tipo de causa |
|---|---|---|
| **Sello** | La grabación [`9d619150…`](https://musicbrainz.org/recording/9d619150-6b0f-4f14-b038-8503ae4c6c8f) tiene **un único lanzamiento** ([`4df304a8…`](https://musicbrainz.org/release/4df304a8-3f71-4c7b-b520-b1efc158a177), single digital, 2024-02-09) con `label-info: []`. El dato **falta en la fuente**. MusicBrainz lo tiene solo como texto libre en la anotación («℗ & © 2024 CSS»). Deezer, en cambio, da `label: "CSS"` para el mismo UPC 197190967067. | **Falta de datos en la fuente** + **consulta insuficiente**: no hay un segundo proveedor. No es un fallo de selección ni de transformación: la caché guarda exactamente lo que devolvió MusicBrainz (verificado en modo lectura). |
| **Género** | Sin ítem de Wikidata para la grabación ni para el lanzamiento. El ítem del artista ([Q125928984](https://www.wikidata.org/wiki/Q125928984)) **no tiene P136**, así que ni siquiera aparece «Estilo del artista». MusicBrainz no tiene tags para esa grabación, y los excluimos por licencia. Deezer e iTunes dicen solo «Dance». | **Falta de datos** + **restricción de licencia** (géneros de MusicBrainz, CC BY-NC-SA). |
| **BPM, tonalidad, energía** | `tracks.dna()` los marca **siempre** como `unavailable` (`backend/app/tracks.py:454`). AcousticBrainz no tiene la grabación (publicada en 2024, después de su congelación en 2022). Deezer devuelve `bpm: 0`. | **Decisión de diseño** (no hay fuente) + falta de datos. |
| **Interpretación IA** | `track_ai.sufficient()` exige texto de Wikipedia sobre **la canción o su lanzamiento** (`DESCRIPTIVE_SCOPES`, `track_ai.py:80`). Solo existe la Wikipedia del artista. En la caché consta `insufficient_sources` (14 días). | **Comportamiento esperado del diseño**: para el underground casi nunca habrá Wikipedia de la pista (1 de 7 en el banco de pruebas). |

**Hallazgo adicional: cambio de nombre.** Deezer e iTunes acreditan Desire a **«CHRIS STASSY»**, con la discografía real del artista (ENDZ032, Midtown Playground…). La Wikipedia inglesa se titula «Chris_Stassy», y la Fase 1.3A ya vio en Discogs «Changed his name to Chris Stassy in August 2026». MusicBrainz sigue con «Chris Stussy». **Cualquier cruce por nombre entre proveedores fallaría.** Por ISRC (`QM4TW2437510`) y por los enlaces `url-rels` del lanzamiento (Deezer, Spotify y Apple) el cruce funciona.

> Conclusión: DESIRE **no** demuestra un error de código. Demuestra que **una sola fuente (MusicBrainz) no basta para un single autoeditado de 2024**, y que el ADN muestra «no disponible» incluso en datos que en realidad no son aplicables o que existen en otra fuente.

### A.2 Problemas confirmados

1. **«[no label]» se presenta como «sin datos».** Con «[no label]», MusicBrainz documenta una **autoedición**, y `_label_names` la descarta (`tracks.py:135`). Después el ADN dice «MusicBrainz no documenta el sello» (`tracks.py:434`). Los dos lanzamientos de Bandcamp del banco de pruebas lo confirman: EED, «Sing», con `[no label]`, y Arapu, «Just a Jam», con `label-info` vacío. **Error de transformación y de redacción.**
2. **Los enlaces de los lanzamientos no se piden.** `recording_releases` usa `inc=labels+release-groups+artist-credits+media` (`musicbrainz.py:192`), sin `url-rels`. Los enlaces útiles para cruzar proveedores y para el usuario (Bandcamp, Deezer, Beatport, Discogs, Spotify, Apple, Tidal) están **en el lanzamiento, no en la grabación**: los 7 lanzamientos originales tienen alguno, y 6 de 7 enlazan a una tienda o servicio (Hanging Tree solo tiene Rate Your Music). `tracks.links()` solo lee los de la grabación (`tracks.py:375`). **Consulta insuficiente.**
3. **Etiqueta «(no usado)».** En `mobile/src/app/(tabs)/index.tsx:59`, a partir del sexto favorito se añade «(no usado)», porque `getDiscovery` solo envía `MAX_SEEDS = 5` (`services/music.ts:13`), que es el límite del backend (`api.py`, `MAX_SEEDS`). Es una decisión de UX, no un error, pero comunica mal: parece que el favorito está estropeado.
4. **El título «TrackDNA · Descubrir»** (`index.tsx:36`) y «music-discovery · TrackDNA» en la incorporación (`onboarding.tsx:60`) son herencia de cuando TrackDNA era el nombre de la app. El docstring de `recommend.py` también habla del «Motor de recomendación de TrackDNA».
5. **Recomendaciones poco relevantes.** Se ven en `eval/last_results.json` (por ejemplo, Joseph Capriati → Mory Kanté, Conrad Schnitzler; Cloonee → Young M.A, Lindy Layton). Las causas están detalladas en la sección E.
6. **Fotos.** De 40 artistas en la caché, **14 tienen foto (35 %)**: 6 por la relación «image» de MusicBrainz y 8 por la P18 de Wikidata. 19 no tienen ítem de Wikidata y 7 tienen ítem sin imagen. Esto refleja la fuente, no un fallo de código: los DJs underground casi no están en Commons.
7. **Biografías.** En la caché hay 3 `ok`, 5 `insufficient_sources` y 1 `rejected`. Mismo patrón: sin Wikipedia ni web oficial legible, no hay texto. Es honesto, pero el resultado es pobre.

### A.3 Sospechas (no confirmadas)

- **Remezclas sin enlazar.** «Sun Goes Down» tiene 4 remixes en MusicBrainz (Kanine, Classmatic, Wade's Acid y el extended), pero **ninguna relación `remix`** en la grabación original. El ADN no mostrará «Remezclas». Sospecha: es habitual en lanzamientos digitales recientes y convendría medirlo en más casos.
- **Grabaciones duplicadas.** Traumer tiene 4 grabaciones «Hoodlum», dos de ellas con el mismo ISRC (`DEHE41400041`). La búsqueda no las fusiona porque el título difiere («Hoodlum» y «Hoodlum (original mix)»), así que el usuario ve dos resultados. La causa está en la fuente (falta fusionar en MusicBrainz), pero el ISRC compartido permitiría agruparlas.
- **Caché sin versión de contrato.** El registro `track` se guarda 7 días sin versión (`api.py:484`). Si en T2.2 se añaden proveedores o se cambia la semántica de «[no label]», las fichas ya guardadas seguirán mostrando el ADN antiguo hasta que caduquen.

### A.4 Limitaciones de las fuentes (no son errores nuestros)

- MusicBrainz no tiene «Breathe» de PAWSA (sus 45 grabaciones revisadas). Deezer tampoco (61 lanzamientos de PAWSA revisados). **El caso 2 del banco no se ha podido verificar** y no se ha sustituido por otro.
- AcousticBrainz no tiene nada publicado después de 2022.
- Wikidata casi no tiene ítems de canciones ni de EPs underground.

---

## B. Tabla de las 15 fuentes

Consulta legal y técnica: **2026-10-17**. Las URL de cada conclusión están en B.1.

| # | Fuente | Tipo | Datos disponibles | Cobertura underground observada (banco de pruebas) | API key | Coste | Límites | Caché | Uso público/comercial | Restricciones | Dificultad | Clase |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | **MusicBrainz** | API remota + volcados | Identidad (MBID), ISRC, lanzamientos, sellos, catálogo, créditos, relaciones (remix, DJ-mix), URL externas | 7/7 canciones verificables. Sello estructurado 4/7 y autoedición identificable 2/7. Créditos más allá del artista: 0/7 | No (User-Agent con contacto) | Gratis | 1 petición/s por IP; 503 intermitentes | Sí (CC0) | Datos centrales CC0. Empresas con ingresos: nivel de soporte de MetaBrainz (requiere confirmación) | Géneros, tags, anotaciones e índices de búsqueda: **CC BY-NC-SA** | Ya integrada | **A** |
| 2 | **ListenBrainz** | API remota (+ Labs experimental) | Popularidad, artistas similares (Labs), metadatos con tags de MusicBrainz | `metadata/recording` sin token: tags en 3/7 (Villalobos y EED solo del artista; Traumer de la grabación y del grupo). `metadata/lookup` **sin token responde 401** (nuevo hoy) | Token gratuito de usuario para popularidad y lookup | Gratis | No publicados (Labs) | Requiere confirmación | Licencia de los datos **sin confirmar** (Fase 1) | Los tags que devuelve son los de MusicBrainz (NC) | Baja | **B** |
| 3 | **Wikidata / Commons** | API remota + SPARQL | Ítems de artista y lanzamiento, P136 (género), P264 (sello), P18 (foto), Wikipedia | Artistas del banco (8, incluido PAWSA): con ítem 5/8, con género 4/8, con foto 3/8 (Arapu, EED y Traumer sin ítem). Lanzamiento con ítem y género: 1/7 (Fizheuer Zieheuer: microhouse, techno) | No | Gratis | Cortesía (User-Agent) | Sí | Wikidata CC0. Commons: licencia **por archivo** | Las fotos exigen atribución y licencia compatible (ya filtramos NC/ND) | Ya integrada | **A** |
| 4 | **Discogs API** | API remota | Géneros y **estilos** por lanzamiento, sellos, catálogo, créditos detallados, imágenes | Lanzamiento público sin token: Fizheuer Zieheuer → Techno/Minimal/Experimental, Playhouse, créditos de mastering. Búsqueda: **pendiente** (exige token) | Token personal gratuito | Gratis | 60/min autenticado, 25/min sin autenticar | **No**: «no más de lo necesario» y frescura de 6 h | Comercial «generalmente permitido», **pero no con Restricted Data** | Contenido restringido no comercial; atribución; licencia revocable | Media | **C** |
| 4b | **Volcados CC0 de Discogs** | Base de datos descargable | Lo mismo que la API, incluidos estilos, créditos y **perfiles de artista** (Fase 1.3B) | Sin piloto (Fase 1.3B) | No | Gratis (más almacenamiento) | Volcado mensual (lanzamientos: 10,5 GB en gzip) | Sí (CC0) | CC0 (revisión legal pendiente, Fase 1) | Sin imágenes | Alta (procesado previo) | **A** (condicionada) |
| 5 | **Last.fm** | API remota | Tags de usuarios (subgéneros), artistas similares, biografías wiki, escuchas | **Pendiente** (sin clave) | Sí (gratuita) | Gratis | A discreción de Last.fm | Según cabeceras HTTP; tope de 100 MB | **Solo no comercial**; las páginas públicas requieren **aprobación por escrito** | **Prohibido usar imágenes/artwork**; atribución con enlace | Baja | **C** |
| 6 | **Deezer API** | API remota | Pista (ISRC, duración, `bpm`, `gain`), álbum (**sello**, género amplio, UPC, portada), artista, búsqueda | Encontradas 5/7 (no: Bibi, Arapu); EED encontrada pero **es otra versión**. Sello en todas las encontradas (Desire: «CSS»), aunque en Villalobos es el de una reedición de 2017 («EAMS»), no el original. BPM ≠ 0 solo en 1 (Hoodlum: 123). Tonalidad: no existe el campo | No (búsqueda y consulta) | Gratis | No publicados | No regulada | **«Strictly limited for a non-commercial purpose»** | Reproducir elementos del sitio (imágenes) sin autorización: **requiere confirmación**; avances de 30 s | Baja | **B** |
| 7 | **Spotify Web API** | API remota | Metadatos, portadas, avances; *audio-features* (BPM, tonalidad, energía) **cerrado** | No probado | Sí + OAuth | Gratis | Modo desarrollo: pocos usuarios. El acceso ampliado ya no está abierto a particulares | No regulada | Comercial muy limitado | Prohibido analizar el contenido o entrenar modelos; atribución y enlace obligatorios | Media | **D** |
| 8 | **Apple Music / MusicKit** | API remota | Catálogo, ISRC, géneros, avances | MusicKit no probado (de pago). iTunes Search (sin clave): Desire 1/3 (género «Dance»); Bibi «Hanging Tree» y Arapu, no encontrados | Token de desarrollador (programa de pago) | MusicKit: programa de desarrollador (de pago, requiere confirmación del importe); iTunes Search gratis | iTunes: ~20/min | iTunes: recomienda caché de las búsquedas | iTunes: **solo para promocionar contenido de la tienda** | Avances: solo en streaming; artwork promocional | Media | **D** (MusicKit) / **C** (iTunes Search) |
| 9 | **TheAudioDB** | API remota | Artistas (estilo, bio, fanart), álbumes y pistas (género, mood), IDs de MusicBrainz | Artista por MBID: 1/3 (Villalobos: estilo Techno, sin biografía). Pistas: 0/2 | Clave pública `123` (pruebas) o personal de pago | **8 $/mes** para publicar | 30/min gratis | No regulada | **El plan gratuito no permite publicar en tiendas de apps** | Fanart creado por usuarios: derechos no garantizados | Baja | **D** |
| 10 | **AcoustID / Chromaprint** | API remota + biblioteca local (huella acústica) | Identificar un audio → MBID de grabación | No probado (requiere clave de aplicación) | Sí (registro gratuito) | Gratis **solo no comercial**; comercial vía acoustid.biz (precio no publicado) | 3 peticiones/s | Requiere confirmación | No comercial salvo contrato | Las claves de usuario no deben ir en el código | Media | **C** |
| 11 | **AcousticBrainz** | API remota congelada + volcados | BPM, tonalidad, descriptores bajos y clasificadores altos (*mood*, *danceability*) | **3/7** con BPM y tonalidad (Bibi 126,9 F mayor; Traumer 123,0 G# menor; Villalobos 124,0 A# menor). Nada posterior a 2022 | No | Gratis | ~10 peticiones cada 10 s | Sí (CC0) | CC0 | Sin datos nuevos desde 2022; la API sigue «por ahora» | Baja | **B** |
| 12 | **Musicstax** | Web sin API pública | BPM, tonalidad, energía mostrados en la web | No hay API documentada. La web devuelve 403 a clientes automáticos; **no se ha intentado esquivarlo** | — | — | — | — | Sin condiciones para desarrolladores | Extraerlo sería scraping no autorizado | — | **D** |
| 13 | **SoundCloud API** | API remota con acceso solicitado | Pistas, sets, perfiles, *waveform* | No probado | Sí (registro con revisión; disponibilidad intermitente, requiere confirmación) | Gratis | 15 000 reproducciones/24 h (anuncio antiguo) | Requiere confirmación | Revocable sin aviso | Contenido de usuarios; sin BPM ni tonalidad estructurados | Media | **D** (hoy) |
| 14 | **Beatport** | API privada (v4) | BPM, tonalidad, género y subgénero, sello: **la mejor fuente teórica para el underground** | Solo enlaces: 1/7 lanzamientos (Dedust) tiene URL de Beatport en MusicBrainz | Solo socios (Partner Portal) | — | — | — | **Sin acceso oficial para terceros** | Usar el client ID público de la documentación sería eludir el acceso: **descartado** | — | **D** |
| 15 | **Bandcamp** | Sin API pública de catálogo | Merch/ventas solo para sellos; reproductor embebible | Enlaces: 2/7 lanzamientos (Arapu y EED) | Solo sellos y socios logísticos | — | — | — | API de catálogo inexistente | oEmbed no documentado oficialmente | — | **D** (API) |

**Alternativas investigadas brevemente:**

| Fuente | Tipo | Valor | Licencia o condición | Clase |
|---|---|---|---|---|
| Cover Art Archive | API remota de imágenes | Portada de 6/7 originales (no: EED «Sing») | «All images are copyrighted by their respective copyright owners»: **sin licencia de reutilización** (ya lo indicamos en la ficha). Mostrarla en una app pública **requiere confirmación** | B |
| Wikipedia / MediaWiki | API remota | Texto descriptivo: 1/7 lanzamientos (Fizheuer Zieheuer) | CC BY-SA 4.0 (se usa como fuente, no se copia) | A |
| **Essentia** | Biblioteca local (C++/Python) | BPM, tonalidad (perfil `edma` para electrónica), loudness, ritmo, *embeddings* | **AGPLv3** o licencia comercial de la UPF. Modelos preentrenados: **CC BY-NC-ND 4.0** | B |
| **librosa** | Biblioteca local (Python) | Tempo, beat, cromagrama (tonalidad, a implementar), RMS, *onset* | **ISC** (permisiva) | A |
| **aubio** | Biblioteca local (C/Python) | Tempo, *onset*, *pitch* | **GPL** (comercial: contactar con el autor) | B |
| GetSongBPM | API remota | Tempo y tonalidad por título/artista | Gratis, con **enlace obligatorio**; 3 000 peticiones/h. Procedencia del dato y caché: **requieren confirmación**. Su web devuelve 403 a clientes automáticos | C (pendiente de prueba) |
| Soundcharts, Chartmetric, Songstats, Tunebat | APIs comerciales | Rasgos de audio y estadísticas | De pago o sin API pública | D |

### B.1 Fuentes legales consultadas (2026-10-17)

| Conclusión | URL oficial |
|---|---|
| Datos centrales de MusicBrainz CC0 y suplementarios CC BY-NC-SA. Los contribuidores permiten a MetaBrainz licenciar comercialmente | https://musicbrainz.org/doc/About/Data_License · desglose en https://musicbrainz.org/doc/MusicBrainz_Database (citado en `docs/t0-contrato-datos.md`) |
| Cover Art Archive: imágenes con copyright de sus titulares | https://coverartarchive.org/ · https://musicbrainz.org/doc/Cover_Art_Archive/API |
| Last.fm: solo no comercial (cl. 3.1–3.2), tope de 100 MB (4.3.4), sin imágenes (5.1.8), aprobación escrita antes de publicar (2.7) | https://www.last.fm/api/tos |
| Discogs: frescura de 6 h, «no longer than necessary», Restricted Data no comercial, atribución. Actualizado el 2025-07-23 según la API del Help Center | https://support.discogs.com/hc/en-us/articles/360009334593 (leído mediante `support.discogs.com/api/v2/help_center/en-us/articles/360009334593.json`, porque la web devuelve 403) |
| Volcados de Discogs CC0 | https://data.discogs.com/ (Fase 1.3B) |
| Deezer: uso «strictly limited for a non-commercial purpose»; avances de 30 s | https://developers.deezer.com/termsofuse · https://developers.deezer.com/guidelines |
| Spotify: no analizar contenido (III.13), no entrenar modelos (III.14), atribución y enlace (II.4) | https://developer.spotify.com/policy |
| Spotify: acceso ampliado desde el 2025-05-15 solo para casos «established, scalable» | https://developer.spotify.com/blog/2025-04-15-updating-the-criteria-for-web-api-extended-access |
| Spotify: *audio-features* devuelve 403 a apps nuevas desde el 2024-11-27 | Respuestas de moderadores en el foro oficial (https://community.spotify.com, foro Spotify for Developers). **No es un anuncio oficial**: requiere confirmación |
| iTunes Search: ~20/min, solo promoción, avances solo en streaming | https://performance-partners.apple.com/search-api |
| MusicKit: tokens firmados desde la cuenta de desarrollador | https://developer.apple.com/musickit/ (el importe del programa no figura en esa página: requiere confirmación) |
| TheAudioDB: clave `123`, 30/min, Premium 8 $/mes | https://www.theaudiodb.com/free_music_api |
| TheAudioDB: «You cannot publish apps to an appstore unless you are a paid subscriber» | https://www.theaudiodb.com/docs_terms_of_use.php |
| AcoustID: gratis solo no comercial, 3 peticiones/s, comercial vía acoustid.biz | https://acoustid.org/webservice |
| AcousticBrainz: CC0, API disponible «for now», datos hasta 2022 | https://acousticbrainz.org/ |
| Essentia AGPLv3/comercial; modelos CC BY-NC-ND 4.0 | https://essentia.upf.edu/licensing_information.html |
| librosa ISC | https://github.com/librosa/librosa/blob/main/LICENSE.md |
| aubio GPL | https://aubio.org/ |
| GetSongBPM: gratis con enlace obligatorio, 3 000/h | https://getsongbpm.com/api (403 al leerla; se tomó del resultado de búsqueda: **requiere confirmación**) |
| Bandcamp: API de merch solo para sellos y socios | https://bandcamp.com/developer/merch |
| SoundCloud: registro de apps, revocación | https://developers.soundcloud.com/docs/api/terms-of-use |
| Beatport v4: solo socios | **No hay página oficial pública**; solo directorios de terceros y https://api.beatport.com/v4/docs/. Requiere confirmación |
| Musicstax: sin API | https://musicstax.com/ (403; no se encontró documentación para desarrolladores) |
| ListenBrainz: licencia de los datos | https://listenbrainz.org/terms-of-service/ (sin contenido legible): **requiere confirmación** |

---

## C. Matriz de cobertura real (observada el 2026-10-17)

**Versiones exactas verificadas en MusicBrainz:**

| # | Canción | Grabación (MBID) | Duración | ISRC | Lanzamiento original |
|---|---|---|---|---|---|
| 1 | Chris Stussy — Desire | `9d619150` | 2:52 | QM4TW2437510 | Single digital, 2024-02-09 |
| 2 | PAWSA — Breathe | **No verificada** | — | — | No existe en MusicBrainz ni en Deezer: **excluida** |
| 3 | Michael Bibi — Hanging Tree | `763d8c0c` | 6:11 | — | Repopulate Mars RPM044, 2018-11-16 |
| 4 | Cloonee — Sun Goes Down | `a9712244` | 2:35 (versión corta; el *extended* es otra grabación) | USAT21903020 | Big Beat, 2021-01-22 |
| 5 | Arapu — Just a Jam | `978e284e` | 14:37 | — | Bandcamp, 2024-07-12 |
| 6 | East End Dubs — Sing | `78d17b14` | 9:05 | — | Bandcamp, 2021-11-17 |
| 7 | Traumer — Hoodlum (original mix) | `98e34bc2` | 6:55 | DEHE41400041 | EP *Dedust*, Desolat DESOLAT 038, 2014-07-14 |
| 8 | Ricardo Villalobos — Fizheuer Zieheuer | `0a8347ed` | 37:10 | — | EP, Playhouse PLAYCD021, 2006-11-06 |

Las celdas de la matriz indican **valor (proveedor)**. Abreviaturas: MB = MusicBrainz, WD = Wikidata, DZ = Deezer, AB = AcousticBrainz, CAA = Cover Art Archive, DG = Discogs, IT = iTunes Search, LB = ListenBrainz. **«—»** significa que se consultó y no hay dato.

| # | Género | Sello | BPM | Tonalidad | Energía / acústica | Portada | Créditos | Descripción |
|---|---|---|---|---|---|---|---|---|
| 1 Desire | «Dance» (DZ, IT): demasiado genérico. WD —, MB — | **«CSS» (DZ)**; MB vacío (solo en la anotación) | DZ `0` (sin dato); AB — | — | DZ `gain` −9,8 dB (*loudness*, no energía) | CAA ✓, DZ ✓ | — | WP solo del artista |
| 3 Hanging Tree | WD del artista: tech house, house (contexto). DZ e IT: no encontrada | **Repopulate Mars (MB)** | **126,9 (AB)**, 4 envíos coherentes | **F mayor (AB)**, fuerza 0,74 | AB: *danceable*, *party* (clasificador poco fiable) | CAA ✓ | — | — |
| 4 Sun Goes Down | «Electro, Dance» (DZ). WD del artista: tech house | **Big Beat (MB)** = «Big Beat Records» (DZ) | DZ `0`; AB — | — | DZ `gain` −8,4 dB | CAA ✓, DZ ✓ | — | — |
| 5 Just a Jam | — (sin ítem WD; ausente en DZ e IT) | Autoedición: `label-info` vacío + Bandcamp (MB url-rels) | — | — | — | CAA ✓ | — | — |
| 6 Sing | Tags de MB del artista: tech house, deep house (LB, NC). DZ: hay un «Sing» de 2024 de 6:09 que **no es la misma versión** | **«[no label]» = autoedición (MB)** + Bandcamp | — | — | — | **CAA ✗** | — | — |
| 7 Hoodlum | Tags de MB: house (grabación), techno (grupo) (LB, NC). DZ «Electro» | **Desolat (MB)** = Desolat (DZ) | **123,0 (AB)** = **123 (DZ)** ✓ | **G# menor (AB)**, fuerza 0,73 | AB: *danceable* | CAA ✓ | — | — |
| 8 Fizheuer Zieheuer | **microhouse, techno (WD, lanzamiento)**; Techno/Minimal/Experimental (DG API, restringido) | **Playhouse (MB)** = Play CD021 (DG). DZ: reedición 2017 «EAMS» | **124,0 (AB)** | **A# menor (AB)** | AB: «not danceable», «ambient» ✗ (error del clasificador) | CAA ✓ | Mastering: Rashad Becker; autor/productor: Villalobos (DG) | **WP (en)** del lanzamiento ✓ |

**Recuento sobre las 7 canciones verificadas:**

| Rasgo | Resultado | Proveedor(es) |
|---|---|---|
| Género con licencia compatible y nivel pista/lanzamiento | **1/7** | WD |
| Género amplio | 4/7 | DZ (no comercial) |
| Sello estructurado | **4/7** | MB |
| Autoedición identificable | +2/7 | MB, hoy mal mostrada |
| Sello que solo aporta un segundo proveedor | +1/7 | DZ (Desire) |
| Sello: total con 2 proveedores | **7/7** | MB + DZ |
| BPM | **3/7** | AB; DZ 1/7, coincide con AB |
| Tonalidad | **3/7** | AB |
| Energía fiable | **0/7** | — |
| Portada | **6/7** | CAA |
| Créditos más allá del artista | **0/7** | MB; DG 1/1 consultado |
| Remixes enlazados | 1/7 | MB (Villalobos, NoiDoi) |
| Descripción de la pista o el lanzamiento | **1/7** | WP |

**Lectura de los resultados:**

- Los datos de **AcousticBrainz** cubren 3 de los 5 temas **anteriores a 2022** (faltan Cloonee y EED, ambos de 2021) y ninguno posterior. Donde se pueden contrastar (Hoodlum), coinciden con Deezer.
- La **Fase 1.3A** midió 1 de 9. Esa muestra tenía casi todo posterior a 2022, así que **el descarte de AcousticBrainz se basó en una muestra sesgada hacia lo reciente**.
- Los **clasificadores de alto nivel** de AcousticBrainz se equivocan con el minimal largo (Villalobos, «ambient» y «not danceable»). Solo son defendibles el **BPM** y la **tonalidad**, y aun así como estimación.

---

## D. Análisis acústico real

### D.1 Opción A: características mediante APIs externas

| Fuente | BPM | Tonalidad | Energía | Viabilidad |
|---|---|---|---|---|
| Spotify *audio-features* | Sí | Sí | Sí | **Cerrado** para apps nuevas; su política prohíbe analizar el contenido |
| Deezer `bpm` | 1/5 encontradas con valor | No | No (`gain` es *loudness*) | Insuficiente; uso no comercial |
| AcousticBrainz | 3/7 (solo ≤ 2022) | 3/7 | Clasificadores poco fiables | CC0, pero congelado: **útil como histórico, nunca como solución** |
| GetSongBPM | Sí (documentado) | Sí (documentado) | No | Pendiente de clave; procedencia y caché sin confirmar |
| Beatport | Sí (catálogo de referencia del DJ) | Sí | No | Sin acceso oficial |
| Musicstax, Tunebat | Sí (en su web) | Sí | Sí | Sin API; extraerlo sería scraping |

**Conclusión A:** **no existe una API gratuita, legal y con cobertura underground actual para BPM y tonalidad.** Para lo anterior a 2022 hay un histórico CC0 (AcousticBrainz).

### D.2 Opción B: calcularlas nosotros

**Qué audio necesitamos**

Audio decodificado, mono, a 44,1 kHz (o remuestreado a 22,05 o 16 kHz). Para el BPM y la tonalidad de house y techno bastan **60–120 s de la parte central**, sin intro ni outro de DJ. Para análisis del tema completo, todo el archivo.

**Cómo obtener el audio legalmente**

| Vía | ¿Legal para analizar? | Comentario |
|---|---|---|
| **Archivos aportados por el usuario** (su biblioteca de DJ: WAV, AIFF, MP3, FLAC) | **Sí**, como función de la herramienta: el usuario ya tiene el archivo y nosotros no lo distribuimos | Encaja con **SetLab**, porque los DJs trabajan con sus propios archivos. Requiere aviso de privacidad y no conservar el audio |
| Avances de 30 s (Deezer, iTunes) | **No**: iTunes los permite «streamed only, not downloaded, saved, cached»; Spotify prohíbe analizar; Deezer, sin autorización expresa | Descartado |
| Enlaces de Bandcamp o SoundCloud | **No**: descargar para analizar no está autorizado | Descartado |
| Audio de DJ sets o grabaciones de terceros | **No** | Descartado |

**Dónde procesarlo**

| Opción | Pros | Contras |
|---|---|---|
| **Backend** (FastAPI + biblioteca Python) | Una sola implementación; librosa o Essentia instalables; el resultado se cachea por huella o hash | Subir el audio: 7 min a 320 kbps son unos 16 MB. Hay que borrarlo al terminar y limitar el tamaño |
| **En el móvil** | El audio no sale del dispositivo | No hay binding mantenido de Essentia ni librosa para React Native. Exige un módulo nativo (fuera de Expo Go) o WASM (`essentia.js`, AGPL) en una WebView. Pesado y frágil |
| **Mixto** | El móvil recorta y decodifica un fragmento de 90 s y sube solo eso | Reduce subida y exposición; la decodificación en el móvil sigue exigiendo trabajo nativo |

**Coste computacional (estimación a medir en T2.2, no medido aquí)**

- Essentia (C++), `RhythmExtractor2013` + `KeyExtractor`, sobre 90 s: del orden de **1–3 s de CPU**.
- librosa (Python, `beat_track` + cromagrama): del orden de **5–15 s**.
- Ambas son viables en un backend pequeño con una cola.

**Precisión y errores habituales**

Según la literatura de MIR (GiantSteps, MIREX), son órdenes de magnitud que **deben validarse con nuestro propio banco**:

- **Tempo:** en electrónica a cuatro por cuatro suele acertarse en una gran mayoría de casos si se admiten errores de **octava**. El error típico es **doble o mitad** (62/124, 87/174). Se mitiga restringiendo el rango (p. ej. 100–150 para house y techno) y marcándolo como «estimado».
- **Tonalidad:** es claramente menos fiable. Errores típicos: **quinta**, **relativa mayor/menor** y paralela. El perfil `edma` de Essentia está pensado para electrónica. Los temas atonales o percusivos (mucho minimal y techno) **no tienen una tonalidad útil**: hay que poder responder «sin tonalidad clara» usando la fuerza (`key_strength`).
- **«Energía»:** no hay un estándar; la *energy* de Spotify es un modelo propietario. Propuesta: un descriptor propio y transparente, basado en *loudness* EBU R128 (LUFS), densidad de *onsets* y flujo espectral, presentado como «intensidad» con su definición. **Nunca** se debe llamar «energía» como si fuera la de Spotify.
- **Similitud acústica:** con *embeddings*. Los de Essentia (Discogs-EffNet y similares) son **CC BY-NC-ND**, es decir, no comerciales. Para uso comercial haría falta un modelo con licencia permisiva (requiere confirmación caso por caso). Se deja fuera del MVP.

**Licencias**

| Biblioteca | Licencia | Implicación |
|---|---|---|
| **librosa** | ISC | Sin obligaciones relevantes |
| **Essentia** | AGPLv3 | Si el backend la usa como servicio en red, puede obligar a **publicar el código del backend bajo AGPL**: **requiere confirmación legal**. Alternativa: licencia comercial de la UPF |
| **aubio** | GPL | Obligaciones de copyleft al distribuir |
| Chromaprint (para AcoustID) | LGPL (documentado por el proyecto; requiere confirmación) | El servicio AcoustID es no comercial salvo contrato |

**¿Sin almacenar audio?** **Sí.** Se procesa en memoria o en un archivo temporal y se borra en el mismo flujo. Solo se guardan los descriptores, la versión del algoritmo y, opcionalmente, una huella Chromaprint o un hash para reutilizar el resultado.

**Arquitectura posible del MVP (no implementar)**

```
App (SetLab) ─ el usuario elige un archivo propio
   └─▶ POST /v1/analysis (fragmento ≤ 120 s o archivo ≤ 30 MB, tipo comprobado)
         backend: decodificar → mono 22 kHz → tempo (rango 100–150), tonalidad + fuerza, LUFS, densidad de onsets
         → borrar el audio → guardar {hash, descriptores, versión del algoritmo, fecha}
         → (opcional) identificar con AcoustID → MBID → enlazar con la ficha TrackDNA
   ◀── {bpm, bpm_confidence, key, key_strength, intensity, status: "estimated", method}
```

**Groq no puede escuchar canciones:** el modelo de texto solo recibe texto. Groq ofrece transcripción de voz, que no sirve para BPM ni tonalidad. Cualquier rasgo sonoro escrito por el modelo sin análisis real seguiría siendo una invención, y por eso `track_ai.validate()` lo bloquea con razón.

### D.3 Recomendación

**Combinar:**

1. **AcousticBrainz** (CC0, por MBID) como histórico, marcado «estimación (AcousticBrainz, ≤ 2022)».
2. **Análisis propio** solo sobre archivos aportados por el usuario (SetLab), marcado «estimado por análisis».
3. Para el resto, «sin dato» **explicado**.

Empezar con **librosa (ISC)** para evitar la cuestión AGPL, y comparar con Essentia en un banco de unas 20 pistas con valores de referencia contrastados (AcousticBrainz y Deezer coincidentes) antes de elegir.

---

## E. Auditoría del código actual

| # | Archivo y función | Problema | Explicación | Arreglo sin APIs nuevas |
|---|---|---|---|---|
| E1 | `backend/app/tracks.py` · `_label_names` (l. 131–137) y `dna()` (l. 423–434) | «[no label]» → «MusicBrainz no documenta el sello» | «[no label]» es un dato: autoedición. Se convierte en ausencia | Rasgo «Sello: Autoedición» (verificado). Si `label-info` está vacío, «sin sello documentado» |
| E2 | `backend/app/musicbrainz.py` · `recording_releases` (l. 192–195) y `tracks.links` (l. 375) | No se piden `url-rels` de los lanzamientos | Los enlaces de Bandcamp, Deezer, Beatport, Discogs y Spotify están en el lanzamiento. Sin ellos no hay ni puente entre proveedores ni enlace de compra o escucha | Una petición extra a `release/{original}?inc=url-rels` (o `url-rels` en el *browse*, comprobando el coste) |
| E3 | `backend/app/tracks.py` · `dna()` (l. 454–456) | 3 filas fijas «no disponible» (BPM, tonalidad, energía) | Penaliza visualmente («0 de 5») datos que hoy **no tenemos ninguna vía de obtener**. No es un fallo, pero transmite poco valor | Agrupar como «Análisis acústico: pendiente» con una sola explicación. Cambiar el recuento para no contar como fallo lo estructuralmente imposible |
| E4 | `backend/app/track_ai.py` · `sufficient` (l. 208) y `DESCRIPTIVE_SCOPES` (l. 80) | La interpretación sale casi siempre «insuficiente» en el underground | Correcto por honestidad (1/7 tiene Wikipedia del lanzamiento), pero la UI ofrece una función que casi nunca funciona | **No relajar la regla.** Ocultar la sección, o cambiar el texto, cuando no hay fuente descriptiva. Reconsiderar la función cuando existan los perfiles de Discogs (CC0) |
| E5 | `backend/app/tracks.py` · `dna()`, rasgo `genre` (l. 401–415) | Género solo desde Wikidata (P4404/P436) | Casi nunca existe para el underground. El fallback «Estilo del artista» depende de P136, ausente para Chris Stussy | Mostrar los sellos como contexto de escena es legítimo. El género real exige otra fuente (Discogs CC0), ver F |
| E6 | `backend/app/recommend.py` · `_signals`, afinidad (l. 103) | **La afinidad mínima (0,50) supera el umbral (0,45)** | El docstring dice que «una señal débil sola no alcanza el umbral», pero cualquier fila de Labs, aunque su puntuación relativa sea casi 0, se publica sola. Explica Mory Kanté o Conrad Schnitzler para Capriati | Fuerza proporcional a la puntuación relativa (p. ej. `0.3 + 0.6·rel`), o exigir una puntuación relativa mínima, o una segunda señal para las filas débiles. Validar con `eval/` |
| E7 | `backend/app/recommend.py` · `_signals`, colaboración (l. 122) | 2 títulos conjuntos = 0,50, publicable sola | Cuenta vocalistas, *samples* acreditados y remezclas (Cloonee → Young M.A, Lindy Layton), aunque el propio docstring lo advierte para 1 título | Distinguir créditos de remix o feat. de los lanzamientos conjuntos con el artista principal; bajar la fuerza a menos de 0,45 si no hay otra señal |
| E8 | `backend/app/musicbrainz.py` · `label_releases` (l. 178) + `recommend.py` (sello compartido) | Solo la **primera página de 100** lanzamientos del sello, sin garantía de orden cronológico | En sellos grandes la época de la semilla puede quedar fuera de la muestra, y los compañeros de sello son los de esa página, no los de la época | Paginar con un tope (2–3 páginas) o filtrar por fecha. Medir con `eval/` |
| E9 | `backend/app/musicbrainz.py` · `LabsClient.ALGORITHMS` (l. 204) | El algoritmo de 7 500 días (≈ 20 años) pesa igual que el de 5 años | Sesgo histórico y hacia lo popular | Ponderar la variante reciente, o usar solo esa, y evaluarlo |
| E10 | `backend/app/recommend.py` (general) | No hay ninguna señal de estilo o escena | Las recomendaciones no comprueban coherencia de género, porque no tenemos géneros con licencia compatible | Dependerá de los estilos de Discogs CC0 (F, T2.2 etapa 3) |
| E11 | `mobile/src/app/(tabs)/index.tsx` (l. 17 y 59) | «(no usado)» | Límite de 5 semillas, comunicado como defecto del favorito | Elegir semillas («Usar para descubrir») o rotarlas; texto neutro («fuera de esta tanda») o sin sufijo |
| E12 | `mobile/src/app/(tabs)/index.tsx` (l. 36) y `onboarding.tsx` (l. 60) | «TrackDNA · Descubrir» y «music-discovery · TrackDNA» | TrackDNA es ahora un módulo | Usar «Chromatic Underground · Descubrir» o solo «Descubrir». Revisar también los docstrings |
| E13 | `backend/app/api.py` · `_track_bundle` (l. 409–486) | Registro `track` sin versión de contrato, con TTL de 7 días | Los cambios de T2.2 no se verían hasta que caduque, o se mezclarían datos viejos y nuevos | Añadir `schema_version` al registro e invalidar por versión (sin vaciar la caché completa) |
| E14 | `backend/app/tracks.py` · `search_results`, clave de fusión (l. 267) | No agrupa por ISRC | «Hoodlum» y «Hoodlum (original mix)» comparten ISRC y salen como dos canciones | Fusionar también por ISRC compartido, con los mismos artistas y duraciones cercanas (±3 s) |
| E15 | Identidad entre proveedores (general) | No hay cruce por ID | El cambio de nombre Stussy → Stassy rompería cualquier cruce por nombre | Regla para T2.2: cruzar **solo** por ISRC, UPC o barcode, o por `url-rels` de MusicBrainz. Por nombre, únicamente como candidato que hay que confirmar |
| E16 | Caché (general) | Funciona según lo diseñado | Memoria 24 h + SQLite por MBID. Los fallos temporales no se guardan. Desire en la caché coincide con MusicBrainz | Nada urgente. E13 es la única mejora necesaria |

**Fotos** (`backend/app/images.py`): la lógica es correcta y prudente. Solo por MBID y con licencia Commons compatible. Que haya foto en solo el 35 % de los artistas es un límite de la fuente.

Ninguna API gratuita resuelve las fotos con derechos claros:

- TheAudioDB: fanart sin garantía de derechos y plan de pago.
- Deezer: no comercial y reproducción sin autorización.
- Discogs: Restricted Data.
- Last.fm: prohíbe expresamente las imágenes.

La vía realista es el **catálogo editorial con permiso**: kits de prensa con autorización escrita, ya soportados por `editorial.json`. A eso se suma un **marcador visual digno** cuando no hay foto.

---

## F. Arquitectura recomendada (no implementar)

```
           ┌──────────── Identidad canónica ─────────────┐
 entrada → │ MusicBrainz: recording MBID + ISRC +         │
           │ release/release-group MBID + url-rels        │
           └───────────────┬──────────────────────────────┘
                           │ IDs puente (nunca por nombre):
                           │ ISRC, UPC/barcode, Discogs release ID, Deezer album ID, Bandcamp URL, P4404/P436
       ┌───────────────────┼─────────────────────┬─────────────────────┬───────────────────┐
  Wikidata (CC0)    Discogs CC0 (volcado)   AcousticBrainz (CC0)   Deezer (no comercial)   Análisis propio
  género, Wikipedia estilos, sello, créditos, BPM/tonalidad ≤2022   sello, género amplio    BPM/tonalidad/intensidad
                    perfil del artista                                                       (archivo del usuario)
       └───────────────────┴──────────┬──────────┴─────────────────────┴───────────────────┘
                                      ▼
                      Normalización → «Assertion» por dato:
                      {campo, valor, ámbito: track|release|artist, proveedor, ID de origen,
                       licencia, fecha_obtención, método: declared|derived|estimated, confianza}
                                      ▼
                      Resolución de conflictos por campo (reglas fijas, explicables)
                                      ▼
                      Ficha TrackDNA: valor elegido + alternativas + procedencia visible
```

**Reglas por bloque:**

- **Identificación canónica.** El MBID de la grabación es la clave. Los proveedores se enlazan por ISRC (pista), UPC/barcode (lanzamiento) o `url-rels` de MusicBrainz. El nombre solo genera **candidatos** y se descarta si la duración difiere más de 3 s (caso EED «Sing»: 9:05 frente a 6:09).
- **Enriquecimiento por proveedor.** Cada proveedor es un módulo aislado, con su caché, su TTL acorde con su licencia y su estado (`ok`, `empty`, `error`, `not_configured`). Ya es el patrón de `_section`.
- **Normalización.** Géneros mapeados a un vocabulario propio pequeño de electrónica (house, deep house, tech house, minimal, techno…), conservando el valor original. Tonalidad en notación musical + Camelot. BPM redondeado a 0,5 con su método.
- **Resolución de conflictos:**
  - **Sello:** MusicBrainz estructurado > autoedición documentada en MusicBrainz > Discogs CC0 > Deezer.
  - **Género:** Wikidata o Discogs CC0 del **lanzamiento** > estilo del artista (marcado como contexto). Los géneros de Deezer o iTunes («Dance») solo si no hay nada más, y rotulados como «categoría de tienda».
  - **BPM:** análisis propio > AcousticBrainz con varios envíos coherentes > Deezer distinto de 0. Si dos fuentes difieren más del 3 % y no es un error de octava, mostrar «discrepancia».
- **Procedencia.** Cada valor lleva fuente, licencia, fecha y método. Ya existe `SourceRef`: se amplía, no se sustituye.
- **Caché y atribución.**
  - CC0 (MusicBrainz, Wikidata, Discogs volcado, AcousticBrainz): persistente.
  - Deezer: TTL corto, sin redistribución, con atribución.
  - Discogs API: **no** se mezcla con el almacén (regla de 6 h).
  - Registros versionados (E13).
- **Calidad y confianza.** `declared` (MusicBrainz, Discogs, Wikidata) > `derived` (autoedición deducida de «[no label]») > `estimated` (análisis). La UI distingue «verificado», «comunidad» y «estimado», que ya existen en `status`.
- **Fallbacks.** Si no hay dato, explicación concreta: «autoeditado», «publicado después de 2022, sin análisis disponible», «analiza tu archivo en SetLab». Nunca «no disponible» genérico, nunca relleno.

---

## G. Ranking final: las 5 mejores opciones

| # | Opción | Valor incremental (sobre lo que ya tenemos) | Coste | Riesgo |
|---|---|---|---|---|
| 1 | **MusicBrainz mejor aprovechado** (`url-rels` de lanzamientos, autoedición, fusión por ISRC) | Lo arreglamos nosotros. Sello o autoedición en 6/7 en lugar de 4/7. Enlaces de compra y escucha en 6/7. Es el **puente de IDs** que hace posible todo lo demás | 0 €; +1 petición por ficha | Bajo |
| 2 | **Volcados CC0 de Discogs** | **Única fuente con licencia compatible para estilos electrónicos por lanzamiento** (Techno/Minimal/Experimental; Tech House…). También créditos (mastering, autoría) y **perfiles de artista** para biografías del underground. Resuelve E5, E10 y parte de E4 | 0 € + almacenamiento y procesado | Medio (piloto y revisión legal pendientes) |
| 3 | **Análisis propio sobre archivos del usuario** (librosa; Essentia en evaluación) | **Única vía sostenible para BPM y tonalidad de música actual** (posterior a 2022). Encaja con SetLab | 0 € + CPU del backend | Medio (precisión de la tonalidad, privacidad, AGPL si Essentia) |
| 4 | **AcousticBrainz** (API o volcado CC0) | BPM y tonalidad históricos sin hacer nada: 3/7 aquí (3 de los 5 temas anteriores a 2022). Coincide con Deezer donde se ha podido contrastar | 0 € | Bajo legalmente. El servicio puede cerrar: conviene valorar un volcado propio |
| 5 | **Deezer API** | Rellena el sello cuando MusicBrainz no lo tiene (Desire: «CSS»), confirma ISRC y fechas, y da portada cuando falta en el CAA. Sin clave | 0 € | **No comercial**: válido solo mientras la app no tenga ingresos. Las imágenes requieren confirmación |

**Quedan fuera del top 5, por qué:**

- **ListenBrainz con token:** útil y gratis (popularidad), pero es configuración, no una integración nueva.
- **Last.fm:** tags buenos, pero no comercial, con aprobación previa y sin imágenes.
- **AcoustID:** solo tiene sentido cuando SetLab acepte archivos.
- **TheAudioDB:** no se puede publicar gratis.
- **Spotify, Beatport, Bandcamp, Musicstax, SoundCloud:** inaccesibles o prohibidos para este uso.

---

## H. Plan T2.2 (propuesta por etapas)

Prioridad: valor → cobertura underground → legalidad → coste 0 → complejidad → mantenimiento.

| Etapa | Contenido | Fuentes nuevas | Comprobación |
|---|---|---|---|
| **0. Correcciones sin APIs** | E1 (autoedición), E2 (`url-rels` → enlaces y puente de IDs), E3 (agrupar lo acústico pendiente), E4 (ocultar la interpretación imposible), E11 y E12 (UX de Inicio), E13 (versión de la caché), E14 (fusión por ISRC) | Ninguna | `pytest`, `tsc`, revisión en iPhone del banco de pruebas |
| **1. Recomendaciones** | E6–E9: recalibrar la afinidad y la colaboración, paginar los sellos, ponderar los algoritmos de Labs. Ampliar `eval/` a más semillas underground (Traumer, EED, Arapu) | Ninguna | `eval/evaluate_discovery.py` antes y después |
| **2. AcousticBrainz histórico** | BPM y tonalidad por MBID con `status: estimated`, número de envíos y coherencia; nunca los clasificadores de alto nivel | AcousticBrainz (CC0, sin clave) | Banco con valores contrastados |
| **3. Piloto de volcados de Discogs** | Proceso offline: índice SQLite de estilos, sello y créditos por ID de lanzamiento de Discogs (vía `url-rels`); después, perfiles de artista como fuente de biografías | Volcado CC0 | Proporción real de electrónica, tamaño, revisión legal (decisión humana) |
| **4. Deezer como respaldo** | Sello y fechas cuando MusicBrainz no los tiene, cruzando solo por ISRC, UPC o `url-rels` | Deezer (sin clave, no comercial) | **Decisión humana previa** sobre el carácter no comercial |
| **5. Prototipo de análisis (SetLab)** | Endpoint de análisis sobre un archivo del usuario, sin almacenar audio; librosa frente a Essentia en unas 20 pistas | Ninguna (bibliotecas locales: nueva dependencia del backend, que se aprueba aparte) | Exactitud de tempo y tonalidad frente a la referencia; tiempo de CPU |

**Claves gratuitas:**

| Clave | ¿Crearla? | Motivo |
|---|---|---|
| **ListenBrainz token** | **Sí** | Gratis. Activa la popularidad (ya implementada) y `metadata/lookup` (ahora exige token) |
| **AcoustID (aplicación)** | **Más adelante** (etapa 5) | Solo para identificar archivos del usuario; no comercial |
| **Discogs token** | **Opcional, solo para el piloto** | Validar cruces durante el piloto. Lo obtenido por API no entra en el producto |
| **GetSongBPM** | **Opcional, solo prueba** | Medir cobertura con el banco. Producción no, hasta confirmar la procedencia del dato y la caché |
| Last.fm | No | No comercial, aprobación escrita, sin imágenes |
| Spotify | No | *audio-features* cerrado; prohíbe el análisis |
| TheAudioDB | No | El plan gratuito no permite publicar; fanart sin derechos claros |
| Apple MusicKit | No | Programa de pago; uso promocional |
| SoundCloud, Beatport | No | Acceso no disponible para nosotros |

**Decisiones humanas pendientes:**

1. ¿Será la app no comercial de forma estable? De ello dependen Deezer, AcoustID, Last.fm y los géneros de MusicBrainz (NC).
2. ¿Se puede asumir AGPL (código abierto del backend) o se usa solo librosa?
3. ¿Se lanza el piloto de volcados de Discogs?
4. Sustituir el caso 2 del banco (PAWSA «Breathe» no existe en las fuentes) por una canción verificada.
