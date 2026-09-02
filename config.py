"""Application configuration.

All settings are read from environment variables (see .env.example) so that no
secret ever lives in the source tree. Select a config class with FLASK_ENV.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


def env(name, default=None):
    """Read an environment variable, treating a blank value as "not set".

    .env.example ships with empty placeholders (DATABASE_URL=, AI_API_KEY=),
    and os.getenv would hand those back as "" rather than the default - which
    would, for example, leave SQLAlchemy with an unparsable database URL.
    """
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    return value.strip()


def env_int(name, default):
    try:
        return int(env(name, default))
    except (TypeError, ValueError):
        return int(default)


def env_float(name, default):
    try:
        return float(env(name, default))
    except (TypeError, ValueError):
        return float(default)


def _as_bool(value, default=False):
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


class Config:
    """Settings shared by every environment."""

    SECRET_KEY = env("SECRET_KEY", "dev-secret-change-me")

    # SQLite for development. Point DATABASE_URL at PostgreSQL in production,
    # e.g. postgresql+psycopg://user:password@host:5432/travel
    SQLALCHEMY_DATABASE_URI = env(
        "DATABASE_URL", f"sqlite:///{BASE_DIR / 'instance' / 'travel.db'}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}

    # Session cookie hardening
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = _as_bool(env("SESSION_COOKIE_SECURE"), False)
    PERMANENT_SESSION_LIFETIME = 60 * 60 * 24 * 14  # 14 days

    # --- AI ---------------------------------------------------------------
    # AI_PROVIDER selects the implementation in app/services/ai_provider.py.
    # "gemini"  -> Google Gemini (free tier available; requires AI_API_KEY)
    # "claude"  -> Anthropic Claude API (requires AI_API_KEY)
    # "mock"    -> offline demo generator, no API key needed
    # "auto"    -> detected from the key prefix, or mock when no key is set
    AI_PROVIDER = env("AI_PROVIDER", "auto")
    AI_API_KEY = env("AI_API_KEY")
    # Leave empty to use each provider's default model
    # (gemini-2.5-flash / claude-opus-5).
    AI_MODEL = env("AI_MODEL")
    AI_TEMPERATURE = env_float("AI_TEMPERATURE", 0.8)  # Gemini
    # Claude only - thinking depth: low | medium | high | xhigh | max
    AI_EFFORT = env("AI_EFFORT", "medium")
    AI_MAX_TOKENS = env_int("AI_MAX_TOKENS", 32000)
    AI_TIMEOUT_SECONDS = env_float("AI_TIMEOUT_SECONDS", 240)

    # --- Weather ----------------------------------------------------------
    # Leave WEATHER_API_KEY empty to use the key-less Open-Meteo service.
    WEATHER_API_KEY = env("WEATHER_API_KEY")
    WEATHER_TIMEOUT_SECONDS = env_float("WEATHER_TIMEOUT_SECONDS", 8)

    # --- Limits -----------------------------------------------------------
    MAX_TRIP_DAYS = env_int("MAX_TRIP_DAYS", 21)
    MAX_TRAVELERS = env_int("MAX_TRAVELERS", 30)


class DevelopmentConfig(Config):
    DEBUG = True


class ProductionConfig(Config):
    DEBUG = False
    SESSION_COOKIE_SECURE = _as_bool(env("SESSION_COOKIE_SECURE"), True)


class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    AI_PROVIDER = "mock"
    WTF_CSRF_ENABLED = False


CONFIG_MAP = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
}


def get_config(name=None):
    """Return the config class for `name` (defaults to $FLASK_ENV)."""
    name = (name or env("FLASK_ENV") or "development").lower()
    return CONFIG_MAP.get(name, DevelopmentConfig)
