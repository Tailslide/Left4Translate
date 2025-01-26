import json
from pathlib import Path
from typing import Any, Dict, List, Optional, TypeVar
from dataclasses import dataclass

T = TypeVar('T')

@dataclass
class GameConfig:
    log_path: str
    poll_interval: int
    message_format: Dict[str, Any]

@dataclass
class TranslationConfig:
    service: str
    api_key: str
    target_language: str
    cache_size: int
    rate_limit_per_minute: int
    retry_attempts: int

@dataclass
class ScreenConfig:
    port: str
    baud_rate: int
    brightness: int
    refresh_rate: int
    display: Dict[str, Any]

@dataclass
class LoggingConfig:
    level: str
    path: str
    max_size: str
    backup_count: int
    format: str

class ConfigManager:
    """Manages application configuration loading and validation."""
    
    def __init__(self, config_path: str):
        # Convert to Path and resolve to handle Windows paths correctly
        self.config_path = Path(config_path).resolve()
        self.config: Dict[str, Any] = {}
        
    def load_config(self) -> None:
        """Load configuration from file."""
        if not self.config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {self.config_path}")
            
        try:
            with open(self.config_path, 'r') as f:
                self.config = json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in configuration file: {e}")
            
    def validate_config(self) -> List[str]:
        """Validate the configuration and return list of errors."""
        errors = []
        
        # Validate game configuration
        if "game" not in self.config:
            errors.append("Missing 'game' configuration section")
        else:
            game_config = self.config["game"]
            if "logPath" not in game_config:
                errors.append("Missing 'game.logPath' setting")
            if "pollInterval" not in game_config:
                errors.append("Missing 'game.pollInterval' setting")
            if "messageFormat" not in game_config:
                errors.append("Missing 'game.messageFormat' setting")
                
        # Validate translation configuration
        if "translation" not in self.config:
            errors.append("Missing 'translation' configuration section")
        else:
            trans_config = self.config["translation"]
            if "apiKey" not in trans_config:
                errors.append("Missing 'translation.apiKey' setting")
            if "service" not in trans_config:
                errors.append("Missing 'translation.service' setting")
                
        # Validate screen configuration
        if "screen" not in self.config:
            errors.append("Missing 'screen' configuration section")
        else:
            screen_config = self.config["screen"]
            if "port" not in screen_config:
                errors.append("Missing 'screen.port' setting")
            if "baudRate" not in screen_config:
                errors.append("Missing 'screen.baudRate' setting")
                
        # Validate logging configuration
        if "logging" not in self.config:
            errors.append("Missing 'logging' configuration section")
        else:
            log_config = self.config["logging"]
            if "level" not in log_config:
                errors.append("Missing 'logging.level' setting")
            if "path" not in log_config:
                errors.append("Missing 'logging.path' setting")
                
        return errors
        
    def get_game_config(self) -> GameConfig:
        """Get game configuration settings."""
        config = self.config.get("game", {})
        return GameConfig(
            log_path=config.get("logPath", ""),
            poll_interval=config.get("pollInterval", 1000),
            message_format=config.get("messageFormat", {})
        )
        
    def get_translation_config(self) -> TranslationConfig:
        """Get translation configuration settings."""
        config = self.config.get("translation", {})
        return TranslationConfig(
            service=config.get("service", "google"),
            api_key=config.get("apiKey", ""),
            target_language=config.get("targetLanguage", "en"),
            cache_size=config.get("cacheSize", 1000),
            rate_limit_per_minute=config.get("rateLimitPerMinute", 100),
            retry_attempts=config.get("retryAttempts", 3)
        )
        
    def get_screen_config(self) -> ScreenConfig:
        """Get screen configuration settings."""
        config = self.config.get("screen", {})
        return ScreenConfig(
            port=config.get("port", "COM8"),
            baud_rate=config.get("baudRate", 115200),
            brightness=config.get("brightness", 80),
            refresh_rate=config.get("refreshRate", 1000),
            display=config.get("display", {})
        )
        
    def get_logging_config(self) -> LoggingConfig:
        """Get logging configuration settings."""
        config = self.config.get("logging", {})
        return LoggingConfig(
            level=config.get("level", "info"),
            path=config.get("path", "logs/app.log"),
            max_size=config.get("maxSize", "10MB"),
            backup_count=config.get("backupCount", 5),
            format=config.get("format", "%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        )
        
    def get_setting(self, key: str, default: Optional[T] = None) -> T:
        """Get a specific configuration setting."""
        keys = key.split('.')
        value = self.config
        
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k, default)
            else:
                return default
                
        return value if value is not None else default