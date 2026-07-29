import logging
import threading
import time

import serial
from serial import SerialException
from serial.tools import list_ports

from devices.parsers.parser_router import (
    parse_device_input,
    is_known_auxiliary_line,
)


def send_ui_message(
    ui_queue,
    message: str,
) -> None:
    if ui_queue is not None:
        ui_queue.put(
            message
        )

    else:
        print(
            message
        )


def clean_serial_display_line(
    raw_line: str,
) -> str | None:
    """
    Cleans raw serial input before displaying/parsing it.

    Some devices, especially the CheckMate 3, may send a useful result line
    followed by extra semicolon padding.

    Example:
        021.1540;;078.8460;;;;;000004;25/06/26;10:34:06;Manual Spot O2;;;;;;;;;;;;;;;;;;;;;

    This keeps only:
        021.1540;;078.8460;;;;;000004;25/06/26;10:34:06;Manual Spot O2
    """
    if raw_line is None:
        return None

    cleaned_input = raw_line.replace(
        "\x00",
        "",
    )

    lines = [
        line.strip()
        for line in cleaned_input.splitlines()
        if line.strip()
    ]

    for line in lines:
        if not line:
            continue

        # Ignore separator / garbage lines made only of semicolons.
        if set(line) == {";"}:
            continue

        # CheckMate 3 lines are semicolon-delimited.
        # Keep only the first 11 fields:
        # O2, CO2, N2, blanks, sample, date, time, product name.
        if ";" in line:
            parts = [
                part.strip()
                for part in line.split(";")
            ]

            if len(parts) >= 11:
                meaningful_parts = parts[:11]

                return ";".join(
                    meaningful_parts
                ).rstrip(";").strip()

        return line

    return None


def get_bytesize(
    data_bits: int,
):
    if data_bits == 5:
        return serial.FIVEBITS

    if data_bits == 6:
        return serial.SIXBITS

    if data_bits == 7:
        return serial.SEVENBITS

    return serial.EIGHTBITS


def get_parity(
    parity: str,
):
    parity = str(
        parity
    ).upper()

    if parity == "E":
        return serial.PARITY_EVEN

    if parity == "O":
        return serial.PARITY_ODD

    if parity == "M":
        return serial.PARITY_MARK

    if parity == "S":
        return serial.PARITY_SPACE

    return serial.PARITY_NONE


def get_stopbits(
    stop_bits,
):
    try:
        stop_bits = float(
            stop_bits
        )
    except Exception:
        stop_bits = 1

    if stop_bits == 1.5:
        return serial.STOPBITS_ONE_POINT_FIVE

    if stop_bits == 2:
        return serial.STOPBITS_TWO

    return serial.STOPBITS_ONE


def get_probe_baud_rates(
    config: dict,
) -> list[int]:
    baud_rates = config.get(
        "serial_probe_baud_rates",
        [
            4800,
            9600,
            57600,
        ],
    )

    clean_baud_rates = []

    for baud_rate in baud_rates:
        try:
            clean_baud_rates.append(
                int(
                    baud_rate
                )
            )

        except Exception:
            continue

    if not clean_baud_rates:
        clean_baud_rates = [
            4800,
            9600,
            57600,
        ]

    return clean_baud_rates


def get_serial_defaults(
    config: dict,
) -> dict:
    return config.get(
        "serial_defaults",
        {
            "data_bits": 8,
            "parity": "N",
            "stop_bits": 1,
        },
    )


def is_port_still_connected(
    com_port: str,
) -> bool:
    current_ports = {
        port.device
        for port in list_ports.comports()
    }

    return com_port in current_ports


def open_serial_device(
    com_port: str,
    baud_rate: int,
    serial_defaults: dict,
):
    data_bits = int(
        serial_defaults.get(
            "data_bits",
            8,
        )
    )

    parity = serial_defaults.get(
        "parity",
        "N",
    )

    stop_bits = serial_defaults.get(
        "stop_bits",
        1,
    )

    return serial.Serial(
        port=com_port,
        baudrate=baud_rate,
        bytesize=get_bytesize(
            data_bits
        ),
        parity=get_parity(
            parity
        ),
        stopbits=get_stopbits(
            stop_bits
        ),
        timeout=1,
        xonxoff=False,
        rtscts=False,
        dsrdtr=False,
    )


def decode_serial_bytes(
    serial_bytes: bytes,
) -> str | None:
    if not serial_bytes:
        return None

    raw_line = serial_bytes.decode(
        "ascii",
        errors="replace",
    ).strip()

    if not raw_line:
        return None

    return clean_serial_display_line(
        raw_line
    )


def process_display_line(
    com_port: str,
    baud_rate: int,
    display_line: str,
    reading_queue,
    ui_queue,
) -> bool:
    """
    Returns True if the line was recognized and queued.
    Returns False if it was not recognized.
    """
    send_ui_message(
        ui_queue,
        f"{com_port}: Received: {display_line}",
    )

    parsed_result = parse_device_input(
        display_line
    )

    if parsed_result is not None:
        device_type, reading = parsed_result

        reading[
            "com_port"
        ] = com_port

        reading[
            "baud_rate"
        ] = baud_rate

        reading_queue.put(
            reading
        )

        logging.info(
            "%s input recognized on %s at %s baud",
            device_type,
            com_port,
            baud_rate,
        )

        return True

    if is_known_auxiliary_line(
        display_line
    ):
        return False

    send_ui_message(
        ui_queue,
        f"{com_port}: Input received, but the format is not recognized.",
    )

    return False


def find_working_baud_rate(
    com_port: str,
    config: dict,
    reading_queue,
    ui_queue,
    stop_event: threading.Event,
) -> int | None:
    """
    Cycles through known baud rates silently until a parser recognizes input.

    Important:
    - A COM port cannot be opened at multiple baud rates at the exact same time.
    - This function rotates through the configured baud rates.
    - When it sees a recognizable line, it processes that line immediately
      and returns the working baud rate.
    """
    baud_rates = get_probe_baud_rates(
        config
    )

    serial_defaults = get_serial_defaults(
        config
    )

    while not stop_event.is_set():
        if not is_port_still_connected(
            com_port
        ):
            return None

        for baud_rate in baud_rates:
            if stop_event.is_set():
                return None

            if not is_port_still_connected(
                com_port
            ):
                return None

            try:
                with open_serial_device(
                    com_port=com_port,
                    baud_rate=baud_rate,
                    serial_defaults=serial_defaults,
                ) as device:
                    logging.info(
                        "Listening on %s at %s baud",
                        com_port,
                        baud_rate,
                    )

                    start_time = time.time()

                    while (
                        time.time() - start_time
                    ) < 3:
                        if stop_event.is_set():
                            return None

                        if not is_port_still_connected(
                            com_port
                        ):
                            return None

                        try:
                            serial_bytes = device.readline()

                        except SerialException:
                            return None

                        except OSError:
                            return None

                        display_line = decode_serial_bytes(
                            serial_bytes
                        )

                        if display_line is None:
                            continue

                        parsed_result = parse_device_input(
                            display_line
                        )

                        if parsed_result is not None:
                            device_type, reading = parsed_result

                            send_ui_message(
                                ui_queue,
                                f"{com_port}: Received: {display_line}",
                            )

                            reading[
                                "com_port"
                            ] = com_port

                            reading[
                                "baud_rate"
                            ] = baud_rate

                            reading_queue.put(
                                reading
                            )

                            logging.info(
                                "%s input recognized on %s at %s baud",
                                device_type,
                                com_port,
                                baud_rate,
                            )

                            return baud_rate

                        if is_known_auxiliary_line(
                            display_line
                        ):
                            logging.info(
                                "Auxiliary input recognized on %s at %s baud",
                                com_port,
                                baud_rate,
                            )

                            return baud_rate

            except SerialException:
                continue

            except OSError:
                continue

            except Exception:
                logging.exception(
                    "Baud-rate probe failed on %s at %s baud",
                    com_port,
                    baud_rate,
                )

                continue

    return None


def listen_with_baud_rate(
    com_port: str,
    baud_rate: int,
    config: dict,
    reading_queue,
    ui_queue,
    stop_event: threading.Event,
) -> None:
    serial_defaults = get_serial_defaults(
        config
    )

    with open_serial_device(
        com_port=com_port,
        baud_rate=baud_rate,
        serial_defaults=serial_defaults,
    ) as device:
        logging.info(
            "Locked %s at %s baud",
            com_port,
            baud_rate,
        )

        while not stop_event.is_set():
            if not is_port_still_connected(
                com_port
            ):
                send_ui_message(
                    ui_queue,
                    f"{com_port}: Device disconnected.",
                )

                logging.info(
                    "%s disconnected",
                    com_port,
                )

                break

            try:
                serial_bytes = device.readline()

            except SerialException:
                send_ui_message(
                    ui_queue,
                    f"{com_port}: Device disconnected.",
                )

                logging.exception(
                    "Serial connection lost on %s",
                    com_port,
                )

                break

            except OSError:
                send_ui_message(
                    ui_queue,
                    f"{com_port}: Device disconnected.",
                )

                logging.exception(
                    "Operating system disconnected %s",
                    com_port,
                )

                break

            display_line = decode_serial_bytes(
                serial_bytes
            )

            if display_line is None:
                continue

            process_display_line(
                com_port=com_port,
                baud_rate=baud_rate,
                display_line=display_line,
                reading_queue=reading_queue,
                ui_queue=ui_queue,
            )


def listen_to_serial_device(
    com_port: str,
    config: dict,
    reading_queue,
    ui_queue,
    stop_event: threading.Event,
    connected_ports: set,
    ports_lock: threading.Lock,
) -> None:
    try:
        send_ui_message(
            ui_queue,
            f"{com_port}: Connected and waiting for readings.",
        )

        working_baud_rate = find_working_baud_rate(
            com_port=com_port,
            config=config,
            reading_queue=reading_queue,
            ui_queue=ui_queue,
            stop_event=stop_event,
        )

        if working_baud_rate is None:
            send_ui_message(
                ui_queue,
                f"{com_port}: Device disconnected.",
            )

            return

        listen_with_baud_rate(
            com_port=com_port,
            baud_rate=working_baud_rate,
            config=config,
            reading_queue=reading_queue,
            ui_queue=ui_queue,
            stop_event=stop_event,
        )

    except SerialException:
        send_ui_message(
            ui_queue,
            f"{com_port}: Device disconnected.",
        )

        logging.exception(
            "Could not connect to or maintain connection with %s",
            com_port,
        )

    except OSError:
        send_ui_message(
            ui_queue,
            f"{com_port}: Device disconnected.",
        )

        logging.exception(
            "Operating system removed or blocked %s",
            com_port,
        )

    except Exception:
        logging.exception(
            "Listener error on %s",
            com_port,
        )

    finally:
        with ports_lock:
            connected_ports.discard(
                com_port
            )