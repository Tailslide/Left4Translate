"""
Voice recorder for voice translation feature.
"""
import logging
import threading
import time
import os
from typing import Optional, Callable, Any
import numpy as np
import sounddevice as sd

# Setup logger
logger = logging.getLogger(__name__)

class VoiceRecorder:
    """
    Records audio from a microphone for voice translation.
    
    This class handles audio recording from the microphone,
    providing methods to start and stop recording, and to
    retrieve the recorded audio data.
    """
    
    def __init__(
        self,
        sample_rate: int = 16000,
        channels: int = 1,
        device: Optional[str] = None,
        on_data_callback: Optional[Callable[[np.ndarray], Any]] = None
    ):
        """
        Initialize the voice recorder.
        
        Args:
            sample_rate: Audio sample rate in Hz
            channels: Number of audio channels (1 for mono, 2 for stereo)
            device: Audio input device name or None for default
            on_data_callback: Function to call with audio data chunks during recording
        """
        self.sample_rate = sample_rate
        self.channels = channels
        self.device = device
        self.on_data_callback = on_data_callback
        
        self.recording = False
        self.audio_data = []
        self.stream = None
        self.lock = threading.Lock()
        
        # Try to find the specified device or use default
        self._find_device()
        
        logger.debug(f"VoiceRecorder initialized with sample_rate={sample_rate}, channels={channels}, device={self.device}")
    
    def _find_device(self) -> None:
        """Find the specified audio device or use default."""
        try:
            devices = sd.query_devices()
            
            if self.device and self.device != "default":
                # Try to find the device by name
                for i, dev in enumerate(devices):
                    if self.device.lower() in dev['name'].lower():
                        self.device = i
                        logger.info(f"Found device: {dev['name']} (index: {i})")
                        self._check_microphone_volume()
                        return
                
                logger.warning(f"Device '{self.device}' not found. Using default input device.")
            
            # Use default input device
            self.device = sd.default.device[0]
            default_device = devices[self.device]
            logger.info(f"Using default input device: {default_device['name']} (index: {self.device})")
            self._check_microphone_volume()
            
        except Exception as e:
            logger.error(f"Error finding audio device: {e}")
            self.device = None
            
    def _check_microphone_volume(self) -> None:
        """Check microphone volume and provide guidance if it's too low."""
        try:
            # Get detailed device info
            devices = sd.query_devices()
            device_info = None
            
            if isinstance(self.device, int):
                if 0 <= self.device < len(devices):
                    device_info = devices[self.device]
                    logger.info(f"Using device index {self.device}: {device_info['name']}")
            else:
                # Find device by name
                for i, dev in enumerate(devices):
                    if self.device.lower() in dev['name'].lower():
                        device_info = dev
                        logger.info(f"Found device by name: {dev['name']} (index: {i})")
                        break
            
            if device_info:
                logger.info(f"Device details:")
                logger.info(f"  Name: {device_info['name']}")
                logger.info(f"  Max input channels: {device_info['max_input_channels']}")
                logger.info(f"  Default sample rate: {device_info['default_samplerate']}")
                logger.info(f"  Host API: {device_info['hostapi']}")
            
            # Record a short audio sample to check levels
            logger.info("Testing microphone volume levels...")
            duration = 2  # seconds - increased from 1 to 2 for better sampling
            sample_rate = self.sample_rate
            channels = self.channels
            
            # Record a short sample
            logger.info(f"Recording {duration} second test sample...")
            recording = sd.rec(
                int(duration * sample_rate),
                samplerate=sample_rate,
                channels=channels,
                device=self.device,
                dtype='float32'
            )
            sd.wait()  # Wait for recording to complete
            
            # Calculate audio levels
            if recording.size > 0:
                rms = np.sqrt(np.mean(np.square(recording)))
                peak = np.max(np.abs(recording))
                
                # Convert to dB
                if rms > 0:
                    rms_db = 20 * np.log10(rms)
                else:
                    rms_db = -100
                    
                if peak > 0:
                    peak_db = 20 * np.log10(peak)
                else:
                    peak_db = -100
                
                logger.info(f"Microphone test - RMS: {rms_db:.1f} dB, Peak: {peak_db:.1f} dB")
                
                # Provide guidance based on levels
                if rms_db < -50:
                    logger.warning("Microphone volume is VERY LOW!")
                    logger.warning("Speech recognition will likely fail with this audio level.")
                    logger.warning("Please check the following:")
                    logger.warning("1. Make sure your microphone is not muted in Windows sound settings")
                    logger.warning("2. Increase microphone volume in Windows sound settings")
                    logger.warning("3. Speak closer to the microphone")
                    logger.warning("4. Try a different microphone if available")
                    
                    # Provide instructions for Windows sound settings
                    logger.info("To adjust microphone volume in Windows:")
                    logger.info("1. Right-click the speaker icon in the system tray")
                    logger.info("2. Select 'Open Sound settings'")
                    logger.info("3. Click on 'Sound Control Panel' on the right")
                    logger.info("4. Go to the 'Recording' tab")
                    logger.info("5. Select your microphone and click 'Properties'")
                    logger.info("6. Go to the 'Levels' tab and increase the volume")
                    
                    # Suggest alternative microphones
                    self._suggest_alternative_microphones()
                elif rms_db < -40:
                    logger.warning("Microphone volume is low. Consider increasing the volume for better speech recognition.")
                elif rms_db > -20:
                    logger.info("Microphone volume is good.")
                else:
                    logger.info("Microphone volume is acceptable but could be improved.")
            else:
                logger.warning("Failed to record audio sample for volume check.")
                
        except Exception as e:
            logger.error(f"Error checking microphone volume: {e}")
            
    def _suggest_alternative_microphones(self) -> None:
        """Suggest alternative microphones if available."""
        try:
            devices = sd.query_devices()
            input_devices = []
            
            # Find all input devices
            for i, device in enumerate(devices):
                if device['max_input_channels'] > 0:
                    input_devices.append((i, device))
            
            if len(input_devices) > 1:
                logger.info("Available alternative microphones:")
                for i, (idx, device) in enumerate(input_devices):
                    if isinstance(self.device, int) and idx == self.device:
                        continue  # Skip current device
                    if isinstance(self.device, str) and self.device.lower() in device['name'].lower():
                        continue  # Skip current device
                    logger.info(f"  {i+1}. {device['name']} (device index: {idx})")
                
                logger.info("To use an alternative microphone, update the 'device' setting in config.json:")
                logger.info('  "device": "Microphone Name" or "device": 2')
            else:
                logger.warning("No alternative microphones found.")
                
        except Exception as e:
            logger.error(f"Error suggesting alternative microphones: {e}")
    
    def start_recording(self) -> bool:
        """
        Start recording audio.
        
        Returns:
            bool: True if recording started successfully, False otherwise
        """
        if self.recording:
            logger.warning("Already recording")
            return False
            
        try:
            # Log audio device information
            logger.info("Starting audio recording with the following configuration:")
            logger.info(f"- Sample rate: {self.sample_rate} Hz")
            logger.info(f"- Channels: {self.channels}")
            logger.info(f"- Device: {self.device}")
            
            try:
                # Get more detailed device info
                devices = sd.query_devices()
                if isinstance(self.device, int) and 0 <= self.device < len(devices):
                    device_info = devices[self.device]
                    logger.info(f"- Device name: {device_info['name']}")
                    logger.info(f"- Max input channels: {device_info['max_input_channels']}")
                    logger.info(f"- Default sample rate: {device_info['default_samplerate']}")
            except Exception as device_error:
                logger.warning(f"Could not get detailed device info: {device_error}")
            
            # Clear previous recording data
            self.audio_data = []
            
            # Start the audio stream
            logger.info("Creating audio input stream...")
            self.stream = sd.InputStream(
                samplerate=self.sample_rate,
                channels=self.channels,
                device=self.device,
                callback=self._audio_callback
            )
            
            logger.info("Starting audio stream...")
            self.stream.start()
            self.recording = True
            
            logger.info(f"Successfully started recording audio")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start recording: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return False
    
    def stop_recording(self) -> np.ndarray:
        """
        Stop recording audio and return the recorded data.
        
        Returns:
            np.ndarray: Recorded audio data as a NumPy array
        """
        if not self.recording:
            logger.warning("Not recording")
            return np.array([])
            
        try:
            # Stop the audio stream
            if self.stream:
                self.stream.stop()
                self.stream.close()
                self.stream = None
                
            self.recording = False
            
            # Combine all audio chunks into a single array
            with self.lock:
                if not self.audio_data:
                    logger.warning("No audio data recorded")
                    return np.array([])
                    
                combined_data = np.concatenate(self.audio_data)
                
            logger.info(f"Stopped recording. Captured {len(combined_data)} samples ({len(combined_data)/self.sample_rate:.2f} seconds)")
            return combined_data
            
        except Exception as e:
            logger.error(f"Failed to stop recording: {e}")
            return np.array([])
    
    def _audio_callback(self, indata, frames, time, status):
        """
        Callback function for audio stream.
        
        Args:
            indata: Input audio data
            frames: Number of frames
            time: Stream time
            status: Stream status
        """
        if status:
            logger.warning(f"Audio stream status: {status}")
            
        # Make a copy of the data to avoid reference issues
        data = indata.copy()
        
        # Log audio levels periodically (every 5 callbacks to avoid excessive logging)
        if len(self.audio_data) % 5 == 0:
            # Calculate RMS value to estimate audio level
            rms = np.sqrt(np.mean(np.square(data)))
            peak = np.max(np.abs(data))
            
            # Convert to dB for easier interpretation
            if rms > 0:
                rms_db = 20 * np.log10(rms)
            else:
                rms_db = -100  # Arbitrary low value for silence
                
            if peak > 0:
                peak_db = 20 * np.log10(peak)
            else:
                peak_db = -100
                
            logger.info(f"Audio levels - RMS: {rms_db:.1f} dB, Peak: {peak_db:.1f} dB")
            
            # Warn if audio level is too low
            if rms_db < -50:
                logger.warning("Audio level is very low. Check microphone and speak louder.")
        
        # Add the data to our buffer
        with self.lock:
            self.audio_data.append(data)
            
        # Call the data callback if provided
        if self.on_data_callback:
            try:
                self.on_data_callback(data)
            except Exception as e:
                logger.error(f"Error in audio data callback: {e}")
    
    def is_recording(self) -> bool:
        """
        Check if recording is in progress.
        
        Returns:
            bool: True if recording, False otherwise
        """
        return self.recording
    
    def update_config(
        self,
        sample_rate: Optional[int] = None,
        channels: Optional[int] = None,
        device: Optional[str] = None
    ) -> None:
        """
        Update configuration.
        
        Args:
            sample_rate: New audio sample rate
            channels: New number of audio channels
            device: New audio input device
        """
        restart_needed = False
        
        if sample_rate is not None and sample_rate != self.sample_rate:
            self.sample_rate = sample_rate
            restart_needed = True
            logger.info(f"Updated sample rate to: {self.sample_rate}")
            
        if channels is not None and channels != self.channels:
            self.channels = channels
            restart_needed = True
            logger.info(f"Updated channels to: {self.channels}")
            
        if device is not None and device != self.device:
            self.device = device
            self._find_device()
            restart_needed = True
            logger.info(f"Updated device to: {self.device}")
            
        # If recording is in progress and config changed, restart recording
        if restart_needed and self.recording:
            logger.info("Restarting recording with new configuration")
            self.stop_recording()
            self.start_recording()