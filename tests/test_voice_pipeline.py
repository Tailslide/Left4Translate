"""Tests for reader shutdown guards, speech-result concatenation, and the
voice status pipeline (plan items 10-12)."""

from __future__ import annotations

import importlib
import os
import re
import sys
import types
from types import SimpleNamespace

import pytest

_SRC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)


# ---------------------------------------------------------------------------
# Item 10 — reader shutdown / event guards
# ---------------------------------------------------------------------------

@pytest.fixture
def reader_module():
    sys.modules.pop("reader.message_reader", None)
    sys.modules.pop("reader", None)
    return importlib.import_module("reader.message_reader")


def test_stop_monitoring_without_start_does_not_raise(reader_module, tmp_path):
    reader = reader_module.GameMessageReader(
        log_path=str(tmp_path / "console.log"),
        message_pattern=r"^(.+?)\s+:\s+(.+)$",
        callback=lambda m: None,
    )
    # Never started; joining the unstarted observer used to raise RuntimeError.
    reader.stop_monitoring()


def test_on_modified_survives_vanished_file(reader_module, tmp_path):
    log = tmp_path / "console.log"
    handler = reader_module.GameLogHandler(
        re.compile(r"^(.+?)\s+:\s+(.+)$"), lambda m: None, str(log)
    )
    event = SimpleNamespace(is_directory=False, src_path=str(log))
    # File does not exist: os.path.samefile would raise; must not propagate
    # (an exception here kills the watchdog thread).
    handler.on_modified(event)


_FULL_REGEX = (
    r"^\((Survivor|Infected)\)\s*(?:C\s*\(Infected\)\s*)?(.+?)\s+:\s+(.+)$"
    r"|^(.+?)\s+:\s+(.+)$"
)


def test_on_created_resets_position(reader_module, tmp_path):
    log = tmp_path / "console.log"
    received = []
    handler = reader_module.GameLogHandler(
        re.compile(_FULL_REGEX), received.append, str(log)
    )
    handler.last_position = 9999  # stale position from a previous file
    log.write_text("Alice  :  hola amigo mundo\n", encoding="utf-8")
    handler.on_created(SimpleNamespace(is_directory=False, src_path=str(log)))
    assert [m.content for m in received] == ["hola amigo mundo"]


# ---------------------------------------------------------------------------
# Item 11 — speech-to-text result concatenation
# ---------------------------------------------------------------------------

def _alt(text: str, confidence: float):
    return SimpleNamespace(transcript=text, confidence=confidence)


def _speech_cls():
    """Import SpeechToTextService with the google modules stubbed."""
    audio_pkg = types.ModuleType("audio")
    audio_pkg.__path__ = [os.path.join(_SRC, "audio")]
    sys.modules["audio"] = audio_pkg
    google = types.ModuleType("google")
    google.__path__ = []
    cloud = types.ModuleType("google.cloud")
    cloud.speech = types.ModuleType("google.cloud.speech")
    cloud.speech.SpeechClient = object  # referenced in method annotations
    oauth2 = types.ModuleType("google.oauth2")
    oauth2.service_account = types.ModuleType("google.oauth2.service_account")
    sys.modules["google"] = google
    sys.modules["google.cloud"] = cloud
    sys.modules["google.cloud.speech"] = cloud.speech
    sys.modules["google.oauth2"] = oauth2
    sys.modules["google.oauth2.service_account"] = oauth2.service_account
    # numpy is a real dependency (requirements.txt); never stub it — a bare
    # stub in sys.modules would poison every later import in the test run.
    sys.modules.pop("numpy", None) if not hasattr(sys.modules.get("numpy"), "ndarray") else None
    sys.modules.pop("audio.speech_to_text", None)
    return importlib.import_module("audio.speech_to_text").SpeechToTextService


def test_transcript_concatenates_all_results():
    cls = _speech_cls()
    response = SimpleNamespace(
        results=[
            SimpleNamespace(alternatives=[_alt("hello there", 0.9)]),
            SimpleNamespace(alternatives=[_alt("how are you", 0.7)]),
            SimpleNamespace(alternatives=[]),  # empty result must be skipped
        ]
    )
    transcript, confidence = cls._extract_transcript(response)
    assert transcript == "hello there how are you"
    assert confidence == pytest.approx(0.8)


def test_transcript_empty_response():
    cls = _speech_cls()
    assert cls._extract_transcript(SimpleNamespace(results=[])) == ("", 0.0)


# ---------------------------------------------------------------------------
# Item 12 — voice status callback (recording / transcribing / armed)
# ---------------------------------------------------------------------------

@pytest.fixture
def manager_module():
    audio_pkg = types.ModuleType("audio")
    audio_pkg.__path__ = [os.path.join(_SRC, "audio")]
    sys.modules["audio"] = audio_pkg
    for parent in ("input", "translator", "utils"):
        sys.modules[parent] = types.ModuleType(parent)

    def _stub(module_name: str, **attrs):
        mod = types.ModuleType(module_name)
        for key, value in attrs.items():
            setattr(mod, key, value)
        sys.modules[module_name] = mod

    _stub("input.mouse_handler", MouseHandler=object)
    _stub("audio.voice_recorder", VoiceRecorder=object)
    _stub("audio.speech_to_text", SpeechToTextService=object)
    _stub("translator.translation_service", TranslationService=object)
    _stub("utils.clipboard_manager", ClipboardManager=object)
    sys.modules.pop("audio.voice_translation_manager", None)
    return importlib.import_module("audio.voice_translation_manager")


class _Recorder:
    def __init__(self):
        self.recording = False
        self.sample_rate = 16000

    def start_recording(self):
        self.recording = True
        return True

    def is_recording(self):
        return self.recording

    def stop_recording(self):
        self.recording = False
        return SimpleNamespace(size=0)  # empty clip: release path bails early


def _bare_manager(mod, statuses):
    mgr = object.__new__(mod.VoiceTranslationManager)
    mgr.is_active = True
    mgr.voice_recorder = _Recorder()
    mgr.speech_to_text = SimpleNamespace(client=object(), language_code="en-US")
    mgr.on_status_callback = lambda state, detail="": statuses.append(state)
    mgr.on_translation_callback = None
    mgr.screen_controller = None
    return mgr


def test_button_press_emits_recording(manager_module):
    statuses = []
    mgr = _bare_manager(manager_module, statuses)
    mgr._on_button_press()
    assert statuses == ["recording"]


def test_process_audio_ends_armed(manager_module):
    statuses = []
    mgr = _bare_manager(manager_module, statuses)
    mgr._check_audio_quality = lambda audio: "very_low"
    mgr._show_transcription_error = lambda *a, **k: None
    mgr._process_audio(SimpleNamespace(size=100))
    assert statuses[-1] == "armed", "pipeline must always return to armed"


def test_status_observer_errors_are_swallowed(manager_module):
    mgr = object.__new__(manager_module.VoiceTranslationManager)
    mgr.on_status_callback = lambda *a: (_ for _ in ()).throw(RuntimeError("gui died"))
    mgr._emit_status("recording")  # must not raise
