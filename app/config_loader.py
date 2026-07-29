import json
from pathlib import Path

from app.paths import CONFIG_PATH


REQUIRED_CONFIG_FIELDS = [
    "qa_excel_path",
]


DEFAULT_CONFIG_VALUES = {
    "com_ports": [],
    "reconnect_delay_seconds": 5,
    "serial_probe_baud_rates": [
        4800,
        9600,
        57600,
    ],
    "serial_defaults": {
        "data_bits": 8,
        "parity": "N",
        "stop_bits": 1,
    },
}


def load_config() -> dict:
    if not CONFIG_PATH.exists():
        raise FileNotFoundError(
            f"Config file was not found: {CONFIG_PATH}"
        )

    with open(
        CONFIG_PATH,
        "r",
        encoding="utf-8",
    ) as config_file:
        config = json.load(
            config_file
        )

    for field_name in REQUIRED_CONFIG_FIELDS:
        if field_name not in config:
            raise ValueError(
                f"Missing config field: {field_name}"
            )

    for field_name, default_value in DEFAULT_CONFIG_VALUES.items():
        if field_name not in config:
            config[field_name] = default_value

    validate_serial_probe_baud_rates(
        config
    )

    validate_serial_defaults(
        config
    )

    return config


def validate_serial_probe_baud_rates(
    config: dict,
) -> None:
    baud_rates = config.get(
        "serial_probe_baud_rates"
    )

    if not isinstance(
        baud_rates,
        list,
    ):
        raise ValueError(
            "Config field 'serial_probe_baud_rates' must be a list."
        )

    if len(
        baud_rates
    ) == 0:
        raise ValueError(
            "Config field 'serial_probe_baud_rates' cannot be empty."
        )

    clean_baud_rates = []

    for baud_rate in baud_rates:
        try:
            clean_baud_rates.append(
                int(
                    baud_rate
                )
            )

        except Exception as error:
            raise ValueError(
                f"Invalid baud rate in serial_probe_baud_rates: {baud_rate}"
            ) from error

    config[
        "serial_probe_baud_rates"
    ] = clean_baud_rates


def validate_serial_defaults(
    config: dict,
) -> None:
    serial_defaults = config.get(
        "serial_defaults"
    )

    if not isinstance(
        serial_defaults,
        dict,
    ):
        raise ValueError(
            "Config field 'serial_defaults' must be an object."
        )

    if "data_bits" not in serial_defaults:
        serial_defaults[
            "data_bits"
        ] = 8

    if "parity" not in serial_defaults:
        serial_defaults[
            "parity"
        ] = "N"

    if "stop_bits" not in serial_defaults:
        serial_defaults[
            "stop_bits"
        ] = 1

    try:
        serial_defaults[
            "data_bits"
        ] = int(
            serial_defaults[
                "data_bits"
            ]
        )

    except Exception as error:
        raise ValueError(
            "serial_defaults.data_bits must be a number."
        ) from error

    serial_defaults[
        "parity"
    ] = str(
        serial_defaults[
            "parity"
        ]
    ).upper()

    try:
        serial_defaults[
            "stop_bits"
        ] = float(
            serial_defaults[
                "stop_bits"
            ]
        )

    except Exception as error:
        raise ValueError(
            "serial_defaults.stop_bits must be a number."
        ) from error


def resolve_excel_path(
    excel_path_from_config: str,
) -> Path:
    excel_path = Path(
        excel_path_from_config
    )

    if excel_path.is_absolute():
        return excel_path

    return (
        CONFIG_PATH.parent
        / excel_path
    ).resolve()