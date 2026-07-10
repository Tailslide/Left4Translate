"""Tests for the GUI crash-reporting hooks (gui/crash_guard.py)."""

from __future__ import annotations

import logging
import os
import sys
import threading

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from gui import crash_guard  # noqa: E402


@pytest.fixture
def installed(tmp_path):
    saved_sys_hook = sys.excepthook
    saved_threading_hook = threading.excepthook
    crash_path = crash_guard.install(tmp_path / "logs")
    yield crash_path
    sys.excepthook = saved_sys_hook
    threading.excepthook = saved_threading_hook


def test_install_creates_crash_log_and_hooks(installed, tmp_path):
    assert installed == tmp_path / "logs" / "crash.log"
    assert installed.exists()
    assert sys.excepthook is crash_guard._sys_hook
    assert threading.excepthook is crash_guard._threading_hook


def test_uncaught_exception_is_logged(installed, caplog):
    with caplog.at_level(logging.CRITICAL, logger="left4translate.crash"):
        try:
            raise ValueError("boom")
        except ValueError:
            crash_guard._sys_hook(*sys.exc_info())
    assert "boom" in caplog.text
    assert "ValueError" in caplog.text


def test_thread_exception_is_logged(installed, caplog):
    def _worker():
        raise RuntimeError("thread boom")

    with caplog.at_level(logging.CRITICAL, logger="left4translate.crash"):
        t = threading.Thread(target=_worker, name="TestWorker")
        t.start()
        t.join()
    assert "thread boom" in caplog.text
    assert "TestWorker" in caplog.text


def test_keyboard_interrupt_passes_through(installed):
    # KeyboardInterrupt must defer to the default hook (no dialog, no log spam).
    called = []
    original = sys.__excepthook__
    sys.__excepthook__ = lambda *a: called.append(a)
    try:
        crash_guard._sys_hook(KeyboardInterrupt, KeyboardInterrupt(), None)
    finally:
        sys.__excepthook__ = original
    assert len(called) == 1
