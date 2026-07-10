"""QApplication bootstrap for the Left4Translate desktop GUI."""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from typing import Optional, Sequence

from PySide6.QtGui import QIcon
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWidgets import QApplication, QMessageBox

from gui import crash_guard
from gui.main_window import MainWindow
from gui.settings_store import SettingsStore
from gui.theme import apply_theme

APP_NAME = "Left4Translate"
ORG_NAME = "Left4Translate"
_SINGLE_INSTANCE_NAME = "Left4Translate-single-instance"


def _base_dir() -> str:
    """Directory the app should resolve data/config against.

    Mirrors the engine's own ``get_executable_dir``: next to the ``.exe`` when
    frozen, the repository root when running from source.
    """
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def resolve_config_path(base_dir: Optional[str] = None) -> str:
    """Resolve config.json the same way the CLI does (config/ then alongside)."""
    base = base_dir or _base_dir()
    flat = os.path.join(base, "config.json")
    if os.path.exists(flat):
        return flat
    return os.path.join(base, "config", "config.json")


def _icon_path(base_dir: str) -> Optional[str]:
    for candidate in (
        os.path.join(base_dir, "res", "icon.ico"),
        os.path.join(getattr(sys, "_MEIPASS", base_dir), "res", "icon.ico"),
    ):
        if os.path.exists(candidate):
            return candidate
    return None


def _setup_logging(base_dir: str) -> None:
    """Send engine/GUI log records to ``logs/app.log``.

    The Logs tab adds its own handler (and tees stdout/stderr) on top of this;
    we deliberately do *not* add a stdout handler here so console output isn't
    duplicated in the tab.
    """
    log_dir = Path(base_dir) / "logs"
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
        handler: logging.Handler = logging.FileHandler(log_dir / "app.log", encoding="utf-8")
    except OSError:
        handler = logging.NullHandler()
    handler.setFormatter(
        logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    )
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    # Avoid stacking file handlers if bootstrapped twice (e.g. tests).
    if not any(isinstance(h, logging.FileHandler) for h in root.handlers):
        root.addHandler(handler)


def _show_crash_dialog(summary: str) -> None:
    """Queued slot for crash_guard.reporter.crashed — runs on the GUI thread."""
    try:
        QMessageBox.critical(
            None,
            "Left4Translate — unexpected error",
            "Left4Translate hit an unexpected error and may be unstable.\n\n"
            f"{summary}\n\n"
            "Details were written to logs/app.log (and logs/crash.log for "
            "native faults). Please include them if you report this.",
        )
    except Exception:  # never let the reporter itself crash the app
        logging.getLogger(__name__).exception("Failed to show crash dialog")


def _activate_running_instance() -> bool:
    """If another Left4Translate is running, ask it to show itself.

    Two instances would fight over the serial port, the console.log watcher
    and the mouse hook — so the second launch defers to the first.
    """
    socket = QLocalSocket()
    socket.connectToServer(_SINGLE_INSTANCE_NAME)
    if socket.waitForConnected(300):
        socket.write(b"show")
        socket.flush()
        socket.waitForBytesWritten(300)
        socket.disconnectFromServer()
        return True
    return False


def _serve_single_instance(window: MainWindow) -> QLocalServer:
    """Listen for 'show yourself' pings from later launches."""
    QLocalServer.removeServer(_SINGLE_INSTANCE_NAME)  # clear stale socket
    server = QLocalServer(window)
    server.newConnection.connect(
        lambda: (_drain(server), window.show_normal())
    )
    server.listen(_SINGLE_INSTANCE_NAME)
    return server


def _drain(server: QLocalServer) -> None:
    conn = server.nextPendingConnection()
    if conn is not None:
        conn.readAll()
        conn.disconnectFromServer()


def build_application(argv: Optional[Sequence[str]] = None) -> tuple[QApplication, MainWindow]:
    """Construct the QApplication and main window without entering the loop."""
    base = _base_dir()
    _setup_logging(base)
    crash_guard.install(Path(base) / "logs")

    app = QApplication.instance() or QApplication(
        list(argv) if argv is not None else sys.argv
    )
    crash_guard.reporter.crashed.connect(_show_crash_dialog)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName(ORG_NAME)
    app.setQuitOnLastWindowClosed(False)  # keep running in the tray

    icon = _icon_path(base)
    if icon:
        app.setWindowIcon(QIcon(icon))

    store = SettingsStore()
    apply_theme(app, store.theme())

    window = MainWindow(config_path=resolve_config_path(base), store=store)
    window._single_instance_server = _serve_single_instance(window)
    if icon:
        window.setWindowIcon(QIcon(icon))
        if window._tray is not None:  # keep the tray icon in sync
            window._tray.setIcon(QIcon(icon))
    return app, window


def run(argv: Optional[Sequence[str]] = None) -> int:
    # A prior QApplication isn't needed for the socket probe.
    if _activate_running_instance():
        print("Left4Translate is already running — brought its window to the front.")
        return 0

    app, window = build_application(argv)
    # Mirror all console output into the Logs tab (GUI-only).
    window.logs_tab.capture_streams()
    try:
        window.show()
        window.maybe_autostart()
        window.maybe_start_minimized()
        return app.exec()
    finally:
        window.logs_tab.release_streams()
