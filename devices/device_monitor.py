import json
import logging
import threading

from serial.tools import list_ports

from app.paths import CONFIG_PATH
from devices.serial_listener import listen_to_serial_device


def detect_usb_serial_ports() -> list[str]:
    detected_ports = []

    for port in list_ports.comports():
        searchable_text = " ".join(
            [
                port.device or "",
                port.description or "",
                port.manufacturer or "",
                port.hwid or "",
            ]
        ).lower()

        usb_indicators = [
            "usb",
            "ftdi",
            "prolific",
            "ch340",
            "cp210",
            "silicon labs",
            "usb serial",
            "usb-serial",
        ]

        if any(
            indicator in searchable_text
            for indicator in usb_indicators
        ):
            detected_ports.append(
                port.device
            )

    return sorted(
        set(detected_ports)
    )


def update_detected_ports_in_config(
    config: dict,
    detected_ports: list[str],
) -> None:
    previous_ports = config.get(
        "com_ports",
        [],
    )

    if previous_ports == detected_ports:
        return

    config["com_ports"] = detected_ports

    try:
        with open(
            CONFIG_PATH,
            "w",
            encoding="utf-8",
        ) as config_file:
            json.dump(
                config,
                config_file,
                indent=2,
            )

    except Exception:
        logging.exception(
            "Could not update detected COM ports in config."
        )


def mark_missing_ports_disconnected(
    detected_ports: list[str],
    listener_threads: dict,
    connected_ports: set,
    ports_lock: threading.Lock,
    ui_queue,
) -> None:
    detected_port_set = set(
        detected_ports
    )

    with ports_lock:
        previously_connected_ports = set(
            connected_ports
        )

    missing_ports = (
        previously_connected_ports
        - detected_port_set
    )

    for com_port in missing_ports:
        if ui_queue is not None:
            ui_queue.put(
                f"{com_port}: Device disconnected."
            )

        with ports_lock:
            connected_ports.discard(
                com_port
            )

        listener_threads.pop(
            com_port,
            None,
        )

        logging.info(
            "%s marked disconnected because it disappeared from available COM ports.",
            com_port,
        )


def monitor_serial_ports(
    config: dict,
    reading_queue,
    ui_queue,
    stop_event: threading.Event,
    listener_threads: dict,
    connected_ports: set,
    ports_lock: threading.Lock,
) -> None:
    while not stop_event.is_set():
        detected_ports = detect_usb_serial_ports()

        mark_missing_ports_disconnected(
            detected_ports=detected_ports,
            listener_threads=listener_threads,
            connected_ports=connected_ports,
            ports_lock=ports_lock,
            ui_queue=ui_queue,
        )

        update_detected_ports_in_config(
            config=config,
            detected_ports=detected_ports,
        )

        for com_port in detected_ports:
            with ports_lock:
                already_connected = (
                    com_port in connected_ports
                )

                existing_thread = listener_threads.get(
                    com_port
                )

                thread_is_alive = (
                    existing_thread is not None
                    and existing_thread.is_alive()
                )

                if already_connected or thread_is_alive:
                    continue

                connected_ports.add(
                    com_port
                )

            listener_thread = threading.Thread(
                target=listen_to_serial_device,
                args=(
                    com_port,
                    config,
                    reading_queue,
                    ui_queue,
                    stop_event,
                    connected_ports,
                    ports_lock,
                ),
                daemon=True,
            )

            listener_threads[
                com_port
            ] = listener_thread

            listener_thread.start()

        for com_port, listener_thread in list(
            listener_threads.items()
        ):
            if not listener_thread.is_alive():
                listener_threads.pop(
                    com_port,
                    None,
                )

        stop_event.wait(
            config.get(
                "reconnect_delay_seconds",
                2,
            )
        )