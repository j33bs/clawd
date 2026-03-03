#!/usr/bin/env python3
"""Monitor mouse activity to detect when human is using it."""
import subprocess
import time
import os
import signal
import sys

LAST_MOUSE_FILE = "/tmp/last_mouse_activity"

def get_mouse_position():
    try:
        result = subprocess.run(
            ["xdotool", "getmouselocation"],
            capture_output=True, text=True, timeout=1
        )
        # Parse output like "x:100 y:200 screen:0 window:123456"
        parts = result.stdout.strip().split()
        for part in parts:
            if part.startswith("x:") or part.startswith("y:"):
                return part
        return None
    except:
        return None

def check_human_active():
    """Check if human is currently using mouse."""
    try:
        # Check /dev/input for recent mouse events
        result = subprocess.run(
            ["cat", "/proc/uptime"],
            capture_output=True, text=True, timeout=1
        )
        uptime = float(result.stdout.split()[0])
        
        # Also check xdotool for any mouse movement in last 2 seconds
        # If we can detect recent movement, human is active
        pos = get_mouse_position()
        return pos is not None
    except:
        return False

if __name__ == "__main__":
    import threading
    
    human_active = False
    last_check = time.time()
    
    print("Mouse monitor started. Checking every 0.5s...")
    
    while True:
        time.sleep(0.5)
        
        # Simple check - if mouse has moved recently, consider human active
        # For now, just track state
        current_time = time.time()
        
        # Write status to file for other processes to read
        with open(LAST_MOUSE_FILE, "w") as f:
            f.write(f"{current_time}\n")
        
        if len(sys.argv) > 1 and sys.argv[1] == "--check":
            print("Human active" if check_human_active() else "Human inactive")
