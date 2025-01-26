#!/usr/bin/env python3
import json
import sys
import time
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

from config.config_manager import ConfigManager
from reader.message_reader import GameMessageReader, Message

def message_callback(message: Message):
    """Callback function to handle detected messages."""
    print(f"\nNew message detected:")
    print(f"Timestamp: {message.timestamp}")
    print(f"Player: {message.player}")
    print(f"Content: {message.content}")
    print("-" * 50)

def main():
    """Test the message reader functionality."""
    try:
        # Load configuration
        config_manager = ConfigManager("config/config.json")
        config_manager.load_config()
        
        # Validate configuration
        errors = config_manager.validate_config()
        if errors:
            print("Configuration errors:")
            for error in errors:
                print(f"- {error}")
            return
        
        # Get game configuration
        game_config = config_manager.get_game_config()
        log_path = game_config.log_path
        message_pattern = game_config.message_format["regex"]
        
        print(f"Starting message reader test...")
        print(f"Log file path: {log_path}")
        print(f"Message pattern: {message_pattern}")
        print("\nWaiting for messages... (Press Ctrl+C to stop)")
        print("-" * 50)
        
        # Initialize message reader
        reader = GameMessageReader(
            log_path=log_path,
            message_pattern=message_pattern,
            callback=message_callback
        )
        
        # Start monitoring
        reader.start_monitoring()
        
        # Keep running until interrupted
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nStopping message reader...")
            reader.stop_monitoring()
            
    except FileNotFoundError as e:
        print(f"Error: {e}")
        print("Please verify the log file path in your configuration.")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()