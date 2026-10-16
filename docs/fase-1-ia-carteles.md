# Fase 1.4 — IA multimodal para carteles musicales

Experimento en [`research/poster_ai/`](../research/poster_ai/README.md). Fecha: 2026-10-16. No toca `mobile/` ni `backend/` ni las fases anteriores.

> **Estado: cerrada (2026-10-16).** Se han hecho **5 llamadas de análisis**, sin reintentos: una por cartel con el esquema original y una más con la **variante compacta** para SW38. Además se consultó el listado de modelos (`GET /openai/v1/models`), que no consume tokens. **Conclusión:** Groq (`qwen/qwen3.8-27b`) queda seleccionado provisionalmente para extraer artistas, con revisión humana obligatoria. La variante compacta es la candidata para continuar. Resultados y decisiones en §8.

## 1. Modelo seleccionado

| | Comprobado (2026-10-16) |
|---|---|
| **Identificador** | `qwen/qwen3.8-27b` |
| Estado | **Preview**: «should not be used in production environments as they may be discontinued at short notice» ([Models](https://console.groq.com/docs/models)) |
| Disponible para nuestra clave | Sí: `GET /openai/v1/models` lo devuelve con `active: true`. Es el **único modelo de visión** de los 11 disponibles para la cuenta. |
| Visión | Entrada de imagen y texto, salida de texto. Hasta 3 imágenes por petición, **cada una cuenta como 2 048 tokens de entrada** y el tamaño máximo es de 20 MB ([Vision](https://console.groq.com/docs/vision), [ficha del modelo](https://console.groq.com/docs/model/qwen/qwen3.8-27b)). |
| JSON | Modo JSON (`response_format: json_object`), con un ejemplo oficial que usa imagen. También tiene modo JSON Schema, sin ejemplo con imagen. |
| Razonamiento | Activado por defecto. Se usa `reasoning_effort: "none"` (modo instruct) para reducir tokens y latencia. |
| Límites | Tabla del plan **Developer**: 30 RPM, 1 000 RPD, 8 000 TPM y 200 000 TPD ([Rate limits](https://console.groq.com/docs/rate-limits)). **Los límites del plan gratuito no están publicados** en esa página (solo hay una pestaña «Free Plan Limits» sin cifras). **Observados en las cabeceras de nuestra cuenta** (2026-10-16): `x-ratelimit-limit-requests: 1000` (peticiones por día) y `x-ratelimit-limit-tokens: 8000` (tokens por minuto). El límite de tokens diario no viene en las cabeceras. |
| Precio (referencia) | 0,80 $ por millón de tokens de entrada y 4,00 $ por millón de salida. No se activa ningún servicio de pago. |

Alternativas descartadas:

- `meta-llama/llama-4-scout-17b-16e-instruct` y `llama-4-maverick`: **retirados** (cierres el 17-07-2026 y el 09-03-2026, según [Deprecations](https://console.groq.com/docs/deprecations)).
- `meta-models/muse-spark-open`: visión en *limited preview*, con acceso previa solicitud, y no aparece en nuestra cuenta.

## 2. Metodología

1. Entre 3 y 5 carteles reales de dificultad creciente, guardados en local (§4).
2. Una persona transcribe la **referencia manual** de cada cartel antes de ver la salida del modelo.
3. **Una llamada por cartel**: la imagen va en base64 junto con el prompt, con `temperature: 0`, `json_object`, `reasoning_effort: none` y `max_completion_tokens: 4096`. Se registran la latencia (reloj local), `usage` (tokens), `x_groq.id`, `finish_reason` y las cabeceras de límite.
4. Validación estructural del JSON (`poster_schema.validate`).
5. Evaluación offline (`evaluate.py`):
   - Se normalizan espacios, mayúsculas y acentos solo para comparar.
   - Las grafías alternativas solo cuentan si la referencia las acepta (`accepted_variants`).
   - Las coincidencias aproximadas (similitud ≥ 0,85) van a **revisión humana** y **no cuentan como acierto**.

Reglas del prompt (en [`poster_schema.py`](../research/poster_ai/poster_schema.py)):

- Solo texto visible.
- No inventar ni completar nombres con conocimiento musical, y conservar la grafía.
- Un nombre parcial va marcado como `uncertain`, nunca como identificación segura.
- `iso` solo si se ven día, mes y año; no se deducen años de otra parte del cartel.
- B2B: cada artista por separado y la relación en `b2b`, sin deducir orden de actuación, duración ni horario. Un colectivo con miembros entre paréntesis es un solo artista.
- Distinguir lo ilegible (`unreadable_text`) de lo ausente (`null` o `[]`).
- Sin géneros ni confianzas numéricas.

## 3. Esquema JSON

```json
{
  "event_name": null,
  "dates": [{"text": "SAT 12 JULY 2025", "iso": "2025-07-12"}],
  "location": null,
  "stages": [],
  "artists": [{"name": "Nombre leído", "stage": null, "day": null, "time": null, "uncertain": false}],
  "unreadable_text": [],
  "sessions": [{"date": {"text": "03.09", "iso": null}, "label": "THURSDAY NIGHTTIME", "stage": "1", "time": "22:00", "artists": ["Nombre leído"]}],
  "b2b": [{"artists": ["Nombre A", "Nombre B"], "text": "NOMBRE A B2B NOMBRE B"}]
}
```

Cambios respecto a la propuesta, y por qué:

- `dates` pasa a ser una lista de objetos con el **texto impreso** y un `iso` opcional, para no forzar fechas incompletas.
- Se añade `stages`, la lista de escenarios del cartel.
- Se añade `artists[].day`, porque en carteles de varios días el horario depende del día.
- Se añaden `sessions` (opcional), para los bloques de día, franja y escenario con su hora impresa, y `b2b` (opcional), para conservar las actuaciones conjuntas sin fundir los nombres. Las salidas sin estas claves siguen siendo válidas.

El validador rechaza claves no previstas, tipos incorrectos, nombres vacíos y fechas `iso` mal formadas.

## 4. Casos de evaluación

Carteles reales guardados por el usuario en `research/poster_ai/data/posters/` (no se versionan). Las referencias están en `research/poster_ai/data/references/`.

| Archivo | Caso | Evento | Referencia | Dry-run |
|---|---|---|---|---|
| `01_sencillo.jpg` (387×516, 0,02 MB) | Pocos artistas | Now Here by Paco Osuna, Medellín, 2026-11-28 | 6 artistas | OK |
| `02_muchos_artistas.jpg` (1080×1350, 0,04 MB) | Muchos artistas, tipografía manuscrita | Circo Loco, DC-10 Ibiza, New Year's Day (sin año) | 18 actos | OK |
| `03_diseno_complejo.png` (1920×1920, 1,37 MB) | Diseño gráfico complejo | Solid Grooves, DC-10, 2026-09-10 | 10 artistas | OK |
| `04_horarios_escenarios.webp` (1090×1350, 0,19 MB) | Horarios y escenarios | SW38, Roquetas de Mar, 3–7 de septiembre de 2026 | 54 artistas, 12 bloques, 4 B2B | OK |

El cartel 03 llegó en AVIF, que el script no admite. Se ha convertido **sin pérdida a PNG** con ffmpeg, con la misma resolución (1920×1920). El AVIF original se conserva en local y no se analiza.

Criterios aplicados en las referencias (también anotados en el campo `_review` de cada JSON):

- **B2B** (SW38): Cuky/Persic, Jamie Jones/Joseph Capriati, Rober Peinado/Gabi y Sera de Villalta/Felipe Bravo. Cada miembro figura por separado en `artists` y en su bloque, y la relación va en `b2b` con el orden impreso. No hay orden de actuación, duración ni horario individual.
- **Colectivos**: `[A:RPIA:R]` (Circo Loco) es un único acto; sus miembros entre paréntesis no cuentan aparte.
- **Variantes aceptadas**: `ROSSI` por `ROSSI.`, y `LIVE` opcional en Ion Ludwig y Alexis Cabrera.
- **Años**: no se deducen. Circo Loco no tiene año, y los bloques de SW38 (`03.09`…) van con `iso: null`. Solo llevan `iso` las fechas con el año impreso (01 y 03).
- **SW38**: se conserva el rango general `3-7 SEPTEMBER 2026` y solo los 12 bloques que aparecen (03.09 a 06.09); no se inventa el día 7. La hora `22:00` es la del inicio del bloque, y solo figura en 4 de ellos.
- **Fuera del lineup**: la firma del artista visual Felipe Pantone (03), los logotipos de promotores y patrocinadores, y lemas como «MUSIC MADE VISIBLE» o «IBIZA26».
- **Ilegible o dudoso**: no se corrige por intuición, solo se señala. El texto bajo el escudo de SW38 va en `unreadable_text`, y `5UNIVERSOS` se transcribe tal cual, sin aceptar `SUNIVERSOS`, de modo que una variante irá a revisión humana.

**Pendiente de confirmación humana** (no bloquea la ejecución):

- Grafías de 02: `JNJS`, `SEDEF ADASÏ`, `DEMI RIQUÍSIMO`.
- Grafías de 04: `5UNIVERSOS`, `DYED SOUNDOROM`, `CRISTIAN MARTLANDED`, `MIN8`, `GOJNEA76`, `BLIEZT`, `GEOUSHY`, `MIHIGH`, `JOËLLA JACKSON`.
- El número `#51D-14` de la dirección en 01, que solo afecta a una variante de ubicación.

## 5. Métricas y resultados

### Cartel 01 (Now Here by Paco Osuna): 1 llamada

| | Resultado |
|---|---|
| Respuesta | HTTP 200, `finish_reason: stop`, JSON válido, 0 errores de esquema |
| Artistas | **6/6 correctos**: 0 omitidos, 0 inventados, 0 en revisión, ninguno marcado como dudoso. **Precisión 1,0 y recall 1,0.** |
| Evento y fecha | `NOW HERE BY PACO OSUNA` (coincide) y `SATURDAY NOV 28, 2026` → `2026-11-28` (exacta) |
| Ubicación | **No coincide**: `SCENE JARDÍN BOTÁNICO \| CL. 73 #51D-14, ARANJUEZ MEDELLÍN, COLOMBIA`. Ha metido en la ubicación el logotipo del promotor «SCENE»; la dirección sí está bien leída. |
| Sin invenciones | Escenarios, horarios, bloques y B2B vacíos, como corresponde |
| Latencia | 1,39 s de reloj local (`total_time` de Groq: 1,01 s; cola: 0,21 s) |
| Tokens | 2 397 de entrada y 429 de salida, 2 826 en total |
| Límites tras la llamada | Peticiones: 999 de 1 000 restantes; tokens: 5 144 de 8 000 restantes por minuto |

### Cartel 02 (Circo Loco): 1 llamada

| | Resultado |
|---|---|
| Respuesta | HTTP 200, `finish_reason: stop`, JSON válido, 0 errores de esquema |
| Artistas | **Los 18 actos de referencia, todos reconocidos.** Hay 1 entrada sobrante: `(PETRE INSPIRESCU RARESH - RHADOO)` como artista aparte, cuando con el criterio acordado forma parte de `[A:RPIA:R]`; cuenta como **inventado**. Lo ha transcrito del cartel, no se lo ha inventado. **Precisión 0,947 (18/19) y recall 1,0.** 0 omitidos, ninguno marcado como dudoso. |
| Grafías | `[A:RPIA:R]`, `ROSSI.`, `JNJS` y `DEMI RIQUÍSIMO` coinciden. **Dudosa:** `SEDEF ADAŞI` (Ş con cedilla y una I sin diéresis) frente a `SEDEF ADASÏ` de la referencia. El evaluador lo da por correcto porque al comparar quita los diacríticos: es una limitación del evaluador que hay que tener en cuenta. |
| Evento | **No coincide**: `CIRCO LOGO NEW YEAR'S DAY` (lee LOGO por LOCO). |
| Fecha | `NEW YEAR'S DAY` con `iso: null`: **no inventa el año**. |
| Ubicación | `DC-10 IBIZA` (coincide) |
| Latencia | 2,48 s de reloj local |
| Tokens | 2 397 de entrada y 982 de salida, 3 379 en total |
| Límites tras la llamada | Peticiones: 999 de 1 000 restantes; tokens: 5 126 de 8 000 restantes por minuto |

### Cartel 03 (Solid Grooves): 1 llamada

| | Resultado |
|---|---|
| Respuesta | HTTP 200, `finish_reason: stop`, JSON válido, 0 errores de esquema |
| Artistas | **10/10 correctos**: 0 omitidos, 0 inventados, ninguno marcado como dudoso. **Precisión 1,0 y recall 1,0.** No incluye la firma de Felipe Pantone ni lemas o elementos gráficos («MUSIC MADE VISIBLE», «IBIZA26»). |
| Grafías | **Dudosa:** `REELow` (minúsculas en «ow») frente a `REELOW`. El evaluador lo da por correcto porque no distingue mayúsculas; la tipografía pixelada puede explicar la lectura. |
| Evento y fecha | `SOLID GROOVES` (coincide) y `SEPTEMBER 10 2026` → `2026-09-10` (exacta) |
| Ubicación | **No coincide**: `IBIZA26`. Toma la marca de temporada como ubicación y omite el logotipo `DC-10`. |
| Latencia | 2,66 s de reloj local (`total_time` de Groq: 1,62 s; cola: 0,48 s) |
| Tokens | 1 885 de entrada y 566 de salida, 2 451 en total. Los tokens de entrada son **menos** que en 01 y 02 (2 397) con la misma petición, así que la imagen no cuesta siempre 2 048 tokens fijos. |
| Límites tras la llamada | Peticiones: 999 de 1 000 restantes; tokens: 4 365 de 8 000 restantes por minuto |

### Cartel 04 (SW38): 1 llamada, salida truncada

| | Resultado |
|---|---|
| Respuesta | HTTP 200, pero **`finish_reason: length`**: agota los 4 096 tokens de salida (`max_completion_tokens`). El JSON se puede leer, pero termina en el 7.º bloque, que está incompleto y sin `artists`, así que hay **1 error de esquema**. Oficialmente **no se evalúa**. No se repitió la llamada. |
| Causa | El modelo repite día y hora en cada uno de los 54 artistas y además los vuelve a listar en `sessions`, lo que duplica la salida. |

**Diagnóstico no oficial** de la parte recibida, con las mismas funciones de `evaluate.py`, sin modificarlas:

| | Resultado |
|---|---|
| Artistas | **52/54 correctos**: precisión 0,963 y recall 0,963. `SUNIVERSOS` en lugar de `5UNIVERSOS` (va a revisión humana, similitud 0,90). `GEOSH` en lugar de `GEOUSHY` (cuenta como inventado + omitido). Ninguno marcado como dudoso. |
| B2B | Separa bien los 8 miembros (Cuky/Persic, Jamie Jones/Joseph Capriati, Rober Peinado/Gabi, Sera de Villalta/Felipe Bravo), pero **no llega a escribir `b2b`**, por el truncado: 0/4 relaciones. |
| Escenarios | `["1", "2"]` y **52/52** artistas en su escenario correcto. |
| Bloques | Recibe 6 de 12 completos y los 6 coinciden. La asignación de artistas es correcta salvo GEOSH y SUNIVERSOS, y el recall global de asignación se queda en 0,463 por los bloques que faltan. La hora del bloque es correcta en 5; **inventa `22:00`** para 04.09 NIGHTTIME en el escenario 2, que no la imprime. |
| Horarios individuales | **Inventa 23**: copia `22:00` a cada DJ de los bloques nocturnos, incluidos 8 DJ de bloques sin hora impresa (escenario 2 del 04.09 y del 05.09 por la noche). Incumple la regla explícita del prompt. |
| Días | En `artists[].day` coloca a MIHIGH, CAP, CEZAR y ANDREI CIUBUC en «06.09 SUNDAY DAYTIME», cuando son de NIGHTTIME. |
| Años y día 7 | **Deduce el año** en los bloques (`iso: 2026-09-03`… a partir de «03.09») y vuelve a incumplir el prompt. Conserva el rango `3-7 SEPTEMBER 2026` sin `iso`. **No inventa el día 7.** |
| Evento y ubicación | `SW38` y `ROQUETAS DE MAR, SPAIN`: los dos coinciden. |
| Latencia y tokens | 8,69 s. 2 397 de entrada y 4 096 de salida (el tope), 6 493 en total. |

### Variante compacta: SW38, 1 llamada adicional

Es una única mejora controlada: mismo modelo, misma imagen, misma configuración y mismo tope de 4 096 tokens. Solo cambian el prompt y el esquema. Los resultados originales no se han tocado (comprobado con md5) y la salida va a `data/outputs/compact/`.

- **Esquema compacto** (`COMPACT_PROMPT` y `validate_compact` en `poster_schema.py`):
  - Cada nombre aparece **una sola vez**: dentro de su sesión, o en `artists` si el cartel no tiene bloques.
  - Las horas individuales van en `individual_times`, solo si están impresas junto al nombre.
  - Las dudas van en `uncertain` y los B2B en `b2b`.
  - `expand_compact` lo convierte de forma determinista al esquema original, de modo que se evalúa con las mismas referencias y métricas.
- **Auditoría determinista** (`audit_extraction`):
  - Descarta, y anota en `review`, las horas individuales iguales a la hora de inicio de su sesión o repetidas en varios artistas del bloque.
  - Descarta el `iso` cuyo año no está impreso en esa misma fecha.
  - En la variante compacta se aplica a la extracción; en la original solo informa.
- **`finish_reason: length`** pasa a ser `error_kind: incomplete`: el script sale con código 5 y el evaluador no evalúa esa salida.
- **Grafía estricta** (`exact_spelling` / `spelling_diffs`), además de la comparación normalizada, que no cambia. En los carteles originales detecta `SEDEF ADAŞI` y `REELow`: 32/34 artistas tienen la grafía exacta.

| | Original (truncada) | Compacta |
|---|---|---|
| Respuesta | `length`, incompleta, 1 error de esquema | **`stop`, completa, JSON válido, 0 errores** |
| Artistas (evaluación oficial) | no evaluable (diagnóstico: 52/54) | **51/54**: precisión y recall 0,944; grafía exacta 51/51 |
| Errores de nombre | `SUNIVERSOS`, `GEOSH` | `SUNIVERSOS` (revisión), `GEOSH`, `BLUEZT` (por `BLIEZT`) |
| Sesiones | 6/12 recibidas | **11/12 emparejadas**; 9 con los artistas exactos. **Fusiona** el bloque 03.09 del escenario 2 con el 04.09 DAYTIME del escenario 2, al que da la hora `22:00` y 4 artistas que no son suyos. Recall de asignación: 0,87. |
| Escenarios | 52/52 | 51/51 artistas en su escenario correcto |
| B2B | 0/4 (truncado) | **4/4** (en dos el texto solo recoge la segunda línea, «B2B JOSEPH CAPRIATI») |
| Horarios individuales inventados | 23 | **0** (el modelo no da ninguno; la auditoría no tuvo que descartar nada) |
| Años deducidos en los bloques | sí | **no** (todos con `iso: null`) |
| Día 7 inventado | no | no |
| Evento y ubicación | correctos | correctos |
| Tokens | 2 397 + 4 096 = 6 493 | 2 390 + 1 540 = **3 930 (−39 %; salida −62 %)** |
| Latencia | 8,69 s | **4,03 s** |

### Agregado oficial del esquema original (`evaluate.py`, 3 carteles evaluables de 4)

| Métrica | Valor |
|---|---|
| JSON válido y conforme | 3/4 (el 04 se truncó) |
| Artistas | 34 correctos de 34, con 35 predichos: **precisión 0,971 y recall 1,0**. 0 omitidos y 1 inventado (los miembros de [A:RPIA:R] como artista aparte). |
| Evento | 2/3 (falla `CIRCO LOGO`) |
| Ubicación | 1/3 (fallan 01, que incluye el logotipo SCENE, y 03, que da IBIZA26 sin DC-10) |
| Fechas exactas | 3/3, sin años inventados |
| Latencia | 1,39 / 2,48 / 2,66 / 8,69 s |
| Tokens (4 llamadas) | 9 076 de entrada y 6 073 de salida, **15 149 en total** |

Sumando el diagnóstico del 04: **86/88 artistas correctos**, con 2 grafías erróneas (las dos en el 04) y 2 grafías dudosas que el evaluador da por buenas porque ignora mayúsculas y diacríticos (`SEDEF ADAŞI`, `REELow`).

Las salidas quedan en `research/poster_ai/data/outputs/` (no se versionan). El evaluador calcula:

- Por cartel: JSON válido y conforme al esquema; artistas correctos, omitidos, inventados y en revisión; precisión y recall; coincidencia del nombre del evento y de la ubicación; fechas exactas, faltantes y sobrantes; aciertos de escenario y horario por artista; horarios individuales inventados; bloques (`sessions`) emparejados y asignación de artistas; relaciones B2B correctas, omitidas y sobrantes (un B2B sin separar cuenta como artista inventado); latencia; tokens de entrada y salida.
- En conjunto: las mismas métricas agregadas.

## 6. Errores y limitaciones

| Aspecto | Estado |
|---|---|
| Errores gestionados | 401/403 (autenticación), 429 (límite, con `retry-after`), 400/413 (petición o imagen), 5xx, timeout (90 s), red y respuesta no JSON. **Sin reintentos automáticos**: tras un error de autenticación o de límite, el script se detiene. **Comprobado con las pruebas offline.** |
| Repetición y presupuesto | No repite un cartel que ya tiene salida y se corta a las 5 llamadas registradas. **Comprobado offline.** |
| Clave | Se lee del entorno o de `research/music_sources/.env`; no aparece en salidas, registros ni URL (hay prueba offline con una clave falsa). |
| Tamaño de imagen | La documentación da 20 MB para imágenes **por URL**; para base64 no da límite. Se usa un **tope prudente de 4 MB**, sin verificar contra la API: **pendiente**. Tampoco se publica la resolución máxima: **pendiente**. Sin dependencias no se puede reescalar; la imagen se reduce a mano si hace falta. |
| Modelo en preview | Puede retirarse sin aviso; ya ha pasado con Llama 4. |
| Carteles de muchos artistas | La lectura es buena (18 actos manuscritos y 54 en tabla). El límite real es la **salida**: con 54 artistas y bloques, 4 096 tokens no bastan. |
| Respuesta truncada | **Resuelto**: `finish_reason: length` se trata como `incomplete` (código de salida 5, no se evalúa). Probado offline. |
| Evaluador | Normaliza mayúsculas y diacríticos. **Resuelto** con una comparación estricta adicional (`exact_spelling`), que no sustituye a la normalizada. |
| Estructura de bloques | Incluso en la variante compacta, el modelo puede fusionar bloques contiguos (SW38: el 03.09 del escenario 2 con el 04.09 del escenario 2). La validación no lo detecta: requiere revisión humana o referencias. |
| Tokens de imagen | No son 2 048 fijos: el 03 (PNG de 1920×1920) gastó 1 885 de entrada, frente a 2 397 de los demás. |

## 7. Consumo y viabilidad gratuita

- **Estimación por cartel**: unos 2 048 tokens de imagen, unos 500 de prompt y entre 300 y 1 500 de salida según el número de artistas, es decir, **unos 3 000–4 000 tokens**. Medido en el cartel 01 (6 artistas): **2 826 tokens**; en el cartel 02 (18 actos): **3 379 tokens**; en el cartel 03 (10 artistas, PNG de 1920×1920): **2 451 tokens**.
- Con los límites del plan Developer (8 000 TPM), cabrían unos **2 carteles por minuto** y unos 50 al día con 200 000 TPD.
- **Plan gratuito observado**: 1 000 peticiones al día y 8 000 tokens por minuto. Un cartel grande (6 493 tokens) consume casi todo el minuto, mientras que los pequeños (unos 2 500–3 400) permiten 2 o 3 por minuto. El límite diario de tokens no aparece en las cabeceras. En las 4 llamadas no hubo errores 429.

## 8. Conclusión y decisiones (cierre de la Fase 1.4, 2026-10-16)

**Fase cerrada. No se harán más llamadas a Groq en esta fase.**

| Llamada | Tipo de resultado | Artistas | Respuesta | Tokens | Latencia |
|---|---|---|---|---|---|
| 1. Cartel 01, esquema original | **Oficial** | 6/6 (P 1,0 · R 1,0) | completa | 2 826 | 1,39 s |
| 2. Cartel 02, esquema original | **Oficial** | 18/18, 1 sobrante (P 0,947 · R 1,0) | completa | 3 379 | 2,48 s |
| 3. Cartel 03, esquema original | **Oficial** | 10/10 (P 1,0 · R 1,0) | completa | 2 451 | 2,66 s |
| 4. Cartel 04, esquema original | **Diagnóstico parcial** (no oficial: truncada) | 52/54 en la parte recibida (P 0,963 · R 0,963) | `length` | 6 493 | 8,69 s |
| 5. Cartel 04, **variante compacta** | **Oficial, solo para la variante** | 51/54 (P 0,944 · R 0,944) | completa | 3 930 | 4,03 s |

- **Métricas oficiales del esquema original** (01–03): 34/34 artistas, precisión 0,971 y recall 1,0. Evento 2/3, ubicación 1/3, fechas 3/3. 32/34 con la grafía exacta.
- **Diagnóstico parcial** (04 original): solo orientativo; no se suma al agregado oficial. Muestra 23 horarios individuales inventados, años deducidos y 0/4 B2B por el truncado.
- **Variante compacta** (04): completa, con 11/12 sesiones emparejadas (9 exactas y 1 fusión), 4/4 B2B, 0 horarios inventados, 0 años deducidos y escenarios 51/51. Tres nombres mal leídos (`SUNIVERSOS`, `GEOSH`, `BLUEZT`).
- **Total de las 5 llamadas:** 19 079 tokens (11 466 de entrada y 7 613 de salida), sin errores de API ni de límite.

### Decisiones

1. **Groq con `qwen/qwen3.8-27b` queda seleccionado provisionalmente para extraer artistas de carteles**, con **revisión humana obligatoria** antes de usar el resultado.
2. **La variante compacta es la candidata para continuar.** Solo se ha probado con SW38, así que debe validarse con más carteles antes de darla por buena.
3. **No se consideran fiables sin validación:** horarios, fechas parciales, ubicación, nombre del evento y agrupación en sesiones o bloques.
4. **El modelo está en *preview*.** Antes de llegar a producción hay que tener prevista y probada una alternativa.
5. **No se integra todavía en `mobile/` ni en `backend/`.** El código queda como experimento en `research/poster_ai/`.

### A tener en cuenta en el diseño futuro de la app

- **Flujo de revisión:** la extracción es una **propuesta**. La app debe mostrar los artistas detectados para que el usuario los confirme, corrija o descarte antes de guardarlos o usarlos en búsquedas.
- **Grafías:** no se debe corregir automáticamente con conocimiento musical. Hay que conservar el texto leído y señalar los nombres dudosos. El modelo casi nunca marca sus dudas (`uncertain` salió vacío en todas las llamadas), así que no se puede confiar en esa marca.
- **Campos estructurados:**
  - Las horas de bloque no son horas por DJ.
  - Las fechas sin año quedan sin fecha ISO.
  - La ubicación y el nombre del evento se muestran como texto editable, no como dato validado.
  - Las sesiones pueden venir fusionadas.
- **Salvaguardas que hay que mantener:**
  - Tratar `finish_reason: length` como incompleto.
  - Validar el esquema.
  - Aplicar la auditoría determinista de horarios y años.
  - No hacer reintentos automáticos que gasten cuota.
  - Mantener un presupuesto de llamadas.
- **Seguridad:** la clave de Groq solo puede vivir en el servidor. Nunca en la app ni en `EXPO_PUBLIC_*`; la llamada al modelo tendrá que pasar por el backend.
- **Coste y límites:** con el plan gratuito se observan 1 000 peticiones al día y 8 000 tokens por minuto. Un cartel ocupa entre 2 500 y 4 000 tokens con la variante compacta, es decir, unos 2–3 carteles por minuto. Hará falta una cola o un límite por usuario. El límite diario de tokens sigue sin conocerse.
- **Imágenes:**
  - Aceptar solo JPEG, PNG o WebP de tamaño acotado, y convertir otros formatos, como AVIF, antes de enviarlos.
  - Los carteles tienen derechos de terceros: no deben guardarse ni versionarse sin necesidad.
- **Dependencia del proveedor:** conviene aislar la extracción tras una interfaz propia (esquema compacto + validación), para poder cambiar de modelo o de proveedor.

### Pendiente para fases futuras

- Validar la variante compacta con los carteles 01–03 y con carteles nuevos.
- Detectar bloques fusionados.
- Evaluar un modelo alternativo.
- Confirmar el límite diario de tokens y el tamaño máximo en base64.
- Confirmar las grafías dudosas (§4).

Comprobado: documentación del modelo, disponibilidad en la cuenta, pruebas offline (13 tests, OK), `--dry-run` de los 4 carteles y las 5 llamadas reales evaluadas offline.
