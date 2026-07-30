from pathlib import Path
import sys


def get_base_directory() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent.resolve()

    return Path(__file__).resolve().parents[1]


def get_bundle_directory() -> Path:
    """
    Read-only assets bundled into the exe by PyInstaller are extracted to a
    temporary directory at runtime, not placed next to the executable, so they
    resolve off sys._MEIPASS rather than BASE_DIR.
    """
    bundle_directory = getattr(
        sys,
        "_MEIPASS",
        None,
    )

    if bundle_directory is not None:
        return Path(bundle_directory).resolve()

    return get_base_directory()


BASE_DIR = get_base_directory()

BUNDLE_DIR = get_bundle_directory()

CONFIG_PATH = BASE_DIR / "config.json"

WINDOW_ICON_PATH = BUNDLE_DIR / "QA Logger.ico"

DATA_DIR = BASE_DIR / "data"
LOG_DIR = BASE_DIR / "logs"
BACKUP_DIR = BASE_DIR / "backups"


def setup_folders() -> None:
    DATA_DIR.mkdir(exist_ok=True)
    LOG_DIR.mkdir(exist_ok=True)
    BACKUP_DIR.mkdir(exist_ok=True)