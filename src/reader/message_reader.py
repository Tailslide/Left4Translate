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
    team: Optional[str] = None  # Team type (Survivor/Infected)
    player: Optional[str] = None  # Player name
    content: Optional[str] = None  # Message content
    timestamp: Optional[datetime] = None

class GameLogHandler(FileSystemEventHandler):
    """Handles file system events for the game log file."""
    
    # System message prefixes to filter out
    SYSTEM_PREFIXES = {
        'Host_', 'Update', 'Unable', 'Changing', 'CAsync', 'NET_', 'L ', 'String', 'Signal',
        'Map:', 'Server:', 'Build:', 'Players:', 'Commentary:', 'VSCRIPT:', 'Anniversary',
        'Steam:', 'Network:', 'RememberIPAddressForLobby:', 'CBaseClientState', 'CSteam3Client',
        'ConVarRef', 'Welcome', 'Steamgroup:', '#Cstrike', 'BinkOpen', 'Bink', 'Couldn\'t find',
        'Invalid', 'Executing', 'Initializing', 'Running', 'Loading', 'Sending', 'Connected',
        'Connecting', 'Receiving', 'Dropped', 'Redownloading', 'SignalXWriteOpportunity',
        'String Table', 'VAC', 'NextBot', 'prop_door_rotating', 'Duplicate sequence', 'Opened',
        'Server using', 'CSteam3', 'No pure server', 'Left 4 Dead', 'Initiating', 'SCRIPT',
        'CSpeechScriptBridge', 'HSCRIPT', 'Director', 'Couldn\'t', 'prop_', 'S_StartSound'
    }
    
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
            
    def _process_new_lines(self, file_path: str, from_start: bool = False):
        """Process new lines added to the log file."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                # Reset position if reading from start
                if from_start:
                    self.last_position = 0
                
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
            
    def _is_system_message(self, line: str) -> bool:
        """Check if a line is a system message."""
        # Skip empty lines and lines without a colon
        if not line or ':' not in line:
            return True
            
        # Skip lines starting with system prefixes
        for prefix in self.SYSTEM_PREFIXES:
            if line.startswith(prefix):
                return True
                
        # Skip lines that look like system paths or commands
        if any(x in line for x in ['\\', '/', '.exe', '.dll', '.txt', '.dat', '.cfg', '.vmt', '.wav', '.bik']):
            return True
            
        # Skip lines that look like system messages
        if any(x in line for x in ['socket', 'handle', 'dictionary', 'whitelist', 'lightmaps']):
            return True
            
        return False
            
    def _clean_text(self, text: str) -> str:
        """Remove special characters from text."""
        # Remove heart emoji
        text = text.replace('♥', '')
        # Remove smiley emoji
        text = text.replace('☺', '')
        # Remove extra spaces
        text = ' '.join(text.split())
        # Remove any remaining control characters
        text = ''.join(c for c in text if ord(c) >= 32)
        return text.strip()
            
    def _process_line(self, line: str):
        """Process a single line from the log file."""
        try:
            # Skip system messages
            if self._is_system_message(line):
                self.logger.debug(f"Skipping system message: '{line}'")
                return
                
            # Debug log every line
            self.logger.debug(f"Processing line: '{line}'")
            
            # Check if it matches our pattern
            match = re.match(self.message_pattern, line)
            if match:
                self.logger.debug(f"Line matched pattern: '{line}'")
                
                # Get player name from appropriate group
                player = match.group(2) if match.group(2) else match.group(4)
                # Get message content from appropriate group
                content = match.group(3) if match.group(3) else match.group(5)
                
                # Clean special characters from player name and content
                player = self._clean_text(player)
                content = self._clean_text(content)
                
                # Create message object with cleaned components
                message = Message(
                    line=line,
                    team=match.group(1),  # Team is always group 1 if present
                    player=player,
                    content=content
                )
                
                if message.player:  # Only send if we got a player name
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
        
    def start_monitoring(self, from_start: bool = False):
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
                self.handler._process_new_lines(str(self.log_path), from_start)
            
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