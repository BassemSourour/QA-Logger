import re
from datetime import datetime


MONTH_LOOKUP = {
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "may": 5,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
}


def identify_coffee_type(
    product_setting: str,
) -> str:
    clean_setting = product_setting.strip().lower()

    if "decaf" in clean_setting:
        return "Decaf"

    if "green" in clean_setting:
        return "Green Bean"

    if "roast" in clean_setting:
        return "Roast Bean"

    return "Unknown"


def parse_beanpro_export_line(
    raw_line: str,
) -> dict | None:
    clean_line = raw_line.strip()

    if not clean_line.startswith(">"):
        return None

    pattern = re.compile(
        r"^>\s+"
        r"(?P<year>\d{4})\s+"
        r"(?P<month>[A-Za-z]{3})\s+"
        r"(?P<day>\d{1,2})\s+"
        r"(?P<hour>\d{1,2}):"
        r"(?P<minute>\d{2}):"
        r"(?P<second>\d{2})\s+"
        r"(?P<batch_number>\d+)\s+"
        r"(?P<channel>\d+)\s+"
        r"(?P<moisture>\d+(?:\.\d+)?)\s+"
        r"(?P<ignored_value>\d+(?:\.\d+)?)\s+"
        r"(?P<temperature>\d+(?:\.\d+)?)\s+"
        r"(?P<density>\d+)\s+"
        r"(?P<product_setting>.+)$"
    )

    match = pattern.match(
        clean_line
    )

    if match is None:
        return None

    values = match.groupdict()

    month_text = values["month"].lower()

    if month_text not in MONTH_LOOKUP:
        return None

    test_datetime = datetime(
        year=int(values["year"]),
        month=MONTH_LOOKUP[month_text],
        day=int(values["day"]),
        hour=int(values["hour"]),
        minute=int(values["minute"]),
        second=int(values["second"]),
    )

    product_setting = values[
        "product_setting"
    ].strip()

    return {
        "device_type": "BeanPro",
        "test_type": "MoistureDensity",
        "machine_datetime": test_datetime,
        "batch_number": int(values["batch_number"]),
        "channel": int(values["channel"]),
        "moisture": float(values["moisture"]),
        "temperature": float(values["temperature"]),
        "density": int(values["density"]),
        "product_setting": product_setting,
        "coffee_type": identify_coffee_type(
            product_setting
        ),
        "raw_input": raw_line,
    }


def is_known_beanpro_auxiliary_line(
    raw_line: str,
) -> bool:
    clean_line = raw_line.strip().lower()

    known_prefixes = [
        "channel",
        "batch no.",
        "batch no:",
        "temp.",
        "moisture",
    ]

    if any(
        clean_line.startswith(prefix)
        for prefix in known_prefixes
    ):
        return True

    known_product_names = [
        "roast bean",
        "roast coffee bns",
        "green bean",
        "decaf",
    ]

    if clean_line in known_product_names:
        return True

    if re.fullmatch(
        r"\d*coff\d+",
        clean_line,
    ):
        return True

    if re.fullmatch(
        r"\d{4}\s+[a-z]{3}\s+\d{1,2}\s+"
        r"\d{1,2}:\d{2}:\d{2}",
        clean_line,
    ):
        return True

    return False