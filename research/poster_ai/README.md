# Experimento: IA multimodal para carteles (Fase 1.4)

Evalúa si un modelo de visión de Groq extrae bien los datos de carteles de eventos. Informe: [`docs/fase-1-ia-carteles.md`](../../docs/fase-1-ia-carteles.md). Solo usa la biblioteca estándar de Python 3.11.

## Pasos

1. Coloca 3–5 carteles reales en `data/posters/` (ver [su README](data/posters/README.md)); otros formatos, como AVIF, se convierten antes a PNG. No se versionan.
2. Por cada cartel, crea a mano su referencia en `data/references/<mismo nombre>.json` a partir de `_template.json`. Hazlo **antes** de ver la salida del modelo.
3. Comprueba la imagen sin consumir cuota:
   ```powershell
   py -3.11 research\poster_ai\extract_poster.py research\poster_ai\data\posters\01_sencillo.jpg --dry-run
   ```
4. Analiza cada cartel; es **una llamada por cartel**:
   ```powershell
   py -3.11 research\poster_ai\extract_poster.py research\poster_ai\data\posters\01_sencillo.jpg
   ```
5. Evalúa offline: `py -3.11 research\poster_ai\evaluate.py`, que escribe `data/outputs/_evaluation.json`.
6. Variante compacta (cada artista una sola vez; pensada para carteles grandes): añade `--variant compact` a los pasos 3–5. Las salidas van a `data/outputs/compact/` y el presupuesto de llamadas es común.

Pruebas offline (con un servidor local simulado): `py -3.11 -m unittest research\poster_ai\test_poster_ai.py`.

## Salvaguardas

- La clave `GROQ_API_KEY` se lee del entorno o de `research/music_sources/.env`. Nunca se imprime ni se guarda, y si llegara a aparecer en un registro, el script aborta.
- No hay reintentos automáticos. Si ya existe la salida de un cartel no se repite la llamada (`--force` lo fuerza), y hay un tope de 5 llamadas registradas en `data/outputs/_calls.jsonl` (`--budget`).
- Ante un error de autenticación (401/403) o de límite (429), el script se detiene y registra `retry-after`.
- Si la respuesta se corta (`finish_reason: length`), se marca como incompleta (código 5) y no se evalúa, aunque el JSON se pueda leer.
- Una auditoría determinista descarta las horas individuales que solo repiten la hora del bloque y los años no impresos en la fecha; los descartes quedan en `review`.
- Imágenes admitidas: JPEG, PNG o WebP de hasta 4 MB, comprobadas por su firma de bytes.
- `data/posters/` (salvo su README) y `data/outputs/` están excluidos de Git.

## Archivos

| Archivo | Función |
|---|---|
| `poster_schema.py` | Esquema, prompt y validación del JSON |
| `extract_poster.py` | Comprobación de la imagen, llamada a Groq y registro de latencia, tokens y límites |
| `evaluate.py` | Métricas frente a las referencias manuales |
| `test_poster_ai.py` | Pruebas offline |
