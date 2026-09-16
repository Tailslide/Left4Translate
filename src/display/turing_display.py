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
- Link supervision: unchanged frames are not re-sent, dropped bytes are
  detected, and a stuck write can be aborted and the link rebuilt

Example usage:
    display = TuringDisplay(port="COM8", orientation="landscape")
    if display.connect():
        display.show_message("Hello, World!")
        display.disconnect()
"""

import sys
import time
import logging
from pathlib import Path
from typing import Optional, Tuple, List

from PIL import Image, ImageDraw, ImageFont

# Module-level logger
logger = logging.getLogger(__name__)


class DisplayLinkError(RuntimeError):
    """Raised when bytes were dropped on the way to the screen.

    The Turing protocol is a byte stream: a DISPLAY_BITMAP command announces a
    rectangle and is followed by exactly ``width * height * 2`` bytes of pixel
    data. If part of a frame is lost the panel keeps waiting for the missing
    bytes and swallows the next command as if it were pixels, so the picture
    freezes permanently. Recovering means rebuilding the link, not writing
    another frame.
    """


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

        # Link supervision state.
        # ``_last_frame`` is the last frame that made it out intact, so an
        # unchanged screen costs no serial traffic at all. ``_write_fault``
        # records bytes the Turing library dropped without telling anyone, and
        # ``_render_started_at`` lets a watchdog spot a write that never
        # returns (the port uses hardware flow control, so a screen that stops
        # asserting CTS blocks the writer forever).
        self._last_frame: Optional[bytes] = None
        self._write_fault: Optional[str] = None
        self._render_started_at: Optional[float] = None
    
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

    @property
    def render_started_at(self) -> Optional[float]:
        """``time.monotonic()`` of the in-flight frame write, else ``None``."""
        return self._render_started_at

    @property
    def write_fault(self) -> Optional[str]:
        """Description of the last dropped write, or ``None`` if the link is clean."""
        return self._write_fault
    
    def _import_screen_class(self):
        """Import the appropriate screen class based on revision."""
        _setup_turing_library_path()
        
        from library.lcd.lcd_comm import Orientation
        
        # Import the appropriate class for this hardware revision.
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

    def _guarded_screen_class(self, screen_class):
        """Return *screen_class* with a non-fatal ``openSerial``.

        The Turing library ends the **process** (``sys.exit(0)``, then
        ``os._exit(0)``) when it cannot open the COM port, and it reopens the
        port from inside its own write error handling. On a worker thread that
        is a silent death: the app either vanishes or loses its display thread
        with nothing in the log. Subclassing lets the override be in place for
        the constructor's own ``openSerial()`` call, so no code path can take
        the process down with it.
        """
        display = self

        def openSerial(screen_self):  # noqa: N802 - matches the library's name
            display._open_serial_port(screen_self)

        return type(
            f"Guarded{screen_class.__name__}",
            (screen_class,),
            {"openSerial": openSerial},
        )

    def _open_serial_port(self, screen, attempts: int = 10, retry_delay: float = 1.0) -> None:
        """Open the screen's serial port, raising instead of exiting on failure.

        Mirrors the library's own parameters (115200 8N1, 1s read timeout,
        RTS/CTS flow control) and re-detects an "AUTO" port on every attempt,
        because the port can change while the screen resets.
        """
        import serial  # imported lazily so the module stays importable without pyserial

        last_error: Optional[Exception] = None
        for attempt in range(1, attempts + 1):
            com_port = getattr(screen, "com_port", None) or self.port
            if str(com_port).upper() == "AUTO":
                com_port = screen.auto_detect_com_port()
                if not com_port:
                    last_error = RuntimeError("no Turing screen found on any COM port")

            if com_port:
                try:
                    screen.lcd_serial = serial.Serial(
                        com_port, self.baud_rate or 115200, timeout=1, rtscts=True
                    )
                    self._install_serial_guards(screen)
                    return
                except Exception as e:
                    last_error = e

            logger.warning(
                f"Cannot open screen port {com_port or 'AUTO'}: {last_error} "
                f"- retrying ({attempt}/{attempts})"
            )
            if attempt < attempts:
                time.sleep(retry_delay)

        raise RuntimeError(f"Could not open the screen COM port after {attempts} attempts: {last_error}")

    def _install_serial_guards(self, screen=None) -> None:
        """Wrap the serial handle so dropped bytes stop being invisible.

        ``LcdComm.WriteLine`` catches ``SerialTimeoutException`` and only logs
        "(Write line) Too fast! Slow down!" before carrying on. On Windows that
        exception means the write was *partial*, so the rest of that bitmap
        chunk never reaches the panel and the frame stream is left misaligned
        for good. Recording the fault here is what turns that silent freeze
        into something :meth:`render` can act on.
        """
        screen = screen if screen is not None else self.screen
        ser = getattr(screen, "lcd_serial", None)
        if ser is None or getattr(getattr(ser, "write", None), "_l4t_guarded", False):
            return

        original_write = ser.write

        def guarded_write(data, _original=original_write):
            try:
                written = _original(data)
            except Exception as e:
                # SerialTimeoutException here is a partial write, not a no-op.
                self._write_fault = f"{type(e).__name__}: {e}"
                raise
            # A write cancelled from another thread (see abort_write) returns
            # short instead of raising.
            if written is not None and written < len(data):
                self._write_fault = f"short write ({written}/{len(data)} bytes)"
            return written

        guarded_write._l4t_guarded = True
        try:
            ser.write = guarded_write
        except (AttributeError, TypeError) as e:  # pragma: no cover - exotic serial backends
            logger.debug(f"Could not instrument serial writes: {e}")

    def abort_write(self) -> bool:
        """Unblock a write that is stuck, from another thread.

        ``cancel_write()`` makes the blocked ``write()`` return short rather
        than raise, so the caller is freed and the dropped bytes are recorded
        as a fault; the link then has to be rebuilt.
        """
        ser = getattr(self.screen, "lcd_serial", None)
        if ser is None:
            return False

        self._write_fault = self._write_fault or "write aborted (screen stopped accepting data)"
        for method in ("cancel_write", "close"):
            fn = getattr(ser, method, None)
            if fn is None:
                continue
            try:
                fn()
                return True
            except Exception as e:
                logger.debug(f"serial {method}() failed: {e}")
        return False

    def reconnect(self) -> bool:
        """Tear the link down and build it back up.

        This is the only way back from a desynchronised frame stream: the panel
        is waiting for the tail of a bitmap it will never get, so it has to be
        reset before any new frame means anything to it.
        """
        self._is_connected = False
        self._last_frame = None
        screen, self.screen = self.screen, None
        if screen is not None:
            try:
                screen.closeSerial()
            except Exception as e:
                logger.debug(f"Error closing screen port before reconnect: {e}")
        return self.connect()

    def connect(self) -> bool:
        """
        Connect to the Turing Smart Screen.
        
        Returns:
            True if connection successful, False otherwise.
        """
        self._last_frame = None
        self._write_fault = None
        try:
            # Import the screen class
            screen_class, Orientation = self._import_screen_class()
            
            # Create LCD communication object
            # Initialize with portrait dimensions (320x480) - we handle orientation
            # The guarded subclass stops a port that won't open from taking
            # the whole process down with it.
            self.screen = self._guarded_screen_class(screen_class)(
                com_port=self.port,
                display_width=self._native_width,
                display_height=self._native_height
            )
            self._install_serial_guards()
            
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
            
        except SystemExit as e:
            # The Turing library exits the process when it gives up on the port.
            logger.error(f"Screen library tried to exit the process while connecting ({e})")
            self._is_connected = False
            return False
        except Exception as e:
            logger.error(f"Failed to connect to screen: {e}")
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
            logger.error(f"Failed to load fonts: {e}")
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
        self._last_frame = None
        self._write_fault = None
    
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
    
    def render(self, force: bool = False) -> bool:
        """
        Send the display buffer to the hardware.

        A full frame is ``width * height * 2`` bytes (~300 KB in landscape).
        Re-sending an identical frame several times a second keeps the serial
        link permanently saturated, which is what eventually stalls a write and
        leaves the panel out of sync, so an unchanged buffer is not sent at all.

        Args:
            force: Send the frame even when it matches what is already on the
                panel (used after a reconnect, where the panel is blank).

        Returns:
            True if a frame was written to the hardware.

        Raises:
            DisplayLinkError: part of the frame was dropped; the panel is now
                out of sync and the link has to be rebuilt.
        """
        if self.screen is None or self._buffer is None:
            raise RuntimeError("Display not connected")

        frame = self._buffer.tobytes()
        if not force and frame == self._last_frame:
            return False

        self._ensure_serial_guards()
        self._write_fault = None
        # Clear first: a half-written frame must never be remembered as the
        # picture the panel is showing.
        self._last_frame = None
        self._render_started_at = time.monotonic()
        try:
            self.screen.DisplayPILImage(self._buffer)
        finally:
            self._render_started_at = None

        if self._write_fault:
            raise DisplayLinkError(self._write_fault)

        self._last_frame = frame
        return True

    def _ensure_serial_guards(self) -> None:
        """Re-instrument the handle after the library reopened the port itself."""
        ser = getattr(self.screen, "lcd_serial", None)
        if ser is not None and not getattr(getattr(ser, "write", None), "_l4t_guarded", False):
            self._install_serial_guards()
    
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
        
        # The panel no longer shows the buffer, so the next render must go out.
        self._last_frame = None
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
            logger.error(f"Failed to load font from {path}: {e}")
            # Return default font as fallback
            return self._font if self._font else ImageFont.load_default()
    
    def __enter__(self):
        """Context manager entry."""
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.disconnect()