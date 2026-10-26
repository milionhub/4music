# Investigación de fuentes musicales (sesión 2)

Consulta y pruebas: **19 de octubre de 2026**. Sin integrar nada, sin claves nuevas, sin Groq. Consultas reales, secuenciales y
dentro de los límites publicados (Discogs 25/min sin autenticar, Openverse 20/min anónimo, Wikidata con espera ante 429).

Artistas: los 10 del piloto + 2 elegidos antes de probar (**Chris Stassy**, **Archie Hamilton**). Identidad siempre por
identificador (MBID → enlace de MusicBrainz a Discogs/Wikidata), nunca por nombre.

Legenda de permisos: **Permitido** (explícito) · **Condicionado** (requisitos) · **No permitido** · **No confirmado**.

## A. Fuentes

| Fuente | Datos útiles | Gratis | Acceso | Portfolio / demo | Fotos reutilizables | Limitaciones | Veredicto |
|---|---|---|---|---|---|---|---|
| MusicBrainz (ya integrada) | Identidad, relaciones (sello fundado, miembro, alias, eventos), enlaces a Discogs/Wikidata | Sí | Sin clave, 1 req/s | **Permitido** (datos núcleo CC0) | — | Etiquetas/géneros y datos suplementarios: CC BY-NC-SA ([licencia](https://musicbrainz.org/doc/About/Data_License)) | Mantener |
| Wikidata (ya integrada) | Ítem por MBID o ID de Discogs, P18, géneros, sitelinks a todas las Wikipedias | Sí | Sin clave (429 si se abusa) | **Permitido** (CC0) | P18 → Commons | Géneros discutibles | Mantener |
| Wikipedia (es/en integradas) | Trayectoria, sellos, fiestas, residencias | Sí | Sin clave | **Condicionado** (CC BY-SA: atribución) | — | **No se leen otros idiomas**: ANOTR solo tiene de/nl/sv, Chris Stassy nl | Ampliar idiomas (con cautela) |
| Wikimedia Commons (integrada) | Fotos con licencia por archivo | Sí | Sin clave | **Condicionado** (licencia del archivo) | Sí, si la licencia es libre | Hay fotos sin P18/P180 que el pipeline no ve (Jamie Jones, ANOTR) | Mantener + curación manual |
| **Discogs API** | Perfil del artista, integrantes, grupos, alias, enlaces; perfil de sellos | Sí | Sin clave para `/artists` y `/labels` (25/min) | **Condicionado**: nombres, notas y lanzamientos son **CC0**; aviso «Data provided by Discogs» con enlace y aviso de no afiliación; frescura ≤ 6 h y caché «no más de lo necesario» ([TOU](https://support.discogs.com/hc/en-us/articles/360009334593-API-Terms-of-Use)) | **No**: las imágenes son «Restricted Data» (licencia personal, no transferible) | La regla de 6 h y caché es ambigua para los datos CC0 | **Integrar** |
| Discogs data dumps | Lo mismo en XML mensual | Sí | Descarga | **Permitido**: «made available under the CC0» ([data.discogs.com](https://data.discogs.com/)) | No incluye imágenes | Volúmenes grandes (cientos de MB) | Alternativa a la API si la caché importa |
| TheAudioDB | Ficha básica, imágenes | Clave pública `123` (30/min); premium 8 $/mes | Clave pública documentada ([doc](https://www.theaudiodb.com/free_music_api)) | **No confirmado** (página de términos inexistente: 404) | **No**: «Most are fan created», sin licencia | 3/12 fichas, 0 biografías en inglés | Descartar |
| Last.fm | Biografías wiki, etiquetas, similares | Sí | **Clave** | **Condicionado**: solo no comercial, atribución, tope de 100 MB, borrar al terminar ([TOS](https://www.last.fm/api/tos)) | **No**: imágenes «expressly excluded» (5.1.8) | Pendiente de clave | Investigar credenciales (baja prioridad) |
| ListenBrainz | Canciones más escuchadas, artistas similares por MBID | Sí | **Token de usuario** (ahora exigido también para popularidad: respuesta 401 «bad actors and AI scrapers») | No confirmado sin token | — | 1 req/s | Investigar credenciales |
| Fanart.tv | Imágenes de artistas | Clave personal | **Clave** | **No confirmado** (páginas de clave y términos con 403) | No confirmado (subidas de fans) | — | Investigar, sin prioridad |
| Setlist.fm | Setlists y recintos por MBID | Sí (no comercial) | **Clave** | **Condicionado**: solo no comercial, enlace de atribución sin nofollow, caché solo «short periods» ([términos](https://www.setlist.fm/help/api-terms)) | — | Útil para SetLab, no para perfiles | Investigar (SetLab) |
| Flickr API | Fotos CC filtrables por licencia | Clave no comercial | **Clave** | **Condicionado**: respetar la licencia de cada foto, borrar en 24 h si el autor lo pide ([TOS](https://www.flickr.com/services/api/tos/)) | Solo CC BY/BY-SA/CC0 (NC solo mientras no haya uso comercial) | Identidad por nombre poco fiable | Investigar (curación manual) |
| Openverse | Búsqueda de imágenes CC (Flickr + Commons) | Sí | Anónimo: 20/min, 200/día (cabeceras) | **Condicionado** por la licencia de cada imagen | Sí, por licencia | Muchos falsos positivos por nombre | Herramienta de curación, no automática |
| Deezer API | Foto, fans | Sí | Sin clave (búsqueda) | **No permitido** para una demo: uso «strictly private use within a family scope»; imágenes prohibidas sin autorización ([términos](https://developers.deezer.com/termsofuse)) | **No** | Homónimos (2 «Jamie Jones», 2 «Traumer») | Descartar |
| iTunes Search API | ID, género principal | Sí | Sin clave (~20/min) | **Condicionado**: solo para promocionar compras, con insignia y enlace ([términos](https://performance-partners.apple.com/search-api)) | No (solo carátulas promocionales) | Género grueso; homónimos (3 «Josh Baker») | Descartar |
| Music Story | Metadatos profesionales | No (B2B con SLA) | Contrato | No | — | De pago | Descartar |
| Resident Advisor | Biografías, eventos, residencias | — | Sin API | **No permitido**: prohíbe el acceso por «automated devices, scripts, bots, spiders, crawlers or scrapers» sin autorización escrita (4.4 f, [términos](https://ra.co/terms)) | No | — | Descartar (o pedir permiso por escrito) |
| Beatport | Géneros, sellos, lanzamientos | — | API v4 **solo para socios aprobados** (fuentes secundarias; [docs](https://api.beatport.com/v4/docs/)) | No | No | Exige acuerdo de socio | Descartar |
| Bandcamp | Discografías, etiquetas | — | Sin API pública de datos | No confirmado (los [términos](https://bandcamp.com/terms_of_use) no autorizan extracción) | No | — | Descartar |
| SoundCloud | Perfiles, pistas | Sí | **Registro de app** | **Condicionado**: sin caché persistente, el contenido es del autor ([términos API](https://developers.soundcloud.com/docs/api/terms-of-use)) | No | — | Descartar para perfiles |
| Mixmag / DJ Mag / Electronic Groove | Entrevistas, noticias | — | Sin API | **No confirmado** (páginas de términos con 404); contenido editorial con copyright | No | — | Descartar (solo enlazar) |
| 1001Tracklists | Tracklists, apoyos de DJs | — | Sin API oficial | **No confirmado**; bloquea bots (según terceros) | No | — | Descartar |

## B. Cobertura real (solo datos reutilizables confirmados)

Fuentes efectivamente probadas: MusicBrainz, Wikidata, Wikipedia (todas las lenguas por sitelink), Commons, Discogs API,
TheAudioDB, Openverse, Deezer, iTunes. TheAudioDB, Deezer e iTunes no suman cobertura (no reutilizable o vacío).

| Artista | Fuente actual (MB + Wikidata + Wikipedia es/en + Commons) | + Discogs CC0 | + Wikipedia otras lenguas |
|---|---|---|---|
| Joseph Capriati | BIO · FOTO · GEN · PROY | (perfil mínimo) | — |
| Jamie Jones | BIO · — · GEN · PROY | PROY (fundador de Hot Creations, grupos) | — |
| Marco Carola | BIO · FOTO · GEN · PROY | PROY (grupos, alias) | — |
| Paco Osuna | BIO · FOTO · GEN · PROY | PROY (Shake/Mindshake, residente de Amnesia) | — |
| **Priku** | — · — · GEN · — | **PROY**: dirige el sello **Atipic** y el proyecto Atipic (live) | — |
| **ANOTR** | — · — · GEN · — | **PROY**: dúo de Ámsterdam, **fundó NO ART en 2017**, 2 integrantes | **BIO** (de: trayectoria, Piotr & Zahn, residentes de ANTS desde 2017) |
| **Traumer** | — · — · GEN · — | **PROY**: propietario del sello **Gettraum** | — |
| **Cloonee** | — · — · GEN · — | **PROY**: fundador de **Hellbent Records** | — |
| Bicep | BIO · — · ? · PROY | PROY (Feel My Bicep con Hammer) | — |
| Josh Baker | BIO · — · GEN · PROY | (sin perfil) | — |
| Chris Stassy (extra) | BIO · FOTO · ? · PROY | PROY (Up The Stuss, 2020) | BIO (nl) |
| Archie Hamilton (extra) | BIO · — · ? · PROY | GEN (house/techno) | — |

«?»: el género no está claro en las fuentes reutilizables. Archie Hamilton: el artículo correcto es «Archie Hamilton
(DJ)»; «Archie Hamilton» a secas es un político. Solo es fiable el sitelink del ítem de Wikidata.

## C. Artistas underground

| Artista | Objetivo | Respaldo encontrado | Confianza | Pendiente |
|---|---|---|---|---|
| Priku | Atipic | Discogs: «runs the label Atipic and Atipic (live) project» (CC0) | Alta (identidad por MBID → Discogs) | Sunrise / Sunwaves: **sin fuente reutilizable** (solo RA, que no autoriza acceso automático). Foto: ninguna con licencia |
| ANOTR | Dúo, NO ART, trayectoria, sonido | Discogs (CC0): dúo de Ámsterdam, NO ART en 2017, integrantes. Wikipedia de/nl (CC BY-SA): trayectoria, house | Alta | Foto: un archivo de Commons (CC BY-SA 4.0) **compartido con otro artista**; requiere revisión humana |
| Traumer | get-traum, estilo | Discogs: «Owner of record label Gettraum» (CC0); MusicBrainz: «house/techno» | Alta | Trayectoria: sin fuente. Foto: ninguna |
| Cloonee | Sellos, tech house | Discogs: «founder of Hellbent Records» (CC0); MusicBrainz y Wikidata: tech house | Alta | Trayectoria: sin fuente. Foto: ninguna (Openverse solo devuelve lugares de Irlanda con ese nombre) |

## D. Fotografías

- **Con identidad verificada y licencia libre (utilizables): 4/12.** Capriati, Carola (CC BY 2.0), Osuna (CC BY-SA 2.0) y
  Chris Stassy (CC0), todas por P18/P180 en Wikidata/Commons. Ya las resuelve el pipeline actual.
- **Candidatas con licencia libre, pendientes de verificar a mano: 2.** Jamie Jones (Commons, CC BY-SA 3.0, 2 archivos sin
  P18/P180) y ANOTR (Commons, CC BY-SA 4.0, foto compartida).
- **Fotos con licencia NC (solo uso no comercial): 4.** Flickr «EXIT Festival» (Capriati, Jones, Carola) y otra de Osuna.
  Solo valdrían mientras el proyecto siga sin monetizar; hoy no se cuentan.
- **Fotos presentes pero no reutilizables:** Discogs (12/12, «Restricted Data»), Deezer (11/12, prohibido), TheAudioDB (3/12, fans).
- **Sin ninguna foto con licencia:** Priku, Traumer, Cloonee, Bicep, Josh Baker y Archie Hamilton.

## E. Ranking de integración

**Integrar**
1. **Discogs: perfil del artista (CC0) a partir del enlace de MusicBrainz.** Es lo que más cobertura añade (4/4 artistas
   underground con sello o proyecto confirmado), sin clave, con identidad segura y licencia explícita.
2. **Wikipedia en otras lenguas por sitelink de Wikidata**, solo cuando falten es/en (ANOTR, Chris Stassy). Misma licencia
   que hoy. Ojo: el selector clasifica en inglés y español; con otras lenguas, solo serviría la frase de presentación.
3. **Fotos de Commons sin enlazar, mediante curación manual** en el catálogo editorial: archivo, licencia y autor revisados
   por una persona. Openverse sirve para encontrarlas, nunca para asignarlas automáticamente.

**Investigar permisos o credenciales**
- ListenBrainz (token gratuito): canciones destacadas y artistas similares por MBID.
- Setlist.fm (clave no comercial): para SetLab.
- Flickr (clave no comercial): fotos CC, con verificación humana.
- Last.fm y Fanart.tv: baja prioridad (imágenes excluidas o licencia sin confirmar).

**Descartar**
TheAudioDB, Deezer, iTunes, Music Story, Resident Advisor (salvo permiso por escrito), Beatport, Bandcamp, SoundCloud,
Mixmag, DJ Mag, Electronic Groove y 1001Tracklists.

## F. Arquitectura propuesta (sin implementar)

- `musicbrainz.artist()` ya trae los enlaces de Discogs. Un cliente pequeño `discogs.artist(id)` con User-Agent propio y
  25 req/min devolvería un `SourceDoc("Discogs (perfil)", url, "CC0", texto)`: perfil sin marcado `[l=…]`/`[a=…]`,
  más «Integrantes» y «Grupos» como campos.
- Licencia y atribución: guardar el texto como CC0 y mostrar «Data provided by Discogs» con enlace en la lista de fuentes.
  Caché: TTL corto para la respuesta cruda (≤ 6 h) mientras no se aclare si la regla aplica a los datos CC0, o bien usar
  los volcados mensuales (CC0 sin condiciones).
- Nombre real: no mostrarlo (dato personal; no aporta a la biografía).
- El selector no cambia de lógica. Solo habría que decidir si «Discogs (perfil)» cuenta como texto descriptivo
  (`DESCRIPTIVE`), que es lo que permitiría biografías breves para los artistas sin Wikipedia.

## G. Próximo paso

**Integrar el perfil de Discogs (CC0) como fuente de hechos**, empezando por Priku, ANOTR, Traumer y Cloonee: sello o
proyecto propio confirmado, origen e integrantes. Es una integración pequeña, sin clave ni coste, con identidad por
MBID → Discogs y licencia explícita, y es la única que convierte a los cuatro artistas sin fuentes en artistas con al
menos un hecho editorial verificable.

## H. Estado de la integración (capa 1.1)

- Implementado: `backend/app/discogs.py`, un cliente aislado. Identidad solo por ID enlazado desde MusicBrainz. Lee
  únicamente nombre, notas e integrantes/grupos (CC0), nunca imágenes, nombre real ni enlaces. User-Agent propio,
  2,5 s entre peticiones (25/min), un único reintento ante 429/503 y caché **solo en memoria, de 6 horas**.
  `facts.py` reconoce «Discogs (perfil)» como texto descriptivo y «Discogs (relaciones)» como campos; «owner of» cuenta
  como dirigir o poseer, no como fundar. Las notas de Discogs ceden ante Wikipedia y MusicBrainz cuando compiten.
- **No conectado a la recopilación** (`api.collect`). Los términos de la API prohíben mostrar contenido con más de 6 h y
  guardarlo más de lo necesario, y el pipeline guarda en SQLite el expediente (con el texto de cada hecho) y la
  biografía derivada durante 90 días. No se ha creado ninguna excepción.
- **Alternativa evaluada: volcados mensuales CC0** (`discogs_20261001_artists.xml.gz`, 475,7 MB; `labels`, 87,0 MB).
  Son CC0 sin las condiciones de la API, así que permiten guardar los hechos y la biografía como el resto de fuentes.
  Coste: descargar unos 560 MB y crear un índice local fuera de Git (ID → nombre, perfil, integrantes, grupos;
  sellos ID → nombre) con la biblioteca estándar (gzip + iterparse), actualizable cada mes.
- Antes de que Discogs pueda producir biografías faltan dos decisiones:
  1. El umbral de 150 caracteres de texto descriptivo (`sources.sufficient`) no cuenta Discogs; y aunque lo contara,
     los cuatro perfiles underground tienen entre 65 y 96 caracteres.
  2. El validador solo acepta como evidencia de fundación Wikipedia, la web oficial y las relaciones de MusicBrainz:
     «fundaron NO ART» se rechaza aunque esté en Discogs.

Scripts y salidas de esta investigación (temporales, fuera del repositorio): carpeta `research` del scratchpad de la sesión.
