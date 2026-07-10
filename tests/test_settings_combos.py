"""Settings-tab dropdowns (user report C): value round-trips and defaults."""

from __future__ import annotations

import json
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from PySide6.QtCore import QSettings  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from gui.settings_store import SettingsStore  # noqa: E402
from gui.settings_tab import _TRIGGER_BUTTONS, SettingsTab  # noqa: E402
from gui.widgets import NoScrollComboBox  # noqa: E402


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def _tab(tmp_path, config: dict | None = None) -> SettingsTab:
    cfg = tmp_path / "config.json"
    if config is not None:
        cfg.write_text(json.dumps(config), encoding="utf-8")
    store = SettingsStore(
        QSettings(str(tmp_path / "prefs.ini"), QSettings.Format.IniFormat)
    )
    return SettingsTab(str(cfg), store)


def test_choice_fields_are_combos(app, tmp_path):
    tab = _tab(tmp_path)
    for path in (
        "translation.targetLanguage",
        "screen.port",
        "voice_translation.trigger_button.button",
        "voice_translation.audio.device",
        "voice_translation.speech_to_text.model",
        "voice_translation.clipboard.format",
    ):
        assert isinstance(tab._widgets[path], NoScrollComboBox), path


def test_trigger_combo_is_fixed_to_valid_buttons(app, tmp_path):
    tab = _tab(tmp_path)
    combo = tab._widgets["voice_translation.trigger_button.button"]
    assert not combo.isEditable(), "free text invited typos that fell back to button4"
    values = {combo.itemData(i) for i in range(combo.count())}
    assert values == {v for v, _ in _TRIGGER_BUTTONS}


def test_language_value_roundtrip(app, tmp_path):
    tab = _tab(tmp_path, {"translation": {"targetLanguage": "pt"}})
    combo = tab._widgets["translation.targetLanguage"]
    assert tab._combo_value(combo) == "pt"
    tab.save()
    saved = json.loads((tmp_path / "config.json").read_text(encoding="utf-8"))
    # The stored value is the bare code, never the display label.
    assert saved["translation"]["targetLanguage"] == "pt"


def test_exotic_language_survives(app, tmp_path):
    # Editable combos must accept values outside the preset list.
    tab = _tab(tmp_path, {"translation": {"targetLanguage": "eu"}})  # Basque
    assert tab._combo_value(tab._widgets["translation.targetLanguage"]) == "eu"
    tab.save()
    saved = json.loads((tmp_path / "config.json").read_text(encoding="utf-8"))
    assert saved["translation"]["targetLanguage"] == "eu"


def test_new_fields_get_safe_defaults(app, tmp_path):
    tab = _tab(tmp_path, {"translation": {"apiKey": "k"}})
    tab.save()
    saved = json.loads((tmp_path / "config.json").read_text(encoding="utf-8"))
    assert saved["voice_translation"]["speech_to_text"]["model"] == "default"
    assert saved["voice_translation"]["clipboard"]["format"] == "translated"
