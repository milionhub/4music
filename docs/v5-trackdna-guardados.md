# V5 — Identidad global · TrackDNA · Guardados (19/10/2026)

La canción es la protagonista: TrackDNA → ficha → Guardar → Guardados. Los perfiles de artista siguen siendo
navegables, pero como pantallas secundarias que se abren desde las canciones.

## Navegación

- La barra inferior tiene **Inicio · TrackDNA · Guardados · Perfil**. Se retira la pestaña Explorar, que era el buscador
  de artistas.
- La búsqueda de canciones vive solo en TrackDNA. Inicio y Perfil eligen sus artistas de partida en
  `/onboarding?mode=edit`, que sigue teniendo el buscador de artistas.
- En una ficha, un artista solo se enlaza a su perfil si tiene **MBID de MusicBrainz**. Eso incluye los artistas
  acreditados y los de los créditos: remezcla, producción y el resto de roles. Nunca se enlaza por nombre.
  «Various Artists», «[unknown]» y los nombres sin identidad se muestran sin enlace.

## Sistema visual compartido

- **Fuentes globales:** las de v4. Anton para los titulares (`Fonts.display`) y Space Mono para metadatos
  (`Fonts.mono`, `monoBold`), además de Archivo Black e Instrument Serif. Son OFL y ya estaban cargadas.
- **`components/editorial.tsx`** reúne las piezas comunes:
  - `ScreenPoster`: cartel de pantalla con palabra gigante ajustada al ancho real de sus letras.
  - `CoverPlate`: la portada o, si no hay, una placa tipográfica determinista.
  - `ArtistMark`: marca tipográfica del artista, en lugar de su foto.
  - `TagPill`, `SaveButton`, `EmptyPoster` y `Kicker`.
- **Paletas, tipografías y superficies** son las de `lib/artist-identity.ts`:
  - `fixedIdentity()` asigna una identidad fija a cada pestaña: TrackDNA lleva «Cielo químico», el cian con círculo
    rosa del perfil de Priku, y Guardados lleva «Ácido».
  - Cada ficha de canción usa `identityFor(recording MBID)`.
- **Sin fotos de artistas en la interfaz.** Se retiran los componentes de fotos de la app y se conservan las portadas
  de los lanzamientos. El backend de imágenes no se toca.

## Ficha TrackDNA

- **Cartel:** portada contenida, año, duración y sello, versión, título gigante y créditos navegables.
- **Guardar canción** es el botón principal.
- **«Detrás del track»** solo usa hechos de la grabación ya documentados:
  - lanzamiento original y sello;
  - «versión de…»;
  - artistas acreditados;
  - remezclas, DJ mixes y número de lanzamientos.

  Si existe una lectura ya redactada, también se muestra, con sus fuentes. Esta versión **no genera** lecturas nuevas,
  así que no hace llamadas a Groq.
- **ADN musical:** género (indicando si es del lanzamiento), estilo, año, duración, sello y versión.
  - BPM, tonalidad y energía solo aparecen si hay una medición real (hoy nunca).
  - El estilo del artista no se muestra como ADN de la canción.
  - Sin coberturas, insignias de procedencia ni campos «pendiente».
- **Versiones:** original, remezclas y edits, cada una como grabación propia con su ficha, además de los lanzamientos
  donde aparece y los DJ mixes.
- **Escuchar:**
  - Iconos de v4, y cada enlace dice a qué lleva: «Canción», «Álbum» o «EP».
  - Si no hay enlace documentado de Spotify o SoundCloud, aparece un botón marcado como **búsqueda**.
- **Fuentes, MBID e ISRC** quedan plegados al final.

## Guardados

- **Clave nueva:** `md.saved_tracks.v1` en `expo-sqlite/kv-store`, local y sin cuenta.
- **Identidad:** el MBID de la grabación que devuelve la ficha. También cuenta como la misma canción un MBID
  duplicado que comparta ISRC y tenga la misma versión.
- **Remixes y edits** tienen otro MBID y otra versión, así que nunca se confunden con el original.
- **Favoritos de artistas** (`md.favorites.v1`): no se migran ni se borran. Siguen siendo los artistas de partida de
  Inicio y se gestionan desde Perfil, pero ya no se muestran en Guardados. La ficha de artista ya no tiene el botón
  «Guardar».

# V5.1 — Dirección artística y profundidad musical (19/10/2026)

## Tipografía
- **Cuatro roles**, todos OFL:
  - **display:** Anton y Archivo Black;
  - **serif expresiva:** DM Serif Display, redonda y cursiva (nueva);
  - **sans de interfaz:** Space Grotesk (nueva);
  - **mono:** Space Mono.
- **Anchos de glifo de DM Serif:** medidos en los TTF para `fitSize`, de modo que los títulos nunca se corten.
- **Combinaciones por canción** (`PAIRINGS` y `trackIdentityFor`), una estable para cada grabación:
  - club: Anton + DM cursiva;
  - editorial: DM Serif + Anton;
  - rave: Archivo + DM cursiva;
  - nocturno: DM cursiva + Archivo.
- **Artistas:** las identidades no cambian.
- **Títulos en dos voces** (`splitTitle`): el nombre gigante y, aparte, el subtítulo o la versión («Dirty Cash» + *Money Talks*).

## BPM, tonalidad y géneros (ver también `docs/t2-1-auditoria-fuentes-musicales.md`)
| Fuente | Qué da | Decisión |
|---|---|---|
| **AcousticBrainz** (CC0, por MBID de grabación) | BPM y tonalidad medidos con Essentia; datos hasta 2022 | **Integrada** (`backend/app/acousticbrainz.py`), con reglas estrictas y caché de 180 días (detalle debajo). Prueba real: Traumer, *Hoodlum* → 123 BPM, Sol# menor (1A), igual que la auditoría; Dirty Cash (2024) no tiene datos. |
| Deezer `bpm` | BPM, a menudo 0; sin tonalidad | Descartada: cobertura muy baja y uso no comercial |
| Spotify *audio-features* | — | Cerrado a apps nuevas |
| Beatport | La mejor fuente teórica (BPM, tonalidad, subgénero) | Sin API para terceros; descartada |
| GetSongBPM | BPM y tonalidad | Requiere clave y enlace obligatorio; pendiente de que el usuario cree la cuenta |
| Análisis local (librosa, ISC) | BPM y tonalidad | Solo con audio legítimo; no hay acceso a audio |
| **Géneros:** volcado CC0 de *releases* de Discogs (estilos por edición, p. ej. «Tech House») | Estilos del lanzamiento concreto, enlazado por la URL Discogs del lanzamiento en MusicBrainz | Mejor opción para mejorar géneros sin inventar: requiere importar el volcado de *releases* (decenas de GB). Pendiente; hoy se usan solo Wikidata P136 de grabación y lanzamiento |

Reglas de la integración de AcousticBrainz:
- Solo cuentan los envíos cuya duración coincide con la de la grabación (±5 %).
- El BPM solo se publica si todos los envíos coinciden (±2 %); si discrepan, no se publica nada.
- La tonalidad solo se publica si todos los envíos coinciden y la fuerza es ≥ 0,6.
- La app la muestra como «estimado», en notación española y Camelot.

## Escuchar
- Solo se muestran Spotify, Apple Music (incluido iTunes), SoundCloud y Discogs. Los datos de las demás plataformas siguen en la API.
- **Prioridad:** el enlace directo a la pista; si no hay, el del lanzamiento, con su tipo («EP», «Álbum»…).
- **Sin enlace documentado:** una búsqueda explícita en Spotify y SoundCloud.
- **Discogs** solo aparece si el enlace es de una edición (`/release/`) con formato físico documentado en MusicBrainz (vinilo, CD o casete). Se presenta como «Edición en vinilo», nunca como venta o disponibilidad. Para ello los enlaces de lanzamiento llevan ahora `formats`, con el contrato de la ficha en v4.

# V5.2 — Music Intelligence (19/10/2026)

## Piloto (8 canciones reales, MusicBrainz en vivo, base temporal)
- **No existen en MusicBrainz:** «Playground» de Arapu (sus 21 grabaciones revisadas) y «Vinotinto» de Luciano (sus 170 revisadas). TrackDNA responde «sin resultados» en lugar de mostrar una coincidencia vaga.
- **Antes:** género 0/6 (solo Wikidata), BPM 2/6, tonalidad 1/6, créditos 1/6.
- **Después:** género 4/6 con los géneros curados de MusicBrainz (CC BY-NC-SA: uso no comercial y con atribución):
  - Dirty Cash: House (de la grabación);
  - Hoodlum: House (de la grabación);
  - Lovelee Dae: House · Deep House (del lanzamiento);
  - Breather: House · Deep House (del lanzamiento).
- **Sin cambios:** BPM, tonalidad y créditos. Desire y Crazy no tienen ningún dato musical en fuentes abiertas.
- **Relaciones:** Lovelee Dae muestra ahora su mashup documentado.

## Decisiones
- **Géneros:** prioridad grabación (MusicBrainz, luego Wikidata) > lanzamiento original. Nunca los del artista. Se excluyen las etiquetas libres; solo cuenta la lista curada de géneros.
- **Estilos de Discogs** (volcado CC0 de lanzamientos): son viables en streaming (unos 20 min, ~100 MB de índice, sin guardar los 10,5 GB). Aun así, se aplazan: solo 2 de 6 grabaciones del piloto enlazan una edición de Discogs desde MusicBrainz, y ambas ya tienen género.
- **GetSongBPM:** necesita que el usuario cree una cuenta gratuita y enlazar su web. Su cobertura del underground reciente está sin verificar, así que no se integra a ciegas.
- **Relaciones nuevas** (`TrackRelations`, aditivas):
  - `samples` y `sampled_by` («samples material»);
  - `mashups`;
  - `cover_of` y `cover_writers`, solo con el atributo «cover» de MusicBrainz.
- **Búsqueda:**
  - Con dos o más palabras significativas, un resultado debe contenerlas todas, tolerando una errata en palabras de 5 letras o más.
  - Si no hay resultados, se hace una única consulta difusa, opcional.
  - Los remixes siguen separados del original.
- **Lecturas con IA:** se vuelven a pedir solo cuando el servidor tiene fuentes descriptivas de la canción (estado `pending`). La redacción se valida y se guarda en caché.
- **Contrato de la ficha:** v5.

# V5.3 — Dirección artística de TrackDNA (19/10/2026)

**Sistema:** `mobile/src/lib/track-art.ts` (lógica pura, reutilizable en Inicio V6) y `mobile/src/components/track-art.tsx` (piezas). Cada rasgo usa su propio hash (FNV-1a con el finalizador fmix32, prefijo de generación `g14`), así que la identidad es estable por MBID y los rasgos no van correlacionados.

**Paletas.** Son 8, de 5 colores cada una:
- **Superficies:** cartel saturado, segunda superficie saturada, papel claro y noche.
- **Dos acentos** decorativos.
- **Cada superficie** lleva una tinta y una tinta suave, ambas con contraste ≥ 4,5:1 (comprobado en los tests).

**Tríos tipográficos** (titular + voz; interfaz en Space Grotesk y datos en Space Mono):

| Trío | Titular | Voz |
|---|---|---|
| club | Anton | DM Serif cursiva |
| fat | Abril Fatface | Syne |
| geo | Syne | Instrument Serif cursiva |
| editorial | DM Serif | Archivo Black |
| rave | Rubik Mono One | Abril Fatface |
| press | Archivo Black | DM Serif cursiva |

**Rasgos que varían por canción:**
- **Composición del cartel** (4):
  - apilado (título a todo ancho; año gigante frente a la portada);
  - bandas (portada con desfase de impresión; título línea a línea sobre bandas);
  - órbita (portada circular en anillo; texto centrado);
  - partido (título sobre papel; la portada cruza a un bloque saturado).
- **Encabezados** (4): voz con filete, mayúsculas condensadas, sans ancha entre líneas, *fat serif* con disco.
- **ADN** (2): cartel con la palabra del género gigante y cifras, o fragmentos de color.
- **Ritmo de superficies** (3), que siempre alterna.
- **Separador** (3): cinta tipográfica, puntos o franjas.

**Ejemplos:**
- **Hoodlum:** Mandarina · club · apilado · sans ancha · ADN cartel.
- **Lovelee Dae:** Sala roja · editorial · partido · voz · ADN fragmentos.
- **Desire:** Petróleo mostaza · rave · bandas · *fat serif* · ADN cartel.
