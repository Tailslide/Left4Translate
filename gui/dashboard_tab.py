"""Dashboard tab — at-a-glance stats plus the live translation feed.

The feed mirrors what scrolls across the Turing Smart Screen: each chat or
voice translation appears as a row (newest on top), team-colored. The stat
cards summarise throughput and the translator cache occupancy, refreshed on a
timer from the engine controller.

The feed is a QTableView over a plain-Python model rather than a
QTableWidget. The widget variant allocates five C++ ``QTableWidgetItem``
objects per translation and has Qt destroy the oldest row's items natively
inside ``removeRow`` once the feed is full — exactly where long sessions
died with a native access violation (see logs/crash.log in the bug
reports: both faults were inside ``add_translation``'s row-trim call).
With a model, rows are tuples in a deque; inserting and trimming never
touches the C++ heap beyond repainting.
"""

from __future__ import annotations

import time
from collections import deque
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from PySide6.QtCore import (
    QAbstractTableModel,
    QEvent,
    QModelIndex,
    Qt,
    QTimer,
)
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from gui.engine_controller import EngineController
from gui.styles import TEXT_SECONDARY, VOICE_ACCENT, team_color
from gui.widgets import StatCard

_MAX_FEED_ROWS = 500

# Shared invalid index for rowCount/columnCount defaults (never mutated).
_ROOT_INDEX = QModelIndex()


class FeedModel(QAbstractTableModel):
    """Read-only model over the translation rows (newest first).

    Each row is ``(cells, accent)``: five display strings and the QColor for
    the Type/Player columns. Everything lives in Python; Qt only reads it.
    """

    HEADERS = ("Time", "Type", "Player", "Original", "Translated")

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._rows: deque[Tuple[List[str], QColor]] = deque()
        self._time_color = QColor(TEXT_SECONDARY)

    # ---- QAbstractTableModel interface ----------------------------------

    def rowCount(self, parent: QModelIndex = _ROOT_INDEX) -> int:  # noqa: N802
        return 0 if parent.isValid() else len(self._rows)

    def columnCount(self, parent: QModelIndex = _ROOT_INDEX) -> int:  # noqa: N802
        return 0 if parent.isValid() else len(self.HEADERS)

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):  # noqa: N802
        if (
            role == Qt.ItemDataRole.DisplayRole
            and orientation == Qt.Orientation.Horizontal
            and 0 <= section < len(self.HEADERS)
        ):
            return self.HEADERS[section]
        return None

    def data(self, index: QModelIndex, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or not (0 <= index.row() < len(self._rows)):
            return None
        cells, accent = self._rows[index.row()]
        col = index.column()
        if role in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.ToolTipRole):
            return cells[col]
        if role == Qt.ItemDataRole.ForegroundRole:
            if col == 0:
                return self._time_color
            if col in (1, 2):
                return accent
        return None

    # ---- Mutation (GUI thread only) --------------------------------------

    def prepend(self, cells: List[str], accent: QColor) -> None:
        """Insert a row at the top, trimming the oldest past the cap."""
        self.beginInsertRows(QModelIndex(), 0, 0)
        self._rows.appendleft((cells, accent))
        self.endInsertRows()
        if len(self._rows) > _MAX_FEED_ROWS:
            last = len(self._rows) - 1
            self.beginRemoveRows(QModelIndex(), last, last)
            self._rows.pop()
            self.endRemoveRows()

    def clear(self) -> None:
        self.beginResetModel()
        self._rows.clear()
        self.endResetModel()


class DashboardTab(QWidget):
    """Stat cards + the live translation feed table."""

    def __init__(self, controller: EngineController, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._controller = controller
        self._count = 0
        self._chars = 0
        self._recent = deque(maxlen=240)  # translation timestamps for rate calc
        self._started_at: Optional[float] = None

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(14)

        root.addLayout(self._build_cards())
        root.addLayout(self._build_feed_header())
        root.addWidget(self._build_feed(), stretch=1)

        # One timer drives the time-based cards (uptime, per-minute) and the
        # cache hit-rate poll. Cheap, so 1s cadence is plenty.
        self._timer = QTimer(self)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._refresh_timed_stats)
        self._timer.start()

    # ---- Construction ---------------------------------------------------

    def _build_cards(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(12)
        self._card_total = StatCard("Translated", "0", accent=True)
        self._card_rate = StatCard("Per Minute", "0.0")
        self._card_cache = StatCard("Cached", "—")
        self._card_chars = StatCard("Characters", "0")
        self._card_uptime = StatCard("Uptime", "00:00:00")
        for card in (self._card_total, self._card_rate, self._card_cache,
                     self._card_chars, self._card_uptime):
            row.addWidget(card)
        return row

    def _section_label(self, text: str) -> QLabel:
        label = QLabel(text.upper())
        label.setObjectName("SectionTitle")
        return label

    def _build_feed_header(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.addWidget(self._section_label("Live Translations"))
        row.addStretch(1)
        self._wrap_check = QCheckBox("Wrap long messages")
        self._wrap_check.setChecked(False)
        self._wrap_check.toggled.connect(self._on_wrap_toggled)
        row.addWidget(self._wrap_check)
        return row

    def _on_wrap_toggled(self, checked: bool) -> None:
        self._feed.setWordWrap(checked)
        if checked:
            self._feed.resizeRowsToContents()
        else:
            for r in range(self._model.rowCount()):
                self._feed.setRowHeight(r, self._feed.verticalHeader().defaultSectionSize())

    def _build_feed(self) -> QTableView:
        self._model = FeedModel(self)
        table = QTableView()
        table.setModel(self._model)
        table.verticalHeader().setVisible(False)
        table.setShowGrid(False)
        table.setAlternatingRowColors(True)
        table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        table.setWordWrap(False)

        header = table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        self._feed = table

        # Centered hint shown while the feed is empty.
        self._empty_hint = QLabel(
            "No translations yet.\nStart the engine and join a game — chat will appear here.",
            table,
        )
        self._empty_hint.setObjectName("EmptyHint")
        self._empty_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        table.installEventFilter(self)
        self._position_empty_hint()
        return table

    def eventFilter(self, obj, event):  # type: ignore[override]
        if obj is self._feed and event.type() == QEvent.Type.Resize:
            self._position_empty_hint()
        return super().eventFilter(obj, event)

    def _position_empty_hint(self) -> None:
        if self._empty_hint is not None:
            self._empty_hint.resize(self._feed.viewport().size())
            self._empty_hint.move(0, self._feed.horizontalHeader().height())

    def _update_empty_hint(self) -> None:
        self._empty_hint.setVisible(self._model.rowCount() == 0)

    # ---- Public slots ---------------------------------------------------

    def add_translation(self, payload: Dict[str, Any]) -> None:
        """Insert a translation at the top of the feed and update counters."""
        kind = payload.get("kind", "chat")
        player = str(payload.get("player") or "—")
        original = str(payload.get("original") or "")
        translated = str(payload.get("translated") or "")
        team = payload.get("team")

        self._count += 1
        self._chars += len(original)
        self._recent.append(time.monotonic())

        now = datetime.now().strftime("%H:%M:%S")
        type_label = "Voice" if kind == "voice" else (team or "Chat")
        if kind == "voice":
            color = QColor(VOICE_ACCENT)
        else:
            color = QColor(team_color(team))

        self._model.prepend([now, type_label, player, original, translated], color)
        if self._wrap_check.isChecked():
            self._feed.resizeRowToContents(0)
        self._update_empty_hint()

        self._card_total.set_value(f"{self._count:,}")
        self._card_chars.set_value(f"{self._chars:,}")

    def set_running(self, running: bool) -> None:
        """Track engine run state to drive the uptime clock and rate window."""
        if running:
            self._started_at = time.monotonic()
        else:
            self._started_at = None
            self._recent.clear()
            self._card_rate.set_value("0.0")
            self._card_uptime.set_value("00:00:00")

    def reset(self) -> None:
        """Clear counters and the feed (e.g. on a fresh start)."""
        self._count = 0
        self._chars = 0
        self._recent.clear()
        self._model.clear()
        self._update_empty_hint()
        self._card_total.set_value("0")
        self._card_chars.set_value("0")
        self._card_cache.set_value("—")

    # ---- Timer ----------------------------------------------------------

    def _refresh_timed_stats(self) -> None:
        # Per-minute rate over the trailing 60s window.
        cutoff = time.monotonic() - 60.0
        while self._recent and self._recent[0] < cutoff:
            self._recent.popleft()
        self._card_rate.set_value(f"{len(self._recent):.1f}")

        # Uptime.
        if self._started_at is not None:
            elapsed = int(time.monotonic() - self._started_at)
            h, rem = divmod(elapsed, 3600)
            m, s = divmod(rem, 60)
            self._card_uptime.set_value(f"{h:02d}:{m:02d}:{s:02d}")

        # Translation cache occupancy (entries currently cached / capacity).
        stats = self._controller.cache_stats()
        currsize = stats.get("currsize", stats.get("size"))
        maxsize = stats.get("maxsize")
        if currsize is not None:
            self._card_cache.set_value(
                f"{currsize:,} / {maxsize:,}" if maxsize else f"{currsize:,}"
            )
