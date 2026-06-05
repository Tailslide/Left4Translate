"""Logs tab — a live, scrolling view of the application's console output.

Installs a :class:`~gui.log_handler.QtLogHandler` on the root logger so any
module that logs via the stdlib ``logging`` package shows up here (the engine,
the reader's watchdog thread, the voice manager's worker threads, etc.), and
tees ``stdout`` / ``stderr`` so raw ``print`` output and noisy libraries are
captured too.
"""

from __future__ import annotations

import logging
import sys
from html import escape
from typing import Optional, TextIO

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from gui.log_handler import QtLogHandler
from gui.stream_capture import StreamTee

# (label, threshold) pairs for the level filter dropdown.
_LEVELS: list[tuple[str, int]] = [
    ("All", logging.NOTSET),
    ("Debug", logging.DEBUG),
    ("Info", logging.INFO),
    ("Warning", logging.WARNING),
    ("Error", logging.ERROR),
]

# Mirrors gui.styles tokens so colors stay consistent with the rest of the app.
_LEVEL_COLOR = {
    logging.DEBUG: "#8888a0",
    logging.INFO: "#e8e8ec",
    logging.WARNING: "#d4a339",
    logging.ERROR: "#e05252",
    logging.CRITICAL: "#e05252",
}


class LogsTab(QWidget):
    """Shows log records routed through :class:`QtLogHandler` plus stdout/stderr."""

    MAX_LINES = 5000

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._min_level = logging.NOTSET
        self._handler: Optional[QtLogHandler] = None
        self._attached_logger: Optional[logging.Logger] = None
        self._stdout_tee: Optional[StreamTee] = None
        self._stderr_tee: Optional[StreamTee] = None
        self._saved_stdout: Optional[TextIO] = None
        self._saved_stderr: Optional[TextIO] = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._build_header())
        layout.addWidget(self._build_view(), stretch=1)

    # ---- UI ----------------------------------------------------------------

    def _build_header(self) -> QWidget:
        bar = QWidget()
        bar.setObjectName("HeaderBar")
        row = QHBoxLayout(bar)
        row.setContentsMargins(14, 8, 14, 8)
        row.setSpacing(10)

        row.addWidget(QLabel("Level"))
        self.level_combo = QComboBox()
        for label, _ in _LEVELS:
            self.level_combo.addItem(label)
        self.level_combo.setCurrentIndex(0)
        self.level_combo.currentIndexChanged.connect(self._on_level_changed)
        row.addWidget(self.level_combo)

        row.addStretch(1)

        self.autoscroll_check = QCheckBox("Auto-scroll")
        self.autoscroll_check.setChecked(True)
        row.addWidget(self.autoscroll_check)

        self.clear_button = QPushButton("Clear")
        self.clear_button.clicked.connect(self.clear)
        row.addWidget(self.clear_button)
        return bar

    def _build_view(self) -> QPlainTextEdit:
        self.view = QPlainTextEdit()
        self.view.setReadOnly(True)
        self.view.setMaximumBlockCount(self.MAX_LINES)
        self.view.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        font = self.view.font()
        font.setStyleHint(font.styleHint().Monospace)
        font.setFamily("Consolas")
        self.view.setFont(font)
        return self.view

    # ---- Logging integration ----------------------------------------------

    def attach(self, logger_name: Optional[str] = None, level: int = logging.INFO) -> None:
        """Install the Qt log handler on ``logger_name`` (root if ``None``).

        Idempotent per logger: any handler we previously added is removed first,
        so building a window repeatedly (e.g. in tests) can't stack handlers.
        """
        logger = logging.getLogger(logger_name)
        for existing in list(logger.handlers):
            if isinstance(existing, QtLogHandler):
                logger.removeHandler(existing)
        if logger.level == logging.NOTSET or logger.level > level:
            logger.setLevel(level)

        handler = QtLogHandler()
        handler.setFormatter(
            logging.Formatter("%(asctime)s  %(levelname)-7s %(name)s: %(message)s", datefmt="%H:%M:%S")
        )
        handler.emitted.connect(self._on_record)
        logger.addHandler(handler)
        self._handler = handler
        self._attached_logger = logger

    def detach(self) -> None:
        """Remove the handler so the tab stops receiving records."""
        if self._handler is not None and self._attached_logger is not None:
            self._attached_logger.removeHandler(self._handler)
        self._handler = None
        self._attached_logger = None

    # ---- Stream capture ----------------------------------------------------

    def capture_streams(self) -> None:
        """Tee ``sys.stdout`` / ``sys.stderr`` into the view (idempotent)."""
        if self._stdout_tee is not None:
            return
        self._saved_stdout = sys.stdout
        self._saved_stderr = sys.stderr
        self._stdout_tee = StreamTee(sys.stdout, self)
        self._stderr_tee = StreamTee(sys.stderr, self)
        self._stdout_tee.line_written.connect(self._on_stdout_line)
        self._stderr_tee.line_written.connect(self._on_stderr_line)
        sys.stdout = self._stdout_tee
        sys.stderr = self._stderr_tee

    def release_streams(self) -> None:
        """Restore the original streams. Idempotent and safe to call on close."""
        if self._stdout_tee is not None and sys.stdout is self._stdout_tee:
            sys.stdout = self._saved_stdout
        if self._stderr_tee is not None and sys.stderr is self._stderr_tee:
            sys.stderr = self._saved_stderr
        self._stdout_tee = None
        self._stderr_tee = None
        self._saved_stdout = None
        self._saved_stderr = None

    # ---- Slots -------------------------------------------------------------

    def _on_record(self, levelno: int, message: str) -> None:
        self._append(levelno, message)

    def _on_stdout_line(self, line: str) -> None:
        if line.strip():
            self._append(logging.INFO, line)

    def _on_stderr_line(self, line: str) -> None:
        if line.strip():
            self._append(logging.ERROR, line)

    def _append(self, levelno: int, message: str) -> None:
        if levelno < self._min_level:
            return
        color = _LEVEL_COLOR.get(levelno, _LEVEL_COLOR[logging.INFO])
        self.view.appendHtml(
            f'<span style="color:{color}; white-space:pre">{escape(message)}</span>'
        )
        if self.autoscroll_check.isChecked():
            bar = self.view.verticalScrollBar()
            bar.setValue(bar.maximum())

    def _on_level_changed(self, index: int) -> None:
        self._min_level = _LEVELS[index][1]

    # ---- Public helpers ----------------------------------------------------

    def clear(self) -> None:
        self.view.clear()
