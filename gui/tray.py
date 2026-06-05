"""System tray icon — quick actions; clicking the icon toggles the window."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import QMenu, QSystemTrayIcon


class TrayIcon(QSystemTrayIcon):
    """Tray icon for Left4Translate.

    Emits typed signals instead of holding a reference to the main window, so it
    can be unit-tested without booting the rest of the GUI.
    """

    show_window_requested = Signal()
    start_stop_requested = Signal()
    quit_requested = Signal()

    def __init__(self, icon: QIcon, parent=None, tooltip: str = "Left4Translate") -> None:
        super().__init__(icon, parent)
        self.setToolTip(tooltip)

        menu = QMenu()
        self._show_action = QAction("Show window", menu)
        self._show_action.triggered.connect(self.show_window_requested)
        menu.addAction(self._show_action)

        self._start_stop_action = QAction("Start translation", menu)
        self._start_stop_action.triggered.connect(self.start_stop_requested)
        menu.addAction(self._start_stop_action)

        menu.addSeparator()

        self._quit_action = QAction("Quit", menu)
        self._quit_action.triggered.connect(self.quit_requested)
        menu.addAction(self._quit_action)

        self.setContextMenu(menu)
        self.activated.connect(self._on_activated)

    def set_running(self, running: bool) -> None:
        """Flip the Start/Stop menu label to match the engine state."""
        self._start_stop_action.setText("Stop translation" if running else "Start translation")

    def _on_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.show_window_requested.emit()


def is_tray_available() -> bool:
    """Wrapper for QSystemTrayIcon.isSystemTrayAvailable() that's easy to mock."""
    return QSystemTrayIcon.isSystemTrayAvailable()
