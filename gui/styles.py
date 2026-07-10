"""Visual design tokens + QSS stylesheet for the Left4Translate desktop GUI.

The palette and typography are deliberately kept in lock-step with the
companion *L4D2 Game Finder* app so the two tools feel like a matched set:
a dark surface with an L4D2-flavoured orange accent and Segoe UI text.

The dark theme owns the visual personality; System / Light fall back to Qt's
Fusion defaults (see :mod:`gui.theme`).
"""

from __future__ import annotations


# ---- Color tokens ---------------------------------------------------------
# Shared with l4d2gamefinder so both apps read as one product family.

BG_WINDOW = "#131316"
BG_PANEL = "#1a1a1f"
BG_CARD = "#1f1f26"
BG_HOVER = "#26262e"
BG_STRIPE = "#1c1c22"

BORDER = "#2e2e38"
BORDER_HI = "#3d3d4d"

ACCENT = "#e05a2b"
ACCENT_HOVER = "#f06535"
ACCENT_DIM = "#7a2e12"

GREEN = "#3dba6f"
YELLOW = "#d4a339"
RED = "#e05252"
BLUE = "#4a9fd4"

TEXT_PRIMARY = "#e8e8ec"
TEXT_SECONDARY = "#8888a0"
TEXT_DIM = "#55556a"

# Team accent colors for the live feed (mirrors the on-screen styling intent:
# survivors read "friendly", infected read "hostile").
TEAM_SURVIVOR = "#5aa9e6"
TEAM_INFECTED = "#e05252"
VOICE_ACCENT = "#b07cf0"


def status_dot_color(state: str) -> str:
    """Map an engine/component status string to a hex color.

    ``state`` is one of: idle / stopped / running / monitoring / armed /
    connected / disconnected / error.
    """
    return {
        "running": GREEN,
        "monitoring": GREEN,
        "armed": GREEN,
        "connected": GREEN,
        "starting": YELLOW,
        "recording": YELLOW,
        "transcribing": YELLOW,
        "disconnected": YELLOW,
        "error": RED,
    }.get(state, TEXT_DIM)


def team_color(team: str | None) -> str:
    """Return the accent color for a chat team, or the neutral primary text."""
    if not team:
        return TEXT_PRIMARY
    low = team.lower()
    if low.startswith("surv"):
        return TEAM_SURVIVOR
    if low.startswith("inf"):
        return TEAM_INFECTED
    return TEXT_PRIMARY


# ---- Stylesheet -----------------------------------------------------------
# One template, two token sets: the dark theme owns the visual personality,
# and the light theme mirrors it so switching themes doesn't drop half the
# styling back to bare Fusion defaults.

_QSS_TEMPLATE = """
QWidget {{
    background: {BG_WINDOW};
    color: {TEXT_PRIMARY};
    font-family: "Segoe UI", "Inter", system-ui, sans-serif;
    font-size: 13px;
}}

QMainWindow, QDialog {{
    background: {BG_WINDOW};
}}

/* ---- Tabs ---- */
QTabWidget::pane {{
    border: none;
    background: {BG_WINDOW};
}}
QTabBar {{
    background: {BG_PANEL};
    border-bottom: 1px solid {BORDER};
}}
QTabBar::tab {{
    background: {BG_PANEL};
    color: {TEXT_SECONDARY};
    padding: 9px 16px;
    margin: 0;
    border: none;
    border-bottom: 2px solid transparent;
    min-width: 72px;
}}
QTabBar::tab:hover {{
    color: {TEXT_PRIMARY};
}}
QTabBar::tab:selected {{
    color: {TEXT_PRIMARY};
    font-weight: 600;
    border-bottom: 2px solid {ACCENT};
}}

/* ---- Tables ---- */
QTableView, QTableWidget {{
    background: {BG_WINDOW};
    alternate-background-color: {BG_STRIPE};
    color: {TEXT_PRIMARY};
    gridline-color: transparent;
    border: none;
    selection-background-color: {ACCENT_DIM};
    selection-color: {TEXT_PRIMARY};
}}
QTableView::item {{
    padding: 6px 10px;
    border: none;
}}
QTableView::item:hover {{
    background: {BG_HOVER};
}}
QHeaderView::section {{
    background: {BG_CARD};
    color: {TEXT_SECONDARY};
    padding: 7px 10px;
    border: none;
    border-bottom: 1px solid {BORDER};
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
}}
QHeaderView::section:hover {{
    color: {TEXT_PRIMARY};
}}

/* ---- Toolbars / panels ---- */
QToolBar, #ControlsBar, #HeaderBar {{
    background: {BG_PANEL};
    border: none;
    border-bottom: 1px solid {BORDER};
    spacing: 10px;
    padding: 8px 14px;
}}

/* ---- Buttons ---- */
QPushButton {{
    background: {BG_CARD};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 6px 14px;
    font-weight: 600;
}}
QPushButton:hover {{
    border-color: {BORDER_HI};
    background: {BG_HOVER};
}}
QPushButton:pressed {{
    background: {BG_PANEL};
}}
QPushButton:disabled {{
    color: {TEXT_DIM};
    background: {BG_PANEL};
}}

QPushButton#PrimaryButton {{
    background: {ACCENT};
    color: white;
    border: 1px solid {ACCENT};
    padding: 7px 20px;
}}
QPushButton#PrimaryButton:hover {{
    background: {ACCENT_HOVER};
    border-color: {ACCENT_HOVER};
}}
QPushButton#PrimaryButton:disabled {{
    background: {ACCENT_DIM};
    border-color: {ACCENT_DIM};
    color: {TEXT_DIM};
}}

QPushButton#DangerButton {{
    background: {RED};
    color: white;
    border: 1px solid {RED};
    padding: 7px 20px;
}}
QPushButton#DangerButton:hover {{
    background: #ef6b6b;
    border-color: #ef6b6b;
}}

/* ---- Inputs ---- */
QLineEdit, QSpinBox, QComboBox {{
    background: {BG_CARD};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 5px 8px;
    selection-background-color: {ACCENT_DIM};
}}
QLineEdit:focus, QSpinBox:focus, QComboBox:focus {{
    border-color: {ACCENT};
}}
QLineEdit:read-only {{
    color: {TEXT_SECONDARY};
    background: {BG_PANEL};
}}
QSpinBox::up-button, QSpinBox::down-button {{
    background: {BG_CARD};
    border: none;
    width: 16px;
}}
QSpinBox::up-button:hover, QSpinBox::down-button:hover {{
    background: {BG_HOVER};
}}
QComboBox::drop-down {{
    border: none;
    width: 18px;
}}
QComboBox QAbstractItemView {{
    background: {BG_CARD};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER_HI};
    selection-background-color: {ACCENT_DIM};
}}

/* ---- Progress bar (audio level meter) ---- */
QProgressBar {{
    background: {BORDER};
    border: none;
    border-radius: 3px;
    text-align: center;
    color: {TEXT_SECONDARY};
    max-height: 8px;
    min-height: 8px;
}}
QProgressBar::chunk {{
    background: {ACCENT};
    border-radius: 3px;
}}

/* ---- Status bar ---- */
QStatusBar {{
    background: {BG_PANEL};
    color: {TEXT_DIM};
    border-top: 1px solid {BORDER};
    padding: 2px 14px;
    font-size: 11px;
}}
QStatusBar::item {{
    border: none;
}}

/* ---- GroupBox (Settings sections) ---- */
QGroupBox {{
    background: transparent;
    border: none;
    border-top: 1px solid {BORDER};
    margin-top: 22px;
    padding-top: 14px;
    font-size: 11px;
    font-weight: 700;
    color: {TEXT_DIM};
    text-transform: uppercase;
    letter-spacing: 1px;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 0 6px 0;
    background: transparent;
}}

/* ---- Checkboxes ---- */
QCheckBox {{
    color: {TEXT_SECONDARY};
    spacing: 8px;
}}
QCheckBox::indicator {{
    width: 16px;
    height: 16px;
    border-radius: 3px;
    border: 2px solid {BORDER_HI};
    background: transparent;
}}
QCheckBox::indicator:hover {{
    border-color: {TEXT_SECONDARY};
}}
QCheckBox::indicator:checked {{
    background: {ACCENT};
    border-color: {ACCENT};
    image: url(:/qt-project.org/styles/commonstyle/images/standardbutton-apply-16.png);
}}

/* ---- Scrollbars ---- */
QScrollBar:vertical {{
    background: {BG_WINDOW};
    width: 10px;
    margin: 0;
    border: none;
}}
QScrollBar::handle:vertical {{
    background: {BORDER};
    border-radius: 4px;
    min-height: 24px;
}}
QScrollBar::handle:vertical:hover {{
    background: {BORDER_HI};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
    background: none;
}}
QScrollBar:horizontal {{
    background: {BG_WINDOW};
    height: 10px;
    margin: 0;
    border: none;
}}
QScrollBar::handle:horizontal {{
    background: {BORDER};
    border-radius: 4px;
    min-width: 24px;
}}
QScrollBar::handle:horizontal:hover {{
    background: {BORDER_HI};
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0;
    background: none;
}}

/* ---- Menu (tray + context menus) ---- */
QMenu {{
    background: {BG_CARD};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER_HI};
    border-radius: 8px;
    padding: 4px 0;
}}
QMenu::item {{
    padding: 7px 18px;
    background: transparent;
}}
QMenu::item:selected {{
    background: {BG_HOVER};
}}
QMenu::separator {{
    height: 1px;
    background: {BORDER};
    margin: 4px 6px;
}}

/* ---- Header bar (control strip) ---- */
QWidget#HeaderBar QLabel#AppTitle {{
    font-size: 14px;
    font-weight: 700;
    color: {TEXT_PRIMARY};
}}
QLabel#StatusPill {{
    font-size: 12px;
    font-weight: 600;
    padding: 0 6px;
}}

/* ---- Stat cards (Dashboard) ---- */
QFrame#StatCard {{
    background: {BG_CARD};
    border: 1px solid {BORDER};
    border-radius: 10px;
}}
QFrame#StatCard QLabel#StatValue {{
    font-size: 26px;
    font-weight: 700;
    color: {TEXT_PRIMARY};
}}
QFrame#StatCard QLabel#StatLabel {{
    font-size: 11px;
    font-weight: 600;
    color: {TEXT_SECONDARY};
    text-transform: uppercase;
    letter-spacing: 1px;
}}
QFrame#StatCard QLabel#StatAccent {{
    color: {ACCENT};
}}

/* ---- Section titles ---- */
QLabel#SectionTitle {{
    font-size: 11px;
    font-weight: 700;
    color: {TEXT_DIM};
    text-transform: uppercase;
    letter-spacing: 1px;
}}
QLabel#HintText {{
    color: {TEXT_SECONDARY};
    font-size: 12px;
}}
QLabel#EmptyHint {{
    color: {TEXT_DIM};
    font-size: 13px;
    background: transparent;
}}
"""

_DARK_TOKENS = {
    "BG_WINDOW": BG_WINDOW,
    "BG_PANEL": BG_PANEL,
    "BG_CARD": BG_CARD,
    "BG_HOVER": BG_HOVER,
    "BG_STRIPE": BG_STRIPE,
    "BORDER": BORDER,
    "BORDER_HI": BORDER_HI,
    "ACCENT": ACCENT,
    "ACCENT_HOVER": ACCENT_HOVER,
    "ACCENT_DIM": ACCENT_DIM,
    "RED": RED,
    "TEXT_PRIMARY": TEXT_PRIMARY,
    "TEXT_SECONDARY": TEXT_SECONDARY,
    "TEXT_DIM": TEXT_DIM,
}

# Light counterparts of the dark tokens; the orange accent carries over.
LIGHT_BG_WINDOW = "#f5f5f7"
LIGHT_TEXT_PRIMARY = "#1d1d24"

_LIGHT_TOKENS = {
    "BG_WINDOW": LIGHT_BG_WINDOW,
    "BG_PANEL": "#ececf0",
    "BG_CARD": "#ffffff",
    "BG_HOVER": "#e4e4ea",
    "BG_STRIPE": "#efeff3",
    "BORDER": "#d5d5de",
    "BORDER_HI": "#bcbcc8",
    "ACCENT": ACCENT,
    "ACCENT_HOVER": ACCENT_HOVER,
    "ACCENT_DIM": "#f3cdbd",
    "RED": RED,
    "TEXT_PRIMARY": LIGHT_TEXT_PRIMARY,
    "TEXT_SECONDARY": "#5a5a6e",
    "TEXT_DIM": "#8a8a9a",
}

DARK_QSS = _QSS_TEMPLATE.format(**_DARK_TOKENS)
LIGHT_QSS = _QSS_TEMPLATE.format(**_LIGHT_TOKENS)
