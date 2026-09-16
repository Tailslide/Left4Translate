from typing import Callable, List, Optional
from datetime import datetime
import time
import re
import logging
from dataclasses import dataclass
import threading

from .turing_display import DisplayLinkError, TuringDisplay

# Module-level logger
logger = logging.getLogger(__name__)


@dataclass
class DisplayMessage:
    """Represents a message to be displayed on the screen."""
    timestamp: datetime
    player: str
    original: str
    translated: str
    is_team_chat: bool = False
    expiry: Optional[datetime] = None


class ScreenController:
    """Controls the Turing Smart Screen display for Left4Translate.
    
    This is the Left4Translate-specific message display controller that
    manages chat messages, colors, and rendering logic while delegating
    hardware communication and low-level rendering to the reusable
    TuringDisplay library.
    """
    
    # Color scheme - Left4Translate specific
    BACKGROUND_COLOR = (0, 0, 0)      # Black background
    PLAYER_COLOR = (0, 191, 255)      # Deep sky blue for player names
    TEAM_PLAYER_COLOR = (255, 165, 0)  # Orange for team chat names
    ORIGINAL_COLOR = (255, 255, 255)   # White for original text
    ARROW_COLOR = (50, 205, 50)       # Lime green for arrow
    TRANSLATED_COLOR = (144, 238, 144) # Light green for translations
    
    # Display constants - Left4Translate specific layout
    LINE_HEIGHT = 18  # Height for each line of text
    MESSAGE_SPACING = 4  # Space between messages

    # Link supervision
    POLL_INTERVAL = 0.2       # How often the loop looks for work, in seconds
    REFRESH_INTERVAL = 60.0   # Repaint an unchanged screen this often, in seconds
    STALL_TIMEOUT = 15.0      # A single frame write may never take this long
    WATCHDOG_INTERVAL = 1.0   # How often the watchdog checks on the display thread
    RECONNECT_BACKOFF = (0, 2, 5, 15, 30)  # Seconds to wait before each retry
    MAX_THREAD_RESTARTS = 3   # Give up restarting a display thread that keeps dying

    def __init__(
        self,
        port: str,
        baud_rate: int = 115200,
        brightness: int = 80,
        max_messages: int = 5,
        message_timeout: int = 10000,
        margin: int = 2,  # Reduced margin
        spacing: int = 2,
        font_path: str = None,
        font_size: int = 14,
        revision: str = "A",
        app_version: str = "",
        on_status: Optional[Callable[[str, str], None]] = None,
        poll_interval: Optional[float] = None,
        stall_timeout: Optional[float] = None,
        refresh_interval: Optional[float] = None
    ):
        self.port = port
        self.baud_rate = baud_rate
        self.brightness = brightness
        self.max_messages = max_messages
        self.message_timeout = message_timeout
        self.margin = margin
        self.spacing = spacing
        self.font_size = font_size
        self.revision = revision
        self.app_version = app_version
        self._on_status = on_status
        self.poll_interval = self.POLL_INTERVAL if poll_interval is None else poll_interval
        self.stall_timeout = self.STALL_TIMEOUT if stall_timeout is None else stall_timeout
        self.refresh_interval = self.REFRESH_INTERVAL if refresh_interval is None else refresh_interval
        self.watchdog_interval = self.WATCHDOG_INTERVAL
        
        # Reusable display library - handles all hardware communication
        self.display = TuringDisplay(
            port=port,
            baud_rate=baud_rate,
            brightness=brightness,
            orientation="landscape",
            font_path=font_path,
            font_size=font_size,
            revision=revision
        )
        
        # App-specific state - use a lock for thread safety
        self._active_messages_lock = threading.Lock()
        self.active_messages: List[DisplayMessage] = []
        self.running = False
        self.display_thread = None

        # Link supervision state
        self._stop_event = threading.Event()
        self.watchdog_thread = None
        self._needs_reconnect = False
        self._reconnect_attempts = 0
        self._aborted_render_at = None
        self._thread_restarts = 0
        self._last_frame_at = 0.0
        
        # Cache for screen dimensions
        self._screen_height = 320  # Landscape mode height
    
    @property
    def display_buffer(self):
        """Delegate to display.buffer for backward compatibility."""
        return self.display.buffer
    
    @property
    def font(self):
        """Delegate to display.font for backward compatibility."""
        return self.display.font
    
    @property
    def font_bold(self):
        """Delegate to display.font_bold for backward compatibility."""
        return self.display.font_bold
    
    @property
    def screen(self):
        """Provide backward compatibility - returns the underlying display."""
        return self.display
    
    def connect(self):
        """Connect to the Turing Smart Screen."""
        try:
            # Connect using the reusable display library
            if not self.display.connect():
                return False
            
            # Display startup message. The version is injected by the app
            # so this module stays reusable (no import from main).
            title = f"Left4Translate v{self.app_version}" if self.app_version else "Left4Translate"
            self.display.show_message(
                title,
                font=self.display.font_bold,
                color=self.PLAYER_COLOR,
                delay=2
            )
            
            # Clear screen for normal operation
            self.display.clear()
            self.display.render()
            
            # Start display and watchdog threads
            self.running = True
            self._stop_event.clear()
            self._needs_reconnect = False
            self._reconnect_attempts = 0
            self._thread_restarts = 0
            self._start_display_thread()

            self.watchdog_thread = threading.Thread(target=self._watchdog_loop, daemon=True)
            self.watchdog_thread.start()
            
            return True
        except Exception as e:
            logger.error(f"Failed to connect to screen: {e}")
            return False

    def _start_display_thread(self):
        """Start (or restart) the thread that pushes frames to the screen."""
        self.display_thread = threading.Thread(target=self._display_loop, daemon=True)
        self.display_thread.start()

    def _emit_status(self, state: str, detail: str = ""):
        """Report a screen state change to an observer (best-effort)."""
        if self._on_status is None:
            return
        try:
            self._on_status(state, detail)
        except Exception as e:  # an observer must never break the display loop
            logger.debug(f"screen status observer error: {e}")

    def disconnect(self):
        """Disconnect from the screen."""
        self.running = False
        self._stop_event.set()
        # A write that is stuck against a wedged screen would otherwise hold
        # the display thread (and the shutdown) for as long as the panel likes.
        if self.display.render_started_at is not None:
            self.display.abort_write()
        for thread in (self.display_thread, self.watchdog_thread):
            if thread is not None and thread.is_alive():
                thread.join(timeout=5)
        # Use the display library's disconnect
        self.display.disconnect()
        
    def _clean_player_name(self, name: str) -> str:
        """Clean up player name to handle special characters."""
        # Remove control characters
        name = re.sub(r'[\x00-\x1F\x7F]', '', name)
        
        # Replace any remaining non-printable or invalid chars with '?'
        name = re.sub(r'[^\x20-\x7E\u2600-\u26FF\u2700-\u27BF♥☺]', '?', name)
        
        # Remove extra spaces
        name = name.strip()
        
        return name
    
    def _calculate_message_height(self, message: DisplayMessage) -> int:
        """Calculate total height needed for a message including spacing."""
        # Use the display's wrap_text for calculations
        # Calculate available width for text (screen width minus margins and player name)
        player_text = f"[{message.player}]"
        player_width = self.display.text_width(player_text, self.display.font_bold)
        available_width = self.display.width - (self.margin * 2 + 5) - player_width - 5

        # Calculate wrapped lines for original and translated text
        original_lines = self.display.wrap_text(message.original, available_width, self.display.font)
        original_height = len(original_lines) * self.LINE_HEIGHT

        if message.original != message.translated:
            # For translations, account for the arrow indent
            translation_width = available_width - 30  # Account for arrow and indent
            translated_lines = self.display.wrap_text(message.translated, translation_width, self.display.font)
            translated_height = len(translated_lines) * self.LINE_HEIGHT
            return original_height + translated_height + self.MESSAGE_SPACING
        
        return original_height + self.MESSAGE_SPACING
            
    def display_message(
        self,
        player: str,
        original: str,
        translated: str,
        is_team_chat: bool = False,
        timeout: Optional[int] = None
    ):
        """
        Add a new message to the display queue.
        
        Args:
            player: Player name or message source
            original: Original message text
            translated: Translated message text
            is_team_chat: Whether this is a team chat message
            timeout: Custom timeout in milliseconds (overrides default message_timeout)
        """
        now = datetime.now()
        
        # Clean up player name
        player = self._clean_player_name(player)
        
        # Use custom timeout if provided, otherwise use default
        message_timeout = timeout if timeout is not None else self.message_timeout
        
        message = DisplayMessage(
            timestamp=now,
            player=player,
            original=original,
            translated=translated,
            is_team_chat=is_team_chat,
            expiry=datetime.fromtimestamp(now.timestamp() + message_timeout / 1000) if message_timeout > 0 else None
        )
        
        # A message taller than the whole screen would previously be dropped
        # silently; shorten its texts until it fits instead.
        max_height = self._screen_height - self.margin * 2
        guard = 0
        while self._calculate_message_height(message) > max_height and guard < 24:
            if len(message.translated) > 40:
                message.translated = message.translated[: int(len(message.translated) * 0.75)].rstrip() + "…"
            elif len(message.original) > 40:
                message.original = message.original[: int(len(message.original) * 0.75)].rstrip() + "…"
            else:
                break
            guard += 1

        # Thread-safe update of active_messages
        with self._active_messages_lock:
            # Calculate total height needed for all messages including the new one
            total_height = self.margin  # Start with top margin
            for msg in self.active_messages:
                total_height += self._calculate_message_height(msg)
            
            # Add height of new message
            new_msg_height = self._calculate_message_height(message)
            
            # Remove oldest messages until new message would fit
            while self.active_messages and (total_height + new_msg_height > self._screen_height - self.margin):
                removed_msg = self.active_messages.pop(0)
                total_height -= self._calculate_message_height(removed_msg)
                
            # Add new message only if it will fit
            if total_height + new_msg_height <= self._screen_height - self.margin:
                self.active_messages.append(message)
        
    def clear_display(self):
        """Clear all messages from the screen."""
        if self.display.is_connected:
            # Clear buffer using display library
            self.display.clear()
            self.display.render()
            
        with self._active_messages_lock:
            self.active_messages.clear()
            
    def set_brightness(self, level: int):
        """Set the screen brightness level (0-100)."""
        self.display.set_brightness(level)
            
    def _prune_expired(self, now: datetime) -> List[DisplayMessage]:
        """Drop expired messages and return a snapshot of the remainder.

        Expiry is per-message: any message created with a positive timeout
        (e.g. voice ``clear_after``) gets an expiry even when the
        controller-wide default is 0 ("keep chat forever"); messages without
        an expiry stay until pushed out by newer ones.
        """
        with self._active_messages_lock:
            self.active_messages = [
                msg for msg in self.active_messages
                if msg.expiry is None or msg.expiry > now
            ]
            return list(self.active_messages)

    def _display_loop(self):
        """Main display update loop."""
        while self.running:
            try:
                if self._needs_reconnect:
                    self._reconnect()
                else:
                    self._update_display()
            except DisplayLinkError as e:
                # Part of a frame was dropped. The panel is now waiting for
                # bytes that will never arrive and treats every later frame as
                # the tail of that one, so it stays frozen until the link is
                # rebuilt - this is the failure that used to look like the
                # screen simply stopping with nothing in the log.
                logger.warning(f"Screen stopped accepting data ({e}) - reconnecting")
                self._needs_reconnect = True
            except SystemExit as e:
                # The Turing library exits the process when it cannot reopen
                # the port; in a thread that kills the display loop silently.
                logger.error(f"Screen library requested exit ({e}) - reconnecting")
                self._needs_reconnect = True
            except Exception as e:
                logger.error(f"Display error: {e}")
                self._stop_event.wait(1)  # Wait before retry
            if not self._needs_reconnect:
                self._stop_event.wait(self.poll_interval)

    def _reconnect(self):
        """Rebuild the link to the screen, backing off between attempts."""
        delay = self.RECONNECT_BACKOFF[min(self._reconnect_attempts, len(self.RECONNECT_BACKOFF) - 1)]
        if delay and self._stop_event.wait(delay):
            return
        if not self.running:  # shut down while we were waiting
            return

        self._reconnect_attempts += 1
        logger.warning(f"Reconnecting to the Turing screen (attempt {self._reconnect_attempts})...")
        self._emit_status("reconnecting", f"attempt {self._reconnect_attempts}")

        if not self.display.reconnect():
            logger.error("Screen reconnect failed - will retry")
            self._emit_status("disconnected", "Screen not responding")
            return

        self._needs_reconnect = False
        self._aborted_render_at = None
        logger.info("Screen reconnected")
        self._emit_status("connected", "Reconnected")
        # The panel is blank after a reset, so the current messages have to be
        # pushed again even though the buffer itself has not changed.
        self._update_display(force=True)
        # Only a frame that actually landed proves the link is back: if this
        # one faults too, the backoff has to keep growing.
        self._reconnect_attempts = 0

    def _watchdog_loop(self):
        """Catch a display thread that can no longer make progress.

        The port is opened with hardware flow control, so a screen that stops
        asserting CTS (USB selective suspend on an idle PC, or a wedged
        controller) blocks ``write()`` indefinitely: the display thread sits
        inside one frame forever while the rest of the app keeps running. That
        is a frozen screen with nothing in the log, so it needs a watchdog
        rather than an error handler.
        """
        while not self._stop_event.wait(self.watchdog_interval):
            if not self.running:
                break

            started = self.display.render_started_at
            if started is not None and started != self._aborted_render_at:
                stuck_for = time.monotonic() - started
                if stuck_for >= self.stall_timeout:
                    logger.warning(
                        f"Screen write stuck for {stuck_for:.0f}s - aborting it and reconnecting"
                    )
                    self._aborted_render_at = started
                    self._needs_reconnect = True
                    self.display.abort_write()

            thread = self.display_thread
            # ``ident`` is only set once a thread has actually started, so a
            # thread caught mid-(re)start doesn't read as a dead one.
            if thread is not None and thread.ident is not None and not thread.is_alive():
                if self._thread_restarts >= self.MAX_THREAD_RESTARTS:
                    logger.error("Display thread keeps dying - giving up on the screen")
                    self._emit_status("disconnected", "Display thread stopped")
                    break
                self._thread_restarts += 1
                logger.error(f"Display thread died - restarting it ({self._thread_restarts})")
                self._needs_reconnect = True
                self._start_display_thread()

    def _update_display(self, force: bool = False):
        """Update the screen display.

        Only the frames that actually changed reach the hardware (see
        :meth:`TuringDisplay.render`); an idle screen costs no serial traffic
        beyond one repaint a minute, which covers a panel that loses its
        picture without the serial link noticing.
        """
        if not self.display.is_connected:
            return

        if not force and time.monotonic() - self._last_frame_at >= self.refresh_interval:
            force = True
            
        now = datetime.now()
        
        # Prune expired messages, then copy under lock for rendering.
        messages_to_display = self._prune_expired(now)
        
        # Clear buffer using display library
        self.display.clear()
        
        # Get direct access to draw for more control
        draw = self.display.draw
        
        # Start from top margin
        y = self.margin
        x = self.margin + 5  # Reduced margin
        
        for msg in messages_to_display:
            # Draw player name in appropriate color
            player_text = f"[{msg.player}]"  # No extra spaces in brackets
            player_color = self.TEAM_PLAYER_COLOR if msg.is_team_chat else self.PLAYER_COLOR
            draw.text((x, y), player_text, font=self.display.font_bold, fill=player_color)
            
            # Calculate available width for text
            text_width = draw.textlength(player_text, font=self.display.font_bold)
            available_width = self.display.width - (self.margin * 2 + 5) - text_width - 5

            # Draw original message with word wrap
            original_lines = self.display.wrap_text(msg.original, available_width, self.display.font)
            for line in original_lines:
                draw.text((x + text_width + 5, y), line, font=self.display.font, fill=self.ORIGINAL_COLOR)
                y += self.LINE_HEIGHT

            # Only show translation if it's different from original
            if msg.original != msg.translated:
                # Calculate width for translated text (account for arrow)
                translation_width = available_width - 30
                translated_lines = self.display.wrap_text(msg.translated, translation_width, self.display.font)
                
                # Draw arrow and translation
                for i, line in enumerate(translated_lines):
                    if i == 0:
                        draw.text((x + 15, y), "→", font=self.display.font_bold, fill=self.ARROW_COLOR)
                    draw.text((x + 30, y), line, font=self.display.font, fill=self.TRANSLATED_COLOR)
                    y += self.LINE_HEIGHT
            
            # Add spacing between messages
            y += self.MESSAGE_SPACING
        
        # Update screen with complete buffer using display library
        if self.display.render(force=force):
            self._last_frame_at = time.monotonic()
