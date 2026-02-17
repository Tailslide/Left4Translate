"""
Voice translation manager for voice translation feature.
"""
import logging
import threading
import time
import numpy as np
from typing import Optional, Dict, Any, Callable

from input.mouse_handler import MouseHandler
from audio.voice_recorder import VoiceRecorder
from audio.speech_to_text import SpeechToTextService
from translator.translation_service import TranslationService
from utils.clipboard_manager import ClipboardManager

# Setup logger
logger = logging.getLogger(__name__)

class VoiceTranslationManager:
    """
    Manages the voice translation process.
    
    This class coordinates the different components of the voice translation feature:
    - Mouse input handling
    - Audio recording
    - Speech-to-text transcription
    - Text translation
    - Display on screen
    - Clipboard operations
    """
    
    def __init__(
        self,
        config: Dict[str, Any],
        translation_service: TranslationService,
        screen_controller = None,
        on_translation_callback: Optional[Callable[[str, str], None]] = None
    ):
        """
        Initialize the voice translation manager.
        
        Args:
            config: Voice translation configuration
            translation_service: Translation service instance
            screen_controller: Screen controller instance for displaying translations
            on_translation_callback: Function to call with translation results
        """
        self.config = config
        self.translation_service = translation_service
        self.screen_controller = screen_controller
        self.on_translation_callback = on_translation_callback
        
        # Extract configuration
        voice_config = config.get("voice_translation", {})
        self.enabled = voice_config.get("enabled", True)
        
        # Initialize components
        self._init_components(voice_config)
        
        # State variables
        self.is_active = False
        self.lock = threading.Lock()
        self.last_audio_level = None  # Store the last measured audio level
        
        logger.info("Voice translation manager initialized")
    
    def _init_components(self, config: Dict[str, Any]) -> None:
        """
        Initialize voice translation components.
        
        Args:
            config: Voice translation configuration
        """
        # Mouse handler
        trigger_config = config.get("trigger_button", {})
        self.mouse_handler = MouseHandler(
            button=trigger_config.get("button", "button4"),
            modifier_keys=trigger_config.get("modifier_keys", []),
            on_press_callback=self._on_button_press,
            on_release_callback=self._on_button_release
        )
        
        # Voice recorder
        audio_config = config.get("audio", {})
        self.voice_recorder = VoiceRecorder(
            sample_rate=audio_config.get("sample_rate", 16000),
            channels=audio_config.get("channels", 1),
            device=audio_config.get("device", "default")
        )
        
        # Speech-to-text service
        stt_config = config.get("speech_to_text", {})
        self.speech_to_text = SpeechToTextService(
            language_code=stt_config.get("language", "en-US"),
            sample_rate_hertz=audio_config.get("sample_rate", 16000),
            model=stt_config.get("model", "default"),
            credentials_path=stt_config.get("credentials_path")
        )
        
        # Clipboard manager
        clipboard_config = config.get("clipboard", {})
        self.clipboard_manager = ClipboardManager(
            auto_copy=clipboard_config.get("auto_copy", True),
            format=clipboard_config.get("format", "both")
        )
        
        # Translation settings
        translation_config = config.get("translation", {})
        voice_translation_config = config.get("voice_translation", {}).get("translation", {})
        self.target_language = voice_translation_config.get("target_language", "es")
        
        # Display settings
        display_config = config.get("display", {})
        self.show_original = display_config.get("show_original", True)
        self.show_translated = display_config.get("show_translated", True)
        self.clear_after = display_config.get("clear_after", 5000)
    
    def start(self) -> bool:
        """
        Start the voice translation manager.
        
        Returns:
            bool: True if started successfully, False otherwise
        """
        if not self.enabled:
            logger.info("Voice translation is disabled in configuration")
            return False
            
        try:
            # Log diagnostic information
            logger.info("Starting voice translation manager with configuration:")
            logger.info(f"- Trigger button: {self.config.get('voice_translation', {}).get('trigger_button', {}).get('button', 'unknown')}")
            logger.info(f"- Audio device: {self.config.get('voice_translation', {}).get('audio', {}).get('device', 'unknown')}")
            
            # Check speech-to-text credentials
            stt_config = self.config.get('voice_translation', {}).get('speech_to_text', {})
            credentials_path = stt_config.get('credentials_path')
            if credentials_path:
                import os
                if os.path.exists(credentials_path):
                    logger.info(f"Speech-to-text credentials file found at: {credentials_path}")
                else:
                    logger.error(f"Speech-to-text credentials file NOT FOUND at: {credentials_path}")
            else:
                logger.warning("No speech-to-text credentials path specified")
            
            # Start mouse handler
            logger.info("Attempting to start mouse handler...")
            if not self.mouse_handler.start():
                logger.error("Failed to start mouse handler")
                return False
            
            # Test voice recorder initialization
            logger.info("Testing voice recorder initialization...")
            try:
                import sounddevice as sd
                devices = sd.query_devices()
                logger.info(f"Available audio devices: {len(devices)}")
                logger.info(f"Default input device: {sd.default.device[0]}")
            except Exception as audio_error:
                logger.error(f"Error querying audio devices: {audio_error}")
                
            self.is_active = True
            logger.info("Voice translation manager started successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start voice translation manager: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            self.stop()
            return False
    
    def stop(self) -> bool:
        """
        Stop the voice translation manager.
        
        Returns:
            bool: True if stopped successfully, False otherwise
        """
        try:
            # Stop recording if in progress
            if self.voice_recorder.is_recording():
                self.voice_recorder.stop_recording()
                
            # Stop mouse handler
            if self.mouse_handler.is_running():
                self.mouse_handler.stop()
                
            self.is_active = False
            logger.info("Voice translation manager stopped")
            return True
            
        except Exception as e:
            logger.error(f"Failed to stop voice translation manager: {e}")
            return False
    
    def _on_button_press(self) -> None:
        """Handle button press event."""
        try:
            # Start recording
            logger.info("Button pressed, starting recording")
            
            if not self.is_active:
                logger.warning("Button press ignored - voice translation manager is not active")
                return
                
            # Check if speech-to-text client is initialized
            if not hasattr(self.speech_to_text, 'client') or self.speech_to_text.client is None:
                logger.error("Speech-to-text client not initialized - check credentials")
                return
                
            logger.info("Attempting to start voice recording...")
            if self.voice_recorder.start_recording():
                logger.info("Successfully started recording on button press")
            else:
                logger.error("Failed to start recording on button press")
            
        except Exception as e:
            logger.error(f"Error handling button press: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
    
    def _on_button_release(self) -> None:
        """Handle button release event."""
        try:
            # Stop recording and process audio
            logger.info("Button released, stopping recording")
            
            if not self.voice_recorder.is_recording():
                logger.warning("Button release ignored - not currently recording")
                return
                
            logger.info("Stopping voice recording and processing audio...")
            audio_data = self.voice_recorder.stop_recording()
            
            if audio_data.size == 0:
                logger.warning("No audio data recorded - recording may have failed")
                return
                
            logger.info(f"Recorded {len(audio_data)} audio samples ({len(audio_data)/self.voice_recorder.sample_rate:.2f} seconds)")
            
            # Process in a separate thread to avoid blocking
            logger.info("Starting audio processing in separate thread")
            threading.Thread(
                target=self._process_audio,
                args=(audio_data,),
                daemon=True
            ).start()
            
        except Exception as e:
            logger.error(f"Error handling button release: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
    
    def _process_audio(self, audio_data) -> None:
        """
        Process recorded audio.
        
        Args:
            audio_data: Recorded audio data
        """
        try:
            # Transcribe audio to text
            logger.info("Starting audio transcription...")
            
            # Check if speech-to-text client is initialized
            if not hasattr(self.speech_to_text, 'client') or self.speech_to_text.client is None:
                logger.error("Speech-to-text client not initialized - check credentials")
                self._show_transcription_error("Speech-to-text client not initialized")
                return
            
            # Calculate audio levels for diagnostic purposes
            audio_quality = self._check_audio_quality(audio_data)
            
            # If audio quality is very low, show a specific error message
            if audio_quality == "very_low":
                logger.warning("Audio level too low for effective speech recognition")
                self._show_transcription_error("Low audio level")
                return
                
            transcript, confidence = self.speech_to_text.transcribe_audio(audio_data)
            
            if not transcript:
                logger.warning("Transcription failed or returned empty result")
                
                # Customize error message based on audio quality
                if audio_quality == "low":
                    self._show_transcription_error("Low audio level")
                else:
                    self._show_transcription_error("No speech detected")
                return
                
            logger.info(f"Transcription successful: '{transcript}' (confidence: {confidence:.2f})")
                
            # Translate text
            logger.info(f"Translating text from '{self.speech_to_text.language_code}' to '{self.target_language}'")
            translated = self.translation_service.translate(
                transcript,
                source_language=self.speech_to_text.language_code,
                target_language=self.target_language
            )
            
            if not translated:
                logger.warning("Translation failed or returned empty result")
                return
                
            logger.info(f"Translation successful: '{translated}'")
                
            # Copy to clipboard
            logger.info("Copying to clipboard...")
            self.clipboard_manager.copy_to_clipboard(transcript, translated)
            
            # Display on screen if screen controller is available
            if self.screen_controller:
                logger.info("Displaying on screen...")
                self.screen_controller.display_message(
                    player="Voice",
                    original=transcript,
                    translated=translated,
                    is_team_chat=False,
                    timeout=self.clear_after if self.clear_after > 0 else None
                )
            
            # Call callback with results
            if self.on_translation_callback:
                logger.info("Calling translation callback...")
                self.on_translation_callback(transcript, translated)
                
            logger.info(f"Voice translation complete: '{transcript}' -> '{translated}'")
            
        except Exception as e:
            logger.error(f"Error processing audio: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
    
    def update_config(self, config: Dict[str, Any]) -> None:
        """
        Update configuration.
        
        Args:
            config: New voice translation configuration
        """
        try:
            # Update main config
            self.config["voice_translation"] = config
            self.enabled = config.get("enabled", True)
            
            # Update components
            trigger_config = config.get("trigger_button", {})
            self.mouse_handler.update_config(
                button=trigger_config.get("button"),
                modifier_keys=trigger_config.get("modifier_keys")
            )
            
            audio_config = config.get("audio", {})
            self.voice_recorder.update_config(
                sample_rate=audio_config.get("sample_rate"),
                channels=audio_config.get("channels"),
                device=audio_config.get("device")
            )
            
            stt_config = config.get("speech_to_text", {})
            self.speech_to_text.update_config(
                language_code=stt_config.get("language"),
                sample_rate_hertz=audio_config.get("sample_rate"),
                model=stt_config.get("model")
            )
            
            clipboard_config = config.get("clipboard", {})
            self.clipboard_manager.update_config(
                auto_copy=clipboard_config.get("auto_copy"),
                format=clipboard_config.get("format")
            )
            
            # Update translation settings
            translation_config = config.get("translation", {})
            self.target_language = translation_config.get("target_language", self.target_language)
            
            # Update display settings
            display_config = config.get("display", {})
            self.show_original = display_config.get("show_original", self.show_original)
            self.show_translated = display_config.get("show_translated", self.show_translated)
            self.clear_after = display_config.get("clear_after", self.clear_after)
            
            logger.info("Voice translation configuration updated")
            
        except Exception as e:
            logger.error(f"Failed to update voice translation configuration: {e}")
    
    def is_running(self) -> bool:
        """
        Check if the voice translation manager is running.
        
        Returns:
            bool: True if running, False otherwise
        """
        return self.is_active
        
    def _check_audio_quality(self, audio_data) -> str:
        """
        Check audio quality and log diagnostic information.
        
        Args:
            audio_data: Audio data to check
            
        Returns:
            str: Quality level ("very_low", "low", "good", "acceptable", "error")
        """
        try:
            # Calculate RMS value to estimate audio level
            rms = np.sqrt(np.mean(np.square(audio_data)))
            peak = np.max(np.abs(audio_data))
            
            # Convert to dB for easier interpretation
            if rms > 0:
                rms_db = 20 * np.log10(rms)
            else:
                rms_db = -100  # Arbitrary low value for silence
                
            if peak > 0:
                peak_db = 20 * np.log10(peak)
            else:
                peak_db = -100
                
            logger.info(f"Audio quality check - RMS: {rms_db:.1f} dB, Peak: {peak_db:.1f} dB")
            
            # Store audio level for later use
            self.last_audio_level = rms_db
            
            # Provide feedback based on audio levels
            if rms_db < -50:
                logger.warning("Audio level is VERY LOW. Speech recognition will likely fail.")
                logger.warning("Please check the following:")
                logger.warning("1. Make sure your microphone is not muted")
                logger.warning("2. Increase microphone volume in system settings")
                logger.warning("3. Speak closer to the microphone")
                logger.warning("4. Try a different microphone if available")
                return "very_low"
            elif rms_db < -40:
                logger.warning("Audio level is low. Consider speaking louder or adjusting microphone settings.")
                return "low"
            elif rms_db > -20:
                logger.info("Audio level is good.")
                return "good"
            else:
                logger.info("Audio level is acceptable.")
                return "acceptable"
                
        except Exception as e:
            logger.error(f"Error checking audio quality: {e}")
            return "error"
            
    def _show_transcription_error(self, error_type: str) -> None:
        """
        Display transcription error message on screen.
        
        Args:
            error_type: Type of error that occurred
        """
        try:
            error_message = "Voice recognition failed"
            
            if error_type == "No speech detected":
                details = "No speech detected. Please speak clearly and check microphone."
            elif error_type == "Low audio level":
                details = "Microphone volume too low. Please speak louder or adjust microphone settings."
            elif error_type == "Speech-to-text client not initialized":
                details = "Speech recognition not initialized. Check credentials."
            else:
                details = "Unknown error. Please try again."
                
            logger.info(f"Showing transcription error: {error_message} - {details}")
            
            # Display on screen if screen controller is available
            if self.screen_controller:
                self.screen_controller.display_message(
                    player="Voice",
                    original=error_message,
                    translated=details,
                    is_team_chat=False,
                    timeout=5000  # 5 seconds
                )
                
        except Exception as e:
            logger.error(f"Error showing transcription error: {e}")