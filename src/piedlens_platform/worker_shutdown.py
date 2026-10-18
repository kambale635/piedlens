import signal
from threading import Event


class GracefulShutdown:
    """Request cooperative worker shutdown between complete processing batches."""

    def __init__(self) -> None:
        self._stop_event = Event()
        self._previous_handlers = {}

    def __enter__(self):
        """Install SIGTERM/SIGINT handlers and remember the process defaults."""
        for signum in (signal.SIGTERM, signal.SIGINT):
            self._previous_handlers[signum] = signal.signal(signum, self._request_stop)
        return self

    def __exit__(self, exception_type, exception, traceback):
        """Restore handlers after the worker exits."""
        for signum, handler in self._previous_handlers.items():
            signal.signal(signum, handler)
        self._previous_handlers.clear()
        return False

    @property
    def stop_requested(self) -> bool:
        """Return whether an operating-system shutdown signal was received."""
        return self._stop_event.is_set()

    def wait(self, timeout: float) -> bool:
        """Wait interruptibly between batches; return true when shutdown is requested."""
        return self._stop_event.wait(timeout)

    def _request_stop(self, signum, frame) -> None:
        self._stop_event.set()
