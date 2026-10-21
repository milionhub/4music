# T1 — Plan de implementación: primer recorrido real

Ejecuta el contrato de [t0-contrato-datos.md](t0-contrato-datos.md). Plan maestro: [Fase 2, hito T1](music-discovery-fase-2-plan-maestro.md). Está pensado para **un único prompt de implementación**, por bloques, con una validación final.

## 0.5 T1.5 — Artist Content Quality (2026-10-16, pendiente de validación en iPhone)

**Biografías:**

- **Sin plantillas de discografía:** `profile.factual_bio` se sustituye por `identity_bio`, una frase de identidad con datos de Wikidata (ocupación y estilo; p. ej. «Disc-jockey de tech house.»). Sin esos datos, estado vacío discreto.
- **Solo se genera con IA si hay texto descriptivo:** al menos 150 caracteres de Wikipedia o de la web oficial (`sources.sufficient`). Con discografía y metadatos no basta, porque producía listas.
- **Fuentes mejoradas:**
  - Introducción completa de Wikipedia (API TextExtracts).
  - Wikidata: sello (P264), país (P27/P495), grupos (P463/P361), premios (P166) e inicio de actividad (P2031).
  - Web oficial: descripciones JSON-LD de schema.org además de las meta descripciones.
  - Los lanzamientos pasan a contexto secundario (máx. 3, «no enumerar»).
- **Discogs: investigado y no integrado.** Los perfiles existen pero son mínimos (Arapu: 68 caracteres; East End Dubs: 117), y las API Terms imponen frescura de 6 h y almacenamiento mínimo (Fase 1.3A). Además, el plan maestro excluye la API.
- **Prompt v4:** identidad y sonido primero, extensión según las fuentes (breve si son escasas), como mucho 1 título y 2 años, y nada de listas.
- **Validación:** rechaza menciones a fuentes o recuentos («publica desde», «el lanzamiento más reciente»…), listas de títulos o años, años o títulos sin respaldo y fuentes inventadas. El catálogo editorial pendiente de revisión pasa el mismo control (se reescribieron los textos de Cloonee, Traumer, Prospa y Capriati).
- **Groq:**
  - `reasoning_effort: low` e `include_reasoning: false`. Con el razonamiento por defecto, la generación de Dom Dolla salía vacía y daba HTTP 400 `json_validate_failed`.
  - Un único reintento en modo `json_object` si falla la salida estricta.
  - Se guarda el código de error (`rate_limited`, `http_400`, motivo del rechazo…).
  - Tras un 429, pausa global con `Retry-After` (mínimo 60 s) sin llamar a Groq.
- **Caché:**
  - Las biografías válidas de versiones anteriores **se conservan si pasan el control editorial actual**; los fallos antiguos se reintentan con las reglas nuevas.
  - Regeneración selectiva: `python -m app.admin invalidate-bio <MBID>` (`show-bio` muestra el estado). Nunca se borra la caché completa.

**Fotos:**

- `ArtistPhoto` recuerda el fallo por URL, así que vuelve a intentarlo si llega otra foto.
- Explorar pide la foto de los 5 primeros resultados.
- Inicio la pide al acercarse cada tarjeta a la pantalla (al desplazarse), en lugar de cortar en las 8 primeras.
- «Sin foto» se guarda 12 h en el dispositivo y 1 día en el backend.
- MBID canónico: la identidad y P434 usan el MBID real de MusicBrainz, y la foto se guarda con el MBID pedido y con el canónico.

**Validación real (8 artistas):**

| Artista | Biografía mostrada | Foto |
|---|---|---|
| Arapu | estado vacío (solo discografía; sin Wikidata) | no hay autorizada (sin ítem en Wikidata) |
| PAWSA | generada v4, 56 palabras (Wikipedia + Wikidata) | no (ítem sin imagen) |
| Cloonee | editorial reescrita (sin fuente descriptiva para la IA) | no (ítem sin imagen) |
| East End Dubs | estado vacío | no (sin ítem) |
| Dom Dolla | identidad («Músico y productor musical.»): la generación se **rechaza por enumerar años**, incluso con la regla reforzada | sí, CC0 |
| Michael Bibi | regenerada, 42 palabras (la v1 era una lista y se descartó) | sí, CC BY-SA 4.0 |
| Joseph Capriati | editorial reescrita (la v3 generada era una lista) | sí, CC BY 4.0 |
| Traumer | editorial reescrita | no (sin ítem) |

**Pruebas:**

- `pytest`: 49 pruebas.
- `npm test`: 11 pruebas.
- `tsc`: sin errores, en la app y en `tests/`.
- `expo install --check`: sin incompatibilidades.
- `expo export`: el bundle de Android compila.

**Pendientes:**

- Dom Dolla: biografía rechazada por la validación. Podría probarse un reintento corrector que le pase el motivo del rechazo, o aceptar 3 años con fuentes largas; no se hizo para no gastar cuota.
- Fotos de PAWSA, Cloonee, Arapu, East End Dubs y Traumer: solo con permiso documentado en el catálogo editorial.
- Revisión humana del catálogo editorial.

## 0.4 T1.4 — Artist Intelligence: biografías con Groq y fotos sincronizadas (2026-10-16, pendiente de validación en iPhone)

**Biografías** (`app/biography.py`, `app/sources.py`, `app/groq_client.py` y `GET /v1/artists/{mbid}/biography`):

- **Flujo:**
  1. Caché persistente por MBID.
  2. Si no hay, fuentes recopiladas antes de llamar al modelo:
     - MusicBrainz: identidad, origen, lanzamientos recientes, sellos y colaboraciones repetidas.
     - Wikidata: ocupaciones y géneros.
     - Wikipedia: resumen del artículo enlazado al ítem verificado.
     - Web oficial: solo la que enlaza MusicBrainz para ese MBID, si `robots.txt` lo permite, con una página y un extracto acotado.
  3. Comprobación de suficiencia.
  4. Groq (`GROQ_MODEL`, por defecto `openai/gpt-oss-20b`) con salida `json_schema` estricta.
  5. Validación.
  6. Almacenamiento.
- **Garantías:**
  - El modelo solo puede citar ids de las fuentes enviadas (S1…); si cita otra, el texto se rechaza.
  - Se rechazan las frases prohibidas («MusicBrainz», recuentos, «registros»…), los años y títulos que no estén en las fuentes y las longitudes fuera de rango.
  - Prompt v3: no puede describir el sonido sin una fuente que lo diga.
  - La clave no se registra ni se devuelve, y el frontend no recibe datos del modelo.
- **Prioridad en la ficha:**
  1. Editorial revisada.
  2. Generada válida.
  3. Editorial pendiente de revisión.
  4. Factual, que ya no incluye recuentos ni menciones a bases de datos.

  El perfil se muestra al instante. Si la biografía puede generarse (`bio_pending`), la app la pide aparte y muestra un esqueleto, sin bloquear la ficha.
- **Caché persistente:** SQLite de la biblioteca estándar en `backend/data/` (fuera de Git).
  - Biografía válida: 90 días. Sin fuentes suficientes: 14. Rechazada: 7. Error o cuota: 1 hora.
  - Un candado por MBID evita generaciones duplicadas simultáneas.
  - Groq tiene timeout de 25 s, un solo reintento ante 429/503 y como mucho 2 generaciones a la vez.
- **Fuentes no integradas:** sellos y biografías promocionales, por falta de un enlace verificable y de condiciones de uso claras. Sin *scraping*.
- **Prueba real:**
  - Joseph Capriati: generada con éxito, 78 palabras, fuentes MusicBrainz y Wikidata.
  - PAWSA: generada con Wikipedia en la primera ronda. En la segunda, Groq devolvió error al encadenar varias generaciones, compatible con el límite gratuito de 8 000 tokens por minuto; la ficha usó la biografía editorial de respaldo y se reintentará pasada 1 hora.

**Fotos sincronizadas:**

- **Causa:** cada tarjeta copiaba la caché al montarse y nadie le notificaba las fotos resueltas después por la ficha. Las pestañas nativas no se desmontan, Explorar no mostraba fotos y la caché no sobrevivía a cerrar la app.
- **Solución:** almacén único y observable por MBID (`mobile/src/state/artist-images.ts`, con `useSyncExternalStore`).
  - Persiste en el dispositivo con la clave nueva `md.images.v1`; las de favoritos no cambian.
  - Una petición por MBID y como mucho 2 simultáneas.
  - Los fallos temporales no se guardan.
  - En el backend, las fotos resueltas también se persisten: `/image` no vuelve a consultar MusicBrainz.

| Artista | Foto autorizada |
|---|---|
| Luciano (DJ) | sí: CC BY-SA 3.0 (relación «image» de MusicBrainz) |
| Joseph Capriati | sí: CC BY 4.0 (Wikidata P18) |
| Paco Osuna | sí: CC BY-SA 2.0 (Wikidata P18) |
| PAWSA, Cloonee | no: el ítem de Wikidata no tiene imagen |
| Traumer, Prospa, Priku | no: no tienen ítem en Wikidata |

**Validación T1.4:**

- `pytest`: 45 pruebas (`tests/test_biography.py`: generación, rechazo de fuentes inventadas, reutilización, errores de Groq sin bucles, concurrencia y persistencia de fotos).
- `npm test`: 11 pruebas.
- `tsc`: sin errores, en la app y en `tests/`.
- `expo install --check`: sin incompatibilidades.
- `expo export`: el bundle de Android compila.
- Prueba real: biografías de Groq y fotos de los 8 artistas.

## 0.3 T1.3 — Motor de recomendación, biografías y cierre funcional (2026-10-16, pendiente de validación en iPhone)

**Fuentes de similitud investigadas (sondas acotadas con datos reales):**

| Fuente | Resultado |
|---|---|
| ListenBrainz Labs `similar-artists` (sin token) | Funciona. **Cobertura irregular** para la escena club: PAWSA 0 resultados en los 3 algoritmos; Cloonee 1–3 (Dom Dolla, SIDEPIECE, Noizu); Paco Osuna 10 (Barem, Marc Houle, Mathias Kaden…); Joseph Capriati ~20 (Adam Beyer, Alan Fitzpatrick… junto a ruido como Theo Parrish o Mory Kanté). Se usan dos algoritmos: el histórico de la web de ListenBrainz y el de los últimos 5 años. |
| LB Radio y `/popularity` | **401 sin token** (comprobado en 1.5B y T1.2): descartados sin token. |
| Relaciones de sello en MusicBrainz (`label-rels`) | Casi vacías para estos DJs: descartadas. |
| **Sellos de los lanzamientos** (MusicBrainz, CC0) | **Señal de escena útil**: Solid Grooves Records da Michael Bibi para PAWSA. Es ruidosa en sellos grandes o antiguos, como Big Beat con R&B de los 90; se filtra por época y tamaño. |
| Créditos compartidos en lanzamientos | Útiles solo si se repiten; un único crédito suele ser un vocalista invitado o un *sample* acreditado. |

**Motor nuevo (`app/recommend.py`, determinista, sin IA):**

- **Candidatos:**
  - Afinidad de escucha (Labs).
  - Sello compartido: los 2 sellos principales de la semilla, solo con lanzamientos de la **misma época** y **sin la propia semilla**.
  - Lanzamientos conjuntos.
- **Fuerzas justificadas en el código:**
  - Afinidad: entre 0,5 y 1.
  - Sello: entre 0,55 y 0,70 si es pequeño, menos si es grande, y 0,30 con un solo lanzamiento.
  - Colaboración: 0,30 con 1 lanzamiento y 0,50 con 2 o más.
- **Combinación «noisy-OR»:** por semilla y entre semillas, de modo que varios favoritos suman. Umbral de 0,45: una coincidencia aislada no recomienda.
- **Diversidad:** penalización ×0,85 por cada tarjeta de la misma semilla. Sin azar.
- **Explicación:** etiqueta según la evidencia («Afinidad de escucha», «Sello compartido», «Colaboración», «Varios de tus favoritos») y una frase breve. La puntuación y las señales se conservan en la respuesta.

**Evaluación con datos reales** (`backend/eval/evaluate_discovery.py`; los objetivos no se usan en el motor):

| Caso | Objetivo | Posición | Negativos (no deben salir) |
|---|---|---|---|
| PAWSA | Michael Bibi | **1.º** (sello compartido: Solid Grooves) | Nate Dogg y Malachiii: no salen |
| Cloonee | Josh Baker | **no aparece**: no está en Labs ni en los sellos muestreados | Jomanda: no sale |
| Paco Osuna | Ilario Alicante / Marco Carola | **no aparece** / **11.º** | — |
| Joseph Capriati | Marco Carola / Ilario Alicante | **no aparecen** | Arnold Jarvis: no sale |
| Paco Osuna + Capriati | ambos | **no aparecen**. Adam Beyer sale 4.º como «Varios de tus favoritos» | Arnold Jarvis: no sale |

**Conclusión honesta:** el motor ya no depende de créditos incidentales, y donde hay señal real recomienda artistas de la misma escena (PAWSA y Capriati). Pero **la relevancia sigue siendo insuficiente** en 3 de los 4 casos de referencia, por falta de cobertura en las fuentes gratuitas, y Labs mete ruido en artistas con mucha audiencia. **TrackDNA no se puede dar por cerrado en relevancia.**

**Fichas:**

- **«Sobre el artista»** siempre visible:
  - Editoriales (6, pendientes de revisión humana): PAWSA, Luciano y Joseph Capriati (Wikipedia, Wikidata y MusicBrainz); Cloonee, Traumer y Prospa (solo hechos de MusicBrainz y Wikidata: lanzamientos, sellos, colaboradores y origen).
  - Factual automática (lugar, discografía documentada, álbumes, colaboradores y estilos) para el resto.
  - Vacío discreto si no hay nada.
- **Colaboraciones:** 2 por defecto, y una tercera solo con 2 o más lanzamientos conjuntos; en filas compactas con miniatura.
- **Lanzamientos:** bloque de texto de altura fija.
- **Más escuchadas:** ver «Pendientes».

**Validación T1.3:**

- `pytest`: 38 pruebas (motor en `tests/test_recommend.py`, contrato en `tests/test_api.py` y reglas de la ficha en `tests/test_profile.py`).
- `npm test`: 11 pruebas.
- `tsc`: sin errores, en la app y en `tests/`.
- `expo install --check`: sin incompatibilidades.
- `expo export`: el bundle de Android compila.
- Evaluación real: la tabla anterior.

**Pendientes:**

- **Relevancia:** hace falta una fuente de similitud con mejor cobertura de la escena club (decisión de producto: token de ListenBrainz, otra fuente con licencia compatible o curación editorial explícita).
- **«Más escuchadas»:** no aparece porque ListenBrainz devuelve **401 sin token**. No es un fallo de interfaz ni de normalización; se activa con `LISTENBRAINZ_TOKEN`.
- **Fotos:** siguen sin foto PAWSA, Cloonee, Traumer, Prospa y Priku. Ni Wikidata/Commons (comprobado también por P180) ni MusicBrainz tienen una imagen libre; solo se resolverá con fotos aportadas con permiso al catálogo editorial.
- **Colaboraciones en la ficha:** pueden incluir vocalistas o *samples* acreditados (Nate Dogg en PAWSA, Lindy Layton en Cloonee), porque MusicBrainz no los distingue en el crédito.
- **Revisión humana** de las 6 biografías editoriales.

## 0.2 T1.2 — Rediseño de la ficha de artista (2026-10-16, pendiente de validación visual en iPhone)

**Contrato:** `GET /v1/artists/{mbid}` devuelve un **perfil modular** (`ArtistProfileResponse`), con los módulos identidad, imagen, estilos, biografía, más escuchadas, lanzamientos recientes, colaboraciones y plataformas. Cada módulo tiene su estado y puede faltar sin bloquear la ficha; solo la identidad de MusicBrainz es imprescindible. Las tres fuentes (MusicBrainz, Wikimedia y ListenBrainz) se consultan en paralelo, cada una con su límite de ritmo y su caché. Es la misma pantalla y el mismo endpoint para Inicio, Explorar, Guardados y, en el futuro, Carteles, partiendo siempre de un MBID.

**Comprobación de cobertura previa** (sonda acotada) **y resultado final**, con el mismo endpoint:

| Artista | Foto | Estilos (Wikidata) | Sobre el artista | Lanzamientos recientes | Colaboraciones |
|---|---|---|---|---|---|
| PAWSA | no (ítem de Wikidata sin foto) | tech house | editorial | 5 singles 2024–2026 | 4 |
| Cloonee | no (ítem sin foto) | tech house | factual | 5 (álbum y singles 2026) | 4 |
| Traumer | no (sin ítem en Wikidata) | — | — | 5 (EP y álbumes) | 4 |
| Luciano (DJ, `6f8d9d66…`) | **sí**: relación «image» de MusicBrainz, CC BY-SA 3.0 | Minimal techno | editorial | 5 | 4 |
| Priku | no (sin ítem) | — | — | 2 | 2 |
| Prospa | no (sin ítem) | — | — | 5 | 4 |
| Joseph Capriati | **sí**: Wikidata P18, CC BY 4.0 | techno | factual | 5 | 4 |

La búsqueda exacta de «Luciano» devuelve primero a un **cantante de reggae** homónimo: la ficha solo es correcta si se elige el MBID del DJ por su descripción.

**Fuentes y reglas:**

- **Fotos** (`app/images.py`, reutilizable desde un MBID), en este orden:
  1. Catálogo editorial con permiso documentado (`app/data/editorial.json`, campo `photo`; hoy vacío).
  2. Relación «image» de MusicBrainz hacia Wikimedia Commons.
  3. P18 del ítem de Wikidata. El ítem se encuentra por el enlace de MusicBrainz o por **búsqueda inversa `haswbstatement:P434=<MBID>`**, y en ambos casos debe declarar el mismo MBID.

  Solo se aceptan CC0, dominio público, CC BY y CC BY-SA, con autor para atribuir. Sin foto válida se usa un póster tipográfico propio, no una imagen generada. No se hace *scraping* de ninguna web.
- **Estilos:** solo el género P136 de Wikidata (CC0), del ítem verificado. Nunca los tags de MusicBrainz ni inferencias.
- **Biografía**, sistema híbrido (`app/editorial.py`, `app/profile.py`):
  1. **Editorial:** texto original de 70–110 palabras del catálogo, con fuentes y `reviewed: false` hasta la revisión humana. Hay dos, PAWSA y Luciano, redactados a partir de Wikipedia (CC BY-SA), Wikidata y MusicBrainz, sin copiar.
  2. **Factual:** frase breve generada solo con ocupaciones y géneros de Wikidata más el lugar de MusicBrainz, cuando aporta algo que la cabecera no tiene.
  3. **Nada**, si no hay datos.

  Sin IA de pago.
- **Más escuchadas (ListenBrainz):** `/1/popularity/top-recordings-for-artist` **responde 401 sin token**, comprobado en T1.2, igual que LB Radio. El módulo está implementado, con orden por recuento real, fusión de versiones equivalentes (los remixes de otros artistas se mantienen aparte), portada de CAA y «Buscar en Spotify» como búsqueda explícita. **Solo se activa con un `LISTENBRAINZ_TOKEN`** (gratuito) en `backend/.env`; sin él no se hace ninguna petición y la sección no aparece.
- **Lanzamientos recientes:** grupos de lanzamientos de MusicBrainz acreditados al artista, de tipo Single, EP o Album y con fecha de primera publicación. Se excluyen recopilatorios, DJ mixes, directos, emisiones, «Various Artists» y lanzamientos sin fecha. Se muestran hasta 5, con su tipo, y enlazan al registro de MusicBrainz.
- **Portadas:** Cover Art Archive (`/release-group/{mbid}/front-250`), con una placa cromática si no hay portada. **La CAA no concede licencia**: su política dice «Use the images at your own risk» y «Be respectful of the rights of the artists and labels». Se usan solo para identificar el lanzamiento y se pueden desactivar con `COVER_ART=off`. **Decisión pendiente** antes de cualquier uso comercial.
- **Colaboraciones destacadas** (máx. 4), por orden de prioridad:
  1. Lanzamiento conjunto (grupo de lanzamientos coacreditado, sin recopilatorios).
  2. «feat.» en el crédito.
  3. Coautoría de una grabación.

  Si no hay ninguna, se muestran relaciones musicales documentadas bajo el título «Conexiones documentadas». Los remixes solo cuentan cuando el remezclador figura en el crédito, porque no se consultan relaciones de grabación.
- **Plataformas:** solo enlaces musicales reales de MusicBrainz, uno por plataforma. El resto de enlaces y las fuentes, en «Información técnica», plegada.

**Validación T1.2:**

- `pytest`: 32 pruebas, con reglas nuevas en `tests/test_profile.py` y contrato y fallos parciales en `tests/test_api.py`.
- `npm test`: 11 pruebas.
- `tsc`: sin errores, en la app y en `tests/`.
- `expo install --check`: sin incompatibilidades.
- `expo export`: el bundle de Android compila.
- Prueba real única: la tabla anterior.

**Pendientes:**

- Validación visual en iPhone.
- Revisión humana de las 2 biografías editoriales.
- Decidir si se crea un token de ListenBrainz.
- Decisión legal sobre Cover Art Archive.
- Fotos de DJs sin ítem en Wikidata: solo con fotos aportadas con permiso al catálogo editorial.
- Relevancia del descubrimiento (sigue siendo la prioridad del siguiente hito).

## 0.1 T1.1 — Correcciones tras la prueba en iPhone (2026-10-16, pendiente de revalidar en el móvil)

**Errores corregidos:**

| Problema observado | Causa | Corrección |
|---|---|---|
| La bienvenida reaparecía tras cerrar Expo Go | `LibraryProvider` guardaba dentro de los *updaters* de React con escrituras **asíncronas**. Al terminar se lanzaban dos escrituras seguidas (estilos con `pending` y luego `completed`), React puede ejecutar los *updaters* dos veces y las escrituras podían completarse en orden inverso, dejando `pending`. Los favoritos se salvaban porque usan una sola escritura. | Se persiste **después del commit** (efecto), con `setItemSync`, que es ordenado. Al salir de la bienvenida hay **una sola** actualización (`completeOnboarding`). Lectura síncrona antes de decidir la navegación. Mismas claves `md.*.v1`, sin migración ni borrado. |
| `Encountered two children with the same key` (Cloonee) | MusicBrainz devuelve la misma URL con varios tipos de relación (Qobuz: «purchase for download» + «streaming»), y la clave era la URL | El backend fusiona los enlaces por URL canónica. En la app, todas las listas usan `withUniqueKeys` |
| «No se pudieron cargar las grabaciones» (Cloonee) | **503 temporal de MusicBrainz**: reproducido varias veces en T1.1; las grabaciones de Cloonee sí existen (121) | Una sola repetición cortés ante 503/429 (respeta `Retry-After`, máx. 3 s). Estado por sección (`ok`, `empty`, `error` con `provider_unavailable` o `provider_bad_response`) con mensajes distintos y opción de reintentar |
| Repeticiones en el descubrimiento | Varias versiones de una pista (extended, original…) contaban como evidencias distintas | Las evidencias se deduplican por título |

**Mejoras:**

- **Fotos de artistas** (`GET /v1/artists/{mbid}/image`, `app/images.py`):
  - Cadena: MBID → enlace a Wikidata documentado en MusicBrainz → el ítem confirma el mismo MBID (P434) → imagen (P18) → licencia en Commons.
  - Solo CC0, dominio público, CC BY y CC BY-SA (se rechazan NC y ND), siempre con atribución (autor · licencia · enlace al archivo). Nunca se busca por nombre.
  - Sin imagen válida se mantiene el avatar cromático.
- **Ficha nueva:**
  1. Cabecera con foto o gradiente.
  2. Identificación.
  3. Favorito.
  4. **«Lanzamientos documentados»** (grupos de lanzamientos acreditados al artista, ordenados por **fecha de primera publicación**, no por fecha de alta en MusicBrainz, con su tipo: Single, Álbum, Remezclas, Recopilatorio…) y **«Colaboraciones acreditadas»** (grabaciones con crédito compartido, sin repetir versiones).
  5. Conexiones.
  6. **«Escuchar y comprar»**: Spotify, SoundCloud, Beatport, Apple Music… detectados por dominio; el resto en «Más enlaces», con etiquetas legibles.
  7. Información técnica y procedencia, plegada.
- **Guardados:** rejilla con foto o avatar. Abrir con una pulsación; quitar con pulsación larga o «⋯», con confirmación.
- **Bienvenida:** botón principal en un pie fijo que sube con el teclado. Las pantallas sin pestañas respetan el área segura inferior.

**Validación T1.1:**

- `pytest`: 21 pruebas superadas.
- `npm test` (`node --test`, sin dependencias nuevas): 9 pruebas de regresión superadas (bienvenida, claves, enlaces y datos ausentes).
- `tsc`: sin errores, en la app y en `tests/`.
- `expo install --check`: sin incompatibilidades.
- `expo export`: el bundle de Android compila.
- Prueba real única de la ficha y la foto: Amelie Lens tiene foto CC BY-SA 4.0 y 71 lanzamientos; Cloonee, 47 lanzamientos y sin foto, porque MusicBrainz no lo enlaza con Wikidata.

**Limitaciones y siguiente prioridad:**

- **Relevancia del descubrimiento (prioridad del próximo hito).** Compartir un crédito no implica afinidad: p. ej., Lizzo aparece junto a Amelie Lens (crédito compartido). No se ha cambiado el algoritmo; la interfaz insiste en que son créditos documentados, no similitud sonora.
- **Cobertura de fotos.** Depende de que MusicBrainz enlace a Wikidata y de que el ítem tenga imagen libre; muchos DJs no la tienen. No se muestran fotos en las tarjetas de descubrimiento, porque exigiría una consulta por tarjeta.
- **Wikimedia.** Las miniaturas se cargan directamente desde los servidores de Wikimedia, con un User-Agent propio. Si Wikimedia limitara ese uso, habría que servirlas a través del backend.

## 0. Estado: implementado, pendiente de validación en el móvil (2026-10-16)

**Decisión de producto posterior a T0:** el onboarding prioriza los artistas favoritos buscados en MusicBrainz. Los estilos son opcionales, declarados por el usuario, de una lista editorial propia (`src/constants/styles.ts`), y no influyen en las recomendaciones.

**Implementado:**

- **Backend:**
  - `app/config.py`, `musicbrainz.py` (cliente con `urllib`, candado de 1,1 s, caché de 24 h y 500 entradas, copia caducada marcada como `stale`, sin reintentos), `normalize.py`, `discovery.py`, `schemas.py` y `api.py`, incluido desde `main.py`.
  - `.env.example`.
  - Pruebas sin red: `tests/test_api.py`, `tests/test_musicbrainz.py` y `tests/fixtures/mb.py`.
- **Mobile:**
  - Navegación: pila raíz con `(tabs)` (Inicio, Explorar, Guardados y Perfil, con `NativeTabs`), `onboarding` y `artist/[mbid]`.
  - Datos y estado: `state/library.tsx` (contexto con escrituras funcionales), `storage/local-store.ts` (`expo-sqlite/kv-store`, claves versionadas, datos corruptos → vacío), `services/api-client.ts` y `music.ts`, y `hooks/use-remote.ts`.
  - Interfaz: `components/ui.tsx` y `music.tsx` (Chromatic Underground con gradientes nativos `experimental_backgroundImage`, tipografía condensada del sistema y acento por MBID).
  - Se retiraron los componentes de la plantilla de Expo. La comprobación de `/health` de la Fase 0 se conserva en Perfil.

**Cambios respecto al contrato de T0** (ya reflejados en el código):

1. **Favoritos y semillas son la misma lista.** Los artistas elegidos en la bienvenida se guardan como favoritos, y los 5 más recientes son las semillas del descubrimiento. `MusicalPreference` queda en `{onboarding, declared_styles}`.
2. **Hasta 5 semillas por consulta** (T0 decía 3), para aprovechar varios favoritos. En frío son hasta 10 peticiones a MusicBrainz, unos 12–15 s; la app espera hasta 45 s.
3. **La ficha incluye `connections`**, calculadas con los mismos datos y sin peticiones extra, y `recordings_source` (`null` si las grabaciones fallan, sin tumbar la ficha).
4. **El descubrimiento devuelve `sources`** (procedencia de cada consulta) en lugar de una sola `source`. Las evidencias se recortan a 3 por motivo, con `evidence_count` total.
5. **Descartes y favoritos se filtran en la app** (no se envía `exclude`, aunque el backend lo admite), para no repetir consultas al descartar.

**Validación ejecutada:**

- `pytest`: 13 pruebas sin red, todas superadas.
- `npx tsc --noEmit`: sin errores, tras regenerar los tipos de rutas con `expo start`.
- `npx expo install --check`: sin incompatibilidades.
- `npx expo export --platform android`: el bundle compila.
- `npm audit`: sin cambios (ver [dependencias.md](dependencias.md)).
- **No hay lint configurado:** `npx expo lint` intentó instalar ESLint y se revirtió.
- **Sin probar en dispositivo.**

## 1. Objetivo y alcance

**Recorrido:** bienvenida opcional → elegir artistas semilla (y, si se aprueba, estilos declarados) → tarjetas de descubrimiento con motivo verificable → ficha del artista → guardar como favorito → verlo en Guardados tras reiniciar la app.

**Dentro de T1:**

- Los tres endpoints `/v1` del contrato, con caché, límite de ritmo y errores tipados.
- Persistencia local de preferencias, favoritos y descartes.
- Estados de carga, vacío y error en cada pantalla.

**Fuera de T1:**

- Carteles y SetLab.
- Colecciones e historial (T3).
- Control de sorpresa y Home personalizado completo (T2).
- Mapa de relaciones (T3).
- Identidad visual Chromatic Underground definitiva (T4): en T1 basta un estilo oscuro sencillo y legible.
- IA, previews, géneros, imágenes, cuentas, ListenBrainz y Spotify.

## 2. Bloques de implementación (en orden)

### Bloque 1 — Backend: proveedor MusicBrainz

- `backend/app/config.py`: lee `MUSICBRAINZ_CONTACT` del entorno (`python-dotenv`, ya instalado) y se crea `backend/.env.example`.
- `backend/app/musicbrainz.py`:
  - Cliente con `urllib.request`: User-Agent con contacto, timeout de 10 s y candado global de 1,1 s entre peticiones.
  - Caché en memoria con TTL de 24 h, unas 500 entradas y servicio de lo caducado si el proveedor falla.
  - Sin reintentos.
  - Excepciones propias: `NotFound`, `Unavailable` y `BadResponse`.
- `backend/app/normalize.py`: convierte las respuestas de MusicBrainz en Artist, Recording, SearchResult y DiscoveryCard, con `null` cuando falta un dato y Source en cada respuesta.
- La lógica de descubrimiento va en `backend/app/discovery.py`. Une coartistas y relaciones musicales, excluye las semillas, los excluidos y las relaciones personales, y ordena de forma determinista. Debe ser una función pura sobre datos ya normalizados, fácil de probar.

### Bloque 2 — Backend: API `/v1`

- Rutas en `backend/app/api.py` (un `APIRouter`, incluido desde `main.py` sin tocar `/health`):
  - `GET /v1/artists/search`
  - `GET /v1/artists/{mbid}`
  - `GET /v1/discovery`
- Modelos de respuesta Pydantic (`backend/app/schemas.py`) y el formato de error común del contrato.

### Bloque 3 — Backend: pruebas (sin red)

`backend/tests/`, con un proveedor falso inyectado que usa respuestas de MusicBrainz guardadas como *fixtures* JSON pequeñas y anonimizadas.

### Bloque 4 — Mobile: datos y almacenamiento

- `npx expo install expo-sqlite`.
- `src/services/api-client.ts`: generaliza el patrón de `health.ts` (timeout y errores tipados) y reutiliza `getApiConfig`.
- `src/services/music.ts`: funciones `searchArtists`, `getArtist` y `getDiscovery`, con tipos TypeScript del contrato en `src/types/music.ts`.
- `src/storage/local-store.ts`: `expo-sqlite/kv-store` con claves versionadas `md.preferences.v1`, `md.favorites.v1` y `md.discarded.v1`. Si el contenido está corrupto, se reinicia vacío.

### Bloque 5 — Mobile: pantallas y navegación (Expo Router)

- `src/app/onboarding.tsx`: bienvenida con «Omitir», búsqueda de artistas con la desambiguación visible (1–3 semillas) y, si se aprueba, los estilos declarados.
- `src/app/index.tsx` (Inicio):
  - Sin semillas: invitación a elegir un artista.
  - Con semillas: tarjetas con motivo y evidencia, y las acciones explorar, guardar y descartar.
  - Estado vacío por semilla sin conexiones.
  - Error con «Reintentar». La comprobación de `/health` actual se reutiliza como diagnóstico dentro del estado de error.
- `src/app/artist/[mbid].tsx`: ficha con datos, enlaces, grabaciones (sin llamarlas «top»), botón Guardar y enlace «Ver en MusicBrainz».
- `src/app/saved.tsx` (Guardados): favoritos guardados en el dispositivo, con opción de quitar.
- Pestañas: **Inicio y Guardados.** Se elimina la pantalla de plantilla `explore.tsx`. Explorar y Perfil (decisión 2) llegan en hitos posteriores.
- En el primer arranque, la redirección al onboarding depende de `preferences.onboarding`.

### Bloque 6 — Documentación y verificación

- README: variables nuevas y ejecución.
- `docs/dependencias.md`: `expo-sqlite` y resultado de `npm audit`.

## 3. Archivos previsiblemente afectados

| Área | Archivos |
|---|---|
| Backend nuevos | `app/config.py`, `app/musicbrainz.py`, `app/normalize.py`, `app/discovery.py`, `app/schemas.py`, `app/api.py`, `.env.example`, `tests/test_api.py`, `tests/test_discovery.py`, `tests/fixtures/*.json` |
| Backend modificados | `app/main.py` (incluir el router) |
| Mobile nuevos | `src/app/onboarding.tsx`, `src/app/artist/[mbid].tsx`, `src/app/saved.tsx`, `src/services/api-client.ts`, `src/services/music.ts`, `src/types/music.ts`, `src/storage/local-store.ts` y componentes de tarjeta y estados |
| Mobile modificados | `src/app/index.tsx`, `src/app/_layout.tsx`, `src/components/app-tabs.tsx` (y `.web.tsx`), `package.json`, `package-lock.json` |
| Mobile eliminados | `src/app/explore.tsx` (plantilla) |
| Documentación | `README.md` y `docs/dependencias.md` |

## 4. Dependencias y riesgos

| Tipo | Detalle | ¿Bloquea? |
|---|---|---|
| Dependencia nueva | `expo-sqlite`, instalada con `npx expo install`. Incluida en Expo Go | No |
| Configuración manual | `MUSICBRAINZ_CONTACT` en `backend/.env` (email o URL; puede ser el mismo contacto de `research/music_sources/.env`) | Sí, para probar con datos reales; las pruebas no lo necesitan |
| Decisión de producto | Estilos del onboarding: lista propia declarativa u omitirlos (T0 §8) | No: se implementa la propuesta simple salvo que se indique otra cosa |
| Cobertura | Muchos DJs tendrán 0–7 conexiones (PAWSA 0). El recorrido debe funcionar igual, con estado vacío y la opción de elegir otra semilla | No (riesgo de utilidad, conocido) |
| Proveedor | 503 intermitentes de MusicBrainz (5 de 13 en la Fase 1.5; 1 de 6 en T0) | No: errores tipados, caché y reintento manual |
| Latencia | Descubrimiento en frío de 7–8 s con 3 semillas | No: indicador de progreso; caché |
| Licencia | Uso comercial de la API de MusicBrainz sin resolver con MetaBrainz | No para T1 (0 €, sin ingresos) |

## 5. Criterios de aceptación

1. `GET /v1/artists/search?q=traumer` devuelve varios resultados con su desambiguación, y la app los muestra para que el usuario elija.
2. La ficha de un MBID válido muestra nombre, desambiguación, tipo, país o área, enlaces y grabaciones. Los campos ausentes no aparecen como texto inventado.
3. Con semillas Amelie Lens o Traumer, Inicio muestra al menos una tarjeta, y cada tarjeta cita su motivo (coartista o relación) con evidencia.
4. Con una semilla sin conexiones (p. ej. PAWSA), Inicio muestra un estado vacío explicativo, sin errores ni tarjetas de relleno.
5. Las tarjetas descartadas no vuelven a aparecer. Los favoritos y las preferencias persisten tras cerrar y reabrir la app.
6. Con el backend parado o MusicBrainz caído, la app muestra un error comprensible con «Reintentar», sin colgarse.
7. «Omitir» en la bienvenida lleva a Inicio con la invitación a elegir un artista, y las preferencias se pueden modificar después.
8. Pasan `pytest`, `npx tsc --noEmit` y `npx expo lint`. `npx expo install --check` no da errores y `npm audit` queda documentado.

## 6. Pruebas críticas (sin red)

- **Normalización:** campos ausentes → `null`/`[]`; fechas parciales intactas; Source presente.
- **Descubrimiento:** coartistas a partir del crédito de artista; exclusión de semillas, excluidos y relaciones personales; orden determinista; semilla sin conexiones → `seeds_without_connections`; semilla con error → `seeds_failed`.
- **API:** 422 por MBID inválido y por más de 3 semillas; 404; 503 `provider_unavailable` sin caché y respuesta `stale: true` con caché caducada; 503 `provider_not_configured`.
- **Límite de ritmo:** dos llamadas seguidas respetan el intervalo mínimo (con un reloj o un `sleep` inyectado).
- `/health` sigue pasando.

## 7. Comprobación manual en el móvil

1. Configura `backend/.env` con `MUSICBRAINZ_CONTACT`, arranca el backend con `--host 0.0.0.0` y la app con Expo Go (README, sección iPhone).
2. Primer arranque: aparece la bienvenida. Pulsa «Omitir» y comprueba que Inicio invita a elegir un artista.
3. Busca «Traumer» y comprueba que aparecen las dos opciones (house/techno y power metal) con su desambiguación. Elige la de París.
4. Inicio muestra tarjetas con su motivo («coacreditado en …»). Abre una tarjeta y comprueba la ficha y el enlace a MusicBrainz.
5. Guarda el artista, descarta otra tarjeta, cierra la app por completo y reábrela: el favorito sigue en Guardados y la tarjeta descartada no vuelve.
6. Añade PAWSA como semilla y comprueba el estado vacío honesto.
7. Detén el backend y comprueba el error con «Reintentar». Vuelve a arrancarlo y reintenta.
