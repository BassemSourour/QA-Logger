import json
import logging
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
    "serial_probe_window_seconds": 20,
    "port_baud_rates": {},
    "serial_defaults": {
        "data_bits": 8,
        "parity": "N",
        "stop_bits": 1,
    },
    "roaster_logs": [],
    "roaster_log_cache_seconds": 120,
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

    validate_serial_probe_window_seconds(
        config
    )

    validate_port_baud_rates(
        config
    )

    validate_serial_defaults(
        config
    )

    validate_roaster_logs(
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


def validate_serial_probe_window_seconds(
    config: dict,
) -> None:
    """
    How long to keep listening on one baud rate after readable text arrives
    before giving up on that baud rate.
    """
    default_value = DEFAULT_CONFIG_VALUES[
        "serial_probe_window_seconds"
    ]

    try:
        window_seconds = float(
            config.get(
                "serial_probe_window_seconds",
                default_value,
            )
        )

    except Exception:
        logging.warning(
            "Config field 'serial_probe_window_seconds' is not a number. Using %s.",
            default_value,
        )

        window_seconds = float(
            default_value
        )

    if window_seconds <= 0:
        logging.warning(
            "Config field 'serial_probe_window_seconds' must be greater than zero. Using %s.",
            default_value,
        )

        window_seconds = float(
            default_value
        )

    config[
        "serial_probe_window_seconds"
    ] = window_seconds


def validate_port_baud_rates(
    config: dict,
) -> None:
    """
    Optional map of COM port to known baud rate, for example:

        "port_baud_rates": { "COM5": 4800 }

    A port listed here skips baud-rate probing completely, which removes any
    chance of missing the first reading from that device.
    """
    port_baud_rates = config.get(
        "port_baud_rates"
    )

    if port_baud_rates in (
        None,
        "",
    ):
        config[
            "port_baud_rates"
        ] = {}

        return

    if not isinstance(
        port_baud_rates,
        dict,
    ):
        logging.warning(
            "Config field 'port_baud_rates' must be an object. Ignoring it."
        )

        config[
            "port_baud_rates"
        ] = {}

        return

    clean_port_baud_rates = {}

    for com_port, baud_rate in port_baud_rates.items():
        port_name = str(
            com_port
        ).strip().upper()

        if not port_name:
            continue

        try:
            clean_port_baud_rates[
                port_name
            ] = int(
                baud_rate
            )

        except Exception:
            logging.warning(
                "Invalid baud rate for %s in port_baud_rates: %s. Ignoring it.",
                port_name,
                baud_rate,
            )

    config[
        "port_baud_rates"
    ] = clean_port_baud_rates


def validate_roaster_logs(
    config: dict,
) -> None:
    """
    Optional list of roaster log workbooks:

        "roaster_logs": [
            { "roaster_number": 1, "excel_path": "S:\\\\..." }
        ]

    Bad or missing entries only disable the roaster log lookup. They never stop
    the application from starting, because the shared drive is not always
    reachable and QA testing has to continue without it.
    """
    roaster_logs = config.get(
        "roaster_logs"
    )

    if roaster_logs in (
        None,
        "",
    ):
        config[
            "roaster_logs"
        ] = []

        return

    if not isinstance(
        roaster_logs,
        list,
    ):
        logging.warning(
            "Config field 'roaster_logs' must be a list. "
            "Roaster log lookup is disabled."
        )

        config[
            "roaster_logs"
        ] = []

        return

    clean_roaster_logs = []

    for roaster_log in roaster_logs:
        if not isinstance(
            roaster_log,
            dict,
        ):
            logging.warning(
                "Ignoring roaster_logs entry that is not an object: %s",
                roaster_log,
            )

            continue

        excel_path = str(
            roaster_log.get(
                "excel_path",
                "",
            )
        ).strip()

        if not excel_path:
            logging.warning(
                "Ignoring roaster_logs entry with no excel_path: %s",
                roaster_log,
            )

            continue

        roaster_number = roaster_log.get(
            "roaster_number"
        )

        try:
            roaster_number = int(
                roaster_number
            )

        except Exception:
            logging.warning(
                "Roaster log %s has an invalid roaster_number: %s. "
                "The roaster number column will be left blank.",
                excel_path,
                roaster_number,
            )

            roaster_number = None

        clean_roaster_logs.append(
            {
                "roaster_number": roaster_number,
                "excel_path": excel_path,
            }
        )

    config[
        "roaster_logs"
    ] = clean_roaster_logs


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