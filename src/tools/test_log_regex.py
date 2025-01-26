import re

# Pattern explanation:
# ^                     Start of line
# (?:                   Non-capturing group for team chat prefix
#   \(                  Opening parenthesis
#   (Survivor|Infected) Team type
#   \)[ ]              Closing parenthesis and exactly one space
# )?                    Team prefix is optional
# (                     Capture player name
#   (?!                 Negative lookahead for system messages
#     Host_|Update|Unable|Changing|CAsync|NET_|L\s|String|Signal|
#     Map|Server|Build|Players|Commentary|VSCRIPT|Anniversary|Steam|Network|
#     RememberIPAddressForLobby
#   )
#   [\x03]?            Optional heart symbol
#   [A-Za-z]           Must start with letter
#   [A-Za-z0-9\s\x01\x03]{2,}? Then 2+ chars including control chars
# )
# [ ]+:[ ][ ]+         One or more spaces, colon, exactly two spaces (from log)
# (.+)                 Message content
# $                    End of line
PATTERN = (
    r'^(?:\((Survivor|Infected)\)[ ])?'  # Note: exactly one space after )
    r'((?!Host_|Update|Unable|Changing|CAsync|NET_|L\s|String|Signal|Map|Server|Build|Players|'
    r'Commentary|VSCRIPT|Anniversary|Steam|Network|RememberIPAddressForLobby)'
    r'[\x03]?[A-Za-z][A-Za-z0-9\s\x01\x03]{2,}?)'
    r'[ ]+:[ ][ ]+(.+)$'  # Exact spacing from log
)

def test_chat_pattern(line):
    """Test chat message pattern matching."""
    match = re.match(PATTERN, line)
    
    if match:
        team_type = match.group(1) or "None"  # None for regular chat
        player = match.group(2).strip()  # Remove extra spaces
        message = match.group(3)
        print(f"\nMatch found:")
        print(f"  Team: {team_type}")
        print(f"  Player: '{player}'")
        print(f"  Message: '{message}'")
        return True
    return False

def main():
    """Test regex pattern against actual console.log file."""
    log_path = "C:/Program Files (x86)/Steam/steamapps/common/Left 4 Dead 2/left4dead2/console.log"
    
    print("Testing chat message pattern against console.log...")
    print("Pattern:", PATTERN)
    print("\nResults:")
    
    try:
        with open(log_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            
        total_lines = len(lines)
        matched_lines = 0
        team_chat = 0
        regular_chat = 0
        
        # First pass - just show team chat lines for debugging
        print("\nTeam chat lines found in log:")
        for line in lines:
            line = line.strip()
            if '(Survivor)' in line or '(Infected)' in line:
                print(f"Found team chat: '{line}'")
                # Debug the line character by character
                print("Characters:", [c for c in line])
        
        # Second pass - actual pattern matching
        print("\nPattern matching results:")
        for line in lines:
            line = line.strip()
            if line:
                match = re.match(PATTERN, line)
                if match:
                    matched_lines += 1
                    if match.group(1):  # Has team type
                        team_chat += 1
                        print("\nTeam chat matched:")
                        print(f"Original line: '{line}'")
                        print(f"Groups: {match.groups()}")
                    else:
                        regular_chat += 1
                    test_chat_pattern(line)
                elif '(Survivor)' in line or '(Infected)' in line:
                    print(f"\nTeam chat NOT matched: '{line}'")
                    # Debug the line character by character
                    print("Characters:", [c for c in line])
                
        print(f"\nSummary:")
        print(f"Total lines processed: {total_lines}")
        print(f"Chat messages found: {matched_lines}")
        print(f"  - Team chat: {team_chat}")
        print(f"  - Regular chat: {regular_chat}")
        print(f"System messages filtered: {total_lines - matched_lines}")
        
    except Exception as e:
        print(f"Error reading log file: {e}")

if __name__ == "__main__":
    main()