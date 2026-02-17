"""
Left4Translate Display Package.

Provides display functionality for the Turing Smart Screen.

Modules:
- TuringDisplay: Reusable display library for Turing Smart Screen
- ScreenController: Left4Translate-specific message display controller

Example usage:
    # Using the reusable library directly:
    from display import TuringDisplay
    display = TuringDisplay(port="COM8", orientation="landscape")
    display.connect()
    display.show_message("Hello, World!")
    display.disconnect()
    
    # Using the Left4Translate controller:
    from display import ScreenController
    screen = ScreenController(port="COM8")
    screen.connect()
    screen.display_message("Player1", "Hello!", "Hola!")
    screen.disconnect()
"""

from .turing_display import TuringDisplay
from .screen_controller import ScreenController, DisplayMessage

__all__ = [
    'TuringDisplay',
    'ScreenController',
    'DisplayMessage'
]
