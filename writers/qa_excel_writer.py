import logging
from datetime import datetime
from pathlib import Path

import pywintypes

from services.backup_service import create_workbook_backup
from services.month_utils import get_month_sheet_name


ROASTING_START_ROW = 4

DATE_COLUMN = 1
BATCH_TICKET_COLUMN = 2
FORMULA_COLUMN = 3
DATE_ROASTED_COLUMN = 4
MOISTURE_COLUMN = 5
DENSITY_COLUMN = 6
QUANTITY_ROASTED_COLUMN = 8
ROAST_SPEC_COLUMN = 11
ACTUAL_COLOR_COLUMN = 12
END_TEMPERATURE_COLUMN = 13
ROASTER_NUMBER_COLUMN = 14
PRESENTATION_ROASTER_DATA = {
    "96560": {
        "quantity_roasted": 3920,
        "end_temperature": 432,
        "roaster_number": 2,
    },
}
ROASTING_START_COLUMN = 1
ROASTING_END_COLUMN = 15

EXCEL_HORIZONTAL_CENTER = -4108
EXCEL_VERTICAL_CENTER = -4108


class DuplicateBatchTicketError(Exception):
    def __init__(
        self,
        full_batch_ticket: int,
        duplicate_sheet: str,
        duplicate_row: int,
    ) -> None:
        self.full_batch_ticket = full_batch_ticket
        self.duplicate_sheet = duplicate_sheet
        self.duplicate_row = duplicate_row

        super().__init__(
            f"Duplicate batch ticket {full_batch_ticket} already exists "
            f"in {duplicate_sheet}, row {duplicate_row}."
        )


def get_worksheet(
    workbook,
    sheet_name: str,
):
    try:
        return workbook.Worksheets(
            sheet_name
        )

    except Exception:
        raise ValueError(
            f"Worksheet '{sheet_name}' was not found in the QA workbook."
        )


def center_row_cells(
    worksheet,
    row_number: int,
    start_column: int = ROASTING_START_COLUMN,
    end_column: int = ROASTING_END_COLUMN,
) -> None:
    cell_range = worksheet.Range(
        worksheet.Cells(
            row_number,
            start_column,
        ),
        worksheet.Cells(
            row_number,
            end_column,
        ),
    )

    cell_range.HorizontalAlignment = EXCEL_HORIZONTAL_CENTER
    cell_range.VerticalAlignment = EXCEL_VERTICAL_CENTER


def normalize_excel_text(
    value,
) -> str:
    if value is None:
        return ""

    text = str(
        value
    ).strip().upper()

    if text.endswith(".0"):
        text = text[:-2]

    return text.replace(
        " ",
        "",
    )


def normalize_batch_ticket_for_excel(
    batch_ticket,
) -> str:
    text = normalize_excel_text(
        batch_ticket
    )

    if text.startswith("BT"):
        text = text[2:]

    if text.isdigit():
        text = str(
            int(
                text
            )
        )

    return text


def get_batch_compare_keys(
    value,
) -> set[str]:
    text = normalize_excel_text(
        value
    )

    if not text:
        return set()

    keys = {
        text,
    }

    if text.startswith("BT"):
        number_part = text[2:]

        if number_part.isdigit():
            stripped_number = str(
                int(
                    number_part
                )
            )

            keys.add(
                stripped_number
            )

            keys.add(
                f"BT{stripped_number}"
            )

    elif text.isdigit():
        stripped_number = str(
            int(
                text
            )
        )

        keys.add(
            stripped_number
        )

        keys.add(
            f"BT{stripped_number}"
        )

    return keys


def batch_tickets_match(
    left,
    right,
) -> bool:
    left_keys = get_batch_compare_keys(
        left
    )

    right_keys = get_batch_compare_keys(
        right
    )

    if not left_keys or not right_keys:
        return False

    return not left_keys.isdisjoint(
        right_keys
    )


def find_next_roasting_row(
    worksheet,
) -> int:
    used_range = worksheet.UsedRange

    last_used_row = (
        used_range.Row
        + used_range.Rows.Count
        - 1
    )

    last_roasting_row = ROASTING_START_ROW - 1

    for row_number in range(
        ROASTING_START_ROW,
        last_used_row + 1,
    ):
        batch_value = worksheet.Cells(
            row_number,
            BATCH_TICKET_COLUMN,
        ).Value

        formula_value = worksheet.Cells(
            row_number,
            FORMULA_COLUMN,
        ).Value

        date_roasted_value = worksheet.Cells(
            row_number,
            DATE_ROASTED_COLUMN,
        ).Value

        moisture_value = worksheet.Cells(
            row_number,
            MOISTURE_COLUMN,
        ).Value

        density_value = worksheet.Cells(
            row_number,
            DENSITY_COLUMN,
        ).Value

        roast_spec_value = worksheet.Cells(
            row_number,
            ROAST_SPEC_COLUMN,
        ).Value

        actual_color_value = worksheet.Cells(
            row_number,
            ACTUAL_COLOR_COLUMN,
        ).Value

        if (
            batch_value is not None
            or formula_value is not None
            or date_roasted_value is not None
            or moisture_value is not None
            or density_value is not None
            or roast_spec_value is not None
            or actual_color_value is not None
        ):
            last_roasting_row = row_number

    return last_roasting_row + 1


def find_batch_ticket_row_in_sheet(
    worksheet,
    batch_ticket,
) -> int | None:
    used_range = worksheet.UsedRange

    last_used_row = (
        used_range.Row
        + used_range.Rows.Count
        - 1
    )

    for row_number in range(
        ROASTING_START_ROW,
        last_used_row + 1,
    ):
        current_value = worksheet.Cells(
            row_number,
            BATCH_TICKET_COLUMN,
        ).Value

        if batch_tickets_match(
            current_value,
            batch_ticket,
        ):
            return row_number

    return None


def convert_to_excel_date(
    date_value: datetime,
):
    return pywintypes.Time(
        datetime(
            date_value.year,
            date_value.month,
            date_value.day,
        )
    )


def get_python_date_only(
    value,
):
    if value is None:
        return None

    if isinstance(
        value,
        datetime,
    ):
        return value.date()

    try:
        return datetime(
            value.year,
            value.month,
            value.day,
        ).date()

    except Exception:
        pass

    text = normalize_excel_text(
        value
    )

    if not text:
        return None

    date_formats = [
        "%b%d-%Y",
        "%b%d-%y",
        "%d-%b-%Y",
        "%d-%b-%y",
        "%d-%b",
    ]

    for date_format in date_formats:
        try:
            parsed_date = datetime.strptime(
                text,
                date_format,
            )

            if parsed_date.year == 1900:
                parsed_date = parsed_date.replace(
                    year=datetime.now().year
                )

            return parsed_date.date()

        except ValueError:
            continue

    return None


def is_roasting_data_row_blank(
    worksheet,
    row_number: int,
) -> bool:
    columns_to_check = [
        BATCH_TICKET_COLUMN,
        FORMULA_COLUMN,
        DATE_ROASTED_COLUMN,
        MOISTURE_COLUMN,
        DENSITY_COLUMN,
        ROAST_SPEC_COLUMN,
        ACTUAL_COLOR_COLUMN,
    ]

    for column_number in columns_to_check:
        value = worksheet.Cells(
            row_number,
            column_number,
        ).Value

        if normalize_excel_text(
            value
        ):
            return False

    return True


def get_last_used_roasting_row(
    worksheet,
) -> int:
    used_range = worksheet.UsedRange

    last_used_row = (
        used_range.Row
        + used_range.Rows.Count
        - 1
    )

    return max(
        last_used_row,
        ROASTING_START_ROW,
    )


def get_roasting_date_headers(
    worksheet,
) -> list[tuple[int, object]]:
    last_used_row = get_last_used_roasting_row(
        worksheet
    )

    date_headers = []

    for row_number in range(
        ROASTING_START_ROW,
        last_used_row + 1,
    ):
        date_value = worksheet.Cells(
            row_number,
            DATE_COLUMN,
        ).Value

        python_date = get_python_date_only(
            date_value
        )

        if python_date is not None:
            date_headers.append(
                (
                    row_number,
                    python_date,
                )
            )

    return date_headers


def find_new_roasting_row_for_date(
    worksheet,
    date_value: datetime,
) -> tuple[int, bool]:
    """
    Finds the correct row for a new roasting entry based on the date group.

    Returns:
        row_number
        should_write_date_header

    Behavior:
    - If the date group already exists, use the first blank row inside that group.
    - If no blank row exists, insert a row before the next date group.
    - If the date does not exist and a later date exists, insert before the later date.
    - If the date is after all existing dates, append at the bottom.
    """
    target_date = date_value.date()

    date_headers = get_roasting_date_headers(
        worksheet
    )

    last_used_row = get_last_used_roasting_row(
        worksheet
    )

    if not date_headers:
        return (
            ROASTING_START_ROW,
            True,
        )

    for index, (
        header_row,
        header_date,
    ) in enumerate(date_headers):
        next_header_row = None

        if index + 1 < len(
            date_headers
        ):
            next_header_row = date_headers[
                index + 1
            ][0]

        if header_date == target_date:
            group_end_row = (
                next_header_row - 1
                if next_header_row is not None
                else last_used_row
            )

            for row_number in range(
                header_row,
                group_end_row + 1,
            ):
                if is_roasting_data_row_blank(
                    worksheet,
                    row_number,
                ):
                    return (
                        row_number,
                        row_number == header_row,
                    )

            if next_header_row is not None:
                worksheet.Rows(
                    next_header_row
                ).Insert()

                return (
                    next_header_row,
                    False,
                )

            return (
                last_used_row + 1,
                False,
            )

        if header_date > target_date:
            worksheet.Rows(
                header_row
            ).Insert()

            return (
                header_row,
                True,
            )

    return (
        last_used_row + 1,
        True,
    )


def should_write_date_in_column_a(
    worksheet,
    row_number: int,
    date_value: datetime,
) -> bool:
    """
    Column A should only show the date once at the start of each day group.

    Example:
        A4 = Jun 11-2026
        A5 = blank
        A6 = blank

    When a new date starts, the first row for that new date gets Column A filled.
    """
    current_date = date_value.date()

    if row_number == ROASTING_START_ROW:
        return True

    for current_row in range(
        row_number - 1,
        ROASTING_START_ROW - 1,
        -1,
    ):
        previous_date_value = worksheet.Cells(
            current_row,
            DATE_COLUMN,
        ).Value

        previous_date = get_python_date_only(
            previous_date_value
        )

        if previous_date is None:
            continue

        return previous_date != current_date

    return True


def get_sheet_for_date(
    workbook,
    date_value: datetime,
):
    sheet_name = get_month_sheet_name(
        date_value
    )

    worksheet = get_worksheet(
        workbook,
        sheet_name,
    )

    return (
        sheet_name,
        worksheet,
    )


def write_sample_barcode_reading(
    reading: dict,
    excel_session: dict,
    excel_path: Path,
) -> tuple[str, int]:
    workbook = excel_session[
        "workbook"
    ]

    scan_datetime = reading.get(
        "machine_datetime"
    )

    if scan_datetime is None:
        scan_datetime = datetime.now()

    sheet_name, worksheet = get_sheet_for_date(
        workbook=workbook,
        date_value=scan_datetime,
    )

    excel_batch_ticket = normalize_batch_ticket_for_excel(
        reading[
            "batch_ticket"
        ]
    )

    row_number = find_batch_ticket_row_in_sheet(
        worksheet=worksheet,
        batch_ticket=excel_batch_ticket,
    )

    if row_number is not None:
        reading[
            "sample_action"
        ] = "selected"

        reading[
            "qa_sheet_name"
        ] = sheet_name

        reading[
            "qa_row_number"
        ] = row_number

        reading[
            "excel_batch_ticket"
        ] = excel_batch_ticket

        hardcoded_roaster_data_applied = apply_hardcoded_roaster_data_for_presentation(
            worksheet=worksheet,
            row_number=row_number,
            batch_ticket=excel_batch_ticket,
        )

        reading[
            "hardcoded_roaster_data_applied"
        ] = hardcoded_roaster_data_applied

        center_row_cells(
            worksheet=worksheet,
            row_number=row_number,
        )

        workbook.Save()

        logging.info(
            "Selected existing sample %s in %s row %s.",
            excel_batch_ticket,
            sheet_name,
            row_number,
        )

        return (
            sheet_name,
            row_number,
        )

    row_number, should_write_date_header = find_new_roasting_row_for_date(
        worksheet=worksheet,
        date_value=scan_datetime,
    )

    excel_date = convert_to_excel_date(
        scan_datetime
    )

    if should_write_date_header:
        worksheet.Cells(
            row_number,
            DATE_COLUMN,
        ).Value = excel_date

        worksheet.Cells(
            row_number,
            DATE_COLUMN,
        ).NumberFormat = "mmm d-yyyy"

    worksheet.Cells(
        row_number,
        BATCH_TICKET_COLUMN,
    ).Value = excel_batch_ticket

    worksheet.Cells(
        row_number,
        FORMULA_COLUMN,
    ).Value = reading[
        "formula_code"
    ]

    worksheet.Cells(
        row_number,
        DATE_ROASTED_COLUMN,
    ).Value = excel_date

    worksheet.Cells(
        row_number,
        DATE_ROASTED_COLUMN,
    ).NumberFormat = "dd-mmm"

    worksheet.Cells(
        row_number,
        ROAST_SPEC_COLUMN,
    ).Value = reading[
        "color_range_text"
    ]

    hardcoded_roaster_data_applied = apply_hardcoded_roaster_data_for_presentation(
        worksheet=worksheet,
        row_number=row_number,
        batch_ticket=excel_batch_ticket,
    )

    reading[
        "hardcoded_roaster_data_applied"
    ] = hardcoded_roaster_data_applied

    center_row_cells(
        worksheet=worksheet,
        row_number=row_number,
    )

    reading[
        "sample_action"
    ] = "created"

    reading[
        "qa_sheet_name"
    ] = sheet_name

    reading[
        "qa_row_number"
    ] = row_number

    reading[
        "excel_batch_ticket"
    ] = excel_batch_ticket

    workbook.Save()

    create_workbook_backup(
        excel_path
    )

    logging.info(
        "Created new sample %s in %s row %s.",
        reading.get("barcode_payload"),
        sheet_name,
        row_number,
    )

    return (
        sheet_name,
        row_number,
    )


def write_moisture_density_reading(
    reading: dict,
    excel_session: dict,
    excel_path: Path,
    allow_duplicate: bool = False,
) -> tuple[str, int]:
    active_sample = reading.get(
        "active_sample"
    )

    if active_sample is None:
        raise ValueError(
            "No active sample selected. Scan the sample barcode before running the moisture/density test."
        )

    workbook = excel_session[
        "workbook"
    ]

    sheet_name = active_sample[
        "sheet_name"
    ]

    row_number = active_sample[
        "row_number"
    ]

    worksheet = get_worksheet(
        workbook,
        sheet_name,
    )

    machine_datetime = reading[
        "machine_datetime"
    ]

    excel_date = convert_to_excel_date(
        machine_datetime
    )

    worksheet.Cells(
        row_number,
        DATE_ROASTED_COLUMN,
    ).Value = excel_date

    worksheet.Cells(
        row_number,
        DATE_ROASTED_COLUMN,
    ).NumberFormat = "dd-mmm"

    worksheet.Cells(
        row_number,
        MOISTURE_COLUMN,
    ).Value = reading[
        "moisture"
    ]

    worksheet.Cells(
        row_number,
        DENSITY_COLUMN,
    ).Value = reading[
        "density"
    ]

    center_row_cells(
        worksheet=worksheet,
        row_number=row_number,
    )

    reading[
        "full_batch_ticket"
    ] = active_sample[
        "batch_ticket"
    ]

    reading[
        "excel_batch_ticket"
    ] = active_sample.get(
        "excel_batch_ticket",
        normalize_batch_ticket_for_excel(
            active_sample[
                "batch_ticket"
            ]
        ),
    )

    reading[
        "qa_sheet_name"
    ] = sheet_name

    reading[
        "qa_row_number"
    ] = row_number

    workbook.Save()

    create_workbook_backup(
        excel_path
    )

    logging.info(
        "Saved moisture/density for %s to %s row %s.",
        active_sample.get("batch_ticket"),
        sheet_name,
        row_number,
    )

    return (
        sheet_name,
        row_number,
    )


def write_reading_to_excel(
    reading: dict,
    excel_session: dict,
    excel_path: Path,
    allow_duplicate: bool = False,
) -> tuple[str, int]:
    test_type = reading.get(
        "test_type"
    )

    if test_type == "SampleBarcode":
        return write_sample_barcode_reading(
            reading=reading,
            excel_session=excel_session,
            excel_path=excel_path,
        )

    if test_type == "MoistureDensity":
        return write_moisture_density_reading(
            reading=reading,
            excel_session=excel_session,
            excel_path=excel_path,
            allow_duplicate=allow_duplicate,
        )

    raise ValueError(
        f"No Excel writer is configured for test type: {test_type}"
    )

def apply_hardcoded_roaster_data_for_presentation(
    worksheet,
    row_number: int,
    batch_ticket,
) -> bool:
    batch_key = normalize_batch_ticket_for_excel(
        batch_ticket
    )

    roaster_data = PRESENTATION_ROASTER_DATA.get(
        batch_key
    )

    if roaster_data is None:
        return False

    worksheet.Cells(
        row_number,
        QUANTITY_ROASTED_COLUMN,
    ).Value = roaster_data[
        "quantity_roasted"
    ]

    worksheet.Cells(
        row_number,
        END_TEMPERATURE_COLUMN,
    ).Value = roaster_data[
        "end_temperature"
    ]

    worksheet.Cells(
        row_number,
        ROASTER_NUMBER_COLUMN,
    ).Value = roaster_data[
        "roaster_number"
    ]

    center_row_cells(
        worksheet=worksheet,
        row_number=row_number,
    )

    return True