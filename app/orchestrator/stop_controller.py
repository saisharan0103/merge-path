class StopController:
    """In-process stop switch for local runs."""

    def __init__(self) -> None:
        self._stop_requested = False

    @property
    def stop_requested(self) -> bool:
        return self._stop_requested

    def request_stop(self) -> None:
        self._stop_requested = True

    def clear_stop(self) -> None:
        self._stop_requested = False
