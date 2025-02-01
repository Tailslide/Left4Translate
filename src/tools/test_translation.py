import unittest
from unittest.mock import Mock, patch
from src.translator.translation_service import TranslationService, RateLimiter
from datetime import datetime, timedelta
import time
import requests

class TestTranslationService(unittest.TestCase):
    def setUp(self):
        """Set up test fixtures before each test method."""
        self.api_key = "test-api-key"
        self.service = TranslationService(
            api_key=self.api_key,
            target_language="en",
            cache_size=10,
            rate_limit_per_minute=60,
            retry_attempts=3
        )

    @patch('requests.post')
    def test_translation_with_language_detection(self, mock_post):
        """Test translation when source language is not provided."""
        # Mock detect response
        detect_response = Mock()
        detect_response.json.return_value = {
            'data': {
                'detections': [[{'language': 'es', 'confidence': 0.99}]]
            }
        }
        
        # Mock translate response
        translate_response = Mock()
        translate_response.json.return_value = {
            'data': {
                'translations': [{'translatedText': 'Hello'}]
            }
        }
        
        mock_post.side_effect = [detect_response, translate_response]
        
        result = self.service.translate("Hola")
        self.assertEqual(result, "Hello")
        self.assertEqual(mock_post.call_count, 2)

    @patch('requests.post')
    def test_translation_with_source_language(self, mock_post):
        """Test translation with explicitly provided source language."""
        # Mock translate response
        mock_response = Mock()
        mock_response.json.return_value = {
            'data': {
                'translations': [{'translatedText': 'Hello'}]
            }
        }
        mock_post.return_value = mock_response
        
        result = self.service.translate("Bonjour", source_language="fr")
        self.assertEqual(result, "Hello")
        self.assertEqual(mock_post.call_count, 1)

    @patch('requests.post')
    def test_caching_mechanism(self, mock_post):
        """Test that translations are properly cached and retrieved."""
        # Mock translate response
        mock_response = Mock()
        mock_response.json.return_value = {
            'data': {
                'translations': [{'translatedText': 'Hello'}]
            }
        }
        mock_post.return_value = mock_response
        
        # First translation should use the API
        result1 = self.service.translate("Hola", source_language="es")
        self.assertEqual(result1, "Hello")
        self.assertEqual(mock_post.call_count, 1)
        
        # Second translation of same text should use cache
        result2 = self.service.translate("Hola", source_language="es")
        self.assertEqual(result2, "Hello")
        self.assertEqual(mock_post.call_count, 1)  # Count shouldn't increase

    def test_rate_limiting(self):
        """Test that rate limiting properly throttles requests."""
        limiter = RateLimiter(rate_limit_per_minute=2)
        
        # Should allow first two requests
        self.assertTrue(limiter.acquire())
        self.assertTrue(limiter.acquire())
        
        # Third request should be blocked
        self.assertFalse(limiter.acquire())
        
        # Wait for token replenishment
        time.sleep(31)  # Wait for ~0.5 token to be replenished
        self.assertTrue(limiter.acquire())

    @patch('requests.post')
    def test_error_handling_and_retries(self, mock_post):
        """Test error handling and retry mechanism."""
        # Configure mock to fail twice then succeed
        mock_error_response = Mock()
        mock_error_response.raise_for_status.side_effect = requests.exceptions.RequestException("API Error")
        
        mock_success_response = Mock()
        mock_success_response.json.return_value = {
            'data': {
                'translations': [{'translatedText': 'Hello'}]
            }
        }
        
        mock_post.side_effect = [
            mock_error_response,  # First attempt fails
            mock_error_response,  # Second attempt fails
            mock_success_response  # Third attempt succeeds
        ]
        
        result = self.service.translate("Hola", source_language="es")
        self.assertEqual(result, "Hello")
        self.assertEqual(mock_post.call_count, 3)

    @patch('requests.post')
    def test_language_detection(self, mock_post):
        """Test standalone language detection."""
        mock_response = Mock()
        mock_response.json.return_value = {
            'data': {
                'detections': [[{'language': 'fr', 'confidence': 0.99}]]
            }
        }
        mock_post.return_value = mock_response
        
        result = self.service.detect_language("Bonjour")
        self.assertEqual(result, "fr")
        self.assertEqual(mock_post.call_count, 1)

    @patch('requests.post')
    def test_cache_stats(self, mock_post):
        """Test cache statistics reporting."""
        mock_response = Mock()
        mock_response.json.return_value = {
            'data': {
                'translations': [{'translatedText': 'Hello'}]
            }
        }
        mock_post.return_value = mock_response
        
        # Perform some translations to populate cache
        self.service.translate("Hola", source_language="es")
        self.service.translate("Adios", source_language="es")
        
        stats = self.service.get_cache_stats()
        self.assertEqual(stats["size"], 2)
        self.assertEqual(stats["maxsize"], 10)
        self.assertEqual(stats["currsize"], 2)

    @patch('requests.post')
    def test_skip_translation_for_target_language(self, mock_post):
        """Test that translation is skipped when text is already in target language."""
        mock_response = Mock()
        mock_response.json.return_value = {
            'data': {
                'detections': [[{'language': 'en', 'confidence': 0.99}]]
            }
        }
        mock_post.return_value = mock_response
        
        result = self.service.translate("Hello")
        
        # Should detect language but skip translation
        self.assertEqual(mock_post.call_count, 1)  # Only detection, no translation
        self.assertEqual(result, "Hello")

    @patch('requests.post')
    def test_mixed_slang_translation(self, mock_post):
        """Test translation of phrases containing both regular words and slang."""
        # Mock Google Translate to return the same text for untranslatable words
        mock_response = Mock()
        mock_response.json.return_value = {
            'data': {
                'translations': [{'translatedText': 'ptm I am black'}]}
        }
        mock_post.return_value = mock_response
        
        # Test that slang words are translated after Google Translate
        result = self.service.translate("ptm soy negro", source_language="es")
        self.assertEqual(result, "damn I am black")
        
        # Test another mixed phrase
        mock_response.json.return_value = {
            'data': {
                'translations': [{'translatedText': 'the manco is here'}]}
        }
        result = self.service.translate("el manco esta aqui", source_language="es")
        self.assertEqual(result, "the noob is here")

    @patch('requests.post')
    def test_untranslatable_content(self, mock_post):
        """Test handling of untranslatable content (symbols, numbers, etc.)."""
        # Mock language detection to fail with 400 error for undefined language
        mock_error_response = Mock()
        mock_error_response.status_code = 400
        mock_error_response.text = '{"error":{"details":[{"fieldViolations":[{"field":"source","description":"Source language: und"}]}]}}'
        mock_error_response.raise_for_status.side_effect = requests.exceptions.HTTPError(
            "400 Client Error: Bad Request",
            response=mock_error_response
        )
        mock_post.return_value = mock_error_response

        # Test various untranslatable content
        test_cases = ["1+?", "123", ":-)", "!!!"]
        for text in test_cases:
            result = self.service.translate(text)
            self.assertEqual(result, text, f"Untranslatable content '{text}' should return unchanged")

if __name__ == '__main__':
    unittest.main()