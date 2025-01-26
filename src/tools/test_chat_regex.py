import re

def test_chat_pattern(line):
    """Test chat message pattern matching."""
    # Pattern explanation:
    # ^                     Start of line
    # (?:                   Non-capturing group for team chat prefix
    #   \(                  Opening parenthesis
    #   (Survivor|Infected) Team type
    #   \)\s+              Closing parenthesis and whitespace
    # )?                    Team prefix is optional
    # (?!                   Negative lookahead for system messages
    #   Host_|Update|Unable|Changing|CAsync|NET_|L\s|String|Signal
    # )
    # (                     Capture player name
    #   [A-Za-z0-9♥☺\s]{2,}? At least 2 chars of allowed types
    # )
    # \s*:\s+              Colon with required space after
    # (.+)                 Message content
    # $                    End of line
    pattern = r'^(?:\((Survivor|Infected)\)\s+)?(?!Host_|Update|Unable|Changing|CAsync|NET_|L\s|String|Signal)([A-Za-z0-9♥☺\s]{2,}?)\s*:\s+(.+)$'
    match = re.match(pattern, line)
    
    if match:
        team_type = match.group(1) or "None"  # None for regular chat
        player = match.group(2).strip()  # Remove extra spaces
        message = match.group(3)
        print(f"\nMatch found:")
        print(f"  Team: {team_type}")
        print(f"  Player: '{player}'")
        print(f"  Message: '{message}'")
    else:
        print(f"\nNo match: '{line}'")

# Test cases from actual console.log
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
    
    # Additional test cases
    'Player with spaces  :  Message here',
    'Simple:not a real chat message',  # Should not match (no space after colon)
    ':: System message ::',  # Should not match
    'Log message without proper format',  # Should not match
    'A : B : C',  # Should not match (too short)
    'L : not a real message',  # Should not match (too short)
    'Host_ : fake message',  # Should not match (blocked prefix)
]

print("Testing chat message pattern matching...")
print("Pattern:", r'^(?:\((Survivor|Infected)\)\s+)?(?!Host_|Update|Unable|Changing|CAsync|NET_|L\s|String|Signal)([A-Za-z0-9♥☺\s]{2,}?)\s*:\s+(.+)$')
print("\nResults:")
for msg in test_messages:
    test_chat_pattern(msg)

if __name__ == "__main__":
    # Allow testing additional messages from command line
    import sys
    if len(sys.argv) > 1:
        print("\nTesting custom message:")
        test_chat_pattern(" ".join(sys.argv[1:]))