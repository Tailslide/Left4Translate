#!/usr/bin/env python3
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

from translator.translation_service import TranslationService

def main():
    """Test name + slang translations."""
    translator = TranslationService(
        api_key="dummy-key",  # Not needed for slang translations
        target_language="en"
    )
    
    # Test messages with name + slang patterns
    test_messages = [
        "Jason broca: hola amigo",
        "Miguel brocoli: que pasa",
        "Carlos brocha: ayuda",
        "Pedro tio: vamos",
        "Juan wey: cuidado",
        "Tanner güey: ostia tio"
    ]
    
    print("Testing name + slang translations:")
    print("-" * 50)
    
    for message in test_messages:
        # Split into player and content parts
        player, content = message.split(": ", 1)
        
        # Test the slang translation
        translated, was_slang = translator._translate_slang(player)
        if was_slang:
            print(f"\nPlayer name translation:")
            print(f"Original: {player}")
            print(f"Translated: {translated}")
            
        # Test content translation
        translated, was_slang = translator._translate_slang(content)
        if was_slang:
            print(f"\nContent translation:")
            print(f"Original: {content}")
            print(f"Translated: {translated}")
        
        print("-" * 50)

if __name__ == "__main__":
    main()