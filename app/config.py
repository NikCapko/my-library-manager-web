"""Конфигурация из переменных окружения с дефолтами."""
import os
import sys
from pathlib import Path


def _default_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


BASE_DIR = Path(os.environ.get("LIBRARY_BASE", _default_base_dir()))
DB_FILE = os.environ.get("LIBRARY_DB", str(BASE_DIR / "library.db"))
LIBRARY_PATH = os.environ.get("LIBRARY_PATH", str(BASE_DIR / "library"))
SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-me")
