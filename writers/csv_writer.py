import csv
from datetime import datetime

from app.paths import DATA_DIR


READINGS_CSV_PATH = DATA_DIR / "saved_readings.csv"

READING_HEADERS = [
    "saved_timestamp",
    "device_type",
    "test_type",
    "com_port",
    "full_batch_ticket",
    "batch_number",
    "machine_datetime",
    "moisture",
    "density",
    "temperature",
    "product_setting",
    "coffee_type",
    "raw_input",
]


def create_csv_if_needed() -> None:
    if READINGS_CSV_PATH.exists():
        return

    with open(
        READINGS_CSV_PATH,
        "w",
        newline="",
        encoding="utf-8",
    ) as csv_file:
        writer = csv.DictWriter(
            csv_file,
            fieldnames=READING_HEADERS,
        )

        writer.writeheader()


def save_reading_to_csv(
    reading: dict,
) -> None:
    create_csv_if_needed()

    record = {}

    for header in READING_HEADERS:
        record[header] = reading.get(
            header,
            "",
        )

    record["saved_timestamp"] = datetime.now().isoformat(
        timespec="seconds"
    )

    machine_datetime = record.get(
        "machine_datetime"
    )

    if hasattr(
        machine_datetime,
        "isoformat",
    ):
        record["machine_datetime"] = machine_datetime.isoformat(
            timespec="seconds"
        )

    with open(
        READINGS_CSV_PATH,
        "a",
        newline="",
        encoding="utf-8",
    ) as csv_file:
        writer = csv.DictWriter(
            csv_file,
            fieldnames=READING_HEADERS,
        )

        writer.writerow(
            record
        )