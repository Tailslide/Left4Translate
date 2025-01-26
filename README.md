# Left4Translate

Real-time chat translation for Left 4 Dead 2, displaying translated messages on a Turing Smart Screen.

## Features

- Real-time monitoring of L4D2 console log
- Automatic translation of chat messages to English
- Support for both regular and team chat messages
- Support for special characters and emojis in player names
- Support for all game chat formats including infected team messages
- Display of translated messages on a Turing Smart Screen
- Message caching to reduce API calls
- Rate limiting to prevent API overuse
- Configurable display settings
- Extensive logging for troubleshooting

## Requirements

- Python 3.8+
- Left 4 Dead 2
- Turing Smart Screen
- Google Cloud Translation API key

## Installation

1. Clone this repository
2. Install dependencies: `pip install -r requirements.txt`
3. Copy `config/config.sample.json` to `config/config.json`
4. Add your Google Cloud Translation API key to `config.json`
5. Configure your screen settings in `config.json`

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
    }
  }
}
```

## Usage

1. Start Left 4 Dead 2
2. Enable console logging: `con_logfile console.log`
3. Run the translator: `python src/main.py`

## Message Format Support

The application supports various chat message formats:

- Regular chat: `PlayerName : message`
- Team chat: `(Survivor|Infected) PlayerName : message`
- Special formats: `(Infected) C(Infected) PlayerName : message`
- Names with special characters: `♥PlayerName☺`
- Messages with emojis and special characters

## Contributing

Pull requests are welcome. For major changes, please open an issue first to discuss what you would like to change.

## License

[MIT](https://choosealicense.com/licenses/mit/)