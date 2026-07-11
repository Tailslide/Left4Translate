"""Global crash reporting for the windowed GUI build.

The packaged ``Left4Translate-GUI.exe`` has no console (``console=False``), so
without these hooks any uncaught exception on a background thread — and any
native fault in Qt, PortAudio, the pynput mouse hook, or pyserial — terminates
the process with nothing shown anywhere. This module makes every crash leave a
trace:

* ``faulthandler`` writes native-fault stacks to ``logs/crash.log``;
* ``sys.excepthook`` / ``threading.excepthook`` log uncaught Python exceptions
  (root logger → ``logs/app.log``) and surface a dialog on the GUI thread;
* Qt's own warnings/fatals are routed into ``logging`` via
  ``qInstallMessageHandler``.

Call :func:`install` once at startup, before any threads are spawned.
"""

from __future__ import annotations

import faulthandler
import logging
import sys
import threading
import traceback
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QObject, Signal, qInstallMessageHandler, QtMsgType

_logger = logging.getLogger("left4translate.crash")

# Keep the crash-log file object alive for the process lifetime; faulthandler
# writes to the raw fd and a garbage-collected handle would close it.
_crash_log_file = None


class CrashReporter(QObject):
    """Marshals crash notifications onto the GUI thread.

    ``crashed`` is emitted (queued, thread-safe) with a short human-readable
    summary whenever an uncaught exception is hooked. The application connects
    it to a dialog; headless embedders can simply not connect anything.
    """

    crashed = Signal(str)


reporter = CrashReporter()


def _format_summary(exc_type, exc_value) -> str:
    return f"{getattr(exc_type, '__name__', exc_type)}: {exc_value}"


def _log_exception(origin: str, exc_type, exc_value, exc_tb) -> None:
    text = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
    _logger.critical("Uncaught exception (%s):\n%s", origin, text)


def _sys_hook(exc_type, exc_value, exc_tb) -> None:
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_tb)
        return
    _log_exception("main thread", exc_type, exc_value, exc_tb)
    try:
        reporter.crashed.emit(_format_summary(exc_type, exc_value))
    except RuntimeError:
        pass  # Qt already torn down


def _threading_hook(args: threading.ExceptHookArgs) -> None:
    if args.exc_type is SystemExit:
        return
    name = args.thread.name if args.thread else "unknown thread"
    _log_exception(f"thread {name}", args.exc_type, args.exc_value, args.exc_traceback)
    try:
        reporter.crashed.emit(_format_summary(args.exc_type, args.exc_value))
    except RuntimeError:
        pass


_QT_LEVELS = {
    QtMsgType.QtDebugMsg: logging.DEBUG,
    QtMsgType.QtInfoMsg: logging.INFO,
    QtMsgType.QtWarningMsg: logging.WARNING,
    QtMsgType.QtCriticalMsg: logging.ERROR,
    QtMsgType.QtFatalMsg: logging.CRITICAL,
}


def _qt_message_handler(msg_type, context, message) -> None:
    logging.getLogger("qt").log(_QT_LEVELS.get(msg_type, logging.WARNING), "%s", message)


def install(log_dir: Path | str) -> Optional[Path]:
    """Install all crash hooks. Returns the crash-log path (or None on failure).

    Idempotent: calling twice re-points the hooks at the same reporter, which
    is harmless.
    """
    global _crash_log_file

    crash_path: Optional[Path] = None
    try:
        log_dir = Path(log_dir)
        log_dir.mkdir(parents=True, exist_ok=True)
        crash_path = log_dir / "crash.log"
        _crash_log_file = open(crash_path, "a", encoding="utf-8", buffering=1)
        faulthandler.enable(file=_crash_log_file, all_threads=True)
    except OSError:
        # A read-only install dir must not stop the app; Python-level hooks
        # below still work and log via the root logger.
        _crash_log_file = None
        crash_path = None

    sys.excepthook = _sys_hook
    threading.excepthook = _threading_hook
    qInstallMessageHandler(_qt_message_handler)
    return crash_path
