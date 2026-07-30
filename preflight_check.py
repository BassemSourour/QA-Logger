"""
Pre-presentation readiness check. Read-only: it changes nothing.

Run this a couple of minutes before a demo or a shift:

    python preflight_check.py

It verifies the things that have actually broken before:
- config.json loads and the QA workbook path resolves
- the QA workbook is not currently open or locked by Excel
- the QA workbook has a sheet for this month, and for next month if the
  month is about to roll over
- the roaster log share is reachable and both workbooks can be read
- a batch ticket from the current roaster log month resolves end to end
- USB serial ports are visible

Exit code is 0 when everything passed, 1 when anything failed.
"""

import sys
from datetime import datetime, timedelta
from pathlib import Path

results = []


def record(
    passed: bool,
    label: str,
    detail: str = "",
) -> bool:
    results.append(
        (
            passed,
            label,
            detail,
        )
    )

    mark = "PASS" if passed else "FAIL"

    print(
        f"  [{mark}] {label}"
        + (
            f"\n         {detail}"
            if detail
            else ""
        )
    )

    return passed


def check_config():
    print("\nConfig")

    try:
        from app.config_loader import load_config, resolve_excel_path

        config = load_config()

    except Exception as error:
        record(
            False,
            "config.json loads",
            repr(
                error
            ),
        )

        return None, None

    record(
        True,
        "config.json loads",
    )

    excel_path = resolve_excel_path(
        config["qa_excel_path"]
    )

    record(
        excel_path.exists(),
        "QA workbook exists",
        str(
            excel_path
        ),
    )

    baud_rates = config.get(
        "serial_probe_baud_rates"
    )

    pinned_ports = config.get(
        "port_baud_rates"
    ) or {}

    record(
        bool(
            baud_rates
        ),
        f"probe baud rates configured: {baud_rates}",
    )

    if pinned_ports:
        record(
            True,
            f"ports pinned to a known baud rate: {pinned_ports}",
        )

    else:
        print(
            "  [WARN] no port_baud_rates pinned. Devices will be probed, and an\n"
            "         unprobed device can lose its very first print. Once you see\n"
            "         'Locked COM<n> at <baud> baud' in the log, pin it in config.json."
        )

    return config, excel_path


def check_workbook_lock(
    excel_path: Path,
):
    print("\nQA workbook availability")

    lock_file = excel_path.parent / f"~${excel_path.name}"

    record(
        not lock_file.exists(),
        "no Excel lock file beside the workbook",
        f"found {lock_file}" if lock_file.exists() else "",
    )

    # An exclusive open is the same thing the app does at startup.
    try:
        with open(
            excel_path,
            "r+b",
        ):
            pass

        record(
            True,
            "workbook is not locked by another program",
        )

    except Exception as error:
        record(
            False,
            "workbook is not locked by another program",
            f"{error}. Close Excel completely before starting the logger.",
        )


def check_month_sheets(
    excel_path: Path,
):
    print("\nMonth sheets")

    try:
        import openpyxl

        from services.month_utils import get_month_sheet_name

        workbook = openpyxl.load_workbook(
            filename=str(
                excel_path
            ),
            read_only=True,
            data_only=True,
        )

        sheet_names = workbook.sheetnames

        workbook.close()

    except Exception as error:
        record(
            False,
            "QA workbook can be read",
            repr(
                error
            ),
        )

        return

    today = datetime.now()

    current_sheet = get_month_sheet_name(
        today
    )

    record(
        current_sheet in sheet_names,
        f"sheet for this month exists: '{current_sheet}'",
        "" if current_sheet in sheet_names
        else "Roasting writes will fail until this sheet exists.",
    )

    # Warn before a month rollover, which silently breaks every write.
    next_month_day = (
        today.replace(
            day=1
        )
        + timedelta(
            days=32
        )
    ).replace(
        day=1
    )

    days_left = (
        next_month_day - today
    ).days

    if days_left <= 7:
        next_sheet = get_month_sheet_name(
            next_month_day
        )

        record(
            next_sheet in sheet_names,
            f"sheet for next month exists: '{next_sheet}' "
            f"(month rolls over in {days_left} day(s))",
            "" if next_sheet in sheet_names
            else f"Create '{next_sheet}' now, or every write fails after rollover.",
        )


def check_roaster_logs(
    config: dict,
):
    print("\nRoaster logs")

    roaster_logs = config.get(
        "roaster_logs"
    ) or []

    if not record(
        bool(
            roaster_logs
        ),
        "roaster_logs configured",
        "" if roaster_logs
        else "Quantity roasted, end temperature and roaster number will stay blank.",
    ):
        return

    for roaster_log in roaster_logs:
        path = Path(
            roaster_log["excel_path"]
        )

        record(
            path.exists(),
            f"roaster {roaster_log.get('roaster_number')} log reachable",
            str(
                path
            ),
        )


def check_roaster_lookup(
    config: dict,
):
    print("\nRoaster log lookup (end to end)")

    if not (
        config.get(
            "roaster_logs"
        )
        or []
    ):
        return

    try:
        import time

        from services.roaster_log_lookup_service import (
            RoasterLogCache,
        )

        started_at = time.time()

        cache = RoasterLogCache(
            config
        )

        lookup = cache.refresh()

        elapsed = time.time() - started_at

        if not record(
            bool(
                lookup
            ),
            f"lookup built: {len(lookup)} batch tickets in {elapsed:.1f}s",
            "" if lookup
            else "No tickets found. Check that the logs have a sheet for this month.",
        ):
            return

        # Prove a real ticket resolves, including the padded barcode form.
        sample_key = max(
            lookup,
            key=lambda key: len(
                lookup[key]["source_rows"]
            ),
        )

        record(
            cache.get_roaster_log_data(
                f"BT{sample_key.zfill(9)}"
            )
            is not None,
            f"ticket {sample_key} resolves from barcode form "
            f"BT{sample_key.zfill(9)}",
            f"{lookup[sample_key]['quantity_roasted']} lbs | "
            f"{lookup[sample_key]['end_temperature']} F | "
            f"roaster {lookup[sample_key]['roaster_number']} | "
            f"{len(lookup[sample_key]['source_rows'])} roast row(s)",
        )

    except Exception as error:
        record(
            False,
            "roaster log lookup runs",
            repr(
                error
            ),
        )


def check_serial_ports():
    print("\nSerial ports")

    try:
        from devices.device_monitor import detect_usb_serial_ports

        detected = detect_usb_serial_ports()

    except Exception as error:
        record(
            False,
            "USB serial detection runs",
            repr(
                error
            ),
        )

        return

    record(
        bool(
            detected
        ),
        f"USB serial ports detected: {detected}",
        "" if detected
        else "Plug the devices in before starting the logger.",
    )


def main() -> int:
    print("=" * 68)
    print(
        " QA Logger preflight check   "
        + datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        )
    )
    print("=" * 68)

    config, excel_path = check_config()

    if config is None:
        print("\nConfig could not be loaded. Nothing else could be checked.")

        return 1

    if excel_path is not None and excel_path.exists():
        check_workbook_lock(
            excel_path
        )

        check_month_sheets(
            excel_path
        )

    check_roaster_logs(
        config
    )

    check_roaster_lookup(
        config
    )

    check_serial_ports()

    failed = [
        label
        for passed, label, _detail in results
        if not passed
    ]

    print("\n" + "=" * 68)

    if failed:
        print(f" NOT READY - {len(failed)} check(s) failed:")

        for label in failed:
            print(f"   - {label}")

    else:
        print(f" READY - all {len(results)} checks passed.")

    print("=" * 68)

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(
        main()
    )
