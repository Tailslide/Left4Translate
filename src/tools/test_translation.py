#!/usr/bin/env python
"""
Test script for translation functionality.
This script can be used to test both text and voice translation.
"""

import os
import sys
import argparse
import logging
import json
from pathlib import Path

# Add the parent directory to the path so we can import modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from translator.translation_service import TranslationService
from audio.speech_to_text import SpeechToTextService
import numpy as np

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("test_translation")

def load_config():
    """Load configuration from config.json."""
    config_paths = [
        os.path.join(os.getcwd(), "config", "config.json"),
        os.path.join(os.getcwd(), "config.json")
    ]
    
    for config_path in config_paths:
        if os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
    
    # If no config file found, return a minimal default config
    logger.warning("No config file found. Using default configuration.")
    return {
        "translation": {
            "apiKey": "",
            "targetLanguage": "en",
            "cacheSize": 100,
            "rateLimitPerMinute": 60,
            "retryAttempts": 3
        }
    }

def test_text_translation(text=None, source_lang=None, target_lang=None, api_key=None):
    # Skip this test when run with pytest
    if text is None:
        import pytest
        pytest.skip("This test requires command-line arguments and is not meant to be run with pytest")
    """Test text translation functionality."""
    logger.info(f"Testing text translation: '{text}'")
    
    # Initialize translation service
    translator = TranslationService(
        api_key=api_key,
        target_language=target_lang,
        cache_size=100,
        rate_limit_per_minute=60,
        retry_attempts=3
    )
    
    try:
        # Detect language if source_lang is not provided
        if not source_lang or source_lang == "auto":
            detected_lang = translator.detect_language(text)
            logger.info(f"Detected language: {detected_lang}")
            source_lang = detected_lang
        
        # Translate text
        translated = translator.translate(text, source_language=source_lang)
        
        # Print results
        print("\nTranslation Results:")
        print(f"Original ({source_lang}): {text}")
        print(f"Translated ({target_lang}): {translated}")
        
        return True
    except Exception as e:
        logger.error(f"Translation error: {e}")
        return False

def test_voice_translation(text=None, source_lang=None, target_lang=None, api_key=None):
    # Skip this test when run with pytest
    if text is None:
        import pytest
        pytest.skip("This test requires command-line arguments and is not meant to be run with pytest")
    """
    Test voice translation functionality.
    
    This simulates the voice translation process by:
    1. Taking a text input (simulating transcribed speech)
    2. Detecting the language
    3. Translating to the target language
    
    In a real scenario, the text would come from the speech-to-text service.
    """
    logger.info(f"Testing voice translation with text: '{text}'")
    
    # Initialize translation service
    translator = TranslationService(
        api_key=api_key,
        target_language=target_lang,
        cache_size=100,
        rate_limit_per_minute=60,
        retry_attempts=3
    )
    
    try:
        # Detect language if source_lang is not provided
        if not source_lang or source_lang == "auto":
            detected_lang = translator.detect_language(text)
            logger.info(f"Detected language: {detected_lang}")
            source_lang = detected_lang
        
        # Translate text
        translated = translator.translate(text, source_language=source_lang)
        
        # Print results
        print("\nVoice Translation Simulation Results:")
        print(f"Original: {text}")
        print(f"Detected language: {source_lang}")
        print(f"Translated ({target_lang}): {translated}")
        
        return True
    except Exception as e:
        logger.error(f"Voice translation error: {e}")
        return False

def main():
    """Main function."""
    parser = argparse.ArgumentParser(description="Test translation functionality")
    parser.add_argument("--mode", choices=["text", "voice"], default="text",
                        help="Translation mode (text or voice)")
    parser.add_argument("--text", type=str, required=True,
                        help="Text to translate")
    parser.add_argument("--source-lang", type=str, default="auto",
                        help="Source language code (default: auto-detect)")
    parser.add_argument("--target-lang", type=str,
                        help="Target language code (default: from config)")
    parser.add_argument("--api-key", type=str,
                        help="Google Cloud API key (default: from config)")
    
    args = parser.parse_args()
    
    # Load configuration
    config = load_config()
    
    # Get API key from args or config
    api_key = args.api_key or config.get("translation", {}).get("apiKey", "")
    if not api_key:
        logger.error("No API key provided. Please specify --api-key or add it to config.json")
        return False
    
    # Get target language from args or config
    target_lang = args.target_lang or config.get("translation", {}).get("targetLanguage", "en")
    
    # Run the appropriate test based on mode
    if args.mode == "text":
        return test_text_translation(args.text, args.source_lang, target_lang, api_key)
    else:  # voice mode
        return test_voice_translation(args.text, args.source_lang, target_lang, api_key)

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)