"""Filesystem locations that work both from source and from a frozen (PyInstaller) build."""
from pathlib import Path

from platformdirs import user_data_dir

APP_NAME = "CaesarCourseCheck"


def data_dir() -> Path:
    # Per-user, writable. Never next to __file__: frozen bundles are read-only / temporary.
    d = Path(user_data_dir(APP_NAME, appauthor=False))
    d.mkdir(parents=True, exist_ok=True)
    return d


def profile_dir() -> Path:
    return data_dir() / "chrome-profile"


def storage_state_path() -> Path:
    return data_dir() / "storage_state.json"


def config_path() -> Path:
    return data_dir() / "config.json"


def static_dir() -> Path:
    # Works from source and when frozen: PyInstaller places data at <bundle>/caesar_checker/static.
    return Path(__file__).parent / "static"


def catalog_path() -> Path:
    # Bundled by PyInstaller next to this module; regenerate with scraper/build_catalog.py.
    return Path(__file__).parent / "catalog.json"
