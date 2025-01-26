# Left4Translate Architecture

## System Overview

Left4Translate is a system designed to capture, translate, and display Left 4 Dead chat messages on a secondary Turing Smart Screen display. The system provides real-time translation of in-game chat messages to English, enhancing communication for non-English speaking players.

## Components

### 1. Game Message Reader
- Monitors Left 4 Dead log files for new chat messages
- Implements the `watchdog` library for real-time file monitoring
- Message parsing using configurable regex patterns
- Component Interface:
  ```python
  class GameMessageReader:
      def start_monitoring()
      def stop_monitoring()
      def on_message(callback: Callable[[Message], None])
  ```

### 2. Translation Service
- Integrates with translation API (configurable)
- Implements LRU cache for common translations
- Handles rate limiting and quotas
- Component Interface:
  ```python
  class TranslationService:
      def translate(text: str, source_lang: Optional[str] = None) -> str
      def detect_language(text: str) -> str
      def clear_cache()
      def get_cache_stats() -> Dict[str, int]
  ```

### 3. Smart Screen Controller
- Uses turing-smart-screen-python library
- Manages message queue and display updates
- Handles screen layout and formatting
- Component Interface:
  ```python
  class ScreenController:
      def connect(port: str, baud_rate: int)
      def disconnect()
      def display_message(message: TranslatedMessage)
      def clear_display()
      def set_brightness(level: int)
  ```

### 4. Configuration Manager
- Loads and validates configuration
- Provides type-safe access to settings
- Handles environment variables
- Component Interface:
  ```python
  class ConfigManager:
      def load_config(path: str)
      def get_setting[T](key: str, default: Optional[T] = None) -> T
      def validate_config() -> List[str]  # Returns validation errors
  ```

### 5. Main Orchestrator
- Application lifecycle management
- Error handling and recovery
- Event logging
- Component Interface:
  ```python
  class Orchestrator:
      def start()
      def stop()
      def handle_error(error: Exception)
      def get_status() -> SystemStatus
  ```

## Data Models

### Message Model
```python
@dataclass
class Message:
    timestamp: datetime
    player: str
    content: str
    original_language: Optional[str] = None

@dataclass
class TranslatedMessage(Message):
    translated_content: str
    translation_service: str
```

### Configuration Model
```python
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
    rate_limit: int

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
```

## Error Handling Strategy

1. Game Message Reader:
   - File access errors: Retry with exponential backoff
   - Parse errors: Log and skip malformed messages
   - File rotation: Reattach to new file

2. Translation Service:
   - API errors: Retry with backoff, fallback to cache
   - Rate limiting: Queue messages, implement token bucket
   - Network errors: Circuit breaker pattern

3. Screen Controller:
   - Connection errors: Auto-reconnect
   - Display errors: Clear and retry
   - Hardware errors: Safe mode fallback

## Logging Strategy

1. Application Events:
   - Component lifecycle events
   - Configuration changes
   - Error conditions
   - Performance metrics

2. Message Events:
   - Original messages
   - Translation results
   - Display updates

3. System Events:
   - Resource usage
   - Component health
   - Error rates

## Testing Strategy

1. Unit Tests:
   - Component isolation
   - Mock external services
   - Configuration validation
   - Error handling

2. Integration Tests:
   - Component interaction
   - Configuration loading
   - File monitoring
   - Screen communication

3. End-to-End Tests:
   - Full message flow
   - Error recovery
   - Performance testing

## Performance Considerations

1. Message Processing:
   - Batch processing for multiple messages
   - Async translation requests
   - Message priority queue

2. Resource Usage:
   - Translation cache size limits
   - Log rotation and cleanup
   - Memory usage monitoring

3. Display Updates:
   - Message coalescing
   - Update rate limiting
   - Screen buffer management

## Security Considerations

1. Configuration:
   - API key protection
   - Sensitive data encryption
   - Configuration validation

2. External Services:
   - HTTPS for API calls
   - Rate limiting
   - Request validation

3. File Access:
   - Minimal permissions
   - Path validation
   - Input sanitization

## Deployment

1. Prerequisites:
   - Python 3.8+
   - Required system libraries
   - USB serial port access

2. Installation:
   - Python package installation
   - Configuration setup
   - Service installation

3. Monitoring:
   - Log aggregation
   - Error alerting
   - Performance metrics

## Future Enhancements

1. Features:
   - Multiple game support
   - Custom translation services
   - Web configuration interface
   - Message filtering rules

2. Technical:
   - Container support
   - Plugin architecture
   - API endpoints
   - Performance optimizations

3. User Experience:
   - GUI configuration
   - Real-time statistics
   - Custom display layouts
   - Theme support