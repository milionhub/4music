# Carteles — Fase 3.0: especificación funcional y técnica

Fecha: 2026-10-21. Documento de diseño: no implica código. Base: `docs/fase-1-ia-carteles.md` (Fase 1.4), `research/poster_ai/` y el estado actual de `mobile/` y `backend/`.

## Estado (2026-10-23)

| Subfase | Estado |
|---|---|
| 3.1 Captura y análisis | **Cerrada**. Tests automáticos, 1 llamada real desde el backend (Now Here: 6/6 artistas, evento y fecha correctos, 1,7 s, 2 437 + 491 tokens) y validación manual en iPhone: captura, envío y análisis de Now Here y Movement Detroit. |
| 3.2 Revisión y recuperación | **Cerrada**. Tests del modelo y validación manual en iPhone: Now Here (13 artistas, 3 escenarios) con edición correcta; Movement Detroit con 44 actuaciones detectadas y varios B2B agrupados correctamente. |
| 3.3 Biblioteca local | **Cerrada**. Tests de la lógica pura y validación manual en iPhone: las ediciones persisten, Movement Detroit queda guardado en la biblioteca y los eventos se reabren correctamente. No se ha probado matar la app durante el análisis. |
| 3.4 Artistas y música | **Cerrada** (2026-10-22). `pytest` con MusicBrainz simulado, tests de Node y validación manual en iPhone con MusicBrainz real: Carl Craig B2B Cajmere abre a cada artista por separado; las vistas rápidas cargan imagen, información y canciones; perfil completo y TrackDNA funcionan; Colette muestra 8 homónimos sin enlace automático y la elección manual persiste al reabrir; Paco Osuna correcto. |
| 3.5 Experiencia editorial | **Cerrada** (2026-10-23), con los ajustes 3.5B y 3.5C. Tests de Node y `pytest`, y validación manual en iPhone: portadas editoriales de Now Here y Movement, biblioteca y explorador, vista rápida «Sobre el artista», fotografías permitidas y atribuciones accesibles, apertura y reapertura de la hoja sin cortes, cambio entre artistas B2B y navegación a perfiles y TrackDNA. Falta la comprobación en Android (pasa a 3.6). |
| 3.6 | Sin empezar. |
| 3.7 | Sin empezar (añadida al plan el 2026-10-23). |

**Decisiones de 3.5**:
- **Paleta** (`lib/poster-art.ts`):
  - Los colores guardados (`palette.seeds`) se validan: se descartan los hex inválidos, los casi negros o blancos y los grises.
  - Se ajustan a la paleta más cercana de `PALETTES`, que ya tiene contraste WCAG comprobado. Un cartel de fondo oscuro usa las paletas oscuras.
  - Sin colores útiles, la paleta se elige por `seedOf(fingerprint ?? id)`.
  - Se deriva siempre de lo guardado: es estable y no reescribe eventos. No se añadió `palette.key`.
- **Portada** (`components/poster-cover.tsx`):
  - Cuatro familias propias (`billboard`, `ticket`, `stamp`, `column`), con la composición y la tipografía elegidas por la misma semilla.
  - Solo datos guardados: nombre, fecha y lugar si existen, recuentos del line-up y nombres en el orden del cartel, sin tamaños decrecientes porque no hay `tiers`.
  - Miniatura que abre el cartel completo. Nunca hay texto sobre el color decorativo `pop`.
- **Explorador** (`lib/poster-explore.ts`, `components/poster-lineup.tsx`):
  - `FlatList` con la barra de filtros fija.
  - Una fila por actuación; en un B2B, cada nombre abre su vista rápida.
  - El estado de identidad es un signo de ancho fijo, así que resolver artistas no mueve las filas.
  - Filtros de día, escenario, horario (solo horas propias, `timeScope: 'set'`) y estilo. Cada uno aparece solo si separa algo.
- **Estilos**: el filtro de estilo usa los estilos documentados del perfil, que se guardan en `artist.styles` al abrir la vista rápida. No hay búsquedas masivas, así que el filtro aparece a medida que se exploran artistas. Si cambia la identidad, los estilos se borran.
- **Vista rápida → Artist Spotlight (3.5B, 2026-10-23)**:
  - Foto solo si `verifiablePhoto`: licencia libre conocida, sin NC ni ND, página de origen y autor cuando hace falta, o catálogo editorial con autor. Si no, cartel tipográfico. El crédito completo se abre con un toque.
  - Estilos documentados, «Sobre el artista» y «Explorar perfil y música». Sin canciones ni lanzamientos (están en el perfil completo), sin fecha de nacimiento, lugar de registro ni evidencias internas.
  - Texto (`artistSpotlight`, `lib/poster-quick.ts`): determinista, sin LLM ni peticiones extra; todo llega en `GET /v1/artists/{mbid}`, por MBID (un homónimo elegido a mano trae su texto). Prioridad: biografía del perfil (editorial revisada o generada y validada antes, nunca al abrir) → introducción de Wikipedia en español del ítem verificado (nuevo campo `summary`, misma petición que ya se hacía para los géneros, literal y atribuida, «Extracto adaptado» si se recorta) → descripción de Wikidata en español. En los dos últimos casos se añade una frase con relaciones documentadas que el texto no menciona (origen, inicio de actividad, sellos fundados o dirigidos, proyectos, integrantes), en formas neutras.
  - Solo frases completas hasta ~110 palabras. No hay mínimo: con pocos datos, una frase; sin datos, se dice. Los textos en inglés no se muestran sin traducir.
- **3.5C (2026-10-23)**:
  - Hoja que se quedaba a media altura al reabrir: la animación de entrada (`SlideInDown`) estaba en el mismo nodo que se ajustaba al contenido; con la caché caliente, la ficha llegaba durante la animación y la hoja conservaba su altura inicial. Ahora se anima un marco de tamaño fijo (zona segura superior → borde inferior) y la tarjeta interior se ajusta al contenido (`maxHeight: '100%'`), desplazando a partir de ahí. Cada artista del B2B empieza arriba.
  - Créditos fuera del flujo: botón ⓘ junto a «Sobre el artista» que abre «Fuentes y créditos» (`spotlightCredits`): autor, fuente, licencia con enlace a sus condiciones, atribución del texto y si es un extracto adaptado.
- **Biblioteca**:
  - Franja con los colores de los carteles guardados.
  - «Por revisar» antes que «Biblioteca».
  - Tarjetas enmarcadas con la paleta del evento y botón de acciones (editar o eliminar).
  - Estado vacío con los tres pasos.

**Pendiente para 3.6** (además de lo anotado abajo):
- Revisión visual en Android (no se ha probado): portadas, biblioteca, explorador, vista rápida y su hoja, y Atrás del sistema.
- Revisión visual en iPhone con las 4 portadas con nombres largos, la barra de filtros fija y el cartel ampliado (Now Here y Movement ya validados).
- Ampliación con pellizco del cartel original: hoy solo encaja la imagen completa.
- Jerarquía del line-up (`tiers`): sin ella, la portada no destaca a ningún artista.

**Decisiones técnicas de 3.4**:
- **Resolución** (`backend/app/poster_identity.py`): `POST /v1/posters/resolve` (1–20 nombres, en serie al ritmo del cliente de MusicBrainz).
  - Regla de §7 sin excepciones: un único candidato con nombre o alias exacto tras normalizar y `score ≥ 95`.
  - Homónimos → `ambiguous`. La desambiguación (DJ, house, techno…) solo ordena y se señala como «Escena electrónica».
  - Sin coincidencia exacta → `none`. Los nombres parecidos (similitud ≥ 0,85) se ofrecen como «¿Quizá…?». El nombre impreso nunca se corrige.
  - Caché: la del cliente (24 h) y el almacén SQLite existente (`poster_resolve_v1`: 7 días; «sin identidad», 1 día). Los fallos no se guardan y, si MusicBrainz cae, el resto del lote queda en `error` sin más peticiones.
  - Discogs no interviene: ningún nombre de cartel tiene id de Discogs.
- **Canciones**: sin `LISTENBRAINZ_TOKEN`, `top_tracks` llega vacío. `GET /v1/posters/artists/{mbid}/tracks` devuelve hasta 5 grabaciones propias con fecha (MBID de grabación → `track/[mbid]`), por fecha y sin rellenar. Reutiliza la consulta del perfil, ya en caché.
- **Móvil**:
  - `lib/poster-identity.ts` (lógica pura). `link` amplía el modelo de 3.3 con campos opcionales: `name`, `candidates`, `evidence`, `origin` y `query`. Los eventos guardados siguen siendo válidos.
  - Lo elegido o dejado sin identificar a mano (`origin: 'user'`) no lo cambian ni la resolución, ni un reanálisis, ni un renombrado. Renombrar sí invalida un enlace automático.
- **Progresiva** (`hooks/use-poster-resolution.ts`):
  - Lotes de 4, uno cada vez, solo con la pantalla enfocada. Se puede pausar.
  - El artista que abre el usuario va en su propia petición.
  - Cada resultado se aplica sobre el evento recién leído del almacenamiento.
- **Vista rápida** (`components/poster-artist.tsx`):
  - Hoja superpuesta, no `Modal` (decisión de §11): el perfil y TrackDNA se apilan encima y, al volver, la hoja, el día elegido y el scroll siguen igual.
  - Atrás en Android cierra la hoja.
  - Un B2B abre una hoja con un selector por artista.
  - Muestra la foto solo si el perfil la trae con licencia; si no, el cartel tipográfico de `identityFor`.
- **Aviso `suspicious_name`**: solo cifras y 10 o más (`9999999999`), mayoría de símbolos, o más de 48 caracteres o 7 palabras. No señala `999999999`, `2562`, `808 State`, `Future.666`, `Âme` ni `&ME`.

**Pendientes detectados en la validación (para fases posteriores)**:
- ~~Nombres sospechosos como `9999999999` pasan sin aviso~~: resuelto en 3.4 (`suspicious_name`).
- Posibles errores de transcripción (p. ej. `PETER GROCE`): desde 3.4 se sugieren nombres parecidos de MusicBrainz sin corregir el impreso. Queda comprobarlo con MusicBrainz real en 3.6.
- La foto en la vista rápida contradice la regla de v5 «sin fotos de artistas en la interfaz». Se añadió por petición expresa de 3.4: hay que confirmar si se mantiene.

**Mejoras anotadas para 3.5** (tras la validación de 3.4):
- Presentación editorial de las fotografías y de sus créditos.
- Sustituir en la vista rápida los datos biográficos poco útiles.
- Elegir canciones más representativas sin inventar popularidad (sin datos de escuchas, hoy solo hay orden por fecha).
- Mejorar la jerarquía visual, la navegación y el explorador del evento.
- Mejorar la extracción y conservación del año cuando está impreso en el cartel.
- 3.6: validar exhaustivamente los B2B y la recuperación de respuestas parciales (`continue`, JSON cortado).

**Decisiones técnicas tomadas en 3.1–3.3**:
- **Modelo**: `qwen/qwen3.8-27b` sigue activo (comprobado con `GET /models` el 2026-10-21). Se configura con `GROQ_VISION_MODEL`.
- **Groq**: método `GroqClient.vision` con `json_object`, `reasoning_effort: none`, timeout de 60 s y sin reintentos. Una respuesta cortada no lanza error: se repara.
- **Endpoint**: `POST /v1/posters/analyze` recibe JSON con base64 (no hace falta `python-multipart`).
  - Valida el formato por bytes mágicos (JPEG, PNG, WebP) y limita a 4 MB.
  - Aplica un límite diario por IP en memoria (`POSTER_DAILY_LIMIT`, 30 por defecto).
  - No guarda la imagen.
  - El prompt compacto de Fase 1.4 incluye ahora `colors`, colocado antes de los bloques para que un corte no lo pierda.
  - Prompts adicionales para los modos `continue` y `region`.
- **JSON cortado** (`repair_json`): conserva el prefijo más largo que termina en un objeto cerrado. Un bloque sin su lista de artistas completa se descarta, nunca se rellena.
- **Avisos**: se calculan en el móvil (`reviewFlags`, lógica pura) y no se guardan, salvo `model_uncertain`. Confirmar o editar un dato lo protege (`meta.locked`) y deja de señalarse.
  - El nombre del evento solo genera `possible_brand` si coincide exactamente, para no marcar al cabeza de cartel de «NOW HERE BY PACO OSUNA».
- **Reanálisis por zona**: 5 franjas fijas con solape (superior, centro, inferior, izquierda y derecha), recortadas con `expo-image-manipulator`. No hay recortador libre: se descartó por frágil.
- **Persistencia**:
  - Claves `md.posters.index.v1` y `md.poster.<id>.v1`. Imagen (máximo 2048 px, JPEG 0,85) y miniatura (480 px) en `Documents/posters/<id>/`.
  - La ruta se calcula al vuelo, porque en iOS puede cambiar entre versiones de la app.
  - Huella: MD5 del archivo elegido (`File.info({ md5 })`) y, como respaldo, el `assetId` de la galería.
- **Pendiente para 3.5**: la jerarquía del line-up por tamaño (`tiers`). Por ahora el orden es el del cartel.

## 1. Visión y alcance de Carteles V1

Carteles convierte la foto de un cartel real (fiesta o festival) en una ficha de evento explorable que lleva a los artistas y a su música. No es un OCR, ni una agenda obtenida de internet, ni un sistema de venta de entradas.

- **Entra en V1**:
  - Captura desde galería o cámara.
  - Extracción con Groq a través del backend.
  - Revisión humana.
  - Ficha editorial del evento con explorador y filtros.
  - Vista rápida de artista con enlace a su perfil y a TrackDNA.
  - Biblioteca local.
- **Fuera de V1**:
  - Cuentas y sincronización.
  - Compartir eventos.
  - Búsqueda de eventos en internet.
  - Entradas y avisos.
  - Planificador personal de horarios (SetLab u otros).
  - Guardar canciones de Discogs.
  - Cambios en Inicio, TrackDNA, Guardados y Perfiles.
- **Principio**: lo que no está impreso o confirmado por el usuario vale `null`. La IA solo propone; la verdad la fija el usuario.

## 2. Decisiones de producto aprobadas (cerradas)

| # | Decisión | Consecuencia técnica |
|---|---|---|
| 1 | Experiencia completa: evento, fecha, lugar, artistas, B2B, días, escenarios, horarios, perfiles y TrackDNA | Modelo con días, escenarios y actuaciones; todo opcional y `null` si falta |
| 2 | Portada editorial + explorador práctico | La ficha tiene cabecera generativa y debajo una lista filtrable |
| 3 | Vista rápida de artista en el contexto del evento | Hoja inferior; sin perfil inventado si no hay identidad |
| 4 | Revisión inteligente | Avisos deterministas; los datos sin avisos no exigen revisión uno a uno |
| 5 | Biblioteca automática | Persistencia local; reabrir sin llamar a Groq; las ediciones se conservan |
| 6 | Explorador con filtros: día, escenario, horario y estilo documentado | Filtros visibles solo si hay datos; orden del cartel; un B2B es una sola actuación |
| 7 | Identidad visual inspirada en el cartel | Paleta estable guardada con el evento y alternativa determinista |
| 8 | Pantalla Carteles: Portada → Analizar → Biblioteca | Pestaña propia; sin duplicar Inicio |
| 9 | Festivales de varios días | Selector de día solo si hay 2 o más; lo que no tiene día queda en «Todo» |
| 10 | Recuperación inteligente | Borrador persistente, continuación o reanálisis por región, fusión que respeta lo editado |

## 3. Flujo de usuario

```
Carteles ─► Analizar ─► Captura (galería | cámara) ─► Previsualización ─► Análisis
   ▲                                                         │ (borrador guardado al recibir la respuesta)
   │                                                         ▼
Biblioteca ◄── Evento ◄── Confirmar ◄── Revisión (dudas, editor, continuar o reanalizar región)
                  │
                  └─► Vista rápida de artista ─► Perfil completo (artist/[mbid]) ─► canción ─► TrackDNA (track/[mbid])
```

Si el cartel ya está en la biblioteca (misma huella), se ofrece abrir el evento existente antes de gastar una llamada.

## 4. Pantallas, navegación y estados

Rutas nuevas con expo-router, en el mismo `Stack` raíz que `artist/[mbid]` y `track/[mbid]`:

| Ruta | Pantalla | Estados |
|---|---|---|
| `(tabs)/posters` | **Carteles**: portada editorial, botón Analizar y biblioteca en cuadrícula de miniaturas | vacío (portada + llamada a analizar), con eventos, borradores marcados «Por revisar», error de lectura del almacenamiento |
| `poster/new` | **Captura y análisis** en una sola ruta con máquina de estados | `pick` (galería o cámara) → `preview` (recorte, rotación, confirmar) → `analyzing` (progreso por fases) → `failed` (motivo y reintento manual) · si sale bien, `router.replace` a la revisión |
| `poster/[id]/review` | **Revisión inteligente**, también como editor de un evento guardado | resumen · dudas · editor de evento, artistas y actuaciones · incompleto (botones «Continuar análisis» y «Reanalizar zona») · confirmar |
| `poster/[id]` | **Evento**: portada, explorador, filtros y cartel original (modal con zoom) | normal · sin programación (solo line-up) · filtros sin resultados |
| hoja dentro de `poster/[id]` | **Vista rápida de artista** | cargando · enlazado (estilos, descripción, 3–5 canciones) · candidatos (elegir homónimo) · sin identificar (solo nombre leído, botón «Buscar en TrackDNA») · error de red |

- **Pestaña**: se añade un `NativeTabs.Trigger` «Carteles» entre TrackDNA y Guardados en `(tabs)/_layout.tsx`. Es el único cambio en archivos existentes de navegación.
- **Vuelta al evento**: la hoja es estado de `poster/[id]`, reflejado en el parámetro `?artist=<id local>` con `router.setParams`.
  - «Perfil completo» hace `router.push('/artist/<mbid>')`. Al volver atrás, la pantalla del evento sigue montada en la pila y la hoja reaparece abierta.
  - Desde el perfil, una canción abre `track/[mbid]` como hoy. Cada «atrás» deshace un paso.
  - Cerrar la hoja borra el parámetro.
- **Hoja**:
  - Recomendado: `presentation: 'formSheet'` con detents de react-native-screens (ya instalado), si se comporta bien en Expo Go con iOS y Android.
  - Si no, componente propio con Reanimated y Gesture Handler (ya instalados). Se decide en 3.4 (§11).
- **Plataformas**:
  - Galería y cámara con permisos bajo demanda. Si se deniega, se explica el motivo y se enlaza a Ajustes.
  - Atrás del sistema en Android equivale a cerrar la hoja y después la pantalla.
  - En el iPhone se respetan las áreas seguras (`status-bar-scrim` existente).

## 5. Modelo de datos propuesto

Dos modelos relacionados: **`PosterExtraction`** (respuesta bruta auditada, Pydantic, no se edita) y **`PosterEvent`** (evento del usuario, TypeScript, editable). `fromExtraction` y `mergeExtraction` (puras, `mobile/src/lib/poster-model.ts`) los convierten.

```ts
type Origin = 'ai' | 'user';                       // procedencia del dato
type Flag = 'similar_name' | 'odd_spelling' | 'not_in_catalog' | 'possible_brand' | 'collective'
  | 'block_time' | 'year_not_printed' | 'possible_merge' | 'incomplete' | 'model_uncertain';
interface Meta { origin: Origin; flags: Flag[]; locked: string[]; printed: string | null } // locked = campos editados a mano

interface PosterEvent {
  schema: 1; id: string;                           // id local (uuid); nunca ligado a cuentas
  fingerprint: string | null;                      // huella de la imagen (deduplicación)
  status: 'draft' | 'partial' | 'confirmed';
  name: string | null; dateText: string | null; location: string | null; meta: Meta;
  image: { file: string; thumb: string; width: number; height: number; bytes: number };
  days: { id: string; label: string; date: string | null; order: number; meta: Meta }[];  // date ISO solo con año impreso
  stages: { id: string; name: string; meta: Meta }[];
  artists: PosterArtist[];                         // personas o colectivos, una vez por evento
  sets: PosterSet[];                               // actuaciones
  palette: { source: 'poster' | 'fallback'; key: string; seeds: string[] };
  analysis: { model: string; calls: number; incomplete: boolean; lastError: string | null; at: string };
  createdAt: string; updatedAt: string;
}
interface PosterSet {
  id: string; artistIds: string[];                 // 1 = individual, ≥2 = B2B/B3B (una sola actuación)
  connector: string | null;                        // «B2B», «B3B», «&», tal como está impreso
  dayId: string | null; stageId: string | null; block: string | null;   // p. ej. «THURSDAY NIGHTTIME»
  start: string | null; end: string | null;        // «HH:MM» locales sin zona horaria
  timeScope: 'set' | 'block' | null;               // la hora de bloque no es la hora de cada DJ
  endsNextDay: boolean;                            // end < start: cruza medianoche
  tier: number | null; order: number;              // jerarquía (1 = cabeza de cartel) y orden en el cartel
  meta: Meta;
}
interface PosterArtist {
  id: string; name: string; meta: Meta;
  link: { status: 'pending' | 'linked' | 'ambiguous' | 'none';
          catalog: 'musicbrainz' | 'discogs' | null; refId: string | null;   // MBID o discogs:artist:<id>
          candidates: { refId: string; name: string; disambiguation: string | null }[];
          evidence: string | null; origin: Origin } ;                         // por qué se enlazó
  styles: string[] | null;                         // copia de estilos documentados del perfil, para filtrar sin red
}
```

- **Artistas y actuaciones**:
  - Una persona aparece una sola vez en `artists` y puede estar en varias `sets` (otro día u otro escenario).
  - Un B2B es un único `PosterSet` con varios `artistIds`.
- **Ausencias**: todo lo ausente es `null`. Nunca se guarda «desconocido» ni se deducen años o zonas horarias.
- **Lado del backend**:
  - `PosterExtraction` mantiene el **esquema compacto** de Fase 1.4: `event_name`, `dates[{text, iso}]`, `location`, `stages`, `sessions[{date, label, stage, time, artists}]`, `artists`, `individual_times`, `b2b`, `uncertain`, `unreadable_text`.
  - Añade `colors` (2–5 hex visibles) y `tiers` (opcional, nombres en orden de tamaño tipográfico).
  - Añade también `review[]` (avisos de la auditoría determinista), `complete: bool` y `usage`.

## 6. Arquitectura y reutilización

| Responsabilidad | Dónde | Reutiliza | Nuevo |
|---|---|---|---|
| A. Ingesta | móvil | `expo-file-system` (ya en el árbol, se fijará con `npx expo install`) | `expo-image-picker` y `expo-image-manipulator` (Expo, gratuitos); hasta 2048 px de lado mayor, JPEG con calidad 0,85, miniatura de 480 px; acepta JPEG, PNG, WebP y HEIC (convertidos a JPEG); máximo 4 MB tras normalizar |
| B. Extracción | backend `POST /v1/posters/analyze` (JSON con base64: evita `python-multipart`) | `groq_client.py` (clave en `backend/.env`, semáforo, errores y `incomplete`); prompt compacto, `validate_compact` y `audit_extraction` de `research/poster_ai/poster_schema.py`, que se trasladan a `backend/app/posters.py` | Método de visión en `GroqClient`: imagen + `json_object` + `reasoning_effort: none` (el actual `structured` solo admite texto y `json_schema`); `GROQ_VISION_MODEL` en `.env.example`; sin guardar la imagen en el servidor |
| C. Normalización y validación | backend (estructura) + móvil (avisos que dependen de la biblioteca) | `normalize.py` (limpieza), auditoría de horas y años de Fase 1.4 | Avisos deterministas (§7), reparación tolerante de JSON truncado |
| D. Corrección | móvil | componentes `ui.tsx` y `sheet.tsx` | Editor de revisión y `mergeExtraction` respetando `locked` |
| E. Resolución | backend `POST /v1/posters/resolve` (hasta 20 nombres por petición) | `MusicBrainzClient.search_artists` + caché `store`, alias, `discogs_tracks.linked_artist` | Regla de enlace automático estricta (§7) |
| F. Descubrimiento | móvil | `GET /v1/artists/{mbid}` (`styles`, `bio`, `top_tracks`, `recent_releases`), `artist/[mbid]`, `track/[mbid]`, `/v1/tracks/search`, favoritos y preferencias de `state/library.tsx` | Vista rápida; motivo visible de cada canción («Más escuchada», «Lanzamiento reciente») y de cada destacado («En tus favoritos») |
| G. Persistencia | móvil | `expo-sqlite/kv-store` (`storage/local-store.ts`), parsers tolerantes como `lib/preferences.ts` | Claves `md.posters.index.v1` y `md.poster.<id>.v1`, archivos en `documentDirectory/posters/` |

No hay segundo catálogo de canciones: la música se obtiene siempre de los perfiles y de TrackDNA existentes.

## 7. B2B, horarios, incertidumbre y correcciones

- **B2B**:
  - Se crea un `PosterSet` por cada entrada de `b2b`, ligado a la sesión en la que aparecen sus miembros.
  - Los miembros dejan de aparecer como actuaciones individuales en ese mismo bloque.
  - Un colectivo con miembros entre paréntesis es un solo artista, con el aviso `collective` para que el usuario decida si los separa.
  - En el editor se puede unir y separar: seleccionar actuaciones → «Unir en B2B»; en un B2B → «Separar».
- **Horarios**:
  - La hora de una sesión se guarda con `timeScope: 'block'` y la UI la muestra como «Bloque desde 22:00», nunca como hora de cada DJ.
  - Las horas individuales solo cuentan si están impresas junto al nombre (`individual_times`, tras la auditoría).
  - `endsNextDay` se calcula solo cuando hay inicio y fin.
  - El orden dentro del día respeta el orden impreso, no se reordena por hora deducida.
- **Fechas**: `date` (ISO) solo si el año está impreso en esa fecha; si no, se conserva `label`. Un rango general («3-7 SEPTEMBER») no crea días que no están en el cartel.
- **Avisos de revisión**: son deterministas. `uncertain` del modelo se usa como un indicio más (`model_uncertain`), porque casi nunca lo marca.

| Aviso | Regla |
|---|---|
| `similar_name` | Dos nombres del evento con similitud ≥ 0,85 (posible duplicado o errata) |
| `odd_spelling` | Mezcla de dígitos y letras (`5UNIVERSOS`), un solo carácter, mayúsculas irregulares (`REELow`) o diacríticos raros |
| `possible_brand` | Coincide con el nombre del evento, del lugar o de un escenario, o con una lista corta de ruido (`presents`, `tickets`, `@`, `www`, año pegado: `IBIZA26`) |
| `block_time`, `year_not_printed` | Auditoría de Fase 1.4 (horas repetidas o iguales al inicio de bloque, año deducido) |
| `possible_merge` | Sesión con el doble de artistas que la mediana del cartel, o el mismo escenario con un día ausente entre bloques |
| `not_in_catalog` | Aviso suave tras la resolución: ningún candidato con nombre o alias exacto |
| `incomplete` | La respuesta se cortó (`finish_reason: length`) o se cortó la continuación |

- Nombre del evento y lugar siempre se presentan como «compruébalo» (fallaron 2/3 y 1/3 en Fase 1.4).
- **Revisión rápida**: los artistas sin avisos se agrupan en un bloque plegado «N nombres sin dudas», que se puede abrir y corregir si hace falta.
- **Bloqueos manuales**:
  - Cualquier edición añade el campo a `meta.locked`.
  - Un artista o actuación creado a mano tiene `origin: 'user'`.
  - Borrar lo que propuso la IA queda registrado en `analysis` (lista de `printed` descartados), para que un reanálisis no lo resucite.
- **Resolución de identidad**:
  - Solo se enlaza de forma automática si hay **un único** candidato de MusicBrainz cuyo nombre o alias coincide exactamente tras normalizar, con `score ≥ 95`, y ningún otro con el mismo nombre normalizado.
  - Con homónimos queda `ambiguous`, y la vista rápida muestra los candidatos con su desambiguación.
  - Discogs se usa solo como evidencia (enlace URL MusicBrainz ↔ Discogs mediante `linked_artist`), sin perfiles nuevos.
  - Un artista sin enlace se muestra solo con su nombre leído.

## 8. Persistencia local y recuperación

- **Orden de escritura**:
  1. La imagen normalizada y la miniatura se copian a `documentDirectory/posters/<id>/` (fuera de la caché que el sistema puede borrar).
  2. Se escribe `md.poster.<id>.v1`.
  3. Se escribe el índice `md.posters.index.v1` (id, nombre, fecha, miniatura, paleta, estado y `updatedAt`).
  - Las escrituras de Carteles **devuelven el error** en lugar de ignorarlo como hoy `write()`: si fallan, se muestra «No se pudo guardar» y el borrador sigue en memoria.
  - Al arrancar, el índice se reconstruye desde las claves si no cuadra, y se borran las carpetas huérfanas.
- **Borrador inmediato**: en cuanto llega la extracción, el evento se guarda como `draft` (o `partial`). Un cierre de la app, un timeout posterior o un fallo de red no pierden nada, y reabrir no llama a Groq.
- **Duplicados**:
  - `fingerprint` es el MD5 del archivo elegido, con `File.md5` de expo-file-system (§11); como respaldo se usa el `assetId` de la galería.
  - Si ya existe, se ofrece «Abrir evento» o «Analizar de nuevo». La segunda opción fusiona con `mergeExtraction` y no crea un duplicado.
- **Tamaño**: unos 0,5–1 MB por evento (imagen de 2048 px) y unos 30 KB de JSON para 54 artistas. No hay límite fijo. La biblioteca muestra el espacio usado y se puede borrar un evento (borra su carpeta y su clave).
- **Recuperación**:
  - Si falla **antes** de la respuesta (red, 429, timeout, clave), no hay borrador: se muestra el motivo y se ofrece reintentar a mano. No hay reintentos automáticos que gasten cuota.
  - Si la respuesta llega **truncada**, el backend repara el JSON parcial (solo conserva sesiones completas) y devuelve `complete: false`. Se guarda `partial`.
  - **«Continuar análisis»**: una llamada nueva con la misma imagen y las etiquetas de las sesiones ya leídas, que pide solo las que faltan (`mode: continue`).
  - **«Reanalizar zona»**: el usuario marca un rectángulo sobre el cartel, la app lo recorta con `expo-image-manipulator` y el backend lo analiza con `mode: region`. El resultado entra como propuesta.
  - **Fusión**: `mergeExtraction` nunca toca campos en `locked` ni recupera lo descartado. Los datos nuevos que contradicen a los existentes se presentan como sugerencias.
  - **Presupuesto**: como máximo 3 llamadas por cartel (1 completa + 2 de recuperación), controlado en el móvil. En el backend, un límite diario por IP en memoria y el semáforo de `groq_client`.

## 9. Dirección artística

- **Coherencia**: el mismo sistema que TrackDNA e Inicio: tipografías de `artist-identity.ts` (Anton, DM Serif, Abril, Syne), superficies y tintas con contraste WCAG ≥ 4,5:1 (`contrast`, `surfaces`) y secciones `SheetSection`/`SheetHead`.
- **Paleta del cartel**:
  - El modelo devuelve 2–5 colores visibles en la **misma llamada**, sin coste extra.
  - El móvil los valida (hex), descarta los casi negros o blancos y **los ajusta a la paleta más cercana** de `ART_PALETTES`/`PALETTES`, que ya garantizan el contraste.
  - Se guarda `key` y no se recalcula nunca.
  - **Alternativa determinista**: `seedOf(fingerprint ?? id)` sobre las mismas paletas. Es gratuita y estable.
- **Portada del evento**:
  - Composición generativa (`stack`/`band`/`orbit`/`split`, como en TrackDNA) con el nombre del evento en tipografía gigante y fecha y lugar en mono.
  - Los 3 primeros niveles del line-up van en cuerpo decreciente.
  - El cartel original no es el fondo: aparece como miniatura enmarcada que se puede abrir.
- **Explorador**:
  - Filas por actuación: nombre o nombres unidos por el `connector` impreso, y escenario, bloque y hora como chips.
  - Los B2B van en una sola fila con los dos nombres pulsables.
  - Los filtros van en una banda de chips horizontal: Día, Escenario, Horario (franjas a partir de horas impresas) y Estilo (solo con estilos documentados en 2 o más artistas).
  - El orden inicial es `tier` y después `order`.
- **Pantalla Carteles**: portada editorial propia (un evento reciente en grande, o un mensaje en el estado vacío), botón Analizar y cuadrícula de miniaturas con la paleta del evento como marco. No reutiliza las portadas de Inicio.

## 10. Plan 3.1–3.7

| Subfase | Objetivo y alcance | Archivos probables | Criterios de aceptación | Pruebas | Fuera |
|---|---|---|---|---|---|
| **3.1 Captura y análisis** | Elegir o hacer foto, normalizar, enviar y recibir `PosterExtraction` auditada; borrador en memoria; pestaña Carteles mínima | `backend/app/posters.py`, `groq_client.py` (visión), `api.py`, `schemas.py`, `config.py`, `.env.example`; `mobile/src/app/(tabs)/posters.tsx`, `app/poster/new.tsx`, `services/posters.ts`, `types/poster.ts` | 3 formatos y HEIC aceptados; más de 4 MB rechazado con mensaje; `length` → `complete:false` con sesiones parciales; 401/429/timeout con mensaje y sin reintento; la clave nunca sale del backend; la imagen no se guarda en el servidor | `pytest` con transporte simulado (salidas completa, truncada, inválida, 429); `tsc`; `expo install --check` y `npm audit` (actualizar `dependencias.md`); 1 llamada real con el cartel 01 | Edición, persistencia, resolución |
| **3.2 Revisión y recuperación** | `fromExtraction`, avisos, editor (evento, artistas, actuaciones, B2B, día, escenario, hora), `locked`, continuar y reanalizar zona | `mobile/src/lib/poster-model.ts`, `lib/poster-flags.ts`, `app/poster/[id]/review.tsx`; `posters.py` (`mode`) | Un B2B es una sola actuación; unir y separar funcionan; un reanálisis no cambia campos `locked` ni resucita borrados; los nombres sin avisos no exigen revisión; hora de bloque ≠ hora de DJ | Tests de Node para modelo, fusión y avisos (casos SW38 y Circoloco sintéticos); `pytest` para `continue`/`region` simulados | Paleta, resolución |
| **3.3 Biblioteca local** | Guardado en dos fases, índice, huella, duplicados, borrar, reabrir sin red | `storage/local-store.ts` (claves nuevas, sin tocar las existentes), `lib/poster-store.ts`, `(tabs)/posters.tsx` | Reabrir no llama a Groq; el borrador sobrevive a cerrar la app; un fallo de escritura se avisa; el mismo archivo no crea un evento duplicado; borrar elimina la carpeta | Tests de Node para parser y migración tolerante, índice y huérfanos; en dispositivo, matar la app durante el análisis | Exportar o compartir |
| **3.4 Artistas y música** | `POST /v1/posters/resolve`, regla de enlace, homónimos, vista rápida, navegación a perfil y TrackDNA | `posters.py`, `api.py`; `app/poster/[id].tsx` (hoja), `components/poster.tsx` | Sin enlace dudoso automático; candidatos elegibles; volver del perfil reabre la hoja; 3–5 canciones solo de datos reales con su motivo; un artista sin identificar no tiene perfil ficticio | `pytest` con MusicBrainz simulado (único, homónimos, alias, sin resultados); `tsc` | Recomendaciones nuevas fuera de los datos existentes |
| **3.5 Experiencia editorial** | Paleta (colores del modelo → paleta cercana, alternativa por semilla), portada, explorador, filtros, cartel original | `lib/poster-art.ts`, `components/poster.tsx`, `app/poster/[id].tsx` | Paleta estable tras reabrir; contraste ≥ 4,5:1; selector de día solo con 2 o más días; lo que no tiene día está en «Todo»; un filtro sin datos no se muestra | Tests de Node de paleta, contraste y filtros; revisión visual en iPhone y Android | Animaciones complejas |
| **3.6 Validación y cierre** | Los 4 carteles piloto de principio a fin, ajustes finos, documentación | `docs/carteles-v1.md` | Now Here 6/6; Circoloco sin artista inventado tras revisión; Solid Grooves con el lugar corregible; SW38 completo (con continuación si hace falta), B2B correctos y 0 horas inventadas | 4–6 llamadas reales con presupuesto fijado; `pytest` y tests móviles completos una vez; prueba en dispositivo por el usuario | SetLab |
| **3.7 Auditoría transversal de cobertura musical** | Revisar conjuntamente TrackDNA, Carteles y perfiles de artista: qué datos musicales cubre cada uno, huecos y coherencia entre ellos | Por definir al empezar | Por definir al empezar | Por definir | Implementación antes de cerrar 3.6 |

Las suites completas se ejecutan al cerrar 3.1, 3.3 y 3.6. En medio, solo lo afectado.

## 11. Riesgos y decisiones técnicas pendientes

- **Modelo `qwen/qwen3.8-27b` en preview**: puede haberse retirado. Al empezar 3.1 se comprueba con `GET /models` (no gasta tokens). Si no está, se elige otro modelo de visión de la cuenta y se repite solo el cartel 01.
- **Límites de Groq**:
  - Se observaron 8 000 TPM, y el límite diario de tokens es desconocido.
  - Un cartel grande consume unos 4 000 tokens.
  - El tamaño máximo de base64 no está confirmado (se usará 4 MB).
- **Fusión de bloques** (SW38): la validación no la detecta de forma fiable. Se mitiga con `possible_merge` y con la revisión humana.
- **Referencia SW38**: Fase 1.4 registra **4 B2B (8 artistas implicados)**, no 8 B2B. 3.6 usará la referencia versionada.
- **Dependencias nuevas** (3.1): `expo-image-picker`, `expo-image-manipulator` y fijar `expo-file-system`. Hay que verificar que funcionan en Expo Go con SDK 57 y que `File.md5` existe; si no, la huella se calcula con `hashlib` en el backend.
- **Hoja de vista rápida**: elegir entre `formSheet` nativo y un componente propio, según cómo se comporte en Android y en Expo Go (3.4).
- **Latencia de resolución**: MusicBrainz admite unas 1 petición/s, así que 54 nombres tardan alrededor de 1 minuto la primera vez. Se resuelve de forma progresiva (cabezas de cartel primero) y con caché.
- **`top_tracks`**: depende de ListenBrainz, que necesita token. Sin él, se recurre a lanzamientos recientes y canciones de MusicBrainz, con el motivo visible.
- **Derechos de las imágenes**: el cartel se guarda solo en el dispositivo y por decisión del usuario. No se sube a ningún almacén ni se versiona.

## 12. Definición de terminado para Carteles V1

- Flujo completo en iPhone y Android, desde la foto o la galería hasta el evento guardado, comprobado por el usuario en dispositivo.
- Ningún dato inventado: fechas sin año, horas de bloque y lugares dudosos quedan como `null` o con aviso.
- Un B2B es una sola actuación. Los artistas que repiten se muestran sin duplicados.
- Las correcciones manuales sobreviven a reanálisis, reinicios y ediciones.
- Reabrir un evento no consume Groq. Borrar libera su espacio.
- Vista rápida, perfil y TrackDNA conectados, con vuelta al evento sin perder el contexto.
- Paleta estable, contraste verificado por tests y diseño coherente con TrackDNA e Inicio.
- `pytest`, `tsc`, tests móviles, `expo install --check` y `npm audit` en verde. `dependencias.md` actualizado.
- Inicio, TrackDNA, Guardados y Perfiles sin cambios de comportamiento.
