from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class SampleBarcode:
    batch_ticket: str
    blend_type: str
    target_color: int

    @property
    def formula_code(self) -> str:
        return f"{self.blend_type}{self.target_color}"

    @property
    def color_low(self) -> int:
        return self.target_color - 2

    @property
    def color_high(self) -> int:
        return self.target_color + 2

    @property
    def color_range_text(self) -> str:
        return f"{self.color_low}-{self.color_high}"

    @property
    def payload(self) -> str:
        return build_sample_barcode_payload(
            batch_ticket=self.batch_ticket,
            blend_type=self.blend_type,
            target_color=self.target_color,
        )


def normalize_batch_ticket(
    batch_ticket: str,
) -> str:
    value = str(
        batch_ticket
    ).strip().upper()

    if not value:
        raise ValueError(
            "Batch ticket cannot be blank."
        )

    return value


def normalize_blend_type(
    blend_type: str,
) -> str:
    value = str(
        blend_type
    ).strip().upper()

    if not value:
        raise ValueError(
            "Blend type cannot be blank."
        )

    return value


def normalize_target_color(
    target_color,
) -> int:
    try:
        value = int(
            str(
                target_color
            ).strip()
        )

    except Exception as error:
        raise ValueError(
            "Target color must be a whole number."
        ) from error

    if value <= 0:
        raise ValueError(
            "Target color must be greater than zero."
        )

    return value


def build_sample_barcode_payload(
    batch_ticket: str,
    blend_type: str,
    target_color,
) -> str:
    normalized_batch_ticket = normalize_batch_ticket(
        batch_ticket
    )

    normalized_blend_type = normalize_blend_type(
        blend_type
    )

    normalized_target_color = normalize_target_color(
        target_color
    )

    return (
        f"{normalized_batch_ticket}/"
        f"{normalized_blend_type}/"
        f"{normalized_target_color}"
    )


def parse_sample_barcode_payload(
    payload: str,
) -> SampleBarcode:
    value = str(
        payload
    ).strip().upper()

    # Accept both:
    #   BT000095489/BLA/54
    #   BT000095489-BLA-54
    match = re.fullmatch(
        r"([A-Z]{0,3}\d+)[/-]([A-Z]+)[/-](\d+)",
        value,
    )

    if match is None:
        raise ValueError(
            "Barcode must be in the format BT#/BLEND/COLOR or BT#-BLEND-COLOR."
        )

    batch_ticket = normalize_batch_ticket(
        match.group(1)
    )

    blend_type = normalize_blend_type(
        match.group(2)
    )

    target_color = normalize_target_color(
        match.group(3)
    )

    return SampleBarcode(
        batch_ticket=batch_ticket,
        blend_type=blend_type,
        target_color=target_color,
    )