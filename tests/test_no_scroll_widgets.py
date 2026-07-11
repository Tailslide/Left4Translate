"""The Settings form must not change values on hover-scroll (user report B)."""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from PySide6.QtCore import QPoint, QPointF, Qt  # noqa: E402
from PySide6.QtGui import QWheelEvent  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from gui.widgets import NoScrollComboBox, NoScrollSpinBox  # noqa: E402


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def _wheel_up(widget) -> None:
    event = QWheelEvent(
        QPointF(5, 5),
        QPointF(widget.mapToGlobal(QPoint(5, 5))),
        QPoint(0, 0),
        QPoint(0, 120),
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
        Qt.ScrollPhase.NoScrollPhase,
        False,
    )
    QApplication.sendEvent(widget, event)


def test_spinbox_ignores_wheel_without_focus(app):
    spin = NoScrollSpinBox()
    spin.setRange(0, 100)
    spin.setValue(50)
    spin.show()
    spin.clearFocus()

    _wheel_up(spin)
    assert spin.value() == 50, "hover-scroll must not change an unfocused spinbox"


def test_spinbox_accepts_wheel_with_focus(app):
    spin = NoScrollSpinBox()
    spin.setRange(0, 100)
    spin.setValue(50)
    spin.show()
    spin.setFocus(Qt.FocusReason.MouseFocusReason)
    app.processEvents()
    if not spin.hasFocus():
        pytest.skip("offscreen platform did not grant focus")

    _wheel_up(spin)
    assert spin.value() == 51


def test_combobox_ignores_wheel_without_focus(app):
    combo = NoScrollComboBox()
    combo.addItems(["a", "b", "c"])
    combo.setCurrentIndex(1)
    combo.show()
    combo.clearFocus()

    _wheel_up(combo)
    assert combo.currentIndex() == 1, "hover-scroll must not change an unfocused combo"


def test_settings_tab_uses_no_scroll_widgets(app, tmp_path):
    from PySide6.QtCore import QSettings

    from gui.settings_store import SettingsStore
    from gui.settings_tab import SettingsTab

    store = SettingsStore(QSettings(str(tmp_path / "t.ini"), QSettings.Format.IniFormat))
    tab = SettingsTab(str(tmp_path / "config.json"), store)
    spins = [w for w in tab._widgets.values() if hasattr(w, "setValue")]
    assert spins, "expected int fields in the settings form"
    assert all(isinstance(w, NoScrollSpinBox) for w in spins)
    assert isinstance(tab._theme_combo, NoScrollComboBox)
    assert isinstance(tab._mode_combo, NoScrollComboBox)
