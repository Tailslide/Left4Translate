#!/usr/bin/env python3
import sys
from pathlib import Path

# Add src directory to Python path
src_dir = Path(__file__).resolve().parent.parent
sys.path.append(str(src_dir))

from config.config_manager import ConfigManager

def test_config():
    """Test configuration loading and validation."""
    print("Testing configuration...")
    
    # Try loading actual config
    config_path = Path(src_dir).parent / "config" / "config.json"
    
    if not config_path.exists():
        print(f"Config not found at: {config_path}")
        return
        
    try:
        # Initialize config manager
        config_manager = ConfigManager(str(config_path))
        
        # Load configuration
        print("\nLoading configuration...")
        config_manager.load_config()
        print("Configuration loaded successfully")
        
        # Validate configuration
        print("\nValidating configuration...")
        errors = config_manager.validate_config()
        
        if errors:
            print("\nConfiguration validation errors:")
            for error in errors:
                print(f"- {error}")
        else:
            print("Configuration validation passed")
            
        # Print configurations
        print("\nGame Configuration:")
        game_config = config_manager.get_game_config()
        print(f"- Log Path: {game_config.log_path}")
        print(f"- Poll Interval: {game_config.poll_interval}")
        
        print("\nTranslation Configuration:")
        trans_config = config_manager.get_translation_config()
        print(f"- Service: {trans_config.service}")
        print(f"- Target Language: {trans_config.target_language}")
        print(f"- Cache Size: {trans_config.cache_size}")
        
        print("\nScreen Configuration:")
        screen_config = config_manager.get_screen_config()
        print(f"- Port: {screen_config.port}")
        print(f"- Baud Rate: {screen_config.baud_rate}")
        print(f"- Brightness: {screen_config.brightness}")
        
        print("\nLogging Configuration:")
        log_config = config_manager.get_logging_config()
        print(f"- Level: {log_config.level}")
        print(f"- Path: {log_config.path}")
        
    except Exception as e:
        print(f"\nError during configuration test: {e}")
        
if __name__ == "__main__":
    test_config()