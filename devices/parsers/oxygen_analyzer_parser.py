from __future__ import annotations

from datetime import datetime
from typing import Any


def _parse_float(value: str) -> float | None:
    value = value.strip()

    if value == "":
        return None

    try:
        return float(value)
    except ValueError:
        return None


def _parse_machine_datetime(date_text: str, time_text: str) -> datetime | None:
    """
    CheckMate 3 outputs date as DD/MM/YY.

    Example:
        23/06/26;15:03:30
    means:
        June 23, 2026, 15:03:30
    """
    date_text = date_text.strip()
    time_text = time_text.strip()

    if not date_text or not time_text:
        return None

    try:
        return datetime.strptime(
            f"{date_text} {time_text}",
            "%d/%m/%y %H:%M:%S",
        )
    except ValueError:
        return None


def _extract_primary_checkmate_line(
    raw_input: str,
) -> str | None:
    """
    The CheckMate 3 sometimes sends:
    - one real result line
    - followed by one or more garbage/separator lines made only of semicolons

    This returns only the first meaningful line.
    """
    cleaned_input = raw_input.replace(
        "\x00",
        "",
    )

    lines = [
        line.strip()
        for line in cleaned_input.splitlines()
        if line.strip()
    ]

    for line in lines:
        if ";" not in line:
            continue

        if set(line) == {";"}:
            continue

        return line

    return None


def parse_oxygen_analyzer_line(
    raw_input: str,
) -> dict[str, Any] | None:
    """
    Parses Dansensor CheckMate 3 RS-232 output.

    Confirmed sample:
        021.1007;;078.8994;;;;;000004;23/06/26;15:03:30;Manual Spot O2

    Field positions:
        0: O2 %
        1: CO2 %, sometimes blank
        2: N2 %
        3-6: unused / blank fields
        7: sample number
        8: date
        9: time
        10+: product/test name
    """
    line = _extract_primary_checkmate_line(
        raw_input
    )

    if line is None:
        return None

    parts = [
        part.strip()
        for part in line.split(";")
    ]

    # Remove empty trailing fields only.
    while parts and parts[-1] == "":
        parts.pop()

    if len(parts) < 10:
        return None

    oxygen = _parse_float(
        parts[0]
    )

    carbon_dioxide = _parse_float(
        parts[1]
    ) if len(parts) > 1 else None

    nitrogen = _parse_float(
        parts[2]
    ) if len(parts) > 2 else None

    if (
        oxygen is None
        and carbon_dioxide is None
        and nitrogen is None
    ):
        return None

    sample_number = parts[7] if len(parts) > 7 else ""
    machine_date_text = parts[8] if len(parts) > 8 else ""
    machine_time_text = parts[9] if len(parts) > 9 else ""

    product_name = ""
    if len(parts) > 10:
        product_name = ";".join(
            parts[10:]
        ).strip().rstrip(";").strip()

    machine_datetime = _parse_machine_datetime(
        machine_date_text,
        machine_time_text,
    )

    return {
        "device_type": "CheckMate 3",
        "test_type": "GasAnalysis",
        "oxygen": oxygen,
        "carbon_dioxide": carbon_dioxide,
        "nitrogen": nitrogen,
        "sample_number": sample_number,
        "machine_date": machine_date_text,
        "machine_time": machine_time_text,
        "machine_datetime": machine_datetime,
        "product_name": product_name,
        "raw_input": line,
    }