# Carteles locales (no se versionan)

Coloca aquí 3–5 imágenes JPEG, PNG o WebP de hasta 4 MB, con un nombre por dificultad (la extensión puede variar):

| Archivo | Caso |
|---|---|
| `01_sencillo.jpg` | Pocos artistas |
| `02_muchos_artistas.jpg` | Muchos artistas, tipografía pequeña |
| `03_diseno_complejo.png` | Diseño gráfico complejo |
| `04_horarios_escenarios.webp` | Horarios y escenarios |
| `05_dificil.jpg` (opcional) | Texto parcialmente difícil de leer |

Por cada imagen, crea su referencia manual en `../references/<mismo nombre>.json` a partir de `../references/_template.json`.

Otros formatos (p. ej. AVIF) se convierten antes sin pérdida, por ejemplo `ffmpeg -i entrada.avif -frames:v 1 salida.png`; el script los rechaza. El original puede quedarse aquí: no se analiza.
