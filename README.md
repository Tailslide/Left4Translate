# Left4Translate

Automatically translate Left 4 Dead chat messages to English and display them on a Turing Smart Screen device.

## Overview

Left4Translate monitors your Left 4 Dead game chat, automatically translates non-English messages to English, and displays them on a secondary Turing Smart Screen display. This enhances communication with players using different languages during gameplay.

## Features

- Real-time chat message monitoring
- Automatic language detection and translation
- Display on Turing Smart Screen device
- Message caching to reduce translation API usage
- Configurable display settings
- Error recovery and logging

## Requirements

- Python 3.8 or higher
- Left 4 Dead game
- Turing Smart Screen device (3.5" or 5")
- Google Cloud Translation API key
- USB port for screen connection

## Hardware Setup

1. Connect your Turing Smart Screen to an available USB port
2. Note the COM port number from Device Manager (Windows) or `ls /dev/tty*` (Linux/Mac)
3. Enable console logging in Left 4 Dead:
   - Right-click Left 4 Dead in Steam
   - Select Properties
   - Set Launch Options: `-condebug -conclearlog`
   - Click OK
   - Launch game

The game will now automatically log all console output to the console.log file in your game directory. The exact path will depend on your Steam installation location and should be configured in `config/config.json`.

## Software Setup

1. Run the setup script to create virtual environment, install dependencies, and set up the Turing Smart Screen library:
```bash
python setup.py
```

2. Activate the virtual environment:
```bash
# On Windows:
.\venv\Scripts\activate

# On Unix/Linux/Mac:
source venv/bin/activate
```

3. Configure settings:
   - Copy `config/config.sample.json` to `config/config.json`
   - Update the following in `config/config.json`:
     - Game log path (path to your Left 4 Dead console.log)
     - Translation API key (from Google Cloud Console)
     - COM port (check Device Manager for correct port)
     - Other display preferences as needed

Note: The sample config contains placeholder values that must be replaced with your actual settings. Never commit your `config/config.json` file as it contains sensitive information.

## Usage

1. Start the application:
```bash
python src/main.py
```

2. The application will:
   - Connect to your Turing Smart Screen
   - Monitor Left 4 Dead chat messages
   - Automatically translate non-English messages
   - Display original and translated messages on screen

3. To stop the application:
   - Press Ctrl+C
   - The application will clean up and exit gracefully

## Testing

Individual components can be tested separately:

1. Test screen connection:
```bash
python src/tools/test_screen.py
```

2. Test configuration:
```bash
python src/tools/test_config.py
```

3. Test message reader:
```bash
python src/tools/test_message_reader.py
```

4. Test translation:

Unit Tests (Mock API):
```bash
python src/tools/test_translation.py
```

The unit test suite verifies:
- Automatic language detection
- Translation with explicit source language
- Translation caching mechanism
- Rate limiting behavior
- Error handling and retries
- Skip translation for text already in target language
- Cache statistics reporting

Live API Tests:
```bash
python src/tools/test_translation_live.py
```

The live test suite makes actual API calls to verify:
- Real translations from Spanish and French
- Live language detection
- Caching with real translations
- Integration with Google Cloud Translation API

Note: Live tests require a valid API key in config.json and will incur API usage costs.

## Configuration

The config.json file supports the following settings:

### Game Settings
- logPath: Path to Left 4 Dead console log
- pollInterval: How often to check for new messages
- messageFormat: Regular expression for parsing chat messages

### Translation Settings
- service: Translation service to use (currently Google)
- apiKey: Your translation API key
- targetLanguage: Language to translate to (e.g., "en")
- cacheSize: Number of translations to cache
- rateLimitPerMinute: API call rate limit

### Screen Settings
- port: COM port for Turing Smart Screen
- baudRate: Communication speed (usually 115200)
- brightness: Screen brightness (0-100)
- display: Layout and message display settings

### Logging Settings
- level: Log level (info, debug, etc.)
- path: Log file location
- maxSize: Maximum log file size
- backupCount: Number of backup logs to keep

## Troubleshooting

1. Screen Connection Issues:
   - Verify COM port number in Device Manager
   - Try running as administrator
   - Check USB connection
   - Ensure no other program is using the port

2. Translation Issues:
    - Verify API key is correct
    - Check internet connection
    - Monitor API quota usage
    - Check log files for errors
    - Enable debug logging in config.json for detailed translation diagnostics:
      ```json
      {
        "logging": {
          "level": "debug"
        }
      }
      ```
    Debug logs will show:
    - Full request/response data
    - Language detection results and confidence
    - Text lengths and content
    - Rate limiting status
    - Detailed API error messages
    - Text cleaning results (removal of color codes and control characters)

    Note: The translation service automatically handles:
    - Color codes and control characters (e.g., \x03, \x01)
    - Both actual control characters and escaped sequences
    - Preserves original text formatting in the display while cleaning for translation

3. Game Log Issues:
   - Verify launch options include `-condebug -conclearlog`
   - Check console.log exists in game directory
   - Ensure game has write permissions
   - Restart game if needed

## Architecture

See [Architecture Documentation](docs/architecture.md) for detailed technical information about the system design and implementation.

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- [Turing Smart Screen Python Library](https://github.com/mathoudebine/turing-smart-screen-python)
- Google Cloud Translation API
- Left 4 Dead game and community