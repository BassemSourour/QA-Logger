import threading


class AppState:
    def __init__(
        self,
    ) -> None:
        self._lock = threading.Lock()
        self._current_mode = None

    def set_mode(
        self,
        mode: str,
    ) -> None:
        if mode not in {
            "roasting",
            "packaging",
        }:
            raise ValueError(
                f"Invalid mode: {mode}"
            )

        with self._lock:
            self._current_mode = mode

    def get_mode(
        self,
    ) -> str | None:
        with self._lock:
            return self._current_mode

    def get_mode_label(
        self,
    ) -> str:
        mode = self.get_mode()

        if mode == "roasting":
            return "Roasting Tests"

        if mode == "packaging":
            return "Packaging Tests"

        return "No Mode Selected"