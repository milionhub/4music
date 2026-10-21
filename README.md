# music-discovery

Proyecto móvil de descubrimiento de música electrónica (nombre provisional).
Estado actual: **Fase 2, hito T1 implementado y pendiente de validación en el móvil** — primer recorrido de TrackDNA: bienvenida opcional, artistas favoritos buscados en MusicBrainz, descubrimiento por conexiones verificables, ficha de artista y Guardados ([plan T1](docs/t1-plan-implementacion.md), [contrato de datos](docs/t0-contrato-datos.md)). **T2.0 TrackDNA (canciones) implementado y pendiente de validación en el iPhone**: pestaña TrackDNA, búsqueda de grabaciones de MusicBrainz y ficha con ADN de procedencia trazable (sin BPM, tonalidad ni energía: no hay fuente autorizada). Fases 0 y 1 cerradas ([conclusiones de la Fase 1](docs/fase-1-conclusiones.md)).

```
mobile/    App Expo SDK 57 (TypeScript, Expo Router), probada con Expo Go
backend/   API FastAPI (Python 3.11): GET /health y /v1 (artistas y descubrimiento vía MusicBrainz)
docs/      Documentación compartida (dependencias, decisiones)
```

Requisitos: Node 24 + npm 11, Python 3.11 (`py -3.11`), Android SDK con emulador, Expo Go en el iPhone.
Todos los comandos son para **PowerShell** y parten de la raíz del repositorio (`C:\dev\music-discovery`).

## Backend

### Instalar

```powershell
cd backend
py -3.11 -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements-dev.txt   # producción: requirements.txt
```

`requirements.txt` (aplicación) y `requirements-dev.txt` (tests) tienen todas las versiones fijadas, incluidas las transitivas.

Configura el contacto que MusicBrainz exige en el User-Agent (email o URL; `backend/.env` no se versiona):

```powershell
Copy-Item .env.example .env   # y rellena MUSICBRAINZ_CONTACT=
```

Sin él, `/health` funciona pero `/v1/*` responde `503 provider_not_configured`. Opcionales: `LISTENBRAINZ_TOKEN` (token gratuito de listenbrainz.org; activa «Más escuchadas», que ListenBrainz ya no sirve sin token) y `COVER_ART=off` (desactiva las portadas de Cover Art Archive). Biografías y fotos con permiso: catálogo `backend/app/data/editorial.json`. Biografías con IA (opcional): `GROQ_API_KEY` y `GROQ_MODEL` (por defecto `openai/gpt-oss-20b`) en `backend/.env`; se generan solo en el backend a partir de fuentes verificadas y se guardan en `backend/data/` (SQLite, fuera de Git). El backend es el único que consulta MusicBrainz (y Wikidata/Commons para fotos de artistas con licencia libre): como máximo 1 petición cada 1,1 s a MusicBrainz, caché en memoria de 24 h (se vacía al reiniciar) y como mucho una repetición ante un 503/429. Usa un solo proceso de uvicorn (como en los comandos de abajo) para que el límite sea global.

### Arrancar

Solo para este PC y el emulador Android:

```powershell
.\.venv\Scripts\python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Para el iPhone (u otro dispositivo físico), ver [iPhone](#iphone-expo-go).

### Probar

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health      # -> status: ok
Invoke-RestMethod "http://127.0.0.1:8000/v1/artists/search?q=traumer"   # consulta real a MusicBrainz
Invoke-RestMethod "http://127.0.0.1:8000/v1/tracks/search?q=deadmau5%20-%20strobe"   # TrackDNA: canciones
# Ficha: /v1/tracks/{mbid} · solo ADN: /v1/tracks/{mbid}/dna · IA: /v1/tracks/{mbid}/interpretation
.\.venv\Scripts\python -m pytest                     # tests sin red (contrato /health y /v1, cliente MusicBrainz)
.\.venv\Scripts\python eval\evaluate_discovery.py         # evaluación del motor con datos reales (consulta MusicBrainz y Labs)
```

### Actualizar dependencias

Cambia la versión en el archivo correspondiente, reinstala en un venv limpio, ejecuta `pip check` y los tests, y vuelve a fijar las versiones resultantes (`pip freeze`), manteniendo separadas las de aplicación y desarrollo.

## Mobile

### Instalar y configurar

```powershell
cd mobile
npm ci
Copy-Item .env.example .env
```

`EXPO_PUBLIC_API_URL` en `mobile/.env` indica dónde está el backend. `.env` no se versiona.
**No pongas secretos en variables `EXPO_PUBLIC_*`**: se incrustan en la app y cualquiera puede leerlas.

> En el móvil, `localhost` / `127.0.0.1` es el propio móvil, no el PC. Nunca uses esas direcciones en `EXPO_PUBLIC_API_URL`.

### Arrancar

```powershell
npx expo start
```

La primera vez aparece la bienvenida (se puede omitir). Las preferencias, favoritos y descartes se guardan solo en el dispositivo (`expo-sqlite/kv-store`). Para diagnosticar la conexión: pestaña **Perfil → Comprobar conexión** (muestra la URL usada y el resultado de `/health`). Para volver a ver la bienvenida desde cero, borra los datos de Expo Go o reinstala la app.

### Cambiar la URL

Cambia `EXPO_PUBLIC_API_URL` cuando cambies de dispositivo de prueba o cambie la IP LAN del PC (otra red, DHCP). Después:

1. Guarda `mobile/.env` y recarga la app por completo (tecla `r` en la terminal de Expo o menú de desarrollo → Reload).
2. Si la URL mostrada en pantalla no cambia, detén Expo (`Ctrl+C`) y arranca con caché limpia: `npx expo start --clear`.

### Emulador Android (Pixel_6a)

El emulador ve el `localhost` del PC como `10.0.2.2`.

```powershell
# Terminal 1
cd backend; .\.venv\Scripts\python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
# Terminal 2
cd mobile; npx expo start      # pulsa "a" para abrir en el emulador
```

`mobile/.env`: `EXPO_PUBLIC_API_URL=http://10.0.2.2:8000`

### iPhone (Expo Go)

El iPhone necesita la IP del PC en la red local, y el backend debe escuchar en todas las interfaces (`0.0.0.0`). Hazlo **solo en desarrollo y en una red de confianza** (casa, no Wi-Fi pública): el backend queda accesible para cualquier equipo de esa red.

1. IP LAN del PC (la del adaptador Wi-Fi/Ethernet conectado a la misma red que el iPhone):
   ```powershell
   Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.PrefixOrigin -in 'Dhcp','Manual' -and $_.IPAddress -notlike '169.254*' } | Select-Object InterfaceAlias, IPAddress
   ```
2. `mobile/.env`: `EXPO_PUBLIC_API_URL=http://<IP-LAN>:8000`
3. Arranca:
   ```powershell
   # Terminal 1
   cd backend; .\.venv\Scripts\python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   # Terminal 2
   cd mobile; npx expo start      # escanea el QR con la cámara del iPhone
   ```
4. Comprueba primero desde Safari del iPhone: `http://<IP-LAN>:8000/health`.

**Firewall de Windows** (no se modifica automáticamente): la primera vez que el backend escuche en `0.0.0.0`, Windows puede preguntar si permite `python.exe`; permite solo **Redes privadas**. La red Wi-Fi debe estar marcada como *Privada* (Configuración → Red e Internet → propiedades de la red). Si Safari no llega a `/health` pero el PC sí, revisa esto antes que la app.

Con la IP LAN y `0.0.0.0`, el emulador Android también puede usar la misma URL.

## Comprobaciones técnicas

```powershell
cd backend; .\.venv\Scripts\python -m pytest; cd ..
cd mobile;  npx tsc --noEmit; npx tsc --noEmit -p tests; npm test; npx expo install --check; cd ..
```

## Fase 0: preparación del entorno ✅ completada

Comprobaciones automáticas:

- [x] Test de contrato `GET /health` (pytest) superado.
- [x] TypeScript sin errores (`npx tsc --noEmit`).
- [x] `npx expo install --check`: dependencias compatibles con SDK 57.
- [x] `npm audit` revisado y documentado (ver pendientes).

Comprobaciones manuales (Expo Go):

- [x] Emulador Android (Pixel_6a, API 35): conexión con `/health` correcta vía `10.0.2.2`.
- [x] iPhone físico: conexión con `/health` correcta usando la IP LAN del PC y backend en `0.0.0.0`.
- [x] Estados de error observados y recuperación correcta al pulsar **Reintentar**.

## Dependencias y vulnerabilidades

Estado de `npm audit` y seguimiento: [docs/dependencias.md](docs/dependencias.md).

## Fase 1: fuentes musicales (investigación) ✅ cerrada

**Documento maestro: [conclusiones de la Fase 1](docs/fase-1-conclusiones.md)** (matriz de fuentes, viabilidad demostrada frente a deseada, riesgos y decisiones pendientes para la Fase 2).

Experimentos en [`research/music_sources/`](research/music_sources/README.md) y [`research/poster_ai/`](research/poster_ai/README.md). Informes: [cobertura (1.2)](docs/fase-1-cobertura-musical.md), [géneros electrónicos (1.3A)](docs/fase-1-generos-electronicos.md), [volcados de Discogs (1.3B)](docs/fase-1-discogs-dumps.md), [IA para carteles (1.4)](docs/fase-1-ia-carteles.md) y [ListenBrainz (1.5)](docs/fase-1-listenbrainz.md). La Fase 1.1 no tiene informe en el repositorio.

Decisiones:

- **MusicBrainz**: fuente principal de identidad (MBID). Solo datos centrales CC0; sus géneros y tags son CC BY-NC-SA.
- **Volcados CC0 de Discogs**: fuente candidata de géneros y estilos (por lanzamiento y con procedencia). Antes de llevarlos a producción faltan un piloto de integración y una revisión legal.
- **API de Discogs**: solo investigación; no es dependencia de producción.
- **Wikidata**: enriquecimiento opcional de artistas, solo con el ID validado por MBID.
- **AcousticBrainz**: descartado.
- **Carteles (Groq `qwen/qwen3.8-27b`)**: seleccionado provisionalmente para extraer artistas, con revisión humana obligatoria; modelo en *preview*.
- **ListenBrainz Labs**: fuente complementaria y opcional de artistas similares; LB Radio y la cuenta de ListenBrainz, aplazados.
- **Personalización V1**: preferencias, favoritos e interacciones propias; sin aprendizaje automático propio ni Spotify.

## Pendientes

- **Fuentes musicales**: piloto con los volcados de Discogs (primero *masters*, luego *releases*); revisión legal de CC0, cadena de derechos y uso de la marca Discogs; proporción real de lanzamientos electrónicos y tamaño final; alojamiento. Sin pipeline ETL todavía.
- **BPM y tonalidad para SetLab**: sin fuente válida (AcousticBrainz descartado).
- **IA a coste cero**: Groq (plan gratuito) probado para carteles en la Fase 1.4; queda prever un modelo alternativo (el actual está en *preview*) y decidir el alcance del análisis de carteles.
- **Decisiones de la Fase 2**: ver [docs/fase-1-conclusiones.md §11](docs/fase-1-conclusiones.md).
- **Nombre y diseño de producto**: nombre definitivo, identidad visual y diseño de pantallas (la pantalla actual es técnica y provisional).
- **Vulnerabilidades sin arreglo compatible en SDK 57**: ver [docs/dependencias.md](docs/dependencias.md).
