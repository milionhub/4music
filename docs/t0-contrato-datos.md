# T0 — Contrato de datos y preparación de TrackDNA

Hito T0 del [plan maestro de la Fase 2](music-discovery-fase-2-plan-maestro.md) (2026-10-16). Prepara el recorrido de T1: **onboarding opcional → selección de gustos → descubrimiento de un artista → ficha musical → guardar favorito**. No implementa nada. Plan de ejecución: [t1-plan-implementacion.md](t1-plan-implementacion.md).

Base: [conclusiones de la Fase 1](fase-1-conclusiones.md) y las decisiones 14, 20, 21, 22, 26 y 28 del plan maestro.

## 1. Estado técnico real (inspeccionado)

| Área | Estado |
|---|---|
| Git | Rama `main`, último commit `fbe272d`. Sin cambios locales salvo `docs/music-discovery-fase-2-plan-maestro.md`, que está **sin versionar** (archivo del usuario; se conserva). |
| Backend | `backend/app/main.py`: solo `GET /health` → `{"status":"ok"}`. Sin modelos, servicios, persistencia ni cliente HTTP. Dependencias fijadas: `fastapi`, `uvicorn[standard]` (trae `python-dotenv`). Desarrollo: `pytest` y `httpx2` (para `TestClient`). Prueba: `tests/test_health.py`. No existe `backend/.env` ni `.env.example`. |
| Mobile | Plantilla de Expo SDK 57 con Expo Router (`src/app/`). Pestañas nativas `index` (pantalla de comprobación de conexión, que usa `services/health.ts`) y `explore` (contenido de plantilla). `config/api.ts` lee `EXPO_PUBLIC_API_URL`. **No hay persistencia local** ni gestión de estado. |
| Variables | `mobile/.env` (`EXPO_PUBLIC_API_URL`, existe y no se versiona). El `.gitignore` raíz ignora `.env` y `.env.*`, salvo `.env.example`. |
| Verificación | `pytest` (backend), `npx tsc --noEmit` y `npx expo lint` (mobile), `npx expo install --check` y `npm audit` (dependencias; ver [dependencias.md](dependencias.md)). |
| Investigación reutilizable | `research/music_sources/http_client.py` (biblioteca estándar: límite de ritmo, caché, presupuesto). Es código de investigación; **no se importa desde el backend**, solo sirve de referencia. |

## 2. Evidencia que condiciona el descubrimiento

- **Fase 1:** no hay fuente de estilos usable en T1. Los géneros y tags de MusicBrainz son CC BY-NC-SA; los volcados de Discogs no tienen piloto ni revisión legal; la API de Discogs está excluida. ListenBrainz queda fuera del primer recorrido.
- **Comprobación puntual de T0** (6 peticiones a MusicBrainz, sin reintentos, más 8 fichas de artista de la caché de la Fase 1):
  - **Relaciones directas entre artistas: escasas** para DJs. Las únicas encontradas fueron «married» y «label founder» en Amelie Lens; ninguna en Traumer, PAWSA, Michael Bibi, Mochakk, Ilario Alicante ni The Martinez Brothers. Sven Väth sí tenía varias («member of band», «is person»).
  - **Coartistas en las grabaciones: existen, pero son pocos.** En las 100 primeras de 195 grabaciones, Amelie Lens tiene 7 coartistas (Farrago, Endel, AIROD, Slam…) y Traumer 3 de 190 (DJ Deep, NTO, Delano Smith). La búsqueda de grabaciones de PAWSA devolvió 503.
  - Algunos coartistas son poco afines al contexto (p. ej., Lizzo en Amelie Lens, probablemente por una remezcla). Son conexiones reales, pero no implican afinidad de estilo.
- **Licencia** ([MusicBrainz Database](https://musicbrainz.org/doc/MusicBrainz_Database)): son **datos centrales CC0** los artistas, las grabaciones, los lanzamientos, los sellos, las **relaciones y URL**, el crédito de artista, los ISRC y los alias. Son **suplementarios (CC BY-NC-SA)** las anotaciones, los tags (incluidas las asociaciones de género), las valoraciones, las estadísticas derivadas, los **índices de búsqueda** y el historial de ediciones.

**Conclusión:** en T1, el descubrimiento se basa en **conexiones verificables de MusicBrainz** (coartistas de grabaciones y relaciones musicales entre artistas), con un motivo explícito. Habrá artistas **sin conexiones**, y eso se muestra como un estado vacío honesto, nunca con relleno.

## 3. Arquitectura mínima

```
App (Expo) ──HTTP JSON──▶ Backend FastAPI ──▶ MusicBrainz /ws/2 (1 petición/s, User-Agent con contacto)
   │  preferencias, favoritos y descartes      │  normalización → contrato propio
   └─ en el dispositivo (expo-sqlite/kv-store) └─ caché en memoria con TTL + límite de ritmo global
```

| Capa | Responsabilidades |
|---|---|
| **Backend** | Único que habla con MusicBrainz. Valida los MBID, limita el ritmo, cachea, normaliza al contrato, añade procedencia y traduce los errores del proveedor. **No guarda datos del usuario.** |
| **App** | Interfaz, recorrido y estados (carga, vacío, error). Guarda las preferencias, los favoritos y los descartes en el dispositivo. Envía al backend los MBID semilla y los excluidos. Nunca llama directamente a MusicBrainz. |

Sin base de datos, Redis, autenticación ni servicios nuevos: T1 no los necesita.

## 4. Entidades de T1

Convenciones:

- Los campos opcionales son `null` cuando la fuente no tiene el dato. **Nunca** se rellenan con valores supuestos.
- Las listas vacías son `[]`.
- Los identificadores son MBID (UUID en minúsculas) y el tipo va en un campo aparte.
- Las fechas de MusicBrainz se conservan como texto parcial (`"1990"`, `"1990-05"`, `"1990-05-31"`).

### Source (procedencia, común a las respuestas)

```json
{ "provider": "musicbrainz", "url": "https://musicbrainz.org/artist/<mbid>", "fetched_at": "2026-10-16T16:00:00Z",
  "license": "CC0 (MusicBrainz core data)", "stale": false }
```

`stale: true` indica que se sirvió desde la caché porque el proveedor no respondió.

### Artist

| Campo | Tipo | Obligatorio | Origen en MusicBrainz |
|---|---|---|---|
| `mbid` | string (UUID) | sí | `id` |
| `name` | string | sí | `name` |
| `sort_name` | string \| null | no | `sort-name` |
| `disambiguation` | string \| null | no | `disambiguation` (clave para distinguir homónimos) |
| `type` | string \| null | no | `type` (Person, Group…) |
| `country` | string \| null | no | `country` (ISO 3166-1) |
| `area` | string \| null | no | `area.name` |
| `begin_date` | string \| null | no | `life-span.begin` (parcial) |
| `aliases` | string[] | no ([]) | `aliases[].name` (máx. 5) |
| `links` | `{kind, url}[]` | no ([]) | Relaciones URL. `kind` es el tipo de relación de MusicBrainz (p. ej. `official homepage`, `discogs`) |
| `source` | Source | sí | — |

**Fuera de T1:** géneros, tags, imágenes, popularidad, BPM y biografía.

### Recording (Track)

| Campo | Tipo | Obligatorio | Origen |
|---|---|---|---|
| `mbid` | string | sí | `id` |
| `title` | string | sí | `title` |
| `artist_credit` | `{mbid, name, join_phrase}[]` | sí | `artist-credit` |
| `length_ms` | int \| null | no | `length` |
| `first_release_date` | string \| null | no | `first-release-date` (parcial) |
| `disambiguation` | string \| null | no | `disambiguation` (p. ej. «extended mix») |
| `source` | Source | sí | — |

En T1, las grabaciones solo se muestran en la ficha del artista y como evidencia de una conexión. Los ISRC y los enlaces a tiendas quedan para más adelante.

### DiscoveryCard

```json
{
  "artist": { "...Artist sin aliases ni links..." },
  "reasons": [
    { "kind": "co_credit", "seed_mbid": "<mbid semilla>", "seed_name": "Amelie Lens",
      "evidence": { "recording_mbid": "<mbid>", "recording_title": "<título>" } }
  ],
  "actions": ["explore", "save", "discard"]
}
```

- `reasons` nunca está vacío: una tarjeta solo existe si hay evidencia.
- `kind` puede ser `co_credit` (aparecen juntos en el crédito de una grabación) o `artist_relation` (relación musical de MusicBrainz).
- Para `artist_relation`, la evidencia es `{"relation_type": "member of band"}`.
- Se excluyen las relaciones personales (`married`, `sibling`, `parent`…): no son conexiones musicales.
- El orden es determinista: número de evidencias de mayor a menor y, en empate, nombre. **No hay porcentajes ni puntuaciones de afinidad.**

### MusicalPreference (solo en el dispositivo)

```json
{ "version": 1, "onboarding": "completed" | "skipped" | "pending",
  "seed_artists": [{ "mbid": "<mbid>", "name": "Amelie Lens", "disambiguation": "Belgian techno DJ & producer" }],
  "declared_styles": ["techno", "minimal"], "updated_at": "2026-10-16T16:00:00Z" }
```

- **`declared_styles`** es una declaración del usuario sobre sus gustos, no un dato musical de ningún artista. Se guarda y se puede editar, pero **en T1 no filtra ni ordena recomendaciones**, porque no hay datos de estilo licenciados para cruzarla (ver §8).
- Se puede omitir y modificar.

### Favorite y descartes (solo en el dispositivo)

```json
{ "version": 1, "items": [{ "kind": "artist", "mbid": "<mbid>", "name": "Traumer",
  "disambiguation": "house/techno", "saved_at": "2026-10-16T16:00:00Z" }] }
```

- `kind` admite `artist` y `recording`; **T1 solo usa `artist`**.
- Se guardan el nombre y la desambiguación para mostrar la lista sin conexión; la ficha se refresca desde el backend.
- Los descartes se guardan aparte, con la misma forma (`kind`, `mbid`, `discarded_at`). Colecciones e historial quedan para T3.

## 5. Contratos de API

> **Actualización T1.1** (detalle en [t1-plan-implementacion.md §0.1](t1-plan-implementacion.md)). Cambios en el contrato:
>
> - `Link` pasa a ser `{url, label, platform, kinds, detail, primary}`: una entrada por URL, con todos sus tipos de relación fusionados.
> - La ficha devuelve `releases` y `releases_status`, `collaborations`, `recordings_status` y `connections`, en lugar de `recordings` y `recordings_source`.
> - Nuevo `GET /v1/artists/{mbid}/image`: foto de Wikimedia Commons verificada por MBID, o `null` con su motivo.
> - Ante un 503 o 429 del proveedor se repite **una sola vez**.
>
> **Actualización T1.2:** `GET /v1/artists/{mbid}` devuelve `ArtistProfileResponse`, un perfil modular con imagen, estilos de Wikidata, biografía editorial o factual con fuentes, más escuchadas (ListenBrainz, solo con token), lanzamientos recientes, colaboraciones y plataformas. Detalle y fuentes en [t1-plan-implementacion.md §0.2](t1-plan-implementacion.md).

Prefijo `/v1`. Todas las respuestas son JSON. `/health` se mantiene sin cambios.

| Método y ruta | Uso | Llamadas a MusicBrainz sin caché |
|---|---|---|
| `GET /v1/artists/search?q=<texto>&limit=10` | Elegir artistas en el onboarding y en la búsqueda de semillas | 1 |
| `GET /v1/artists/{mbid}` | Ficha: artista y hasta 25 grabaciones | 2: ficha (`inc=aliases+url-rels+artist-rels`) y listado de grabaciones (`/recording?artist=<mbid>&inc=artist-credits&limit=100`; la ficha muestra las 25 primeras) |
| `GET /v1/discovery?seeds=<mbid,…>&exclude=<mbid,…>&limit=10` | Tarjetas a partir de un máximo de 3 semillas | 2 por semilla (las mismas consultas que la ficha, compartiendo caché) |

**Búsqueda** (`200`):

```json
{ "query": "traumer",
  "results": [
    { "mbid": "319c89bc-…", "name": "Traumer", "disambiguation": "house/techno", "type": "Person", "country": "FR", "area": "Paris", "score": 100 },
    { "mbid": "0950f065-…", "name": "TraumeR", "disambiguation": "Brazilian Power Metal Band", "type": "Group", "country": null, "area": "São Paulo", "score": 92 } ],
  "source": { "...": "..." } }
```

La app **muestra la desambiguación y el usuario elige**; nunca se selecciona el primer resultado automáticamente.

**Ficha** (`200`): `{ "artist": Artist, "recordings": Recording[], "recordings_total": 190 }`.

**Descubrimiento** (`200`):

```json
{ "cards": [DiscoveryCard], "seeds_without_connections": ["202ed573-…"],
  "seeds_failed": [], "source": { "...": "..." } }
```

Con `cards: []` y todas las semillas en `seeds_without_connections`, la respuesta es **200 y vacía, no un error**.

**Errores** (formato común: `{ "error": { "code": "...", "message": "..." } }`):

| HTTP | `code` | Cuándo |
|---|---|---|
| 422 | `invalid_mbid` / `invalid_query` | MBID que no es UUID; `q` vacío o de más de 100 caracteres; más de 3 semillas |
| 404 | `not_found` | MusicBrainz responde 404 |
| 503 | `provider_unavailable` | MusicBrainz responde 503 o 5xx, o se agota el tiempo (10 s), y no hay caché |
| 503 | `provider_not_configured` | Falta `MUSICBRAINZ_CONTACT` en el backend |
| 502 | `provider_bad_response` | La respuesta no es JSON o no tiene la forma esperada |

En el descubrimiento, una semilla que falla va a `seeds_failed` y no tumba la respuesta si otras funcionan.

## 6. Matriz de procedencia y licencias

Estados:

- **Validado:** comprobado en la Fase 1 o en T0 con datos reales.
- **Pendiente:** previsto, sin comprobar o con dudas.
- **No disponible:** no hay fuente permitida.

| Campo | Fuente | Estado | Licencia y dudas | Si no hay dato |
|---|---|---|---|---|
| MBID, nombre, desambiguación, tipo, país, área y fecha de inicio del artista | MusicBrainz, ficha de artista | **Validado** (1.2 y 1.5) | Datos centrales CC0 | `null`; la interfaz muestra «Sin dato» u oculta el campo |
| Alias | MusicBrainz `inc=aliases` | **Validado** (1.2) | CC0 | `[]` |
| Enlaces externos | MusicBrainz, relaciones URL | **Validado** (1.5, verify) | CC0 (las URL son datos centrales). El contenido enlazado tiene sus propias condiciones | `[]` |
| Resultados de búsqueda | MusicBrainz `/ws/2/artist?query=` | **Validado** técnicamente | Los datos devueltos son entidades CC0, pero la página de licencia clasifica los «search indexes» como suplementarios. Se interpreta que afecta al volcado del índice, no al uso de la API: **pendiente de confirmar** | Lista vacía y mensaje «Sin resultados» |
| Grabaciones: título, crédito, duración, fecha | MusicBrainz, listado de grabaciones por artista | **Validado** (T0: Amelie Lens y Traumer; 503 en PAWSA) | CC0. **El orden del listado no es de popularidad**: no se presenta como «top» | `[]` y «Sin grabaciones registradas» |
| Conexión por coautoría | Derivada de `artist-credit` | **Validado** (T0), cobertura baja | CC0; la conexión es nuestra, con evidencia citada | El artista va a `seeds_without_connections` |
| Conexión por relación musical | MusicBrainz, relaciones de artista | **Validado** técnicamente; cobertura muy baja en DJs | CC0 | Ídem |
| Géneros y estilos de artista o grabación | — | **No disponible** | Los tags y géneros de MusicBrainz son CC BY-NC-SA (excluidos). Volcados de Discogs pendientes. API de Discogs excluida | No se muestra el campo |
| Estilos declarados por el usuario | El propio usuario | Dato propio | Sin licencia de terceros | Vacío si omite el paso |
| BPM, tonalidad, energía y similitud acústica | — | **No disponible** | Sin fuente validada (Fase 1) | No se muestra |
| Previews de audio | — | **No disponible** | Sin fuente autorizada | No se muestra |
| Imágenes de artista | — | **No disponible** en T1 | No investigado | Marcador gráfico propio, sin foto |
| Artistas similares (ListenBrainz Labs) | — | Excluido de T1 | Licencia sin confirmar; servicio experimental | — |
| Uso comercial de la API de MusicBrainz | — | **Pendiente** | MetaBrainz pide un nivel de soporte a empresas con ingresos (Fase 1). No bloquea el desarrollo con 0 € y sin ingresos | — |

## 7. Persistencia local, errores y límites

- **Dispositivo:** `expo-sqlite`, mediante su almacén clave-valor `expo-sqlite/kv-store`. Es un módulo de Expo incluido en Expo Go que sustituye directamente a AsyncStorage y deja abierta la vía a tablas SQL para colecciones e historial (T3).
  - Claves: `md.preferences.v1`, `md.favorites.v1` y `md.discarded.v1`, con valores JSON versionados.
  - Si el JSON no se puede leer o la versión es desconocida, se ignora y se empieza vacío, sin bloquear la app.
  - **Se instalará en T1** con `npx expo install expo-sqlite`; hoy no está instalado.
- **Caché del backend:** en memoria del proceso, con TTL de 24 h para fichas, grabaciones y búsquedas, y un límite de unas 500 entradas.
  - Se pierde al reiniciar (con `--reload`, en cada cambio). Es aceptable para el volumen de T1.
  - Si hiciera falta persistirla, `sqlite3` de la biblioteca estándar, sin dependencias nuevas, queda como ampliación.
- **Límite de ritmo:** un candado global garantiza al menos 1,1 s entre peticiones a MusicBrainz, con un solo proceso de uvicorn.
  - User-Agent: `music-discovery/0.1 ( <MUSICBRAINZ_CONTACT> )`. La variable va en `backend/.env` (no versionado), y se crea `backend/.env.example` sin valores.
- **Sin reintentos automáticos en el backend.** El usuario reintenta desde la interfaz. Con caché caducada y proveedor caído, se sirve lo caducado con `stale: true`.
- **Latencia en frío:** un descubrimiento con 3 semillas sin caché hace hasta 6 peticiones, unos 7–8 s. La app muestra el progreso; las peticiones siguientes salen de la caché.
- **Cliente HTTP del backend:** `urllib.request` de la biblioteca estándar, en endpoints síncronos de FastAPI. No se añade `httpx` a `requirements.txt`.

## 8. Decisiones técnicas y abiertas

| # | Decisión | Motivo |
|---|---|---|
| D1 | MBID como identificador único; el tipo de entidad va en un campo aparte | Fase 1: el MBID es el enlace común entre fuentes |
| D2 | Descubrimiento por conexiones verificables de MusicBrainz, con motivo y evidencia obligatorios | Única fuente permitida con datos de relación; sin estilos licenciados |
| D3 | Estados vacíos honestos cuando no hay conexiones (PAWSA) | No inventar recomendaciones (decisión 26) |
| D4 | Preferencias, favoritos y descartes solo en el dispositivo, con `expo-sqlite/kv-store` | Sin registro (decisión 21); módulo de Expo incluido en Expo Go |
| D5 | Caché en memoria y límite de ritmo en el backend; sin infraestructura nueva | Suficiente para T1 y con 0 € |
| D6 | Endpoints con el prefijo `/v1` | Permite cambiar el contrato sin romper la app |

**Decisión de producto necesaria antes de T1 (no bloquea la técnica):** qué hacer con los **estilos del onboarding**. La decisión 21 pide elegir «estilos y artistas», pero en T1 no hay datos de estilo de artistas.

- **Propuesta más simple:** ofrecer una lista corta de estilos propia (p. ej. Techno, House, Tech House, Deep House, Minimal, Melodic Techno, Electro, Breaks), guardarla como gusto declarado y avisar de que todavía no condiciona las recomendaciones.
- **Alternativa:** omitir los estilos en T1.
- La lista concreta es una decisión de producto.
