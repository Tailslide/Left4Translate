#!/usr/bin/env python3
import sys
import time
from pathlib import Path
import serial.tools.list_ports

# Add src directory to Python path
src_dir = Path(__file__).resolve().parent.parent
sys.path.append(str(src_dir))

from display.screen_controller import ScreenController

def list_com_ports():
    """List all available COM ports."""
    print("\nAvailable COM ports:")
    ports = list(serial.tools.list_ports.comports())
    if not ports:
        print("No COM ports found!")
    else:
        for port in ports:
            print(f"- {port.device}: {port.description}")

def test_screen():
    """Test the Turing Smart Screen connection and display."""
    print("Testing Turing Smart Screen connection...")
    
    # List available COM ports
    list_com_ports()
    
    try:
        # Initialize screen controller with COM8
        print("\nInitializing screen controller on COM8...")
        screen = ScreenController(
            port="COM8",
            baud_rate=115200,
            brightness=80,
            max_messages=5,
            message_timeout=10000,
            margin=5,
            spacing=2
        )
        
        # Connect to screen
        print("Attempting to connect to screen...")
        if not screen.connect():
            print("\nFailed to connect to screen! Please check:")
            print("1. The screen is properly connected via USB")
            print("2. No other program is using COM8")
            print("3. You have sufficient permissions (try running as administrator)")
            return
            
        print("Successfully connected to screen")
        
        # Clear display
        screen.clear_display()
        print("Cleared display")
        
        # Test message display
        print("Displaying test messages...")
        
        # Test message 1
        print("Sending message 1...")
        screen.display_message(
            player="System",
            original="Testing screen display...",
            translated="画面表示をテスト中..."
        )
        time.sleep(2)
        
        # Test message 2
        print("Sending message 2...")
        screen.display_message(
            player="Test",
            original="¡Hola Mundo!",
            translated="Hello World!"
        )
        time.sleep(2)
        
        # Test message 3
        print("Sending message 3...")
        screen.display_message(
            player="Left4Translate",
            original="Тестирование завершено",
            translated="Test complete"
        )
        
        # Wait for messages to display
        print("Messages sent to display. Waiting 10 seconds...")
        time.sleep(10)
        
        print("Test completed successfully")
        
    except Exception as e:
        print(f"\nError during test: {e}")
        print("\nPlease check:")
        print("1. The screen is properly connected via USB")
        print("2. No other program is using COM8")
        print("3. You have sufficient permissions (try running as administrator)")
        
    finally:
        # Clean up
        screen.disconnect()
        print("Disconnected from screen")

if __name__ == "__main__":
    test_screen()