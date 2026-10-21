# Artist Experience v4 — decisiones (19/10/2026)

## 2A · Artist Intelligence («Más allá de la cabina»)

- Endpoint `GET /v1/artists/{mbid}/stories` (`backend/app/stories.py`), separado del perfil y con caché propia
  (kind `stories`, versionada): la ficha nunca espera a la investigación.
- Evidencia (todo por identificadores, nunca por nombre):
  - documentos de la biografía: MusicBrainz, Wikidata, Wikipedia en es/en u otro idioma, web oficial y notas CC0 de
    Discogs;
  - **trayectoria de MusicBrainz**: primer lanzamiento propio y su sello (solo con la discografía completa), sellos
    donde más publica (sin implicar fundación), lanzamientos conjuntos repetidos;
  - **perfiles CC0 de los sellos que enlaza el perfil de Discogs del artista** (`[l123]`/`[l=Nombre]`, nunca por nombre
    libre) y su **web propia** según Discogs si MusicBrainz no la enlaza (respetando robots.txt).
- Redacción: Groq escribe de 1 a 3 historias (`inicios`, `universo`, `momento`) citando los hechos. Cada historia se
  valida contra los hechos que cita (`biography.story_issue`): años, títulos, afirmaciones sensibles (fundar,
  residencias…), nombres propios, géneros y gentilicios, copia literal, y además relleno valorativo o causal
  («consolidando», «se inspira», «refleja su visión», «esencia»…). Las que fallan se descartan; un único reintento.
- Nombres civiles: los que MusicBrainz documenta para un solista (alias «Legal name» o la desambiguación «Nombre
  Apellido, …») se sustituyen en la evidencia por el nombre artístico y nunca aparecen en una historia.
- Sin Groq, o si ninguna historia es válida: historias deterministas con datos estructurados (primer lanzamiento,
  sellos fundados o dirigidos, integrantes, ediciones de festivales con año).

## Fuentes investigadas

| Fuente | Resultado |
|---|---|
| Discogs (volcados CC0): perfiles de artista y **de sello**, webs propias | Integrado |
| MusicBrainz: trayectoria (primer lanzamiento, sellos, colaboraciones, eventos) | Integrado |
| Wikipedia es/en + otro idioma por sitelink; webs oficiales con robots.txt | Integrado (capas anteriores) |
| Resident Advisor | Descartado: sus términos prohíben el acceso automatizado (4.4 f) |
| DJ Mag, Beatportal | Descartados: robots.txt bloquea bots de IA (`Disallow: /`) |
| Electronic Groove, Trommel, XLR8R | API pública de WordPress operativa, pero sus búsquedas devuelven menciones (carteles, podcasts de otros), no perfiles, y sus condiciones de uso no están publicadas: candidatos pendientes, no integrados |
| Mixmag | Sin API ni feed utilizable |
| ListenBrainz (popularidad) | Exige token de usuario (401 sin él). El backend ya lo usa si `LISTENBRAINZ_TOKEN` está en `.env` |
| Last.fm `artist.getTopTracks` | Exige clave API; no configurada |
| MusicBrainz como «temas destacados» (apariciones en lanzamientos) | Descartado: con `inc=recordings` devuelve páginas parciales (ANOTR: 10 de 54) y recuentos de 1–3; no es un criterio fiable |

## 2D · Música

- Con escuchas reales (ListenBrainz): «Temas más escuchados», numerados, con la aclaración de que son escuchas
  registradas en ListenBrainz y no reproducciones globales.
- Sin ellas: «Su música», discografía documentada por fecha, sin ranking. Nunca se presenta una fecha como popularidad.

## 2B / 2C · Visual

- Superficies de la ficha teñidas con la paleta del artista (`surfaces()`), con el contraste comprobado en pruebas.
- Cabeceras con recursos propios por composición; historias como bloques editoriales; banda tipográfica.
- Iconos de plataformas: Simple Icons 13.21.0 (CC0), generados en `mobile/src/constants/platform-icons.ts` y pintados
  con `react-native-svg` (incluido en Expo Go). Sin icono libre (Deezer, Traxsource, Qobuz…): insignia con iniciales.
