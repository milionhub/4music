# Experimento de cobertura de fuentes musicales (Fase 1.2)

Experimento aislado: no lo usa ni la app (`mobile/`) ni el backend. Resultados y conclusiones en
[`docs/fase-1-cobertura-musical.md`](../../docs/fase-1-cobertura-musical.md).

Solo usa la biblioteca estándar de Python 3.11 (sin dependencias ni venv propio).

## Ejecutar

```powershell
Copy-Item research\music_sources\.env.example research\music_sources\.env   # rellena MUSIC_RESEARCH_CONTACT
py -3.11 research\music_sources\run_experiment.py             # reutiliza la caché: 0 peticiones si ya existe
py -3.11 research\music_sources\run_experiment.py --refresh   # vuelve a consultar todo (~75 MB + ~10 WD, ~2 min)
py -3.11 -m unittest research\music_sources\test_http_client.py   # pruebas offline del cliente HTTP
```

`MUSIC_RESEARCH_CONTACT` (email o URL) va en el User-Agent que exigen MusicBrainz y Wikimedia. No se escribe en ningún log ni resultado.

## Archivos

| Archivo | Qué hace |
|---|---|
| `cases.json` | Casos de prueba tal como se dieron; las correcciones son *candidatas*, se buscan aparte. |
| `http_client.py` | GET JSON con límite de ritmo por fuente, presupuesto máximo, reintentos (429/5xx/timeout, `Retry-After`), caché en disco y registro sin cabeceras. |
| `sources.py` | Endpoints oficiales de MusicBrainz (`/ws/2`) y Wikidata (`wbsearchentities`, `wbgetentities`); estado de Discogs (no consultado). |
| `run_experiment.py` | Ejecuta los casos y escribe los resultados. |
| `test_http_client.py` | Pruebas contra un servidor local: caché, JSON inválido, 404, 503 con reintento, timeout, ritmo, presupuesto y ausencia de credenciales en el log. |

## Datos generados (`data/`)

- `raw/<fuente>/<hash>.json`: **datos originales**, la respuesta íntegra de cada URL (con `url`, `fetched_at`, `status`). Hace también de caché. Solo se guardan las respuestas 200 y los 4xx definitivos.
- `logs/run-*.jsonl`: una línea por petición, con URL, intento, estado, inicio y duración, y si vino de la caché.
- `results/songs.json`, `results/artists.json`: en cada entidad, `observed` son valores copiados de la fuente y `interpretation` las decisiones del script (tipo de coincidencia, estado de validación). Cada bloque incluye `request.url` y `request.raw_file`.
- `results/summary.json`: versiones, presupuesto, peticiones, errores, comprobación de ritmo y estado de Discogs. Describe la última ejecución (la versionada se hizo desde la caché, con 0 peticiones). El total de peticiones de red está en `all_runs`.

En Git solo se versiona `results/`. `raw/` y `logs/` se quedan en local (ver `.gitignore`); `--refresh` los regenera, aunque los datos de las fuentes pueden haber cambiado desde entonces.

Licencias de lo guardado: los datos centrales de MusicBrainz y todo Wikidata son CC0. Las etiquetas (tags) y asociaciones de género de MusicBrainz son CC BY-NC-SA 3.0 (datos suplementarios).

## Fase 1.3: Discogs y AcousticBrainz

Informe: [`docs/fase-1-generos-electronicos.md`](../../docs/fase-1-generos-electronicos.md). Reutiliza `cases.json` y `data/results/` de la Fase 1.2 en solo lectura, y no consulta MusicBrainz ni Wikidata.

```powershell
py -3.11 research\music_sources\run_phase13.py                 # caché; necesita DISCOGS_TOKEN en .env
py -3.11 research\music_sources\run_phase13.py --skip-discogs  # solo AcousticBrainz
py -3.11 -m unittest research\music_sources\test_phase13.py    # pruebas offline
```

| Archivo | Qué hace |
|---|---|
| `discogs.py` | API oficial de Discogs: token en la cabecera `Authorization`, 1,2 s entre peticiones y pausa si `X-Discogs-Ratelimit-Remaining` ≤ 3. Antes de cachear elimina los campos de Restricted Data (imágenes, comunidad y usuarios, Marketplace). |
| `acousticbrainz.py` | API histórica de AcousticBrainz: consultas masivas de hasta 25 MBID y solo los descriptores BPM y tonalidad. |
| `run_phase13.py` | Ejecuta la fase y escribe `data/results_phase13/`; registra en `data/logs/phase13-*.jsonl`. |
| `test_phase13.py` | Comprueba que el token no se filtra, que los campos restringidos se eliminan, la pausa por límite, las reglas de coincidencia y el límite de la consulta masiva. |

Presupuesto de la Fase 1.3: Discogs 150 (se usaron 80) y AcousticBrainz 10 (se usaron 4).

`data/results_phase13/discogs_*.json` contiene datos obtenidos de la API de Discogs (almacenamiento limitado por sus API Terms of Use): **se queda en local y no se versiona** (ver `.gitignore`). Se versionan `summary.json` y `acousticbrainz.json`.

## Presupuesto de peticiones (techo duro por ejecución)

| Fuente | Intervalo mínimo | Techo | Uso real en una ejecución en frío |
|---|---|---|---|
| MusicBrainz | 1,5 s (la norma es ~1/s por IP) | 130 | ~74 (69 URL únicas + reintentos por 503) |
| Wikidata | 1,0 s | 30 | 10 |
| Discogs | — | 0 | 0 (bloqueado; ver el informe) |

Límites por caso: 3 grabaciones, 3 lanzamientos y 2 release groups por canción; 2 artistas candidatos por caso; 3 homónimos en la búsqueda diagnóstica; 3 candidatos de Wikidata sin enlace. Si se agota el presupuesto, el script se detiene y lo registra en `summary.json` (`aborted`).

## Fase 1.5: ListenBrainz (artistas similares)

Ver [`listenbrainz/README.md`](listenbrainz/README.md) e informe [`docs/fase-1-listenbrainz.md`](../../docs/fase-1-listenbrainz.md). Usa ListenBrainz Labs (sin clave) y MusicBrainz para los MBID; no modifica los datos de las fases anteriores.
