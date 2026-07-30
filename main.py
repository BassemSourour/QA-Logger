import logging
import queue
import threading
from datetime import datetime

from app.app_state import AppState
from app.config_loader import load_config, resolve_excel_path
from app.logging_setup import setup_logging
from app.paths import LOG_DIR, setup_folders

from devices.device_monitor import monitor_serial_ports

from services.mode_validation_service import (
    build_wrong_machine_mode_message,
    is_machine_test_allowed_for_mode,
)
from services.roaster_log_lookup_service import RoasterLogCache

from ui.desktop_window import QALoggerWindow

from writers.csv_writer import (
    create_csv_if_needed,
    save_reading_to_csv,
)
from writers.excel_connection import (
    close_excel_connection,
    connect_to_excel,
)
from writers.qa_excel_writer import (
    DuplicateBatchTicketError,
    write_reading_to_excel,
)


def send_ui_message(
    ui_queue: queue.Queue,
    message: str,
) -> None:
    ui_queue.put(message)


def format_gas_value(
    value,
) -> str:
    if value is None:
        return "N/A"

    try:
        return f"{float(value):.4f}%"
    except Exception:
        return str(value)


def handle_gas_analysis_reading(
    reading: dict,
    ui_queue: queue.Queue,
    app_state: AppState,
) -> None:
    save_reading_to_csv(reading)

    current_mode = app_state.get_mode()
    com_port = reading.get("com_port", "Device")

    oxygen = format_gas_value(reading.get("oxygen"))
    carbon_dioxide = format_gas_value(reading.get("carbon_dioxide"))
    nitrogen = format_gas_value(reading.get("nitrogen"))

    sample_number = reading.get("sample_number", "")
    product_name = reading.get("product_name", "")
    machine_date = reading.get("machine_date", "")
    machine_time = reading.get("machine_time", "")

    if current_mode == "packaging":
        mode_note = "Packaging mode selected. O2 packaging Excel writing is not built yet."
    elif current_mode == "roasting":
        mode_note = "Roasting mode selected. Gas result saved to CSV only."
    else:
        mode_note = "No mode selected. Gas result saved to CSV only."

    send_ui_message(
        ui_queue,
        f"{com_port}: CheckMate 3 result received | "
        f"O2 {oxygen} | "
        f"CO2 {carbon_dioxide} | "
        f"N2 {nitrogen} | "
        f"Sample {sample_number} | "
        f"{machine_date} {machine_time} | "
        f"{product_name} | "
        f"{mode_note}",
    )

    logging.info(
        "Saved CheckMate 3 gas analysis result to CSV only | "
        "sample=%s | O2=%s | CO2=%s | N2=%s | product=%s | mode=%s",
        sample_number,
        reading.get("oxygen"),
        reading.get("carbon_dioxide"),
        reading.get("nitrogen"),
        product_name,
        current_mode,
    )


def build_active_sample_from_barcode_reading(
    reading: dict,
) -> dict:
    return {
        "batch_ticket": reading["batch_ticket"],
        "excel_batch_ticket": reading.get(
            "excel_batch_ticket",
            reading["batch_ticket"],
        ),
        "formula_code": reading["formula_code"],
        "color_range_text": reading["color_range_text"],
        "sheet_name": reading["qa_sheet_name"],
        "row_number": reading["qa_row_number"],
    }


def describe_roaster_log_data(
    roaster_log_data,
) -> str:
    if not roaster_log_data:
        return "not found"

    return (
        f"roaster {roaster_log_data.get('roaster_number')} | "
        f"lbs {roaster_log_data.get('quantity_roasted')} | "
        f"temp {roaster_log_data.get('end_temperature')} | "
        f"sheet {roaster_log_data.get('source_sheet')} | "
        f"rows {len(roaster_log_data.get('source_rows', []))}"
    )


def get_roaster_log_data_for_reading(
    reading: dict,
    roaster_log_cache,
):
    """
    Looks up roaster production data before the Excel write.

    A lookup failure must never stop a sample from being recorded, so every
    error here is logged and treated as "not found".
    """
    if roaster_log_cache is None:
        return None

    try:
        return roaster_log_cache.get_roaster_log_data(
            reading["batch_ticket"]
        )

    except Exception:
        logging.exception(
            "Roaster log lookup failed for batch %s",
            reading.get(
                "batch_ticket"
            ),
        )

        return None


def handle_sample_barcode_reading(
    reading: dict,
    ui_queue: queue.Queue,
    excel_session: dict,
    excel_path,
    roaster_log_cache=None,
) -> dict:
    roaster_log_data = get_roaster_log_data_for_reading(
        reading=reading,
        roaster_log_cache=roaster_log_cache,
    )

    reading[
        "roaster_log_data"
    ] = roaster_log_data

    sheet_name, row_number = write_reading_to_excel(
        reading=reading,
        excel_session=excel_session,
        excel_path=excel_path,
    )

    save_reading_to_csv(reading)

    active_roasting_sample = build_active_sample_from_barcode_reading(
        reading
    )

    sample_action = reading.get(
        "sample_action",
        "selected",
    )

    if sample_action == "created":
        action_text = "New roasting sample created"
    else:
        action_text = "Roasting sample selected"

    display_batch_ticket = reading.get(
        "excel_batch_ticket",
        reading["batch_ticket"],
    )

    send_ui_message(
        ui_queue,
        f"{reading.get('com_port', 'Device')}: "
        f"{action_text} | "
        f"{display_batch_ticket} | "
        f"{reading['formula_code']} | "
        f"Color range {reading['color_range_text']} | "
        f"Row {row_number}",
    )

    logging.info(
        "%s | batch=%s | sheet=%s | row=%s | roaster_log=%s",
        action_text,
        display_batch_ticket,
        sheet_name,
        row_number,
        describe_roaster_log_data(
            roaster_log_data
        ),
    )

    return active_roasting_sample

def handle_moisture_density_reading(
    reading: dict,
    ui_queue: queue.Queue,
    excel_session: dict,
    excel_path,
    active_roasting_sample: dict | None,
) -> None:
    if active_roasting_sample is None:
        save_reading_to_csv(reading)

        send_ui_message(
            ui_queue,
            f"{reading.get('com_port', 'Device')}: NOT SAVED: "
            "No active roasting sample selected. Scan the roasting barcode first.",
        )

        logging.warning(
            "Moisture/density received with no active roasting sample selected. raw=%s",
            reading.get("raw_input", ""),
        )

        return

    reading["active_sample"] = active_roasting_sample

    sheet_name, row_number = write_reading_to_excel(
        reading=reading,
        excel_session=excel_session,
        excel_path=excel_path,
    )

    save_reading_to_csv(reading)

    display_batch_ticket = active_roasting_sample.get(
        "excel_batch_ticket",
        active_roasting_sample["batch_ticket"],
    )

    send_ui_message(
        ui_queue,
        f"{reading.get('com_port', 'Device')}: "
        f"Moisture/density saved | "
        f"{display_batch_ticket} | "
        f"Moisture {reading.get('moisture')}% | "
        f"Density {reading.get('density')} | "
        f"Row {row_number}",
    )

    logging.info(
        "Moisture/density saved for %s to %s row %s",
        display_batch_ticket,
        sheet_name,
        row_number,
    )


def handle_generic_roasting_reading(
    reading: dict,
    ui_queue: queue.Queue,
    excel_session: dict,
    excel_path,
) -> None:
    sheet_name, row_number = write_reading_to_excel(
        reading=reading,
        excel_session=excel_session,
        excel_path=excel_path,
    )

    save_reading_to_csv(reading)

    send_ui_message(
        ui_queue,
        f"{reading.get('com_port', 'Device')}: Saved to Excel: "
        f"{sheet_name}, row {row_number}",
    )

    logging.info(
        "Saved %s reading to %s row %s",
        reading.get("test_type"),
        sheet_name,
        row_number,
    )


def prewarm_roaster_log_cache(
    roaster_log_cache,
) -> None:
    try:
        roaster_log_cache.refresh()

    except Exception:
        logging.exception(
            "Could not prewarm the roaster log lookup."
        )


def backend_worker(
    ui_queue: queue.Queue,
    stop_event: threading.Event,
    duplicate_prompt_queue: queue.Queue,
    app_state: AppState,
) -> None:
    excel_session = None
    monitor_thread = None
    listener_threads = {}

    active_roasting_sample = None

    try:
        setup_folders()
        setup_logging()

        config = load_config()

        excel_path = resolve_excel_path(
            config["qa_excel_path"]
        )

        if not excel_path.exists():
            send_ui_message(
                ui_queue,
                f"ERROR: The QA Excel file was not found: {excel_path}",
            )

            stop_event.set()
            return

        create_csv_if_needed()

        reading_queue = queue.Queue()

        connected_ports = set()
        ports_lock = threading.Lock()

        excel_session = connect_to_excel(
            excel_path
        )

        # Reading both roaster logs takes a few seconds because they are large
        # files on a network share. Warming the cache here means the first
        # barcode scan does not have to wait for it.
        roaster_log_cache = RoasterLogCache(
            config
        )

        if roaster_log_cache.is_enabled():
            prewarm_thread = threading.Thread(
                target=prewarm_roaster_log_cache,
                args=(
                    roaster_log_cache,
                ),
                daemon=True,
            )

            prewarm_thread.start()

        else:
            logging.info(
                "Roaster log lookup is disabled. "
                "Quantity roasted, end temperature, and roaster number "
                "will be left blank."
            )

        send_ui_message(
            ui_queue,
            "QA Logger started.",
        )

        send_ui_message(
            ui_queue,
            f"Excel workbook opened: {excel_path}",
        )

        send_ui_message(
            ui_queue,
            "Select Roasting Tests or Packaging Tests before scanning.",
        )

        send_ui_message(
            ui_queue,
            "Monitoring connected USB serial ports.",
        )

        monitor_thread = threading.Thread(
            target=monitor_serial_ports,
            args=(
                config,
                reading_queue,
                ui_queue,
                stop_event,
                listener_threads,
                connected_ports,
                ports_lock,
            ),
            daemon=True,
        )

        monitor_thread.start()

        while not stop_event.is_set():
            try:
                reading = reading_queue.get(
                    timeout=0.2
                )

            except queue.Empty:
                continue

            try:
                test_type = reading.get(
                    "test_type"
                )

                current_mode = app_state.get_mode()

                if current_mode is None:
                    save_reading_to_csv(reading)

                    send_ui_message(
                        ui_queue,
                        f"{reading.get('com_port', 'Device')}: NOT SAVED: "
                        "Select Roasting Tests or Packaging Tests first.",
                    )

                    logging.warning(
                        "Reading received before mode selection. test_type=%s raw=%s",
                        test_type,
                        reading.get("raw_input", ""),
                    )

                    continue

                if not is_machine_test_allowed_for_mode(
                    test_type=test_type,
                    mode=current_mode,
                ):
                    save_reading_to_csv(reading)

                    send_ui_message(
                        ui_queue,
                        build_wrong_machine_mode_message(
                            com_port=reading.get(
                                "com_port",
                                "Device",
                            ),
                            test_type=test_type,
                            current_mode=current_mode,
                        ),
                    )

                    logging.warning(
                        "Rejected machine reading because wrong mode was selected. "
                        "mode=%s test_type=%s raw=%s",
                        current_mode,
                        test_type,
                        reading.get("raw_input", ""),
                    )

                    continue

                if test_type == "GasAnalysis":
                    handle_gas_analysis_reading(
                        reading=reading,
                        ui_queue=ui_queue,
                        app_state=app_state,
                    )

                    continue

                if current_mode == "packaging":
                    save_reading_to_csv(reading)

                    send_ui_message(
                        ui_queue,
                        f"{reading.get('com_port', 'Device')}: Packaging mode selected. "
                        "Packaging Excel writing is not built yet. Result saved to CSV only.",
                    )

                    logging.info(
                        "Packaging mode received %s. Saved to CSV only for now.",
                        test_type,
                    )

                    continue

                if current_mode == "roasting":
                    if test_type == "SampleBarcode":
                        active_roasting_sample = handle_sample_barcode_reading(
                            reading=reading,
                            ui_queue=ui_queue,
                            excel_session=excel_session,
                            excel_path=excel_path,
                            roaster_log_cache=roaster_log_cache,
                        )

                        continue

                    if test_type == "MoistureDensity":
                        handle_moisture_density_reading(
                            reading=reading,
                            ui_queue=ui_queue,
                            excel_session=excel_session,
                            excel_path=excel_path,
                            active_roasting_sample=active_roasting_sample,
                        )

                        continue

                    handle_generic_roasting_reading(
                        reading=reading,
                        ui_queue=ui_queue,
                        excel_session=excel_session,
                        excel_path=excel_path,
                    )

                    continue

            except DuplicateBatchTicketError as error:
                response_queue = queue.Queue()

                duplicate_prompt_queue.put(
                    {
                        "full_batch_ticket": error.full_batch_ticket,
                        "duplicate_sheet": error.duplicate_sheet,
                        "duplicate_row": error.duplicate_row,
                        "response_queue": response_queue,
                    }
                )

                send_ui_message(
                    ui_queue,
                    f"{reading.get('com_port', 'Device')}: Duplicate batch "
                    f"{error.full_batch_ticket} found. Waiting for user decision.",
                )

                try:
                    should_override = response_queue.get(
                        timeout=120
                    )

                except queue.Empty:
                    send_ui_message(
                        ui_queue,
                        f"{reading.get('com_port', 'Device')}: Duplicate decision timed out. "
                        "Result was not saved.",
                    )

                    logging.warning(
                        "Duplicate batch decision timed out for batch %s",
                        error.full_batch_ticket,
                    )

                    continue

                if not should_override:
                    send_ui_message(
                        ui_queue,
                        f"{reading.get('com_port', 'Device')}: Duplicate batch "
                        f"{error.full_batch_ticket} cancelled. Result was not saved.",
                    )

                    logging.info(
                        "Duplicate batch %s cancelled by user.",
                        error.full_batch_ticket,
                    )

                    continue

                sheet_name, row_number = write_reading_to_excel(
                    reading=reading,
                    excel_session=excel_session,
                    excel_path=excel_path,
                    allow_duplicate=True,
                )

                save_reading_to_csv(reading)

                send_ui_message(
                    ui_queue,
                    f"{reading.get('com_port', 'Device')}: Saved duplicate/retest to Excel: "
                    f"{sheet_name}, row {row_number}",
                )

                logging.info(
                    "Duplicate batch %s saved by user override to %s row %s",
                    reading.get("full_batch_ticket"),
                    sheet_name,
                    row_number,
                )

            except PermissionError as error:
                send_ui_message(
                    ui_queue,
                    f"NOT SAVED: {error}",
                )

                logging.exception(
                    "Workbook permission error"
                )

            except ValueError as error:
                send_ui_message(
                    ui_queue,
                    f"NOT SAVED: {error}",
                )

                logging.warning(
                    "Reading rejected: %s | raw=%s",
                    error,
                    reading.get("raw_input", ""),
                )

            except Exception as error:
                send_ui_message(
                    ui_queue,
                    f"Excel update error: {error}",
                )

                logging.exception(
                    "Excel update error"
                )

            finally:
                reading_queue.task_done()

    except Exception as error:
        send_ui_message(
            ui_queue,
            f"CRASH: {error}",
        )

        logging.exception(
            "Backend worker crashed"
        )

        stop_event.set()

    finally:
        stop_event.set()

        if monitor_thread is not None:
            monitor_thread.join(
                timeout=3
            )

        for listener_thread in list(
            listener_threads.values()
        ):
            listener_thread.join(
                timeout=3
            )

        close_excel_connection(
            excel_session
        )

        send_ui_message(
            ui_queue,
            "QA Logger stopped.",
        )


def run_app() -> None:
    setup_folders()
    setup_logging()

    ui_queue = queue.Queue()
    duplicate_prompt_queue = queue.Queue()
    stop_event = threading.Event()
    app_state = AppState()

    worker_thread = threading.Thread(
        target=backend_worker,
        args=(
            ui_queue,
            stop_event,
            duplicate_prompt_queue,
            app_state,
        ),
        daemon=True,
    )

    worker_thread.start()

    window = QALoggerWindow(
        ui_queue=ui_queue,
        stop_event=stop_event,
        duplicate_prompt_queue=duplicate_prompt_queue,
        app_state=app_state,
    )

    window.run()

    stop_event.set()

    worker_thread.join(
        timeout=5
    )


if __name__ == "__main__":
    try:
        run_app()

    except Exception as error:
        setup_folders()

        crash_log_path = LOG_DIR / "crash_error.log"

        with open(
            crash_log_path,
            "a",
            encoding="utf-8",
        ) as crash_log:
            crash_log.write(
                "\n" + "=" * 80 + "\n"
            )

            crash_log.write(
                f"Crash time: "
                f"{datetime.now().isoformat(timespec='seconds')}\n"
            )

            crash_log.write(
                f"Error: {repr(error)}\n"
            )

            import traceback

            crash_log.write(
                traceback.format_exc()
            )

        print()
        print("The QA Logger crashed.")
        print(f"Error: {error}")
        print()
        print("The full crash details were saved here:")
        print(crash_log_path)
        print()
        input("Press Enter to close this window...")