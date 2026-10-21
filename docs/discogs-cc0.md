# Discogs (volcados CC0) — índice local

Fuente complementaria de hechos para los perfiles de artista, sobre todo los underground sin Wikipedia. Se usa el
volcado mensual oficial, no la API, durante la ejecución.

## Licencia y condiciones

- [data.discogs.com](https://data.discogs.com/): «This data is made available under the CC0 No Rights Reserved license».
- Los [términos de la API](https://support.discogs.com/hc/en-us/articles/360009334593-API-Terms-of-Use) (6 horas de
  antigüedad, caché, avisos obligatorios) se refieren al contenido servido por la API («data made available through
  Our API»). El volcado no se obtiene por la API, de modo que hechos y biografías derivados pueden conservarse como los
  de otras fuentes. Es una lectura razonable del texto, no una confirmación expresa de Discogs.
- Atribución (buena práctica, no obligación de CC0): la fuente aparece como «Discogs (perfil)» con licencia CC0 y enlace a
  la ficha del artista. No se usa la marca de forma que sugiera respaldo de Discogs.
- Datos personales excluidos aunque sean CC0: nombre real (`realname`), datos de contacto de sellos (`contactinfo`) y
  enlaces. El volcado no incluye imágenes.

## Construcción y actualización mensual

Desde `backend/` con el entorno virtual:

```bash
python -m app.discogs_dump fetch 20261001   # artistas + sellos en data/discogs/, SHA-256 oficial verificado
python -m app.discogs_dump build 20261001   # data/discogs.sqlite3 en streaming; sustitución atómica
```

- `fetch` comprueba el espacio libre, lee el `CHECKSUM.txt` oficial del mes y no repite una descarga ya verificada.
- `build` lee el XML comprimido registro a registro (memoria constante), escribe en `discogs.sqlite3.building` y solo
  sustituye el índice anterior si el nuevo tiene filas. El backend abre el índice en solo lectura en cada consulta: no
  hay que reiniciarlo, y el móvil no se ve afectado.
- Cada mes: `fetch` y `build` con la nueva fecha. Después pueden borrarse los `.xml.gz` del mes anterior.
- Las biografías existentes no se regeneran al actualizar; se renuevan con su TTL y versionado habituales.
- Otra ruta: variable `DISCOGS_DB_PATH`. Sin índice, el backend funciona igual con las demás fuentes.
- Nada de esto va a Git (`backend/data/` está ignorado).

## Contenido del índice

| Tabla | Campos |
|---|---|
| `artist` | `id`, `name` (todos los artistas, para resolver referencias `[a123]`); `variations`, `profile` (notas originales comprimidas con zlib), `members`, `groups`, solo si el artista tiene perfil o relaciones |
| `label` | `id`, `name`, `parent_id` (para resolver referencias `[l123]`) |
| `meta` | fecha del volcado, licencia, archivos, SHA-256, recuentos, fecha y duración de la construcción |

## Uso en el pipeline

- Identidad: solo el ID de Discogs que MusicBrainz enlaza al MBID, si es único, y solo si el nombre coincide con el de
  Discogs o con una de sus variantes. Nunca se busca por nombre.
- `app/discogs.py` normaliza las notas: quita el marcado de presentación (`[b]`, `[url=…]`, `[a=…]`, `[l=…]`) y
  resuelve `[a123]`/`[l123]` con el índice. Si una referencia no se resuelve (p. ej. `[r123]`, un lanzamiento), se descarta la frase
  entera en lugar de dejarla incompleta.
- Integrantes y grupos de Discogs solo completan lo que MusicBrainz no tiene, y nunca ocupan plazas reservadas del
  selector.
- Las notas cuentan como texto descriptivo en el umbral de 150 caracteres (sin rebajarlo) y respaldan en el validador
  las afirmaciones de fundación; residencias y éxitos siguen exigiendo Wikipedia o la web oficial. Ante el mismo hecho,
  el selector prefiere Wikipedia y MusicBrainz.

## Limitaciones conocidas

- Las notas son breves, escritas por la comunidad y sin fecha («He's the resident DJ of…» puede estar desfasado).
- El volcado tiene hasta un mes de antigüedad.
- Los perfiles underground de una o dos frases (65–100 caracteres) no alcanzan por sí solos el umbral para generar una
  biografía. Aportan hechos al expediente y al prompt cuando hay más texto.
- Si Discogs fusiona artistas, un ID antiguo enlazado desde MusicBrainz puede no existir en el volcado: no se usa.
