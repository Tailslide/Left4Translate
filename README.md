# Left4Translate v1.2.2

Real-time chat and voice translation for Left 4 Dead 2, displaying translated messages on a Turing Smart Screen.
See here for compatible screen: https://www.aliexpress.com/item/1005003931363455.html
See here for more info on screens: https://github.com/mathoudebine/turing-smart-screen-python

[![Version](https://img.shields.io/badge/version-1.2.2-blue.svg)](https://github.com/yourusername/Left4Translate)

## Changelog

### v1.2.3
- Fixed potential API rate limit errors by adding rate limiting to language detection calls.

### v1.2.2
- Fixed issue where chat messages weren't showing on the Turing screen at startup
- Added "Registered" to system message prefixes to properly filter out system messages
- Fixed message processing to correctly handle both team chat and regular chat formats
- Improved message filtering to ensure only actual chat messages are displayed

### v1.2.1
- Fixed voice translation error: Corrected parameter name mismatch in TranslationService.translate() call
- Voice translation now correctly passes source_language instead of target_language parameter
- Fixed target language configuration in voice translation manager to use the correct configuration section
- Changed default clipboard format to only copy translated text instead of both original and translated

### v1.2.0
- Initial release with voice translation feature

## Features

### Chat Translation
- Real-time monitoring of L4D2 console log with initial processing of last 10 chat messages
- Automatic translation of chat messages to English in real-time
- Support for both regular and team chat messages
- Support for special characters and emojis in player names
- Support for all game chat formats including infected team messages
- Improved chat message detection with UTF-8 encoding support and error handling
- Fixed handling of special characters in player names and messages
- Enhanced system message filtering with prioritized prefix detection to properly handle system messages containing colons
- Improved handling of non-translatable content:
  * Short messages and punctuation-only content
  * Numbers and mathematical expressions (e.g., "1+?")
  * Emoticons and special characters
  * Messages with undefined language
- Smart translation of gaming slang and casual expressions with extensive Spanish gaming dictionary and context-aware translations:
  * Game mechanics: "rushear" → "rush", "campear" → "camping", "farmear" → "farming"
  * Special infected: "bruja" → "witch", "tanque" → "tank"
  * Unique Spanish gaming slang and expressions that wouldn't be properly translated by Google Translate:
    * Gaming terms: "manco" → "noob", "puntaje" → "score", "reconectar" → "reconnecting"
    * Reactions: "ostia tio" → "holy crap dude", "a huevo" → "hell yeah", "no mames" → "no way", "si" → "yeah" (only as standalone or in "eso si")

### Voice Translation (New!)
- Record speech by holding down a mouse button (default: forward button, configured as "button4")
- Transcribe speech to text using Google Cloud Speech-to-Text
- Translate transcribed text to the target language (default: Spanish)
- Display both original and translated text on the Turing Smart Screen
- Automatically copy translated text to clipboard for easy pasting
- Configurable settings for audio recording, transcription, translation, and display
- Works as a standalone feature or alongside chat translation
- Enhanced microphone volume diagnostics:
  * Automatic volume level detection during initialization and recording
  * Detailed feedback on audio levels with dB measurements
  * Suggestions for alternative microphones when volume is too low
  * Customized error messages based on audio quality
- Visual error feedback for transcription issues with specific guidance

### General Features
- Display of translated messages on a Turing Smart Screen
- Message caching to reduce API calls
- Rate limiting to prevent API overuse
- Configurable display settings
- Extensive logging for troubleshooting with privacy-focused audio data handling

## Requirements

- Python 3.10+
- Left 4 Dead 2 (for chat translation feature)
- Turing Smart Screen
    See here for compatible screen: https://www.aliexpress.com/item/1005003931363455.html
    See here for more info on screens: https://github.com/mathoudebine/turing-smart-screen-python
- Google Cloud Authentication:
    - Translation API key for chat and voice translation
    - Speech-to-Text service account credentials for voice transcription (can use the same project)
    - See: https://stackoverflow.com/questions/4854388/google-api-key-for-translation for Translation API
    - See: https://cloud.google.com/speech-to-text/docs/quickstart-client-libraries for Speech-to-Text service account setup
    - Note we are using Google Translate API V2 which has 500,000 free characters per month.
    - Speech-to-Text API offers 60 minutes of free transcription per month.
    - Also when you first sign up for Google Cloud API you get like $500 free credit for the first year.
- Working microphone (for voice translation feature)
- Roboto Mono fonts (included in res/fonts/roboto-mono)

### Important Note About Speech-to-Text Authentication

Google Cloud Speech-to-Text API requires proper authentication using a service account with appropriate IAM permissions. Unlike the Translation API which can work with just an API key, Speech-to-Text requires a service account JSON credentials file.

To set up authentication for Speech-to-Text:

1. Go to the Google Cloud Console > IAM & Admin > Service Accounts
2. Create a new service account with the "Cloud Speech Client" role
3. Create a key for this service account (JSON format)
4. Save the JSON file to a secure location on your computer
5. Add the path to this file in the `voice_translation.speech_to_text.credentials_path` setting in `config.json`

Without proper service account credentials, the voice translation feature will not work correctly.

## Installation

1. Clone this repository
2. Install dependencies: `pip install -r requirements.txt`
3. Copy `config/config.sample.json` to `config/config.json`
4. Add your Google Cloud Translation API key to `config.json`
5. For voice translation, create a service account and download the JSON credentials file:
   - Go to the Google Cloud Console > IAM & Admin > Service Accounts
   - Create a new service account with the "Cloud Speech Client" role
   - Create a key for this service account (JSON format)
   - Save the JSON file to a secure location
   - Add the path to this file in the `voice_translation.speech_to_text.credentials_path` setting in `config.json`
6. Configure your screen settings in `config.json`

### Building Executable

To create a standalone executable:

1. Create and activate a virtual environment (recommended):
   ```bash
   python -m venv venv
   .\venv\Scripts\activate  # Windows
   source venv/bin/activate # Linux/Mac
   ```
2. Install dependencies: `pip install -r requirements.txt`
3. Build the executable: `pyinstaller Left4Translate.spec`
4. Create your configuration:
   - Copy `config.sample.json` from the dist directory to `config.json`
   - Add your Google Cloud Translation API key to `config.json`
   - For voice translation, add the path to your service account credentials file in `config.json`
   - Configure your screen settings in `config.json`

The executable will be created in the `dist` directory. All required resources (fonts, config samples, etc.) are automatically included in the build. Note that you must create your own config.json with your API key - this is not included in the build for security reasons.
| 
| **Note on PyInstaller Build Issues:** If you encounter an `ImportError: DLL load failed while importing _ctypes` when running the built executable, you may need to explicitly add `'ctypes'` to the `hiddenimports` list within the `Left4Translate.spec` file and rebuild. This ensures PyInstaller bundles the necessary libraries used by dependencies like `pyserial`.

## Configuration

The `config.json` file contains all settings:

```json
{
  "game": {
    "logPath": "path/to/left4dead2/console.log",
    "pollInterval": 1000,
    "messageFormat": {
      "regex": "...",  // Pattern for parsing chat messages
      "groups": {
        "team": 1,     // Group number for team name
        "player": "2,4", // Group numbers for player name
        "message": "3,5" // Group numbers for message content
      }
    }
  },
  "translation": {
    "service": "google",
    "apiKey": "YOUR_API_KEY_HERE",
    "targetLanguage": "en",
    "cacheSize": 1000,
    "rateLimitPerMinute": 100,
    "retryAttempts": 3
  },
  "screen": {
    "port": "COM8",
    "baudRate": 115200,
    "brightness": 50,
    "refreshRate": 1000,
    "display": {
      "fontSize": 14,
      "maxMessages": 12,
      "messageTimeout": 0,
      "layout": {
        "margin": 2,
        "spacing": 2
      }
      // Messages are automatically word-wrapped to fit the screen width
    }
  },
  "voice_translation": {
    "enabled": true,
    "trigger_button": {
      "button": "button4",
      "modifier_keys": []
    },
    "audio": {
      "sample_rate": 16000,
      "channels": 1,
      "device": "default"
    },
    "speech_to_text": {
      "language": "en-US",
      "model": "default",
      "credentials_path": "path/to/your-service-account-credentials.json"
    },
    "translation": {
      "target_language": "es",
      "show_original": true
    },
    "display": {
      "show_original": true,
      "show_translated": true,
      "clear_after": 5000
    },
    "clipboard": {
      "auto_copy": true,
      "format": "translated"
    }
  }
}
```

For detailed information about voice translation configuration options, see [Voice Translation Documentation](docs/voice_translation.md).

## Usage

### Basic Setup

1. Plug in your turing screen.
2. Copy config.sample.json to config.json
3. Update config.json with your turing screen com port number See: https://github.com/mathoudebine/turing-smart-screen-python
4. Update config.json with your Google Cloud API key. See: https://stackoverflow.com/questions/4854388/google-api-key-for-translation

### For Chat Translation

1. Start Left 4 Dead 2
2. Enable console logging: `con_logfile console.log`
3. Optionally set this in steam launch options: `-condebug -conclearlog`
4. Update config.json log file path if it's not in default location.
5. Run the translator in chat mode: `python src/main.py --mode chat`

### For Voice Translation

1. Ensure your microphone is properly connected and working
2. Configure the voice translation settings in config.json
3. Run the translator in voice mode: `python src/main.py --mode voice`

### For Both Features

Run the translator with both features enabled: `python src/main.py --mode both` (or simply `python src/main.py` as 'both' is the default)

## Testing

### Running the Test Suite

To run the complete test suite:

1. Activate the virtual environment:
   ```bash
   .\venv\Scripts\activate  # Windows
   source venv/bin/activate # Linux/Mac
   ```
2. Install pytest: `pip install pytest`
3. Run the tests: `python -m pytest src/tools/ -v`

For running all tests in the project, use:
```bash
python -m pytest --ignore=turing-smart-screen-python
```
(The `--ignore` flag is needed to skip tests in the external turing-smart-screen-python dependency that require additional dependencies)

The test suite includes:
- Chat message pattern matching
- Translation service functionality
- Configuration handling
- Screen display (skipped when run with pytest as it requires hardware)
- Slang translation
- Live translation tests
- Handling of untranslatable content

### Testing Chat Translations

To test the chat translation functionality specifically:

1. Use the test script: `python src/tools/test_log_translation.py --read-once --from-start --log-path "path/to/console.log"`
2. Options:
   - `--read-once`: Read existing content and exit
   - `--from-start`: Start reading from beginning of file
   - `--log-path`: Path to log file (overrides config)
   - `--timeout`: Stop after N seconds (0 for no timeout)

Example translations:
```
(Survivor) Player: soy tu fan
Translated: I'm your fan

(Infected) Player: por las tetas de alfredo no mms
Translated: for alfredo's tits no mms

(Survivor) Player: di lo mejor que tenia
Translated: I gave my best
```

The test script helps verify:
- Message detection and parsing
- Special character handling
- Translation API connectivity
- Context-aware translations

### Testing Voice Translations

To test the voice translation functionality:

1. Use the test script: `python src/tools/test_translation.py --mode voice --text "Hello, this is a test" --target-lang es`
2. Options:
   - `--mode`: Translation mode (voice or text)
   - `--text`: Text to translate
   - `--target-lang`: Target language code (default: es)
   - `--source-lang`: Source language code (default: auto-detect)

Example voice translation test:
```
Original: Hello, this is a test
Detected language: en
Translated (es): Hola, esto es una prueba
```

This test script helps verify:
- Speech-to-text configuration
- Translation API connectivity
- Language detection
- Voice translation pipeline

Note: The `test_translation.py` script is designed to be run as a standalone script with command-line arguments, not as a pytest test. When run with pytest, these tests are automatically skipped.

### Testing Screen Display

To test the Turing Smart Screen display:

1. Use the test script: `python src/tools/test_screen.py`

This script will:
- List available COM ports
- Connect to the screen on the configured port (default: COM8)
- Display test messages with various formatting
- Test word wrapping and special character handling

Note: The `test_screen.py` script is designed to be run as a standalone script and requires physical hardware (Turing Smart Screen). When run with pytest, this test is automatically skipped.

## Message Format Support

The application supports various chat message formats:

- Regular chat: `PlayerName : message`
- Team chat: `(Survivor|Infected) PlayerName : message`
- Special formats: `(Infected) C(Infected) PlayerName : message`
- Names with special characters: `♥PlayerName☺`
- Messages with emojis and special characters

Note: Due to limitations in Left 4 Dead 2's console logging system, chat messages from players with certain Unicode or special characters in their names may not be written to the console.log file at all. This is a game engine limitation and not an issue with the translation system. The game supports displaying these characters in-game, but they may not be captured in the log file for translation.

## Contributing

Pull requests are welcome. For major changes, please open an issue first to discuss what you would like to change.

## License

[MIT](https://choosealicense.com/licenses/mit/)
