"""Live API tests for the translation service.

NOTE: These tests make actual API calls and may incur costs.
Run these tests manually when needed to verify API integration.
"""

import unittest
from src.translator.translation_service import TranslationService
import os
import json

def load_api_key():
    """Load API key from config file."""
    config_path = os.path.join('config', 'config.json')
    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)
    return config['translation']['apiKey']

class TestTranslationServiceLive(unittest.TestCase):
    """Live API tests for TranslationService.
    
    These tests make actual API calls to Google Cloud Translation.
    They verify that our service works correctly with the live API.
    """
    
    @classmethod
    def setUpClass(cls):
        """Set up test fixtures before running tests."""
        api_key = load_api_key()
        cls.service = TranslationService(
            api_key=api_key,
            target_language="en",
            cache_size=10,
            rate_limit_per_minute=60,
            retry_attempts=3
        )

    def test_live_translation_spanish(self):
        """Test live translation from Spanish to English."""
        result = self.service.translate("Hola mundo", source_language="es")
        self.assertEqual(result.lower(), "hello world")

    def test_live_translation_french(self):
        """Test live translation from French to English."""
        result = self.service.translate("Bonjour le monde", source_language="fr")
        self.assertEqual(result.lower(), "hello world")

    def test_live_language_detection(self):
        """Test live language detection."""
        # Test Spanish detection
        text = "Hola mundo"
        detected = self.service.detect_language(text)
        self.assertEqual(detected, "es")
        
        # Test French detection
        text = "Bonjour le monde"
        detected = self.service.detect_language(text)
        self.assertEqual(detected, "fr")

    def test_live_translation_with_detection(self):
        """Test live translation with automatic language detection."""
        # Spanish
        result = self.service.translate("Hola mundo")
        self.assertEqual(result.lower(), "hello world")
        
        # French
        result = self.service.translate("Bonjour le monde")
        self.assertEqual(result.lower(), "hello world")

    def test_live_caching(self):
        """Test that caching works with live translations."""
        # First translation should use API
        text = "Gracias amigo"
        result1 = self.service.translate(text, source_language="es")
        
        # Second translation should use cache
        result2 = self.service.translate(text, source_language="es")
        
        # Results should match
        self.assertEqual(result1, result2)
        
        # Verify it's in cache
        cache_key = f"es:{text}"
        self.assertIn(cache_key, self.service.cache)

if __name__ == '__main__':
    print("WARNING: These tests make actual API calls and may incur costs.")
    response = input("Do you want to continue? (y/N): ")
    if response.lower() == 'y':
        unittest.main(argv=['first-arg-is-ignored'], exit=False)
    else:
        print("Tests cancelled.")