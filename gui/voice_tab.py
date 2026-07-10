"""Voice tab — push-to-talk status, mic level, and the last voice translation.

Voice translation is hold-a-mouse-button → record → transcribe → translate.
This tab surfaces that pipeline: whether it's armed, the configured trigger /
device / target language, the level of the last captured clip, and the most
recent transcription → translation result.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QVBoxLayout,
    QWidget,
)

from gui.engine_controller import EngineController
from gui.styles import VOICE_ACCENT
from gui.widgets import StatusPill

# Map a useful slice of the dBFS range onto the meter.
_DB_FLOOR = -60.0
_DB_CEIL = 0.0


class VoiceTab(QWidget):
    """Live status for the push-to-talk voice translation feature."""

    def __init__(self, controller: EngineController, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._controller = controller

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(16)

        root.addWidget(self._build_status_card())
        root.addWidget(self._build_config_card())
        root.addWidget(self._build_last_card(), stretch=1)

        self._timer = QTimer(self)
        self._timer.setInterval(500)
        self._timer.timeout.connect(self._refresh_level)
        self._timer.start()

    # ---- Construction ---------------------------------------------------

    def _card(self, title: str) -> tuple[QFrame, QVBoxLayout]:
        frame = QFrame()
        frame.setObjectName("StatCard")
        lay = QVBoxLayout(frame)
        lay.setContentsMargins(16, 14, 16, 16)
        lay.setSpacing(10)
        label = QLabel(title.upper())
        label.setObjectName("SectionTitle")
        lay.addWidget(label)
        return frame, lay

    def _build_status_card(self) -> QFrame:
        frame, lay = self._card("Status")
        self._pill = StatusPill("Voice idle")
        self._pill.setObjectName("StatusPill")
        lay.addWidget(self._pill)

        level_row = QHBoxLayout()
        level_row.setSpacing(10)
        caption = QLabel("Last mic level")
        caption.setObjectName("HintText")
        level_row.addWidget(caption)
        self._meter = QProgressBar()
        self._meter.setRange(0, 100)
        self._meter.setValue(0)
        self._meter.setTextVisible(False)
        level_row.addWidget(self._meter, stretch=1)
        self._level_label = QLabel("—")
        self._level_label.setObjectName("HintText")
        self._level_label.setMinimumWidth(64)
        self._level_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        level_row.addWidget(self._level_label)
        lay.addLayout(level_row)
        return frame

    def _build_config_card(self) -> QFrame:
        frame, lay = self._card("Configuration")
        form = QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)
        form.setSpacing(8)
        self._lbl_trigger = QLabel("—")
        self._lbl_device = QLabel("—")
        self._lbl_target = QLabel("—")
        self._lbl_clipboard = QLabel("—")
        for label, value in (
            ("Trigger button", self._lbl_trigger),
            ("Microphone", self._lbl_device),
            ("Target language", self._lbl_target),
            ("Auto-copy", self._lbl_clipboard),
        ):
            cap = QLabel(label)
            cap.setObjectName("HintText")
            form.addRow(cap, value)
        lay.addLayout(form)
        return frame

    def _build_last_card(self) -> QFrame:
        frame, lay = self._card("Last Voice Translation")
        self._last_original = QLabel("No voice translation yet.")
        self._last_original.setWordWrap(True)
        self._last_original.setObjectName("HintText")
        self._last_translated = QLabel("")
        self._last_translated.setWordWrap(True)
        self._last_translated.setStyleSheet(
            f"color: {VOICE_ACCENT}; font-size: 15px; font-weight: 600;"
        )
        lay.addWidget(self._last_original)
        lay.addWidget(self._last_translated)
        lay.addStretch(1)
        return frame

    # ---- Public slots ---------------------------------------------------

    def set_config(self, config: Dict[str, Any]) -> None:
        """Refresh the displayed configuration (called on load and after save)."""
        vt = (config or {}).get("voice_translation", {})
        trigger = vt.get("trigger_button", {}).get("button", "—")
        device = vt.get("audio", {}).get("device", "—")
        target = vt.get("translation", {}).get("target_language", "—")
        clipboard = vt.get("clipboard", {}).get("auto_copy", False)
        enabled = vt.get("enabled", True)
        self._lbl_trigger.setText(str(trigger))
        self._lbl_device.setText(str(device))
        self._lbl_target.setText(str(target))
        self._lbl_clipboard.setText("On" if clipboard else "Off")
        if not enabled:
            self._pill.set_state("idle", "Voice disabled in config")

    def set_status(self, state: str, detail: str = "") -> None:
        text = {
            "armed": "Armed — hold trigger to talk",
            "recording": "Recording…",
            "error": detail or "Voice error",
            "idle": "Voice idle",
        }.get(state, detail or state.capitalize())
        self._pill.set_state(state, text)

    def add_voice_translation(self, payload: Dict[str, Any]) -> None:
        original = str(payload.get("original") or "")
        translated = str(payload.get("translated") or "")
        self._last_original.setText(f"“{original}”")
        self._last_translated.setText(f"→ {translated}")

    # ---- Timer ----------------------------------------------------------

    def _refresh_level(self) -> None:
        db = self._controller.last_audio_level_db()
        if db is None:
            return
        clamped = max(_DB_FLOOR, min(_DB_CEIL, db))
        pct = int((clamped - _DB_FLOOR) / (_DB_CEIL - _DB_FLOOR) * 100)
        self._meter.setValue(pct)
        self._level_label.setText(f"{db:.0f} dB")
