from typing import List, Optional
from datetime import datetime
import time
import re
import logging
from dataclasses import dataclass
import threading

from .turing_display import TuringDisplay

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
        revision: str = "A"
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
            
            # Display startup message
            from main import __version__
            self.display.show_message(
                f"Left4Translate v{__version__}",
                font=self.display.font_bold,
                color=self.PLAYER_COLOR,
                delay=2
            )
            
            # Clear screen for normal operation
            self.display.clear()
            self.display.render()
            
            # Start display thread
            self.running = True
            self.display_thread = threading.Thread(target=self._display_loop)
            self.display_thread.daemon = True
            self.display_thread.start()
            
            return True
        except Exception as e:
            logger.error(f"Failed to connect to screen: {e}")
            return False
            
    def disconnect(self):
        """Disconnect from the screen."""
        self.running = False
        if self.display_thread:
            self.display_thread.join()
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
            
    def _display_loop(self):
        """Main display update loop."""
        while self.running:
            try:
                self._update_display()
                time.sleep(0.2)  # Reduced delay between updates
            except Exception as e:
                logger.error(f"Display error: {e}")
                time.sleep(1)  # Wait before retry
                
    def _update_display(self):
        """Update the screen display."""
        if not self.display.is_connected:
            return
            
        now = datetime.now()
        
        # Get a copy of messages under lock for thread safety
        with self._active_messages_lock:
            # Remove expired messages if timeout is enabled
            if self.message_timeout > 0:
                self.active_messages = [
                    msg for msg in self.active_messages
                    if msg.expiry and msg.expiry > now
                ]
            # Make a copy to avoid holding lock during rendering
            messages_to_display = list(self.active_messages)
        
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
        self.display.render()
