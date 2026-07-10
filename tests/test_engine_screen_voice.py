"""Regression tests for the headless engine (``src/main.py``).

These cover two behaviours that broke when running without the Turing hardware:

1. A chat message must still reach the ``on_translation`` observer (the GUI
   overlay / live feed) even when the screen is disabled or its display call
   raises — previously a screen error aborted ``_handle_message`` before the
   translation was emitted.
2. Voice translation must not be initialised at all when it's disabled in
   config — constructing the manager probes the microphone and validates
   speech-to-text credentials, which should not happen when voice is off.

``src/main.py`` imports several heavy collaborators (Google Cloud, PIL, PyAudio)
at module load, so we stub those modules before importing it. The engine's own
logic under test is exercised against the real :class:`ConfigManager`.
"""

from __future__ import annotations

import importlib
import json
import os
import sys
import types

import pytest

_SRC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)


class _FakeScreenController:
    last_instance = None

    def __init__(self, *args, **kwargs):
        self.displayed = []
        self.raise_on_display = False
        _FakeScreenController.last_instance = self

    def display_message(self, **kwargs):
        if self.raise_on_display:
            raise RuntimeError("Display not connected. Call connect() first.")
        self.displayed.append(kwargs)

    def connect(self):
        return False

    def disconnect(self):
        pass


class _FakeTranslationService:
    def __init__(self, *args, **kwargs):
        pass

    def detect_language(self, text):
        return "es"

    def translate(self, text, source_language=None):
        return f"EN:{text}"

    def translate_with_detection(self, text, source_language=None, target_language=None):
        return f"EN:{text}", "es"


class _FakeVoiceManager:
    instances = 0

    def __init__(self, *args, **kwargs):
        _FakeVoiceManager.instances += 1

    def start(self):
        return True

    def stop(self):
        pass


class _FakeReader:
    def __init__(self, *args, **kwargs):
        pass

    def start_monitoring(self, *args, **kwargs):
        pass

    def stop_monitoring(self):
        pass


class _FakeMessage:
    def __init__(self, player, content, team=None):
        self.player = player
        self.content = content
        self.team = team


def _install_stub_modules():
    """Stub the heavy modules ``main`` imports, then (re)import ``main``."""
    reader_mod = types.ModuleType("reader.message_reader")
    reader_mod.GameMessageReader = _FakeReader
    reader_mod.Message = _FakeMessage

    translator_mod = types.ModuleType("translator.translation_service")
    translator_mod.TranslationService = _FakeTranslationService

    display_mod = types.ModuleType("display.screen_controller")
    display_mod.ScreenController = _FakeScreenController

    audio_mod = types.ModuleType("audio.voice_translation_manager")
    audio_mod.VoiceTranslationManager = _FakeVoiceManager

    # Parent packages so the dotted imports resolve.
    for pkg in ("reader", "translator", "display", "audio"):
        sys.modules.setdefault(pkg, types.ModuleType(pkg))
    sys.modules["reader.message_reader"] = reader_mod
    sys.modules["translator.translation_service"] = translator_mod
    sys.modules["display.screen_controller"] = display_mod
    sys.modules["audio.voice_translation_manager"] = audio_mod

    sys.modules.pop("main", None)
    return importlib.import_module("main")


@pytest.fixture
def main_module():
    return _install_stub_modules()


def _write_config(tmp_path, *, screen_enabled, voice_enabled):
    sample = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "config", "config.sample.json",
    )
    with open(sample, "r", encoding="utf-8") as fh:
        cfg = json.load(fh)
    cfg["translation"]["apiKey"] = "test-key"
    cfg["screen"]["enabled"] = screen_enabled
    cfg["voice_translation"]["enabled"] = voice_enabled
    path = tmp_path / "config.json"
    path.write_text(json.dumps(cfg), encoding="utf-8")
    return str(path)


def _make_engine(main_module, config_path, mode, on_translation=None):
    return main_module.Left4Translate(
        config_path,
        mode,
        on_translation=on_translation,
        on_status=lambda *a, **k: None,
        install_signal_handlers=False,
    )


def test_message_emits_when_screen_disabled(main_module, tmp_path):
    config_path = _write_config(tmp_path, screen_enabled=False, voice_enabled=False)
    received = []
    engine = _make_engine(main_module, config_path, "chat", on_translation=received.append)

    engine._handle_message(_FakeMessage("Pug Wrangler", "hola", team="Survivor"))

    assert len(received) == 1
    assert received[0]["player"] == "Pug Wrangler"
    assert received[0]["translated"] == "EN:hola"
    # Screen disabled: nothing should have been pushed to the (fake) display.
    assert _FakeScreenController.last_instance.displayed == []


def test_message_emits_when_screen_display_raises(main_module, tmp_path):
    config_path = _write_config(tmp_path, screen_enabled=True, voice_enabled=False)
    received = []
    engine = _make_engine(main_module, config_path, "chat", on_translation=received.append)
    # Simulate the "Display not connected" failure on every render.
    _FakeScreenController.last_instance.raise_on_display = True

    engine._handle_message(_FakeMessage("Bob", "corre", team="Infected"))

    # The screen error must not stop the translation from reaching the observer.
    assert len(received) == 1
    assert received[0]["translated"] == "EN:corre"


def test_voice_manager_not_initialised_when_disabled(main_module, tmp_path):
    _FakeVoiceManager.instances = 0
    config_path = _write_config(tmp_path, screen_enabled=False, voice_enabled=False)
    engine = _make_engine(main_module, config_path, "both")

    assert engine.voice_manager is None
    assert _FakeVoiceManager.instances == 0


def test_voice_manager_initialised_when_enabled(main_module, tmp_path):
    _FakeVoiceManager.instances = 0
    config_path = _write_config(tmp_path, screen_enabled=False, voice_enabled=True)
    engine = _make_engine(main_module, config_path, "both")

    assert engine.voice_manager is not None
    assert _FakeVoiceManager.instances == 1
