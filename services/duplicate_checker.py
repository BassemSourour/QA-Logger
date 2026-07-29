def find_duplicate_batch_ticket(
    workbook,
    full_batch_ticket: int,
) -> tuple[str, int] | None:
    for worksheet in workbook.Worksheets:
        used_range = worksheet.UsedRange
        row_count = used_range.Rows.Count

        for row_number in range(
            4,
            row_count + 1,
        ):
            value = worksheet.Cells(
                row_number,
                2,
            ).Value

            if value is None:
                continue

            try:
                existing_batch = int(
                    value
                )

            except Exception:
                continue

            if existing_batch == full_batch_ticket:
                return (
                    worksheet.Name,
                    row_number,
                )

    return None