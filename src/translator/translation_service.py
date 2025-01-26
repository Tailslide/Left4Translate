from typing import Dict, Optional
from cachetools import LRUCache
from google.cloud import translate_v2 as translate
import requests
from datetime import datetime, timedelta
import time
import logging
import re
import html

logging.basicConfig(level=logging.DEBUG,
                   format='%(asctime)s [%(levelname)s] %(message)s',
                   datefmt='%m/%d/%Y %I:%M:%S %p')

class RateLimiter:
    """Simple token bucket rate limiter."""
    
    def __init__(self, rate_limit_per_minute: int):
        self.rate_limit = rate_limit_per_minute
        self.tokens = rate_limit_per_minute
        self.last_update = datetime.now()
        
    def acquire(self) -> bool:
        """Attempt to acquire a token. Returns True if successful."""
        now = datetime.now()
        time_passed = now - self.last_update
        
        # Replenish tokens based on time passed
        old_tokens = self.tokens
        self.tokens = min(
            self.rate_limit,
            self.tokens + (time_passed.total_seconds() / 60.0) * self.rate_limit
        )
        self.last_update = now
        
        if self.tokens >= 1:
            self.tokens -= 1
            logging.debug(f"Rate limiter: Token acquired. Tokens before/after: {old_tokens:.2f}/{self.tokens:.2f}")
            return True
            
        logging.warning(f"Rate limiter: No tokens available. Current tokens: {self.tokens:.2f}")
        return False

class TranslationService:
    """Handles translation of messages using Google Cloud Translation API."""
    
    def __init__(
        self,
        api_key: str,
        target_language: str = "en",
        cache_size: int = 1000,
        rate_limit_per_minute: int = 100,
        retry_attempts: int = 3
    ):
        self.api_key = api_key
        self.base_url = "https://translation.googleapis.com/language/translate/v2"
        self.headers = {'Content-Type': 'application/json'}
        self.target_language = target_language
        self.cache = LRUCache(maxsize=cache_size)
        self.rate_limiter = RateLimiter(rate_limit_per_minute)
        self.retry_attempts = retry_attempts
        
    def _clean_text(self, text: str) -> str:
        """Remove color codes and other special characters."""
        # First handle escaped sequences
        cleaned = re.sub(r'\\x[0-9a-fA-F]{2}', '', text)
        # Then handle actual control characters
        cleaned = re.sub(r'[\x00-\x1F\x7F-\x9F]', '', cleaned)
        logging.debug(f"Cleaned text: '{text}' -> '{cleaned}'")
        return cleaned

    def translate(
        self,
        text: str,
        source_language: Optional[str] = None
    ) -> str:
        """
        Translate text to target language.
        
        Args:
            text: Text to translate
            source_language: Source language code (optional)
            
        Returns:
            Translated text
        """
        # Clean the text first
        cleaned_text = self._clean_text(text)
        
        # Check cache first
        cache_key = f"{source_language or 'auto'}:{cleaned_text}"
        if cache_key in self.cache:
            return self.cache[cache_key]
            
        # Apply rate limiting
        attempts = 0
        while attempts < self.retry_attempts:
            if self.rate_limiter.acquire():
                try:
                    # Skip translation for very short text
                    if len(cleaned_text) <= 1:
                        logging.debug(f"Skipping translation for short text: '{text}'")
                        return text

                    # Detect language if not provided
                    if not source_language:
                        detected = self.detect_language(cleaned_text)
                        source_language = detected
                        
                        # Skip translation if already in target language or undefined
                        if source_language == self.target_language or source_language == 'und':
                            logging.debug(f"Skipping translation for language: {source_language}")
                            return text  # Return original text, not cleaned
                    
                    # Perform translation
                    data = {
                        'q': cleaned_text,
                        'target': self.target_language
                    }
                    if source_language:
                        data['source'] = source_language

                    logging.debug("Translation request data: " + ", ".join(f"{k}: {v}" for k, v in data.items()))
                    logging.debug(f"Text length: {len(text)} characters")
                    logging.debug(f"Attempt {attempts + 1} of {self.retry_attempts}")

                    response = requests.post(
                        self.base_url,
                        params={'key': self.api_key},
                        json=data,
                        headers=self.headers
                    )

                    if response.status_code != 200:
                        logging.error(f"Translation API error - Status: {response.status_code}")
                        logging.error(f"Response content: {response.text}")
                        logging.error(f"Request URL: {response.url}")
                        response.raise_for_status()

                    result = response.json()
                    
                    translated_text = result['data']['translations'][0]['translatedText']
                    # Decode HTML entities (like &#39; to ')
                    decoded_text = html.unescape(translated_text)
                    logging.debug(f"Successfully translated text. Length: {len(decoded_text)} characters")
                    
                    # Cache the decoded result
                    self.cache[cache_key] = decoded_text
                    
                    return decoded_text
                    
                except requests.exceptions.HTTPError as e:
                    attempts += 1
                    logging.error(f"HTTP Error on attempt {attempts}: {str(e)}")
                    if attempts >= self.retry_attempts:
                        raise Exception(f"Translation failed after {attempts} attempts: {e}")
                    time.sleep(1)  # Wait before retry
                except Exception as e:
                    attempts += 1
                    logging.error(f"Unexpected error on attempt {attempts}: {str(e)}")
                    if attempts >= self.retry_attempts:
                        raise Exception(f"Translation failed after {attempts} attempts: {e}")
                    time.sleep(1)  # Wait before retry
            else:
                time.sleep(0.1)  # Wait for rate limit
                
        raise Exception("Failed to acquire rate limit token")
        
    def detect_language(self, text: str) -> str:
        """
        Detect the language of the given text.
        
        Args:
            text: Text to detect language for
            
        Returns:
            Language code (e.g., 'en', 'es', 'fr')
        """
        try:
            # Clean the text first
            cleaned_text = self._clean_text(text)
            data = {'q': cleaned_text}
            logging.debug(f"Language detection request - Text length: {len(cleaned_text)} characters")
            logging.debug("Detection request data: " + ", ".join(f"{k}: {v}" for k, v in data.items()))

            response = requests.post(
                f"{self.base_url}/detect",  # This is a different endpoint for detection
                params={'key': self.api_key},
                json=data,
                headers=self.headers
            )

            if response.status_code != 200:
                logging.error(f"Language detection API error - Status: {response.status_code}")
                logging.error(f"Response content: {response.text}")
                logging.error(f"Request URL: {response.url}")
                response.raise_for_status()

            result = response.json()
            detected_lang = result['data']['detections'][0][0]['language']
            confidence = result['data']['detections'][0][0].get('confidence', 0)
            logging.debug(f"Detected language: {detected_lang} with confidence: {confidence}")
            return detected_lang

        except requests.exceptions.HTTPError as e:
            logging.error(f"HTTP Error during language detection: {str(e)}")
            raise Exception(f"Language detection failed: {e}")
        except Exception as e:
            logging.error(f"Unexpected error during language detection: {str(e)}")
            raise Exception(f"Language detection failed: {e}")
            
    def clear_cache(self):
        """Clear the translation cache."""
        self.cache.clear()
        
    def get_cache_stats(self) -> Dict[str, int]:
        """Get cache statistics."""
        return {
            "size": len(self.cache),
            "maxsize": self.cache.maxsize,
            "currsize": self.cache.currsize
        }