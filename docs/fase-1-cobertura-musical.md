# Fase 1.2 — Cobertura de fuentes musicales (experimento)

Experimento aislado en [`research/music_sources/`](../research/music_sources/README.md). No toca `mobile/` ni el backend. Su fin es aportar evidencia para decidir qué fuentes integrar, no construir el producto.

> **Limitaciones:** resultados **preliminares** con 11 casos; **Discogs no evaluado** (bloqueado, §2); la **cobertura de géneros electrónicos es insuficiente** en las fuentes evaluadas (§8). Los resultados interpretados están en [`research/music_sources/data/results/`](../research/music_sources/data/results/); las respuestas HTTP originales y los logs no se versionan.

## 1. Ejecución y versiones

| | |
|---|---|
| Fecha | 2026-10-16. Ejecución en frío a las 11:24 UTC, ampliación incremental a las 11:28 y repetición íntegra desde caché a las 11:28. |
| Entorno | Python 3.11.2 (Windows 11), solo biblioteca estándar, sin dependencias nuevas. |
| MusicBrainz | API `https://musicbrainz.org/ws/2/` (JSON). |
| Wikidata | Action API `https://www.wikidata.org/w/api.php` (`wbsearchentities`, `wbgetentities`, `maxlag=5`). |
| Discogs | No consultado (§2). |
| User-Agent | `music-discovery-coverage-research/0.1 ( <contacto> )`. El contacto se lee de un `.env` local y no aparece en ningún archivo generado. |
| Reproducibilidad | La segunda ejecución hizo 0 peticiones de red y produjo `songs.json` y `artists.json` idénticos a los de la primera. |

Antes de esta ejecución hubo una pasada preliminar (80 peticiones: 70 a MB y 10 a WD) con un intervalo de 1,1 s. Al revisarla salieron errores de criterio: el homónimo de Adrian Mills, se elegían grabaciones de DJ‑mix en vez de la original y no se buscaba el enlace inverso en Wikidata. Se corrigieron los scripts, se borraron esos datos y se regeneró todo. En esa pasada hubo 11 respuestas 503 de MusicBrainz, todas recuperadas al reintentar; por eso el intervalo subió a 1,5 s.

## 2. Fuentes y restricciones

Vocabulario de este informe:

- **Documentada**: se han leído sus condiciones.
- **Consulta correcta**: HTTP 200 con JSON válido.
- **Encontrado**: el campo viene en la respuesta.
- **Validado**: lo confirma un enlace independiente (ID MB↔WD) o coincide en dos fuentes con al menos una afirmación referenciada.
- **Ausente**: la consulta fue correcta pero el campo no existe.
- **Bloqueada / no evaluada**: no se ha consultado.

| Fuente | Documentada | Estado | Restricciones relevantes |
|---|---|---|---|
| **MusicBrainz** | Sí ([rate limiting](https://musicbrainz.org/doc/MusicBrainz_API/Rate_Limiting), [licencia](https://musicbrainz.org/doc/About/Data_License), [datos centrales y suplementarios](https://musicbrainz.org/doc/MusicBrainz_Database)) | 74 peticiones, todas correctas al final | ~1 petición/s de media **por IP**: si se supera, se rechazan *todas*. User-Agent con contacto obligatorio. Los datos centrales (artistas, grabaciones, lanzamientos, sellos, relaciones y URL) son **CC0**. Las **etiquetas y asociaciones de género, valoraciones y anotaciones** son **CC BY-NC-SA 3.0** (no comercial). El uso comercial del Live Data Feed requiere licencia de MetaBrainz. |
| **Wikidata** | Sí ([Help:Data_access](https://www.wikidata.org/wiki/Help:Data_access)) | 10 peticiones, 0 errores | CC0. Sin límite numérico publicado: User-Agent correcto, pocas peticiones simultáneas, respetar 429/`Retry-After` y `maxlag`. Las interfaces «no garantizan estabilidad». |
| **Discogs** | **Parcial**: `discogs.com/developers` y las [API Terms of Use](https://support.discogs.com/hc/en-us/articles/360009334593-API-Terms-of-Use) devuelven **HTTP 403** a clientes automatizados, así que solo se han leído fragmentos a través de buscadores. | **Bloqueada, no evaluada.** 0 peticiones. | Según esos fragmentos: el contenido mostrado no puede tener más de **6 horas** de antigüedad respecto a Discogs, el almacenamiento se limita a lo necesario, la atribución «Data provided by Discogs» es obligatoria y los «Restricted Data» tienen licencia aparte. Ritmo: 60/min autenticado, 25/min sin autenticar. Según la documentación conocida, que no se ha podido volver a verificar, `/database/search` requiere token, y no hay ninguno (ni se ha pedido). Se ha reservado la variable `DISCOGS_TOKEN` en `.env.example`, sin código que la use. |

## 3. Canciones

Todos los datos proceden de MusicBrainz salvo que se indique otra fuente. La duración sale del campo `length` de la grabación.

| # | Entrada | Identificación | Artista y colaboradores | Versión(es) encontradas | Duración | Fecha | Tipo | Sello (n.º de catálogo) | Géneros (procedencia) | Enlaces | IDs | Ambigüedades y contradicciones |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| S1 | On 2nite — Silva Bumpa | **Encontrado, coincidencia exacta** de título y artista. Grabación [de0b20c7](https://musicbrainz.org/recording/de0b20c7-0aa0-4ab2-8e4a-52bf9ae54c1d). | Silva Bumpa («Sheffield, UK DJ»), sin colaboradores. | Original, *extended mix* [68e07af2](https://musicbrainz.org/recording/68e07af2-584a-47e4-a45f-96d90c5efd4d) y *Dusky remix* (solo en la búsqueda, sin consulta detallada). | 2:38 (original), 4:30 (extended), 2:53 (Dusky remix) | 2026-05-29 | Single | Room Two Recordings (el extended tiene cat. G010005833291B) | MB: *uk garage* y *speed garage*, 1 voto cada uno, solo en el extended mix. | Spotify, Deezer, Apple Music, Qobuz y Beatport (extended) | ISRC GBARL2600782 (original), GBARL2601058 (remix); códigos de barras 196874442296 y 196874442302 | **Dos grabaciones con el mismo ISRC** y duraciones distintas (158 000 y 158 848 ms). La segunda aparece en otro single, «Fantasy (Baby if u know me)» (2026-08-14), así que es probablemente un duplicado sin fusionar en MB. Hay además dos lanzamientos «On 2nite» en el mismo release group: uno sin sello ni fecha completa. Un homónimo de otro artista: «On 2Nite» de Stick Figure. |
| S2 | Vinotinto — Luciano | **No encontrado en MB.** Las consultas fueron correctas; es ausencia, no error de búsqueda. | — | — | — | — | — | — | — | — | — | Hay **3 artistas «Luciano»** en MB: cantante jamaicano de reggae, rapero alemán y «Chilean-Swiss DJ, techno & house producer». Se hizo una búsqueda aproximada restringida al MBID de cada uno (`vinotinto~` o `vino*`, que cubre «Vino Tinto») y dio 0 resultados en los tres. Con el título solo, MB devuelve «La Vinotinto» (Los Mentas) y WD un club de fútbol: no guardan relación. |
| S3 | Lovelee Dae — Blaze | **Encontrado, coincidencia exacta.** Grabación más antigua y con más lanzamientos: [8edae321](https://musicbrainz.org/recording/8edae321-48fc-4ae6-add1-bc976cb1a823) (10 lanzamientos). | Blaze («New Jersey-based house duo»). Otras grabaciones acreditan a Amine Edge & DANCE vs. Blaze (versión de 2017–2022). | Original, «(original)», «(Mixed)», cortes de DJ‑mix y la versión de Amine Edge & DANCE. | 7:36 la principal. Las demás grabaciones con ese título van de 1:41 a 7:37. | 1997 | Single (y numerosos recopilatorios) | Urban Tracks (571 917‑2), Classic (CMC 90), Substance (SUB 4891.2, 1998) | Release group: *deep house* (3 votos), *electronic* y *house* (2 votos cada uno). | Discogs (3 lanzamientos y el master 73016) | ISRC DED579706570; código de barras 731457191729 | **Más de 25 grabaciones** solo en la primera página de resultados (124 en total), sin fusionar. **4 artistas «Blaze»** (house, heavy metal, rap alemán, metal de Osaka); acierta gracias a la desambiguación. |
| S4 | Dirty Cash — PAWSA | **Encontrado como variante de título**: en MB el título completo es «Dirty Cash (Money Talks)». No es coincidencia exacta. | PAWSA (desambiguación: «David Esekhile») **& Adventures of Stevie V** | Radio [f2399817](https://musicbrainz.org/recording/f2399817-454b-4c24-8af4-b7c1b17dc00a) y extended [89fbe5e3](https://musicbrainz.org/recording/89fbe5e3-b2e9-492d-a83c-4b4c18eb723d) | 3:41 y 4:40 | 2024-11-15 | Single (también en *Now That's What I Call Music! 120*) | Altra Moda Music (AMM946 / AMM945) | MB: *house* (1 voto), *electronic* (release group) | Spotify, Deezer, Apple, Beatport, Qobuz, Tidal y Discogs (2) | ISRC NLML62400170 y NLML62400169; códigos de barras 8718274967463 y 8718274967456 | El título «Dirty Cash» a secas devuelve 246 grabaciones, muchas del **original de Adventures of Stevie V (1989/1990)**. MB **no** enlaza la versión de PAWSA con esa obra; Wikidata tiene el original (Q2002632) como candidato, sin vincular. |
| S5 | Breather — Chris Stassy | **Solo con la corrección candidata «Chris Stassy».** La entrada original da 0 resultados. Grabación [e0ee17b8](https://musicbrainz.org/recording/e0ee17b8-17d3-4514-8579-9a1fd127b57f). | Chris Stassy («NL \| electronic») & S.A.M. | Una sola grabación | 7:45 | 2021-06-08 | EP *Get Together* | Up the Stuss (UTS04) | Release group: *deep house*, *electronic* y *house* (1 voto cada uno) | Bandcamp | Sin ISRC | «Breather» a secas devuelve 438 grabaciones. La corrección no se ha validado con una segunda fuente: es una **coincidencia candidata**. |

Resumen: 3 de 5 encontradas con la entrada exacta (S1, S3 y S4, esta como variante de título), 1 solo con corrección (S5) y 1 ausente (S2). **Ninguna canción tiene enlace a Wikidata desde MB**, y la búsqueda de texto en Wikidata no encontró ninguna de las cinco versiones.

## 4. Artistas

| # | Entrada | Identificación (MB) | Homónimos | País / origen | Nacimiento | Bio verificable | Sellos | Géneros (procedencia) | Wikidata | IDs y enlaces |
|---|---|---|---|---|---|---|---|---|---|---|
| A1 | The Martinez Brothers | **Exacta**, [c9c65c94](https://musicbrainz.org/artist/c9c65c94-27b4-4eca-82f0-80055ac4f8a7) (grupo, «Chris Martinez and Steve Jr. Martinez») | **Sí**: otro «The Martinez Brothers» (Jaron y Marc Martinez, 1 lanzamiento) | MB: zona de inicio New York, país ausente. WD: país de origen **República Dominicana** (importado de Wikipedia) y lugar de formación Nueva York (sin referencia). | No aplica (grupo); inicio 2007 (MB) | Dúo de DJ/productores estadounidense (descripción WD) | MB por número de lanzamientos: Defected 7, EMPIRE 6, Cuttin' Headz 5…; relación «recording contract» con Independent Co. | MB: ausente. WD: house (importado de Wikipedia). | Q20687342, **validado** (enlace en ambos sentidos) | Discogs 715291, Spotify, Beatport, Apple, Tidal, SoundCloud, YouTube y redes sociales |
| A2 | Adrian Mills | **Ambigua.** La regla de nombre exacto elige [24b97924](https://musicbrainz.org/artist/24b97924-39eb-4e1d-a817-b2622fdeb339), un «Adrian Mills» miembro de **Diamond Head**, banda de heavy metal: probablemente **no** es el buscado. El candidato corregido «Adrián Mills» ([e4243e21](https://musicbrainz.org/artist/e4243e21-8b1a-4060-a5e4-f8001989afe1), desambiguación «techno», DE) aparece con la entrada sin tilde. | **Sí, 2** | Adrián Mills: DE (MB) | Ausente | Ausente | Ausente: los dos tienen 0 lanzamientos en MB | Solo la desambiguación «techno» | Ninguno enlazado. La búsqueda de texto devuelve un presentador de televisión británico (**no validado, descartado**). | Adrián Mills: Instagram y SoundCloud. El otro: Discogs 671778. |
| A3 | Ilario Alicante | **Exacta**, [f1ea7840](https://musicbrainz.org/artist/f1ea7840-95a4-4798-945f-140b8af5b208) | No | IT; zona de inicio Livorno (MB) | Año 1988 en MB (`life-span.begin`), sin referencia en la API | Fundador del sello Virgo (relación MB) | Drumcode 3, SCI+TEC 2, Cocoon, Tenax, Nervous, Virgo y Cécille | Ausente en MB | **Ausente**: la búsqueda de texto da 0 resultados | Discogs 862287, SoundCloud y redes sociales |
| A4 | Sven Vath | **Encontrado por diacríticos o alias**: «Sven Vath» y «Sven Vaeth» son alias en MB de [Sven Väth](https://musicbrainz.org/artist/14008378-5900-4370-831e-3d17f9749caf). La corrección candidata da el mismo MBID. | No | DE; nacido en Obertshausen (MB y WD, en WD importado de Wikipedia) | **1964-10-26, validado**: coincide en MB y en WD, y en WD está referenciado por la GND | Alias y proyectos (R U Ready, Sam Vision, Barbarella, 16 BIT…), hermano Mike Väth (MB y WD) | Fundador de Cocoon y Eye Q (MB). Por lanzamientos: Cocoon 22, Eye Q 18, Virgin 16… WD solo recoge Warner Bros. Records, sin referencia. | MB: electronic, techno y trance (1 voto cada uno). WD: techno y trance (sin referencia). La descripción en español de WD dice «techno minimal». | Q61011, **validado** (24 wikis enlazadas) | Discogs 1328, VIAF, AllMusic, IMDb, RA, Bandcamp, Beatport, Spotify… |
| A5 | Mochackk | **Solo con la corrección candidata «Mochakk»**: la entrada original da 0 resultados. [35321b91](https://musicbrainz.org/artist/35321b91-98ca-4a78-b34f-cb113722eab9) («Brazilian DJ and producer») | No | BR; Sorocaba (MB y WD; en WD referenciado con una web de terceros) | 1999-09-21 **solo en WD**, referenciado con technobeatscloud.com. Encontrado, no validado. | — | CircoLoco 5, Nervous 2, Cercle, Ninja Tune… (MB). WD: Cercle Records y un ítem sin etiqueta. | MB: ausente. WD: house (referencia RA) y **tech house** (referencia a una revista). | Q124125060, **validado** (enlace en ambos sentidos) | Discogs 7725928, RA, Beatport, Spotify, Bandcamp, web oficial… |
| A6 | Michael Bibi | **Exacta**, [a5cce1aa](https://musicbrainz.org/artist/a5cce1aa-b8eb-4592-a0d9-a021be3bdcf8) (desambiguación «electronic») | No | MB: ausente. WD: ciudadanía Reino Unido (referencia insomniac.com). | 1990-06-23 **solo en WD**, referenciado con famousbirthdays.com (fuente débil). No validado. | — | Solid Grooves Records 9, Solid Grooves Raw 3, CircoLoco 2… Incluye sellos ajenos al género (Drag City, Big Beat), probablemente lanzamientos de remezclas. | MB: ausente. WD: house (referencia DJ Mag) y **tech house** (referencia insomniac). | Q115631706. **MB no enlaza a WD**; se encontró por texto y se validó porque su P434 apunta al MBID: **validado solo por enlace inverso**. | Discogs 6016798, RA, Beatport, Spotify, SoundCloud… |

## 5. Campos completos, ausentes o ambiguos

- **Siempre presentes en MB cuando la entidad existe:** MBID, nombre, créditos de artista con MBID, título, duración (canciones), lanzamientos y tipo de release group, y enlaces a tiendas o streaming en la mayoría.
- **Frecuentes:** sello y número de catálogo (4/4 canciones encontradas), ISRC (3/4) y código de barras (3/4), siempre a nivel de lanzamiento. Discogs IDs a través de MB: 6/6 artistas (para A2 solo el homónimo) y 2/4 canciones.
- **Ausentes o escasos:** géneros (en el apartado 8), fecha de nacimiento en MB (solo Sven Väth y el año de Ilario Alicante), país (sin dato en 2/6) y biografía (MB no la tiene). Enlace de canción a Wikidata: 0/5.
- **Ambiguos:**
  - El «origen» de The Martinez Brothers: República Dominicana o Nueva York.
  - La fecha «2026» frente a «2026-05-29» en dos lanzamientos de S1.
  - Grabaciones duplicadas (S1, S3).
  - Sellos derivados de los lanzamientos, que mezclan remezclas y recopilatorios (A6).
  - Sven Väth: solo se procesaron 100 de sus 120 lanzamientos (una página).

## 6. Contradicciones entre fuentes

| Caso | MusicBrainz | Wikidata | Valoración |
|---|---|---|---|
| A1 origen | Zona de inicio New York; país ausente | País de origen República Dominicana (importado de Wikipedia); formación en Nueva York | Contradicción aparente: probablemente herencia frente a lugar de formación. No resoluble sin una fuente referenciada. |
| A4 sellos | Fundó Cocoon y Eye Q; más de 22 lanzamientos en cada uno | Solo Warner Bros. Records, sin referencia | WD está incompleto y no es fiable para sellos. |
| A6 país | Ausente | Reino Unido (referenciado) | Complementario, no contradictorio. |
| A4 nacimiento y lugar | 1964-10-26, Obertshausen | Mismos valores | **Coinciden.** La fecha queda validada con la referencia de la GND. |

Matiz: Wikidata marca como «referenciadas» afirmaciones cuya fuente es «stated in: MusicBrainz/Discogs». Para validar contra MB eso es **circular** y no cuenta como confirmación independiente. Recuento en los 4 ítems validados: 26 afirmaciones con referencia, 6 solo importadas de Wikipedia y 22 sin referencia.

## 7. MusicBrainz solo frente a MusicBrainz + Wikidata

| Aspecto | Solo MB | Con Wikidata | Ganancia |
|---|---|---|---|
| Canciones | 4/5 identificadas | +0 (no hay ítems de WD para estas versiones) | **Nula** |
| Artistas con ítem WD | — | 4/6 (3 enlazados desde MB y 1 por enlace inverso) | — |
| Fecha de nacimiento | 1/6 completa (Väth) y 1 solo con el año | +2 (Mochakk, Bibi), con referencias de calidad discutible | Media, pero requiere juicio sobre la fuente |
| País / ciudadanía | 4/6 | +1 (Bibi: Reino Unido) y 1 conflictiva (A1) | Baja |
| Géneros | 1/6 artistas | +3 (Martinez, Mochakk, Bibi), con tech house referenciado en 2 | **La mayor ganancia**, aunque sin cobertura en canciones |
| Biografía | Desambiguación y relaciones | Descripción breve, ocupación, hermanos, enlaces a 4–24 Wikipedias | Media (los enlaces a Wikipedia permitirían ir más allá, fuera de alcance) |
| Sellos | Buena, derivada de los lanzamientos | Pobre o incompleta | Nula |

Wikidata **no** aporta nada para los artistas emergentes o de nicho (A2, A3). Sin el enlace desde MB, su búsqueda por texto devolvió un homónimo erróneo para A2. Por eso solo se aceptan ítems validados por MBID.

## 8. Géneros específicos de electrónica

| Caso | MB (asociaciones de género, NC) | Wikidata |
|---|---|---|
| S1 | uk garage y speed garage (1 voto, solo en el extended) | — |
| S2 | — | — |
| S3 | deep house (3), house y electronic | — |
| S4 | house y electronic (1) | — |
| S5 | deep house, house y electronic (1) | — |
| A1–A6 | Solo Väth: electronic, techno y trance | house (A1, A5, A6), tech house (A5, A6), techno y trance (A4) |

Conclusiones:

- La cobertura es **escasa y superficial**: casi siempre 1 voto y en el release group, no en la grabación.
- Términos clave de la escena actual como **tech house** o **minimal** están **ausentes en MB** para todos los casos. Solo aparecen en Wikidata para 2 artistas.
- Las asociaciones de género de MB son **CC BY-NC-SA**: no sirven para un producto comercial sin licencia.
- **Ninguna fuente evaluada cubre bien los estilos electrónicos.** Discogs, la candidata natural por sus *styles*, sigue sin evaluar.

## 9. Versiones y homónimos

- **Versiones:** MB distingue bien grabación, lanzamiento y release group. Las versiones aparecen como grabaciones distintas: original, extended, remix (S1, S4) y cortes de DJ‑mix (S3). Problemas:
  - Grabaciones duplicadas sin fusionar: S3 tiene más de 25 con el mismo título y artista, y S1 tiene dos con el mismo ISRC.
  - El sufijo «(Original Mix)» de las tiendas no existe en MB.
  - El título real puede ser más largo que el que se usa al hablar («Dirty Cash (Money Talks)»).
  - Elegir la versión correcta requiere reglas explícitas: más antigua, no DJ‑mix, con más lanzamientos. Aun así es una **interpretación**: sin la duración o el ISRC del usuario, no se puede saber qué versión quería.
- **Homónimos:**
  - Blaze tiene 4 artistas en MB y Luciano 3; para las canciones se resolvieron por título y desambiguación.
  - The Martinez Brothers tiene 2.
  - **Adrian Mills es el caso peligroso:** la coincidencia exacta lleva a un músico de heavy metal y la buena tiene tilde.
  - Las erratas (Stassy, Mochackk) dan 0 resultados en MB con búsqueda por frase: hace falta un paso de **sugerencia de corrección con confirmación**, nunca automático. «Sven Vath» funciona porque MB guarda ese alias.

## 10. Coste, límites y sostenibilidad

| | MusicBrainz | Wikidata | Discogs |
|---|---|---|---|
| Coste | Gratis | Gratis | Gratis con token |
| Peticiones en este experimento | 74 en la ejecución final, 144 en total hoy contando la pasada descartada | 10 (20 en total) | 0 |
| Errores | 503 transitorios: 5 de 74 a 1,5 s y 11 de 70 a 1,1 s. Todos se recuperaron al reintentar; 0 fallos finales. | 0 | — |
| Ritmo medido | Separación mínima entre inicios de 1,5 s; media de 0,59/s | 1,0 s | — |
| Peticiones por entidad (en frío) | ~10–12 por canción y ~4–5 por artista; ~15 s por canción por el límite | 1–2 por lote de 50 entidades | — |
| Licencia para producto | Datos centrales CC0; géneros y tags no comerciales | CC0 | Restricciones de frescura (6 h), almacenamiento y atribución |

Sostenibilidad: llamar en directo a MB desde cada usuario no escala, porque el límite es por IP y global. Un producto necesitaría una **caché propia en el backend** o una réplica de la base de datos. La réplica por Live Data Feed es CC BY-NC-SA y su uso comercial exige licencia de MetaBrainz; habría que estudiar los volcados CC0. Wikidata es asumible a bajo volumen; para volumen alto habría que usar volcados.

## 11. Recomendación técnica provisional

1. **MusicBrainz como columna vertebral de identificación** (MBID, ISRC, sellos, catálogos, lanzamientos y enlaces a tiendas). Encontró 4/5 canciones (una solo con la corrección) y candidato para 6/6 artistas (A5 solo con la corrección; A2 ambiguo). Usar solo sus **datos centrales CC0**; no apoyarse en sus géneros o tags sin resolver la licencia.
2. **Wikidata solo como enriquecimiento de artistas**, y únicamente cuando el ítem está validado por MBID (en cualquiera de los dos sentidos). Hay que mostrar el estado de referencia y descartar las referencias circulares. No sirve para canciones.
3. **Géneros electrónicos: problema abierto.** Ninguna fuente evaluada lo resuelve. Próximo paso, decisión humana: leer las condiciones de Discogs en un navegador, decidir si se pide un token y valorar si la regla de 6 h y la limitación de almacenamiento son compatibles con el producto. MB ya da los IDs de Discogs, así que bastaría con consultas por ID, sin búsqueda.
4. **Correspondencias siempre con estado explícito** (exacta, por diacríticos o alias, corrección candidata, variante de título, ambigua por homónimos, no encontrada) y confirmación del usuario en los casos ambiguos. A2 demuestra que la coincidencia exacta de nombre no basta.
5. Repetir con una muestra mayor (20–50 casos) antes de cerrar la decisión: con 11 casos estas cifras son indicativas, no estadísticas.

Pendiente o fuera de alcance: Discogs (bloqueado), Wikipedia (no evaluada) y validación de las referencias externas de Wikidata (solo se ha comprobado si existen, no su calidad).
