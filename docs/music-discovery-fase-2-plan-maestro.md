# music-discovery — Plan maestro de producto y desarrollo

**Estado:** Fase 2, 28 decisiones de producto cerradas. Documento de planificación; no acredita implementación.

## 1. Propósito
Aplicación móvil de descubrimiento de música electrónica, con especial atención a la cultura club y underground. Combina tres herramientas conectadas: TrackDNA, Carteles y SetLab. Presupuesto adicional objetivo: **0 €**. Prioridad: producto útil, original, visualmente distintivo y terminado.

## 2. Base técnica y estado conocido
- Repositorio privado: `milionhub/music-discovery`.
- Directorio local: `C:\dev\music-discovery`.
- Cliente: Expo + React Native + TypeScript.
- Servidor: FastAPI + Python.
- Fase 0 de entorno cerrada anteriormente. Fase 1 de investigación documentada en `docs/fase-1-conclusiones.md`.
- Este plan **no presupone que las funciones de la Fase 2 estén programadas**.

## 3. Las 28 decisiones aprobadas
1. TrackDNA, Carteles y SetLab tienen igual peso en la visión de producto.
2. Home central y navegación inferior: Inicio, Explorar, Guardados y Perfil; herramientas accesibles desde Home.
3. Home centrado en recomendaciones personalizadas.
4. TrackDNA incluye identidad de canciones, identidad de artistas y ADN sonoro (BPM/tonalidad/energía solo si existen datos fiables).
5. Descubrimiento guiado y conexiones musicales, no búsqueda convencional como experiencia central.
6. Descubrimiento mediante tarjetas con guardar, descartar y explorar; conexiones accesibles al profundizar.
7. Tarjetas enfatizan ADN sonoro y estilo cuando los datos están disponibles; ausencia de datos bien resuelta.
8. Previews autorizadas dentro de la app si son viables, además de enlaces a plataformas externas; no reproductor completo.
9. Carteles: extraer nombres de artistas con revisión humana, recomendar según gustos y ayudar a planificar si se verifican horarios/escenarios.
10. Resultados de Carteles integran artistas, recomendaciones y organización del evento; sin porcentajes inventados.
11. SetLab: selecciones, preparación de sets y compatibilidad musical condicionada a datos reales; no mezcla en directo.
12. SetLab permite comenzar vacío, con ayuda de IA o analizando una selección existente.
13. IA de SetLab como asesora, copiloto creativo y planificadora; cambios aprobados por el usuario.
14. Personalización por gustos iniciales, interacción con la app y modos contextuales; reglas explicables antes que ML propio.
15. Identidad underground / club culture.
16. **#4MUSIC**: base oscura y cromatismo multicolor adaptable, gradientes vivos y movimiento; reducción de movimiento/paleta fija, contraste y rendimiento. No asociación rígida color-género. Reacción al audio solo si hay audio autorizado.
17. Lenguaje visual: Rave Brutalism + Fluid Immersive UI; tipografía fuerte, composiciones atrevidas y gradientes fluidos.
18. Experiencia móvil inmersiva, dinámica y audiovisual, con accesibilidad y control de movimiento.
19. Implementación secuencial: TrackDNA → revisión y aprobación → Carteles → revisión y aprobación → SetLab.
20. Primer gran objetivo: TrackDNA completo en descubrimiento, con onboarding, tarjetas, perfiles, guardados, recomendaciones evolutivas, conexiones y Home. ADN avanzado/previews/reactividad, sujetos a viabilidad, no bloquean la entrega.
21. Bienvenida visual personalizada para seleccionar estilos y artistas; sin registro obligatorio, con opción de omitir y preferencias locales.
22. Guardados incluye favoritos, colecciones personalizadas e historial de descubrimientos.
23. Conexiones visibles en las fichas y mapa musical interactivo, únicamente con relaciones respaldadas por datos.
24. Recomendaciones por afinidad y exploración, con control ajustable del nivel de sorpresa. El control no representa precisión predictiva.
25. Explicaciones breves, explicación detallada y conversación con IA sobre recomendaciones, con evidencia y restricciones de coste.
26. Mostrar información verificada e intentar completar datos mediante fuentes adicionales permitidas; no inventar valores ni conexiones.
27. Validación funcional y en dispositivo móvil real; aprobación expresa del usuario antes de avanzar.
28. Desarrollo por **hitos utilizables de extremo a extremo**; cada hito deja un recorrido comprobable.

## 4. Investigación de Fase 1: hechos y límites
- MusicBrainz: identidades/MBID como base principal, datos CC0 pertinentes; comprobar términos y atribuciones aplicables a cada integración.
- Wikidata: posible complemento.
- MusicBrainz tags/genres: no asumir uso comercial/producto por condiciones CC BY-NC-SA; no incluir sin resolver compatibilidad.
- Discogs API: excluida por licencia; dumps CC0 mensuales como hipótesis para estilos de electrónica, pendiente de revisión legal/técnica.
- ListenBrainz: similitud experimental, cobertura incierta y licencias por confirmar.
- Groq: se probó un modelo gratuito para extraer **nombres de artistas** de carteles, con confirmación humana. No asumir fiabilidad para horarios/escenarios; modelos, cuotas y disponibilidad pueden cambiar.
- AcousticBrainz: discontinuado; no hay fuente validada para BPM, tonalidad o energía a escala de producto.
- Previews de audio: todavía no existe fuente autorizada validada.
- Las fuentes externas requieren caché, límites de peticiones, gestión de errores y verificación de licencias.

## 5. Alcance de TrackDNA y criterios de honestidad
### Núcleo imprescindible
- Onboarding opcional con gustos iniciales y persistencia local.
- Home y descubrimiento con tarjetas utilizables y datos reales trazables.
- Perfiles de artistas y canciones cuando exista información fiable.
- Favoritos, colecciones e historial.
- Recomendaciones basadas en preferencias, relaciones verificadas y control de exploración; explicación de su origen.
- Relaciones en fichas y mapa interactivo construido a partir de vínculos existentes.
- Experiencia visual #4MUSIC, con controles de accesibilidad.
- Funcionamiento correcto en dispositivos móviles reales.

### Capacidades aprobadas en visión pero dependientes de investigación
- BPM, tonalidad, energía y compatibilidad sonora avanzadas.
- Previews autorizadas y efectos reactivos a audio.
- IA conversacional: validar cuotas gratuitas, latencia, seguridad, contexto y degradación cuando no esté disponible. No debe bloquear el recorrido básico.
- Enriquecimiento de datos desde otras fuentes únicamente tras verificar términos y procedencia.

**Principio:** la ausencia de una capacidad dependiente de datos se resuelve mediante estados claros y alternativas útiles, no mediante cifras inventadas o datos simulados presentados como reales.

## 6. Hoja de ruta preliminar por hitos utilizables
Los hitos son propuestas para revisar contra el estado real del repositorio antes de asignar tareas. No son fechas ni estimaciones comprometidas.

### Hito T0 — Revisión y contrato de datos
- Inspeccionar estructura existente, dependencias y pruebas actuales.
- Confirmar endpoints, modelos de datos, persistencia local, límites y licencia de cada campo usado.
- Definir cómo se registra procedencia y cómo se representan campos desconocidos.
- Entregable: recorrido de datos viable y backlog de riesgos, sin reconstruir la Fase 0.

### Hito T1 — Primer recorrido real
- Bienvenida opcional → preferencias → tarjetas de descubrimiento → ficha de artista/canción → favorito.
- Con datos de origen autorizado y estados de carga, vacío y error.
- Entregable: recorrido completo en móvil.

### Hito T2 — Descubrimiento personalizado
- Afinidad, exploración y control ajustable; guardar/descartar.
- Recomendaciones explicables con razones basadas en relaciones verificables.
- Home personalizado y evolución básica de preferencias.
- Entregable: recomendaciones coherentes, no porcentajes ficticios.

### Hito T3 — Biblioteca y relaciones
- Favoritos, colecciones, historial y persistencia.
- Relaciones en perfiles y mapa interactivo con navegación móvil accesible.
- Entregable: descubrir, conectar y recuperar música.

### Hito T4 — Identidad visual y funciones avanzadas viables
- Refinamiento #4MUSIC, animaciones, rendimiento y reducción de movimiento.
- Explicaciones profundas y conversación con IA, solo tras validar disponibilidad y límites; fallback sin IA.
- Previews/ADN sonoro avanzado solo si se confirma fuente legítima y fiable.
- Entregable: experiencia diferenciada sin dependencias falsas.

### Hito T5 — Validación y aprobación
- Comprobaciones técnicas críticas y pruebas manuales en móvil real.
- Revisión de utilidad, estabilidad, legibilidad, latencia y manejo de fallos.
- Resolver defectos bloqueantes; documentar limitaciones no bloqueantes.
- **Puerta de salida:** aprobación explícita del usuario para empezar Carteles.

## 7. Forma de trabajar con Claude Code
1. ChatGPT mantiene decisiones de producto, prioridades y criterios de aceptación.
2. Claude inspecciona el repositorio antes de modificar; no supone funcionalidades ya terminadas.
3. Una instrucción amplia por hito, suficientemente delimitada; implementación end-to-end y pruebas críticas, evitando auditorías repetitivas.
4. Claude informa archivos cambiados, decisiones técnicas, pruebas realizadas y pendientes reales.
5. Usuario prueba en dispositivo y decide si aprobar, corregir o repetir el hito.
6. No avanzar de módulo sin aprobación explícita.

## 8. Próximo paso
Antes de pedir código a Claude, contrastar este plan con `docs/fase-1-conclusiones.md` y el estado real de Git. Preparar un prompt único para **T0 — Revisión y contrato de datos**. No iniciar Carteles ni SetLab. No instalar servicios de pago ni integrar fuentes de licencia no validada.
