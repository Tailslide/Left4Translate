#!/usr/bin/env python3
"""Test script for translating console log messages in real-time."""

import sys
import os
import argparse
import logging
import time

# Add the project root directory to the Python path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(project_root)

from src.translator.translation_service import TranslationService
from src.reader.message_reader import GameMessageReader
from src.config.config_manager import ConfigManager

def main():
    """Main entry point."""
    # Set up argument parser
    parser = argparse.ArgumentParser(description='Test log translation with optional timeout')
    parser.add_argument('--timeout', type=int, default=0, help='Stop after N seconds (0 for no timeout)')
    parser.add_argument('--read-once', action='store_true', help='Read existing log content and exit')
    parser.add_argument('--from-start', action='store_true', help='Start reading from beginning of file')
    parser.add_argument('--log-path', help='Path to log file to test (overrides config)')
    
    args = parser.parse_args()
    
    # Set up logging with UTF-8 encoding
    import sys
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )
    # Force UTF-8 encoding for stdout
    sys.stdout.reconfigure(encoding='utf-8')
    logger = logging.getLogger(__name__)
    
    try:
        # Initialize config
        config_path = os.path.join(project_root, 'config', 'config.json')
        config = ConfigManager(config_path)
        
        # Load config
        config.load_config()
        
        # Get configurations
        game_config = config.get_game_config()
        log_path = args.log_path if args.log_path else game_config.log_path
        message_pattern = game_config.message_format['regex']
        
        # Initialize translation service
        translation_config = config.get_translation_config()
        translator = TranslationService(
            api_key=translation_config.api_key,
            target_language=translation_config.target_language,
            cache_size=translation_config.cache_size,
            rate_limit_per_minute=translation_config.rate_limit_per_minute,
            retry_attempts=translation_config.retry_attempts
        )
        
        print(f"Starting translation test...")
        print(f"Log file path: {log_path}")
        print(f"Message pattern: {message_pattern}")
        print(f"Mode: {'Read existing content and exit' if args.read_once else 'Monitor continuously'}")
        if args.from_start:
            print("Starting from beginning of file")
        print("\nWaiting for messages... (Press Ctrl+C to stop)")
        print("--------------------------------------------------")
        
        def handle_message(message):
            """Handle a new chat message."""
            # Translate Spanish messages
            if message.content:
                try:
                    # Print original message
                    team_str = f"({message.team}) " if message.team else ""
                    print(f"{team_str}{message.player}: {message.content}")
                    
                    # Only translate if message contains Spanish characters or common Spanish words
                    if (any(ord(c) > 127 for c in message.content) or
                        any(word in message.content.lower() for word in ['soy', 'por', 'las', 'que', 'muy'])):
                        translation = translator.translate(message.content)
                        print(f"Translated: {translation}")
                    print("--------------------------------------------------")
                except Exception as e:
                    logger.error(f"Translation error: {e}")
        
        # Initialize message reader
        reader = GameMessageReader(log_path, message_pattern, handle_message)
        
        # Start monitoring
        reader.start_monitoring(from_start=args.from_start)
        
        # If read once mode, wait a bit for processing then exit
        if args.read_once:
            time.sleep(1)
            reader.stop_monitoring()
        else:
            # Otherwise run until timeout or Ctrl+C
            start_time = time.time()
            try:
                while True:
                    if args.timeout > 0 and time.time() - start_time > args.timeout:
                        print("\nTimeout reached")
                        break
                    time.sleep(0.1)
            finally:
                reader.stop_monitoring()
                
    except KeyboardInterrupt:
        print("\nStopped by user")
    except Exception as e:
        logger.error(f"Error: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()