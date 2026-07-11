"""Typed accessors for persistent GUI preferences (QSettings-backed).

These are *app/window* preferences (theme, tray behaviour, last mode, window
geometry) — distinct from the translation engine's ``config.json``, which the
Settings tab edits directly. Tests can pass a fresh ``QSettings`` pointing at a
tmp_path-backed INI file.
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QByteArray, QSettings


THEME_SYSTEM = "system"
THEME_DARK = "dark"
THEME_LIGHT = "light"
THEMES = (THEME_SYSTEM, THEME_DARK, THEME_LIGHT)

MODES = ("chat", "voice", "both")


def _coerce_bool(value, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() in ("1", "true", "yes", "on")
    if isinstance(value, (int, float)):
        return bool(value)
    return default


class SettingsStore:
    """Strongly-typed facade over QSettings."""

    KEY_THEME = "appearance/theme"
    KEY_MODE = "engine/mode"
    KEY_AUTOSTART = "engine/autostart"
    KEY_MINIMIZE_TO_TRAY = "tray/minimize_on_close"
    KEY_START_MINIMIZED = "tray/start_minimized"
    KEY_GEOMETRY = "window/geometry"
    KEY_WINDOW_STATE = "window/state"
    KEY_OVERLAY_VISIBLE = "overlay/visible"
    KEY_OVERLAY_GEOMETRY = "overlay/geometry"
    KEY_OVERLAY_OPACITY = "overlay/opacity"
    KEY_OVERLAY_FONT_SIZE = "overlay/font_size"

    DEFAULT_THEME = THEME_DARK
    DEFAULT_MODE = "both"
    DEFAULT_AUTOSTART = True
    DEFAULT_MINIMIZE_TO_TRAY = True
    DEFAULT_START_MINIMIZED = False
    DEFAULT_OVERLAY_VISIBLE = False
    DEFAULT_OVERLAY_OPACITY = 0.9
    DEFAULT_OVERLAY_FONT_SIZE = 13

    def __init__(self, qsettings: Optional[QSettings] = None) -> None:
        self._settings = qsettings if qsettings is not None else QSettings()

    @property
    def raw(self) -> QSettings:
        return self._settings

    # ---- Appearance -----------------------------------------------------

    def theme(self) -> str:
        value = str(self._settings.value(self.KEY_THEME, self.DEFAULT_THEME))
        return value if value in THEMES else self.DEFAULT_THEME

    def set_theme(self, value: str) -> None:
        if value not in THEMES:
            raise ValueError(f"Unknown theme: {value!r}; expected one of {THEMES}")
        self._settings.setValue(self.KEY_THEME, value)

    # ---- Engine ---------------------------------------------------------

    def mode(self) -> str:
        value = str(self._settings.value(self.KEY_MODE, self.DEFAULT_MODE))
        return value if value in MODES else self.DEFAULT_MODE

    def set_mode(self, value: str) -> None:
        if value not in MODES:
            raise ValueError(f"Unknown mode: {value!r}; expected one of {MODES}")
        self._settings.setValue(self.KEY_MODE, value)

    def autostart(self) -> bool:
        return _coerce_bool(
            self._settings.value(self.KEY_AUTOSTART, self.DEFAULT_AUTOSTART),
            self.DEFAULT_AUTOSTART,
        )

    def set_autostart(self, value: bool) -> None:
        self._settings.setValue(self.KEY_AUTOSTART, bool(value))

    # ---- Tray behaviour -------------------------------------------------

    def minimize_to_tray(self) -> bool:
        return _coerce_bool(
            self._settings.value(self.KEY_MINIMIZE_TO_TRAY, self.DEFAULT_MINIMIZE_TO_TRAY),
            self.DEFAULT_MINIMIZE_TO_TRAY,
        )

    def set_minimize_to_tray(self, value: bool) -> None:
        self._settings.setValue(self.KEY_MINIMIZE_TO_TRAY, bool(value))

    def start_minimized(self) -> bool:
        return _coerce_bool(
            self._settings.value(self.KEY_START_MINIMIZED, self.DEFAULT_START_MINIMIZED),
            self.DEFAULT_START_MINIMIZED,
        )

    def set_start_minimized(self, value: bool) -> None:
        self._settings.setValue(self.KEY_START_MINIMIZED, bool(value))

    # ---- Window geometry ------------------------------------------------

    def geometry(self) -> Optional[QByteArray]:
        value = self._settings.value(self.KEY_GEOMETRY)
        return value if isinstance(value, QByteArray) and not value.isEmpty() else None

    def set_geometry(self, value: QByteArray) -> None:
        self._settings.setValue(self.KEY_GEOMETRY, value)

    def window_state(self) -> Optional[QByteArray]:
        value = self._settings.value(self.KEY_WINDOW_STATE)
        return value if isinstance(value, QByteArray) and not value.isEmpty() else None

    def set_window_state(self, value: QByteArray) -> None:
        self._settings.setValue(self.KEY_WINDOW_STATE, value)

    # ---- Overlay window -------------------------------------------------

    def overlay_visible(self) -> bool:
        return _coerce_bool(
            self._settings.value(self.KEY_OVERLAY_VISIBLE, self.DEFAULT_OVERLAY_VISIBLE),
            self.DEFAULT_OVERLAY_VISIBLE,
        )

    def set_overlay_visible(self, value: bool) -> None:
        self._settings.setValue(self.KEY_OVERLAY_VISIBLE, bool(value))

    def overlay_geometry(self) -> Optional[QByteArray]:
        value = self._settings.value(self.KEY_OVERLAY_GEOMETRY)
        return value if isinstance(value, QByteArray) and not value.isEmpty() else None

    def set_overlay_geometry(self, value: QByteArray) -> None:
        self._settings.setValue(self.KEY_OVERLAY_GEOMETRY, value)

    def overlay_opacity(self) -> float:
        try:
            value = float(self._settings.value(self.KEY_OVERLAY_OPACITY, self.DEFAULT_OVERLAY_OPACITY))
        except (TypeError, ValueError):
            return self.DEFAULT_OVERLAY_OPACITY
        return min(1.0, max(0.3, value))

    def set_overlay_opacity(self, value: float) -> None:
        self._settings.setValue(self.KEY_OVERLAY_OPACITY, float(value))

    def overlay_font_size(self) -> int:
        try:
            value = int(self._settings.value(self.KEY_OVERLAY_FONT_SIZE, self.DEFAULT_OVERLAY_FONT_SIZE))
        except (TypeError, ValueError):
            return self.DEFAULT_OVERLAY_FONT_SIZE
        return min(24, max(9, value))

    def set_overlay_font_size(self, value: int) -> None:
        self._settings.setValue(self.KEY_OVERLAY_FONT_SIZE, int(value))
