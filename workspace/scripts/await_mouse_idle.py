#!/usr/bin/env python3
"""Wait for human to stop using mouse before proceeding."""
import subprocess
import time
import sys

def get_mouse_position():
    try:
        result = subprocess.run(
            ["xdotool", "getmouselocation"],
            capture_output=True, text=True, timeout=1
        )
        return result.stdout.strip()
    except:
        return None

def wait_for_idle(timeout=10):
    """Wait for mouse to be still."""
    last_pos = None
    stable_count = 0
    
    for i in range(int(timeout * 10)):
        current_pos = get_mouse_position()
        
        if current_pos == last_pos:
            stable_count += 1
            if stable_count >= 5:  # 0.5 seconds of stillness
                return True
        else:
            stable_count = 0
            last_pos = current_pos
        
        time.sleep(0.1)
    
    return False  # Timeout

if __name__ == "__main__":
    if wait_for_idle():
        print("IDLE")
        sys.exit(0)
    else:
        print("TIMEOUT")
        sys.exit(1)
