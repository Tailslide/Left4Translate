"""The Settings tab must never destroy config.json (bug 5).

A JSON parse error used to leave the form backed by an empty dict; pressing
Save then rewrote the file with only the ~19 form fields, wiping the chat
regex (game.messageFormat) and the logging section.
"""

from __future__ import annotations

import json
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from PySide6.QtCore import QSettings  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from gui.settings_store import SettingsStore  # noqa: E402
from gui.settings_tab import SettingsTab  # noqa: E402


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def _store(tmp_path) -> SettingsStore:
    return SettingsStore(
        QSettings(str(tmp_path / "prefs.ini"), QSettings.Format.IniFormat)
    )


_GOOD_CONFIG = {
    "game": {
        "logPath": "x",
        "messageFormat": {"regex": "IMPORTANT-REGEX", "groups": {"team": 1}},
    },
    "translation": {"apiKey": "k"},
    "logging": {"level": "info", "path": "logs/app.log"},
}


def test_save_disabled_when_config_unparsable(app, tmp_path):
    cfg = tmp_path / "config.json"
    cfg.write_text("{ this is not json", encoding="utf-8")
    original = cfg.read_text(encoding="utf-8")

    tab = SettingsTab(str(cfg), _store(tmp_path))
    assert not tab._save_btn.isEnabled()

    tab.save()  # even a forced call must refuse
    assert cfg.read_text(encoding="utf-8") == original, (
        "save on an unparsable config must not touch the file"
    )


def test_save_preserves_unknown_keys_and_writes_backup(app, tmp_path):
    cfg = tmp_path / "config.json"
    cfg.write_text(json.dumps(_GOOD_CONFIG), encoding="utf-8")

    tab = SettingsTab(str(cfg), _store(tmp_path))
    assert tab._save_btn.isEnabled()
    tab.save()

    saved = json.loads(cfg.read_text(encoding="utf-8"))
    assert saved["game"]["messageFormat"]["regex"] == "IMPORTANT-REGEX"
    assert saved["logging"]["level"] == "info"
    assert (tmp_path / "config.json.bak").exists()
    backup = json.loads((tmp_path / "config.json.bak").read_text(encoding="utf-8"))
    assert backup == _GOOD_CONFIG


def test_reload_reenables_save_after_fix(app, tmp_path):
    cfg = tmp_path / "config.json"
    cfg.write_text("{ broken", encoding="utf-8")
    tab = SettingsTab(str(cfg), _store(tmp_path))
    assert not tab._save_btn.isEnabled()

    cfg.write_text(json.dumps(_GOOD_CONFIG), encoding="utf-8")
    tab.reload()
    assert tab._save_btn.isEnabled()
    tab.save()
    saved = json.loads(cfg.read_text(encoding="utf-8"))
    assert saved["game"]["messageFormat"]["regex"] == "IMPORTANT-REGEX"
