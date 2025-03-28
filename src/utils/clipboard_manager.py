"""
Clipboard manager for voice translation feature.
"""
import logging
from typing import Optional
import pyperclip

# Setup logger
logger = logging.getLogger(__name__)

class ClipboardManager:
    """
    Manages clipboard operations for voice translation.
    
    This class handles copying translated text to the clipboard,
    with options for formatting and automatic copying.
    """
    
    def __init__(self, auto_copy: bool = True, format: str = "both"):
        """
        Initialize the clipboard manager.
        
        Args:
            auto_copy: Whether to automatically copy translations to clipboard
            format: Format to use when copying ("original", "translated", or "both")
        """
        self.auto_copy = auto_copy
        self.format = format
        
        logger.debug(f"ClipboardManager initialized with auto_copy={auto_copy}, format={format}")
    
    def copy_to_clipboard(self, original_text: str, translated_text: str) -> bool:
        """
        Copy text to clipboard.
        
        Args:
            original_text: Original text
            translated_text: Translated text
            
        Returns:
            bool: True if copied successfully, False otherwise
        """
        if not self.auto_copy:
            logger.debug("Auto-copy disabled, skipping clipboard operation")
            return False
            
        try:
            # Format the text based on the configured format
            if self.format == "original":
                text = original_text
            elif self.format == "translated":
                text = translated_text
            else:  # "both" or any other value
                text = f"{original_text}\n{translated_text}"
                
            # Copy to clipboard
            pyperclip.copy(text)
            
            logger.info(f"Copied to clipboard: '{text}'")
            return True
            
        except Exception as e:
            logger.error(f"Failed to copy to clipboard: {e}")
            return False
    
    def update_config(self, auto_copy: Optional[bool] = None, format: Optional[str] = None) -> None:
        """
        Update configuration.
        
        Args:
            auto_copy: New auto-copy setting
            format: New format setting
        """
        if auto_copy is not None and auto_copy != self.auto_copy:
            self.auto_copy = auto_copy
            logger.info(f"Updated auto_copy to: {self.auto_copy}")
            
        if format is not None and format != self.format:
            # Validate format
            if format not in ["original", "translated", "both"]:
                logger.warning(f"Invalid format: {format}. Using 'both' as default.")
                self.format = "both"
            else:
                self.format = format
                
            logger.info(f"Updated format to: {self.format}")