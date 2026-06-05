"""Bridge from Python ``logging`` to a Qt signal so records show in the GUI.

The :class:`~gui.logs_tab.LogsTab` installs a :class:`QtLogHandler` on a logger;
each record is formatted and re-emitted as a Qt signal. Records can originate on
worker threads (the translation engine runs off the GUI thread), and emitting a
Qt signal across threads is safe — Qt queues delivery onto the receiver's thread.
"""

from __future__ import annotations

import logging

from PySide6.QtCore import QObject, Signal


class _LogSignal(QObject):
    """Carrier for the per-record signal; lives on its creating thread."""

    emitted = Signal(int, str)  # (levelno, formatted message)


class QtLogHandler(logging.Handler):
    """A ``logging.Handler`` that forwards formatted records to a Qt signal.

    Multiple inheritance from ``QObject`` and ``logging.Handler`` triggers a
    metaclass clash, so the signal lives on a contained ``QObject`` instead.
    """

    def __init__(self, level: int = logging.NOTSET) -> None:
        super().__init__(level)
        self.signal = _LogSignal()

    @property
    def emitted(self) -> Signal:
        """The ``(levelno, message)`` signal slots connect to."""
        return self.signal.emitted

    def emit(self, record: logging.LogRecord) -> None:
        try:
            message = self.format(record)
        except Exception:  # pragma: no cover - mirrors logging's own contract
            self.handleError(record)
            return
        try:
            self.signal.emitted.emit(record.levelno, message)
        except RuntimeError:  # pragma: no cover - carrier already deleted
            pass
