from pathlib import Path
import sys


def get_base_directory() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent.resolve()

    return Path(__file__).resolve().parents[1]


BASE_DIR = get_base_directory()

CONFIG_PATH = BASE_DIR / "config.json"

DATA_DIR = BASE_DIR / "data"
LOG_DIR = BASE_DIR / "logs"
BACKUP_DIR = BASE_DIR / "backups"


def setup_folders() -> None:
    DATA_DIR.mkdir(exist_ok=True)
    LOG_DIR.mkdir(exist_ok=True)
    BACKUP_DIR.mkdir(exist_ok=True)