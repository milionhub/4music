# Dependencias móviles: estado de `npm audit`

Revisión: 2026-10-16 · Expo SDK 57 (`expo@57.0.30`, `expo-router@57.0.28`, `react-native@0.86.3`).

`npm audit` informa **29 avisos (11 moderados, 18 altos)**. Proceden de **4 avisos raíz**; los otros 25 son paquetes que solo «dependen de una versión vulnerable» (expo, react-native, metro, reanimated, worklets…). La «solución» que propone `npm audit fix --force` baja a `expo@44`, `react-native@0.72` o sube a `expo-router@58` (SDK 58): incompatible con SDK 57 / Expo Go, así que **no se aplica**. `npm audit fix` sin `--force` no cambia nada.

**No se ha modificado ninguna dependencia ni el lockfile** en este bloque.

| Aviso raíz | Ruta | Uso afectado | Exposición | ¿Arreglo compatible? |
|---|---|---|---|---|
| `braces@3.0.3` — DoS por patrones muy anidados ([GHSA-vfj7-8cjw-p6xm](https://github.com/advisories/GHSA-vfj7-8cjw-p6xm)), alto | `expo` → `@expo/metro` → `metro-file-map` → `micromatch` → `braces` | Metro (bundler en el PC) al vigilar archivos con globs | Solo herramienta de desarrollo en el PC; los patrones vienen de la configuración del proyecto, no de entrada externa. No va en el bundle de la app. | No: 3.0.3 es la última versión publicada. |
| `node-forge@1.4.0` — verificación de firmas RSA PKCS#1 v1.5 permisiva ([GHSA-86w9-cpqp-85rv](https://github.com/advisories/GHSA-86w9-cpqp-85rv)), alto | `expo` → `@expo/cli` (y `@expo/code-signing-certificates`) → `node-forge` | Expo CLI: firma de código de actualizaciones (expo-updates) y certificados en `run:ios` | En el PC. Este proyecto no usa firma de actualizaciones ni `run:ios`. Pasará a importar si se activan EAS Update con code signing. | No: 1.4.0 es la última versión publicada. |
| `decode-uri-component@0.2.2` — DoS por decodificación exponencial ([GHSA-vcc3-ghjq-m6fr](https://github.com/advisories/GHSA-vcc3-ghjq-m6fr)), moderado | `expo-router` → `query-string@7.1.3` → `decode-uri-component` | **Runtime de la app**: Expo Router lo usa para parsear la query de rutas y enlaces profundos (`getStateFromPath`) | **Está en el bundle** que corre en el móvil. Un enlace profundo malicioso (`mobile://…?<percent-encoding malformado>`) podría bloquear la app (DoS local, sin fuga de datos). Hoy la app no procesa enlaces de terceros. | No en SDK 57: el parche (0.5.0) está fuera del rango `^0.2.2` de `query-string@7`; corregido en `expo-router@58.0.13+` (SDK 58). Un override forzaría un salto mayor sin compatibilidad verificada. |
| `uuid@7.0.3` — falta de comprobación de límites en v3/v5/v6 con `buf` ([GHSA-w5hq-g745-h8pq](https://github.com/advisories/GHSA-w5hq-g745-h8pq)), moderado | `expo-splash-screen` → `@expo/config-plugins` → `xcode@3.0.1` → `uuid` | Generación del proyecto iOS en `prebuild` (config plugins) | En el PC durante prebuild. `xcode` solo llama a `uuid.v4()` sin `buf`, que no es la función afectada. | No: `xcode@3.0.1` (última) pide `uuid@^7`; el parche está en ≥11.1.1 (mayor). |

## Seguimiento

- Al migrar a **Expo SDK 58**: repetir `npm audit`; debería resolver `decode-uri-component` (expo-router ≥58.0.13). Prioridad media porque afecta al runtime.
- Antes de **aceptar enlaces profundos externos** o publicar la app: resolver o mitigar `decode-uri-component`.
- Antes de activar **EAS Update con firma de código**: revisar si `node-forge` tiene versión corregida.
- `braces` y `uuid`: revisar en cada actualización de SDK; sin acción mientras sigan limitados a herramientas del PC.
