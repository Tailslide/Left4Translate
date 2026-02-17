"""
TuringDisplay - Reusable display library for Turing Smart Screen.

This module provides a complete display library for driving Turing Smart Screen
displays. It handles hardware communication, display buffer management, font
loading, and text rendering utilities. Can be used by any application that
needs to drive a Turing Smart Screen.

Supports:
- Hardware revisions: Rev A (3.5"), Rev B (3.5"), Rev C (5"), Rev D (3.5")
- Orientations: portrait (320x480), landscape (480x320)
- Custom fonts and colors
- Text wrapping and drawing helpers

Example usage:
    display = TuringDisplay(port="COM8", orientation="landscape")
    if display.connect():
        display.show_message("Hello, World!")
        display.disconnect()
"""

import sys
import time
from pathlib import Path
from typing import Optional, Tuple, List

from PIL import Image, ImageDraw, ImageFont


def get_resource_path(relative_path: str) -> str:
    """Get absolute path to resource, works for dev and for PyInstaller."""
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = str(Path(__file__).resolve().parent.parent.parent)
    
    return str(Path(base_path) / relative_path)


def _setup_turing_library_path() -> None:
    """Add Turing library to Python path if not already present."""
    turing_path = str(Path(__file__).resolve().parent.parent.parent / 'turing-smart-screen-python')
    if turing_path not in sys.path:
        sys.path.append(turing_path)


class TuringDisplay:
    """
    Reusable Turing Smart Screen display library.
    
    Provides hardware communication, display buffer management,
    font loading, and text rendering utilities. Can be used by
    any application that needs to drive a Turing Smart Screen.
    """
    
    # Default dimensions for different orientations
    PORTRAIT_WIDTH = 320
    PORTRAIT_HEIGHT = 480
    LANDSCAPE_WIDTH = 480
    LANDSCAPE_HEIGHT = 320
    
    # Default colors
    DEFAULT_BACKGROUND = (0, 0, 0)
    DEFAULT_FOREGROUND = (255, 255, 255)
    
    def __init__(
        self,
        port: str,
        baud_rate: int = 115200,
        brightness: int = 80,
        orientation: str = "landscape",
        font_path: Optional[str] = None,
        font_size: int = 14,
        revision: str = "A"
    ):
        """
        Initialize the Turing Display.
        
        Args:
            port: COM port for the display (e.g., "COM8")
            baud_rate: Serial baud rate (default: 115200)
            brightness: Initial brightness level 0-100 (default: 80)
            orientation: Display orientation - "portrait" or "landscape" (default: "landscape")
            font_path: Path to font directory (default: auto-detect)
            font_size: Default font size (default: 14)
            revision: Hardware revision - "A", "B", "C", or "D" (default: "A")
        """
        self.port = port
        self.baud_rate = baud_rate
        self.brightness = brightness
        self.orientation = orientation.lower()
        self.font_size = font_size
        self.revision = revision.upper()
        
        # Determine effective dimensions
        if self.orientation == "landscape":
            self._native_width = self.LANDSCAPE_WIDTH
            self._native_height = self.LANDSCAPE_HEIGHT
        else:
            self._native_width = self.PORTRAIT_WIDTH
            self._native_height = self.PORTRAIT_HEIGHT
        
        # Font path setup
        if font_path is None:
            # Try multiple paths
            possible_paths = [
                get_resource_path('res/fonts/roboto-mono'),
                get_resource_path('turing-smart-screen-python/res/fonts/roboto-mono'),
            ]
            for p in possible_paths:
                if Path(p).exists():
                    font_path = p
                    break
            else:
                font_path = possible_paths[0]
        
        self.font_path = font_path
        
        # Hardware connection
        self.screen = None
        self._screen_class = None
        
        # Display buffer
        self._buffer: Optional[Image.Image] = None
        self._draw: Optional[ImageDraw.Draw] = None
        
        # Fonts
        self._font: Optional[ImageFont.FreeTypeFont] = None
        self._font_bold: Optional[ImageFont.FreeTypeFont] = None
        
        # State
        self._is_connected = False
    
    @property
    def width(self) -> int:
        """Get effective display width in pixels."""
        return self._native_width
    
    @property
    def height(self) -> int:
        """Get effective display height in pixels."""
        return self._native_height
    
    @property
    def buffer(self) -> Image.Image:
        """Get direct access to the display buffer (PIL Image)."""
        if self._buffer is None:
            raise RuntimeError("Display not connected. Call connect() first.")
        return self._buffer
    
    @property
    def draw(self) -> ImageDraw.Draw:
        """Get direct access to the display buffer's ImageDraw object."""
        if self._draw is None:
            raise RuntimeError("Display not connected. Call connect() first.")
        return self._draw
    
    @property
    def font(self) -> ImageFont.FreeTypeFont:
        """Get the default regular font."""
        if self._font is None:
            raise RuntimeError("Display not connected. Call connect() first.")
        return self._font
    
    @property
    def font_bold(self) -> ImageFont.FreeTypeFont:
        """Get the default bold font."""
        if self._font_bold is None:
            raise RuntimeError("Display not connected. Call connect() first.")
        return self._font_bold
    
    @property
    def is_connected(self) -> bool:
        """Check if display is connected."""
        return self._is_connected
    
    def _import_screen_class(self):
        """Import the appropriate screen class based on revision."""
        _setup_turing_library_path()
        
        from library.lcd.lcd_comm import Orientation
        from library.lcd.color import Color
        
        # Map revision to class
        revision_map = {
            "A": "LcdCommRevA",
            "B": "LcdCommRevB",
            "C": "LcdCommRevC",
            "D": "LcdCommRevD",
        }
        
        class_name = revision_map.get(self.revision, "LcdCommRevA")
        
        # Import the appropriate class
        if self.revision == "A":
            from library.lcd.lcd_comm_rev_a import LcdCommRevA
            return LcdCommRevA, Orientation
        elif self.revision == "B":
            from library.lcd.lcd_comm_rev_b import LcdCommRevB
            return LcdCommRevB, Orientation
        elif self.revision == "C":
            from library.lcd.lcd_comm_rev_c import LcdCommRevC
            return LcdCommRevC, Orientation
        elif self.revision == "D":
            from library.lcd.lcd_comm_rev_d import LcdCommRevD
            return LcdCommRevD, Orientation
        else:
            from library.lcd.lcd_comm_rev_a import LcdCommRevA
            return LcdCommRevA, Orientation
    
    def connect(self) -> bool:
        """
        Connect to the Turing Smart Screen.
        
        Returns:
            True if connection successful, False otherwise.
        """
        try:
            # Import the screen class
            screen_class, Orientation = self._import_screen_class()
            
            # Create LCD communication object
            # Initialize with portrait dimensions (320x480) - we handle orientation
            self.screen = screen_class(
                com_port=self.port,
                display_width=self._native_width,
                display_height=self._native_height
            )
            
            # Reset screen and initialize
            self.screen.Reset()
            time.sleep(0.5)
            
            self.screen.InitializeComm()
            time.sleep(0.5)
            
            # Configure brightness
            self.screen.SetBrightness(level=self.brightness)
            time.sleep(0.1)
            
            # Set orientation
            if self.orientation == "landscape":
                self.screen.SetOrientation(orientation=Orientation.LANDSCAPE)
            else:
                self.screen.SetOrientation(orientation=Orientation.PORTRAIT)
            time.sleep(0.5)
            
            # Create display buffer
            self._buffer = Image.new('RGB', (self.width, self.height), self.DEFAULT_BACKGROUND)
            self._draw = ImageDraw.Draw(self._buffer)
            
            # Load fonts
            self._load_fonts()
            
            self._is_connected = True
            return True
            
        except Exception as e:
            print(f"Failed to connect to screen: {e}")
            self._is_connected = False
            return False
    
    def _load_fonts(self) -> None:
        """Load fonts from the font path."""
        try:
            font_path = Path(self.font_path)
            if font_path.exists():
                self._font = ImageFont.truetype(
                    str(font_path / "RobotoMono-Regular.ttf"),
                    self.font_size
                )
                self._font_bold = ImageFont.truetype(
                    str(font_path / "RobotoMono-Bold.ttf"),
                    self.font_size
                )
            else:
                # Fallback to default font
                self._font = ImageFont.load_default()
                self._font_bold = ImageFont.load_default()
        except Exception as e:
            print(f"Failed to load fonts: {e}")
            # Fallback to default
            self._font = ImageFont.load_default()
            self._font_bold = ImageFont.load_default()
    
    def disconnect(self) -> None:
        """Disconnect from the screen."""
        self._is_connected = False
        
        if self.screen:
            try:
                # Clear screen before disconnecting
                black_screen = Image.new('RGB', (self.width, self.height), self.DEFAULT_BACKGROUND)
                self.screen.DisplayPILImage(black_screen)
                self.screen.closeSerial()
            except Exception:
                pass
        
        self.screen = None
        self._buffer = None
        self._draw = None
        self._font = None
        self._font_bold = None
    
    def clear(self, color: Tuple[int, int, int] = None) -> None:
        """
        Clear the display buffer.
        
        Args:
            color: RGB color tuple (default: black)
        """
        if self._draw is None:
            raise RuntimeError("Display not connected")
        
        if color is None:
            color = self.DEFAULT_BACKGROUND
        
        self._draw.rectangle([0, 0, self.width, self.height], fill=color)
    
    def render(self) -> None:
        """
        Send the display buffer to the hardware.
        """
        if self.screen is None or self._buffer is None:
            raise RuntimeError("Display not connected")
        
        self.screen.DisplayPILImage(self._buffer)
    
    def display_image(self, image: Image.Image) -> None:
        """
        Display an arbitrary PIL Image on the screen.
        
        Args:
            image: PIL Image to display (will be resized to fit if needed)
        """
        if self.screen is None:
            raise RuntimeError("Display not connected")
        
        # Resize image if needed
        if image.size != (self.width, self.height):
            image = image.resize((self.width, self.height), Image.Resampling.LANCZOS)
        
        self.screen.DisplayPILImage(image)
    
    def set_brightness(self, level: int) -> None:
        """
        Set the screen brightness.
        
        Args:
            level: Brightness level 0-100
        """
        if self.screen is None:
            raise RuntimeError("Display not connected")
        
        self.brightness = max(0, min(100, level))
        self.screen.SetBrightness(level=self.brightness)
    
    def text_width(self, text: str, font: ImageFont.FreeTypeFont = None) -> float:
        """
        Calculate the width of text in pixels.
        
        Args:
            text: Text to measure
            font: Font to use (default: default font)
        
        Returns:
            Width in pixels
        """
        if self._draw is None:
            raise RuntimeError("Display not connected")
        
        if font is None:
            font = self._font
        
        return self._draw.textlength(text, font=font)
    
    def wrap_text(
        self,
        text: str,
        max_width: int,
        font: ImageFont.FreeTypeFont = None
    ) -> List[str]:
        """
        Wrap text to fit within a given width.
        
        Args:
            text: Text to wrap
            max_width: Maximum width in pixels
            font: Font to use (default: default font)
        
        Returns:
            List of wrapped lines
        """
        if self._draw is None:
            raise RuntimeError("Display not connected")
        
        if font is None:
            font = self._font
        
        words = text.split()
        lines = []
        current_line = []
        current_width = 0
        
        for word in words:
            word_width = self._draw.textlength(word, font=font)
            space_width = self._draw.textlength(" ", font=font)
            
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
        
        return lines if lines else [""]
    
    def draw_text(
        self,
        x: int,
        y: int,
        text: str,
        font: ImageFont.FreeTypeFont = None,
        color: Tuple[int, int, int] = None
    ) -> None:
        """
        Draw text at a specific position.
        
        Args:
            x: X coordinate
            y: Y coordinate
            text: Text to draw
            font: Font to use (default: default font)
            color: RGB color tuple (default: white)
        """
        if self._draw is None:
            raise RuntimeError("Display not connected")
        
        if font is None:
            font = self._font
        
        if color is None:
            color = self.DEFAULT_FOREGROUND
        
        self._draw.text((x, y), text, font=font, fill=color)
    
    def draw_centered_text(
        self,
        y: int,
        text: str,
        font: ImageFont.FreeTypeFont = None,
        color: Tuple[int, int, int] = None
    ) -> None:
        """
        Draw text centered horizontally on the display.
        
        Args:
            y: Y coordinate
            text: Text to draw
            font: Font to use (default: default font)
            color: RGB color tuple (default: white)
        """
        if self._draw is None:
            raise RuntimeError("Display not connected")
        
        if font is None:
            font = self._font
        
        if color is None:
            color = self.DEFAULT_FOREGROUND
        
        text_width = self._draw.textlength(text, font=font)
        x = (self.width - text_width) // 2
        
        self._draw.text((x, y), text, font=font, fill=color)
    
    def show_message(
        self,
        text: str,
        font: ImageFont.FreeTypeFont = None,
        color: Tuple[int, int, int] = None,
        delay: float = 0
    ) -> None:
        """
        Clear display and show a centered message.
        
        Args:
            text: Message to display
            font: Font to use (default: default font)
            color: RGB color tuple (default: white)
            delay: Seconds to display before returning (0 = no auto-clear)
        """
        if self._draw is None:
            raise RuntimeError("Display not connected")
        
        if font is None:
            font = self._font
        
        if color is None:
            color = self.DEFAULT_FOREGROUND
        
        # Clear and draw centered text
        self.clear()
        
        # Calculate vertical center
        # Use a single line for height calculation
        line_height = self.font_size + 4
        y = (self.height - line_height) // 2
        
        self.draw_centered_text(y, text, font=font, color=color)
        self.render()
        
        if delay > 0:
            time.sleep(delay)
    
    def load_font(
        self,
        path: str,
        size: int = 14,
        bold: bool = False
    ) -> ImageFont.FreeTypeFont:
        """
        Load a custom font from a file.
        
        Args:
            path: Path to font file
            size: Font size
            bold: Use bold variant if available
        
        Returns:
            Loaded font
        """
        try:
            font = ImageFont.truetype(path, size)
            return font
        except Exception as e:
            print(f"Failed to load font from {path}: {e}")
            # Return default font as fallback
            return self._font if self._font else ImageFont.load_default()
    
    def __enter__(self):
        """Context manager entry."""
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.disconnect()