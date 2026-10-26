# Fase 1.3 — Géneros electrónicos: Discogs y AcousticBrainz

Experimento en [`research/music_sources/`](../research/music_sources/README.md) (`run_phase13.py`). Reutiliza los casos y los identificadores de la [Fase 1.2](fase-1-cobertura-musical.md) en solo lectura y **no vuelve a consultar MusicBrainz (MB) ni Wikidata (WD)**. No toca `mobile/` ni `backend/`.

> **Limitaciones:** 11 casos, así que los resultados son **preliminares**. Los estilos de Discogs se asignan al **lanzamiento**, no a la pista ni al artista. Las condiciones de Discogs **no declaran CC0 los géneros y estilos de la API**, así que este informe **no** afirma que sean reutilizables comercialmente. Lo que da AcousticBrainz son **estimaciones algorítmicas**, no datos verificados.

Ejecución: 2026-10-16, a las 11:54 UTC en frío y a las 11:57 UTC una ampliación incremental (5 peticiones nuevas; el resto, desde caché). Python 3.11.2 y solo biblioteca estándar.

Estados usados en este informe:

- **No encontrado**: la consulta fue correcta y no hubo resultados.
- **No consultado**: no se lanzó la consulta.
- **No permitido**: las condiciones lo impiden.
- **Servicio no disponible**: error o timeout del servicio.
- **Ambiguo**: varios candidatos sin forma de validar cuál es el correcto.

## 1. Fuentes y condiciones verificadas (consultadas el 2026-10-16)

| Documento | Cómo se leyó | Puntos verificados |
|---|---|---|
| [Discogs API Terms of Use](https://support.discogs.com/hc/en-us/articles/360009334593-API-Terms-of-Use) («Last Updated: May 27th, 2025») | La página web devuelve **HTTP 403** a clientes automatizados. Se leyó el mismo artículo a través de la **API pública oficial del Help Center** de Discogs (`support.discogs.com/api/v2/help_center/…/360009334593.json`), sin eludir controles de acceso. | Ver la lista que sigue a esta tabla. |
| [Discogs Developers](https://www.discogs.com/developers) | **No se ha podido leer**: HTTP 403. | Se verificó **empíricamente**: la autenticación con la cabecera `Authorization: Discogs token=…` funciona, y las respuestas traen `X-Discogs-Ratelimit: 60` (60 peticiones/min autenticado) y los contadores `-Used` y `-Remaining`. |
| [Volcados de datos de Discogs](https://data.discogs.com/) | WebFetch | «This data is made available under the **CC0** No Rights Reserved license». Volcados mensuales de lanzamientos, artistas, sellos y masters. **No se ha verificado** que incluyan géneros y estilos. |
| [AcousticBrainz](https://acousticbrainz.org/) | WebFetch | Recogió datos de 2015 a 2022. En 2022 se decidió dejar de recoger, y el sitio y la API «continuarán disponibles» por ahora. |
| [API de AcousticBrainz](https://acousticbrainz.readthedocs.io/api.html) | WebFetch | Consulta masiva de hasta 25 MBID (`/api/v1/{count,low-level,high-level}`). Límite «típicamente 10 peticiones cada 10 s por IP», comunicado en las cabeceras `X-RateLimit-*`. |
| [Blog de MetaBrainz, 2022-02-16](https://blog.metabrainz.org/2022/02/16/acousticbrainz-making-a-hard-decision-to-end-the-project/) | WebFetch | Sobre la calidad de sus propios datos: la tonalidad es «accurate on some styles of music, but not on the full range»; en BPM, «many recordings for which the predicted value is incorrect»; y los modelos de género «didn't work very well». Anunciaba el cierre del sitio para principios de 2023, cosa que no ha ocurrido. La licencia CC0 solo consta en un comentario del equipo. |

Condiciones de Discogs relevantes para el producto, citadas de las API Terms of Use:

- **Datos CC0** declarados: «Release titles, notes, dates, format, track listings, barcodes and other identifiers, credits, versions, URL links»; «Artist names, notes, associated releases»; y nombres y notas de sellos.
- **Restricted Data**: datos de usuarios (incluidas colecciones y wantlists), datos de Marketplace e imágenes. Sobre ellos: «You may not… Use Restricted Data for any commercial purposes».
- **Los géneros y estilos no aparecen en ninguna de las dos listas.** No son CC0 de forma explícita en la API.
- **Frescura y almacenamiento**, aplicables a todo el contenido: «You may not display… the Content if it is more than six (6) hours older than the information on Our online properties», y «You may not cache or store the Content longer than is necessary to provide a service».
- **Atribución**: el aviso de no afiliación debe mostrarse en la app, y junto a cada dato debe aparecer «Data provided by Discogs» con un enlace a la página de Discogs, sin `nofollow`.
- **Uso comercial**: «generally permitted, but may not be permitted… in Our sole discretion». Entre los usos comerciales prohibidos, cobrar por acceder a algo que Discogs ofrece gratis y «Using Our API or the Content with the intent to drive traffic to other non-Discogs websites». Discogs se reserva cobrar por la API en el futuro y revocar el acceso sin preaviso.

Decisión: las condiciones **permiten un experimento pequeño de evaluación**, así que se hizo. Medidas aplicadas:

- Antes de guardar nada se eliminan los campos de Restricted Data: imágenes, `community`, `user_data`, `stats`, `submitter`, `lowest_price`, `num_for_sale` y `blocked_from_sale`.
- No se descarga ninguna imagen.
- Las respuestas originales y los logs se quedan en local y fuera de Git.

## 2. Estado de acceso

| Fuente | Estado | Detalle |
|---|---|---|
| **Discogs** | **Operativo, consultado** | 80 peticiones, todas HTTP 200. El token se lee del `.env` local y solo se envía en la cabecera a `api.discogs.com`; no aparece en URL, logs, resultados ni salida. |
| **AcousticBrainz** | **Operativo, pero degradado y congelado** | 4 peticiones: el primer intento **agotó el tiempo de espera (20 s)** y el reintento funcionó. Las respuestas tardan entre 6,5 y 10,8 s. Las cabeceras indican un límite de 100 por ventana, distinto del de la documentación. Desde 2022 no entran datos nuevos. |
| MusicBrainz y Wikidata | No consultados (por diseño) | Se usan los resultados de la Fase 1.2. |

## 3. Canciones: comparativa

Los estilos de Discogs son de **nivel de lanzamiento**. El sello y la fecha son los de la edición confirmada; la confirmación exige que la pista esté en el tracklist y que el artista esté acreditado.

| # | Entrada | MB (Fase 1.2) | Discogs: identificación | Versión y edición en Discogs | Género / estilo en Discogs | Sello y fecha en Discogs | AcousticBrainz | Novedad respecto a MB | Ambigüedades y contradicciones |
|---|---|---|---|---|---|---|---|---|---|
| S1 | On 2nite — Silva Bumpa | Exacta; *uk garage* y *speed garage* (1 voto, solo en el extended) | **Encontrado** por búsqueda con la entrada: [release 37517538](https://www.discogs.com/release/37517538-Silva-Bumpa-On-2nite). Artista: [Silva Bumpa](https://www.discogs.com/artist/11143466), Harry Eagle, «from Sheffield», que coincide con la desambiguación de MB. | 1 edición digital (FLAC), con la pista de 2:38. **No** incluye el extended ni el remix de Dusky que tiene MB. | Electronic / **UK Garage** | Room Two Recordings, 2026-05-29. Calidad: «Needs Vote». | No encontrado (0 envíos; publicada después de 2022) | Estilo a nivel de lanzamiento y nombre real del artista | MB tiene más versiones que Discogs |
| S2 | Vinotinto — Luciano | **No encontrado** | **Encontrado** por búsqueda con la entrada: [master 3614923](https://www.discogs.com/master/3614923) y [release 29565955](https://www.discogs.com/release/29565955). Créditos: Luciano, Carloh, Bastidas y Carlos Corté$. «Luciano» es el [artista 6362](https://www.discogs.com/artist/6362), Lucien Nicolet, «Swiss and Chilean DJ», coherente con uno de los 3 Luciano de MB. **No validado por ID**: MB no tiene esta grabación. | 2 ediciones digitales (WAV y MP3) con la pista de 9:19 | Electronic / **Tech House** (master y WAV); la edición MP3 añade *Deep House* | From The South, FTSR001, 2022-11-18 | No consultado (sin MBID) | **Identificación nueva**: MB no la tenía | El estilo difiere entre las dos ediciones digitales |
| S3 | Lovelee Dae — Blaze | Exacta (1997); release group *deep house*, *house* y *electronic* | **Confirmado por los IDs compartidos con MB** (3 releases) y por búsqueda. [Master 73016](https://www.discogs.com/master/73016-Blaze-Lovelee-Dae): **36 ediciones** de 1997 a 2018. Artista [Blaze (13)](https://www.discogs.com/artist/13), «New Jersey-based duo». | Créditos de cada versión: Original (7:35–7:36), Radio Edit (3:30, editada por Jörn Elling Wuttke y Roman Flügel), remezclas de 20:20 Vision, Eight Miles High, Isolée, Primitive Dub (Chris Duckenfield y Swag), The Beloved y Freaks, y A Cappella. | Master: Electronic / **House, Deep House**. La edición francesa (Substance, 1998) añade **Minimal y Techno**. | Urban Tracks/**Playhouse** 571 917‑2 (DE, 1997); Classic CMC90 (UK, 1997, «main release»); Substance (FR, 1998); True (BE, 1998) | **Estimado** (1 de las 3 grabaciones; ver §5) | Créditos de remezcla con duración, el sello Playhouse y 36 ediciones | Estilos incoherentes entre ediciones del mismo master |
| S4 | Dirty Cash — PAWSA | Variante de título, «Dirty Cash (Money Talks)»; *house* | **Confirmado por los IDs compartidos con MB** (2 releases) y por búsqueda (vinilo de 2025). Artista [PAWSA](https://www.discogs.com/artist/3750137), David Esekhile, igual que en MB. | Digital: Extended Mix (4:39, AMM945) y versión corta (3:41). El vinilo de 2025 (High Fashion Music, MS 540) añade un **«Sold Out Mix» de David Morales** (7:32). | Releases: Electronic / **House**; otra edición en vinilo añade *Hip-House*. El master tiene *Breakbeat, House y Hip-House*, pero **no es aplicable** (ver la última columna). | AltraModa, 2024-11-15. MB da el catálogo AMM946 a la versión corta y Discogs, «none». | No encontrado (2024) | Nueva versión con remezclador acreditado y una edición en vinilo | Discogs **agrupa la versión de 2024 bajo el master del original de 1989** de Adventures Of Stevie V ([master 96113](https://www.discogs.com/master/96113), 71 ediciones). Los estilos de ese master son del original y **se han excluido**. |
| S5 | Breather — Chris Stassy | Solo con la corrección «Chris Stassy»; *deep house* | Con «Chris Stassy»: **no encontrado** (0 resultados). Con «Chris Stassy»: [release 19018573](https://www.discogs.com/release/19018573), EP *Get Together*. El perfil del [artista 4465293](https://www.discogs.com/artist/4465293) dice: «**Changed his name to Chris Stassy in August 2026**». | LP de vinilo (edición limitada), pista A1 de 7:45; coincide con MB | Electronic / **Deep House, House** | Up The Stuss, UTS04, **2021-06-04**. MB da 2021-06-08 para su edición. | No encontrado | **El cambio de nombre**: la entrada probablemente **no era una errata** | Ni MB ni Discogs encuentran el nombre nuevo. Las fechas difieren 4 días entre ediciones. La afirmación del cambio procede de un perfil editado por usuarios y no está validada. |

Resumen de canciones en Discogs:

- **Encontradas: 5/5**, una de ellas solo con el nombre anterior (S5).
- Confirmadas por IDs compartidos con MB: 2.
- Estilo electrónico específico a nivel de lanzamiento: **5/5**.
- Calidad declarada de los lanzamientos consultados: 4 «Correct» y 6 «Needs Vote».

## 4. Artistas: comparativa

Los estilos proceden de una muestra de las **5 publicaciones más recientes con rol «Main»**, consultadas una a una. Son **estilos de esas publicaciones, no del artista**.

| # | Entrada | Identificación en Discogs | Homónimos en Discogs | Estilos en publicaciones concretas (muestra de 5) | Cobertura de la discografía | Novedad respecto a MB/WD | Calidad y procedencia |
|---|---|---|---|---|---|---|---|
| A1 | The Martinez Brothers | [715291](https://www.discogs.com/artist/715291), mediante el ID compartido con MB. Miembros: Chris Martinez (2) y Steve Jr. Martinez; alias Masters At Dutch. | Sí: «The Martinez Brothers (2)» (1 lanzamiento de 1997, «Needs Major Changes») | House ×3, Minimal, Tribal House y Tech House | **177 entradas** en Discogs (Main 33 y Remix 49 en la primera página de 100) frente a 46 lanzamientos en MB | Perfil: «DJs and producers from the Bronx, New York City… mentored by Dennis Ferrer», sellos Tuskegee y Cuttin' Headz. Apoya el origen en Nueva York, frente a la República Dominicana de WD. | Needs Vote; perfil editado por usuarios |
| A2 | Adrian Mills | **Ambiguo.** El ID que enlaza MB ([671778](https://www.discogs.com/artist/671778)) tiene el perfil «British heavy metal guitarist» (Diamond Head): **confirma que el enlace de MB apunta al homónimo equivocado** para nuestro dominio. «Adrián Mills» ([12773240](https://www.discogs.com/artist/12773240)) no tiene perfil y solo 1 aparición en pista. | **6 entradas**: Adrian Mills, (2) a (5) y Adrián Mills | Ninguno: ninguna publicación con rol Main | Prácticamente nula | Ninguna | Needs Major Changes |
| A3 | Ilario Alicante | [862287](https://www.discogs.com/artist/862287), mediante el ID de MB | No | **Techno ×5** y Neo Trance | 137 entradas (Main 38) frente a 10 en MB | «Italian DJ and producer, now based in Berlin», grupo Alicanuel y alias Rail (7). **Primeros estilos para este artista**: MB y WD no tenían ninguno. | Needs Vote |
| A4 | Sven Vath | [1328](https://www.discogs.com/artist/1328) Sven Väth, mediante el ID de MB | Una entrada duplicada sin tilde, «Sven Vath» (610651), con 1 lanzamiento no oficial | Techno ×4, Tech House ×2, Ambient, Fusion, Downtempo, Microhouse, Deep House, Trance y House | **1158 entradas** frente a 120 en MB | El perfil repite la fecha y el lugar de nacimiento (26-10-1964, Obertshausen), que coinciden con MB y WD; añade alias y grupos | Needs Vote. La muestra incluye una edición no oficial de un tercero («Nicolas Barnes Edit», autoeditada) marcada como Main. |
| A5 | Mochackk | Con «Mochackk»: **no encontrado**. Con «Mochakk»: [7725928](https://www.discogs.com/artist/7725928) (ID de MB), nombre real Pedro Maia. | No | **Tech House ×3**, House ×2 y Electro | 23 entradas frente a 18 en MB | «DJ and producer from São Paulo, Brazil». MB y WD dicen Sorocaba, que está en el estado de São Paulo: **ambiguo** (estado o ciudad), no contradictorio. | Needs Vote |
| A6 | Michael Bibi | [6016798](https://www.discogs.com/artist/6016798), mediante el ID de MB | No | **Tech House ×3**, House, Progressive House y Minimal Techno | 33 entradas frente a 34 en MB | «DJ and producer based in London. Son of Robin Bibi. Runs Solid Grooves Records» | Needs Vote |

## 5. Cobertura de géneros específicos

| Caso | MB (Fase 1.2) | WD (Fase 1.2) | Discogs (nivel de lanzamiento) | AcousticBrainz (estimación) |
|---|---|---|---|---|
| S1 | uk garage, speed garage (1 voto) | — | UK Garage | No encontrado |
| S2 | No encontrado | — | **Tech House** (+ Deep House en 1 edición) | No consultado |
| S3 | deep house, house y electronic | — | House y Deep House (+ Minimal y Techno en 1 edición) | `genre_electronic`: House (p = 0,40) |
| S4 | house y electronic | — | House (+ Hip-House en 1 edición) | No encontrado |
| S5 | deep house, house y electronic | — | Deep House y House | No encontrado |
| A1–A6 | Solo Väth (electronic, techno, trance) | house, tech house (A5, A6), techno y trance | 5/6 con estilos en publicaciones concretas; tech house en 4/6; techno dominante en A3 y A4 | — |

**Discogs mejora claramente la cobertura de estilos electrónicos:**

- 5/5 canciones con estilo, frente a 4/5 en MB con 1–3 votos.
- **Tech House** aparece en S2 y en la discografía de 4 artistas; en MB no aparecía en ningún caso.
- También aparecen *Minimal Techno*, *Microhouse*, *Tribal House* y *Progressive House*.

**Limitaciones de esos estilos:**

1. Son de lanzamiento o master. En un EP no dicen nada de cada pista.
2. Varían entre ediciones del mismo master (S2, S3 y S4).
3. Un master puede pertenecer a la obra original de otro artista (S4).
4. Los estilos de un artista dependen de la muestra elegida; aquí, las más recientes.

**AcousticBrainz** cubre **1 de 9** grabaciones de MB: la original de *Lovelee Dae* de 1997, con 11 envíos (solo se leyó el primero). Los valores, todos **estimados** con Essentia 2.1-beta1 y los modelos v2.1_beta1:

- 124,16 BPM, tonalidad **B menor** (fuerza 0,67) y duración de 456,6 s, que coincide con los 456 000 ms de MB.
- Los cuatro modelos de género **se contradicen**: `genre_electronic` House (0,40), `genre_dortmund` Electronic (1,00), `genre_rosamerica` **Hiphop** (0,42) y `genre_tzanetakis` **Jazz** (0,31).

Las grabaciones posteriores a 2022 no están cubiertas por diseño.

## 6. Identidad, versiones y homónimos

- **Cambio de nombre (S5):** «Chris Stassy» no era una errata segura. Según el perfil de Discogs, es el nombre que usa el artista desde agosto de 2026. Ninguna base de datos lo resuelve por búsqueda. Confirma la regla de la Fase 1.2: no normalizar en silencio, y tratar las correcciones y los alias como candidatos con confirmación.
- **Homónimos:**
  - Discogs los marca con sufijos («Adrian Mills (2)…(5)», «The Martinez Brothers (2)», «S.A.M. (5)»).
  - **Para A2 confirma que el ID enlazado desde MB apunta al guitarrista de heavy metal.** El Adrián Mills de techno apenas tiene datos en ninguna fuente, así que sigue **ambiguo**.
  - Para S2 deshace la ambigüedad entre los 3 Luciano de MB gracias al perfil del artista, sin validación por ID.
- **Versiones:**
  - Discogs aporta créditos por pista (remezcladores, editores) y ediciones físicas que MB no tenía: el vinilo de PAWSA con el remix de Morales y las 36 ediciones de *Lovelee Dae*.
  - MB tiene versiones que Discogs no (extended y remix de S1).
  - Elegir la edición sigue siendo una interpretación. El script confirma la pista en el tracklist y nunca toma automáticamente el master como fuente de estilos sin comprobar que el artista coincide.
- **Duplicados:** «Sven Vath» (610651) es una entrada aparte de «Sven Väth» con un lanzamiento no oficial.

## 7. Información nueva por fuente

| Fuente | Aporta | No aporta |
|---|---|---|
| **Discogs** | Estilos electrónicos específicos (de lanzamiento), una canción ausente en MB (S2), créditos de remezcla y edición por pista, ediciones físicas, sellos coeditores (Playhouse), perfiles breves con nombre real y relaciones, homónimos explícitos, el cambio de nombre de S5 y discografías más completas (Väth: 1158 entradas frente a 120 en MB) | Validación independiente: los perfiles y estilos los editan usuarios, y 6 de 10 lanzamientos están en «Needs Vote». Tampoco datos a nivel de pista sobre estilos. |
| **AcousticBrainz** | BPM y tonalidad estimados para 1 grabación antigua | Cobertura de música posterior a 2022, géneros fiables y datos verificados. El propio equipo reconoce su baja calidad. |

## 8. Limitaciones legales y técnicas

- **Discogs, legal:**
  - Los géneros y estilos de la API **no están declarados como CC0**.
  - Todo el contenido de la API está sujeto a la regla de **6 horas** de frescura y a no almacenar «más de lo necesario». Una caché propia de larga duración o un índice de estilos entra en conflicto con eso.
  - Atribución con enlace junto a cada dato.
  - Hay usos comerciales prohibidos que afectan al producto: dirigir tráfico a sitios que no son Discogs (por ejemplo, enlaces a tiendas o streaming) y cobrar por funciones que Discogs da gratis.
  - Discogs puede cobrar o revocar el acceso.
  - **Conclusión: no se puede afirmar que el uso comercial de estilos vía API sea viable.**
  - Los **volcados mensuales** se declaran CC0. Son la vía legal a estudiar, pero falta verificar que incluyan géneros y estilos y su coste de proceso.
- **Discogs, almacenamiento en este experimento:**
  - `data/raw/discogs/` (ya sin campos restringidos) y los logs están fuera de Git.
  - `data/results_phase13/discogs_*.json` contiene datos de Discogs: **excluido de Git** al cerrar la fase (solo local). Conviene borrar la caché local cuando ya no haga falta.
- **Discogs, técnicas:**
  - 60 peticiones/min por token.
  - La búsqueda no encuentra nombres nuevos ni con erratas.
  - Hace falta 1 petición por publicación para conocer sus estilos: muestrear la discografía de Väth al completo costaría más de 1000 peticiones.
- **AcousticBrainz:**
  - Proyecto cerrado a datos nuevos desde 2022 y con un cierre total anunciado y no cumplido: puede desaparecer en cualquier momento.
  - API lenta (6–20 s por petición).
  - La licencia CC0 solo consta en un comentario del blog, no en un documento formal revisado.
  - Calidad reconocida como baja.

## 9. Peticiones y errores

| Fuente | Presupuesto | Peticiones de red | Errores | Ritmo |
|---|---|---|---|---|
| Discogs | 150 | **80** (75 en frío + 5 de la ampliación de identidad de artistas en canciones); 83 URL únicas en total con AcousticBrainz | 0 | 1,2 s de intervalo configurado (mínimo medido entre inicios: 1,19 s, unas 50/min). Como mínimo quedaron 12 de 60 peticiones en la ventana; la pausa de seguridad (≤ 3) no llegó a activarse. |
| AcousticBrainz | 10 | **4** (3 consultas masivas + 1 reintento) | 1 timeout (20 s) recuperado al reintentar; 0 fallos finales | Mínimo de 6,5 s entre inicios, porque el servicio es lento |
| MusicBrainz / Wikidata | 0 | 0 | — | No consultados |

## 10. Recomendación provisional

1. **Discogs sí mejora la identificación de estilos electrónicos**: 5/5 canciones con estilo específico, una canción que MB no tenía, Tech House y Minimal donde MB no daba nada, y créditos de versión. Hoy es la mejor fuente evaluada para esta necesidad.
2. **Pero no es viable integrarlo tal cual en el producto por la API**: los estilos no son CC0 en la API, está la regla de 6 h, el almacenamiento limitado, la prohibición de dirigir tráfico a terceros y el riesgo de revocación. Siguiente paso, con decisión humana: **evaluar los volcados CC0 de Discogs** (si contienen géneros y estilos, tamaño, frecuencia y coste de procesarlos) y, si hay dudas, **consultar a Discogs** el uso previsto.
3. **Modelo de datos:** guardar los estilos **por lanzamiento con su procedencia** (ID de Discogs y edición), nunca como atributo de la pista ni del artista. Para un artista, mostrar como mucho una distribución sobre N publicaciones. Descartar los estilos de un master cuyo artista no coincide.
4. **MusicBrainz sigue como columna vertebral de identidad** (Fase 1.2). Los IDs de Discogs enlazados desde MB funcionan bien como puente, salvo con homónimos (A2), que siguen necesitando confirmación.
5. **AcousticBrainz: descartado** como fuente de géneros, BPM o tonalidad (1/9 de cobertura, congelado desde 2022 y baja calidad reconocida). Lo que necesite SetLab (BPM y tonalidad) queda como **problema abierto** para otra fase.
6. Repetir con una muestra mayor antes de decidir: 11 casos son indicativos.
