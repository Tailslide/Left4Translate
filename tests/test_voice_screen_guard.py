"""Regression test for voice translation when the Turing screen isn't connected.

``VoiceTranslationManager._process_audio`` displays the result on the Turing
screen before invoking ``on_translation_callback``. When the screen is disabled
or not connected, ``display_message`` raises ``Display not connected`` — that
must not stop the translation from reaching the callback (the GUI overlay /
clipboard).

``voice_translation_manager`` imports several hardware/cloud collaborators at
module load (PyAudio-backed recorder, pynput mouse handler, Google speech, …),
so we stub those modules before importing it, and build the manager via
``object.__new__`` to bypass the mic-probing constructor.
"""

from __future__ import annotations

import importlib
import os
import sys
import types

import pytest

_SRC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)


def _stub(module_name: str, **attrs) -> None:
    mod = types.ModuleType(module_name)
    for key, value in attrs.items():
        setattr(mod, key, value)
    sys.modules[module_name] = mod


class _RaisingScreen:
    def display_message(self, **kwargs):
        raise RuntimeError("Display not connected. Call connect() first.")


class _SpeechToText:
    client = object()
    language_code = "en-US"

    def transcribe_audio(self, audio_data):
        return "hello", 0.95


class _Translator:
    def translate(self, text, source_language=None, target_language=None):
        return "hola"


class _Clipboard:
    def __init__(self):
        self.copied = []

    def copy_to_clipboard(self, original, translated):
        self.copied.append((original, translated))


@pytest.fixture
def manager_module():
    # Make `audio` a package whose submodules resolve to the real source dir,
    # so the real voice_translation_manager.py loads while its heavy siblings
    # (and the heavy `audio/__init__.py`) are replaced by the stubs below.
    audio_pkg = types.ModuleType("audio")
    audio_pkg.__path__ = [os.path.join(_SRC, "audio")]
    sys.modules["audio"] = audio_pkg
    for parent in ("input", "translator", "utils"):
        sys.modules[parent] = types.ModuleType(parent)

    _stub("input.mouse_handler", MouseHandler=object)
    _stub("audio.voice_recorder", VoiceRecorder=object)
    _stub("audio.speech_to_text", SpeechToTextService=object)
    _stub("translator.translation_service", TranslationService=object)
    _stub("utils.clipboard_manager", ClipboardManager=object)
    sys.modules.pop("audio.voice_translation_manager", None)
    return importlib.import_module("audio.voice_translation_manager")


def _make_manager(manager_module, on_translation_callback):
    mgr = object.__new__(manager_module.VoiceTranslationManager)
    mgr.speech_to_text = _SpeechToText()
    mgr.translation_service = _Translator()
    mgr.clipboard_manager = _Clipboard()
    mgr.screen_controller = _RaisingScreen()
    mgr.on_translation_callback = on_translation_callback
    mgr.target_language = "es"
    mgr.clear_after = 5000
    # Bypass the numpy-based audio check.
    mgr._check_audio_quality = lambda audio_data: "good"
    return mgr


def test_voice_callback_fires_when_screen_raises(manager_module):
    received = []
    mgr = _make_manager(manager_module, lambda t, tr: received.append((t, tr)))

    mgr._process_audio(b"\x00\x00")

    # The screen failure must not prevent the callback (overlay/feed) from firing.
    assert received == [("hello", "hola")]
    # …and the clipboard copy should still have happened.
    assert mgr.clipboard_manager.copied == [("hello", "hola")]
