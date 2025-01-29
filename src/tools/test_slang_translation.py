#!/usr/bin/env python3
"""Test cases for gaming slang translations."""

import unittest
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from src.translator.translation_service import TranslationService

class TestSlangTranslation(unittest.TestCase):
    """Test cases for gaming slang translations."""
    
    def setUp(self):
        """Set up test fixtures before each test method."""
        self.service = TranslationService(
            api_key="test-api-key",
            target_language="en",
            cache_size=10,
            rate_limit_per_minute=60,
            retry_attempts=3
        )

    def test_basic_slang(self):
        """Test basic gaming slang translations."""
        test_cases = {
            "manco": "noob",
            "puntaje": "score",
            "reconectar": "reconnecting"
        }
        for input_text, expected in test_cases.items():
            result, was_slang = self.service._translate_slang(input_text)
            self.assertTrue(was_slang)
            self.assertEqual(result, expected)

    def test_phrase_with_si(self):
        """Test that 'si' is handled correctly in phrases."""
        test_cases = {
            "si": "yeah",  # Basic case
            "eso si": "yeah",  # Simple phrase
            "perdieron mentalmente eso si": "perdieron mentalmente eso si"  # Should not translate 'si' in complex phrase
        }
        for input_text, expected in test_cases.items():
            result, was_slang = self.service._translate_slang(input_text)
            if input_text == "si" or input_text == "eso si":
                self.assertTrue(was_slang)
            else:
                self.assertFalse(was_slang)
            self.assertEqual(result, expected)

    def test_combined_slang(self):
        """Test combinations of slang terms."""
        test_cases = {
            "ostia tio": "holy crap dude",
            "a huevo": "hell yeah",
            "no mames": "no way"
        }
        for input_text, expected in test_cases.items():
            result, was_slang = self.service._translate_slang(input_text)
            self.assertTrue(was_slang)
            self.assertEqual(result, expected)

if __name__ == '__main__':
    unittest.main()