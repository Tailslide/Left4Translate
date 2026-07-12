"""Tests for gui.gc_guard — GUI-thread-only cyclic garbage collection.

The guard exists to stop CPython's cyclic collector from running on engine
worker threads, where freeing a cycle that contains PySide6 wrappers destroys
Qt objects off the GUI thread and corrupts Qt (native access violation in the
dashboard feed). These tests pin the contract: automatic GC is off while the
guard is installed, the timer tick still reclaims cycles, and uninstall
restores the interpreter default.
"""

from __future__ import annotations

import gc
import os
import weakref

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402

from gui import gc_guard  # noqa: E402


@pytest.fixture(scope="module")
def app():
    application = QApplication.instance() or QApplication([])
    yield application


@pytest.fixture()
def guard(app):
    driver = gc_guard.install(app)
    yield driver
    gc_guard.uninstall()
    assert gc.isenabled()  # uninstall must always restore the default


def test_install_disables_automatic_gc(guard):
    assert not gc.isenabled()


def test_install_is_idempotent(guard, app):
    assert gc_guard.install(app) is guard


def test_timer_runs_on_expected_interval(guard):
    assert guard._timer.isActive()
    assert guard._timer.interval() == gc_guard._INTERVAL_MS


def test_tick_collects_reference_cycles(guard):
    class Node:
        pass

    a, b = Node(), Node()
    a.other, b.other = b, a  # unreachable cycle: refcounting alone can't free it
    ref = weakref.ref(a)
    del a, b

    guard._collect()  # what the QTimer runs each tick
    assert ref() is None


def test_full_collection_every_nth_tick(guard, monkeypatch):
    generations = []
    monkeypatch.setattr(gc, "collect", lambda gen: generations.append(gen))

    guard._tick = 0
    for _ in range(gc_guard._FULL_EVERY):
        guard._collect()

    assert generations.count(2) == 1  # exactly one full pass per cycle
    assert set(generations) <= {1, 2}
