"""
Mouse input handler for voice translation feature.
"""
import logging
import threading
from typing import Callable, List, Optional
from pynput import mouse

# Setup logger
logger = logging.getLogger(__name__)

class MouseHandler:
    """
    Handles mouse button events for voice translation.
    
    This class monitors mouse button events and triggers callbacks
    when the specified button is pressed or released.
    """
    
    def __init__(
        self,
        button: str = "right",
        on_press_callback: Optional[Callable] = None,
        on_release_callback: Optional[Callable] = None,
        modifier_keys: Optional[List[str]] = None
    ):
        """
        Initialize the mouse handler.
        
        Args:
            button: Mouse button to monitor ("left", "right", "middle", "button4", "button5")
            on_press_callback: Function to call when button is pressed
            on_release_callback: Function to call when button is released
            modifier_keys: List of modifier keys that must be pressed along with the button
        """
        self.button_str = button.lower()
        self.on_press_callback = on_press_callback
        self.on_release_callback = on_release_callback
        self.modifier_keys = modifier_keys or []
        
        # Map button string to pynput button object
        self.button_map = {
            "left": mouse.Button.left,
            "right": mouse.Button.right,
            "middle": mouse.Button.middle,
            # In pynput, button4 and button5 are typically represented as x2 and x1
            # Note: On some systems, x1 is back and x2 is forward, on others it's reversed
            "button4": mouse.Button.x2 if hasattr(mouse.Button, "x2") else None,
            "button5": mouse.Button.x1 if hasattr(mouse.Button, "x1") else None
        }
        
        self.button = self.button_map.get(self.button_str)
        if not self.button:
            logger.warning(f"Invalid button: {button}. Using button4 (x2) as default if available, otherwise right button.")
            self.button = mouse.Button.x2 if hasattr(mouse.Button, "x2") else mouse.Button.right
            self.button_str = "button4" if hasattr(mouse.Button, "x2") else "right"
            
        self.listener = None
        self.running = False
        
        logger.debug(f"MouseHandler initialized with button: {self.button_str}")
    
    def start(self) -> bool:
        """
        Start monitoring mouse events.
        
        Returns:
            bool: True if started successfully, False otherwise
        """
        if self.running:
            logger.warning("Mouse handler already running")
            return False
            
        try:
            # Log available buttons for debugging
            logger.info("Available mouse buttons:")
            for button_name, button_obj in self.button_map.items():
                logger.info(f"- {button_name}: {button_obj}")
            
            logger.info(f"Configured to monitor button: {self.button_str} ({self.button})")
            
            # Check if the button is available
            if self.button_str in ["button4", "button5"]:
                if not hasattr(mouse.Button, "x1") or not hasattr(mouse.Button, "x2"):
                    logger.warning("Extended mouse buttons (x1/x2) not available on this system")
                    logger.warning("This may prevent button4/button5 from working correctly")
            
            # Create and start the listener in a separate thread
            self.listener = mouse.Listener(
                on_click=self._on_click,
                suppress=False  # Don't suppress events
            )
            
            self.listener.start()
            self.running = True
            
            logger.info(f"Started monitoring {self.button_str} mouse button")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start mouse handler: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return False
    
    def stop(self) -> bool:
        """
        Stop monitoring mouse events.
        
        Returns:
            bool: True if stopped successfully, False otherwise
        """
        if not self.running:
            logger.warning("Mouse handler not running")
            return False
            
        try:
            if self.listener:
                self.listener.stop()
                self.listener = None
                
            self.running = False
            
            logger.info("Stopped monitoring mouse button")
            return True
            
        except Exception as e:
            logger.error(f"Failed to stop mouse handler: {e}")
            return False
    
    def _on_click(self, x, y, button, pressed):
        """
        Handle mouse click events.
        
        Args:
            x: X coordinate of the mouse
            y: Y coordinate of the mouse
            button: Button that was clicked
            pressed: True if button was pressed, False if released
        """
        try:
            # Log all button events for debugging
            logger.debug(f"Mouse event: button={button}, pressed={pressed}, at ({x}, {y})")
            
            # Check if it's the button we're monitoring
            if button == self.button:
                if pressed and self.on_press_callback:
                    # TODO: Check modifier keys if implemented
                    logger.info(f"Target button {self.button_str} pressed at ({x}, {y})")
                    self.on_press_callback()
                elif not pressed and self.on_release_callback:
                    logger.info(f"Target button {self.button_str} released at ({x}, {y})")
                    self.on_release_callback()
            else:
                # Log when other buttons are clicked to help diagnose button mapping issues
                button_name = "unknown"
                for name, btn in self.button_map.items():
                    if btn == button:
                        button_name = name
                        break
                
                if pressed:
                    logger.debug(f"Other button ({button_name}) pressed at ({x}, {y})")
        except Exception as e:
            logger.error(f"Error handling mouse event: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
    
    def is_running(self) -> bool:
        """
        Check if the mouse handler is running.
        
        Returns:
            bool: True if running, False otherwise
        """
        return self.running
    
    def update_config(self, button: Optional[str] = None, modifier_keys: Optional[List[str]] = None) -> None:
        """
        Update configuration.
        
        Args:
            button: New button to monitor
            modifier_keys: New list of modifier keys
        """
        restart_needed = False
        
        if button and button.lower() != self.button_str:
            new_button = self.button_map.get(button.lower())
            if new_button:
                self.button = new_button
                self.button_str = button.lower()
                restart_needed = True
                logger.info(f"Updated button to: {self.button_str}")
            else:
                logger.warning(f"Invalid button: {button}. Keeping current button: {self.button_str}")
        
        if modifier_keys is not None:
            self.modifier_keys = modifier_keys
            logger.info(f"Updated modifier keys to: {self.modifier_keys}")
        
        # Restart the listener if needed
        if restart_needed and self.running:
            self.stop()
            self.start()