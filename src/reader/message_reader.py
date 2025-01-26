import re
import os
import time
import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional, Pattern

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileModifiedEvent

@dataclass
class Message:
    """Represents a chat message from the game."""
    line: str  # Full line from log file
    timestamp: Optional[datetime] = None

class GameLogHandler(FileSystemEventHandler):
    """Handles file system events for the game log file."""
    
    def __init__(
        self,
        message_pattern: Pattern[str],
        callback: Callable[[Message], None]
    ):
        self.message_pattern = message_pattern
        self.callback = callback
        self.last_position = 0
        self.logger = logging.getLogger(__name__)
        
    def on_modified(self, event: FileModifiedEvent):
        """Called when the log file is modified."""
        if not event.is_directory:
            self._process_new_lines(event.src_path)
            
    def _process_new_lines(self, file_path: str):
        """Process new lines added to the log file."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                # Seek to last known position
                f.seek(self.last_position)
                
                # Read new lines
                new_lines = f.readlines()
                
                # Update position
                self.last_position = f.tell()
                
                # Process each new line
                for line in new_lines:
                    line = line.strip()
                    if line:  # Skip empty lines
                        self._process_line(line)
                    
        except Exception as e:
            self.logger.error(f"Error reading log file: {e}")
            
    def _process_line(self, line: str):
        """Process a single line from the log file."""
        try:
            # Debug log every line
            self.logger.debug(f"Processing line: '{line}'")
            
            # Check if it matches our pattern
            match = re.match(self.message_pattern, line)
            if match:
                self.logger.debug(f"Line matched pattern: '{line}'")
                # Create message object with full line
                message = Message(line=line)
                self.callback(message)
            else:
                self.logger.debug(f"Line did not match pattern: '{line}'")
                
        except Exception as e:
            self.logger.error(f"Error processing line: {e}")

class GameMessageReader:
    """Monitors the game log file for new chat messages."""
    
    def __init__(
        self,
        log_path: str,
        message_pattern: str,
        callback: Callable[[Message], None]
    ):
        self.log_path = Path(log_path)
        self.message_pattern = re.compile(message_pattern)
        self.callback = callback
        self.observer = Observer()
        self.handler = GameLogHandler(self.message_pattern, self.callback)
        self.running = False
        self.logger = logging.getLogger(__name__)
        
    def start_monitoring(self):
        """Start monitoring the log file for changes."""
        try:
            self.running = True
            
            # Wait for log file to be created if it doesn't exist
            if not self.log_path.exists():
                self.logger.info(f"Waiting for log file to be created: {self.log_path}")
            
            # Start watching the directory for changes
            self.observer.schedule(
                self.handler,
                str(self.log_path.parent),
                recursive=False
            )
            self.observer.start()
            
            # Process existing content if file exists
            if self.log_path.exists():
                self.logger.info(f"Monitoring log file: {self.log_path}")
                self.handler._process_new_lines(str(self.log_path))
            
        except Exception as e:
            self.logger.error(f"Error starting monitoring: {e}")
            raise
        
    def stop_monitoring(self):
        """Stop monitoring the log file."""
        self.logger.info("Stopping log file monitoring...")
        self.running = False
        self.observer.stop()
        self.observer.join()
        self.logger.info("Log file monitoring stopped")