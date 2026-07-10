from typing import Dict, Optional, Tuple
from cachetools import LRUCache
import requests
from datetime import datetime
import threading
import time
import logging
import re
import html

# Network timeout for every Translation API call. Without one, a stalled
# connection blocks the calling thread (chat reader / voice worker) forever.
REQUEST_TIMEOUT_SECONDS = 10

class RateLimiter:
    """Simple token-bucket rate limiter. Thread-safe: the chat reader and
    voice worker threads share one instance."""

    def __init__(self, rate_limit_per_minute: int):
        self.rate_limit = rate_limit_per_minute
        self.tokens = rate_limit_per_minute
        self.last_update = datetime.now()
        self._lock = threading.Lock()

    def acquire(self) -> bool:
        """Attempt to acquire a token. Returns True if successful."""
        with self._lock:
            now = datetime.now()
            time_passed = now - self.last_update

            # Replenish tokens based on time passed
            self.tokens = min(
                self.rate_limit,
                self.tokens + (time_passed.total_seconds() / 60.0) * self.rate_limit
            )
            self.last_update = now

            if self.tokens >= 1:
                self.tokens -= 1
                return True

            logging.debug(f"Rate limiter: no tokens available ({self.tokens:.2f})")
            return False

def is_undefined_language_error(e: requests.exceptions.HTTPError) -> bool:
    """Check if the error is due to undefined language."""
    try:
        return (e.response.status_code == 400 and
                'Source language: und' in e.response.text)
    except Exception:
        return False

def is_untranslatable_content(text: str) -> bool:
    """Check if the content is likely untranslatable."""
    # Check for very short text
    if len(text) <= 3:  # Increased from 1 to catch more short content
        return True
        
    # Check if text contains only special characters, numbers, and punctuation
    if not any(c.isalpha() for c in text):
        return True
        
    # Check for common untranslatable patterns
    untranslatable_patterns = [
        r'^\d+[\+\-\*\/\?]+\d*$',  # Math expressions like "1+?"
        r'^[:\-\(\)]+$',  # Emoticons like ":-)"
        r'^[!@#$%^&\*\(\)_\+\-=\[\]\{\};:\'",\.<>\/\?]+$'  # Only punctuation
    ]
    
    for pattern in untranslatable_patterns:
        if re.match(pattern, text):
            return True
            
    return False

# Spanish gaming/internet slang dictionary as a class constant
SPANISH_SLANG_DICT = {
    # Gaming performance/status
    'bistec': 'buff',  # Gaming slang for strong/muscular
    'op': 'overpowered',
    'nerfear': 'nerf',
    'rushear': 'rush',
    'ptm': 'damn',  # Spanish gaming slang expletive
    'campear': 'camping',
    'farmear': 'farming',
    'lootear': 'looting',
    'spawnear': 'spawning',
    'lagger': 'lagging',
    'lagueado': 'lagging',
    'bugeado': 'bugged',
    'rip': 'dead',
    'f': 'rip',

    # Common reactions and affirmations
    'si': 'yeah',
    'eso si': 'yeah',  # Common affirmation
    'ostia tio': 'holy crap dude',
    'tio': 'bro',
    'broca': 'bro',  # Mexican slang
    'brocoli': 'bro',  # Playful variant of broca
    'brocha': 'bro',  # Another variant
    'vale': 'ok',
    
    'joder': 'damn',
    'vamos': "let's go",
    'que pasa': "what's up",
    'no mames': 'no way',
    'pinche': 'freaking',
    'wey': 'dude',
    'güey': 'dude',  # Proper spelling of wey
    'chido': 'cool',
    'a huevo': 'hell yeah',
    'no manche': 'no way',
    'nel': 'nope',
    'simon': 'yeah',
    'neta': 'really',
    'que onda': "what's up",
    'equis': "whatever",
    'x': "whatever",
    'va': 'ok',  # Short form of vale
    'sale': 'ok',  # Mexican slang for agreement
    'sobres': 'alright',  # Mexican slang for agreement
    'fierro': "let's go",  # Northern Mexican slang for enthusiasm

    # Team communication
    'izi': 'ez',  # Common Spanish variant of 'ez'
    
    # Base forms
    'rico': 'nice',
    'delicioso': 'delicious',
    'deli': 'nice',
    
    # Extended forms with emphasis
    'ricooo': 'niceee',
    'ricxoooooo': 'niceeee',
    'ricoo+': 'nicee+',
    
    # With que/q prefix
    'q rico': 'so nice',
    'que rico': 'so nice',
    'q ricxoooooo': 'so niceeee',
    
    # Add to Spanish indicators
    'ricx': 'nice',
    'ricoo': 'nice',
    'ricxo': 'nice',
    'q ric': 'so nice',
    'que ric': 'so nice',
    'q ricx': 'so nice',
    'que ricx': 'so nice',
    'ayuda': 'help',
    'cuidado': 'watch out',
    'atras': 'behind',
    'vienen': 'incoming',
    'tanque': 'tank',
    'bruja': 'witch',
    
    # Only unique Spanish gaming slang and expressions that differ from English
    'manco': 'noob',
    'puntaje': 'score',
    'reconectar': 'reconnecting',
}


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
        # LRUCache is not thread-safe; the chat reader and voice worker
        # threads share this service, so guard all cache access.
        self._cache_lock = threading.Lock()
        self.rate_limiter = RateLimiter(rate_limit_per_minute)
        self.retry_attempts = retry_attempts
        # Longest a caller may block waiting for a rate-limit token. Beyond
        # this we degrade gracefully (original text) instead of stalling the
        # reader/voice thread indefinitely.
        self.rate_limit_wait_seconds = 5.0
        
    def _clean_text(self, text: str) -> str:
        """Remove color codes and other special characters."""
        # First handle escaped sequences
        cleaned = re.sub(r'\\x[0-9a-fA-F]{2}', '', text)
        # Then handle actual control characters
        cleaned = re.sub(r'[\x00-\x1F\x7F-\x9F]', '', cleaned)
        logging.debug(f"Cleaned text: '{text}' -> '{cleaned}'")
        return cleaned

    def _get_slang_translations(self) -> dict:
        """Get dictionary of Spanish gaming/internet slang translations.
        
        Returns the module-level SPANISH_SLANG_DICT constant.
        """
        return SPANISH_SLANG_DICT

    def _translate_slang(self, text: str) -> tuple[str, bool]:
        """
        Attempt to translate common gaming/internet slang.
        Returns tuple of (translated_text, was_translated).
        """
        slang_dict = self._get_slang_translations()
        lower_text = text.lower().strip()
        words = lower_text.split()
        
        # Only translate 'si' or 'eso si' as standalone phrases
        if lower_text == 'si' or lower_text == 'eso si':
            return slang_dict.get(lower_text, text), True
            
        # Don't translate 'si' when it's part of a larger phrase
        if 'si' in words and len(words) > 1:
            slang_dict = {k: v for k, v in slang_dict.items() if k != 'si'}
        
        # Try exact matches first for other phrases
        if lower_text in slang_dict:
            return slang_dict[lower_text], True
        
        # Handle name + slang patterns (e.g., "Jason broca")
        name_slang_patterns = {
            'broca': 'bro',
            'brocoli': 'bro',
            'brocha': 'bro',
            'wey': 'dude',
            'güey': 'dude',
            'tio': 'bro'
        }
        
        words = text.split()  # Use original text to preserve name capitalization
        if len(words) >= 2:
            last_word = words[-1].lower()
            if last_word in name_slang_patterns:
                # Keep original name but translate the slang term
                name_part = ' '.join(words[:-1])
                return f"{name_part} {name_slang_patterns[last_word]}", True
        
        # First check for exact matches
        if lower_text in slang_dict:
            return slang_dict[lower_text], True
            
        # Then check if it's a single word
        if ' ' not in lower_text:
            # If it's a single word and it's in our slang dictionary, translate it
            if lower_text in slang_dict:
                return slang_dict[lower_text], True
            
        # Don't translate slang words that are part of larger phrases
        return text, False

    def _preprocess_text(self, text: str) -> str:
        """Preprocess text to help with language detection."""
        # Common Spanish words/phrases that might be misdetected
        spanish_indicators = [
            'hola', 'amigo', 'que', 'como', 'estas', 'bien',
            'gracias', 'por favor', 'ostia', 'tio',  # Removed 'si' from indicators
            'vale', 'joder', 'vamos', 'adios', 'wey', 'chido',
            'pinche', 'mames', 'bistec'
        ]
        
        # Check if text contains any Spanish indicators
        lower_text = text.lower()
        for word in spanish_indicators:
            if word in lower_text:
                return 'es'  # Return Spanish language code
        return ''  # No specific language detected

    def translate(
        self,
        text: str,
        source_language: Optional[str] = None,
        target_language: Optional[str] = None
    ) -> str:
        """Translate ``text``; see :meth:`translate_with_detection`."""
        translated, _ = self.translate_with_detection(
            text, source_language=source_language, target_language=target_language
        )
        return translated

    def translate_with_detection(
        self,
        text: str,
        source_language: Optional[str] = None,
        target_language: Optional[str] = None
    ) -> Tuple[str, Optional[str]]:
        """
        Translate text to the target language in a single API call.

        When ``source_language`` is omitted the Translation API auto-detects it
        server-side and reports ``detectedSourceLanguage`` in the same response,
        so no separate /detect round-trip is needed.

        Returns:
            (translated_text, source_language) — the source is the caller's,
            the local heuristic's, or the API-detected base code; ``None`` when
            unknown (untranslatable content, rate-limit fallback).
        """
        # Use provided target language or fall back to the default
        target_lang = target_language or self.target_language
        # Clean the text first
        cleaned_text = self._clean_text(text)

        # Local slang translation needs no API call, so it runs before every
        # other bail-out — in particular before the untranslatable-content
        # check, which would otherwise swallow short slang like "si" or "f".
        slang_translated, was_slang = self._translate_slang(cleaned_text)
        if was_slang:
            logging.debug(f"Used slang translation: '{cleaned_text}' -> '{slang_translated}'")
            return slang_translated, 'es'

        # Skip translation for untranslatable content
        if is_untranslatable_content(cleaned_text):
            logging.debug(f"Skipping translation for untranslatable content: '{text}'")
            return text, None

        # Resolve the source language: caller-provided, else the cheap local
        # Spanish-indicator heuristic; else let the API auto-detect.
        source_base = source_language.split('-')[0] if source_language else None
        if source_base is None:
            hint = self._preprocess_text(cleaned_text)
            source_base = hint or None
        if source_base and source_base == target_lang:
            return text, source_base

        cache_key = f"{source_base or 'auto'}:{target_lang}:{cleaned_text}"
        with self._cache_lock:
            cached = self.cache.get(cache_key)
        if cached is not None:
            return cached

        deadline = time.monotonic() + self.rate_limit_wait_seconds
        attempts = 0
        while True:
            if not self.rate_limiter.acquire():
                if time.monotonic() >= deadline:
                    # Degrade gracefully: showing the original text beats
                    # stalling the reader/voice thread behind one message.
                    logging.warning(
                        "Rate limit wait budget exhausted; showing original text"
                    )
                    return text, None
                time.sleep(0.1)
                continue

            try:
                data = {'q': cleaned_text, 'target': target_lang}
                if source_base:
                    data['source'] = source_base

                logging.debug(f"Translation request: target={target_lang} source={source_base or 'auto'} len={len(text)}")

                response = requests.post(
                    self.base_url,
                    params={'key': self.api_key},
                    json=data,
                    headers=self.headers,
                    timeout=REQUEST_TIMEOUT_SECONDS,
                )
                if response.status_code != 200:
                    logging.error(f"Translation API error - Status: {response.status_code}")
                    logging.error(f"Response content: {response.text}")
                    response.raise_for_status()

                payload = response.json()['data']['translations'][0]
                decoded_text = html.unescape(payload['translatedText'])
                detected = payload.get('detectedSourceLanguage') or source_base
                detected_base = detected.split('-')[0] if detected else None

                if detected_base in (target_lang, 'und'):
                    # Already in the target language (or undetectable):
                    # keep the original text.
                    result: Tuple[str, Optional[str]] = (text, detected_base)
                else:
                    result = (self._apply_slang_postpass(cleaned_text, decoded_text), detected_base)

                with self._cache_lock:
                    self.cache[cache_key] = result
                return result

            except requests.exceptions.HTTPError as e:
                # If it's an undefined language error, return original text immediately
                if is_undefined_language_error(e):
                    logging.debug(f"Undefined source language, returning original: '{text}'")
                    return text, None

                attempts += 1
                logging.error(f"HTTP Error on attempt {attempts}: {str(e)}")
                if attempts >= self.retry_attempts:
                    raise Exception(f"Translation failed after {attempts} attempts: {e}") from e
                time.sleep(1)  # Wait before retry
            except Exception as e:
                attempts += 1
                logging.error(f"Unexpected error on attempt {attempts}: {str(e)}")
                if attempts >= self.retry_attempts:
                    raise Exception(f"Translation failed after {attempts} attempts: {e}") from e
                time.sleep(1)  # Wait before retry

    def _apply_slang_postpass(self, original: str, translated: str) -> str:
        """Replace slang tokens Google left unchanged.

        A token qualifies only if it appears (case-insensitively) in both the
        original and the translated text — i.e. Google passed it through. This
        is position-independent, so differing word counts between source and
        translation can't misalign the substitution.
        """
        slang_dict = self._get_slang_translations()
        original_tokens = {w.lower() for w in original.split()}
        out = translated.split()
        for i, word in enumerate(out):
            lowered = word.lower()
            if lowered in slang_dict and lowered in original_tokens:
                out[i] = slang_dict[lowered]
        return ' '.join(out)
        
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
            
            # Try slang translation first
            _, was_slang = self._translate_slang(cleaned_text)
            if was_slang:
                return 'es'  # If it's in our slang dictionary, it's Spanish
            
            # Check for common Spanish phrases next
            preprocessed = self._preprocess_text(cleaned_text)
            if preprocessed:
                return preprocessed
                
            data = {'q': cleaned_text}
            logging.debug(f"Language detection request - Text length: {len(cleaned_text)} characters")
            logging.debug("Detection request data: " + ", ".join(f"{k}: {v}" for k, v in data.items()))

            # Apply rate limiting before making the API call, with a
            # deadline so a drained bucket can't stall the caller forever.
            wait_deadline = time.monotonic() + self.rate_limit_wait_seconds
            while not self.rate_limiter.acquire():
                if time.monotonic() >= wait_deadline:
                    raise Exception("Rate limit wait budget exhausted during language detection")
                time.sleep(0.1)  # Wait briefly for token replenishment

            response = requests.post(
                f"{self.base_url}/detect",  # This is a different endpoint for detection
                params={'key': self.api_key},
                json=data,
                headers=self.headers,
                timeout=REQUEST_TIMEOUT_SECONDS,
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
            raise  # Re-raise the error to be handled by the translate method
        except Exception as e:
            logging.error(f"Unexpected error during language detection: {str(e)}")
            raise Exception(f"Language detection failed: {e}") from e
            
    def clear_cache(self):
        """Clear the translation cache."""
        with self._cache_lock:
            self.cache.clear()

    def get_cache_stats(self) -> Dict[str, int]:
        """Get cache statistics."""
        with self._cache_lock:
            return {
                "size": len(self.cache),
                "maxsize": self.cache.maxsize,
                "currsize": self.cache.currsize
            }