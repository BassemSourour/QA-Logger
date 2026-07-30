# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A Windows-only Tkinter desktop app for a coffee roastery QA lab. It listens to lab instruments on USB serial ports, parses their printout streams, and writes results into a live Excel workbook (`Quality Assurance <year>.xlsx`) via COM automation, plus a CSV audit trail.

## Commands

```powershell
pip install -r requirements.txt
python main.py                              # run the app (opens Excel, needs real COM devices)
pyinstaller OA_Logger.spec                  # build dist/OA_Logger.exe (current spec; QA_Logger.spec is the older one)
python ma35_serial_test.py                  # scratch script: dump raw bytes from a hardcoded COM port
```

There are no tests, linter, formatter, or CI. Python 3.14 (`__pycache__` is `cpython-314`).

A `.gitignore` now covers `build/`, `dist/`, `__pycache__/`, `logs/`, `data/`, and `backups/`, but those paths were already committed in `8fc7981`, so git keeps tracking them until someone runs `git rm -r --cached`. `*.spec` is deliberately **not** ignored — `OA_Logger.spec` is the build definition.

## Runtime architecture

Four kinds of threads, communicating **only** through `queue.Queue`:

1. **Main thread** — `ui/desktop_window.py` Tk mainloop. Polls `ui_queue` every 200 ms.
2. **`backend_worker`** (`main.py`) — owns the Excel session and all routing logic.
3. **`monitor_serial_ports`** (`devices/device_monitor.py`) — one thread, polls available COM ports every `reconnect_delay_seconds`, spawns/reaps listeners.
4. **`listen_to_serial_device`** (`devices/serial_listener.py`) — one thread per connected port.

Queues:

- `reading_queue` — listener threads → `backend_worker`. Payload is a plain dict ("reading").
- `ui_queue` — anyone → UI. Payload is a **plain string**.
- `duplicate_prompt_queue` — `backend_worker` → UI, carrying a nested `response_queue` for the answer (120 s timeout).

### UI messages are a de-facto protocol

`QALoggerWindow.get_message_type`, `update_status_from_message`, and `extract_port` classify activity rows and drive the device table by **substring matching on the message text** (`"Saved to Excel"`, `"Device disconnected"`, `"NOT SAVED:"`, `"Received:"`, a leading `"COM<n>: "` prefix, …). Rewording a `send_ui_message` string in `main.py` or `serial_listener.py` silently breaks status colors, the connected-device count, and the device rows. Change both sides together.

## The reading dict

Every parser returns a dict with `device_type` and `test_type`; `test_type` is the single routing key used by both `main.backend_worker` and `writers.qa_excel_writer.write_reading_to_excel`. `com_port` and `baud_rate` are stamped on by the listener. Writers mutate the dict in place to add `qa_sheet_name`, `qa_row_number`, `excel_batch_ticket`, `sample_action`. `writers/csv_writer.py` projects it onto a fixed header list (unknown keys are dropped, so a new field needs adding to `READING_HEADERS` to be persisted).

## Serial input pipeline

`device_monitor` detects USB serial ports by keyword-sniffing `list_ports.comports()` descriptions (`usb`, `ftdi`, `ch340`, `cp210`, …) and **writes the discovered list back into `config.json`** — the `com_ports` field is an output, not configuration.

Each listener then finds the device's baud rate. A port can only be open at one baud rate at a time, so this has to be discovered by listening. The rule is **rotate on garbage, not on a timer** (`find_working_baud_rate`):

1. A port listed in `port_baud_rates` is used directly and never probed. This is the reliable option for a known device — no probe, so no chance of losing its first print.
2. While the port is **silent**, stay on the current baud rate. The old code rotated every 3 s, which is what lost BeanPro readings: the device prints once and never repeats, so a reopen at the wrong moment discarded the reading outright.
3. Once bytes arrive, judge them with `looks_like_device_text` on the **raw bytes** — mostly non-printable means the baud rate is wrong, so rotate immediately; readable text arms a `serial_probe_window_seconds` deadline on that baud rate.

`looks_like_device_text` must inspect raw bytes rather than the decoded string: `decode_serial_bytes` uses `errors="replace"`, which turns wrong-baud garbage into innocuous-looking question marks.

Wire format beyond baud comes from `serial_defaults` (8-N-1; the BeanPro is confirmed working at that framing — `ma35_serial_test.py` uses 7-O-1 for a *different* instrument, so don't copy it).

`is_port_still_connected` is checked once per serial read and memoized for 2 s by `get_available_port_names`. Uncached, `list_ports.comports()` costs ~95 ms per call, which was being paid on every single `readline()`.

`clean_serial_display_line` pre-trims raw lines (strips NULs, drops all-semicolon garbage, truncates CheckMate 3 lines to their first 11 semicolon fields) before parsing.

### Adding a device

Add a module under `devices/parsers/` exposing `parse_x(raw_line) -> dict | None`, then register it in the `parsers` list in `devices/parsers/parser_router.py`. First parser to return non-`None` wins, so ordering matters. `colour_meter_parser.py` and `sieve_analyzer_parser.py` are registered stubs that always return `None`.

Currently implemented: barcode scanner (`SampleBarcode`), Ohaus/BeanPro moisture-density (`MoistureDensity`), Dansensor CheckMate 3 (`GasAnalysis`).

## Mode gating and roasting session state

`app/app_state.py` holds a lock-guarded mode: `"roasting"`, `"packaging"`, or `None`. `services/mode_validation_service.py` maps each machine `test_type` to the mode that accepts it.

Routing precedence in `backend_worker`:

1. No mode selected → CSV only, `NOT SAVED` message.
2. Machine test not allowed for the current mode → CSV only, "switch to X" message.
3. `GasAnalysis` → CSV only (Excel writing for O2 is not built).
4. Packaging mode → CSV only (packaging Excel writing is not built).
5. Roasting mode → Excel.

The roasting flow is **stateful**: scanning a sample barcode sets `active_roasting_sample` (a local variable in `backend_worker`, holding sheet name + row number). A subsequent `MoistureDensity` reading is written to *that* row; with no active sample it is rejected to CSV. Only one active sample exists globally — the most recent scan wins.

Barcode format is `BT000095489/BLA/54` or `BT000095489-BLA-54` (ticket / blend / target color). `services/sample_barcode_service.py` derives `formula_code` (`BLA54`) and the roast spec range (`target ± 2` → `"52-56"`).

## Excel layer

`writers/excel_connection.py` drives a **visible** Excel instance through `win32com` (`pythoncom.CoInitialize()` runs on the worker thread). `openpyxl` is in `requirements.txt` but unused by the running code. If the workbook opens read-only the app raises `PermissionError` and refuses to start — the workbook must not already be open elsewhere.

`writers/qa_excel_writer.py` conventions:

- One worksheet per month, named `datetime.strftime("%B %Y")` (`"July 2026"`), via `services/month_utils.py`. The sheet must already exist; a missing sheet is a `ValueError`.
- Roasting data starts at row 4 (`ROASTING_START_ROW`); columns are module-level constants (`BATCH_TICKET_COLUMN = 2`, `MOISTURE_COLUMN = 5`, …). Change them there, not inline.
- Column A holds the date **once per date group**. `find_new_roasting_row_for_date` finds the group for a date, reuses the first blank row inside it, and otherwise calls `Rows(...).Insert()` to keep date groups contiguous and chronologically ordered.
- Batch tickets are normalized for Excel by stripping the `BT` prefix and leading zeros (`BT000095489` → `95489`); `get_batch_compare_keys` / `batch_tickets_match` compare both forms so an existing row is found either way.
- Every write calls `workbook.Save()`; new samples and moisture/density writes also copy the whole `.xlsx` into `backups/` (`services/backup_service.py`). This directory grows quickly.

## Roaster log lookup

`services/roaster_log_lookup_service.py` fills the QA sheet's quantity-roasted, end-temperature, and roaster-number columns from the two roaster log workbooks on the `S:` share. The lookup runs on the backend worker **before** `write_reading_to_excel`, and the result rides on `reading["roaster_log_data"]` so no file reading happens on the Excel write path.

Both workbooks share a layout: header on row 6, data from **row 7**, batch ticket in **col C**, `FINAL TEMP.` in **col J**, `LBS` in **col M**.

A batch ticket normally spans several roast rows, so **pounds are summed** across them and the final temperature is taken from the last row that has one. Batch `96560` has 10 rows summing to 3920 lbs at 432°F on roaster 2 — which is exactly what the old hardcoded demo dict contained, confirming the semantics.

Four things about these files dictate the implementation, and all three of the previous implementation's bugs came from missing them:

- **Never trust `max_row`.** Roaster 2's July sheet reports `max_row: 1048565`, `max_column: 16384`. The old code looped `range(7, max_row + 1)` with random `.cell()` access on a read-only sheet — that is why lookups were slow and why tickets that were plainly visible in the sheet were never found. Use `iter_rows(min_row=7, max_col=13, values_only=True)` bounded by `MAX_SCAN_ROWS` and `MAX_CONSECUTIVE_BLANK_ROWS`.
- **Chartsheets are interleaved** among the month sheets. A `Chartsheet` has no `max_row`/`iter_rows`; `is_data_worksheet` filters them.
- **Sheet names are inconsistent** across 77/85 sheets (`'2026 July'` vs `'JULY 2026 '`), so `find_month_sheet_names` matches on normalized year + 3-letter month tokens, and only the current and previous month are scanned. A batch roasted more than about a month before its QA test will not resolve.
- **openpyxl, never COM.** Reading these over COM produced `Call was rejected by callee` because Excel was busy with the QA workbook. openpyxl read-only streams the XML and leaves the running Excel instance alone.

`RoasterLogCache` holds the result with a `roaster_log_cache_seconds` TTL (default 120) and is prewarmed by a daemon thread in `backend_worker`, since a cold read of both files takes ~2 s. A miss forces one refresh — a miss usually means the roast was logged after the last read — rate-limited by `MIN_REFRESH_INTERVAL_SECONDS`. Every failure path logs and yields an empty lookup; a missing or unreachable `S:` drive disables the feature rather than blocking QA testing, and unmatched cells are left untouched rather than blanked.

`normalize_batch_ticket_key` reduces `BT000096560`, `000096560`, `96560`, `96560.0`, int/float cell values, and surrounding spaces to one key. It duplicates ~10 lines of `normalize_batch_ticket_for_excel` in `qa_excel_writer.py`; kept separate to avoid a `services` → `writers` import.

### Known dormant / hack code

- `DuplicateBatchTicketError` is defined and fully handled in `main.py` (prompt, override, re-write with `allow_duplicate=True`), but **nothing raises it** — the duplicate-detection path is inert. `services/duplicate_checker.py` is the unused implementation.
- Unreferenced or empty: `services/batch_resolver.py` (pre-barcode workflow), `services/duplicate_checker.py`, `ui/console_ui.py`, `inputs/*.py`, `app/models.py`.

## Paths and config

`app/paths.py` resolves `BASE_DIR` to the executable's directory when frozen, otherwise the repo root; `config.json`, `data/`, `logs/`, and `backups/` all hang off it, so the packaged exe reads a `config.json` sitting beside it (see `dist/`). `qa_excel_path` may be absolute or relative to `config.json`. Only `qa_excel_path` is required; everything else has defaults in `app/config_loader.py`.

Serial and roaster-log keys: `serial_probe_baud_rates`, `serial_probe_window_seconds`, `port_baud_rates` (`{"COM5": 4800}` — skips probing for that port), `roaster_logs` (`[{roaster_number, excel_path}]`), `roaster_log_cache_seconds`. The roaster-log and per-port validators **sanitize and warn rather than raise**, deliberately: a bad entry or an unreachable share must not stop the app from starting. Because `device_monitor.update_detected_ports_in_config` rewrites `config.json` whenever the port list changes, any defaults the loader fills in get persisted into the file on the first port change.

Logging is a single `logging.basicConfig` to `logs/qa_logger.log`; an unhandled crash in `run_app` also appends a traceback to `logs/crash_error.log` and pauses on `input()`.

## Code style

The codebase uses a distinctive very-vertical formatting style: one argument per line, keyword arguments almost everywhere, blank lines between statements, `logging` with `%s` lazy formatting. There is no formatter config — match the surrounding file rather than reformatting it.
