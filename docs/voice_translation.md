# Voice Translation Feature

The voice translation feature allows you to record speech by holding down a mouse button, transcribe it to text, translate it to another language, and display both the original and translated text on the Turing Smart Screen.

## How It Works

1. **Recording**: Hold down the configured mouse button (default: forward button) to record your speech.
2. **Transcription**: When you release the button, the recorded audio is transcribed to text using Google Cloud Speech-to-Text.
3. **Translation**: The transcribed text is translated to the target language (default: Spanish) using Google Cloud Translation.
4. **Display**: Both the original and translated text are displayed on the Turing Smart Screen.
5. **Clipboard**: The translated text is automatically copied to the clipboard for easy pasting.

## Configuration

The voice translation feature is configured in the `voice_translation` section of the `config.json` file:

```json
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
    "model": "default"
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
    "format": "both"
  }
}
```

### Configuration Options

#### General Settings

- `enabled`: Enable or disable the voice translation feature (true/false).

#### Trigger Button

- `button`: Mouse button to use for recording:
  - "left": Left mouse button
  - "right": Right mouse button
  - "middle": Middle mouse button (scroll wheel)
  - "button4": Forward button (typically the front side button on most mice)
  - "button5": Back button (typically the rear side button on most mice)
  
  Note: The mapping of "button4" and "button5" to physical buttons can vary between mouse models and systems.
- `modifier_keys`: List of modifier keys that must be pressed along with the button (e.g., ["ctrl", "shift"]). Currently not implemented.

#### Audio Settings

- `sample_rate`: Audio sample rate in Hz (16000 recommended for speech recognition).
- `channels`: Number of audio channels (1 for mono, 2 for stereo).
- `device`: Audio input device name or "default" to use the system default.

#### Speech-to-Text Settings

- `language`: Language code for speech recognition (e.g., "en-US", "es-ES").
- `model`: Speech recognition model to use ("default" or specific model name).
- `credentials_path`: Path to the Google Cloud service account credentials JSON file. This is required for Speech-to-Text functionality.

#### Translation Settings

- `target_language`: Target language code for translation (e.g., "es" for Spanish, "fr" for French).
- `show_original`: Whether to include the original text in the display (true/false).

#### Display Settings

- `show_original`: Whether to show the original text on the screen (true/false).
- `show_translated`: Whether to show the translated text on the screen (true/false).
- `clear_after`: Time in milliseconds to clear the display after translation (0 to disable).

#### Clipboard Settings

- `auto_copy`: Whether to automatically copy translations to clipboard (true/false).
- `format`: Format to use when copying ("original", "translated", or "both"). Default is "translated".

## Supported Languages

### Speech Recognition Languages

The voice translation feature supports all languages available in Google Cloud Speech-to-Text. Some common language codes include:

- English (US): "en-US"
- English (UK): "en-GB"
- Spanish: "es-ES"
- French: "fr-FR"
- German: "de-DE"
- Italian: "it-IT"
- Japanese: "ja-JP"
- Korean: "ko-KR"
- Portuguese: "pt-BR"
- Russian: "ru-RU"
- Chinese (Simplified): "zh-CN"

For a complete list, see the [Google Cloud Speech-to-Text documentation](https://cloud.google.com/speech-to-text/docs/languages).

### Translation Languages

The voice translation feature supports all languages available in Google Cloud Translation. Some common language codes include:

- English: "en"
- Spanish: "es"
- French: "fr"
- German: "de"
- Italian: "it"
- Japanese: "ja"
- Korean: "ko"
- Portuguese: "pt"
- Russian: "ru"
- Chinese (Simplified): "zh-CN"

For a complete list, see the [Google Cloud Translation documentation](https://cloud.google.com/translate/docs/languages).

## Usage Tips

- Speak clearly and at a moderate pace for best transcription results.
- Keep the microphone close to your mouth for better audio quality.
- Short phrases (5-10 seconds) work best for accurate transcription.
- If transcription fails, try adjusting the audio settings or speaking more clearly.
- For languages with different dialects (e.g., Spanish), choose the appropriate language code for best results.
- Test different microphones if you experience poor transcription quality.

## Authentication Setup

### Google Cloud Speech-to-Text Authentication

The voice translation feature uses Google Cloud Speech-to-Text API, which requires proper authentication using a service account with appropriate IAM permissions. Unlike the Translation API which can work with just an API key, Speech-to-Text requires a service account.

To set up authentication:

1. Create a Google Cloud project (or use an existing one)
2. Enable the Speech-to-Text API for your project
3. Create a service account with the "Cloud Speech Client" role
4. Generate a JSON key file for the service account
5. Save the JSON key file to a secure location on your computer
6. Update the `credentials_path` in the `speech_to_text` section of your `config.json` file to point to this JSON file

For detailed instructions on creating a service account and generating a key file, see the [Google Cloud documentation](https://cloud.google.com/speech-to-text/docs/quickstart-client-libraries).

## Implementation Notes

### Translation Service Parameters

The voice translation feature uses the `TranslationService.translate()` method with the following parameters:

- `text`: The text to translate (required)
- `source_language`: The source language code (optional, defaults to auto-detect)

The target language is configured when initializing the `TranslationService` class and doesn't need to be passed as a parameter to each translate call.

## Troubleshooting

### No Audio Recorded

- Check that your microphone is properly connected and working.
- Verify that the correct audio device is selected in the configuration.
- Try increasing the microphone volume in your system settings.
- The application now automatically checks microphone volume levels and provides guidance if they're too low.

### Poor Transcription Quality

- Ensure you're speaking clearly and at a moderate pace.
- Check that the correct language code is set for speech recognition.
- Try using a higher quality microphone or reducing background noise.
- Adjust the sample rate or channels in the configuration.
- Pay attention to the audio level diagnostics in the logs - levels below -50 dB are too low for effective speech recognition.

### Error Messages

The application now provides more specific error messages based on detected issues:

- **"No speech detected"**: The application detected audio but couldn't identify speech content.
  - Speak more clearly and ensure you're speaking during the recording.
  - Check that you're using the correct language setting.

- **"Low audio level"**: The microphone volume is too low for effective speech recognition.
  - Increase microphone volume in system settings.
  - Speak closer to the microphone.
  - Try a different microphone if available.

- **"Speech-to-text client not initialized"**: The application couldn't initialize the speech recognition service.
  - Check that your credentials file exists and is valid.
  - Verify that the service account has the correct permissions.

### Audio Level Diagnostics

The application includes enhanced audio level diagnostics that:

1. Checks microphone volume when initializing the voice recorder
2. Measures audio levels during recording
3. Provides detailed feedback in the logs and on screen when levels are too low
4. Categorizes audio quality as "good", "low", or "very_low" based on measured levels
5. Customizes error messages based on the detected audio quality
6. Lists available alternative microphones when volume is too low

Audio quality categories:
- **Good**: Audio levels are sufficient for effective speech recognition
- **Low**: Audio levels are below optimal but may still work for speech recognition
- **Very Low**: Audio levels are too low for effective speech recognition

If you see messages about low audio levels:
- Check Windows sound settings:
  1. Right-click the speaker icon in the system tray
  2. Select 'Open Sound settings'
  3. Click on 'Sound Control Panel' on the right
  4. Go to the 'Recording' tab
  5. Select your microphone and click 'Properties'
  6. Go to the 'Levels' tab and increase the volume
- Speak closer to the microphone
- Try a different microphone if available (the application will list alternatives)
- Check if your microphone is muted or if the physical mute switch is enabled

### Authentication Issues

- Verify that you've created a service account with the proper permissions for Speech-to-Text.
- Check that the service account credentials file path is correct in your configuration.
- Ensure the service account has the "Cloud Speech Client" role.
- If you see "PERMISSION_DENIED" or "UNAUTHENTICATED" errors, check your service account permissions.

### Translation Issues

- Verify that your Google Cloud API key is valid and has access to the Translation API.
- Check that the target language code is correct.
- Some slang or technical terms may not translate accurately.

### Mouse Button Not Working

- Verify that the correct mouse button is configured in the `trigger_button.button` setting.
- The mapping of buttons can vary between mouse models:
  - If "button4" activates the wrong button (e.g., back instead of forward):
    - Try swapping to "button5" instead
    - Or modify the config to use "right" for the right mouse button
  - If neither "button4" nor "button5" work:
    - Your mouse might not have additional buttons beyond left, right, and middle
    - Or the buttons might not be recognized by the system
  - Check if your mouse driver software allows you to remap buttons
- Restart the application after changing the configuration.

### Logging and Privacy

- The application logs API requests and responses for debugging purposes.
- Audio content is truncated in logs to protect privacy and reduce log file size.
- If you need to troubleshoot API issues, check the logs for request/response details without the actual audio content.
- Log files can be found in the `logs` directory.

## API Usage and Costs

The voice translation feature uses two Google Cloud APIs:

1. **Speech-to-Text API**: Used for transcribing speech to text.
   - Pricing: $0.006 per 15 seconds of audio (as of 2025).
   - Free tier: 60 minutes per month.

2. **Translation API**: Used for translating text.
   - Pricing: $20 per million characters (as of 2025).
   - Free tier: 500,000 characters per month.

To minimize costs:
- Keep recordings short and concise.
- Use the cache feature to avoid retranslating the same text.
- Monitor your API usage in the Google Cloud Console.