# Setup Guide

## Initial Setup

### 1. Left 4 Dead Configuration

1. Enable Console
   - Right-click Left 4 Dead in Steam
   - Select Properties
   - Set Launch Options: `-console`
   - Click OK

2. Enable Chat Logging
   - Launch Left 4 Dead
   - Open Console (~)
   - Enter commands:
     ```
     con_logfile console.log
     con_timestamp 1
     ```

### 2. Turing Smart Screen Setup

1. Hardware Connection
   - Connect the Turing Smart Screen to an available USB port
   - Note the COM port number (can be found in Device Manager on Windows)
   - Ensure proper power supply

2. Driver Installation
   - Windows: Usually automatic via Windows Update
   - Linux: No additional drivers typically needed
   - MacOS: May need CH340 driver installation

### 3. Translation Service Setup

1. Google Cloud Translation API (Recommended)
   - Create Google Cloud account
   - Enable Cloud Translation API
   - Create API key with translation scope
   - Note: Keep API key secure

2. Alternative Services
   - DeepL API
   - Microsoft Translator
   - LibreTranslate (self-hosted option)

## Software Installation

### 1. Python Setup

1. Install Python 3.8+
   ```bash
   # Windows
   # Download from python.org and install with "Add to PATH" option

   # Linux
   sudo apt update
   sudo apt install python3.8 python3.8-venv

   # MacOS
   brew install python@3.8
   ```

2. Create Virtual Environment
   ```bash
   # Windows
   python -m venv venv
   .\venv\Scripts\activate

   # Linux/MacOS
   python3 -m venv venv
   source venv/bin/activate
   ```

### 2. Application Installation

1. Clone Repository
   ```bash
   git clone https://github.com/yourusername/Left4Translate.git
   cd Left4Translate
   ```

2. Install Dependencies
   ```bash
   pip install -r requirements.txt
   ```

## Configuration

### 1. Basic Configuration

1. Create Configuration File
   ```bash
   cp config/config.sample.json config/config.json
   ```

2. Edit Required Settings
   ```json
   {
     "game": {
       "logPath": "path/to/left4dead/console.log"
     },
     "translation": {
       "apiKey": "your-api-key"
     },
     "screen": {
       "port": "COM3"  // Your actual COM port
     }
   }
   ```

### 2. Advanced Configuration

1. Translation Settings
   ```json
   {
     "translation": {
       "service": "google",
       "targetLanguage": "en",
       "cacheSize": 1000,
       "rateLimitPerMinute": 100
     }
   }
   ```

2. Display Settings
   ```json
   {
     "screen": {
       "brightness": 80,
       "display": {
         "fontSize": 16,
         "maxMessages": 5,
         "messageTimeout": 10000
       }
     }
   }
   ```

3. Logging Settings
   ```json
   {
     "logging": {
       "level": "info",
       "path": "logs/app.log",
       "maxSize": "10MB"
     }
   }
   ```

## Testing

### 1. Configuration Test
```bash
python -m left4translate.tools.test_config
```

### 2. Screen Test
```bash
python -m left4translate.tools.test_screen
```

### 3. Translation Test
```bash
python -m left4translate.tools.test_translation
```

## Running the Application

### 1. Standard Mode
```bash
python src/main.py
```

### 2. Debug Mode
```bash
python src/main.py --debug
```

### 3. Service Installation (Optional)

Windows:
```bash
python tools/install_service.py
```

Linux:
```bash
sudo ./tools/install_service.sh
```

## Troubleshooting

### 1. Common Issues

1. Screen Not Detected
   - Check USB connection
   - Verify COM port
   - Test with different USB port
   - Check device manager

2. Translation Errors
   - Verify API key
   - Check internet connection
   - Monitor API quota
   - Review error logs

3. Game Log Issues
   - Verify log file path
   - Check file permissions
   - Ensure console logging is enabled
   - Restart game

### 2. Diagnostic Tools

1. Log Analysis
   ```bash
   python tools/analyze_logs.py
   ```

2. System Check
   ```bash
   python tools/system_check.py
   ```

## Maintenance

### 1. Regular Tasks

1. Log Rotation
   - Automated by default
   - Check logs directory size
   - Archive old logs

2. Cache Management
   - Clear translation cache if needed
   - Monitor cache hit rate
   - Adjust cache size

### 2. Updates

1. Software Update
   ```bash
   git pull
   pip install -r requirements.txt
   ```

2. Configuration Update
   - Backup current config
   - Compare with new sample
   - Update as needed

## Support

- GitHub Issues: Report bugs and feature requests
- Documentation: Check for updates
- Community: Join discussions
- Email: Contact maintainers