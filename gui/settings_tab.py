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
import shutil
import threading
from typing import Any, Callable, Dict, List, Optional, Tuple

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
from gui.widgets import NoScrollComboBox, NoScrollSpinBox

# ---- Choice presets for the dropdown fields -------------------------------
# (value, label) pairs. Editable combos accept free text for exotic values.

_LANGS: List[Tuple[str, str]] = [
    ("en", "en — English"), ("es", "es — Spanish"), ("fr", "fr — French"),
    ("de", "de — German"), ("pt", "pt — Portuguese"), ("it", "it — Italian"),
    ("ru", "ru — Russian"), ("ja", "ja — Japanese"), ("ko", "ko — Korean"),
    ("zh", "zh — Chinese"), ("pl", "pl — Polish"), ("tr", "tr — Turkish"),
    ("ar", "ar — Arabic"), ("nl", "nl — Dutch"), ("sv", "sv — Swedish"),
]

_SPEECH_LANGS: List[Tuple[str, str]] = [
    ("en-US", "en-US — English (US)"), ("en-GB", "en-GB — English (UK)"),
    ("es-ES", "es-ES — Spanish (Spain)"), ("es-MX", "es-MX — Spanish (Mexico)"),
    ("fr-FR", "fr-FR — French"), ("de-DE", "de-DE — German"),
    ("pt-BR", "pt-BR — Portuguese (Brazil)"), ("it-IT", "it-IT — Italian"),
    ("ru-RU", "ru-RU — Russian"), ("ja-JP", "ja-JP — Japanese"),
    ("ko-KR", "ko-KR — Korean"), ("pl-PL", "pl-PL — Polish"),
    ("tr-TR", "tr-TR — Turkish"), ("nl-NL", "nl-NL — Dutch"),
]

# The only values MouseHandler accepts (src/input/mouse_handler.py); free text
# used to silently fall back to button4 on any typo.
_TRIGGER_BUTTONS: List[Tuple[str, str]] = [
    ("button4", "button4 — side/forward"),
    ("button5", "button5 — side/back"),
    ("middle", "middle"),
    ("right", "right"),
    ("left", "left"),
]

_CLIPBOARD_FORMATS: List[Tuple[str, str]] = [
    ("translated", "translated only"),
    ("original", "original only"),
    ("both", "original + translated"),
]

_SPEECH_MODELS: List[Tuple[str, str]] = [
    ("default", "default"),
    ("command_and_search", "command_and_search — short phrases"),
    ("latest_short", "latest_short"),
    ("latest_long", "latest_long"),
    ("phone_call", "phone_call"),
    ("video", "video"),
]


def _com_ports() -> List[Tuple[str, str]]:
    """Enumerate serial ports; empty when pyserial or hardware is absent."""
    try:
        from serial.tools import list_ports

        return [
            (p.device, f"{p.device} — {p.description}")
            for p in sorted(list_ports.comports(), key=lambda p: p.device)
        ]
    except Exception:
        return []


def _input_devices() -> List[Tuple[str, str]]:
    """Enumerate audio input devices; 'default' is always offered."""
    devices: List[Tuple[str, str]] = [("default", "default")]
    try:
        import sounddevice as sd

        for index, dev in enumerate(sd.query_devices()):
            if dev.get("max_input_channels", 0) > 0:
                devices.append((dev["name"], f"{dev['name']}  (#{index})"))
    except Exception:
        pass
    return devices


# Choice presets: name -> (options-provider, editable, refreshable)
_CHOICES: Dict[str, Tuple[Callable[[], List[Tuple[str, str]]], bool, bool]] = {
    "lang": (lambda: _LANGS, True, False),
    "speechlang": (lambda: _SPEECH_LANGS, True, False),
    "trigger": (lambda: _TRIGGER_BUTTONS, False, False),
    "clipformat": (lambda: _CLIPBOARD_FORMATS, False, False),
    "speechmodel": (lambda: _SPEECH_MODELS, False, False),
    "ports": (_com_ports, True, True),
    "miclist": (_input_devices, True, True),
}

# (config dotted-path, kind) for each engine-config field the form exposes.
# kind drives how the widget is read/written: text / int / bool.
_FIELDS: List[Tuple[str, str]] = [
    ("game.logPath", "text"),
    ("game.pollInterval", "int"),
    ("translation.apiKey", "secret"),
    ("translation.targetLanguage", "choice:lang"),
    ("translation.cacheSize", "int"),
    ("translation.rateLimitPerMinute", "int"),
    ("screen.enabled", "bool"),
    ("screen.port", "choice:ports"),
    ("screen.baudRate", "int"),
    ("screen.brightness", "int"),
    ("screen.display.maxMessages", "int"),
    ("screen.display.messageTimeout", "int"),
    ("voice_translation.enabled", "bool"),
    ("voice_translation.trigger_button.button", "choice:trigger"),
    ("voice_translation.audio.device", "choice:miclist"),
    ("voice_translation.translation.target_language", "choice:lang"),
    ("voice_translation.speech_to_text.language", "choice:speechlang"),
    ("voice_translation.speech_to_text.model", "choice:speechmodel"),
    ("voice_translation.speech_to_text.credentials_path", "text"),
    ("voice_translation.clipboard.auto_copy", "bool"),
    ("voice_translation.clipboard.format", "choice:clipformat"),
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
    # Diagnostics workers emit their outcome here (marshalled to GUI thread).
    _diag_done = Signal(str)

    def __init__(self, config_path: str, store: SettingsStore,
                 parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._config_path = config_path
        self._store = store
        self._raw: Dict[str, Any] = {}
        self._widgets: Dict[str, QWidget] = {}
        self._load_failed = False
        self._engine_running = False

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
            ("translation.targetLanguage", "Target language", "choice:lang"),
            ("translation.cacheSize", "Cache size", "int:0:100000"),
            ("translation.rateLimitPerMinute", "Rate limit / min", "int:1:100000"),
        ]))
        self._form_root.addWidget(self._group("Turing Screen", [
            ("screen.enabled", "Use hardware Turing screen (uncheck to use the overlay only)", "bool"),
            ("screen.port", "Serial port", "choice:ports"),
            ("screen.baudRate", "Baud rate", "int:9600:1000000"),
            ("screen.brightness", "Brightness", "int:0:100"),
            ("screen.display.maxMessages", "Max messages", "int:1:50"),
            ("screen.display.messageTimeout", "Message timeout (ms, 0=keep)", "int:0:600000"),
        ]))
        self._form_root.addWidget(self._group("Voice Translation", [
            ("voice_translation.enabled", "Enable voice translation", "bool"),
            ("voice_translation.trigger_button.button", "Trigger button", "choice:trigger"),
            ("voice_translation.audio.device", "Microphone device", "choice:miclist"),
            ("voice_translation.translation.target_language", "Voice target language", "choice:lang"),
            ("voice_translation.speech_to_text.language", "Speech language", "choice:speechlang"),
            ("voice_translation.speech_to_text.model", "Speech model", "choice:speechmodel"),
            ("voice_translation.speech_to_text.credentials_path", "Google credentials JSON", "browse_file"),
            ("voice_translation.clipboard.auto_copy", "Auto-copy translation", "bool"),
            ("voice_translation.clipboard.format", "Clipboard contents", "choice:clipformat"),
        ]))
        self._form_root.addWidget(self._diagnostics_group())
        self._form_root.addStretch(1)

    def _app_prefs_group(self) -> QGroupBox:
        box = QGroupBox("Application")
        form = QFormLayout(box)
        form.setContentsMargins(0, 10, 0, 0)
        form.setSpacing(8)

        self._theme_combo = NoScrollComboBox()
        for label, value in (("System", THEME_SYSTEM), ("Dark", THEME_DARK), ("Light", THEME_LIGHT)):
            self._theme_combo.addItem(label, value)
        self._select_data(self._theme_combo, self._store.theme())
        self._theme_combo.currentIndexChanged.connect(self._on_theme_changed)
        form.addRow(self._cap("Theme"), self._theme_combo)

        self._mode_combo = NoScrollComboBox()
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
            elif kind.startswith("choice:"):
                name = kind.split(":", 1)[1]
                provider, _editable, refreshable = _CHOICES[name]
                if refreshable:
                    form.addRow(self._cap(label), self._with_refresh(widget, provider))
                else:
                    form.addRow(self._cap(label), widget)
            else:
                form.addRow(self._cap(label), widget)
        return box

    def _with_refresh(self, combo: QComboBox, provider) -> QWidget:
        wrap = QWidget()
        row = QHBoxLayout(wrap)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(6)
        row.addWidget(combo, stretch=1)
        button = QPushButton("↻")
        button.setFixedWidth(32)
        button.setToolTip("Re-scan available devices")
        button.clicked.connect(lambda: self._fill_combo(combo, provider()))
        row.addWidget(button)
        return wrap

    def _make_widget(self, path: str, kind: str) -> QWidget:
        if kind == "bool":
            return QCheckBox()
        if kind == "secret":
            edit = QLineEdit()
            edit.setEchoMode(QLineEdit.EchoMode.Password)
            edit.setPlaceholderText("Google Cloud Translation API key")
            return edit
        if kind.startswith("int"):
            spin = NoScrollSpinBox()
            parts = kind.split(":")
            lo = int(parts[1]) if len(parts) > 1 else 0
            hi = int(parts[2]) if len(parts) > 2 else 1_000_000
            spin.setRange(lo, hi)
            return spin
        if kind.startswith("choice:"):
            provider, editable, _refreshable = _CHOICES[kind.split(":", 1)[1]]
            combo = NoScrollComboBox()
            combo.setEditable(editable)
            self._fill_combo(combo, provider())
            return combo
        edit = QLineEdit()
        if kind == "browse_file":
            edit.setPlaceholderText("Path…")
        return edit

    @staticmethod
    def _fill_combo(combo: QComboBox, options: List[Tuple[str, str]]) -> None:
        current = combo.currentText()
        combo.clear()
        for value, label in options:
            combo.addItem(label, value)
        if current:
            SettingsTab._set_combo_value(combo, current)

    @staticmethod
    def _set_combo_value(combo: QComboBox, value: str) -> None:
        if not value:
            # Nothing configured: keep the first preset selected (editable
            # combos clear their text so the stored value stays empty).
            if combo.isEditable():
                combo.setEditText("")
            return
        idx = combo.findData(value)
        if idx < 0:
            idx = combo.findText(value)
        if idx >= 0:
            combo.setCurrentIndex(idx)
        elif combo.isEditable():
            combo.setEditText(value)
        else:
            combo.addItem(value, value)
            combo.setCurrentIndex(combo.count() - 1)

    @staticmethod
    def _combo_value(combo: QComboBox) -> str:
        data = combo.currentData()
        # For a preset entry return its value; for free text the label IS the value.
        if data is not None and combo.currentText() == combo.itemText(combo.currentIndex()):
            return str(data)
        return combo.currentText().strip()

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
        self._save_btn = QPushButton("Save")
        self._save_btn.setObjectName("PrimaryButton")
        self._save_btn.clicked.connect(self.save)
        row.addWidget(self._save_btn)
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
        self._load_failed = False
        self._save_btn.setEnabled(True)
        try:
            with open(self._config_path, "r", encoding="utf-8") as fh:
                self._raw = json.load(fh)
        except FileNotFoundError:
            self._raw = {}
            self.status_message.emit("No config.json yet — fill in fields and Save to create it.")
        except (json.JSONDecodeError, OSError) as exc:
            # Saving now would rewrite the file with only the form's fields,
            # destroying everything else (messageFormat regex, logging, ...).
            # Block Save until the file parses again.
            self._raw = {}
            self._load_failed = True
            self._save_btn.setEnabled(False)
            self._save_btn.setToolTip(
                "Save is disabled: config.json could not be parsed. Fix the "
                "file (or restore config.json.bak) and press Reload."
            )
            self._path_label.setText(f"⚠ {self._config_path} — unreadable: {exc}")
            self.status_message.emit(
                f"config.json could not be parsed — Save disabled to protect the file: {exc}"
            )
            return
        self._save_btn.setToolTip("")

        for path, kind in _FIELDS:
            widget = self._widgets.get(path)
            if widget is None:
                continue
            value = _dig(self._raw, path)
            # Defaults for keys that may be absent in older configs, chosen so
            # a Save doesn't silently change behaviour.
            if value is None:
                value = {
                    "screen.enabled": True,
                    "voice_translation.speech_to_text.model": "default",
                    "voice_translation.clipboard.format": "translated",
                }.get(path)
            self._set_widget_value(widget, kind, value)

    def save(self) -> None:
        """Collect the form into ``config.json``, preserving untouched keys."""
        if self._load_failed:
            self.status_message.emit(
                "Not saving: config.json could not be parsed. Fix the file and press Reload first."
            )
            return

        for path, kind in _FIELDS:
            widget = self._widgets.get(path)
            if widget is None:
                continue
            _bury(self._raw, path, self._get_widget_value(widget, kind))

        try:
            os.makedirs(os.path.dirname(os.path.abspath(self._config_path)), exist_ok=True)
            # Keep a one-deep backup so a bad save is always recoverable.
            if os.path.exists(self._config_path):
                shutil.copy2(self._config_path, self._config_path + ".bak")
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
        elif kind.startswith("choice"):
            self._set_combo_value(widget, "" if value is None else str(value))
        else:  # text / secret
            widget.setText("" if value is None else str(value))

    def _get_widget_value(self, widget: QWidget, kind: str) -> Any:
        if kind == "bool":
            return widget.isChecked()
        if kind.startswith("int"):
            return widget.value()
        if kind.startswith("choice"):
            return self._combo_value(widget)
        return widget.text()

    # ---- Diagnostics ------------------------------------------------------

    def _diagnostics_group(self) -> QGroupBox:
        box = QGroupBox("Diagnostics")
        lay = QVBoxLayout(box)
        lay.setContentsMargins(0, 10, 0, 0)
        lay.setSpacing(8)

        row = QHBoxLayout()
        row.setSpacing(8)
        self._btn_test_translation = QPushButton("Test translation")
        self._btn_test_translation.setToolTip(
            "One round-trip to the Translation API with the key above"
        )
        self._btn_test_translation.clicked.connect(self._test_translation)
        self._btn_test_screen = QPushButton("Test screen")
        self._btn_test_screen.setToolTip(
            "Connect to the Turing screen on the configured port and show a splash"
        )
        self._btn_test_screen.clicked.connect(self._test_screen)
        self._btn_test_mic = QPushButton("Test microphone")
        self._btn_test_mic.setToolTip("Record 1.5s and report the level")
        self._btn_test_mic.clicked.connect(self._test_mic)
        for btn in (self._btn_test_translation, self._btn_test_screen, self._btn_test_mic):
            row.addWidget(btn)
        row.addStretch(1)
        lay.addLayout(row)

        self._diag_label = QLabel("")
        self._diag_label.setObjectName("HintText")
        self._diag_label.setWordWrap(True)
        lay.addWidget(self._diag_label)

        self._diag_done.connect(self._on_diag_done)
        return box

    def set_engine_running(self, running: bool) -> None:
        """Hardware diagnostics must not fight the engine over the serial
        port / microphone while it runs; the API test is always safe."""
        self._engine_running = running
        self._btn_test_screen.setEnabled(not running)
        self._btn_test_mic.setEnabled(not running)
        tip = "Stop the engine first" if running else ""
        self._btn_test_screen.setToolTip(tip or "Connect to the Turing screen on the configured port and show a splash")
        self._btn_test_mic.setToolTip(tip or "Record 1.5s and report the level")

    def _on_diag_done(self, message: str) -> None:
        self._diag_label.setText(message)
        self.status_message.emit(message)
        self._btn_test_translation.setEnabled(True)
        # Screen/mic buttons may be gated by a running engine; re-enable only
        # when they weren't disabled for that reason.
        if not self._engine_running:
            self._btn_test_screen.setEnabled(True)
            self._btn_test_mic.setEnabled(True)

    def _run_diagnostic(self, button: QPushButton, work) -> None:
        button.setEnabled(False)
        self._diag_label.setText("Working…")

        def _wrapped():
            try:
                self._diag_done.emit(work())
            except Exception as exc:  # surfaced, never raised into the GUI
                self._diag_done.emit(f"Failed: {exc}")

        threading.Thread(target=_wrapped, daemon=True).start()

    def _test_translation(self) -> None:
        api_key = self._widgets["translation.apiKey"].text().strip()
        target = self._combo_value(self._widgets["translation.targetLanguage"]) or "en"
        if not api_key:
            self._diag_label.setText("Enter a Google API key first.")
            return

        def work() -> str:
            from gui.engine_controller import _ensure_engine_importable

            _ensure_engine_importable()
            from translator.translation_service import TranslationService

            svc = TranslationService(api_key=api_key, target_language=target)
            translated, source = svc.translate_with_detection("hola amigo")
            return f"Translation OK: 'hola amigo' → '{translated}' (detected: {source})"

        self._run_diagnostic(self._btn_test_translation, work)

    def _test_screen(self) -> None:
        port = self._combo_value(self._widgets["screen.port"])
        baud = self._widgets["screen.baudRate"].value()
        brightness = self._widgets["screen.brightness"].value()
        if not port:
            self._diag_label.setText("Pick a serial port first.")
            return

        def work() -> str:
            from gui.engine_controller import _ensure_engine_importable

            _ensure_engine_importable()
            from display.screen_controller import ScreenController

            screen = ScreenController(port=port, baud_rate=baud, brightness=brightness)
            try:
                if screen.connect():
                    return f"Screen OK on {port} — splash shown."
                return f"Could not connect to a Turing screen on {port}."
            finally:
                try:
                    screen.disconnect()
                except Exception:
                    pass

        self._run_diagnostic(self._btn_test_screen, work)

    def _test_mic(self) -> None:
        device = self._combo_value(self._widgets["voice_translation.audio.device"])

        def work() -> str:
            import numpy as np
            import sounddevice as sd

            seconds, rate = 1.5, 16000
            kwargs = {} if device in ("", "default") else {"device": device}
            clip = sd.rec(int(seconds * rate), samplerate=rate, channels=1,
                          dtype="float32", **kwargs)
            sd.wait()
            rms = float(np.sqrt(np.mean(np.square(clip))))
            db = 20 * float(np.log10(rms)) if rms > 0 else -100.0
            if db < -50:
                verdict = "VERY LOW — check mute/levels in Windows sound settings"
            elif db < -40:
                verdict = "low — consider speaking closer or raising the level"
            else:
                verdict = "good"
            return f"Microphone level: {db:.1f} dB RMS ({verdict})."

        self._run_diagnostic(self._btn_test_mic, work)

    # ---- Slots ----------------------------------------------------------

    def _on_theme_changed(self) -> None:
        theme = self._theme_combo.currentData()
        self._store.set_theme(theme)
        self.theme_changed.emit(theme)
