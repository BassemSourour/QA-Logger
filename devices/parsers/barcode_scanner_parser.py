from __future__ import annotations

from typing import Any

from services.sample_barcode_service import parse_sample_barcode_payload


def parse_barcode_scanner_input(
    raw_input: str,
) -> dict[str, Any] | None:
    """
    Parses QA sample barcode scans.

    Accepted formats:
        BT000095489/BLA/54
        BT000095489-BLA-54
    """
    line = str(
        raw_input
    ).strip()

    if not line:
        return None

    # Barcode must contain either slash or hyphen separators.
    if "/" not in line and "-" not in line:
        return None

    try:
        barcode = parse_sample_barcode_payload(
            line
        )

    except ValueError:
        return None

    return {
        "device_type": "Barcode Scanner",
        "test_type": "SampleBarcode",
        "batch_ticket": barcode.batch_ticket,
        "blend_type": barcode.blend_type,
        "target_color": barcode.target_color,
        "formula_code": barcode.formula_code,
        "color_low": barcode.color_low,
        "color_high": barcode.color_high,
        "color_range_text": barcode.color_range_text,
        "barcode_payload": barcode.payload,
        "raw_input": line,
    }