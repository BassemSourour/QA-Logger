import logging
import os
import queue
import threading
import tkinter as tk
import winsound
from tkinter import messagebox
from tkinter import ttk

from app.paths import LOG_DIR
from app.paths import WINDOW_ICON_PATH


class QALoggerWindow:
    def __init__(
        self,
        ui_queue: queue.Queue,
        stop_event: threading.Event,
        duplicate_prompt_queue: queue.Queue | None = None,
        app_state=None,
    ) -> None:
        self.ui_queue = ui_queue
        self.stop_event = stop_event
        self.duplicate_prompt_queue = duplicate_prompt_queue
        self.app_state = app_state

        self.connected_ports = set()
        self.troubleshooting_frame = None

        self.root = tk.Tk()
        self.root.title("QA Logger")
        self.root.geometry("1050x680")
        self.root.minsize(900, 560)
        self.root.state("zoomed")

        self._apply_window_icon()

        self.status_text = tk.StringVar(value="Running")
        self.excel_status_text = tk.StringVar(value="Excel: Starting...")
        self.device_count_text = tk.StringVar(value="Connected Devices: 0")
        self.mode_status_text = tk.StringVar(value="Current Mode: No Mode Selected")

        self._setup_styles()
        self._build_window()

        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.check_ui_queue()

    def _apply_window_icon(self) -> None:
        """
        Sets the title bar and taskbar icon. Passing default= also applies it to
        every Toplevel the app opens later, so the message boxes match.

        The .ico is a bundled data file, so a missing or unreadable one must
        degrade to the stock Tk icon rather than stop the app from opening.
        """
        try:
            self.root.iconbitmap(
                default=str(
                    WINDOW_ICON_PATH
                ),
            )

        except Exception as icon_error:
            logging.warning(
                "Could not load window icon from %s: %s",
                WINDOW_ICON_PATH,
                icon_error,
            )

    def _setup_styles(self) -> None:
        self.style = ttk.Style()

        try:
            self.style.theme_use("clam")
        except Exception:
            pass

        self.style.configure("Header.TFrame", background="#1f2937")
        self.style.configure(
            "HeaderTitle.TLabel",
            background="#1f2937",
            foreground="white",
            font=("Segoe UI", 22, "bold"),
        )
        self.style.configure(
            "HeaderStatus.TLabel",
            background="#1f2937",
            foreground="#bbf7d0",
            font=("Segoe UI", 11, "bold"),
        )
        self.style.configure(
            "Card.TFrame",
            background="#f8fafc",
            relief="solid",
            borderwidth=1,
        )
        self.style.configure(
            "CardTitle.TLabel",
            background="#f8fafc",
            foreground="#111827",
            font=("Segoe UI", 10, "bold"),
        )
        self.style.configure(
            "CardValue.TLabel",
            background="#f8fafc",
            foreground="#111827",
            font=("Segoe UI", 12, "bold"),
        )
        self.style.configure(
            "SectionTitle.TLabel",
            foreground="#111827",
            font=("Segoe UI", 12, "bold"),
        )
        self.style.configure(
            "Treeview",
            rowheight=28,
            font=("Segoe UI", 10),
        )
        self.style.configure(
            "Treeview.Heading",
            font=("Segoe UI", 10, "bold"),
        )

    def _build_window(self) -> None:
        self.root.configure(background="#e5e7eb")
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(3, weight=1)

        self._build_header()
        self._build_mode_selector()
        self._build_status_cards()
        self._build_logger_content()
        self._build_bottom_buttons()

    def _build_header(self) -> None:
        header_frame = ttk.Frame(
            self.root,
            padding=16,
            style="Header.TFrame",
        )
        header_frame.grid(row=0, column=0, sticky="ew")
        header_frame.columnconfigure(0, weight=1)

        title_label = ttk.Label(
            header_frame,
            text="QA Logger",
            style="HeaderTitle.TLabel",
        )
        title_label.grid(row=0, column=0, sticky="w")

        status_label = ttk.Label(
            header_frame,
            textvariable=self.status_text,
            style="HeaderStatus.TLabel",
        )
        status_label.grid(row=0, column=1, sticky="e")

    def _build_mode_selector(self) -> None:
        self.mode_frame = tk.Frame(
            self.root,
            bg="#f4f6f8",
            padx=16,
            pady=12,
            bd=1,
            relief="solid",
        )
        self.mode_frame.grid(
            row=1,
            column=0,
            sticky="ew",
            padx=12,
            pady=(12, 0),
        )
        self.mode_frame.columnconfigure(0, weight=1)
        self.mode_frame.columnconfigure(1, weight=1)

        self.mode_title_label = tk.Label(
            self.mode_frame,
            text="What are you logging?",
            font=("Segoe UI", 16, "bold"),
            bg="#f4f6f8",
            fg="#1f2937",
        )
        self.mode_title_label.grid(
            row=0,
            column=0,
            columnspan=2,
            pady=(0, 8),
        )

        self.mode_cards_frame = tk.Frame(
            self.mode_frame,
            bg="#f4f6f8",
        )
        self.mode_cards_frame.grid(
            row=1,
            column=0,
            columnspan=2,
            pady=4,
        )

        self.roasting_mode_card = self.create_mode_card(
            parent=self.mode_cards_frame,
            title="Roasting Tests",
            subtitle="Moisture, density, roast spec, color",
            normal_bg="#ecfdf5",
            hover_bg="#d1fae5",
            selected_bg="#bbf7d0",
            accent_color="#16a34a",
            command=self.set_roasting_mode,
        )
        self.roasting_mode_card.grid(
            row=0,
            column=0,
            padx=10,
            sticky="ew",
        )

        self.packaging_mode_card = self.create_mode_card(
            parent=self.mode_cards_frame,
            title="Packaging Tests",
            subtitle="O2, package weight, BUB, package color",
            normal_bg="#eff6ff",
            hover_bg="#dbeafe",
            selected_bg="#bfdbfe",
            accent_color="#2563eb",
            command=self.set_packaging_mode,
        )
        self.packaging_mode_card.grid(
            row=0,
            column=1,
            padx=10,
            sticky="ew",
        )

        self.mode_status_label = tk.Label(
            self.mode_frame,
            textvariable=self.mode_status_text,
            font=("Segoe UI", 12, "bold"),
            bg="#f4f6f8",
            fg="#374151",
        )
        self.mode_status_label.grid(
            row=2,
            column=0,
            columnspan=2,
            pady=(10, 0),
        )

    def create_mode_card(
        self,
        parent,
        title: str,
        subtitle: str,
        normal_bg: str,
        hover_bg: str,
        selected_bg: str,
        accent_color: str,
        command,
    ):
        card = tk.Frame(
            parent,
            bg=normal_bg,
            bd=1,
            relief="solid",
            highlightthickness=3,
            highlightbackground="#d1d5db",
            highlightcolor=accent_color,
            cursor="hand2",
            padx=18,
            pady=14,
            width=310,
            height=96,
        )
        card.pack_propagate(False)

        title_label = tk.Label(
            card,
            text=title,
            font=("Segoe UI", 15, "bold"),
            bg=normal_bg,
            fg="#111827",
            cursor="hand2",
            justify="center",
            anchor="center",
        )
        title_label.pack(
            anchor="center",
            fill="x",
        )

        subtitle_label = tk.Label(
            card,
            text=subtitle,
            font=("Segoe UI", 10),
            bg=normal_bg,
            fg="#4b5563",
            cursor="hand2",
            justify="center",
            anchor="center",
        )
        subtitle_label.pack(
            anchor="center",
            fill="x",
            pady=(6, 0),
        )

        card.mode_title = title
        card.mode_normal_bg = normal_bg
        card.mode_hover_bg = hover_bg
        card.mode_selected_bg = selected_bg
        card.mode_accent_color = accent_color
        card.mode_children = [
            title_label,
            subtitle_label,
        ]

        def set_background(color):
            card.configure(bg=color)

            for child in card.mode_children:
                child.configure(bg=color)

        def on_enter(event):
            current_mode = None

            if self.app_state is not None:
                current_mode = self.app_state.get_mode()

            is_selected = (
                title == "Roasting Tests"
                and current_mode == "roasting"
            ) or (
                title == "Packaging Tests"
                and current_mode == "packaging"
            )

            if not is_selected:
                set_background(hover_bg)

        def on_leave(event):
            self.refresh_mode_cards()

        def on_click(event):
            command()

        for widget in [
            card,
            title_label,
            subtitle_label,
        ]:
            widget.bind("<Enter>", on_enter)
            widget.bind("<Leave>", on_leave)
            widget.bind("<Button-1>", on_click)

        return card

    def refresh_mode_cards(self) -> None:
        current_mode = None

        if self.app_state is not None:
            current_mode = self.app_state.get_mode()

        mode_cards = [
            (
                self.roasting_mode_card,
                "roasting",
            ),
            (
                self.packaging_mode_card,
                "packaging",
            ),
        ]

        for card, mode_name in mode_cards:
            if current_mode == mode_name:
                background = card.mode_selected_bg
                border_color = card.mode_accent_color
            else:
                background = card.mode_normal_bg
                border_color = "#d1d5db"

            card.configure(
                bg=background,
                highlightbackground=border_color,
            )

            for child in card.mode_children:
                child.configure(bg=background)

    def _build_status_cards(self) -> None:
        cards_frame = tk.Frame(
            self.root,
            background="#e5e7eb",
            padx=12,
            pady=12,
        )
        cards_frame.grid(
            row=2,
            column=0,
            sticky="ew",
        )
        cards_frame.columnconfigure(
            0,
            weight=1,
            uniform="cards",
        )
        cards_frame.columnconfigure(
            1,
            weight=1,
            uniform="cards",
        )
        cards_frame.columnconfigure(
            2,
            weight=1,
            uniform="cards",
        )

        self._build_card(
            parent=cards_frame,
            column=0,
            title="Workbook",
            value_variable=self.excel_status_text,
        )

        self._build_card(
            parent=cards_frame,
            column=1,
            title="Devices",
            value_variable=self.device_count_text,
        )

        self._build_static_card(
            parent=cards_frame,
            column=2,
            title="Instruction",
            value="Keep this window and the QA Excel sheet open while testing",
        )

    def _build_card(
        self,
        parent,
        column: int,
        title: str,
        value_variable: tk.StringVar,
    ) -> None:
        card = ttk.Frame(
            parent,
            padding=12,
            style="Card.TFrame",
        )
        card.grid(
            row=0,
            column=column,
            sticky="ew",
            padx=6,
        )

        ttk.Label(
            card,
            text=title,
            style="CardTitle.TLabel",
        ).pack(anchor="w")

        ttk.Label(
            card,
            textvariable=value_variable,
            style="CardValue.TLabel",
        ).pack(
            anchor="w",
            pady=(4, 0),
        )

    def _build_static_card(
        self,
        parent,
        column: int,
        title: str,
        value: str,
    ) -> None:
        card = ttk.Frame(
            parent,
            padding=12,
            style="Card.TFrame",
        )
        card.grid(
            row=0,
            column=column,
            sticky="ew",
            padx=6,
        )

        ttk.Label(
            card,
            text=title,
            style="CardTitle.TLabel",
        ).pack(anchor="w")

        ttk.Label(
            card,
            text=value,
            style="CardValue.TLabel",
        ).pack(
            anchor="w",
            pady=(4, 0),
        )

    def _build_logger_content(self) -> None:
        self.content_frame = tk.Frame(
            self.root,
            background="#e5e7eb",
            padx=12,
            pady=0,
        )
        self.content_frame.grid(
            row=3,
            column=0,
            sticky="nsew",
        )
        self.content_frame.columnconfigure(0, weight=1)
        self.content_frame.rowconfigure(1, weight=1)

        device_label = ttk.Label(
            self.content_frame,
            text="Device Status",
            style="SectionTitle.TLabel",
            background="#e5e7eb",
        )
        device_label.grid(
            row=0,
            column=0,
            sticky="w",
            pady=(0, 6),
        )

        self.device_table = ttk.Treeview(
            self.content_frame,
            columns=(
                "indicator",
                "port",
                "status",
                "last_message",
            ),
            show="headings",
            height=6,
            selectmode="none",
            takefocus=False,
        )

        self.device_table.heading(
            "indicator",
            text="",
            anchor="center",
        )
        self.device_table.heading(
            "port",
            text="Port",
            anchor="center",
        )
        self.device_table.heading(
            "status",
            text="Status",
            anchor="center",
        )
        self.device_table.heading(
            "last_message",
            text="Last Message",
            anchor="center",
        )

        self.device_table.column(
            "indicator",
            width=55,
            anchor="center",
            stretch=False,
        )
        self.device_table.column(
            "port",
            width=130,
            anchor="center",
            stretch=False,
        )
        self.device_table.column(
            "status",
            width=180,
            anchor="center",
            stretch=False,
        )
        self.device_table.column(
            "last_message",
            width=680,
            anchor="center",
        )

        self.device_table.grid(
            row=1,
            column=0,
            sticky="nsew",
        )

        self.device_table.bind(
            "<ButtonRelease-1>",
            lambda event: self.device_table.selection_remove(
                self.device_table.selection()
            ),
        )

        self.device_table.tag_configure(
            "connected",
            foreground="#16a34a",
        )
        self.device_table.tag_configure(
            "connecting",
            foreground="#f59e0b",
        )
        self.device_table.tag_configure(
            "disconnected",
            foreground="#dc2626",
        )
        self.device_table.tag_configure(
            "received",
            foreground="#2563eb",
        )
        self.device_table.tag_configure(
            "unrecognized",
            foreground="#ea580c",
        )

        activity_label = ttk.Label(
            self.content_frame,
            text="Activity",
            style="SectionTitle.TLabel",
            background="#e5e7eb",
        )
        activity_label.grid(
            row=2,
            column=0,
            sticky="w",
            pady=(14, 6),
        )

        activity_frame = tk.Frame(
            self.content_frame,
            background="white",
            bd=1,
            relief="solid",
        )
        activity_frame.grid(
            row=3,
            column=0,
            sticky="nsew",
        )
        self.content_frame.rowconfigure(
            3,
            weight=2,
        )

        self.activity_canvas = tk.Canvas(
            activity_frame,
            background="white",
            highlightthickness=0,
        )

        self.activity_scrollbar = ttk.Scrollbar(
            activity_frame,
            orient="vertical",
            command=self.activity_canvas.yview,
        )

        self.activity_list_frame = tk.Frame(
            self.activity_canvas,
            background="white",
        )

        self.activity_list_frame.bind(
            "<Configure>",
            lambda event: self.activity_canvas.configure(
                scrollregion=self.activity_canvas.bbox("all")
            ),
        )

        self.activity_canvas.create_window(
            (
                0,
                0,
            ),
            window=self.activity_list_frame,
            anchor="nw",
        )

        self.activity_canvas.configure(
            yscrollcommand=self.activity_scrollbar.set
        )

        self.activity_canvas.pack(
            side=tk.LEFT,
            fill=tk.BOTH,
            expand=True,
        )

        self.activity_scrollbar.pack(
            side=tk.RIGHT,
            fill=tk.Y,
        )

        self.activity_canvas.bind(
            "<MouseWheel>",
            self._on_activity_mousewheel,
        )

        self.activity_list_frame.bind(
            "<MouseWheel>",
            self._on_activity_mousewheel,
        )

    def _build_bottom_buttons(self) -> None:
        self.button_frame = tk.Frame(
            self.root,
            background="#e5e7eb",
            padx=12,
            pady=12,
        )
        self.button_frame.grid(
            row=4,
            column=0,
            sticky="ew",
        )
        self.button_frame.columnconfigure(
            0,
            weight=1,
        )

        clear_button = ttk.Button(
            self.button_frame,
            text="Clear Messages",
            command=self.clear_messages,
        )
        clear_button.grid(
            row=0,
            column=0,
            sticky="w",
            padx=(0, 8),
        )

        logs_button = ttk.Button(
            self.button_frame,
            text="Open Logs Folder",
            command=self.open_logs_folder,
        )
        logs_button.grid(
            row=0,
            column=1,
            sticky="w",
            padx=(0, 8),
        )

        troubleshooting_button = ttk.Button(
            self.button_frame,
            text="Troubleshooting",
            command=self.show_troubleshooting_guide,
        )
        troubleshooting_button.grid(
            row=0,
            column=2,
            sticky="w",
            padx=(0, 8),
        )

        stop_button = ttk.Button(
            self.button_frame,
            text="Stop Logger",
            command=self.stop_logger,
        )
        stop_button.grid(
            row=0,
            column=3,
            sticky="e",
        )

    def get_troubleshooting_content(self) -> str:
        return """1. Device is connected but nothing appears in the app

What to check:
- Make sure the USB/serial cable is fully plugged in.
- Make sure no other software is currently connected to the same device.
- Only one program can listen to a COM port at a time.
- Unplug the device and plug it back in.
- Wait a few seconds for the app to reconnect.


2. Barcode scans but the app does not recognize it

What to check:
- Make sure the scanner is connected before starting the test.
- The barcode should look like this:
  BT000095489-BLA-54
- If the app says the format is not recognized, the barcode format may be wrong.
- Scan the barcode again and make sure the scanner beeps successfully.


3. App says “NOT SAVED: Select Roasting Tests or Packaging Tests first”

What it means:
- A device sent data before a mode was selected.

How to fix:
- Click Roasting Tests or Packaging Tests.
- Then scan/run the test again.


4. App says “No active roasting sample selected”

What it means:
- A machine result came in before a sample barcode was scanned.

How to fix:
- Select Roasting Tests.
- Scan the sample barcode first.
- Then run the moisture/density test again.


5. Result went to the wrong row

What to check:
- Confirm the correct sample barcode was scanned immediately before the test.
- If multiple people are testing at the same time, the most recently scanned barcode becomes the active sample.
- Scan the correct barcode again before running the test.


6. Excel does not update

What to check:
- Make sure the QA Excel workbook is not opened manually before starting the app.
- Close Excel completely.
- Restart QA Logger and let the app open the workbook.
- Make sure the workbook is not in Protected View.
- Make sure the workbook path in config.json is correct.


7. App says Excel update error

What to check:
- Excel may be busy, locked, or waiting for a popup.
- Look for hidden Excel dialogs.
- Save and close Excel.
- Restart the app.
- If the issue continues, open the logs folder and check the latest log file.


8. Device disconnected

What to check:
- Cable may have been unplugged or the USB adapter reset.
- Reconnect the device.
- Wait a few seconds.
- If it does not reconnect, restart the app.


9. Wrong mode selected

Examples:
- Roasting Tests selected, but a packaging/O2 test is sent.
- Packaging Tests selected, but a roasting moisture/density test is sent.

How to fix:
- Select the correct mode.
- Repeat the scan or test.


10. App freezes or closes unexpectedly

What to do:
- Restart the app.
- Open the logs folder.
- Check crash_error.log if it exists.
- Send the latest log file to whoever supports the QA Logger.


11. Best normal workflow for roasting

Steps:
1. Open QA Logger.
2. Select Roasting Tests.
3. Scan the sample barcode.
4. Confirm the app says the sample was selected or created.
5. Run the moisture/density test.
6. Confirm the app says the result was saved.
7. Check Excel if needed.


12. Best normal workflow for packaging

Steps:
1. Open QA Logger.
2. Select Packaging Tests.
3. Follow the packaging test process.
4. Confirm the app says the result was received or saved.

Note:
Packaging Excel writing may still be under development depending on the current version.
"""

    def show_troubleshooting_guide(self) -> None:
        if self.troubleshooting_frame is not None:
            return

        self.content_frame.grid_remove()
        self.button_frame.grid_remove()

        self.troubleshooting_frame = tk.Frame(
            self.root,
            background="#e5e7eb",
            padx=20,
            pady=16,
        )
        self.troubleshooting_frame.grid(
            row=3,
            column=0,
            sticky="nsew",
        )
        self.troubleshooting_frame.columnconfigure(
            0,
            weight=1,
        )
        self.troubleshooting_frame.rowconfigure(
            2,
            weight=1,
        )

        title_label = tk.Label(
            self.troubleshooting_frame,
            text="QA Logger Troubleshooting Guide",
            font=("Segoe UI", 18, "bold"),
            bg="#e5e7eb",
            fg="#111827",
        )
        title_label.grid(
            row=0,
            column=0,
            sticky="w",
            pady=(0, 6),
        )

        subtitle_label = tk.Label(
            self.troubleshooting_frame,
            text="Common issues and what to check before calling for support.",
            font=("Segoe UI", 10),
            bg="#e5e7eb",
            fg="#4b5563",
        )
        subtitle_label.grid(
            row=1,
            column=0,
            sticky="w",
            pady=(0, 12),
        )

        text_frame = tk.Frame(
            self.troubleshooting_frame,
            bg="#e5e7eb",
        )
        text_frame.grid(
            row=2,
            column=0,
            sticky="nsew",
        )
        text_frame.columnconfigure(
            0,
            weight=1,
        )
        text_frame.rowconfigure(
            0,
            weight=1,
        )

        scrollbar = ttk.Scrollbar(
            text_frame,
            orient="vertical",
        )

        guide_text = tk.Text(
            text_frame,
            wrap="word",
            yscrollcommand=scrollbar.set,
            font=("Segoe UI", 10),
            bg="white",
            fg="#111827",
            relief="solid",
            bd=1,
            padx=14,
            pady=12,
        )

        scrollbar.configure(
            command=guide_text.yview
        )

        guide_text.grid(
            row=0,
            column=0,
            sticky="nsew",
        )

        scrollbar.grid(
            row=0,
            column=1,
            sticky="ns",
        )

        guide_text.insert(
            "1.0",
            self.get_troubleshooting_content(),
        )

        guide_text.configure(
            state="disabled"
        )

        back_button = ttk.Button(
            self.troubleshooting_frame,
            text="Back to Logger",
            command=self.show_logger_view,
        )
        back_button.grid(
            row=3,
            column=0,
            sticky="e",
            pady=(12, 0),
        )

    def show_logger_view(self) -> None:
        if self.troubleshooting_frame is not None:
            self.troubleshooting_frame.destroy()
            self.troubleshooting_frame = None

        self.content_frame.grid()
        self.button_frame.grid()

    def add_message(
        self,
        message: str,
        status_type: str | None = None,
    ) -> None:
        if status_type is None:
            status_type = self.get_message_type(message)

        self.add_activity_row(
            message=message,
            status_type=status_type,
        )

        self.update_status_from_message(message)

    def get_message_type(
        self,
        message: str,
    ) -> str:
        if (
            "Connected and waiting" in message
            or "Saved to Excel" in message
            or "QA Logger started" in message
            or "Excel workbook opened" in message
            or "Mode selected:" in message
            or "Roasting sample selected" in message
            or "New roasting sample created" in message
            or "Moisture/density saved" in message
        ):
            return "success"

        if (
            "Connecting" in message
            or "Monitoring connected" in message
            or "Stopping" in message
            or "Duplicate batch" in message
        ):
            return "warning"

        if (
            "Device disconnected" in message
            or message.startswith("ERROR:")
            or message.startswith("CRASH:")
            or message.startswith("NOT SAVED:")
            or "Excel update error" in message
            or "cancelled. Result was not saved" in message
            or "timed out. Result was not saved" in message
        ):
            return "error"

        if (
            "Received:" in message
            or "Input received" in message
        ):
            return "info"

        return "neutral"

    def get_status_dot(
        self,
        status_type: str,
    ) -> tuple[str, str]:
        if status_type == "success":
            return (
                "●",
                "#16a34a",
            )

        if status_type == "warning":
            return (
                "●",
                "#f59e0b",
            )

        if status_type == "error":
            return (
                "●",
                "#dc2626",
            )

        if status_type == "info":
            return (
                "●",
                "#2563eb",
            )

        return (
            "",
            "#111827",
        )

    def bind_activity_mousewheel(
        self,
        widget,
    ) -> None:
        widget.bind(
            "<MouseWheel>",
            self._on_activity_mousewheel,
        )

    def add_activity_row(
        self,
        message: str,
        status_type: str,
    ) -> None:
        dot_text, dot_color = self.get_status_dot(status_type)

        row = tk.Frame(
            self.activity_list_frame,
            background="white",
            padx=8,
            pady=4,
        )
        row.pack(
            fill=tk.X,
            anchor="w",
        )
        self.bind_activity_mousewheel(row)

        if dot_text:
            dot = tk.Label(
                row,
                text=dot_text,
                foreground=dot_color,
                background="white",
                font=("Segoe UI", 13, "bold"),
                width=2,
            )
            dot.pack(
                side=tk.LEFT,
                anchor="n",
            )
            self.bind_activity_mousewheel(dot)
        else:
            spacer = tk.Label(
                row,
                text="",
                background="white",
                width=2,
            )
            spacer.pack(
                side=tk.LEFT,
                anchor="n",
            )
            self.bind_activity_mousewheel(spacer)

        label = tk.Label(
            row,
            text=message,
            background="white",
            foreground="#111827",
            font=("Consolas", 10),
            justify="left",
            anchor="w",
            wraplength=930,
        )
        label.pack(
            side=tk.LEFT,
            fill=tk.X,
            expand=True,
        )
        self.bind_activity_mousewheel(label)

        self.activity_canvas.update_idletasks()
        self.activity_canvas.yview_moveto(1.0)

    def _on_activity_mousewheel(
        self,
        event,
    ) -> None:
        scroll_region = self.activity_canvas.bbox("all")

        if scroll_region is None:
            return

        content_height = scroll_region[3] - scroll_region[1]
        visible_height = self.activity_canvas.winfo_height()

        if content_height <= visible_height:
            self.activity_canvas.yview_moveto(0)
            return

        self.activity_canvas.yview_scroll(
            int(-1 * (event.delta / 120)),
            "units",
        )

    def update_status_from_message(
        self,
        message: str,
    ) -> None:
        if "Excel workbook opened:" in message:
            self.excel_status_text.set("Excel: Open")

        if message.startswith("ERROR:"):
            self.status_text.set("Error")
            self.style.configure(
                "HeaderStatus.TLabel",
                background="#1f2937",
                foreground="#fecaca",
                font=("Segoe UI", 11, "bold"),
            )

        if message.startswith("CRASH:"):
            self.status_text.set("Crashed")
            self.style.configure(
                "HeaderStatus.TLabel",
                background="#1f2937",
                foreground="#fecaca",
                font=("Segoe UI", 11, "bold"),
            )

        port = self.extract_port(message)

        if port is None:
            return

        if "Connected and waiting" in message:
            self.connected_ports.add(port)
            self.set_device_row(
                port=port,
                status="Connected",
                last_message="Waiting for readings",
                status_type="connected",
            )

        elif "Connecting" in message:
            self.set_device_row(
                port=port,
                status="Connecting",
                last_message="Connecting to device",
                status_type="connecting",
            )

        elif "Device disconnected" in message:
            self.connected_ports.discard(port)
            self.set_device_row(
                port=port,
                status="Disconnected",
                last_message="Device disconnected",
                status_type="disconnected",
            )

        elif (
            "Saved to Excel:" in message
            or "Roasting sample selected" in message
            or "New roasting sample created" in message
            or "Moisture/density saved" in message
        ):
            self.set_device_row(
                port=port,
                status="Connected",
                last_message="Saved successfully",
                status_type="connected",
            )

        elif "Received:" in message:
            self.set_device_row(
                port=port,
                status="Connected",
                last_message="Received input",
                status_type="received",
            )

            self.root.after(
                1500,
                lambda port=port: self.set_device_row(
                    port=port,
                    status="Connected",
                    last_message="Waiting for readings",
                    status_type="connected",
                ),
            )

        elif "Input received, but the format is not recognized" in message:
            self.set_device_row(
                port=port,
                status="Unrecognized",
                last_message="Input format not recognized",
                status_type="unrecognized",
            )

        self.device_count_text.set(
            f"Connected Devices: {len(self.connected_ports)}"
        )

    def extract_port(
        self,
        message: str,
    ) -> str | None:
        if not message.startswith("COM"):
            return None

        first_part = message.split(":", 1)[0]

        if first_part.upper().startswith("COM"):
            return first_part

        return None

    def get_device_dot(
        self,
        status_type: str,
    ) -> str:
        if status_type in [
            "connected",
            "connecting",
            "disconnected",
            "received",
            "unrecognized",
        ]:
            return "●"

        return ""

    def set_device_row(
        self,
        port: str,
        status: str,
        last_message: str,
        status_type: str,
    ) -> None:
        existing_item = None

        for item_id in self.device_table.get_children():
            values = self.device_table.item(
                item_id,
                "values",
            )

            if values and values[1] == port:
                existing_item = item_id
                break

        row_values = (
            self.get_device_dot(status_type),
            port,
            status,
            last_message,
        )

        if existing_item is None:
            self.device_table.insert(
                "",
                tk.END,
                values=row_values,
                tags=(status_type,),
            )
        else:
            self.device_table.item(
                existing_item,
                values=row_values,
                tags=(status_type,),
            )

    def clear_messages(self) -> None:
        for child in self.activity_list_frame.winfo_children():
            child.destroy()

        self.activity_canvas.update_idletasks()
        self.activity_canvas.yview_moveto(0)

    def play_alert_sound(self) -> None:
        try:
            alert_pattern = [
                (
                    1200,
                    350,
                ),
                (
                    900,
                    250,
                ),
                (
                    1200,
                    350,
                ),
                (
                    900,
                    250,
                ),
                (
                    1200,
                    500,
                ),
            ]

            for frequency, duration in alert_pattern:
                winsound.Beep(
                    frequency,
                    duration,
                )

        except Exception:
            try:
                winsound.MessageBeep(winsound.MB_ICONHAND)
            except Exception:
                pass

    def check_duplicate_prompt_queue(self) -> None:
        if self.duplicate_prompt_queue is None:
            return

        while True:
            try:
                prompt_request = self.duplicate_prompt_queue.get_nowait()
            except queue.Empty:
                break

            self.play_alert_sound()

            self.root.lift()
            self.root.focus_force()
            self.root.attributes(
                "-topmost",
                True,
            )

            message = (
                f"Batch ticket {prompt_request['full_batch_ticket']} "
                f"already exists in {prompt_request['duplicate_sheet']}, "
                f"row {prompt_request['duplicate_row']}.\n\n"
                "This may be a retest.\n\n"
                "Do you want to save this result anyway?"
            )

            should_override = messagebox.askyesno(
                title="Duplicate Batch Ticket",
                message=message,
                parent=self.root,
            )

            self.root.attributes(
                "-topmost",
                False,
            )

            prompt_request["response_queue"].put(should_override)
            self.duplicate_prompt_queue.task_done()

    def open_logs_folder(self) -> None:
        try:
            os.startfile(LOG_DIR)
        except Exception as error:
            messagebox.showerror(
                "Open Logs Folder",
                f"Could not open logs folder:\n{error}",
            )

    def stop_logger(self) -> None:
        if self.stop_event.is_set():
            return

        self.status_text.set("Stopping...")
        self.add_message("Stopping QA Logger...")
        self.stop_event.set()

    def set_roasting_mode(self) -> None:
        if self.app_state is not None:
            current_mode = self.app_state.get_mode()

            if current_mode == "roasting":
                return

            self.app_state.set_mode("roasting")

        self.mode_status_text.set("Current Mode: Roasting Tests")
        self.refresh_mode_cards()

        self.add_message(
            "Mode selected: Roasting Tests",
            "success",
        )

    def set_packaging_mode(self) -> None:
        if self.app_state is not None:
            current_mode = self.app_state.get_mode()

            if current_mode == "packaging":
                return

            self.app_state.set_mode("packaging")

        self.mode_status_text.set("Current Mode: Packaging Tests")
        self.refresh_mode_cards()

        self.add_message(
            "Mode selected: Packaging Tests",
            "success",
        )

    def on_close(self) -> None:
        should_close = messagebox.askyesno(
            "Stop QA Logger",
            "Do you want to stop the QA Logger?",
        )

        if should_close:
            self.stop_logger()

    def check_ui_queue(self) -> None:
        while True:
            try:
                message = self.ui_queue.get_nowait()
            except queue.Empty:
                break

            self.add_message(message)
            self.ui_queue.task_done()

        self.check_duplicate_prompt_queue()

        if self.stop_event.is_set():
            self.status_text.set("Stopped")

            self.root.after(
                800,
                self.root.destroy,
            )

            return

        self.root.after(
            200,
            self.check_ui_queue,
        )

    def run(self) -> None:
        self.root.mainloop()