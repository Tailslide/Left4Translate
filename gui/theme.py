"""Theme application: system / dark / light Fusion palettes + dark QSS.

Matches the approach used by the companion l4d2gamefinder app so the two
tools share one look. The dark palette is tuned to the tokens in
:mod:`gui.styles`; System / Light defer to Qt's Fusion defaults.
"""

from __future__ import annotations

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication, QStyleFactory

from gui.settings_store import THEME_DARK, THEME_LIGHT, THEME_SYSTEM, THEMES
from gui.styles import BG_WINDOW, DARK_QSS, TEXT_PRIMARY


def _dark_palette() -> QPalette:
    """Palette consistent with ``gui.styles.DARK_QSS`` for native widgets."""
    p = QPalette()
    win = QColor(BG_WINDOW)
    text = QColor(TEXT_PRIMARY)
    p.setColor(QPalette.ColorRole.Window, win)
    p.setColor(QPalette.ColorRole.WindowText, text)
    p.setColor(QPalette.ColorRole.Base, QColor("#1f1f26"))
    p.setColor(QPalette.ColorRole.AlternateBase, QColor("#1c1c22"))
    p.setColor(QPalette.ColorRole.ToolTipBase, QColor("#1f1f26"))
    p.setColor(QPalette.ColorRole.ToolTipText, text)
    p.setColor(QPalette.ColorRole.Text, text)
    p.setColor(QPalette.ColorRole.Button, QColor("#1f1f26"))
    p.setColor(QPalette.ColorRole.ButtonText, text)
    p.setColor(QPalette.ColorRole.BrightText, QColor("#e05252"))
    p.setColor(QPalette.ColorRole.Highlight, QColor("#e05a2b"))
    p.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
    p.setColor(QPalette.ColorRole.Link, QColor("#e05a2b"))
    p.setColor(
        QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, QColor("#55556a")
    )
    p.setColor(
        QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText, QColor("#55556a")
    )
    return p


def _fusion_light_palette() -> QPalette:
    return QStyleFactory.create("Fusion").standardPalette()


def apply_theme(app: QApplication, theme: str) -> str:
    """Apply ``theme`` to ``app``; returns the theme actually applied.

    Unknown theme names fall back to ``system`` so a corrupted settings file
    can't block startup.
    """
    if theme not in THEMES:
        theme = THEME_SYSTEM

    if theme == THEME_DARK:
        app.setStyle("Fusion")
        app.setPalette(_dark_palette())
        app.setStyleSheet(DARK_QSS)
    elif theme == THEME_LIGHT:
        app.setStyle("Fusion")
        app.setPalette(_fusion_light_palette())
        app.setStyleSheet("")
    else:  # system
        app.setPalette(app.style().standardPalette())
        app.setStyleSheet("")
    return theme
