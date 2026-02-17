import sys
import signal
import logging
from pathlib import Path
import os
import time
import argparse

# Import all modules at top level (but only initialize logging when needed)
from config.config_manager import ConfigManager
from reader.message_reader import GameMessageReader, Message
from translator.translation_service import TranslationService
from display.screen_controller import ScreenController
from audio.voice_translation_manager import VoiceTranslationManager

__version__ = "1.2.7"  # Updated version with chat message display fix


def get_executable_dir():
    """Get the directory containing the executable or script."""
    exe_dir = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return exe_dir


def setup_logging(config_path: str):
    """Set up logging configuration."""
    import json
    
    # Load logging config from config.json
    with open(config_path) as f:
        config = json.load(f)
    log_config = config.get("logging", {})
    
    # Create logs directory if it doesn't exist
    log_dir = Path(log_config.get("path", "logs/app.log")).parent
    log_dir.mkdir(parents=True, exist_ok=True)
    
    # Set up root logger with UTF-8 encoding
    logging.basicConfig(
        level=getattr(logging, log_config.get("level", "INFO").upper()),
        format=log_config.get("format", "%(asctime)s - %(name)s - %(levelname)s - %(message)s"),
        handlers=[
            logging.FileHandler(log_config.get("path", "logs/app.log"), encoding='utf-8'),
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    return logging.getLogger(__name__)


def resolve_config_path(args, exe_dir):
    """Resolve config path from args or default locations."""
    if args.config:
        return args.config
    elif os.path.exists(os.path.join(exe_dir, "config.json")):
        return os.path.join(exe_dir, "config.json")
    else:
        return os.path.join(exe_dir, "config", "config.json")


def main():
    """Application entry point."""
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Left4Translate - Real-time chat translation for Left 4 Dead 2')
    parser.add_argument('--config', help='Path to config file')
    parser.add_argument('--mode', choices=['chat', 'voice', 'both'], default='both',
                        help='Operating mode: chat, voice, or both (default: both)')
    args = parser.parse_args()
    
    # Resolve config path before setting up logging
    exe_dir = get_executable_dir()
    config_path = resolve_config_path(args, exe_dir)
    
    # Set up logging first
    logger = setup_logging(config_path)
    
    # Run the application
    app = Left4Translate(config_path, args.mode)
    app.start()


class Left4Translate:
    """Main application class."""
    
    def __init__(self, config_path: str, mode: str = 'both'):
        self.running = False
        self.mode = mode
        
        try:
            # Load configuration
            self.config_manager = ConfigManager(config_path)
            self.config_manager.load_config()
            
            # Set up application logging
            self.logger = logging.getLogger(__name__)
            
            # Validate configuration
            errors = self.config_manager.validate_config()
            if errors:
                for error in errors:
                    self.logger.error(f"Configuration error: {error}")
                print("\nConfiguration errors found. Please:")
                print("1. Copy config.sample.json to config.json")
                print("2. Add your Google Cloud Translation API key")
                print("3. Configure your screen settings")
                sys.exit(1)
        except FileNotFoundError:
            print("\nConfiguration file not found. Please:")
            print("1. Copy config.sample.json to config.json")
            print("2. Add your Google Cloud Translation API key")
            print("3. Configure your screen settings")
            sys.exit(1)
            
        # Initialize components
        self._init_components()
        
        # Set up signal handlers
        signal.signal(signal.SIGINT, self._handle_shutdown)
        signal.signal(signal.SIGTERM, self._handle_shutdown)
        
    def _init_components(self):
        """Initialize application components."""
        try:
            # Get configurations
            game_config = self.config_manager.get_game_config()
            trans_config = self.config_manager.get_translation_config()
            screen_config = self.config_manager.get_screen_config()
            
            # Initialize translation service
            self.translator = TranslationService(
                api_key=trans_config.api_key,
                target_language=trans_config.target_language,
                cache_size=trans_config.cache_size,
                rate_limit_per_minute=trans_config.rate_limit_per_minute,
                retry_attempts=trans_config.retry_attempts
            )
            
            # Initialize screen controller
            self.screen = ScreenController(
                port=screen_config.port,
                baud_rate=screen_config.baud_rate,
                brightness=screen_config.brightness,
                max_messages=screen_config.display.get("maxMessages", 5),
                message_timeout=screen_config.display.get("messageTimeout", 10000),
                margin=screen_config.display.get("layout", {}).get("margin", 5),
                spacing=screen_config.display.get("layout", {}).get("spacing", 2)
            )
            
            # Initialize chat message reader if mode is 'chat' or 'both'
            if self.mode in ['chat', 'both']:
                self.reader = GameMessageReader(
                    log_path=game_config.log_path,
                    message_pattern=game_config.message_format["regex"],
                    callback=self._handle_message
                )
            else:
                self.reader = None
                
            # Initialize voice translation manager if mode is 'voice' or 'both'
            if self.mode in ['voice', 'both']:
                # Get the full config dictionary
                config_dict = self.config_manager.get_config()
                
                # Initialize voice translation manager
                self.voice_manager = VoiceTranslationManager(
                    config=config_dict,
                    translation_service=self.translator,
                    screen_controller=self.screen
                )
            else:
                self.voice_manager = None
                
        except Exception as e:
            self.logger.error(f"Failed to initialize components: {e}")
            sys.exit(1)
            
    def _handle_message(self, message: Message):
        """Handle new chat messages."""
        try:
            # Use the already-parsed message fields from the Message dataclass
            # The GameLogHandler already extracted player, content, and team
            player_name = message.player
            chat_message = message.content
            team_type = message.team
            
            if player_name is None or chat_message is None:
                self.logger.debug("Message missing player name or content")
                return
            
            self.logger.info(f"New message from {player_name}: {chat_message}")
            
            try:
                # Detect and translate message
                source_lang = self.translator.detect_language(chat_message)
                
                # Only translate if not already in target language
                if source_lang != self.config_manager.get_translation_config().target_language:
                    translated = self.translator.translate(
                        chat_message,
                        source_language=source_lang
                    )
                else:
                    translated = chat_message
            except Exception as e:
                self.logger.error(f"Translation error: {e}")
                translated = chat_message  # Use original message if translation fails
            
            # Display message
            self.screen.display_message(
                player=player_name,
                original=chat_message,
                translated=translated,
                is_team_chat=bool(team_type)  # True if team chat (Survivor/Infected)
            )
            
            if translated != chat_message:
                self.logger.info(f"Translated ({source_lang}): {translated}")
            else:
                self.logger.info("Using original message")
                
        except Exception as e:
            self.logger.error(f"Error handling message: {e}")
            
    def _handle_shutdown(self, signum, frame):
        """Handle shutdown signals."""
        self.logger.info("Shutdown signal received, cleaning up...")
        self.stop()
        
    def start(self):
        """Start the application."""
        try:
            self.logger.info(f"Starting Left4Translate v{__version__}...")
            self.running = True
            
            # Connect to screen
            if not self.screen.connect():
                self.logger.error("Failed to connect to screen")
                # Graceful degradation: continue running without screen
                self.logger.warning("Continuing without screen - translations will be logged but not displayed")
            
            # Start chat message monitoring if enabled
            if self.reader and self.mode in ['chat', 'both']:
                self.reader.start_monitoring(from_start=True)
                self.logger.info("Started monitoring game log (showing last 10 lines)")
                
            # Start voice translation if enabled
            if self.voice_manager and self.mode in ['voice', 'both']:
                if self.voice_manager.start():
                    self.logger.info("Started voice translation mode")
                else:
                    self.logger.error("Failed to start voice translation mode")
            
            # Log the active modes
            if self.mode == 'both':
                self.logger.info("Left4Translate is running in chat and voice translation modes. Press Ctrl+C to stop.")
            elif self.mode == 'chat':
                self.logger.info("Left4Translate is running in chat translation mode only. Press Ctrl+C to stop.")
            elif self.mode == 'voice':
                self.logger.info("Left4Translate is running in voice translation mode only. Press Ctrl+C to stop.")
            
            # Keep the main thread alive
            while self.running:
                time.sleep(1)
            
        except Exception as e:
            self.logger.error(f"Error starting application: {e}")
            self.stop()
            
    def stop(self):
        """Stop the application."""
        self.running = False
        
        try:
            self.logger.info("Stopping Left4Translate...")
            
            # Stop components
            if self.reader:
                self.reader.stop_monitoring()
                
            if self.voice_manager:
                self.voice_manager.stop()
                
            self.screen.disconnect()
            
            self.logger.info("Left4Translate stopped")
            
        except Exception as e:
            self.logger.error(f"Error stopping application: {e}")


if __name__ == "__main__":
    main()
