import re
import sys
import pytest

test_messages = [
    # Regular chat
    ('Pug Wrangler  :  hola amigo !', True),
    ('Pug Wrangler  :  Hola Amigo!', True),
    ('Pug Wrangler  :  whassup', True),
    ('Pug Wrangler  :  pal', True),
    ('Pug Wrangler  :  hows it going', True),
    ('Pug Wrangler  :  for reals', True),
    
    # Team chat
    ('(Survivor) ♥Pug Wrangler☺ :  Que pasa ?', True),
    ('(Survivor) ♥Pug Wrangler☺ :  hi team', True),
    ('(Survivor) ♥Pug Wrangler☺ :  hi teamies', True),
    ('(Infected) ZombiePro :  Team message', True),
    ('(Survivor) Player :  Another team message', True),
    
    # Spanish chat
    ('(Infected) C(Infected) Jason3854N : si', True),
    ('(Infected) Jason3854N : :v', True),
    ('(Infected) Tanner : soy muy cojones', True),
    ('(Infected) Tanner : bistec', True),
    ('(Infected) Jason3854N : ostia tio', True),
    
    # Color code test cases
    ('\x03Player\x03 :  Colored message', True),
    ('\x03Player with color\x03 :  Message', True),
    
    # System messages (should not match)
    ('Host_WriteConfiguration: Wrote cfg/config.cfg', False),
    ('Changing resolutions from (3840, 2160) -> (1360, 768)', False),
    ('Unable to remove c:\\program files (x86)\\steam\\steamapps\\common\\left 4 dead 2\\left4dead2\\textwindow_temp.html!', False),
    ('UpdateSystemLevel: ConVar mat_queue_mode controlled by gpu_level/cpu_level must not be marked as FCVAR_ARCHIVE or FCVAR_CHEAT!', False),
    ('CAsyncWavDataCache:  0 .wavs total 0 bytes 0.00 % of capacity', False),
    ('NET_GetBindAddresses found 192.168.12.143: Killer E2600 Gigabit Ethernet Controller', False),
    ('L 01/26/2024 - 02:12:48: Log message', False),
    ('String Table dictionary for downloadables should be rebuilt', False),
    ('SignalXWriteOpportunity(2)', False),
    ('Map: c1m1_hotel', False),
    ('Server: 192.168.1.1', False),
    ('Build: 123456', False),
    ('Players: 4/8', False),
    ('Commentary: enabled', False),
    ('VSCRIPT: Loading script', False),
    ('Anniversary: 10 years', False),
    ('Steam: Connecting', False),
    ('Network: Initialized', False),
    ('RememberIPAddressForLobby: 192.168.1.1', False),
    
    # Additional test cases
    ('Player with spaces  :  Message here', True),
    ('Simple:not a real chat message', False),  # Should not match (no space after colon)
    (':: System message ::', False),  # Should not match
    ('Log message without proper format', False),  # Should not match
    ('A : B : C', False),  # Should not match (too short)
    ('L : not a real message', False),  # Should not match (too short)
    ('Host_ : fake message', False),  # Should not match (blocked prefix)
]

@pytest.mark.parametrize("line,expected", test_messages)
def test_chat_pattern(line, expected):
    """Test chat message pattern matching."""
    pattern = (
        r'^(?:\((Survivor|Infected)\)[ ])?'  # Optional team prefix
        r'((?!Host_|Update|Unable|Changing|CAsync|NET_|L\s|String|Signal|Map|Server|Build|Players|Commentary|VSCRIPT|Anniversary|Steam|Network|RememberIPAddressForLobby)'  # Negative lookahead for system messages
        r'[\x03]?[A-Za-z0-9♥☺][\(\)A-Za-z0-9♥☺\s\x01\x03]{2,}?)'  # Player name with special chars and color codes
        r'\s*:\s+'  # Colon with flexible spacing
        r'(.+)$'  # Message content
    )
    match = re.match(pattern, line)
    result = bool(match)
    assert result == expected, f"Expected {expected} for line: {line}"
    
    if match and expected:
        team_type = match.group(1) or "None"  # None for regular chat
        player = match.group(2).strip()  # Remove extra spaces
        message = match.group(3)
        # These prints are useful for debugging but not necessary for pytest
        # print(f"\nMatch found in: '{line}'")
        # print(f"  Team: {team_type}")
        # print(f"  Player: '{player}'")
        # print(f"  Message: '{message}'")