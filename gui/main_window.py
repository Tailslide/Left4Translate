"""Main window: header controls, tabbed UI, tray icon, and engine wiring."""

from __future__ import annotations

import logging
from typing import Optional

from PySide6.QtCore import QTimer
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QStatusBar,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from gui.dashboard_tab import DashboardTab
from gui.engine_controller import EngineController
from gui.logs_tab import LogsTab
from gui.overlay_window import OverlayWindow
from gui.settings_store import MODES, SettingsStore
from gui.settings_tab import SettingsTab
from gui.theme import apply_theme
from gui.tray import TrayIcon, is_tray_available
from gui.voice_tab import VoiceTab
from gui.widgets import NoScrollComboBox, StatusBank

_logger = logging.getLogger("left4translate.gui")

# Components shown as status pills in the header strip.
_STATUS_COMPONENTS = ["engine", "screen", "chat", "voice"]


class MainWindow(QMainWindow):
    """Top-level window for the Left4Translate desktop GUI."""

    def __init__(
        self,
        config_path: str,
        store: Optional[SettingsStore] = None,
        controller: Optional[EngineController] = None,
    ) -> None:
        super().__init__()
        self.setWindowTitle("Left4Translate")

        self._config_path = config_path
        self._store = store or SettingsStore()
        self._controller = controller or EngineController(config_path, parent=self)
        self._force_quit = False
        self._running = False
        self._restart_pending = False

        central = QWidget()
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._build_header())
        layout.addWidget(self._build_tabs(), stretch=1)
        self.setCentralWidget(central)

        self.setStatusBar(QStatusBar(self))
        self.statusBar().showMessage("Ready")

        self._overlay = OverlayWindow(self._store)

        self._tray = self._build_tray()
        self._restore_geometry()
        self._wire_signals()
        self._set_ui_running(False)
        self._restore_overlay()

    # ---- Construction ---------------------------------------------------

    def _build_header(self) -> QWidget:
        bar = QWidget()
        bar.setObjectName("HeaderBar")
        row = QHBoxLayout(bar)
        row.setContentsMargins(14, 10, 14, 10)
        row.setSpacing(14)

        title = QLabel("Left4Translate")
        title.setObjectName("AppTitle")
        row.addWidget(title)

        self._mode_combo = NoScrollComboBox()
        for mode in MODES:
            self._mode_combo.addItem(mode.capitalize(), mode)
        idx = self._mode_combo.findData(self._store.mode())
        if idx >= 0:
            self._mode_combo.setCurrentIndex(idx)
        self._mode_combo.setToolTip("Translation mode (stop to change)")
        row.addWidget(self._mode_combo)

        self._start_button = QPushButton("Start")
        self._start_button.setObjectName("PrimaryButton")
        self._start_button.clicked.connect(self._toggle_engine)
        row.addWidget(self._start_button)

        self._overlay_button = QPushButton("Overlay")
        self._overlay_button.setCheckable(True)
        self._overlay_button.setToolTip(
            "Show an always-on-top translation overlay (a software stand-in for "
            "the Turing screen). Floats over a borderless/windowed game without "
            "stealing focus."
        )
        self._overlay_button.toggled.connect(self._toggle_overlay)
        row.addWidget(self._overlay_button)

        row.addStretch(1)

        self._status_bank = StatusBank(_STATUS_COMPONENTS)
        row.addWidget(self._status_bank)
        return bar

    def _build_tabs(self) -> QTabWidget:
        self.dashboard_tab = DashboardTab(self._controller, self)
        self.voice_tab = VoiceTab(self._controller, self)
        self.settings_tab = SettingsTab(self._config_path, self._store, self)
        self.logs_tab = LogsTab(self)
        self.logs_tab.attach(level=logging.INFO)

        self.tabs = QTabWidget(self)
        self.tabs.addTab(self.dashboard_tab, "Dashboard")
        self.tabs.addTab(self.voice_tab, "Voice")
        self.tabs.addTab(self.settings_tab, "Settings")
        self.tabs.addTab(self.logs_tab, "Logs")

        # Seed the Voice tab with the current config snapshot.
        self.voice_tab.set_config(getattr(self.settings_tab, "_raw", {}))
        return self.tabs

    def _build_tray(self) -> Optional[TrayIcon]:
        if not is_tray_available():
            return None
        tray = TrayIcon(self.windowIcon() or QIcon(), parent=self)
        tray.show()
        return tray

    def _restore_geometry(self) -> None:
        geometry = self._store.geometry()
        if geometry is not None:
            self.restoreGeometry(geometry)
        else:
            self.resize(1040, 680)
        state = self._store.window_state()
        if state is not None:
            self.restoreState(state)

    def _wire_signals(self) -> None:
        self._controller.translation.connect(self._on_translation)
        self._controller.status.connect(self._on_status)
        self._controller.started.connect(self._on_started)
        self._controller.stopped.connect(self._on_stopped)
        self._controller.failed.connect(self._on_failed)
        self._controller.start_rejected.connect(self._on_start_rejected)

        self.settings_tab.theme_changed.connect(self._on_theme_changed)
        self.settings_tab.config_saved.connect(self._on_config_saved)
        self.settings_tab.status_message.connect(lambda msg: self._show_status(msg, 5000))

        if self._tray is not None:
            self._tray.show_window_requested.connect(self.show_normal)
            self._tray.start_stop_requested.connect(self._toggle_engine)
            self._tray.quit_requested.connect(self._quit_application)

    # ---- Engine control -------------------------------------------------

    def _toggle_engine(self) -> None:
        if self._running or self._controller.is_running():
            self._show_status("Stopping…")
            self._controller.stop()
            return
        mode = self._mode_combo.currentData()
        self._store.set_mode(mode)
        self.dashboard_tab.reset()
        self._start_button.setEnabled(False)
        self._status_bank.set_state("engine", "starting", "Starting…")
        self._show_status(f"Starting translation ({mode})…")
        self._controller.start(mode)

    # ---- Overlay --------------------------------------------------------

    def _restore_overlay(self) -> None:
        """Re-open the overlay on launch if it was visible last session."""
        if self._store.overlay_visible():
            self._overlay_button.setChecked(True)

    def _toggle_overlay(self, checked: bool) -> None:
        if checked:
            self._overlay.show()
            self._overlay.raise_()
        else:
            self._overlay.hide()
        self._store.set_overlay_visible(checked)

    def maybe_autostart(self) -> None:
        if self._store.autostart():
            self._toggle_engine()

    def maybe_start_minimized(self) -> None:
        if not self._store.start_minimized():
            return
        if self._tray is None:
            self._show_status("System tray unavailable — starting in a normal window.", 4000)
            return
        self.hide()

    # ---- Controller slots (GUI thread) ----------------------------------

    def _on_translation(self, payload: dict) -> None:
        self.dashboard_tab.add_translation(payload)
        self._overlay.add_translation(payload)
        if payload.get("kind") == "voice":
            self.voice_tab.add_voice_translation(payload)

    def _on_status(self, component: str, state: str, detail: str) -> None:
        text = component.capitalize()
        if detail:
            text = f"{component.capitalize()}: {detail}"
        elif state not in ("idle",):
            text = f"{component.capitalize()} {state}"
        self._status_bank.set_state(component, state, text)
        if component == "voice":
            self.voice_tab.set_status(state, detail)

    def _on_started(self) -> None:
        self._set_ui_running(True)
        self.dashboard_tab.set_running(True)
        self._show_status("Translation running")

    def _on_stopped(self) -> None:
        self._set_ui_running(False)
        self.dashboard_tab.set_running(False)
        for component in _STATUS_COMPONENTS:
            self._status_bank.set_state(component, "idle", component.capitalize())
        self._show_status("Translation stopped")
        if self._restart_pending:
            # Config-saved restart: the old engine is fully down, start anew.
            self._restart_pending = False
            self._toggle_engine()

    def _on_start_rejected(self, message: str) -> None:
        """Previous engine still winding down: restore the idle UI."""
        self._set_ui_running(False)
        self._show_status(message, 6000)

    def _on_failed(self, message: str) -> None:
        self._set_ui_running(False)
        self.dashboard_tab.set_running(False)
        self._status_bank.set_state("engine", "error", "Engine error")
        self._show_status(message, 0)
        _logger.error(message)

    def _set_ui_running(self, running: bool) -> None:
        self._running = running
        self._start_button.setEnabled(True)
        self._start_button.setText("Stop" if running else "Start")
        self._start_button.setObjectName("DangerButton" if running else "PrimaryButton")
        # Re-polish so the objectName change re-applies the QSS.
        self._start_button.style().unpolish(self._start_button)
        self._start_button.style().polish(self._start_button)
        self._mode_combo.setEnabled(not running)
        self.settings_tab.set_engine_running(running)
        if self._tray is not None:
            self._tray.set_running(running)

    # ---- Settings slots -------------------------------------------------

    def _on_theme_changed(self, theme: str) -> None:
        app = QApplication.instance()
        if app is not None:
            apply_theme(app, theme)

    def _on_config_saved(self, config: dict) -> None:
        self.voice_tab.set_config(config)
        if not self._running:
            return
        answer = QMessageBox.question(
            self,
            "Apply settings",
            "Settings saved. Restart translation now to apply them?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if answer == QMessageBox.StandardButton.Yes:
            self._restart_pending = True
            self._show_status("Restarting translation…")
            self._controller.stop()
        else:
            self._show_status("Config saved — will apply on the next Start.", 6000)

    # ---- Window / lifecycle ---------------------------------------------

    def show_normal(self) -> None:
        if not self.isVisible():
            self.show()
        if self.isMinimized():
            self.showNormal()
        self.raise_()
        self.activateWindow()

    def _show_status(self, text: str, timeout_ms: int = 4000) -> None:
        self.statusBar().showMessage(text, timeout_ms)

    def closeEvent(self, event) -> None:  # type: ignore[override]
        if (
            self._tray is not None
            and self._store.minimize_to_tray()
            and not self._force_quit
        ):
            self.hide()
            event.ignore()
            self._show_status("Still running in the tray — right-click the tray icon to quit.")
            return

        self._store.set_geometry(self.saveGeometry())
        self._store.set_window_state(self.saveState())
        if self._overlay.isVisible():
            self._overlay.save_geometry()
        self._overlay.close()
        self._controller.stop()
        self.logs_tab.detach()
        self.logs_tab.release_streams()
        if self._tray is not None:
            self._tray.hide()
        super().closeEvent(event)

    def _quit_application(self) -> None:
        self._force_quit = True
        self.close()  # closeEvent saves state and requests engine stop
        app = QApplication.instance()
        if app is None:
            return
        if not self._controller.is_running():
            app.quit()
            return
        # Give the engine a moment to wind down cleanly (serial port, log
        # watcher), but never hang the quit: hard deadline via timer. The
        # engine thread is a daemon, so process exit can't be held hostage.
        self._controller.stopped.connect(app.quit)
        QTimer.singleShot(3000, app.quit)
