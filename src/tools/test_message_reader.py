#!/usr/bin/env python3
import json
import sys
import time
from pathlib import Path
import argparse

sys.path.append(str(Path(__file__).parent.parent))

from config.config_manager import ConfigManager
from reader.message_reader import GameMessageReader, Message

def message_callback(message: Message):
    """Callback function to handle detected messages."""
    print(f"\nNew message detected:")
    if message.team:
        print(f"Team: {message.team}")
    print(f"Player: {message.player}")
    print(f"Content: {message.content}")
    print("-" * 50)

def main():
    """Test the message reader functionality."""
    parser = argparse.ArgumentParser(description='Test message reader with optional timeout')
    parser.add_argument('--timeout', type=int, default=0, help='Stop after N seconds (0 for no timeout)')
    parser.add_argument('--read-once', action='store_true', help='Read existing log content and exit')
    parser.add_argument('--from-start', action='store_true', help='Start reading from beginning of file')
    args = parser.parse_args()

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
        if args.read_once:
            print("Mode: Read existing content and exit")
        elif args.timeout > 0:
            print(f"Mode: Monitor with {args.timeout} second timeout")
        else:
            print("Mode: Monitor continuously")
        if args.from_start:
            print("Starting from beginning of file")
        print("\nWaiting for messages... (Press Ctrl+C to stop)")
        print("-" * 50)
        
        # Initialize message reader
        reader = GameMessageReader(
            log_path=log_path,
            message_pattern=message_pattern,
            callback=message_callback
        )
        
        try:
            if args.read_once:
                # Just process existing content and exit
                if Path(log_path).exists():
                    reader.handler._process_new_lines(str(log_path), args.from_start)
                print("\nFinished reading existing content")
            else:
                # Start monitoring
                reader.start_monitoring(args.from_start)
                
                # Keep running until timeout or interrupted
                start_time = time.time()
                while True:
                    if args.timeout > 0 and time.time() - start_time >= args.timeout:
                        print(f"\nTimeout reached ({args.timeout} seconds)")
                        break
                    time.sleep(1)
        except KeyboardInterrupt:
            print("\nStopping message reader...")
        finally:
            if not args.read_once:
                reader.stop_monitoring()
            print("Message reader stopped")
            
    except FileNotFoundError as e:
        print(f"Error: {e}")
        print("Please verify the log file path in your configuration.")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()