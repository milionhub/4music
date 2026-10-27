# #4MUSIC

**App móvil para descubrir música electrónica a partir de conexiones verificables**: de dónde viene una canción, quién la firma, qué samplea, con quién comparte sello o escenario… y qué artistas de un cartel de festival encajan contigo.

Cada recomendación muestra su motivo y su fuente. Nada de «porque sí»: si la app dice que dos artistas están conectados, enseña la relación documentada en MusicBrainz, Discogs o ListenBrainz que lo respalda.

> Proyecto personal de portfolio, sin ánimo de lucro. Probado en iPhone y en Android (emulador Pixel 6a, Android 15) con Expo Go.

<p align="center">
  <img src="docs/screenshots/02-inicio-hoy.png" width="200" alt="Inicio: la canción del día" />
  <img src="docs/screenshots/13-ficha-dirty-cash.png" width="200" alt="Ficha de canción en TrackDNA" />
  <img src="docs/screenshots/24-artista-anotr.png" width="200" alt="Perfil de artista: ANOTR" />
  <img src="docs/screenshots/22-hoja-de-ruta.png" width="200" alt="Hoja de ruta de un cartel" />
  <img src="docs/screenshots/10-guardados.png" width="200" alt="Guardados" />
</p>

## Qué hace

| | |
|---|---|
| **Inicio** | Una «edición» diaria con diseño editorial que cambia de paleta y tipografía cada día: canción del día, *En el radar*, *Tu frecuencia* (afín a tus artistas y estilos, siempre con el motivo) y *Detrás del sonido* (samples confirmados). |
| **TrackDNA** | Busca cualquier canción y obtén su ficha: género y estilos, BPM y perfil sonoro estimados, edición original, sellos, créditos, samples, remezclas, extracto de 30 s y enlaces para escucharla. Cada dato indica su procedencia. |
| **Carteles** | Fotografía el cartel de un festival: un modelo de visión lee el line-up (días, escenarios, horarios y B2B), tú revisas lo dudoso y la app identifica a cada artista en MusicBrainz, te dice quién te encaja *para ti* y te ayuda a planificar la ruta. |
| **Guardados** | Tu cajón de canciones, disponible sin conexión y guardado solo en el dispositivo. |
| **Perfil** | Tu «pase»: artistas de partida, estilos y lo que se repite en lo que guardas. Sin cuenta ni registro. |

## Capturas

**Bienvenida** — la app presentada como el cartel de un festival (cada sección es un escenario del line-up) y, después, tus artistas de partida y tus estilos.

<p align="center">
  <img src="docs/screenshots/01-bienvenida-4music.png" width="180" alt="Bienvenida: la app como cartel de festival" />
  <img src="docs/screenshots/01b-bienvenida-artistas.png" width="180" alt="Elegir artistas" />
  <img src="docs/screenshots/01-bienvenida-estilos.png" width="180" alt="Elegir estilos" />
</p>

**Inicio** — la edición del día, *Tu frecuencia* (cada recomendación dice de qué canción guardada viene) y *Detrás del sonido* (un sample confirmado de tus Guardados).

<p align="center">
  <img src="docs/screenshots/02-inicio-hoy.png" width="180" alt="Inicio" />
  <img src="docs/screenshots/12-tu-frecuencia.png" width="180" alt="Tu frecuencia" />
  <img src="docs/screenshots/03-inicio-secciones.png" width="180" alt="Detrás del sonido" />
</p>

**TrackDNA** — búsqueda, ficha y análisis DNA de una canción: género, BPM, perfil sonoro, sello, artistas y dónde escucharla.

<p align="center">
  <img src="docs/screenshots/04-trackdna.png" width="180" alt="TrackDNA" />
  <img src="docs/screenshots/13-ficha-dirty-cash.png" width="180" alt="Ficha de canción" />
  <img src="docs/screenshots/14-adn-musical-detalle.png" width="180" alt="ADN musical" />
  <img src="docs/screenshots/15-artistas-y-escuchar.png" width="180" alt="Artistas y escuchar" />
</p>

**Perfil de artista** — ANOTR: ficha verificada (dúo, Ámsterdam, sello NO ART), su historia contada a partir de fuentes, sus esenciales y dónde escucharlo.

<p align="center">
  <img src="docs/screenshots/24-artista-anotr.png" width="180" alt="Perfil de artista: ANOTR" />
  <img src="docs/screenshots/25-artista-anotr-historia.png" width="180" alt="Historia y esenciales de ANOTR" />
</p>

**Carteles: análisis con IA** — eliges la foto, la IA lee el line-up (escenarios, horarios, B2B) y marca solo lo dudoso para que lo revises.

<p align="center">
  <img src="docs/screenshots/07-carteles.png" width="180" alt="Carteles" />
  <img src="docs/screenshots/16-cartel-vista-previa.png" width="180" alt="Vista previa" />
  <img src="docs/screenshots/17-cartel-ia-leyendo.png" width="180" alt="La IA lee el cartel" />
  <img src="docs/screenshots/18-cartel-revision-ia.png" width="180" alt="Revisión" />
</p>

**Carteles: el evento** — artistas identificados en MusicBrainz, *Para ti* con el motivo y un extracto, el sonido del cartel y la hoja de ruta: una ruta sin solapes y la parrilla por escenario para hacerla tuya.

<p align="center">
  <img src="docs/screenshots/19-evento.png" width="180" alt="Evento" />
  <img src="docs/screenshots/20-para-ti.png" width="180" alt="Para ti" />
  <img src="docs/screenshots/21-sonido-y-lineup.png" width="180" alt="Sonido del cartel" />
  <img src="docs/screenshots/22-hoja-de-ruta.png" width="180" alt="Hoja de ruta" />
  <img src="docs/screenshots/23-parrilla.png" width="180" alt="Parrilla" />
</p>

**Guardados y Perfil**

<p align="center">
  <img src="docs/screenshots/10-guardados.png" width="180" alt="Guardados" />
  <img src="docs/screenshots/10b-guardados-lista.png" width="180" alt="Lista de guardados" />
  <img src="docs/screenshots/11-perfil.png" width="180" alt="Perfil" />
</p>

## Cómo está hecho

```
mobile/    App Expo SDK 58 · React Native · TypeScript · Expo Router · expo-sqlite (datos locales)
backend/   API FastAPI · Python 3.11 · SQLite (caché de IA)
research/  Experimentos de la fase de investigación (fuentes musicales, IA para carteles)
docs/      Decisiones, contratos de datos e informes de cada hito
```

- **Backend como única puerta a las fuentes externas**: limita el ritmo de MusicBrainz (1 petición/1,1 s), cachea, reintenta una sola vez y nunca expone claves a la app (nada sensible en `EXPO_PUBLIC_*`).
- **IA con revisión humana**: Groq (LLM con visión) solo *propone* lo que lee en un cartel; el usuario confirma o corrige. Las biografías generadas parten solo de datos verificados.
- **Privacidad por defecto**: sin cuentas; gustos, guardados y carteles viven en el dispositivo.
- **Datos con licencia y procedencia**: datos centrales CC0 de MusicBrainz, volcados CC0 de Discogs, Wikidata/Commons para fotos con licencia libre, Cover Art Archive, ListenBrainz, ReccoBeats y Deezer (extractos y catálogo, solo uso no comercial; se pueden desactivar con `DATA_USE=commercial`).
- **Pruebas**: 255 tests de backend (pytest, sin red) y 135 tests de lógica móvil (`node --test`), más TypeScript estricto.

El proceso completo, por fases y con sus decisiones, está documentado en [`docs/`](docs/) (empieza por las [conclusiones de la Fase 1](docs/fase-1-conclusiones.md) y el [plan maestro de la Fase 2](docs/music-discovery-fase-2-plan-maestro.md)).

## Puesta en marcha

Requisitos: Node 24 + npm 11, Python 3.11 (`py -3.11`), y Expo Go en el móvil o un emulador Android.
Todos los comandos son para **PowerShell** y parten de la raíz del repositorio.

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

Sin él, `/health` funciona pero `/v1/*` responde `503 provider_not_configured`. Opcionales: `LISTENBRAINZ_TOKEN` (token gratuito de listenbrainz.org; activa «Más escuchadas», que ListenBrainz ya no sirve sin token), `COVER_ART=off` (desactiva las portadas de Cover Art Archive) y `DATA_USE=commercial` (desactiva las fuentes de uso solo no comercial, activas por defecto: fotos de artista, extractos de 30 s, sellos y catálogo de reserva de Deezer; ver [V6](docs/v6-fuentes-no-comerciales.md)). Biografías y fotos con permiso: catálogo `backend/app/data/editorial.json`. Biografías con IA (opcional): `GROQ_API_KEY` y `GROQ_MODEL` (por defecto `openai/gpt-oss-20b`) en `backend/.env`; se generan solo en el backend a partir de fuentes verificadas y se guardan en `backend/data/` (SQLite, fuera de Git). El backend es el único que consulta MusicBrainz (y Wikidata/Commons para fotos de artistas con licencia libre): como máximo 1 petición cada 1,1 s a MusicBrainz, caché en memoria de 24 h (se vacía al reiniciar) y como mucho una repetición ante un 503/429. Usa un solo proceso de uvicorn (como en los comandos de abajo) para que el límite sea global.

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
# Extracto de 30 s de Deezer (V6.1): /v1/tracks/{mbid}/preview
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

## Dependencias y vulnerabilidades

Estado de `npm audit` y seguimiento: [docs/dependencias.md](docs/dependencias.md).

## Historia del proyecto

- **Fase 0 — entorno**: monorepo, contrato `/health`, Expo Go en emulador Android e iPhone.
- **Fase 1 — investigación de fuentes**: cobertura musical, géneros electrónicos, volcados de Discogs, IA para carteles y ListenBrainz ([conclusiones](docs/fase-1-conclusiones.md); experimentos en [`research/`](research/)). Decisiones clave: MusicBrainz como identidad (MBID, solo datos CC0), Discogs CC0 para géneros y estilos, AcousticBrainz descartado y personalización sin cuentas.
- **Fase 2 — producto**: descubrimiento por conexiones, TrackDNA, Guardados, Perfil e Inicio editorial ([plan maestro](docs/music-discovery-fase-2-plan-maestro.md)).
- **Fase 3 — Carteles**: lectura de carteles con IA, line-up revisable, «Para ti» y planificador de ruta ([plan](docs/carteles-fase-3-plan.md)).

## Limitaciones conocidas

- Se ejecuta con Expo Go y un backend local; no hay builds publicadas en tiendas ni backend desplegado.
- BPM y perfil sonoro son estimaciones de fuentes externas, no análisis propio del audio.
- Algunas fuentes (Deezer y los géneros de MusicBrainz) solo permiten uso no comercial.
- La lectura de carteles depende de un modelo en *preview* de Groq y siempre requiere revisión.
