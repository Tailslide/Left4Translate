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
    
    # System message prefixes to filter out (removed 'L ' since it's part of our log format)
    SYSTEM_PREFIXES = {
        '- Material', '- Surface', 'Host_', 'Update', 'Unable', 'Changing', 'CAsync', 'NET_', 'String', 'Signal',
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
        callback: Callable[[Message], None],
        file_path: str
    ):
        self.message_pattern = message_pattern
        self.callback = callback
        self.last_position = 0
        self.file_path = file_path
        self.logger = logging.getLogger(__name__)
        
    def on_modified(self, event: FileModifiedEvent):
        """Called when the log file is modified."""
        if not event.is_directory and os.path.samefile(event.src_path, self.file_path):
            self._process_new_lines(event.src_path)
            
    def _get_last_n_lines(self, file_path: str, n: int = 10) -> list[str]:
        """Get the last N lines from a file that match our message pattern."""
        matching_lines = []
        try:
            with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                # Read all lines and filter out system messages
                lines = [line.strip() for line in f.readlines() if line.strip()]
                for line in reversed(lines):  # Process lines in reverse
                    if not self._is_system_message(line):
                        matching_lines.append(line)
                        if len(matching_lines) >= n:
                            break
                return list(reversed(matching_lines))  # Return in original order
        except Exception as e:
            self.logger.error(f"Error reading last {n} lines: {e}")
            return []

    def _process_new_lines(self, file_path: str, from_start: bool = False):
        """Process new lines added to the log file."""
        try:
            if from_start:
                # Only process last 10 chat messages when starting
                self.logger.info("Reading last 10 chat messages...")
                lines = self._get_last_n_lines(file_path, 10)
                for line in lines:
                    self._process_line(line)
                # Set position to end of file
                with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                    f.seek(0, 2)  # Seek to end
                    self.last_position = f.tell()
            else:
                # Process new lines normally for real-time updates
                with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                    f.seek(self.last_position)
                    new_lines = f.readlines()
                    self.logger.debug(f"Read {len(new_lines)} lines from file")
                    self.last_position = f.tell()
                    
                    for line in new_lines:
                        line = line.strip()
                        if line:  # Skip empty lines
                            self.logger.debug(f"Processing raw line: {line}")
                            self._process_line(line)
                    
        except Exception as e:
            self.logger.error(f"Error reading log file: {e}")
            
    def _is_system_message(self, line: str) -> bool:
        """Check if a line is a system message."""
        # Skip empty lines first
        if not line:
            return True
            
        # Check system prefixes first - this should take priority
        for prefix in self.SYSTEM_PREFIXES:
            if line.startswith(prefix):
                return True
                
        # Only then check if it matches chat pattern
        # Chat messages have a specific format:
        # 1. Team chat: "(Survivor|Infected) ♥Name : message"
        # 2. Regular chat: "Name : message"
        chat_pattern = r'^(?:\((Survivor|Infected)\)\s+)?[^:]+\s+:\s+.+'
        if re.match(chat_pattern, line):
            return False
                
        return True  # Default to treating unknown formats as system messages
            
    def _clean_text(self, text: str | None) -> str | None:
        """Remove special characters from text."""
        if text is None:
            return None
            
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
            self.logger.debug(f"Regex pattern: {self.message_pattern.pattern}")
            if match:
                self.logger.debug(f"Line matched pattern: '{line}'")
                self.logger.debug(f"Match groups: {match.groups()}")
                
                groups = match.groups()
                if len(groups) >= 3:  # We expect at least 3 groups (team, player, message)
                    team_type = groups[0]  # First group is team type (Survivor/Infected)
                    player_name = groups[1]  # Second group is player name
                    message_content = groups[2]  # Third group is message content
                    
                    # Create message object with cleaned components
                    message = Message(
                        line=line,
                        team=self._clean_text(team_type) if team_type else None,
                        player=self._clean_text(player_name),
                        content=self._clean_text(message_content)
                    )
                    
                    if message.player:  # Only send if we got a player name
                        self.callback(message)
                else:
                    self.logger.debug(f"Not enough groups in match: {len(groups)}")
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
        self.handler = GameLogHandler(self.message_pattern, self.callback, str(self.log_path))
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