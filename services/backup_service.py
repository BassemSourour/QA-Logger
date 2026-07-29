import logging
import shutil
from datetime import datetime
from pathlib import Path

from app.paths import BACKUP_DIR


def create_workbook_backup(
    excel_path: Path,
) -> None:
    try:
        timestamp = datetime.now().strftime(
            "%Y%m%d_%H%M%S"
        )

        backup_path = (
            BACKUP_DIR
            / f"{excel_path.stem}_{timestamp}{excel_path.suffix}"
        )

        shutil.copy2(
            excel_path,
            backup_path,
        )

        logging.info(
            "Workbook backup created: %s",
            backup_path,
        )

    except Exception:
        logging.exception(
            "Could not create workbook backup."
        )