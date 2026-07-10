"""Tests for the async stop path and double-start guard (plan items 22-24)."""

from __future__ import annotations

import os
import sys
import threading
import time
import types

import pytest

_SRC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)


# ---------------------------------------------------------------------------
# Item 22 — event-based engine loop: stop() unblocks start() immediately
# ---------------------------------------------------------------------------

def test_engine_stop_unblocks_start_quickly(tmp_path):
    # Reuse the stub-module strategy from test_engine_screen_voice.
    import importlib
    import json

    class _Sink:
        def __init__(self, *a, **k):
            pass

        def connect(self):
            return False

        def disconnect(self):
            pass

        def start_monitoring(self, *a, **k):
            pass

        def stop_monitoring(self):
            pass

    reader_mod = types.ModuleType("reader.message_reader")
    reader_mod.GameMessageReader = _Sink
    reader_mod.Message = object
    translator_mod = types.ModuleType("translator.translation_service")
    translator_mod.TranslationService = _Sink
    display_mod = types.ModuleType("display.screen_controller")
    display_mod.ScreenController = _Sink
    audio_mod = types.ModuleType("audio.voice_translation_manager")
    audio_mod.VoiceTranslationManager = _Sink
    for pkg in ("reader", "translator", "display", "audio"):
        sys.modules.setdefault(pkg, types.ModuleType(pkg))
    sys.modules["reader.message_reader"] = reader_mod
    sys.modules["translator.translation_service"] = translator_mod
    sys.modules["display.screen_controller"] = display_mod
    sys.modules["audio.voice_translation_manager"] = audio_mod
    sys.modules.pop("main", None)
    main = importlib.import_module("main")

    sample = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "config", "config.sample.json",
    )
    with open(sample, "r", encoding="utf-8") as fh:
        cfg = json.load(fh)
    cfg["translation"]["apiKey"] = "k"
    cfg["screen"]["enabled"] = False
    cfg["voice_translation"]["enabled"] = False
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps(cfg), encoding="utf-8")

    engine = main.Left4Translate(
        str(config_path), "chat",
        on_status=lambda *a: None,
        install_signal_handlers=False,
    )
    t = threading.Thread(target=engine.start, daemon=True)
    t.start()
    time.sleep(0.2)  # let start() reach the wait
    began = time.monotonic()
    engine.stop()
    t.join(timeout=2.0)
    elapsed = time.monotonic() - began

    assert not t.is_alive(), "engine.start() must return after stop()"
    assert elapsed < 1.0, f"stop took {elapsed:.2f}s; the old poll loop needed up to 1s"


# ---------------------------------------------------------------------------
# Item 23 — controller refuses to start while the old thread is alive
# ---------------------------------------------------------------------------

@pytest.fixture
def controller():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication

    QApplication.instance() or QApplication([])
    from gui.engine_controller import EngineController

    return EngineController("unused-config.json")


def test_start_refused_while_previous_thread_winding_down(controller):
    rejections = []
    controller.start_rejected.connect(rejections.append)

    release = threading.Event()
    zombie = threading.Thread(target=release.wait, daemon=True)
    zombie.start()
    controller._thread = zombie  # engine gone (stop() ran) but thread alive
    controller._engine = None

    controller.start("chat")

    assert len(rejections) == 1
    assert controller._thread is zombie, "no new thread may be spawned"
    release.set()


def test_stop_is_nonblocking(controller):
    class _SlowEngine:
        def __init__(self):
            self.stop_called = False

        def stop(self):
            self.stop_called = True  # instant flag flip; real teardown is async

    engine = _SlowEngine()
    controller._engine = engine
    began = time.monotonic()
    controller.stop()
    assert time.monotonic() - began < 0.5
    assert engine.stop_called
    assert controller._engine is None


# ---------------------------------------------------------------------------
# Item 24 — audio callback does no blocking work, swallows consumer errors
# ---------------------------------------------------------------------------

def test_audio_callback_minimal(monkeypatch):
    import importlib

    import numpy as np

    fake_sd = types.ModuleType("sounddevice")
    fake_sd.query_devices = lambda: []
    fake_sd.default = types.SimpleNamespace(device=[0, 0])
    sys.modules["sounddevice"] = fake_sd
    audio_pkg = types.ModuleType("audio")
    audio_pkg.__path__ = [os.path.join(_SRC, "audio")]
    sys.modules["audio"] = audio_pkg
    sys.modules.pop("audio.voice_recorder", None)
    mod = importlib.import_module("audio.voice_recorder")

    rec = object.__new__(mod.VoiceRecorder)
    rec.lock = threading.Lock()
    rec.audio_data = []
    rec.last_level_db = None
    rec._callback_status = None
    rec.on_data_callback = lambda data: (_ for _ in ()).throw(RuntimeError("consumer died"))

    block = np.full((160, 1), 0.5, dtype=np.float32)
    # Must not raise despite the exploding consumer callback.
    rec._audio_callback(block, 160, None, "input overflow")

    assert len(rec.audio_data) == 1
    assert rec.last_level_db == pytest.approx(20 * np.log10(0.5), abs=0.01)
    assert rec._callback_status == "input overflow"


def test_audio_callback_does_not_log(monkeypatch, caplog):
    import importlib
    import logging

    import numpy as np

    fake_sd = types.ModuleType("sounddevice")
    fake_sd.query_devices = lambda: []
    fake_sd.default = types.SimpleNamespace(device=[0, 0])
    sys.modules["sounddevice"] = fake_sd
    audio_pkg = types.ModuleType("audio")
    audio_pkg.__path__ = [os.path.join(_SRC, "audio")]
    sys.modules["audio"] = audio_pkg
    sys.modules.pop("audio.voice_recorder", None)
    mod = importlib.import_module("audio.voice_recorder")

    rec = object.__new__(mod.VoiceRecorder)
    rec.lock = threading.Lock()
    rec.audio_data = []
    rec.last_level_db = None
    rec._callback_status = None
    rec.on_data_callback = None

    with caplog.at_level(logging.DEBUG):
        for _ in range(10):
            rec._audio_callback(np.zeros((160, 1), dtype=np.float32), 160, None, None)

    assert caplog.records == [], "the realtime audio callback must never log"
