# Fase 1.3B — Viabilidad de los volcados CC0 de Discogs

Consultado el 2026-10-16. No se ha descargado ningún volcado completo, no se ha consultado ninguna API musical, no se han instalado dependencias y no se ha tocado `mobile/` ni `backend/`. Todas las pruebas se hicieron en el directorio temporal de la sesión, fuera del repositorio.

## 1. Archivos, formato, tamaño y frecuencia

Fuente: listado oficial de [data.discogs.com](https://data.discogs.com/) (bucket público con «Last Modified / Size / Name»).

| Archivo (volcado 2026-10-01) | Tamaño (gzip) | Bytes exactos (`Content-Length`) |
|---|---|---|
| `discogs_20261001_releases.xml.gz` | 10.5 GB | 11 304 225 465 |
| `discogs_20261001_masters.xml.gz` | 600.5 MB | 629 708 615 |
| `discogs_20261001_artists.xml.gz` | 475.7 MB | — |
| `discogs_20261001_labels.xml.gz` | 87.0 MB | — |
| `discogs_20261001_CHECKSUM.txt` | 388 B | SHA-256 de los 4 archivos (descargado y leído) |

- **Formato:** XML comprimido con gzip, «formatted according to the API spec».
- **Frecuencia:** mensual, publicado el día 1. En 2026 están completos los 10 meses (de enero a octubre).
- **Irregularidades:** en el listado de 2025 faltan el *masters* de febrero y el *releases* de octubre. Todos los archivos de 2025 tienen fecha de modificación 2026-01-15, lo que apunta a una resubida. No hay garantía publicada de continuidad.
- **Crecimiento:** *releases* pasó de 9.6 GB (2025-01) a 10.5 GB (2026-10), unos +0.05 GB al mes.
- El servidor **ignora las peticiones `Range`**: devuelve el archivo entero con 200. Al repetir el listado, devolvió **429**, así que no se insistió.

## 2. ¿Contienen género y estilo?

**Sí, verificado.** Se leyeron solo los **primeros 512 KB comprimidos** de *releases* y de *masters* de 2026-10-01; se cerró la conexión y se descomprimió el fragmento.

```xml
<release id="1">…<genres><genre>Electronic</genre></genres><styles><style>Deep House</style></styles>
  <country>Sweden</country><released>1999-03-00</released>…<master_id is_main_release="true">1660109</master_id>…
<master id="113"><main_release>116925</main_release>…<genres><genre>Electronic</genre></genres>
  <styles><style>Techno</style><style>Tech House</style></styles><year>2002</year>…
```

En la muestra (713 lanzamientos y 1 416 masters):

- **Lanzamientos:** traen `genres` y `styles` (el 100 % con estilo), además de `artists`, `labels` (con `catno`), `formats`, `released`, `master_id`, `tracklist`, `extraartists`, `identifiers`, `notes`, `videos` y `data_quality`.
- **Masters:** `genres` y `styles` (el 99.5 % con estilo), `main_release` y `year`.
- **No hay `<images>`** en ninguna de las dos muestras, así que no aparecen datos de imágenes.

Los estilos son los mismos que se vieron por API en la Fase 1.3A (Deep House, Tech House, Techno, Minimal…).

## 3. Licencia: volcados frente a API

| Documento | Texto relevante |
|---|---|
| [data.discogs.com](https://data.discogs.com/) | «This data is made available under the **CC0 No Rights Reserved** license». |
| [Terms of Service](https://support.discogs.com/hc/en-us/articles/360009334333-Terms-of-Service) (actualizados el 2026-02-23; leídos con la API oficial del Help Center, porque la web devuelve 403) | «**Content made available via our Data Dump is subject to the license found on the Data Dump landing page.** … Use of Service Data obtained via APIs is generally subject to Our API Terms of Use». Los usuarios conceden a Discogs una licencia «with the right to sublicense… including… making available the Data Dump». |
| [API Terms of Use](https://support.discogs.com/hc/en-us/articles/360009334593-API-Terms-of-Use) | Se aplican a «Our API… and data made available through Our API». Las reglas de 6 h, almacenamiento mínimo, atribución obligatoria y prohibiciones comerciales se refieren al contenido **obtenido por la API**. |

**Conclusión:** los Terms of Service separan expresamente los dos regímenes. Los géneros y estilos **obtenidos del volcado** quedan bajo CC0, sin la regla de 6 h ni el límite de almacenamiento de la API. Lo obtenido por API en la Fase 1.3A sigue bajo las API Terms of Use y no debe mezclarse con el almacén del producto.

## 4. Restricciones adicionales para una app pública o comercial

| Cuestión | Estado |
|---|---|
| Uso comercial de los datos del volcado | CC0 no lo restringe. **Pendiente** de una revisión legal formal: este análisis no es asesoramiento jurídico. |
| Atribución | CC0 no la exige; se recomienda por cortesía («Datos: Discogs, CC0»). |
| Marca «Discogs» | **No la cubre CC0.** No usar el nombre ni el logotipo de forma que sugiera afiliación. Están la «Application Name and Description Policy», citada en las API Terms of Use (no leída), y las políticas de marca del ToS: **pendiente** de revisar si se nombra Discogs en la app. |
| Cadena de derechos del contenido aportado por usuarios | Los ToS dicen que los usuarios conceden a Discogs una licencia sublicenciable para «the Data Dump». **Pendiente** de valoración legal. El riesgo parece bajo para etiquetas factuales como género y estilo. |
| Campos de texto libre (`notes`, `videos` con descripciones de YouTube) | Pueden contener texto de terceros. **Pendiente**; recomendación: no usarlos y quedarse con campos estructurados (IDs, títulos, sellos, catálogo, fechas, géneros, estilos). |
| Continuidad del servicio de volcados | **Sin garantía** publicada; ya hay huecos en 2025. |
| Página [Developers](https://www.discogs.com/developers) | Sigue devolviendo **403**; **pendiente** (no afecta a la licencia del volcado). |

## 5. Requisitos en este equipo

Equipo: Windows 11, Intel i5-10210U, 15.8 GB de RAM y 206.8 GB libres en C:.

Medido sobre la muestra con `xml.etree.ElementTree.iterparse` de la biblioteca estándar, liberando cada elemento con `clear()`:

- **11 MB/s** de XML, incluida la extracción de campos.
- **0,3 MB** de pico de memoria del analizador.
- Tasa de compresión: 6,3 veces en *releases* y 5,5 en *masters*.

| | *masters* | *releases* |
|---|---|---|
| Descarga | 0,63 GB | **11,3 GB**; ~15 min a 100 Mbit/s y ~30 min a 50 Mbit/s (estimado) |
| XML descomprimido (estimado) | ~3,5 GB | **~71 GB**. **No hace falta guardarlo**: se lee el `.gz` en flujo. |
| Elementos (estimado) | ~1,7 M | ~15 M por bytes medios; la API de Discogs anunciaba 19,5 M |
| Tiempo de una pasada | ~5–6 min | **~1,5–3 h** (6 500 s a 11 MB/s, más margen por throttling del portátil) |
| RAM | < 100 MB | < 100 MB, en flujo y sin cargar el archivo |
| Disco | 0,63 GB | 11,3 GB (el `.gz`, que se puede borrar tras procesarlo) más el resultado |

**La extracción incremental es viable** sin dependencias nuevas: `gzip.open` + `iterparse` + `clear()`, filtrando `genre == "Electronic"` en una sola pasada. La integridad se comprueba con el SHA-256 de `CHECKSUM.txt`.

## 6. Tamaño final, actualización y alojamiento

- **Proporción de lanzamientos electrónicos: pendiente.** La muestra da un 100 % pero está sesgada: los primeros IDs son electrónicos, porque Discogs nació así. Solo una pasada completa lo mide.
- Escenario orientativo de 4–7 M lanzamientos electrónicos, con unos 300 B por registro reducido (IDs de lanzamiento, master, artistas y sello; título; catálogo; fecha; país; formato; géneros; estilos):
  - **~1,2–2,8 GB** en TSV.
  - **~2–5 GB** en SQLite con índices.
- **Variantes más pequeñas:**
  - Solo masters electrónicos: ~1–1,5 M × ~150 B = **~150–250 MB**. Pero los masters no cubren lanzamientos sin master: S1 y S5 de la Fase 1.3A no tenían.
  - Solo IDs de Discogs enlazados desde MusicBrainz, con sus estilos: tamaño **pendiente**, porque requiere un volcado de MB (los datos centrales de MB, URL incluidas, son CC0). Previsiblemente de decenas o cientos de MB.
- **Actualización:** mensual, reprocesando el volcado entero (no hay deltas). Coste aproximado: 11 GB de descarga y 2–3 h de proceso al mes. Asumible en local; es mejor programarlo que hacerlo a mano.
- **Alojamiento gratuito: pendiente** de verificar los límites actuales de cada proveedor. Por órdenes de magnitud:
  - Un subconjunto de 100–300 MB cabe en niveles gratuitos habituales o como archivo estático.
  - 2–5 GB, en general no.
  - El procesamiento mensual no debería hacerse en un nivel gratuito en la nube; mejor en este equipo.

## 7. Comparación con «solo MusicBrainz y géneros desconocidos»

| Criterio | Volcados CC0 de Discogs | Solo MB con géneros desconocidos |
|---|---|---|
| Cobertura de estilos electrónicos | Alta (5/5 canciones con estilo en la Fase 1.3A, con Tech House, Minimal…); es el mismo dato que da la API | Prácticamente nula: los géneros de MB son escasos y además **CC BY-NC-SA**, no utilizables comercialmente |
| Licencia | CC0 según el ToS y la página de volcados (con los pendientes de §4) | CC0 para la identidad; los géneros quedan excluidos |
| Coste | 0 €; ~11 GB y 2–3 h de proceso al mes | 0 € |
| Complejidad | Pipeline de ingesta mensual y cruce MB↔Discogs por URL o ID | Ninguna adicional |
| Precisión | Estilo por **lanzamiento o master**, editado por usuarios (en la Fase 1.3A: 6 de 10 en «Needs Vote»), variable entre ediciones y con masters de obras originales | Honesto, pero sin valor para descubrir por estilo |
| Frescura | Hasta ~1 mes de retraso | — |
| Riesgo | Huecos en los volcados y continuidad sin garantía | Ninguno |

## 8. Recomendación

**Adoptar los volcados CC0 de Discogs como fuente de géneros y estilos, de forma provisional, manteniendo MusicBrainz como fuente de identidad.** Cuando no haya un enlace fiable a Discogs, el género queda «desconocido»; nunca se rellena por aproximación.

Pasos propuestos para la siguiente fase (no ejecutados):

1. Piloto con *masters* (0,6 GB, unos 5 min). Después, una pasada completa de *releases* que mida la proporción real de electrónica y el tamaño final, guardando solo campos estructurados.
2. Cruzar con los IDs de Discogs de MusicBrainz y guardar los estilos **por lanzamiento con procedencia** (ID y mes del volcado), aplicando las reglas de la Fase 1.3A: nada de atribuir a pista o artista, ni de usar masters de otro artista.
3. Separar estrictamente lo obtenido por API (bajo las API Terms of Use) del almacén alimentado por volcados.
4. Antes de publicar: resolver los pendientes legales de §4 (revisión jurídica de CC0 y la cadena de derechos, y el uso de la marca).

**Pendientes:**

- Revisión legal formal.
- Políticas de marca.
- Proporción real de electrónica.
- Tamaño final.
- Límites del alojamiento gratuito.
- Tamaño del subconjunto enlazado desde MB.
- Página Developers (403).
