import logging

from devices.parsers.barcode_scanner_parser import (
    parse_barcode_scanner_input,
)

from devices.parsers.beanpro_parser import (
    parse_beanpro_export_line,
    is_known_beanpro_auxiliary_line,
)

from devices.parsers.oxygen_analyzer_parser import (
    parse_oxygen_analyzer_line,
)

from devices.parsers.colour_meter_parser import (
    parse_colour_meter_input,
)

from devices.parsers.sieve_analyzer_parser import (
    parse_sieve_analyzer_input,
)


def parse_device_input(
    raw_line: str,
) -> tuple[str, dict] | None:
    parsers = [
        (
            "Barcode Scanner",
            parse_barcode_scanner_input,
        ),
        (
            "BeanPro",
            parse_beanpro_export_line,
        ),
        (
            "Oxygen Analyzer",
            parse_oxygen_analyzer_line,
        ),
        (
            "Colour Meter",
            parse_colour_meter_input,
        ),
        (
            "Sieve Analyzer",
            parse_sieve_analyzer_input,
        ),
    ]

    for device_type, parser_function in parsers:
        try:
            reading = parser_function(
                raw_line
            )

        except Exception:
            logging.exception(
                "%s parser failed while processing: %s",
                device_type,
                raw_line,
            )

            continue

        if reading is not None:
            return (
                device_type,
                reading,
            )

    return None


def is_known_auxiliary_line(
    raw_line: str,
) -> bool:
    return is_known_beanpro_auxiliary_line(
        raw_line
    )