"""Regression tests for the critical bugs fixed in the improvement plan.

1. Voice target language read from the wrong config key (always fell back to
   Spanish, ignoring ``voice_translation.translation.target_language``).
2. Short slang ("si", "f", "va", …) swallowed by the untranslatable-content
   check before the slang dictionary ever ran.
3. Chat monitoring silently stopping after the game truncates console.log
   (every game restart, and -conclearlog on every launch).
4. Per-message display expiry ignored when the controller-wide
   ``messageTimeout`` is 0 — voice messages/errors stuck on the Turing screen
   forever with the shipped sample config.
"""

from __future__ import annotations

import importlib
import os
import re
import sys
import types
from datetime import datetime, timedelta

import pytest

_SRC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)


# ---------------------------------------------------------------------------
# Bug 1 — voice target language
# ---------------------------------------------------------------------------

def _stub(module_name: str, **attrs) -> None:
    mod = types.ModuleType(module_name)
    for key, value in attrs.items():
        setattr(mod, key, value)
    sys.modules[module_name] = mod


class _KwargsSink:
    """Accepts any constructor signature; records nothing."""

    def __init__(self, *args, **kwargs):
        pass


@pytest.fixture
def manager_module():
    audio_pkg = types.ModuleType("audio")
    audio_pkg.__path__ = [os.path.join(_SRC, "audio")]
    sys.modules["audio"] = audio_pkg
    for parent in ("input", "translator", "utils"):
        sys.modules[parent] = types.ModuleType(parent)

    _stub("input.mouse_handler", MouseHandler=_KwargsSink)
    _stub("audio.voice_recorder", VoiceRecorder=_KwargsSink)
    _stub("audio.speech_to_text", SpeechToTextService=_KwargsSink)
    _stub("translator.translation_service", TranslationService=_KwargsSink)
    _stub("utils.clipboard_manager", ClipboardManager=_KwargsSink)
    sys.modules.pop("audio.voice_translation_manager", None)
    return importlib.import_module("audio.voice_translation_manager")


def test_voice_target_language_comes_from_config(manager_module):
    config = {
        "voice_translation": {
            "enabled": True,
            "translation": {"target_language": "fr"},
        }
    }
    mgr = manager_module.VoiceTranslationManager(
        config=config, translation_service=object()
    )
    assert mgr.target_language == "fr", (
        "voice target language must honour "
        "voice_translation.translation.target_language"
    )


def test_voice_target_language_default_is_spanish(manager_module):
    mgr = manager_module.VoiceTranslationManager(
        config={"voice_translation": {}}, translation_service=object()
    )
    assert mgr.target_language == "es"


# ---------------------------------------------------------------------------
# Bug 2 — short slang vs. the untranslatable-content check
# ---------------------------------------------------------------------------

@pytest.fixture
def translator():
    # Force a fresh import in case another test stubbed the module.
    sys.modules.pop("translator.translation_service", None)
    sys.modules.pop("translator", None)
    mod = importlib.import_module("translator.translation_service")
    return mod.TranslationService(api_key="test-key")


@pytest.mark.parametrize(
    "slang,expected",
    [
        ("si", "yeah"),
        ("f", "rip"),
        ("va", "ok"),
        ("nel", "nope"),
        ("izi", "ez"),
        ("rip", "dead"),
        ("tio", "bro"),
        ("eso si", "yeah"),
    ],
)
def test_short_slang_translates_without_api(translator, slang, expected):
    # No network mock: if the slang path regressed, this would attempt a real
    # HTTP call and fail loudly rather than silently passing.
    assert translator.translate(slang) == expected


def test_untranslatable_content_still_skipped(translator):
    assert translator.translate(":-)") == ":-)"
    assert translator.translate("123") == "123"
    assert translator.translate("1+?") == "1+?"


# ---------------------------------------------------------------------------
# Bug 3 — log truncation
# ---------------------------------------------------------------------------

_CHAT_REGEX = (
    r"^\((Survivor|Infected)\)\s*(?:C\s*\(Infected\)\s*)?(.+?)\s+:\s+(.+)$"
    r"|^(.+?)\s+:\s+(.+)$"
)


@pytest.fixture
def reader_handler(tmp_path):
    sys.modules.pop("reader.message_reader", None)
    sys.modules.pop("reader", None)
    mod = importlib.import_module("reader.message_reader")
    log = tmp_path / "console.log"
    log.write_text("", encoding="utf-8")
    received = []
    handler = mod.GameLogHandler(
        re.compile(_CHAT_REGEX), received.append, str(log)
    )
    return handler, log, received


def test_reader_survives_log_truncation(reader_handler):
    handler, log, received = reader_handler

    log.write_text("Alice  :  hola amigo mundo\n", encoding="utf-8")
    handler._process_new_lines(str(log))
    assert [m.content for m in received] == ["hola amigo mundo"]
    assert handler.last_position > 0

    # Game restart: console.log truncated, then new chat arrives.
    log.write_text("", encoding="utf-8")
    log.write_text("Bob  :  buenos dias companeros\n", encoding="utf-8")
    handler._process_new_lines(str(log))

    assert [m.content for m in received] == [
        "hola amigo mundo",
        "buenos dias companeros",
    ], "messages after truncation must still be read"


def test_reader_handles_missing_file(reader_handler):
    handler, log, received = reader_handler
    log.unlink()
    # Must not raise; watchdog thread would otherwise die.
    handler._process_new_lines(str(log))
    assert received == []


# ---------------------------------------------------------------------------
# Bug 4 — per-message expiry with messageTimeout=0
# ---------------------------------------------------------------------------

@pytest.fixture
def screen_module():
    sys.modules.pop("display.screen_controller", None)
    if "display" in sys.modules and not hasattr(sys.modules["display"], "__path__"):
        sys.modules.pop("display", None)
    return importlib.import_module("display.screen_controller")


def _bare_controller(mod):
    import threading

    ctl = object.__new__(mod.ScreenController)
    ctl._active_messages_lock = threading.Lock()
    ctl.active_messages = []
    ctl.message_timeout = 0  # the shipped sample config default
    return ctl


def test_voice_message_expires_even_with_global_timeout_zero(screen_module):
    ctl = _bare_controller(screen_module)
    now = datetime.now()
    expired_voice = screen_module.DisplayMessage(
        timestamp=now - timedelta(seconds=10),
        player="Voice",
        original="hello",
        translated="hola",
        expiry=now - timedelta(seconds=5),  # clear_after elapsed
    )
    chat_keep_forever = screen_module.DisplayMessage(
        timestamp=now - timedelta(hours=1),
        player="Alice",
        original="hi",
        translated="hi",
        expiry=None,  # messageTimeout=0 → keep until pushed out
    )
    ctl.active_messages = [expired_voice, chat_keep_forever]

    remaining = ctl._prune_expired(now)

    assert remaining == [chat_keep_forever], (
        "voice clear_after must expire its message even when the global "
        "messageTimeout is 0"
    )


def test_future_expiry_is_kept(screen_module):
    ctl = _bare_controller(screen_module)
    now = datetime.now()
    fresh = screen_module.DisplayMessage(
        timestamp=now,
        player="Voice",
        original="a",
        translated="b",
        expiry=now + timedelta(seconds=5),
    )
    ctl.active_messages = [fresh]
    assert ctl._prune_expired(now) == [fresh]
