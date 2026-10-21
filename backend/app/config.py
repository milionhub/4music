"""Configuración del backend leída del entorno (y de backend/.env si existe, que no se versiona)."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BACKEND_DIR / ".env")


def listenbrainz_token() -> str:
    """Token de usuario de ListenBrainz (opcional, gratuito). Sin él no se consulta la popularidad."""
    return os.environ.get("LISTENBRAINZ_TOKEN", "").strip()


def groq_api_key() -> str:
    """Clave de Groq (solo backend; nunca se registra ni se devuelve)."""
    return os.environ.get("GROQ_API_KEY", "").strip()


def groq_model() -> str:
    return os.environ.get("GROQ_MODEL", "").strip() or "openai/gpt-oss-20b"


def cover_art_enabled() -> bool:
    """Portadas de Cover Art Archive (activadas por defecto; COVER_ART=off las desactiva). Ver docs/t1-plan."""
    return os.environ.get("COVER_ART", "on").strip().lower() not in ("off", "0", "false", "no")


def musicbrainz_contact() -> str:
    """Email o URL de contacto que MusicBrainz exige en el User-Agent. Cadena vacía si no está configurado."""
    return os.environ.get("MUSICBRAINZ_CONTACT", "").strip()
