"""Settings tab — edit the engine's ``config.json`` and app preferences.

Two kinds of settings live here:

* **Engine config** — the same ``config/config.json`` the CLI uses. Edited via
  a form and written back with ``Save``; the raw file is loaded first so keys
  this form doesn't expose are preserved. Changes take effect on the next
  *Start* (the engine reads config at construction).
* **App preferences** — theme, default mode, tray behaviour. These are stored in
  ``QSettings`` (via :class:`SettingsStore`) and apply immediately.
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional, Tuple

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from gui.settings_store import (
    MODES,
    THEME_DARK,
    THEME_LIGHT,
    THEME_SYSTEM,
    SettingsStore,
)

# (config dotted-path, kind) for each engine-config field the form exposes.
# kind drives how the widget is read/written: text / int / bool.
_FIELDS: List[Tuple[str, str]] = [
    ("game.logPath", "text"),
    ("game.pollInterval", "int"),
    ("translation.apiKey", "secret"),
    ("translation.targetLanguage", "text"),
    ("translation.cacheSize", "int"),
    ("translation.rateLimitPerMinute", "int"),
    ("screen.port", "text"),
    ("screen.baudRate", "int"),
    ("screen.brightness", "int"),
    ("screen.display.maxMessages", "int"),
    ("screen.display.messageTimeout", "int"),
    ("voice_translation.enabled", "bool"),
    ("voice_translation.trigger_button.button", "text"),
    ("voice_translation.audio.device", "text"),
    ("voice_translation.translation.target_language", "text"),
    ("voice_translation.speech_to_text.language", "text"),
    ("voice_translation.speech_to_text.credentials_path", "text"),
    ("voice_translation.clipboard.auto_copy", "bool"),
]


def _dig(data: Dict[str, Any], path: str) -> Any:
    cur: Any = data
    for key in path.split("."):
        if isinstance(cur, dict) and key in cur:
            cur = cur[key]
        else:
            return None
    return cur


def _bury(data: Dict[str, Any], path: str, value: Any) -> None:
    keys = path.split(".")
    cur = data
    for key in keys[:-1]:
        nxt = cur.get(key)
        if not isinstance(nxt, dict):
            nxt = {}
            cur[key] = nxt
        cur = nxt
    cur[keys[-1]] = value


class SettingsTab(QWidget):
    """Form editor for ``config.json`` and the GUI's own preferences."""

    theme_changed = Signal(str)
    config_saved = Signal(dict)
    status_message = Signal(str)

    def __init__(self, config_path: str, store: SettingsStore,
                 parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._config_path = config_path
        self._store = store
        self._raw: Dict[str, Any] = {}
        self._widgets: Dict[str, QWidget] = {}

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        body = QWidget()
        self._form_root = QVBoxLayout(body)
        self._form_root.setContentsMargins(18, 16, 18, 16)
        self._form_root.setSpacing(6)
        scroll.setWidget(body)
        outer.addWidget(scroll, stretch=1)
        outer.addWidget(self._build_button_bar())

        self._build_sections()
        self.reload()

    # ---- Construction ---------------------------------------------------

    def _build_sections(self) -> None:
        self._form_root.addWidget(self._app_prefs_group())

        self._form_root.addWidget(self._group("Game", [
            ("game.logPath", "L4D2 console.log path", "browse_file"),
            ("game.pollInterval", "Poll interval (ms)", "int:100:60000"),
        ]))
        self._form_root.addWidget(self._group("Translation", [
            ("translation.apiKey", "Google API key", "secret"),
            ("translation.targetLanguage", "Target language", "text"),
            ("translation.cacheSize", "Cache size", "int:0:100000"),
            ("translation.rateLimitPerMinute", "Rate limit / min", "int:1:100000"),
        ]))
        self._form_root.addWidget(self._group("Turing Screen", [
            ("screen.port", "Serial port", "text"),
            ("screen.baudRate", "Baud rate", "int:9600:1000000"),
            ("screen.brightness", "Brightness", "int:0:100"),
            ("screen.display.maxMessages", "Max messages", "int:1:50"),
            ("screen.display.messageTimeout", "Message timeout (ms, 0=keep)", "int:0:600000"),
        ]))
        self._form_root.addWidget(self._group("Voice Translation", [
            ("voice_translation.enabled", "Enable voice translation", "bool"),
            ("voice_translation.trigger_button.button", "Trigger button", "text"),
            ("voice_translation.audio.device", "Microphone device", "text"),
            ("voice_translation.translation.target_language", "Voice target language", "text"),
            ("voice_translation.speech_to_text.language", "Speech language", "text"),
            ("voice_translation.speech_to_text.credentials_path", "Google credentials JSON", "browse_file"),
            ("voice_translation.clipboard.auto_copy", "Auto-copy translation", "bool"),
        ]))
        self._form_root.addStretch(1)

    def _app_prefs_group(self) -> QGroupBox:
        box = QGroupBox("Application")
        form = QFormLayout(box)
        form.setContentsMargins(0, 10, 0, 0)
        form.setSpacing(8)

        self._theme_combo = QComboBox()
        for label, value in (("System", THEME_SYSTEM), ("Dark", THEME_DARK), ("Light", THEME_LIGHT)):
            self._theme_combo.addItem(label, value)
        self._select_data(self._theme_combo, self._store.theme())
        self._theme_combo.currentIndexChanged.connect(self._on_theme_changed)
        form.addRow(self._cap("Theme"), self._theme_combo)

        self._mode_combo = QComboBox()
        for mode in MODES:
            self._mode_combo.addItem(mode.capitalize(), mode)
        self._select_data(self._mode_combo, self._store.mode())
        self._mode_combo.currentIndexChanged.connect(
            lambda _i: self._store.set_mode(self._mode_combo.currentData())
        )
        form.addRow(self._cap("Default mode"), self._mode_combo)

        self._autostart_check = QCheckBox("Start translating automatically on launch")
        self._autostart_check.setChecked(self._store.autostart())
        self._autostart_check.toggled.connect(self._store.set_autostart)
        form.addRow("", self._autostart_check)

        self._min_tray_check = QCheckBox("Minimize to tray on close")
        self._min_tray_check.setChecked(self._store.minimize_to_tray())
        self._min_tray_check.toggled.connect(self._store.set_minimize_to_tray)
        form.addRow("", self._min_tray_check)

        self._start_min_check = QCheckBox("Start minimized to tray")
        self._start_min_check.setChecked(self._store.start_minimized())
        self._start_min_check.toggled.connect(self._store.set_start_minimized)
        form.addRow("", self._start_min_check)
        return box

    def _group(self, title: str, rows: List[Tuple[str, str, str]]) -> QGroupBox:
        box = QGroupBox(title)
        form = QFormLayout(box)
        form.setContentsMargins(0, 10, 0, 0)
        form.setSpacing(8)
        for path, label, kind in rows:
            widget = self._make_widget(path, kind)
            self._widgets[path] = widget
            if kind == "bool":
                widget.setText(label)
                form.addRow("", widget)
            elif kind == "browse_file":
                form.addRow(self._cap(label), self._with_browse(widget))
            else:
                form.addRow(self._cap(label), widget)
        return box

    def _make_widget(self, path: str, kind: str) -> QWidget:
        if kind == "bool":
            return QCheckBox()
        if kind == "secret":
            edit = QLineEdit()
            edit.setEchoMode(QLineEdit.EchoMode.Password)
            edit.setPlaceholderText("Google Cloud Translation API key")
            return edit
        if kind.startswith("int"):
            spin = QSpinBox()
            parts = kind.split(":")
            lo = int(parts[1]) if len(parts) > 1 else 0
            hi = int(parts[2]) if len(parts) > 2 else 1_000_000
            spin.setRange(lo, hi)
            return spin
        edit = QLineEdit()
        if kind == "browse_file":
            edit.setPlaceholderText("Path…")
        return edit

    def _with_browse(self, edit: QWidget) -> QWidget:
        wrap = QWidget()
        row = QHBoxLayout(wrap)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(6)
        row.addWidget(edit, stretch=1)
        button = QPushButton("Browse…")
        button.clicked.connect(lambda: self._browse_into(edit))
        row.addWidget(button)
        return wrap

    def _build_button_bar(self) -> QWidget:
        bar = QWidget()
        bar.setObjectName("HeaderBar")
        row = QHBoxLayout(bar)
        row.setContentsMargins(14, 8, 14, 8)
        row.setSpacing(10)
        self._path_label = QLabel("")
        self._path_label.setObjectName("HintText")
        row.addWidget(self._path_label)
        row.addStretch(1)
        reload_btn = QPushButton("Reload")
        reload_btn.clicked.connect(self.reload)
        row.addWidget(reload_btn)
        save_btn = QPushButton("Save")
        save_btn.setObjectName("PrimaryButton")
        save_btn.clicked.connect(self.save)
        row.addWidget(save_btn)
        return bar

    # ---- Helpers --------------------------------------------------------

    def _cap(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("HintText")
        return label

    @staticmethod
    def _select_data(combo: QComboBox, data: Any) -> None:
        idx = combo.findData(data)
        if idx >= 0:
            combo.setCurrentIndex(idx)

    def _browse_into(self, edit: QWidget) -> None:
        start = edit.text() or os.path.expanduser("~")
        path, _ = QFileDialog.getOpenFileName(self, "Select file", start)
        if path:
            edit.setText(path)

    # ---- Load / save ----------------------------------------------------

    def reload(self) -> None:
        """Read ``config.json`` from disk into the form (best-effort)."""
        self._path_label.setText(self._config_path)
        try:
            with open(self._config_path, "r", encoding="utf-8") as fh:
                self._raw = json.load(fh)
        except FileNotFoundError:
            self._raw = {}
            self.status_message.emit("No config.json yet — fill in fields and Save to create it.")
        except (json.JSONDecodeError, OSError) as exc:
            self._raw = {}
            self.status_message.emit(f"Could not read config.json: {exc}")
            return

        for path, kind in _FIELDS:
            widget = self._widgets.get(path)
            if widget is None:
                continue
            value = _dig(self._raw, path)
            self._set_widget_value(widget, kind, value)

    def save(self) -> None:
        """Collect the form into ``config.json``, preserving untouched keys."""
        for path, kind in _FIELDS:
            widget = self._widgets.get(path)
            if widget is None:
                continue
            _bury(self._raw, path, self._get_widget_value(widget, kind))

        try:
            os.makedirs(os.path.dirname(os.path.abspath(self._config_path)), exist_ok=True)
            with open(self._config_path, "w", encoding="utf-8") as fh:
                json.dump(self._raw, fh, indent=2, ensure_ascii=False)
        except OSError as exc:
            self.status_message.emit(f"Failed to save config: {exc}")
            return

        self.status_message.emit("Settings saved — changes apply on next Start.")
        self.config_saved.emit(dict(self._raw))

    # ---- Widget <-> value -----------------------------------------------

    def _set_widget_value(self, widget: QWidget, kind: str, value: Any) -> None:
        if kind == "bool":
            widget.setChecked(bool(value))
        elif kind.startswith("int"):
            try:
                widget.setValue(int(value))
            except (TypeError, ValueError):
                pass
        else:  # text / secret
            widget.setText("" if value is None else str(value))

    def _get_widget_value(self, widget: QWidget, kind: str) -> Any:
        if kind == "bool":
            return widget.isChecked()
        if kind.startswith("int"):
            return widget.value()
        return widget.text()

    # ---- Slots ----------------------------------------------------------

    def _on_theme_changed(self) -> None:
        theme = self._theme_combo.currentData()
        self._store.set_theme(theme)
        self.theme_changed.emit(theme)
