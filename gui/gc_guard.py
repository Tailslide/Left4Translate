"""Run Python's cyclic garbage collector only on the GUI thread.

CPython triggers a cyclic collection on whichever thread happens to trip the
allocation threshold. In this app that is almost always one of the engine's
worker threads — the watchdog log reader, the voice pipeline, the display
loop — because they allocate constantly. When a collection running on such a
thread frees a reference cycle that contains PySide6 wrappers, the underlying
Qt C++ objects are destroyed *on that worker thread*. Qt requires GUI objects
to be destroyed on the thread that owns them; destroying them elsewhere
corrupts Qt's internal state, and the damage detonates later as a native
access violation in unrelated GUI-thread code (observed in the field as a
crash inside the dashboard feed's QTableWidget row churn — see
``logs/crash.log`` in the bug report).

The mitigation — used by calibre, Anki, and other large PyQt/PySide apps —
is to disable the automatic collector and drive ``gc.collect()`` from a
QTimer on the GUI thread, where deleting those wrappers is safe. Reference
counting is unaffected: acyclic objects are still freed immediately, only
reference *cycles* wait for the timer tick.
"""

from __future__ import annotations

import gc
from typing import Optional

from PySide6.QtCore import QObject, QTimer

# How often the GUI-thread collection runs, and how many ticks between full
# (generation 2) collections. Young-generation passes are cheap (<1 ms); the
# occasional full pass keeps long-lived cycles from accumulating.
_INTERVAL_MS = 2000
_FULL_EVERY = 15

_instance: Optional["GcDriver"] = None


class GcDriver(QObject):
    """Owns the collection timer. Must be created on the GUI thread."""

    def __init__(
        self,
        parent: Optional[QObject] = None,
        interval_ms: int = _INTERVAL_MS,
        full_every: int = _FULL_EVERY,
    ) -> None:
        super().__init__(parent)
        self._full_every = max(1, full_every)
        self._tick = 0
        self._timer = QTimer(self)
        self._timer.setInterval(interval_ms)
        self._timer.timeout.connect(self._collect)

    def start(self) -> None:
        gc.disable()
        self._timer.start()

    def stop(self) -> None:
        self._timer.stop()
        gc.enable()

    def _collect(self) -> None:
        self._tick = (self._tick + 1) % self._full_every
        # Generation 1 also sweeps generation 0; generation 2 sweeps everything.
        gc.collect(2 if self._tick == 0 else 1)


def install(parent: Optional[QObject] = None) -> GcDriver:
    """Disable automatic GC and start GUI-thread collections. Idempotent.

    Call on the GUI thread after the QApplication exists (the timer needs a
    running event loop to fire, and must have GUI-thread affinity).
    """
    global _instance
    if _instance is None:
        _instance = GcDriver(parent)
        _instance.start()
    return _instance


def uninstall() -> None:
    """Stop the driver and restore automatic GC (used by tests)."""
    global _instance
    if _instance is not None:
        _instance.stop()
        _instance = None
