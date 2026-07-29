import logging

from app.paths import LOG_DIR


def setup_logging() -> None:
    log_path = LOG_DIR / "qa_logger.log"

    logging.basicConfig(
        filename=log_path,
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
    )

    logging.info("Logging started.")