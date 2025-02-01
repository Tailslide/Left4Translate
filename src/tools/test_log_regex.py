import re
import pytest

# Pattern explanation in comments preserved from original
PATTERN = (
    r'^(?:\((Survivor|Infected)\)\s+|(?!\([^)]*\)))'  # Team prefix must be Survivor/Infected or no parentheses at all
    r'(?!.*(?:CBase|CSteam|CAsync|Map:|Players:|Build:|Server\s+Number|Unable\s+to|Update|RememberIPAddressForLobby|BinkOpen))'  # System messages
    r'((?:(?:\s*♥?(?:\([A-Za-z]+\))?\s*)*'  # Handle repeated team/name parts
    r'[\x03♥]?[A-Za-z][A-Za-z0-9\s\x01\x03♥☺()\s]{2,}?))'  # Player name (added () to allowed chars)
    r'\s*:\s*'  # Colon separator
    r'(?!.*(?:FileReceived|InitiateConnection|Damage\s+(?:Given|Taken)|\.wavs\s+total|\.(bik|wav|cfg)))'  # System message content
    r'(.+)$'  # Message content
)

test_cases = [
    # Regular chat messages (should match)
    ('Player : Hello world', True),
    ('♥Player♥ : Hi there', True),
    ('Player123 : Testing message', True),
    ('Pro Gamer : GG WP', True),
    
    # Team chat messages (should match)
    ('(Survivor) Player : Need help!', True),
    ('(Infected) ZombiePlayer : Coming!', True),
    ('(Survivor) ♥Player♥ : Watch out!', True),
    ('(Infected) Player123 : Almost there', True),
    
    # Complex player names (should match)
    ('♥Player (Pro)♥ : Message here', True),
    ('(Survivor) Player (MVP) : Team message', True),
    ('\x03ColoredName\x03 : Colored message', True),
    ('Player ☺ : Happy message', True),
    
    # System messages (should not match)
    ('CBase Entity created', False),
    ('CSteam Connection established', False),
    ('CAsync Operation completed', False),
    ('Map: c1m1_hotel', False),
    ('Players: 4/8', False),
    ('Build: 123456', False),
    ('Server Number: 1', False),
    ('Unable to connect', False),
    ('Update available', False),
    ('RememberIPAddressForLobby: 192.168.1.1', False),
    ('BinkOpen: video.bik', False),
    
    # System message content (should not match)
    ('Player : FileReceived data.txt', False),
    ('Player : InitiateConnection to server', False),
    ('Player : Damage Given 100', False),
    ('Player : Damage Taken 50', False),
    ('Player : 10 .wavs total', False),
    ('Player : loading test.bik', False),
    ('Player : config.wav loaded', False),
    ('Player : autoexec.cfg executed', False),
    
    # Edge cases
    ('(Survivor) : Invalid message', False),  # No player name
    ('(Invalid) Player : Bad team', False),  # Invalid team
    (' : Empty player', False),  # No player name
    ('Player :', False),  # No message
    (':', False),  # Empty line with colon
    ('Just a regular line', False),  # No chat format
]

@pytest.mark.parametrize("line,expected", test_cases)
def test_chat_pattern(line, expected):
    """Test chat message pattern matching."""
    match = re.match(PATTERN, line)
    result = bool(match)
    assert result == expected, f"Expected {expected} for line: {line}"
    
    if match and expected:
        team_type = match.group(1) or "None"  # None for regular chat
        player = match.group(2).strip()  # Remove extra spaces
        message = match.group(3)
        # These prints are useful for debugging but not necessary for pytest
        # print(f"\nMatch found:")
        # print(f"  Team: {team_type}")
        # print(f"  Player: '{player}'")
        # print(f"  Message: '{message}'")