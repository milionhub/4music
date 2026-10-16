# Fase 1.5: artistas similares de ListenBrainz Labs

Investigación aislada (no la usan `mobile/` ni `backend/`). Informe: [`docs/fase-1-listenbrainz.md`](../../../docs/fase-1-listenbrainz.md). Solo usa la biblioteca estándar de Python 3.11 y reutiliza `../http_client.py`.

```powershell
py -3.11 research\music_sources\listenbrainz\run_phase15.py identify   # MusicBrainz: candidatos + enlaces externos
py -3.11 research\music_sources\listenbrainz\run_phase15.py verify     # MusicBrainz: ficha de los MBID fijados
py -3.11 research\music_sources\listenbrainz\run_phase15.py similar    # ListenBrainz Labs: 1 consulta por artista
py -3.11 research\music_sources\listenbrainz\run_phase15.py radio --ids L1   # 1.5B: LB Radio sin token (responde 401)
```

- Necesita `MUSIC_RESEARCH_CONTACT` en `research/music_sources/.env` (User-Agent que exige MusicBrainz); no se registra.
- **Sin reintentos automáticos.** Las respuestas se cachean, así que repetir no hace peticiones nuevas. El presupuesto es acumulado entre ejecuciones: MusicBrainz 14, Labs 4 (agotado) y LB Radio 4 (usado 1). LB Radio exige token de usuario; no se usa ninguno.
- El MBID de cada artista lo fija una persona en `artists.json` tras revisar `identify`; el script no elige solo.

| Archivo | Contenido |
|---|---|
| `artists.json` | Artistas de prueba, MBID elegido y evidencia de identidad |
| `run_phase15.py` | Etapas `identify`, `verify`, `similar` y `radio` (1.5B) |
| `data/results/` | Resultados interpretados (versionados) |
| `data/raw/`, `data/logs/` | Respuestas originales y registro de peticiones (solo local) |
