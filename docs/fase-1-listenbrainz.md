# Fase 1.5 — ListenBrainz

Investigación en [`research/music_sources/listenbrainz/`](../research/music_sources/listenbrainz/README.md). Fecha: 2026-10-16. **Fase cerrada (1.5D)**: conclusión y decisiones definitivas en §10. No toca `mobile/` ni `backend/`. Tiene tres partes: **1.5A**, similitud de artistas en Labs (§1–7); **1.5B**, LB Radio (§8); y **1.5C**, personalización (§9, solo documental).

> **Resultado:** el endpoint de artistas similares de ListenBrainz Labs **sigue disponible** y responde sin clave. Devuelve resultados útiles para 2 de los 4 artistas (Amelie Lens y Ricardo Villalobos). Para Traumer devuelve muy pocos (4) y para PAWSA ninguno. **Recomendación provisional: seguir investigando.** **1.5B:** LB Radio **exige un token de usuario**; sin él responde 401, así que con las condiciones de la fase (sin cuentas ni claves nuevas) no se ha podido obtener ninguna canción (§8). **1.5C:** para la primera versión se recomienda una personalización propia, sin cuentas externas; ListenBrainz queda como importación opcional en el futuro (§9).

## 1. Endpoints, autenticación, límites y uso

| Aspecto | Comprobado (2026-10-16) |
|---|---|
| Similitud | `GET https://labs.api.listenbrainz.org/similar-artists/json?artist_mbids=<MBID>&algorithm=<algoritmo>`. La página de Labs solo documenta los dos parámetros y una lista de algoritmos; el formato de salida no está documentado (se observó en las respuestas). |
| Algoritmo | `session_based_days_7500_session_300_contribution_3_threshold_10_limit_100_filter_True_skip_30`. Es el que usa la página de artista de listenbrainz.org (`entity_pages.py` del repositorio oficial) y figura en la lista de Labs. Su nombre indica un máximo de 100 resultados. |
| Salida observada | Lista JSON de objetos con `artist_mbid`, `name`, `comment` (desambiguación de MusicBrainz), `type`, `gender`, `score` y `reference_mbid`. **`score` es un número entero no normalizado** (de 11 a 185 en esta prueba), así que no es comparable entre artistas. **No incluye géneros.** |
| Identificadores | `GET https://musicbrainz.org/ws/2/artist?query=artist:"<nombre>"&fmt=json` (búsqueda) y `GET https://musicbrainz.org/ws/2/artist/<MBID>?inc=url-rels&fmt=json` (ficha con enlaces externos). |
| Autenticación | Ninguna: Labs y MusicBrainz responden sin clave. La API principal de ListenBrainz usa tokens de usuario opcionales que pueden dar límites más altos; no se ha usado ninguno. MusicBrainz exige un User-Agent con contacto (se lee de `.env` y no se registra). |
| Límites | **MusicBrainz:** de media, 1 petición por segundo por IP; si se excede, responde 503. **API de ListenBrainz:** «never make more than ONE call per second», con cabeceras `X-RateLimit-*` y 429 si se excede. **Labs:** no documenta límites y **no envió cabeceras de límite**. Aquí se usó 1 petición cada 1,1 s. |
| Estabilidad | Labs es un servicio **experimental**: no aparece en la referencia de la API principal (`api.listenbrainz.org`) y no promete estabilidad ni formato. |
| Uso comercial | MetaBrainz pide a las empresas con ingresos (actuales o previstos) apuntarse a un nivel de soporte: Bronze desde 100 $/mes para apps móviles populares y start-ups con producto público; Stealth Start-Up y Non-profit desde 0 $. Fuentes secundarias indican que los datos de escuchas de ListenBrainz son CC0 y que los datos centrales de MusicBrainz son CC0 (las etiquetas son CC BY-NC-SA). **La licencia concreta de los datos de similitud de Labs no se ha podido confirmar en una página oficial: pendiente.** |

Fuentes: [ListenBrainz Labs](https://labs.api.listenbrainz.org/), [Similar Artists Viewer](https://labs.api.listenbrainz.org/similar-artists), [API de ListenBrainz](https://listenbrainz.readthedocs.io/en/latest/users/api/index.html), [límites de MusicBrainz](https://musicbrainz.org/doc/MusicBrainz_API/Rate_Limiting), [niveles de soporte de MetaBrainz](https://metabrainz.org/supporters/account-type) y [`entity_pages.py`](https://github.com/metabrainz/listenbrainz-server/blob/master/listenbrainz/webserver/views/entity_pages.py).

## 2. Identificación de los artistas (MusicBrainz)

| Artista | MBID | Evidencia de identidad |
|---|---|---|
| PAWSA | `202ed573-bcb9-4686-bc98-6fc96b1f6ae9` | Persona, Londres (GB), desambiguación «David Esekhile», enlace a Beatport. La búsqueda por nombre dio **503 dos veces**; el MBID salió de la caché de MusicBrainz de la Fase 1.2 (crédito de «Dirty Cash (Money Talks)») y se confirmó con la ficha. |
| Ricardo Villalobos | `bbd79854-df54-4c1b-b7d6-cf7eea2d0afb` | Única coincidencia exacta: persona, Alemania, nacido el 1970-08-06, «electronic music producer and DJ», con Discogs y Wikidata. Respondió 200 al tercer intento manual, tras dos 503. |
| Amelie Lens | `67db280d-c3e4-49d9-978e-4050f4e209ef` | Única coincidencia exacta: persona, Bélgica, nacida el 1990-05-31, «Belgian techno DJ & producer», con ra.co, Beatport y Discogs. |
| Traumer | `319c89bc-c7a3-4139-8386-a2a5b48b4ed7` | **Hay dos coincidencias exactas.** Se elige la persona de París «house/techno», con ra.co, Discogs y traumer-music.com. Se descarta `TraumeR` (`0950f065-…`, banda brasileña de power metal). |

Riesgo de identidad real: el nombre «Traumer» es ambiguo, y un buscador que tome el primer resultado podría elegir mal.

## 3. Resultados de similitud (1 consulta por artista)

| Artista | Estado | Resultados | Top 10 (nombre · puntuación) |
|---|---|---|---|
| PAWSA | 200 | **0 (lista vacía)** | — |
| Ricardo Villalobos | 200 | 100 | Aphex Twin 185 · Apparat 163 · Floating Points 158 · WK7 138 · KMA 125 · Booka Shade 125 · Red Rack’em 121 · Percussions 120 · Crazy Bald Heads 118 · C++ 115 |
| Amelie Lens | 200 | 99 | Charlotte de Witte 102 · Regal 67 · Umek 61 · Boris Brejcha 56 · Joyhauser 53 · Enrico Sangiuliano 50 · I Hate Models 48 · Spektre 44 · Layton Giordani 42 · ANNA 42 |
| Traumer | 200 | **4** | Hot Since 82 20 · Boris Brejcha 13 · Kölsch 13 · Ten Walls 11 |

Los MBID de cada recomendación están en [`data/results/similar.json`](../research/music_sources/listenbrainz/data/results/similar.json). En ningún caso aparece el propio artista consultado, y todos los `reference_mbid` coinciden con el MBID enviado.

### Revisión de errores e identificadores

- **Errores:** ninguno en Labs (4/4 con HTTP 200). MusicBrainz devolvió 503 de forma intermitente en 5 de 13 peticiones, sin reintento automático.
- **Resultados vacíos o escasos:** PAWSA tiene 0 resultados y Traumer 4, con puntuaciones bajas (de 11 a 20).
- **Posibles errores de identidad en las recomendaciones:** no se ha comprobado cada MBID recomendado. Sí hay una señal en los datos: **KMA** (puesto 5 de Villalobos) lleva la desambiguación «Finnish band». Es posible que las escuchas de otro artista con el mismo nombre se hayan asociado a este MBID. **Pendiente de verificar.**
- **Contexto musical:**
  - Solo se puede juzgar con la desambiguación de MusicBrainz (`comment`), porque la API no da géneros.
  - En Amelie Lens, 6 de los 10 primeros tienen un comentario que menciona techno o que son DJ o productores. La lista es coherente con el contexto «techno» que indicó el usuario.
  - En Villalobos, los tres primeros (Aphex Twin, Apparat, Floating Points) son artistas electrónicos conocidos, pero el resultado no confirma que encajen en «minimal». Sin géneros, esa valoración necesita revisión humana.

## 4. Evaluación para music-discovery

- **Cobertura:** buena para artistas con muchas escuchas en ListenBrainz (Amelie Lens y Villalobos tienen cerca de 100 resultados). Escasa o nula para artistas igual de relevantes en la escena pero con menos escuchas registradas en ListenBrainz (Traumer y PAWSA). En 4 artistas, 2 tienen resultados útiles.
- **Utilidad:** cuando hay datos, las recomendaciones son plausibles y aportan MBID, lo que encaja con MusicBrainz como identificador común (Fases 1.2–1.3). Pero la similitud se basa en sesiones de escucha, no en el estilo: no distingue subgéneros (Villalobos aparece junto a artistas de IDM) y no da géneros con los que filtrar.
- **Puntuación:** sirve para ordenar dentro de un mismo artista, pero no como umbral absoluto ni para comparar entre artistas.

## 5. Limitaciones

- Solo se han probado 4 artistas, con una consulta cada uno y un único algoritmo; no se han comparado los demás algoritmos.
- Labs es experimental: no documenta el formato ni los límites, no envía cabeceras de límite y no garantiza estabilidad.
- La licencia de los datos de similitud y las condiciones comerciales concretas están pendientes de confirmar en una página oficial.
- La búsqueda de MusicBrainz falla de forma intermitente (503). Un flujo real necesita tolerar errores y mantener una caché de MBID.
- La identidad de los artistas puede ser ambigua (Traumer), tanto al buscar como dentro de los datos de escuchas (KMA).

## 6. Recomendación provisional (1.5A; decisión definitiva en §10)

**Seguir investigando; no integrar todavía.** ListenBrainz Labs es una fuente gratuita, sin clave y basada en MBID, prometedora para artistas con muchas escuchas. Pero su cobertura de la escena electrónica más de club es irregular (PAWSA sin resultados), y es un servicio experimental cuya licencia comercial está sin confirmar. Antes de decidir:

1. Probar más artistas.
2. Comparar los demás algoritmos de Labs.
3. Confirmar la licencia y las condiciones comerciales con MetaBrainz.
4. Valorar otras fuentes que complementen la cobertura.

Todo ello sin llamadas adicionales en esta fase.

## 7. Consumo

| Fuente | Peticiones de red | Presupuesto |
|---|---|---|
| ListenBrainz Labs | **4** (una por artista, sin reintentos) | 4 |
| MusicBrainz | 13, de ellas 5 con 503: 2 + 2 búsquedas fallidas y 1 ficha. Hubo una repetición manual solo para Villalobos. | 14 |

Las respuestas originales y los registros se quedan en local (`data/raw/` y `data/logs/`, excluidos de Git); se versionan los resultados en `data/results/`.

## 8. Fase 1.5B — LB Radio

### Documentación (2026-10-16)

| Aspecto | Comprobado |
|---|---|
| Endpoint | `GET https://api.listenbrainz.org/1/explore/lb-radio?prompt=<prompt>&mode=<easy\|medium\|hard>` ([API de ListenBrainz](https://listenbrainz.readthedocs.io/en/latest/users/api/misc.html)). Errores documentados: 400 (parámetros) y 500 (fallo de troi). |
| Prompt | Sintaxis de troi: `entidad:valores:peso:opciones`. Para artistas, `artist:(Nombre exacto en MusicBrainz)` o `artist:(MBID)`. Por defecto añade **artistas similares**; con la opción `nosim` usa solo el artista dado. Hay más entidades (tag, collection, playlist, stats, recs, country…) ([referencia de prompts](https://troi.readthedocs.io/en/latest/lb_radio.html)). |
| Modos | `easy`, `medium` y `hard` dividen cada conjunto ordenado de datos: *easy* toma lo más relevante y *hard* la cola; los modos difíciles dan música menos conocida. |
| Respuesta | JSON `{"payload": {"jspf": <playlist JSPF>, "feedback": [...]}}`. Según troi, las listas globales «contain only MusicBrainz MBIDs» y «Normal music players cannot play these playlists». Es decir, se identifican por **MBID de grabación** y **no traen enlaces de reproducción**. **No se ha podido observar** porque la respuesta no llegó. |
| Autenticación | **Obligatoria.** El código oficial (`explore_api.py`) llama a `ensure_user_token_for_expensive_endpoint()` (`api_tools.py`), que exige la cabecera `Authorization` con token de usuario «due to bad actors and AI scrapers». La documentación de la API no lo menciona. |
| Límites | Límite general de la API (cabeceras `X-RateLimit-*`; en la respuesta, 30 por ventana de 6 s). En el código, además, `LB_RADIO_PER_TOKEN_LIMIT = 5` por ventana para cada token. |
| Uso comercial | El mismo marco que en §1: niveles de soporte de MetaBrainz para empresas con ingresos. **No hay ninguna fuente oficial que confirme permisos comerciales** ni la licencia de las listas generadas. Un token de usuario está ligado a una cuenta personal, lo que no encaja con un servicio de la app. |

### Prueba

- **Diseño:** 1 consulta por artista con `prompt=artist:(<MBID de 1.5A>)` y `mode=easy`, sin token y sin reintentos. Presupuesto: 4.
- **Ejecución:** como el código oficial muestra que el endpoint exige token, se hizo **una sola petición** (PAWSA) para confirmar el error real. Las otras tres darían el mismo 401, así que no se hicieron. Peticiones: **1 de 4**.

| Artista | Estado HTTP | Canciones | Observado |
|---|---|---|---|
| PAWSA | **401** | 0 | `{"code": 401, "error": "Due to bad actors and AI scrapers causing undue traffic on our sites, you need to provide an Auth token for this endpoint. Sorry for this mess."}` |
| Ricardo Villalobos | no consultado | — | Mismo endpoint y misma exigencia de token |
| Amelie Lens | no consultado | — | Ídem |
| Traumer | no consultado | — | Ídem |

**Interpretación:** sin token no se puede evaluar la calidad musical ni la cobertura. Por eso **no se sabe si PAWSA o Traumer mejoran respecto a 1.5A**. Hay un riesgo adicional: el prompt de artista se apoya por defecto en artistas similares, y para PAWSA la similitud de Labs devolvió 0 resultados. **Esto es una hipótesis sin verificar.**

### Comparación 1.5A frente a 1.5B

| | 1.5A: similitud de artistas (Labs) | 1.5B: LB Radio |
|---|---|---|
| Acceso sin clave | Sí | **No** (401 sin token de usuario) |
| Peticiones | 4/4, todas 200 | 1/4, 401 |
| PAWSA | 0 resultados | sin datos (401) |
| Traumer | 4 resultados | sin datos (no consultado) |
| Amelie Lens / Villalobos | 99 / 100 resultados | sin datos (no consultado) |
| Identificadores | MBID de artista | MBID de grabación (según la documentación; no observado) |
| Reproducción | No aplica | Sin enlaces de reproducción (según la documentación) |
| Estabilidad | Labs experimental | API principal, pero con restricción de acceso reciente y explícita |

### Recomendación provisional sobre LB Radio

**No usarlo por ahora y no seguir investigándolo con las condiciones actuales.** Exige un token de usuario y responde 401 sin él. Además, para ser útil en la app habría que resolver los MBID de grabación con otro servicio para poder reproducir, y no hay ninguna fuente oficial que confirme el uso comercial.

Retomarlo solo si se decide de forma explícita usar un token. Ese token tendría que ser de una cuenta de servicio, nunca la cuenta personal del usuario ni dentro de la app, y requiere confirmar antes las condiciones con MetaBrainz. Ampliar el presupuesto o usar un token queda a decisión del usuario.

| Fuente | Peticiones en 1.5B | Presupuesto |
|---|---|---|
| API de ListenBrainz (LB Radio) | 1 (401, sin reintento) | 4 |

## 9. Fase 1.5C — Personalización con ListenBrainz (solo documental)

Revisión documental del 2026-10-16. **Sin llamadas a APIs, sin cuentas y sin claves.** Cuando la documentación no lo dice, se indica como inferencia o como pendiente.

### Qué ofrece ListenBrainz

| Pregunta | Lo que dice la documentación oficial |
|---|---|
| **1. Datos de escucha y estadísticas** | **Escuchas:** `GET /1/user/<usuario>/listens` (hasta 1 000 por petición; la documentación pide no recorrer todo el historial y usar la exportación), además de `listen-count` y `playing-now`. **Estadísticas por usuario** (`/1/stats/user/<usuario>/…`): artistas, discos, grabaciones, actividad de escucha, actividad por artista, por época, por género y hora, mapa de países y *Year in Music*. Rangos de `this_week` a `all_time`. Si aún no están calculadas, responde **204**. Las estadísticas se actualizan a diario con las escuchas nuevas, y las importaciones y escuchas antiguas, los días 1 y 15 de cada mes. |
| **2. Recomendaciones personalizadas** | `GET /1/cf/recommendation/user/<usuario>/recording`: MBID de grabación con `score`, generados por **filtrado colaborativo** a partir de las escuchas. La documentación avisa: «This endpoint is experimental and probably will change in the future». Si no hay recomendaciones generadas, responde 204. Además hay listas automáticas: *Daily Jams* (cada mañana) y listas semanales (los lunes). **No se documenta un mínimo de escuchas** ni la frecuencia de cálculo del filtrado colaborativo: pendiente. |
| **3. Público frente a autenticado** | Las lecturas por nombre de usuario (escuchas, estadísticas, recomendaciones, *feedback*) **no documentan autenticación**, así que, por inferencia, son públicas. Escribir (`submit-listens`, *feedback*) exige un token de usuario. Endpoints «caros» como **LB Radio y popularidad** exigen token desde hace poco (comprobado en 1.5B y en el código de `api_tools.py`). |
| **4. ¿Hace falta cuenta e historial?** | **Sí, las dos cosas.** Todo lo personal va ligado a un usuario de ListenBrainz con escuchas registradas. Sin historial no hay estadísticas ni recomendaciones (204), y las recomendaciones se generan por lotes, no al instante. |
| **5. Importar escuchas** | **Histórico (archivo):** importador en `listenbrainz.org/settings/import/` para el *Extended Streaming History* de Spotify (el usuario lo pide a Spotify y tarda días) y para copias de ListenBrainz. Solo esos 2 formatos ([blog GSoC 2025](https://blog.metabrainz.org/2025/08/30/gsoc-2025-importing-listening-history-files-in-listenbrainz/)). **Continuo:** conectar Spotify o Last.fm en «Connected services». Para una app de terceros, el flujo oficial solo admite **Spotify**, y exige OAuth de MetaBrainz con el *scope* `listenbrainz:connect-services` **aprobado por MetaBrainz** y un email verificado ([connect-music-services](https://listenbrainz.readthedocs.io/en/latest/users/connect-music-services.html)). **Otros:** reproductores y *scrobblers* que envían escuchas, y una API compatible con Last.fm. Enviar las mismas escuchas desde dos fuentes puede **duplicarlas**. |
| **6. Gustos por MBID** | Las estadísticas y recomendaciones devuelven **MBID** de artistas y grabaciones, y el *feedback* se puede consultar para una lista de MBID de grabación. **No hay** un endpoint de «qué opina el usuario de este artista». Tampoco se puede enviar una lista de artistas favoritos y recibir recomendaciones: la entrada es siempre el historial de un usuario. |

### Limitaciones

- **Cobertura:** depende de que los usuarios de ListenBrainz escuchen esa música. En 1.5A, PAWSA no tenía datos y Traumer muy pocos. El filtrado colaborativo hereda el mismo sesgo hacia lo más escuchado.
- **Privacidad:** por inferencia de la API, el historial y las estadísticas son **legibles públicamente por nombre de usuario**. Pedir a nuestros usuarios su nombre de ListenBrainz expone y vincula su historial. **No se ha encontrado** una política oficial específica de ListenBrainz que lo confirme: pendiente.
- **Estabilidad:** las recomendaciones son experimentales, el acceso a endpoints caros se ha restringido recientemente (LB Radio) y Labs no garantiza nada.
- **Licencias y uso comercial:** igual que en §1. No hay una fuente oficial que confirme la licencia de estadísticas y recomendaciones, y MetaBrainz pide un nivel de soporte a empresas con ingresos. El flujo de conexión de servicios necesita **aprobación** de MetaBrainz.
- **Fricción:** el usuario necesita cuenta en ListenBrainz y un historial importado (en el caso de Spotify, días de espera), y las estadísticas y recomendaciones tardan en calcularse.

### Comparación de opciones

| | A. Personalización propia, sin cuentas externas | B. Opcional con ListenBrainz | C. A + B |
|---|---|---|---|
| Qué usa | Artistas favoritos, preferencias de estilo y acciones dentro de la app (guardar, descartar, escuchar, «no me interesa») | Estadísticas y recomendaciones del usuario de ListenBrainz (por nombre de usuario) | A como base y B como señal adicional opcional |
| Funciona desde el primer día | **Sí**: con 3–5 artistas favoritos ya se puede combinar con la similitud de artistas (1.5A) | No: requiere cuenta, historial y cálculo por lotes | Sí, gracias a A |
| Cobertura de electrónica de club | La que tengan nuestras fuentes; el usuario puede añadir lo que no aparezca | Irregular (sesgo hacia lo más escuchado) | Igual que A; B solo suma donde hay datos |
| Privacidad | Datos solo en nuestra app | Vincula un historial público | Igual que B para quien lo active |
| Coste y complejidad | Baja: unas tablas y reglas simples (excluir lo descartado, priorizar similares a los favoritos) | Media: cliente de API, cuentas vinculadas, 204, caché y cambios en endpoints experimentales | La suma de ambas |
| Dependencia externa | Ninguna | Alta y en parte experimental | Acotada a la parte opcional |
| Aporte real | Suficiente para una v1 de descubrimiento | Útil solo para usuarios que ya registran sus escuchas | Marginal hasta que haya usuarios que lo pidan |

### Recomendación

- **Primera versión: opción A.** Personalización propia, sin cuentas externas: artistas favoritos elegidos por el usuario, preferencias de estilo y las acciones dentro de la app. Se apoya en la similitud de artistas por MBID (1.5A) cuando hay datos, y en reglas simples cuando no. **Sin filtrado colaborativo ni aprendizaje automático propio**: con pocos usuarios no hay datos que lo justifiquen.
- **Fases futuras: B como importación opcional y puntual** de gustos de ListenBrainz (p. ej., traer sus artistas más escuchados como favoritos iniciales). Solo si los usuarios lo piden, y después de confirmar la licencia y la privacidad con MetaBrainz. **La opción C** se vería después, si B demuestra valor.
- **No recomendado:** depender de las recomendaciones experimentales de ListenBrainz o del flujo de conexión de Spotify, que requiere aprobación, para la experiencia principal.

Fuentes: [estadísticas](https://listenbrainz.readthedocs.io/en/latest/users/api/statistics.html), [recomendaciones](https://listenbrainz.readthedocs.io/en/latest/users/api/recommendation.html), [API core](https://listenbrainz.readthedocs.io/en/latest/users/api/core.html), [intervalos de actualización](https://listenbrainz.readthedocs.io/en/latest/general/data-update-intervals.html), [conectar servicios](https://listenbrainz.readthedocs.io/en/latest/users/connect-music-services.html), [dumps](https://listenbrainz.readthedocs.io/en/latest/users/listenbrainz-dumps.html), [importación de archivos (GSoC 2025)](https://blog.metabrainz.org/2025/08/30/gsoc-2025-importing-listening-history-files-in-listenbrainz/) y [`api_tools.py`](https://github.com/metabrainz/listenbrainz-server/blob/master/listenbrainz/webserver/views/api_tools.py).

## 10. Fase 1.5D — Conclusión final y cierre

Cierre del 2026-10-16. No se han hecho más consultas a APIs. Peticiones de red de toda la Fase 1.5: Labs **4**, MusicBrainz **13** y LB Radio **1**.

### Hechos comprobados

- El endpoint de artistas similares de ListenBrainz Labs responde sin clave (4/4 con HTTP 200) y devuelve MBID, nombre, desambiguación y una puntuación sin normalizar. **No devuelve géneros.**
- Cobertura con el algoritmo de la web oficial: Amelie Lens 99 resultados, Ricardo Villalobos 100, **Traumer 4** y **PAWSA 0**.
- El nombre «Traumer» es ambiguo en MusicBrainz (hay dos coincidencias exactas). La búsqueda de MusicBrainz devolvió 503 en 5 de 13 peticiones.
- LB Radio (`/1/explore/lb-radio`) **exige un token de usuario**: respondió 401 sin él, y el código oficial lo impone. No se obtuvo ninguna canción.
- Las recomendaciones personalizadas de ListenBrainz se basan en el historial de un usuario con cuenta y están marcadas como experimentales en la documentación.

### Inferencias (no verificadas directamente)

- Las recomendaciones de Labs para Amelie Lens parecen coherentes con el techno, y las de Villalobos son electrónicas, pero no necesariamente «minimal». La valoración usa solo la desambiguación de MusicBrainz y el criterio humano.
- «KMA» («Finnish band») en la lista de Villalobos podría ser un error de identidad en los datos de escucha.
- Las lecturas por nombre de usuario (escuchas, estadísticas, recomendaciones) parecen públicas, porque la documentación no pide autenticación.
- LB Radio probablemente tampoco mejoraría PAWSA, porque por defecto se apoya en artistas similares.

### Cuestiones pendientes

- Licencia oficial de los datos de similitud, estadísticas y recomendaciones, y condiciones comerciales concretas: hay que confirmarlas con MetaBrainz.
- Límites de uso de Labs (no están documentados y no envía cabeceras de límite).
- Política de privacidad específica de ListenBrainz.
- Calidad real de LB Radio (sin evaluar).
- Comportamiento con más artistas y con otros algoritmos de Labs.
- Verificar la identidad de KMA.

### Decisiones definitivas

| Tema | Decisión |
|---|---|
| ListenBrainz Labs | **Fuente complementaria y opcional** de artistas similares. **Nunca será la única fuente** de recomendaciones. |
| LB Radio | **Aparcado**: exige token y no se ha podido evaluar su calidad. |
| Personalización V1 | **Preferencias propias del usuario, artistas favoritos e interacciones sencillas** dentro de music-discovery. |
| Cuenta de ListenBrainz | Integración **pospuesta**. |
| Aprendizaje automático y Spotify | **Ni aprendizaje automático propio ni integración con Spotify en V1.** |

### Riesgos

| Riesgo | Detalle |
|---|---|
| Cobertura irregular de DJs | La similitud depende de las escuchas registradas en ListenBrainz: PAWSA 0 y Traumer 4. La electrónica de club menos escuchada puede quedarse sin resultados. |
| Errores de identidad | Nombres ambiguos en MusicBrainz (Traumer) y posibles asociaciones erróneas en los datos de escucha (KMA). Exige verificar los MBID y no elegir automáticamente el primer resultado. |
| Dependencia de Labs | Servicio experimental: sin formato documentado, sin límites publicados y sin garantía de continuidad. El acceso a endpoints caros ya se ha restringido (LB Radio). |
| Licencias no confirmadas | No hay una licencia oficial confirmada para los datos de similitud ni para las recomendaciones. MetaBrainz pide un nivel de soporte a empresas con ingresos. Los resultados versionados se limitan a los 10 primeros por artista, para respaldar este informe. |
| Límites de API | MusicBrainz admite 1 petición por segundo por IP y responde 503 si se supera, también de forma intermitente. La API de ListenBrainz limita mediante cabeceras y exige token en algunos endpoints. Labs no publica límites. |

### Posibilidades abiertas para la Fase 2 (sin diseñar ni implementar)

- Usar Labs como señal opcional junto a otras fuentes, con caché de MBID y tolerancia a respuestas vacías.
- Comparar otros algoritmos de Labs y ampliar la muestra de artistas.
- Confirmar con MetaBrainz la licencia y las condiciones comerciales.
- Importación opcional y puntual de gustos desde ListenBrainz, si los usuarios lo piden.
- Revaluar LB Radio solo si se decide usar un token de servicio.

### Organización de los resultados

- **Versionado:** `research/music_sources/listenbrainz/` (`run_phase15.py`, `artists.json`, `README.md` y `data/results/` con `identify`, `verify`, `similar` y `radio`) y este informe.
- **Solo local** (`.gitignore`): `data/raw/` (respuestas originales) y `data/logs/` (registro de peticiones), además del `.env` con el contacto del User-Agent.
