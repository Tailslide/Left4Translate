"""Tests for the desktop GUI layer.

The Qt-dependent tests run under the ``offscreen`` platform plugin so they need
no display. They're skipped automatically if PySide6 isn't installed (e.g. on a
CLI-only checkout).
"""

from __future__ import annotations

import json
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from PySide6.QtCore import QSettings  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from gui import styles  # noqa: E402
from gui.settings_tab import _bury, _dig  # noqa: E402


@pytest.fixture(scope="module")
def app():
    application = QApplication.instance() or QApplication([])
    yield application


# ---- Pure helpers (no Qt) -------------------------------------------------

def test_dig_and_bury_roundtrip():
    data: dict = {}
    _bury(data, "screen.display.maxMessages", 12)
    _bury(data, "translation.apiKey", "abc")
    assert data == {"screen": {"display": {"maxMessages": 12}}, "translation": {"apiKey": "abc"}}
    assert _dig(data, "screen.display.maxMessages") == 12
    assert _dig(data, "missing.path") is None


def test_bury_preserves_siblings():
    data = {"screen": {"port": "COM8", "brightness": 50}}
    _bury(data, "screen.brightness", 80)
    assert data["screen"]["port"] == "COM8"
    assert data["screen"]["brightness"] == 80


def test_team_color_mapping():
    assert styles.team_color("Survivor") == styles.TEAM_SURVIVOR
    assert styles.team_color("Infected") == styles.TEAM_INFECTED
    assert styles.team_color(None) == styles.TEXT_PRIMARY


def test_status_dot_color_known_and_unknown():
    assert styles.status_dot_color("running") == styles.GREEN
    assert styles.status_dot_color("error") == styles.RED
    assert styles.status_dot_color("whatever") == styles.TEXT_DIM


# ---- Widgets --------------------------------------------------------------

def test_dashboard_counts_and_feed(app):
    from gui.dashboard_tab import DashboardTab
    from gui.engine_controller import EngineController

    tab = DashboardTab(EngineController("nonexistent.json"))
    model = tab._feed.model()
    tab.add_translation({"kind": "chat", "player": "P", "original": "hola", "translated": "hi", "team": "Survivor"})
    tab.add_translation({"kind": "voice", "player": "Voice", "original": "uno", "translated": "one", "team": None})
    assert tab._count == 2
    assert tab._chars == len("hola") + len("uno")
    assert model.rowCount() == 2
    # Newest row is on top.
    assert model.index(0, 2).data() == "Voice"
    tab.reset()
    assert tab._count == 0
    assert model.rowCount() == 0


def test_dashboard_feed_caps_rows(app):
    """Regression: long sessions crashed natively when the feed trimmed its
    oldest QTableWidget row (access violation in removeRow, logs/crash.log).
    The model-backed feed must cap rows in pure Python without ever exceeding
    the limit."""
    from gui.dashboard_tab import _MAX_FEED_ROWS, DashboardTab
    from gui.engine_controller import EngineController

    tab = DashboardTab(EngineController("nonexistent.json"))
    model = tab._feed.model()
    for i in range(_MAX_FEED_ROWS + 25):
        tab.add_translation({
            "kind": "chat", "player": f"P{i}", "original": f"msg {i}",
            "translated": f"tr {i}", "team": "Survivor",
        })
    assert model.rowCount() == _MAX_FEED_ROWS
    # Newest row on top, oldest rows trimmed from the bottom.
    assert model.index(0, 2).data() == f"P{_MAX_FEED_ROWS + 24}"
    assert model.index(model.rowCount() - 1, 2).data() == "P25"
    assert tab._count == _MAX_FEED_ROWS + 25


def test_settings_save_then_reload(app, tmp_path):
    from gui.settings_store import SettingsStore
    from gui.settings_tab import SettingsTab

    ini = tmp_path / "prefs.ini"
    store = SettingsStore(QSettings(str(ini), QSettings.Format.IniFormat))
    cfg = tmp_path / "config.json"

    tab = SettingsTab(str(cfg), store)
    # screen.port is now an editable combo (enumerated COM ports + free text).
    tab._set_combo_value(tab._widgets["screen.port"], "COM9")
    tab._widgets["game.pollInterval"].setValue(750)
    tab._widgets["voice_translation.enabled"].setChecked(True)
    tab.save()

    on_disk = json.loads(cfg.read_text())
    assert on_disk["screen"]["port"] == "COM9"
    assert on_disk["game"]["pollInterval"] == 750
    assert on_disk["voice_translation"]["enabled"] is True

    # A fresh tab should read those values back into its widgets.
    tab2 = SettingsTab(str(cfg), store)
    assert tab2._combo_value(tab2._widgets["screen.port"]) == "COM9"
    assert tab2._widgets["game.pollInterval"].value() == 750
    assert tab2._widgets["voice_translation.enabled"].isChecked() is True


def test_engine_controller_status_signal(app):
    from gui.engine_controller import EngineController

    controller = EngineController("nonexistent.json")
    received = []
    controller.status.connect(lambda c, s, d: received.append((c, s, d)))
    controller._on_status("screen", "connected", "")
    controller._on_translation({"kind": "chat", "original": "x", "translated": "y"})
    assert ("screen", "connected", "") in received


# ---- Overlay window -------------------------------------------------------

def _count_overlay_messages(overlay) -> int:
    from gui.overlay_window import _MessageLabel

    return sum(
        1
        for i in range(overlay._body_layout.count())
        if isinstance(overlay._body_layout.itemAt(i).widget(), _MessageLabel)
    )


def test_overlay_add_and_clear(app, tmp_path):
    from gui.overlay_window import OverlayWindow
    from gui.settings_store import SettingsStore

    store = SettingsStore(QSettings(str(tmp_path / "p.ini"), QSettings.Format.IniFormat))
    overlay = OverlayWindow(store)

    overlay.add_translation({"kind": "chat", "player": "Bob", "original": "hola",
                             "translated": "hi", "team": "Survivor"})
    overlay.add_translation({"kind": "voice", "player": "Voice", "original": "uno",
                             "translated": "one", "team": None})
    assert _count_overlay_messages(overlay) == 2
    assert overlay._hint.isVisibleTo(overlay) is False

    overlay.clear()
    assert _count_overlay_messages(overlay) == 0
    assert overlay._hint.isVisibleTo(overlay) is True


def test_overlay_trims_to_max(app, tmp_path):
    from gui.overlay_window import _MAX_MESSAGES, OverlayWindow
    from gui.settings_store import SettingsStore

    store = SettingsStore(QSettings(str(tmp_path / "p.ini"), QSettings.Format.IniFormat))
    overlay = OverlayWindow(store)
    for i in range(_MAX_MESSAGES + 5):
        overlay.add_translation({"kind": "chat", "player": f"P{i}",
                                 "original": str(i), "translated": str(i), "team": None})
    assert _count_overlay_messages(overlay) == _MAX_MESSAGES


def test_overlay_opacity_persists(app, tmp_path):
    from gui.overlay_window import OverlayWindow
    from gui.settings_store import SettingsStore

    settings = QSettings(str(tmp_path / "p.ini"), QSettings.Format.IniFormat)
    store = SettingsStore(settings)
    overlay = OverlayWindow(store)
    start = overlay._opacity
    overlay._decrease_opacity()
    assert overlay._opacity < start
    # Persisted to the store so a new overlay restores it.
    assert SettingsStore(settings).overlay_opacity() == overlay._opacity


def test_settings_screen_enabled_defaults_on_when_absent(app, tmp_path):
    from gui.settings_store import SettingsStore
    from gui.settings_tab import SettingsTab

    store = SettingsStore(QSettings(str(tmp_path / "prefs.ini"), QSettings.Format.IniFormat))
    cfg = tmp_path / "config.json"
    # An older config with no screen.enabled key.
    cfg.write_text(json.dumps({"screen": {"port": "COM8"}}))

    tab = SettingsTab(str(cfg), store)
    # Absent should load as enabled, so a Save won't disable the hardware screen.
    assert tab._widgets["screen.enabled"].isChecked() is True
    tab.save()
    assert json.loads(cfg.read_text())["screen"]["enabled"] is True
