"""Tests for M4 items: slang overrides, persistent cache, oversized-message
truncation, get_setting traversal, and the logs-tab filter/save."""

from __future__ import annotations

import importlib
import json
import os
import sys

import pytest

_SRC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)


@pytest.fixture
def svc_module():
    sys.modules.pop("translator.translation_service", None)
    sys.modules.pop("translator", None)
    return importlib.import_module("translator.translation_service")


# ---------------------------------------------------------------------------
# Slang overrides from config/slang_es.json
# ---------------------------------------------------------------------------

def test_slang_file_overrides_and_extends(svc_module, tmp_path):
    slang = tmp_path / "slang_es.json"
    slang.write_text(
        json.dumps({"khe": "what", "manco": "bad player"}), encoding="utf-8"
    )
    svc = svc_module.TranslationService(api_key="k", slang_path=str(slang))

    assert svc.translate("khe") == "what"  # new entry
    assert svc.translate("manco") == "bad player"  # override wins
    assert svc.translate("nel") == "nope"  # built-ins still present


def test_bad_slang_file_is_ignored(svc_module, tmp_path):
    slang = tmp_path / "slang_es.json"
    slang.write_text("{ not json", encoding="utf-8")
    svc = svc_module.TranslationService(api_key="k", slang_path=str(slang))
    assert svc.translate("nel") == "nope"  # built-ins unaffected


# ---------------------------------------------------------------------------
# Persistent translation cache
# ---------------------------------------------------------------------------

def test_cache_persists_across_instances(svc_module, tmp_path):
    cache_file = tmp_path / "translation_cache.json"
    svc = svc_module.TranslationService(api_key="k", cache_file=str(cache_file))
    with_lock = svc._cache_lock
    with with_lock:
        svc.cache["auto:en:bonjour le monde"] = ("hello world", "fr")
    svc.save_cache()
    assert cache_file.exists()

    svc2 = svc_module.TranslationService(api_key="k", cache_file=str(cache_file))
    # A warm cache means no HTTP call at all for the same text.
    translated, source = svc2.translate_with_detection("bonjour le monde")
    assert (translated, source) == ("hello world", "fr")


# ---------------------------------------------------------------------------
# Oversized message truncation (screen controller)
# ---------------------------------------------------------------------------

def test_oversized_message_truncated_not_dropped():
    sys.modules.pop("display.screen_controller", None)
    if "display" in sys.modules and not hasattr(sys.modules["display"], "__path__"):
        sys.modules.pop("display", None)
    mod = importlib.import_module("display.screen_controller")

    import threading

    ctl = object.__new__(mod.ScreenController)
    ctl._active_messages_lock = threading.Lock()
    ctl.active_messages = []
    ctl.message_timeout = 0
    ctl.margin = 2
    ctl._screen_height = 320
    # Height model: proportional to text length, so a huge message "won't fit"
    # until display_message shortens it.
    ctl._calculate_message_height = lambda msg: (len(msg.original) + len(msg.translated)) // 4
    ctl._clean_player_name = lambda name: name

    huge = "palabra " * 400
    ctl.display_message(player="Bob", original=huge, translated=huge)

    assert len(ctl.active_messages) == 1, "message must be shown, not dropped"
    msg = ctl.active_messages[0]
    assert len(msg.original) < len(huge)
    assert msg.original.endswith("…") or msg.translated.endswith("…")


# ---------------------------------------------------------------------------
# ConfigManager.get_setting traversal
# ---------------------------------------------------------------------------

def test_get_setting_missing_intermediate_returns_default():
    sys.modules.pop("config.config_manager", None)
    if "config" in sys.modules and not hasattr(sys.modules["config"], "__path__"):
        sys.modules.pop("config", None)
    mod = importlib.import_module("config.config_manager")
    mgr = mod.ConfigManager.__new__(mod.ConfigManager)
    mgr.config = {"a": {"b": 1}}
    assert mgr.get_setting("a.b") == 1
    assert mgr.get_setting("a.missing.deep", "fallback") == "fallback"
    assert mgr.get_setting("missing.b", 42) == 42


# ---------------------------------------------------------------------------
# Logs tab: filter + save
# ---------------------------------------------------------------------------

def test_logs_tab_filter_and_save(tmp_path):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    pytest.importorskip("PySide6")
    import logging

    from PySide6.QtWidgets import QApplication

    QApplication.instance() or QApplication([])
    from gui.logs_tab import LogsTab

    tab = LogsTab()
    tab._append(logging.INFO, "alpha message")
    tab._append(logging.ERROR, "bravo failure")
    tab._append(logging.INFO, "bravo message")

    tab._on_search_changed("bravo")
    text = tab.view.toPlainText()
    assert "alpha" not in text
    assert "bravo failure" in text and "bravo message" in text

    # Search cleared: everything comes back (buffer survived the filter).
    tab._on_search_changed("")
    assert "alpha message" in tab.view.toPlainText()

    out = tmp_path / "saved.log"
    from unittest import mock

    with mock.patch(
        "gui.logs_tab.QFileDialog.getSaveFileName", return_value=(str(out), "")
    ):
        tab.save_to_file()
    saved = out.read_text(encoding="utf-8")
    assert "alpha message" in saved and "bravo failure" in saved


def test_version_single_source():
    sys.modules.pop("version", None)
    mod = importlib.import_module("version")
    import tomllib

    with open(os.path.join(os.path.dirname(_SRC), "pyproject.toml"), "rb") as fh:
        py = tomllib.load(fh)
    assert mod.__version__ == py["project"]["version"]
    assert mod.__version__ == py["tool"]["bumpversion"]["current_version"]
