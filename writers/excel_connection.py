import logging
from pathlib import Path

import pythoncom
import win32com.client.dynamic


def connect_to_excel(
    excel_path: Path,
) -> dict:
    pythoncom.CoInitialize()

    excel = win32com.client.dynamic.Dispatch(
        pythoncom.CoCreateInstance(
            "Excel.Application",
            None,
            pythoncom.CLSCTX_LOCAL_SERVER,
            pythoncom.IID_IDispatch,
        )
    )

    excel.Visible = True
    excel.DisplayAlerts = False

    workbook = excel.Workbooks.Open(
        str(excel_path.resolve()),
        ReadOnly=False,
        Notify=False,
    )

    if workbook.ReadOnly:
        workbook.Close(
            SaveChanges=False
        )

        excel.Quit()

        raise PermissionError(
            "The QA workbook opened as read-only. "
            "Close all Excel windows, make sure the workbook is closed, "
            "then start the application again."
        )

    logging.info(
        "Excel opened QA workbook: %s",
        excel_path,
    )

    return {
        "excel": excel,
        "workbook": workbook,
        "excel_started_by_logger": True,
        "workbook_opened_by_logger": True,
    }


def close_excel_connection(
    excel_session: dict | None,
) -> None:
    if excel_session is None:
        return

    workbook = excel_session.get(
        "workbook"
    )

    excel = excel_session.get(
        "excel"
    )

    try:
        if workbook is not None:
            workbook.Save()

    except Exception:
        logging.exception(
            "Could not save workbook during shutdown."
        )

    try:
        if workbook is not None:
            workbook.Close(
                SaveChanges=True
            )

    except Exception:
        logging.exception(
            "Could not close workbook during shutdown."
        )

    try:
        if excel is not None:
            excel.Quit()

    except Exception:
        logging.exception(
            "Could not close Excel during shutdown."
        )

    try:
        pythoncom.CoUninitialize()

    except Exception:
        logging.exception(
            "Could not uninitialize COM."
        )