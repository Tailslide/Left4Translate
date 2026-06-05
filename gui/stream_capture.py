"""Tee ``sys.stdout`` / ``sys.stderr`` into the GUI while preserving the console.

Used only by the desktop GUI entry point so that *all* console output — raw
``print`` calls and chatty third-party libraries included — surfaces in the
Logs tab. The original stream is always written to as well, so nothing is lost
and the CLI (which never installs this) behaves exactly as before.
"""

from __future__ import annotations

import threading
from typing import Optional, TextIO

from PySide6.QtCore import QObject, Signal


class StreamTee(QObject):
    """A file-like object forwarding writes to the original stream and a signal.

    Output is emitted one complete line at a time: text is buffered until a
    newline so the Logs tab shows whole lines rather than partial fragments.
    Writes may arrive from worker threads, so a lock guards the buffer and the
    cross-thread ``line_written`` signal is delivered on the GUI thread by Qt.
    """

    line_written = Signal(str)

    def __init__(self, original: Optional[TextIO], parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._original = original
        self._buffer = ""
        self._lock = threading.Lock()

    @property
    def original(self) -> Optional[TextIO]:
        return self._original

    def write(self, text: str) -> int:
        if self._original is not None:
            try:
                self._original.write(text)
            except Exception:
                pass
        lines: list[str] = []
        with self._lock:
            self._buffer += text
            while "\n" in self._buffer:
                line, self._buffer = self._buffer.split("\n", 1)
                lines.append(line)
        for line in lines:
            self.line_written.emit(line)
        return len(text)

    def flush(self) -> None:
        if self._original is not None:
            try:
                self._original.flush()
            except Exception:
                pass

    def isatty(self) -> bool:
        getter = getattr(self._original, "isatty", None)
        return bool(getter()) if callable(getter) else False

    def fileno(self) -> int:
        if self._original is None or not hasattr(self._original, "fileno"):
            raise OSError("StreamTee has no underlying file descriptor")
        return self._original.fileno()
