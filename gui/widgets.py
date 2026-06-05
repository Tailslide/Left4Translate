"""Small reusable presentational widgets shared across tabs."""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from gui.styles import status_dot_color


class StatCard(QFrame):
    """A rounded card showing a big value over a small uppercase label."""

    def __init__(self, label: str, value: str = "—", accent: bool = False,
                 parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("StatCard")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 14, 16, 14)
        lay.setSpacing(4)

        self._value = QLabel(value)
        self._value.setObjectName("StatValue")
        if accent:
            # Accent the number with the brand orange while keeping StatValue sizing.
            self._value.setStyleSheet("color: #e05a2b;")
        self._value.setTextInteractionFlags(Qt.TextSelectableByMouse)

        self._label = QLabel(label.upper())
        self._label.setObjectName("StatLabel")

        lay.addWidget(self._value)
        lay.addWidget(self._label)

    def set_value(self, value: str) -> None:
        self._value.setText(value)


class StatusPill(QLabel):
    """A colored ``● Label`` indicator used in the header strip.

    The dot color reflects a component state (running/connected/error/idle);
    the text shows the human-readable label.
    """

    def __init__(self, name: str, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("StatusPill")
        self._name = name
        self.set_state("idle", name)

    def set_state(self, state: str, text: Optional[str] = None) -> None:
        color = status_dot_color(state)
        label = text if text is not None else self._name
        self.setText(f'<span style="color:{color}">●</span> '
                     f'<span style="color:#8888a0">{label}</span>')


class StatusBank(QWidget):
    """A horizontal row of :class:`StatusPill`s keyed by component name."""

    def __init__(self, names: list[str], parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(16)
        self._pills: dict[str, StatusPill] = {}
        for name in names:
            pill = StatusPill(name.capitalize())
            self._pills[name] = pill
            row.addWidget(pill)

    def set_state(self, component: str, state: str, text: Optional[str] = None) -> None:
        pill = self._pills.get(component)
        if pill is not None:
            pill.set_state(state, text)
