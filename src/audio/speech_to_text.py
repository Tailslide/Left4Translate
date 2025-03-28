"""
Speech-to-text service for voice translation feature.
"""
import logging
import os
import io
from typing import Tuple, Optional, Dict, Any
import numpy as np
from google.cloud import speech
from google.oauth2 import service_account

# Setup logger
logger = logging.getLogger(__name__)

class SpeechToTextService:
    """
    Provides speech-to-text transcription using Google Cloud Speech-to-Text API.
    
    This class handles the transcription of audio data to text,
    supporting various languages and audio formats.
    """
    
    def __init__(
        self,
        language_code: str = "en-US",
        sample_rate_hertz: int = 16000,
        model: str = "default",
        credentials_path: Optional[str] = None
    ):
        """
        Initialize the speech-to-text service.
        
        Args:
            language_code: Language code for speech recognition (e.g., "en-US", "es-ES")
            sample_rate_hertz: Audio sample rate in Hz
            model: Speech recognition model to use
            credentials_path: Path to Google Cloud service account credentials JSON file
        """
        self.language_code = language_code
        self.sample_rate_hertz = sample_rate_hertz
        self.model = model
        self.credentials_path = credentials_path
        
        # Initialize client
        self.client = self._initialize_client()
        
        logger.debug(f"SpeechToTextService initialized with language={language_code}, sample_rate={sample_rate_hertz}")
    
    def _initialize_client(self) -> Optional[speech.SpeechClient]:
        """
        Initialize the Google Cloud Speech client.
        
        Returns:
            speech.SpeechClient: Initialized client or None if initialization failed
        """
        try:
            # If credentials path is provided, use it
            if self.credentials_path:
                logger.info(f"Attempting to use credentials from: {self.credentials_path}")
                
                if not os.path.exists(self.credentials_path):
                    logger.error(f"Credentials file does not exist at path: {self.credentials_path}")
                    logger.error("Please check that the file exists and the path is correct in config.json")
                    return None
                
                try:
                    # Try to load and validate the credentials file
                    with open(self.credentials_path, 'r') as f:
                        import json
                        cred_data = json.load(f)
                        required_keys = ['type', 'project_id', 'private_key_id', 'private_key', 'client_email']
                        missing_keys = [key for key in required_keys if key not in cred_data]
                        
                        if missing_keys:
                            logger.error(f"Credentials file is invalid. Missing required keys: {missing_keys}")
                            return None
                        
                        logger.info(f"Credentials file appears valid. Project ID: {cred_data.get('project_id')}")
                except Exception as file_error:
                    logger.error(f"Error reading credentials file: {file_error}")
                    return None
                
                try:
                    credentials = service_account.Credentials.from_service_account_file(self.credentials_path)
                    client = speech.SpeechClient(credentials=credentials)
                    logger.info(f"Successfully initialized Speech-to-Text client with credentials")
                    return client
                except Exception as cred_error:
                    logger.error(f"Failed to initialize client with credentials file: {cred_error}")
                    import traceback
                    logger.error(f"Traceback: {traceback.format_exc()}")
                    return None
            
            # Try to use Application Default Credentials
            logger.info("No credentials file specified or failed to load. Trying Application Default Credentials...")
            try:
                client = speech.SpeechClient()
                logger.info("Successfully initialized Speech-to-Text client with Application Default Credentials")
                return client
            except Exception as e:
                logger.error(f"Failed to initialize Speech-to-Text client with Application Default Credentials: {e}")
                
            logger.error("No valid credentials provided. Speech-to-Text requires a service account.")
            logger.error("Please provide a valid service account credentials file path in the configuration.")
            return None
            
        except Exception as e:
            logger.error(f"Failed to initialize Speech-to-Text client: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return None
    
    def transcribe_audio(self, audio_data: np.ndarray) -> Tuple[str, float]:
        """
        Transcribe audio data to text.
        
        Args:
            audio_data: Audio data as a NumPy array
            
        Returns:
            Tuple[str, float]: Transcribed text and confidence score
        """
        if audio_data.size == 0:
            logger.warning("Empty audio data")
            return "", 0.0
            
        try:
            # Log audio data statistics to help diagnose issues
            duration = audio_data.size / self.sample_rate_hertz
            logger.info(f"Transcribing audio: {duration:.2f} seconds, {audio_data.size} samples")
            
            # Calculate audio levels
            rms = np.sqrt(np.mean(np.square(audio_data)))
            peak = np.max(np.abs(audio_data))
            
            # Convert to dB
            if rms > 0:
                rms_db = 20 * np.log10(rms)
            else:
                rms_db = -100
                
            if peak > 0:
                peak_db = 20 * np.log10(peak)
            else:
                peak_db = -100
                
            logger.info(f"Audio levels for transcription - RMS: {rms_db:.1f} dB, Peak: {peak_db:.1f} dB")
            
            # Warn if audio level is too low
            if rms_db < -50:
                logger.warning("Audio level is very low for transcription. Speech recognition may fail.")
            
            # Convert audio data to bytes
            audio_bytes = self._convert_to_bytes(audio_data)
            logger.info(f"Converted audio to {len(audio_bytes)} bytes")
            
            # Create recognition config
            config = speech.RecognitionConfig(
                encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
                sample_rate_hertz=self.sample_rate_hertz,
                language_code=self.language_code,
                model=self.model if self.model != "default" else None,
                enable_automatic_punctuation=True,
                audio_channel_count=1  # Mono audio
            )
            
            logger.info(f"Recognition config: encoding=LINEAR16, sample_rate={self.sample_rate_hertz}, language={self.language_code}, model={self.model}")
            
            # Create recognition audio
            audio = speech.RecognitionAudio(content=audio_bytes)
            
            # Perform synchronous speech recognition
            logger.info("Sending request to Google Speech-to-Text API...")
            response = self.client.recognize(config=config, audio=audio)
            logger.info("Received response from Google Speech-to-Text API")
            
            # Process results
            if not response.results:
                logger.warning("No transcription results returned from API")
                logger.info("This could be due to no speech detected or audio quality issues")
                return "", 0.0
                
            result = response.results[0]
            if not result.alternatives:
                logger.warning("No transcription alternatives in results")
                return "", 0.0
                
            transcript = result.alternatives[0].transcript
            confidence = result.alternatives[0].confidence
            
            logger.info(f"Transcribed: '{transcript}' (confidence: {confidence:.2f})")
            return transcript, confidence
            
        except Exception as e:
            logger.error(f"Transcription error: {e}")
            import traceback
            logger.error(f"Transcription error traceback: {traceback.format_exc()}")
            return "", 0.0
    
    def _convert_to_bytes(self, audio_data: np.ndarray) -> bytes:
        """
        Convert NumPy audio data to bytes.
        
        Args:
            audio_data: Audio data as a NumPy array
            
        Returns:
            bytes: Audio data as bytes
        """
        try:
            # Ensure audio data is in the right format (16-bit PCM)
            if audio_data.dtype != np.int16:
                # Scale float values to int16 range
                if audio_data.dtype == np.float32 or audio_data.dtype == np.float64:
                    audio_data = (audio_data * 32767).astype(np.int16)
                else:
                    audio_data = audio_data.astype(np.int16)
            
            # Convert to bytes
            byte_io = io.BytesIO()
            byte_io.write(audio_data.tobytes())
            audio_bytes = byte_io.getvalue()
            
            return audio_bytes
            
        except Exception as e:
            logger.error(f"Error converting audio data to bytes: {e}")
            return b""
    
    def update_config(
        self,
        language_code: Optional[str] = None,
        sample_rate_hertz: Optional[int] = None,
        model: Optional[str] = None
    ) -> None:
        """
        Update configuration.
        
        Args:
            language_code: New language code
            sample_rate_hertz: New sample rate
            model: New speech recognition model
        """
        if language_code is not None and language_code != self.language_code:
            self.language_code = language_code
            logger.info(f"Updated language code to: {self.language_code}")
            
        if sample_rate_hertz is not None and sample_rate_hertz != self.sample_rate_hertz:
            self.sample_rate_hertz = sample_rate_hertz
            logger.info(f"Updated sample rate to: {self.sample_rate_hertz}")
            
        if model is not None and model != self.model:
            self.model = model
            logger.info(f"Updated model to: {self.model}")