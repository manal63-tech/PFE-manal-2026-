"""Application configuration."""
import os
from pathlib import Path

# Project root (the directory that contains this package).
BASE_DIR = Path(__file__).resolve().parent.parent


class Config:
    """Base configuration, overridable via environment variables."""

    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-me")

    # Database. Defaults to a SQLite file at the project root.
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL",
        f"sqlite:///{(BASE_DIR / 'hydromon.db').as_posix()}",
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Directory holding the trained ML artifacts (*.pkl).
    MODEL_DIR = Path(os.environ.get("MODEL_DIR", BASE_DIR / "models"))

    # Maximum number of recent readings returned by /api/history.
    MAX_HISTORY = int(os.environ.get("MAX_HISTORY", "100"))

    # Scheduled export settings.
    EXPORT_DIR = Path(os.environ.get("EXPORT_DIR", BASE_DIR / "exports"))
    EXPORT_INTERVAL_MINUTES = int(os.environ.get("EXPORT_INTERVAL_MINUTES", "5"))
    ENABLE_EXPORT_SCHEDULER = os.environ.get("ENABLE_EXPORT_SCHEDULER", "true").lower() in ("1", "true", "yes")
    EXPORT_PASSWORD = os.environ.get("EXPORT_PASSWORD", "manalpfe2026")
