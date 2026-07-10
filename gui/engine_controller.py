"""Runs the Left4Translate engine on a background thread, bridged via Qt signals.

The engine (``src/main.py``'s :class:`Left4Translate`) is a blocking, callback
driven object. This controller owns its lifecycle for the GUI:

* constructs and runs it on a daemon thread (``engine.start()`` blocks),
* forwards its ``on_translation`` / ``on_status`` callbacks — which may fire on
  the reader's watchdog thread or a voice worker thread — onto Qt signals that
  Qt delivers safely to the GUI thread,
* exposes live stats (cache hit-rate, last mic level) by polling the engine.

The engine's own behaviour is unchanged; the CLI constructs it without any of
these callbacks.
"""

from __future__ import annotations

import os
import sys
import threading
from typing import Any, Dict, Optional

from PySide6.QtCore import QObject, Signal


def _ensure_engine_importable() -> None:
    """Put the engine's ``src`` directory on ``sys.path`` (idempotent).

    Works both from source (``<repo>/src``) and from a PyInstaller bundle,
    where the engine modules are collected at the bundle root.
    """
    here = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.path.join(os.path.dirname(here), "src"),  # <repo>/src (from source)
        os.path.join(getattr(sys, "_MEIPASS", here), "src"),  # bundled under src/
        getattr(sys, "_MEIPASS", here),  # bundled flat at root
    ]
    for path in candidates:
        if path and os.path.isdir(path) and path not in sys.path:
            sys.path.insert(0, path)


class EngineController(QObject):
    """Owns the translation engine thread and re-emits its activity as signals."""

    # (kind, player, original, translated, team, source_language)
    translation = Signal(dict)
    # (component, state, detail)
    status = Signal(str, str, str)
    started = Signal()
    stopped = Signal()
    failed = Signal(str)
    # Emitted when start() is refused because the previous engine thread is
    # still winding down (prevents duplicated global mouse hooks / watchers).
    start_rejected = Signal(str)

    def __init__(self, config_path: str, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._config_path = config_path
        self._thread: Optional[threading.Thread] = None
        self._engine = None
        self._lock = threading.Lock()

    # ---- Public API -----------------------------------------------------

    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self, mode: str) -> None:
        """Start the engine in ``mode`` (chat/voice/both).

        Refused while a previous engine thread is still alive: that engine
        still owns the global mouse hook, the log watcher, the serial port and
        the audio stream — starting a second one would duplicate all of them
        (a recipe for native crashes on Windows).
        """
        if self._thread is not None and self._thread.is_alive():
            if self._engine is not None:
                return  # plain double-start of a running engine: no-op
            self.start_rejected.emit(
                "The previous session is still stopping — try again in a moment."
            )
            return
        self._thread = threading.Thread(
            target=self._run, args=(mode,), name="L4T-Engine", daemon=True
        )
        self._thread.start()

    def stop(self) -> None:
        """Ask the engine to stop. Non-blocking: never joins on the GUI
        thread (a frozen window that gets killed looks like a silent crash).
        The ``stopped`` signal fires when the thread actually winds down."""
        engine = self._engine
        self._engine = None
        if engine is not None:
            try:
                engine.stop()
            except Exception:
                pass

    # ---- Live stats (polled from the GUI thread) ------------------------

    def cache_stats(self) -> Dict[str, int]:
        engine = self._engine
        translator = getattr(engine, "translator", None) if engine else None
        if translator is not None and hasattr(translator, "get_cache_stats"):
            try:
                return translator.get_cache_stats()
            except Exception:
                return {}
        return {}

    def last_audio_level_db(self) -> Optional[float]:
        engine = self._engine
        voice = getattr(engine, "voice_manager", None) if engine else None
        if voice is None:
            return None
        # While recording, the recorder publishes a per-block level — a live
        # meter. Otherwise fall back to the last completed clip's level.
        recorder = getattr(voice, "voice_recorder", None)
        try:
            if recorder is not None and recorder.is_recording():
                live = getattr(recorder, "last_level_db", None)
                if live is not None:
                    return live
        except Exception:
            pass
        return getattr(voice, "last_audio_level", None)

    # ---- Worker thread --------------------------------------------------

    def _run(self, mode: str) -> None:
        _ensure_engine_importable()
        try:
            from main import Left4Translate  # noqa: WPS433 (deferred import)
        except Exception as exc:  # pragma: no cover - import wiring
            self.failed.emit(f"Could not load translation engine: {exc}")
            return

        try:
            engine = Left4Translate(
                self._config_path,
                mode,
                on_translation=self._on_translation,
                on_status=self._on_status,
                install_signal_handlers=False,
            )
        except SystemExit:
            # The engine calls sys.exit() on missing/invalid config. Details are
            # already in the log; surface a friendly pointer to Settings.
            self.failed.emit(
                "Engine could not start — check the configuration "
                "(API key, log path, screen port) in the Settings tab."
            )
            return
        except Exception as exc:
            self.failed.emit(f"Engine failed to initialise: {exc}")
            return

        self._engine = engine
        self.started.emit()
        try:
            engine.start()  # blocks until stop() sets the engine's stop event
        except Exception as exc:
            self.failed.emit(f"Engine error: {exc}")
        finally:
            # Clear refs before signalling so a stopped-handler that calls
            # start() again isn't refused by our own stale references.
            self._engine = None
            self._thread = None
            self.stopped.emit()

    # ---- Engine callbacks (may run on non-GUI threads) ------------------

    def _on_translation(self, payload: Dict[str, Any]) -> None:
        # Signals marshal the dict to the GUI thread for us.
        self.translation.emit(dict(payload))

    def _on_status(self, component: str, state: str, detail: str = "") -> None:
        self.status.emit(component, state, detail or "")
