# Fase 1 — Conclusiones y decisiones consolidadas

Documento maestro de cierre de la Fase 1 (investigación), del 2026-10-16. Consolida los informes de las fases 1.2 a 1.5 para preparar la Fase 2 (diseño). **No añade decisiones nuevas**: todo lo que figura como decidido está decidido en los informes enlazados, y lo que no lo está aparece como pendiente.

| Fase | Informe | Tema |
|---|---|---|
| 1.1 | — | **No hay ningún documento de la Fase 1.1 en el repositorio** (ni informe, ni commit, ni referencias). Su contenido no se reconstruye aquí. |
| 1.2 | [fase-1-cobertura-musical.md](fase-1-cobertura-musical.md) | Cobertura de MusicBrainz y Wikidata (11 casos) |
| 1.3A | [fase-1-generos-electronicos.md](fase-1-generos-electronicos.md) | Géneros electrónicos: API de Discogs y AcousticBrainz |
| 1.3B | [fase-1-discogs-dumps.md](fase-1-discogs-dumps.md) | Viabilidad de los volcados CC0 de Discogs |
| 1.4 | [fase-1-ia-carteles.md](fase-1-ia-carteles.md) | IA multimodal (Groq) para extraer datos de carteles |
| 1.5 | [fase-1-listenbrainz.md](fase-1-listenbrainz.md) | ListenBrainz: artistas similares, LB Radio y personalización |

> Todas las cifras proceden de **muestras pequeñas** (11 casos en 1.2–1.3, 4 carteles en 1.4 y 4 artistas en 1.5). Son indicativas, no estadísticas.

## 1. Objetivo de music-discovery

App móvil de **descubrimiento de música electrónica** (nombre provisional): una app Expo y un backend FastAPI. La Fase 0 dejó el entorno preparado, sin funciones musicales. La Fase 1 ha investigado **de dónde pueden salir los datos** (identidad, estilos, similitud, carteles) y con qué límites. Las funcionalidades de producto (**TrackDNA, análisis de carteles y SetLab**) **siguen pendientes de definición detallada**.

## 2. Matriz de fuentes

| Fuente | Estado | Uso | Limitaciones principales | Fase |
|---|---|---|---|---|
| **MusicBrainz** (datos centrales) | **Principal** | Identidad de artistas y grabaciones (MBID), ISRC, sellos, lanzamientos y enlaces externos (incluidos los IDs de Discogs) | 1 petición por segundo por IP y 503 intermitentes. Homónimos y erratas. Uso comercial sujeto a los niveles de soporte de MetaBrainz (pendiente) | 1.2, 1.5 |
| MusicBrainz (géneros y tags) | **Descartada** para producto | — | CC BY-NC-SA (no comercial) y escasos en electrónica | 1.2, 1.3B |
| **Volcados CC0 de Discogs** | **Principal provisional para estilos** | Géneros y estilos **por lanzamiento con procedencia**, cruzados por los IDs de Discogs de MusicBrainz | **Sin piloto** todavía (releases: 10,5 GB en gzip). Pendientes: revisión legal (CC0, cadena de derechos, marca) y alojamiento | 1.3B |
| API de Discogs | **Descartada** para producto (solo investigación) | — | Estilos no CC0, regla de 6 h, almacenamiento limitado y riesgo de revocación | 1.3A |
| **Wikidata** | **Complementaria** | Enriquecimiento de artistas, solo con el ítem validado por MBID | No sirve para canciones; referencias de calidad variable | 1.2 |
| **ListenBrainz Labs** (similar artists) | **Complementaria** (opcional) | Artistas similares por MBID; nunca la única fuente de recomendaciones | Servicio experimental. Cobertura irregular (PAWSA 0, Traumer 4). Sin límites publicados. Licencia sin confirmar | 1.5A |
| **Groq** `qwen/qwen3.8-27b` | **Experimental** (seleccionado provisionalmente) | Extracción de **nombres de artistas** de carteles, con revisión humana obligatoria | Modelo en *preview*. Horarios, fechas parciales, ubicaciones y sesiones no fiables. Límites del plan gratuito | 1.4 |
| LB Radio | **Aplazada** | — | Exige token de usuario (401); calidad no evaluada | 1.5B |
| Cuenta y recomendaciones de ListenBrainz | **Aplazada** | — | Requieren cuenta e historial; endpoints experimentales; privacidad | 1.5C |
| Spotify (conexión o importación) | **Aplazada** (sin integración en V1) | — | Fuera del alcance de V1 | 1.5C/D |
| AcousticBrainz | **Descartada** | — | 1/9 de cobertura, congelado desde 2022 | 1.3A |
| Wikipedia | No evaluada | — | — | 1.2 |

## 3. Comprobado frente a experimental

**Comprobado en los experimentos** (con muestras pequeñas):

- MusicBrainz identifica bien artistas y grabaciones si se confirma el candidato: 4/5 canciones y candidatos para 6/6 artistas en 1.2, y 4/4 artistas en 1.5.
- Wikidata enriquece artistas cuando está validada por MBID.
- Discogs (por API) da estilos electrónicos específicos: 5/5 canciones en 1.3A.
- Los volcados CC0 de Discogs contienen géneros y estilos, y existen con tamaño y frecuencia conocidos (1.3B, sin descargar).
- Groq lee bien los nombres de artistas de carteles reales: oficial en 01–03, 34/34 con precisión 0,971 y recall 1,0. La variante compacta procesa un cartel grande completo.
- ListenBrainz Labs devuelve artistas similares sin clave para artistas con muchas escuchas.

**Experimental o sin demostrar:**

- Estilos a escala desde los volcados (falta el piloto y la proporción real de electrónica).
- Extracción fiable de horarios, fechas parciales, ubicación, nombre del evento y sesiones en carteles.
- Variante compacta del esquema de carteles: probada solo con SW38.
- Cobertura de similitud para DJs con pocas escuchas registradas.
- Calidad de LB Radio y de las recomendaciones personalizadas de ListenBrainz (sin evaluar).

## 4. Funcionalidades deseadas frente a viabilidad demostrada

| Capacidad | Viabilidad técnica | Evidencia |
|---|---|---|
| Identificar artistas y canciones por MBID, con confirmación en casos ambiguos | **Demostrada** (muestra pequeña) | 1.2, 1.5 |
| Enriquecer artistas con Wikidata | **Demostrada** | 1.2 |
| Estilo electrónico por lanzamiento | **Parcial**: demostrada por API, que no sirve para producto. Por volcados, sin piloto | 1.3A, 1.3B |
| Extraer artistas de un cartel con IA, con revisión humana | **Demostrada** (4 carteles) | 1.4 |
| Extraer programación (horarios, sesiones, B2B) de un cartel | **Parcial**: la variante compacta funcionó en 1 cartel, pero fusionó un bloque | 1.4 |
| Artistas similares para descubrir | **Parcial**: buena con artistas con muchas escuchas, nula o escasa con otros | 1.5A |
| Personalización por favoritos, preferencias e interacciones propias | **Deseada.** No requiere fuentes externas nuevas; no se ha implementado | 1.5C |
| BPM y tonalidad (SetLab) | **Sin fuente válida** | 1.3A |
| Enlaces de reproducción | **No investigada** (LB Radio solo daría MBID, según su documentación) | 1.5B |
| TrackDNA, análisis de carteles como producto, SetLab | **Pendientes de definición de producto** | — |

## 5. Fuentes recomendadas para V1 y sus limitaciones

- **MusicBrainz** como columna vertebral de identidad (solo datos centrales CC0). Requiere caché propia en el backend: llamar en directo desde cada usuario no escala con el límite por IP.
- **Volcados CC0 de Discogs** para estilos, **condicionados** a un piloto y a la revisión legal. Sin enlace fiable a Discogs, el estilo queda como «desconocido»; nunca se rellena por aproximación.
- **Wikidata** como enriquecimiento opcional de artistas.
- **ListenBrainz Labs** como señal complementaria y opcional de similitud, tolerando respuestas vacías.
- **Groq** solo si se incluye el análisis de carteles, como extractor de nombres con revisión humana y llamado siempre desde el backend.

## 6. Papel de la IA en el análisis de carteles

- **Qué hace:** propone la lista de artistas leída en el cartel. El usuario revisa, corrige o descarta antes de usarla. El modelo casi nunca marca sus dudas, así que no hay que confiar en esa marca.
- **Qué no es fiable sin validación:** horarios, fechas parciales, ubicación, nombre del evento y agrupación en sesiones.
- **Salvaguardas que se mantienen:**
  - Tratar `finish_reason: length` como respuesta incompleta.
  - Validar el esquema.
  - Aplicar la auditoría determinista de horarios y años.
  - No hacer reintentos automáticos.
  - Mantener un presupuesto de llamadas.
- **Clave de Groq:** solo en el servidor, nunca en la app ni en `EXPO_PUBLIC_*`.
- **Riesgos:** modelo en *preview* (hay que prever una alternativa) y límites del plan gratuito observados de 1 000 peticiones al día y 8 000 tokens por minuto.
- **Pendiente:** si el análisis de carteles entra en V1 y con qué alcance (ver §10).

## 7. Identificación de artistas mediante MBID

- El **MBID** es el identificador común: enlaza MusicBrainz, los IDs de Discogs, Wikidata y ListenBrainz.
- **No elegir automáticamente el primer resultado de búsqueda.** Hay homónimos peligrosos: Adrian Mills (la coincidencia exacta lleva a un músico de heavy metal), Traumer (coincide también con una banda de power metal), Blaze, Luciano y The Martinez Brothers.
- Correspondencias con **estado explícito**: exacta, por diacríticos o alias, corrección candidata, ambigua o no encontrada. En los casos ambiguos, el usuario confirma.
- Las erratas y los cambios de nombre (Stassy/Stussy, Mochackk) requieren **sugerencias con confirmación**, nunca normalización silenciosa.
- Los nombres extraídos de carteles pasan por la misma identificación.

## 8. Personalización propia basada en preferencias

Decisión de 1.5D para V1:

- **Personalización V1:** preferencias propias del usuario, artistas favoritos e interacciones sencillas dentro de la app.
- **Ni aprendizaje automático propio ni integración con Spotify en V1.** La integración con una cuenta de ListenBrainz queda pospuesta.
- La similitud de artistas (Labs) es solo una señal complementaria.

El diseño concreto (qué preferencias, qué interacciones y cómo se combinan) corresponde a la Fase 2.

## 9. Riesgos

| Tipo | Riesgo |
|---|---|
| Cobertura | Estilos de electrónica escasos en MusicBrainz; similitud irregular para DJs con pocas escuchas; carteles con programación compleja. |
| Identidad | Homónimos, erratas y cambios de nombre; posibles errores en los datos de escucha (KMA en 1.5A). |
| Costes | Hoy todo es gratuito. MetaBrainz pide un nivel de soporte a empresas con ingresos (Bronze desde 100 $/mes). Groq cobra por encima del plan gratuito. Hay que alojar los volcados de Discogs. |
| Licencias | Géneros y tags de MusicBrainz no comerciales. Volcados de Discogs pendientes de revisión legal (CC0, cadena de derechos, marca). Licencia de los datos de ListenBrainz sin confirmar. Lo obtenido por la API de Discogs no debe mezclarse con el almacén del producto. Los carteles tienen derechos de terceros. |
| Estabilidad | Modelo de Groq en *preview*; ListenBrainz Labs experimental; acceso a endpoints de ListenBrainz restringido recientemente; 503 intermitentes en MusicBrainz. |
| Privacidad | El historial de ListenBrainz es, por inferencia, público por nombre de usuario. Las imágenes de los carteles no deben guardarse sin necesidad. Las claves solo van en el backend. |

## 10. Descartado o aplazado

| Elemento | Estado | Motivo |
|---|---|---|
| AcousticBrainz | Descartado | Cobertura 1/9 y servicio congelado |
| Géneros y tags de MusicBrainz | Descartados para producto | Licencia no comercial |
| API de Discogs en producción | Descartada | Términos de uso de la API |
| LB Radio | Aplazado | Exige token; calidad no evaluada |
| Cuenta y recomendaciones de ListenBrainz | Aplazadas | Requieren cuenta e historial; experimentales |
| Spotify | Aplazado (sin integración en V1) | Fuera del alcance de V1 |
| Aprendizaje automático propio | Descartado para V1 | Sin datos ni necesidad demostrada |
| Fuente de BPM y tonalidad | Sin solución | AcousticBrainz descartado; no hay alternativa evaluada |

## 11. Decisiones pendientes para la Fase 2

1. **Definición de producto** de TrackDNA, análisis de carteles y SetLab, y cuáles entran en V1.
2. Si el análisis de carteles entra en V1: alcance (solo artistas o también programación), flujo de revisión humana y modelo alternativo previsto.
3. Ejecutar el **piloto de volcados de Discogs** y la **revisión legal**. Decidir el alojamiento y el tamaño asumible.
4. Arquitectura de **caché en el backend** para MusicBrainz (y Wikidata y Labs), dada la limitación por IP.
5. **Uso comercial**: si el proyecto tendrá ingresos y qué implica (nivel de soporte de MetaBrainz, licencias de ListenBrainz).
6. Diseño de la **personalización V1**: qué preferencias, favoritos e interacciones, y cómo se usa la similitud complementaria.
7. **SetLab**: buscar otra fuente de BPM y tonalidad o redefinir su alcance.
8. **Reproducción**: si V1 necesita enlaces a servicios de streaming y de dónde saldrían (no investigado).
9. **Nombre definitivo, identidad visual y diseño de pantallas.**
10. Ampliar las muestras (20–50 casos, más carteles y más artistas) antes de comprometer fuentes en producción.

## 12. Coherencia revisada

- Los informes 1.2 a 1.5 son coherentes entre sí. MusicBrainz es la identidad en todos. Discogs pasa de «problema abierto» (1.2) a «API no viable» (1.3A) y a «volcados como candidata provisional» (1.3B): es una evolución, no una contradicción.
- Se ha corregido el README, que daba la Fase 1 por cerrada pero solo enlazaba 1.2 y 1.3 y mantenía el estado general en Fase 0.
- **Hueco documental:** la Fase 1.1 no tiene informe en el repositorio.
