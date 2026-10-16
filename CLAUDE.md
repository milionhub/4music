# Instrucciones para Claude

Monorepo: `mobile/` (Expo SDK 57, ver también `mobile/AGENTS.md`), `backend/` (FastAPI, Python 3.11, venv en `backend/.venv`), `docs/`. Comandos en `README.md`.

## Forma de trabajar

- **Alcance por hitos**: haz solo lo que pide el bloque actual. No adelantes funciones de hitos futuros (fuentes musicales, IA, base de datos, auth, diseño definitivo) sin que se pidan.
- **Informes breves**: cambios, comprobaciones con su resultado real, pendientes/bloqueos. No declares superado lo que no se ha ejecutado (p. ej. pruebas visuales en dispositivo).
- **Secretos fuera del código**: nada de claves en el repo ni en `EXPO_PUBLIC_*` (se incrustan en la app). Usa `.env` locales (ignorados por Git) y deja un `.env.example` sin valores sensibles.
- **Comprobaciones proporcionales** al cambio: backend → `pytest`; mobile → `npx tsc --noEmit`; dependencias móviles → `npx expo install --check` y `npm audit` (actualizando `docs/dependencias.md`). Repite solo lo afectado.
- Git: sin commit, push ni remotos salvo petición explícita. Nunca `reset --hard` ni repos anidados.

## Dependencias

- Mobile: instalar con `npx expo install`; nunca `npm audit fix --force` ni overrides que fuercen versiones mayores sin verificar compatibilidad con el SDK y Expo Go. Conservar `package-lock.json`.
- Backend: versiones fijadas; aplicación en `requirements.txt`, desarrollo en `requirements-dev.txt`.
- No añadas librerías que el hito no necesite.
