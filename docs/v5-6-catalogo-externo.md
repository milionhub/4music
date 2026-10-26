# TrackDNA V5.6 — Catálogo externo (Discogs)

Fecha: 2026-10-21. Piloto reproducible: `backend/eval/pilot_v56.py` (resultados en `eval/pilot_v56_results.json`, fuera de Git).

## Decisión

- **Fuente: API de Discogs**, sin token. `/database/search` responde sin autenticación (en la fase 1 se documentó lo contrario; comprobado el 2026-10-21). Deezer sigue descartado (uso no comercial).
- **Condiciones** (API Terms of Use, citadas en `fase-1-generos-electronicos.md`):
  - Tracklists, fechas, formatos, identificadores y créditos: CC0.
  - Imágenes: Restricted Data, **no se usan**. Las fichas externas no llevan portada.
  - Estilos: no son CC0. Se muestran como dato del lanzamiento y con atribución.
  - Caché de **6 h** como máximo. «Data provided by Discogs» con enlace junto a los datos, más aviso de no afiliación (en la ficha).
  - Uso comercial «generally permitted», salvo decisión de Discogs. Si el proyecto pasa a ser comercial, conviene revisarlo.

## Piloto (API real, 8 búsquedas)

| Búsqueda | Resultado |
|---|---|
| Luciano Vinotinto | **Encontrada**: `discogs:29565955:1`, 9:19, From The South FTSR001, 2022-11-18, Tech House (del lanzamiento). El artista enlaza con el Luciano correcto de MusicBrainz (`6f8d9d66…`) a través de su ID de Discogs (6362), no con sus homónimos. |
| Arapu Playground | **Rechazada**: no está en Discogs (solo en Deezer). Ningún resultado parecido. |
| Arapu You Got The Groove | Encontrada: `discogs:36998067:1`, 8:16, Solid Grooves Raw SGRAW081, 2025. |
| Arapu Tribal Nation | Encontrada: `discogs:31292360:A1`, vinilo de Satya sin duración. |
| Arapu Unexpected | Encontrada: `discogs:31044784:4`, Cadenza CADENZA124, 2024. |
| Arapu Deep Down | Encontrada: «Take It Deep Down» (`discogs:31759997:A1`), del EP *Deep Down* de Rawax. |
| Fired Up Arapu Remix · Chris Stassy Desire | Controles: MusicBrainz los tiene, así que Discogs no se consulta. |

Latencia de la primera búsqueda: 4–7 s (MusicBrainz más Discogs). La ficha tarda menos de 4 s en frío y sale de la caché después.

## Implementado

- **`app/discogs_tracks.py`**:
  - Búsqueda complementaria: solo si MusicBrainz (con su reintento difuso) no da ningún resultado, y solo con dos o más palabras significativas.
  - Peticiones: 1 de búsqueda y hasta 3 lanzamientos, con 1 s de separación como mínimo.
  - Mismo filtro estricto de palabras que la búsqueda de MusicBrainz (título y artistas).
  - Si Discogs falla, la búsqueda sigue respondiendo sin resultados externos.
- **Identidad**:
  - Formato `discogs:<release>:<posición>`: una pista concreta de una edición concreta.
  - Original, extended, edit y remix son siempre canciones distintas.
  - Dos ediciones solo se presentan como una si coinciden título, artistas (por ID de Discogs) y duración (±3 %).
  - Se excluyen las sesiones mezcladas (fragmentos de DJ mix).
- **Artistas**: llevan MBID solo si MusicBrainz enlaza ese ID de Discogs a un único artista. Si no, se muestran sin enlace, con id `discogs:artist:<id>`.
- **API**:
  - `GET /v1/tracks/ext/{id}` devuelve `TrackResponse` con `catalog: "discogs"`.
  - `TrackSearchResult` y `TrackResponse` ganan el campo opcional `catalog`, por defecto `musicbrainz`.
  - `Source.provider` admite `discogs`.
  - `/v1/tracks/{mbid}` sigue aceptando solo MBID.
- **Ficha externa**:
  - Género y estilos del lanzamiento, salvo en recopilatorios.
  - Sello, catálogo, formato, fecha, duración y versión.
  - Sin BPM, tonalidad, portada ni interpretación con IA.
- **Móvil**:
  - La búsqueda marca los resultados externos con la etiqueta «Discogs».
  - La misma pantalla TrackDNA carga la ruta `ext`.
  - Sin botón Guardar.
  - Pie con «Data provided by Discogs ↗» y el aviso de no afiliación.

## Limitaciones

- **Guardados**: siguen identificados por MBID. Guardar canciones externas exigiría migrar el almacenamiento local y la carga de Inicio (`useTracks`), así que queda pendiente.
- **Sin ISRC ni BPM** en las fichas externas: Discogs no da ISRC por pista de forma fiable, y el ISRC de Deezer para Vinotinto corresponde a otra versión (2:23).
- **Búsqueda**: con una sola palabra no se consulta Discogs. Solo se revisan los 3 primeros lanzamientos distintos que devuelve Discogs.
- **Fuera de alcance**: canciones que no están ni en MusicBrainz ni en Discogs (p. ej. *Playground*).
