"""
List all available audio input devices with their indices and properties.
This helps identify the correct microphone to use in the configuration.
"""
import sounddevice as sd
import numpy as np
import sys

def main():
    """List all audio devices with detailed information."""
    print("\n=== AUDIO DEVICE INFORMATION ===\n")
    
    # Get all devices
    devices = sd.query_devices()
    
    # Get default devices
    default_input = sd.default.device[0]
    default_output = sd.default.device[1]
    
    print(f"Default input device: {default_input}")
    print(f"Default output device: {default_output}")
    print(f"Total devices found: {len(devices)}\n")
    
    # Print all input devices with their properties
    print("=== INPUT DEVICES ===\n")
    
    input_devices = []
    
    for i, device in enumerate(devices):
        # Check if this is an input device (has input channels)
        if device['max_input_channels'] > 0:
            input_devices.append((i, device))
            default_marker = " (DEFAULT)" if i == default_input else ""
            print(f"Device {i}{default_marker}: {device['name']}")
            print(f"  Max input channels: {device['max_input_channels']}")
            print(f"  Default sample rate: {device['default_samplerate']}")
            print(f"  Host API: {device['hostapi']}")
            print()
    
    print(f"Total input devices: {len(input_devices)}\n")
    
    # Test recording from default device
    if len(input_devices) > 0:
        print("=== TESTING DEFAULT INPUT DEVICE ===\n")
        
        try:
            # Record a short sample to check levels
            duration = 1  # seconds
            sample_rate = 16000
            channels = 1
            
            print(f"Recording {duration} second sample from default device...")
            
            # Record a short sample
            recording = sd.rec(
                int(duration * sample_rate),
                samplerate=sample_rate,
                channels=channels,
                device=default_input,
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
                
                print(f"Audio levels from default device:")
                print(f"  RMS: {rms_db:.1f} dB")
                print(f"  Peak: {peak_db:.1f} dB")
                
                if rms_db < -50:
                    print("\nWARNING: Audio level is very low!")
                elif rms_db < -40:
                    print("\nWARNING: Audio level is low.")
                else:
                    print("\nAudio level is good.")
            else:
                print("Failed to record audio sample.")
                
        except Exception as e:
            print(f"Error testing default device: {e}")
    
    print("\n=== CONFIGURATION RECOMMENDATION ===\n")
    print("To specify a device in config.json, use either:")
    print("1. The device name (recommended): \"device\": \"Device Name Here\"")
    print("2. The device index: \"device\": 1")
    print("\nExample:")
    print("""
    "audio": {
      "sample_rate": 16000,
      "channels": 1,
      "device": "Microphone (Your Device Name)"
    }
    """)

if __name__ == "__main__":
    main()