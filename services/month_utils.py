from datetime import datetime


def get_month_sheet_name(
    date_value: datetime,
) -> str:
    return date_value.strftime(
        "%B %Y"
    )