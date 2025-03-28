from typing import List, Optional
from datetime import datetime
import time
import re
from dataclasses import dataclass
from queue import Queue
import threading
import sys
import os
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

def get_resource_path(relative_path):
    """Get absolute path to resource, works for dev and for PyInstaller"""
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = str(Path(__file__).resolve().parent.parent.parent)
    
    return os.path.join(base_path, relative_path)

import sys
from pathlib import Path

# Add turing library to path
turing_path = str(Path(__file__).resolve().parent.parent.parent / 'turing-smart-screen-python')
if turing_path not in sys.path:
    sys.path.append(turing_path)

# Import Turing library
from library.lcd.lcd_comm_rev_a import LcdCommRevA, Orientation
from library.lcd.color import Color

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
    """Controls the Turing Smart Screen display."""
    
    # Color scheme
    BACKGROUND_COLOR = (0, 0, 0)      # Black background
    PLAYER_COLOR = (0, 191, 255)      # Deep sky blue for player names
    TEAM_PLAYER_COLOR = (255, 165, 0)  # Orange for team chat names
    ORIGINAL_COLOR = (255, 255, 255)   # White for original text
    ARROW_COLOR = (50, 205, 50)       # Lime green for arrow
    TRANSLATED_COLOR = (144, 238, 144) # Light green for translations
    
    # Display constants
    LINE_HEIGHT = 18  # Height for each line of text
    MESSAGE_SPACING = 4  # Space between messages
    SCREEN_HEIGHT = 320  # Landscape mode height
    
    def __init__(
        self,
        port: str,
        baud_rate: int = 115200,
        brightness: int = 80,
        max_messages: int = 5,
        message_timeout: int = 10000,
        margin: int = 2,  # Reduced margin
        spacing: int = 2
    ):
        self.port = port
        self.baud_rate = baud_rate
        self.brightness = brightness
        self.max_messages = max_messages
        self.message_timeout = message_timeout
        self.margin = margin
        self.spacing = spacing
        
        self.screen = None
        self.message_queue = Queue()
        self.active_messages: List[DisplayMessage] = []
        self.running = False
        self.display_thread = None
        self.display_buffer = None
        self.font = None
        self.font_bold = None
        
    def connect(self):
        """Connect to the Turing Smart Screen."""
        try:
            # Create LCD communication object for hardware revision A
            # Initialize with portrait dimensions (320x480)
            self.screen = LcdCommRevA(
                com_port=self.port,
                display_width=320,
                display_height=480
            )
            
            # Reset screen and initialize
            self.screen.Reset()
            time.sleep(0.5)  # Wait after reset
            
            self.screen.InitializeComm()
            time.sleep(0.5)  # Wait after init
            
            # Configure display
            self.screen.SetBrightness(level=self.brightness)
            time.sleep(0.1)  # Wait after brightness change
            
            # Set to landscape orientation
            self.screen.SetOrientation(orientation=Orientation.LANDSCAPE)
            time.sleep(0.5)  # Wait after orientation change
            
            # Create display buffer
            self.display_buffer = Image.new('RGB', (480, 320), self.BACKGROUND_COLOR)
            
            # Load fonts with absolute paths
            try:
                # First try the PyInstaller path
                font_path = get_resource_path(os.path.join('res', 'fonts', 'roboto-mono'))
                self.font = ImageFont.truetype(os.path.join(font_path, "RobotoMono-Regular.ttf"), 14)
                self.font_bold = ImageFont.truetype(os.path.join(font_path, "RobotoMono-Bold.ttf"), 14)
            except Exception as e:
                print(f"Failed to load fonts from primary path: {e}")
                # Try the development path
                font_path = os.path.join(str(Path(__file__).resolve().parent.parent.parent),
                                       'turing-smart-screen-python', 'res', 'fonts', 'roboto-mono')
                self.font = ImageFont.truetype(os.path.join(font_path, "RobotoMono-Regular.ttf"), 14)
                self.font_bold = ImageFont.truetype(os.path.join(font_path, "RobotoMono-Bold.ttf"), 14)
            
            # Display startup message
            from main import __version__
            draw = ImageDraw.Draw(self.display_buffer)
            startup_msg = f"Left4Translate v{__version__}"
            # Center the text
            text_width = draw.textlength(startup_msg, font=self.font_bold)
            x = (480 - text_width) // 2  # Center horizontally
            y = 150  # Center vertically (320/2 - line height)
            draw.text((x, y), startup_msg, font=self.font_bold, fill=self.PLAYER_COLOR)
            self.screen.DisplayPILImage(self.display_buffer)
            time.sleep(2)  # Show startup message for 2 seconds
            
            # Clear screen for normal operation
            draw.rectangle([0, 0, 480, 320], fill=self.BACKGROUND_COLOR)
            self.screen.DisplayPILImage(self.display_buffer)
            
            # Start display thread
            self.running = True
            self.display_thread = threading.Thread(target=self._display_loop)
            self.display_thread.daemon = True
            self.display_thread.start()
            
            return True
        except Exception as e:
            print(f"Failed to connect to screen: {e}")
            return False
            
    def disconnect(self):
        """Disconnect from the screen."""
        self.running = False
        if self.display_thread:
            self.display_thread.join()
        if self.screen:
            try:
                # Clear screen before disconnecting
                black_screen = Image.new('RGB', (480, 320), self.BACKGROUND_COLOR)
                self.screen.DisplayPILImage(black_screen)
                self.screen.closeSerial()
            except:
                pass
            
    def _clean_player_name(self, name: str) -> str:
        """Clean up player name to handle special characters."""
        # Remove control characters
        name = re.sub(r'[\x00-\x1F\x7F]', '', name)
        
        # Replace any remaining non-printable or invalid chars with '?'
        name = re.sub(r'[^\x20-\x7E\u2600-\u26FF\u2700-\u27BF♥☺]', '?', name)
        
        # Remove extra spaces
        name = name.strip()
        
        return name
            
    def _wrap_text(self, text: str, max_width: int, draw: ImageDraw.Draw, font: ImageFont.FreeTypeFont) -> list[str]:
        """Wrap text to fit within a given width."""
        words = text.split()
        lines = []
        current_line = []
        current_width = 0

        for word in words:
            word_width = draw.textlength(word, font=font)
            space_width = draw.textlength(" ", font=font)
            
            if current_line and current_width + word_width + space_width > max_width:
                lines.append(" ".join(current_line))
                current_line = [word]
                current_width = word_width
            else:
                if current_line:
                    current_width += space_width
                current_line.append(word)
                current_width += word_width
        
        if current_line:
            lines.append(" ".join(current_line))
        
        return lines if lines else [""]  # Return at least one empty line

    def _calculate_message_height(self, message: DisplayMessage, draw: ImageDraw.Draw) -> int:
        """Calculate total height needed for a message including spacing."""
        # Calculate available width for text (screen width minus margins and player name)
        player_text = f"[{message.player}]"
        player_width = draw.textlength(player_text, font=self.font_bold)
        available_width = 480 - (self.margin * 2 + 5) - player_width - 5  # Screen width minus margins and player section

        # Calculate wrapped lines for original and translated text
        original_lines = self._wrap_text(message.original, available_width, draw, self.font)
        original_height = len(original_lines) * self.LINE_HEIGHT

        if message.original != message.translated:
            # For translations, account for the arrow indent
            translation_width = available_width - 30  # Account for arrow and indent
            translated_lines = self._wrap_text(message.translated, translation_width, draw, self.font)
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
        
        # Create temporary draw context for height calculations
        temp_buffer = Image.new('RGB', (480, 320), self.BACKGROUND_COLOR)
        draw = ImageDraw.Draw(temp_buffer)
        
        # Calculate total height needed for all messages including the new one
        total_height = self.margin  # Start with top margin
        for msg in self.active_messages:
            total_height += self._calculate_message_height(msg, draw)
        
        # Add height of new message
        new_msg_height = self._calculate_message_height(message, draw)
        
        # Remove oldest messages until new message would fit
        while self.active_messages and (total_height + new_msg_height > self.SCREEN_HEIGHT - self.margin):
            removed_msg = self.active_messages.pop(0)
            total_height -= self._calculate_message_height(removed_msg, draw)
            
        # Add new message only if it will fit
        if total_height + new_msg_height <= self.SCREEN_HEIGHT - self.margin:
            self.active_messages.append(message)
        
    def clear_display(self):
        """Clear all messages from the screen."""
        if self.screen and self.display_buffer:
            # Clear buffer
            draw = ImageDraw.Draw(self.display_buffer)
            draw.rectangle([0, 0, 480, 320], fill=self.BACKGROUND_COLOR)
            
            # Update screen
            self.screen.DisplayPILImage(self.display_buffer)
            
        self.active_messages.clear()
        while not self.message_queue.empty():
            self.message_queue.get()
            
    def set_brightness(self, level: int):
        """Set the screen brightness level (0-100)."""
        if self.screen:
            self.brightness = max(0, min(100, level))
            self.screen.SetBrightness(level=self.brightness)
            
    def _display_loop(self):
        """Main display update loop."""
        while self.running:
            try:
                self._update_display()
                time.sleep(0.2)  # Reduced delay between updates
            except Exception as e:
                print(f"Display error: {e}")
                time.sleep(1)  # Wait before retry
                
    def _update_display(self):
        """Update the screen display."""
        if not self.screen or not self.display_buffer:
            return
            
        now = datetime.now()
        
        # Remove expired messages if timeout is enabled
        if self.message_timeout > 0:
            self.active_messages = [
                msg for msg in self.active_messages
                if msg.expiry and msg.expiry > now
            ]
        
        # Clear buffer
        draw = ImageDraw.Draw(self.display_buffer)
        draw.rectangle([0, 0, 480, 320], fill=self.BACKGROUND_COLOR)
        
        # Start from top margin
        y = self.margin
        x = self.margin + 5  # Reduced margin
        
        for msg in self.active_messages:
            # Draw player name in appropriate color
            player_text = f"[{msg.player}]"  # No extra spaces in brackets
            player_color = self.TEAM_PLAYER_COLOR if msg.is_team_chat else self.PLAYER_COLOR
            draw.text((x, y), player_text, font=self.font_bold, fill=player_color)
            
            # Calculate available width for text
            text_width = draw.textlength(player_text, font=self.font_bold)
            available_width = 480 - (self.margin * 2 + 5) - text_width - 5

            # Draw original message with word wrap
            original_lines = self._wrap_text(msg.original, available_width, draw, self.font)
            for line in original_lines:
                draw.text((x + text_width + 5, y), line, font=self.font, fill=self.ORIGINAL_COLOR)
                y += self.LINE_HEIGHT

            # Only show translation if it's different from original
            if msg.original != msg.translated:
                # Calculate width for translated text (account for arrow)
                translation_width = available_width - 30
                translated_lines = self._wrap_text(msg.translated, translation_width, draw, self.font)
                
                # Draw arrow and translation
                for i, line in enumerate(translated_lines):
                    if i == 0:
                        draw.text((x + 15, y), "→", font=self.font_bold, fill=self.ARROW_COLOR)
                    draw.text((x + 30, y), line, font=self.font, fill=self.TRANSLATED_COLOR)
                    y += self.LINE_HEIGHT
            
            # Add spacing between messages
            y += self.MESSAGE_SPACING
            
        # Update screen with complete buffer
        self.screen.DisplayPILImage(self.display_buffer)