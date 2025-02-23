# Left4Translate v1.0.0

Real-time chat translation for Left 4 Dead 2, displaying translated messages on a Turing Smart Screen.
See here for compatible screen: https://www.aliexpress.com/item/1005003931363455.html
See here for more info on screens: https://github.com/mathoudebine/turing-smart-screen-python

[![Version](https://img.shields.io/badge/version-1.0.0-blue.svg)](https://github.com/yourusername/Left4Translate)

## Features

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
- Display of translated messages on a Turing Smart Screen
- Message caching to reduce API calls
- Rate limiting to prevent API overuse
- Configurable display settings
- Extensive logging for troubleshooting

## Requirements

- Python 3.8+
- Left 4 Dead 2
- Turing Smart Screen
    See here for compatible screen: https://www.aliexpress.com/item/1005003931363455.html
    See here for more info on screens: https://github.com/mathoudebine/turing-smart-screen-python
- Google Cloud Translation API key See: https://stackoverflow.com/questions/4854388/google-api-key-for-translation
    Note we are using Google Translate API V2 which has 500,000 free characters per month.
    Also when you first sign up for Google Cloud API you get like $500 free credit for the first year.
- Roboto Mono fonts (included in res/fonts/roboto-mono)

## Installation

1. Clone this repository
2. Install dependencies: `pip install -r requirements.txt`
3. Copy `config/config.sample.json` to `config/config.json`
4. Add your Google Cloud Translation API key to `config.json` 
5. Configure your screen settings in `config.json`

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
   - Configure your screen settings in `config.json`

The executable will be created in the `dist` directory. All required resources (fonts, config samples, etc.) are automatically included in the build. Note that you must create your own config.json with your API key - this is not included in the build for security reasons.

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
  }
}
```

## Usage

1. Plug in your turing screen.
2. Start Left 4 Dead 2
3. Enable console logging: `con_logfile console.log`
4. Optionally set this in steam launch options: `-condebug -conclearlog`
5. Copy config.sample.json to config.json
6. Update config.json log file path if it's not in default location.
7. Update config.json with your turing screen com port number See: https://github.com/mathoudebine/turing-smart-screen-python
8. Update config.json with your google translate API key. See: https://stackoverflow.com/questions/4854388/google-api-key-for-translation
9. Run the translator: `python src/main.py`

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

The test suite includes:
- Chat message pattern matching
- Translation service functionality
- Configuration handling
- Screen display
- Slang translation
- Live translation tests
- Handling of untranslatable content

### Testing Translations

To test the translation functionality specifically:

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