"""Always-on-top translation overlay — a software stand-in for the Turing screen.

This frameless, semi-transparent window mirrors what would scroll across the
Turing Smart Screen, so the app is useful with no hardware at all. It is built
to float over a *borderless / windowed-fullscreen* game:

* ``WindowStaysOnTopHint`` keeps it above the game window,
* ``WA_ShowWithoutActivating`` (plus ``WS_EX_NOACTIVATE`` on Windows) means
  showing it — and even clicking its drag bar — never pulls keyboard focus
  away from Left 4 Dead 2.

It consumes the same ``on_translation`` payloads the dashboard feed does, so the
engine and its callbacks are completely unaware of it.

Note: a game running in *exclusive* (true) fullscreen will paint over every
top-most window, this one included. Run the game in borderless/windowed mode
for the overlay to be visible.
"""

from __future__ import annotations

import sys
from collections import deque
from html import escape
from typing import Any, Deque, Dict, Optional

from PySide6.QtCore import QPoint, Qt
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizeGrip,
    QVBoxLayout,
    QWidget,
)

from gui.settings_store import SettingsStore

# Colors mirror ScreenController's Turing palette so the overlay reads the same.
_PLAYER_COLOR = "#00BFFF"        # deep sky blue — regular chat names
_TEAM_PLAYER_COLOR = "#FFA500"   # orange — team chat names
_ORIGINAL_COLOR = "#FFFFFF"      # white — original text
_ARROW_COLOR = "#32CD32"         # lime green — the "→" arrow
_TRANSLATED_COLOR = "#90EE90"    # light green — translated text
_VOICE_COLOR = "#b07cf0"         # purple — voice transcriptions

_MAX_MESSAGES = 10               # rows kept on screen (newest on top)
_MIN_OPACITY = 0.30
_MAX_OPACITY = 1.0


class _MessageLabel(QLabel):
    """One translation rendered as rich text (player + original + translation)."""

    def __init__(self, html: str, parent: Optional[QWidget] = None) -> None:
        super().__init__(html, parent)
        self.setObjectName("OverlayMessage")
        self.setWordWrap(True)
        self.setTextFormat(Qt.TextFormat.RichText)
        self.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)


class OverlayWindow(QWidget):
    """Frameless, always-on-top mirror of the Turing screen output."""

    def __init__(
        self,
        store: Optional[SettingsStore] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        # No Qt parent: a top-level tool window that floats independently of the
        # main window (so it survives the main window being hidden to tray).
        super().__init__(None)
        self._store = store or SettingsStore()
        self._messages: Deque[str] = deque(maxlen=_MAX_MESSAGES)
        self._drag_offset: Optional[QPoint] = None
        self._opacity = self._store.overlay_opacity()
        self._font_size = self._store.overlay_font_size()
        self._click_through = False  # session-only; reset on every show

        self.setWindowTitle("Left4Translate Overlay")
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        # Show without grabbing focus from the game.
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setMinimumSize(220, 120)

        self._build_ui()
        self._apply_opacity()
        self._restore_geometry()

    # ---- Construction ---------------------------------------------------

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        self._panel = QFrame(self)
        self._panel.setObjectName("OverlayPanel")
        outer.addWidget(self._panel)

        panel = QVBoxLayout(self._panel)
        panel.setContentsMargins(2, 2, 2, 2)
        panel.setSpacing(2)

        panel.addWidget(self._build_title_bar())

        self._body = QWidget(self._panel)
        self._body.setObjectName("OverlayBody")
        self._body_layout = QVBoxLayout(self._body)
        self._body_layout.setContentsMargins(8, 6, 8, 6)
        self._body_layout.setSpacing(5)
        self._body_layout.addStretch(1)  # newest rows insert above this
        panel.addWidget(self._body, stretch=1)

        self._hint = QLabel("Waiting for translations…", self._body)
        self._hint.setObjectName("OverlayHint")
        self._body_layout.insertWidget(0, self._hint)

        # Fixed pool of message labels, reused for every update. Creating and
        # destroying QLabels per translation churned the C++ heap on the GUI
        # thread and was one of the native-crash detonation sites seen in
        # logs/crash.log (access violation inside _MessageLabel.__init__).
        # Labels sit between the hint and the trailing stretch; index 0 is the
        # topmost (newest) message.
        self._labels: list[_MessageLabel] = []
        for _ in range(_MAX_MESSAGES):
            label = _MessageLabel("", self._body)
            label.setVisible(False)
            self._body_layout.insertWidget(self._body_layout.count() - 1, label)
            self._labels.append(label)

        # Resize handle in the bottom-right corner.
        grip_row = QHBoxLayout()
        grip_row.setContentsMargins(0, 0, 2, 2)
        grip_row.addStretch(1)
        grip_row.addWidget(QSizeGrip(self._panel))
        panel.addLayout(grip_row)

        self._panel.setStyleSheet(self._panel_qss())

    def _build_title_bar(self) -> QWidget:
        bar = QWidget(self._panel)
        bar.setObjectName("OverlayTitleBar")
        bar.setFixedHeight(26)
        # Dragging the bar moves the whole window.
        bar.mousePressEvent = self._bar_mouse_press  # type: ignore[assignment]
        bar.mouseMoveEvent = self._bar_mouse_move    # type: ignore[assignment]
        bar.mouseReleaseEvent = self._bar_mouse_release  # type: ignore[assignment]

        row = QHBoxLayout(bar)
        row.setContentsMargins(8, 0, 4, 0)
        row.setSpacing(4)

        title = QLabel("Left4Translate", bar)
        title.setObjectName("OverlayTitle")
        row.addWidget(title)
        row.addStretch(1)

        smaller = self._tool_button("A–", "Smaller text", self._decrease_font)
        bigger = self._tool_button("A+", "Larger text", self._increase_font)
        less = self._tool_button("–", "Less opaque", self._decrease_opacity)
        more = self._tool_button("+", "More opaque", self._increase_opacity)
        ghost = self._tool_button(
            "▣",
            "Click-through: clicks pass to the game (Windows). Hide and "
            "re-show the overlay to interact with it again.",
            self._enable_click_through,
        )
        clear = self._tool_button("⌫", "Clear messages", self.clear)
        close = self._tool_button("✕", "Hide overlay", self.hide)
        for btn in (smaller, bigger, less, more, ghost, clear, close):
            row.addWidget(btn)
        return bar

    def _tool_button(self, text: str, tip: str, slot) -> QPushButton:
        btn = QPushButton(text, self)
        btn.setObjectName("OverlayToolButton")
        btn.setFixedSize(26 if len(text) > 1 else 20, 20)
        btn.setToolTip(tip)
        btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.clicked.connect(slot)
        return btn

    # ---- Public API -----------------------------------------------------

    def add_translation(self, payload: Dict[str, Any]) -> None:
        """Render a translation row (newest on top), trimming old ones."""
        kind = payload.get("kind", "chat")
        player = str(payload.get("player") or "—")
        original = str(payload.get("original") or "")
        translated = str(payload.get("translated") or "")
        team = payload.get("team")

        if kind == "voice":
            name_color = _VOICE_COLOR
        elif team and str(team).lower().startswith(("surv", "inf")):
            name_color = _TEAM_PLAYER_COLOR
        else:
            name_color = _PLAYER_COLOR

        parts = [
            f'<span style="color:{name_color}; font-weight:bold;">'
            f'[{escape(player)}]</span> '
            f'<span style="color:{_ORIGINAL_COLOR};">{escape(original)}</span>'
        ]
        if translated and translated != original:
            parts.append(
                f'<span style="color:{_ARROW_COLOR};">&#8594;</span> '
                f'<span style="color:{_TRANSLATED_COLOR};">{escape(translated)}</span>'
            )
        html = "<br>".join(parts)

        self._messages.append(html)
        self._rebuild()

    def clear(self) -> None:
        """Remove all messages from the overlay."""
        self._messages.clear()
        self._rebuild()

    # ---- Rendering ------------------------------------------------------

    def _rebuild(self) -> None:
        # Repopulate the fixed label pool: newest message in the top label,
        # unused labels hidden. No widgets are created or destroyed here.
        messages = list(reversed(self._messages))  # newest first
        self._hint.setVisible(not messages)
        for label, html in zip(self._labels, messages, strict=False):
            label.setText(html)
            label.setVisible(True)
        for label in self._labels[len(messages):]:
            label.setVisible(False)
            label.setText("")

    # ---- Font size ------------------------------------------------------

    def _increase_font(self) -> None:
        self._set_font_size(self._font_size + 1)

    def _decrease_font(self) -> None:
        self._set_font_size(self._font_size - 1)

    def _set_font_size(self, value: int) -> None:
        self._font_size = min(24, max(9, value))
        self._store.set_overlay_font_size(self._font_size)
        self._panel.setStyleSheet(self._panel_qss())

    # ---- Click-through ---------------------------------------------------

    def _enable_click_through(self) -> None:
        """Let all mouse input fall through to the game (Windows).

        Deliberately one-way and session-only: once the window ignores the
        mouse its own buttons are unreachable, so the escape hatch is hiding
        and re-showing the overlay (main-window Overlay button), which
        resets the flag in showEvent.
        """
        if sys.platform != "win32":
            return
        self._click_through = True
        self._apply_window_ex_style()

    # ---- Opacity --------------------------------------------------------

    def _apply_opacity(self) -> None:
        self.setWindowOpacity(self._opacity)

    def _increase_opacity(self) -> None:
        self._set_opacity(self._opacity + 0.1)

    def _decrease_opacity(self) -> None:
        self._set_opacity(self._opacity - 0.1)

    def _set_opacity(self, value: float) -> None:
        self._opacity = max(_MIN_OPACITY, min(_MAX_OPACITY, round(value, 2)))
        self._apply_opacity()
        self._store.set_overlay_opacity(self._opacity)

    # ---- Dragging -------------------------------------------------------

    def _bar_mouse_press(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_offset = (
                event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            )
            event.accept()

    def _bar_mouse_move(self, event) -> None:
        if self._drag_offset is not None and (event.buttons() & Qt.MouseButton.LeftButton):
            self.move(event.globalPosition().toPoint() - self._drag_offset)
            event.accept()

    def _bar_mouse_release(self, event) -> None:
        self._drag_offset = None
        self._snap_to_edges()
        event.accept()

    def _snap_to_edges(self, threshold: int = 20) -> None:
        """Stick to a screen edge when released within ``threshold`` px."""
        screen = self.screen() or QApplication.primaryScreen()
        if screen is None:
            return
        area = screen.availableGeometry()
        geo = self.frameGeometry()
        x, y = geo.x(), geo.y()
        if abs(geo.left() - area.left()) <= threshold:
            x = area.left()
        elif abs(area.right() - geo.right()) <= threshold:
            x = area.right() - geo.width() + 1
        if abs(geo.top() - area.top()) <= threshold:
            y = area.top()
        elif abs(area.bottom() - geo.bottom()) <= threshold:
            y = area.bottom() - geo.height() + 1
        if (x, y) != (geo.x(), geo.y()):
            self.move(x, y)

    # ---- Geometry persistence -------------------------------------------

    def _restore_geometry(self) -> None:
        geometry = self._store.overlay_geometry()
        if geometry is not None and self.restoreGeometry(geometry):
            return
        # Default: a compact strip near the top-left of the primary screen.
        self.resize(420, 260)
        screen = QApplication.primaryScreen()
        if screen is not None:
            available = screen.availableGeometry()
            self.move(available.left() + 24, available.top() + 24)

    def save_geometry(self) -> None:
        self._store.set_overlay_geometry(self.saveGeometry())

    # ---- Window events --------------------------------------------------

    def showEvent(self, event) -> None:  # type: ignore[override]
        super().showEvent(event)
        self._click_through = False  # escape hatch: re-show restores the mouse
        self._apply_window_ex_style()
        self.raise_()

    def hideEvent(self, event) -> None:  # type: ignore[override]
        self.save_geometry()
        super().hideEvent(event)

    def _apply_window_ex_style(self) -> None:
        """On Windows, apply WS_EX_NOACTIVATE (never steal focus) and, when
        click-through is enabled, WS_EX_TRANSPARENT (mouse passes to the game).

        ``WA_ShowWithoutActivating`` stops the initial show from stealing focus,
        but a click on the drag bar would otherwise activate the window and pull
        focus out of the game. The extended style makes the window unfocusable.
        """
        if sys.platform != "win32":
            return
        try:
            import ctypes

            GWL_EXSTYLE = -20
            WS_EX_NOACTIVATE = 0x08000000
            WS_EX_TOOLWINDOW = 0x00000080
            WS_EX_TRANSPARENT = 0x00000020
            hwnd = int(self.winId())
            user32 = ctypes.windll.user32
            style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            style |= WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW
            if self._click_through:
                style |= WS_EX_TRANSPARENT
            else:
                style &= ~WS_EX_TRANSPARENT
            user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style)
        except Exception:
            # Best-effort: WA_ShowWithoutActivating still covers the common path.
            pass

    # ---- Styling --------------------------------------------------------

    def _panel_qss(self) -> str:
        return _PANEL_QSS_TEMPLATE.format(font_size=self._font_size)


_PANEL_QSS_TEMPLATE = """
        QFrame#OverlayPanel {{
            background: rgba(8, 8, 10, 235);
            border: 1px solid rgba(224, 90, 43, 200);
            border-radius: 10px;
        }}
        QWidget#OverlayTitleBar {{
            background: rgba(26, 26, 31, 230);
            border-top-left-radius: 9px;
            border-top-right-radius: 9px;
        }}
        QLabel#OverlayTitle {{
            color: #e05a2b;
            font-weight: 700;
            font-size: 11px;
            background: transparent;
        }}
        QWidget#OverlayBody {{ background: transparent; }}
        QLabel#OverlayMessage {{
            color: #ffffff;
            background: transparent;
            font-family: "Consolas", "Roboto Mono", monospace;
            font-size: {font_size}px;
        }}
        QLabel#OverlayHint {{
            color: #8888a0;
            background: transparent;
            font-size: 12px;
            font-style: italic;
        }}
        QPushButton#OverlayToolButton {{
            background: rgba(255, 255, 255, 18);
            color: #c8c8d4;
            border: none;
            border-radius: 4px;
            font-weight: 700;
            font-size: 12px;
            padding: 0;
        }}
        QPushButton#OverlayToolButton:hover {{
            background: rgba(224, 90, 43, 180);
            color: white;
        }}
        """
