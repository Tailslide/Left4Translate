import re
import sys

def test_chat_pattern(line):
    """Test chat message pattern matching."""
    try:
        # Using the same pattern from config.json but with more flexible spacing
        pattern = (
            r'^(?:\((Survivor|Infected)\)[ ])?'  # Optional team prefix
            r'((?!Host_|Update|Unable|Changing|CAsync|NET_|L\s|String|Signal|Map|Server|Build|Players|Commentary|VSCRIPT|Anniversary|Steam|Network|RememberIPAddressForLobby)'  # Negative lookahead for system messages
            r'[\x03]?[A-Za-z0-9♥☺][\(\)A-Za-z0-9♥☺\s\x01\x03]{2,}?)'  # Player name with special chars and color codes
            r'\s*:\s+'  # Colon with flexible spacing
            r'(.+)$'  # Message content
        )
        match = re.match(pattern, line)
        
        if match:
            team_type = match.group(1) or "None"  # None for regular chat
            player = match.group(2).strip()  # Remove extra spaces
            message = match.group(3)
            sys.stdout.write(f"\nMatch found in: '{line}'\n")
            sys.stdout.write(f"  Team: {team_type}\n")
            sys.stdout.write(f"  Player: '{player}'\n")
            sys.stdout.write(f"  Message: '{message}'\n")
            sys.stdout.flush()
            return True
        else:
            sys.stdout.write(f"\nNo match in: '{line}'\n")
            sys.stdout.flush()
            return False
    except Exception as e:
        sys.stdout.write(f"\nError processing line '{line}': {str(e)}\n")
        sys.stdout.flush()
        return False

def run_tests():
    """Run all test cases."""
    test_messages = [
        # Regular chat
        'Pug Wrangler  :  hola amigo !',
        'Pug Wrangler  :  Hola Amigo!',
        'Pug Wrangler  :  whassup',
        'Pug Wrangler  :  pal',
        'Pug Wrangler  :  hows it going',
        'Pug Wrangler  :  for reals',
        
        # Team chat
        '(Survivor) ♥Pug Wrangler☺ :  Que pasa ?',
        '(Survivor) ♥Pug Wrangler☺ :  hi team',
        '(Survivor) ♥Pug Wrangler☺ :  hi teamies',
        '(Infected) ZombiePro :  Team message',
        '(Survivor) Player :  Another team message',
        
        # New test cases for Spanish chat
        '(Infected) C(Infected) Jason3854N : si',
        '(Infected) Jason3854N : :v',
        '(Infected) Tanner : soy muy cojones',
        '(Infected) Tanner : bistec',
        '(Infected) Jason3854N : ostia tio',
        
        # Color code test cases
        '\x03Player\x03 :  Colored message',
        '\x03Player with color\x03 :  Message',
        
        # System messages (should not match)
        'Host_WriteConfiguration: Wrote cfg/config.cfg',
        'Changing resolutions from (3840, 2160) -> (1360, 768)',
        'Unable to remove c:\\program files (x86)\\steam\\steamapps\\common\\left 4 dead 2\\left4dead2\\textwindow_temp.html!',
        'UpdateSystemLevel: ConVar mat_queue_mode controlled by gpu_level/cpu_level must not be marked as FCVAR_ARCHIVE or FCVAR_CHEAT!',
        'CAsyncWavDataCache:  0 .wavs total 0 bytes 0.00 % of capacity',
        'NET_GetBindAddresses found 192.168.12.143: Killer E2600 Gigabit Ethernet Controller',
        'L 01/26/2024 - 02:12:48: Log message',
        'String Table dictionary for downloadables should be rebuilt',
        'SignalXWriteOpportunity(2)',
        'Map: c1m1_hotel',
        'Server: 192.168.1.1',
        'Build: 123456',
        'Players: 4/8',
        'Commentary: enabled',
        'VSCRIPT: Loading script',
        'Anniversary: 10 years',
        'Steam: Connecting',
        'Network: Initialized',
        'RememberIPAddressForLobby: 192.168.1.1',
        
        # Additional test cases
        'Player with spaces  :  Message here',
        'Simple:not a real chat message',  # Should not match (no space after colon)
        ':: System message ::',  # Should not match
        'Log message without proper format',  # Should not match
        'A : B : C',  # Should not match (too short)
        'L : not a real message',  # Should not match (too short)
        'Host_ : fake message',  # Should not match (blocked prefix)
    ]

    sys.stdout.write("Testing chat message pattern matching...\n")
    sys.stdout.write("Pattern: " + (
        r'^(?:\((Survivor|Infected)\)[ ])?'
        r'((?!Host_|Update|Unable|Changing|CAsync|NET_|L\s|String|Signal|Map|Server|Build|Players|Commentary|VSCRIPT|Anniversary|Steam|Network|RememberIPAddressForLobby)'
        r'[\x03]?[A-Za-z0-9♥☺][\(\)A-Za-z0-9♥☺\s\x01\x03]{2,}?)'
        r'\s*:\s+'
        r'(.+)$'
    ) + "\n")
    sys.stdout.write("\nResults:\n")
    sys.stdout.flush()

    success_count = 0
    total_count = len(test_messages)
    
    for msg in test_messages:
        if test_chat_pattern(msg):
            success_count += 1
    
    sys.stdout.write(f"\nTest Summary:\n")
    sys.stdout.write(f"Total tests: {total_count}\n")
    sys.stdout.write(f"Successful matches: {success_count}\n")
    sys.stdout.write(f"Failed matches: {total_count - success_count}\n")
    sys.stdout.flush()

if __name__ == "__main__":
    run_tests()
    
    # Allow testing additional messages from command line
    if len(sys.argv) > 1:
        sys.stdout.write("\nTesting custom message:\n")
        test_chat_pattern(" ".join(sys.argv[1:]))