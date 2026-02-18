#!/usr/bin/env python3
"""
Time Management Learning System
Tracks user responses to suggestions and learns preferences over time.
"""

import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from random import choice, random
from typing import Optional

DATA_DIR = Path(__file__).parent / "data"
FEEDBACK_FILE = DATA_DIR / "feedback.json"
PREFERENCES_FILE = DATA_DIR / "preferences.json"

# Ensure data directory exists
DATA_DIR.mkdir(exist_ok=True)

def _load_json(file_path: Path, default: dict) -> dict:
    """Load JSON or return default."""
    if file_path.exists():
        with open(file_path) as f:
            return json.load(f)
    return default

def _save_json(file_path: Path, data: dict):
    """Save JSON to file."""
    with open(file_path, 'w') as f:
        json.dump(data, f, indent=2)

def _get_time_category() -> str:
    """Get time category based on current hour."""
    hour = datetime.now().hour
    if 5 <= hour < 10:
        return "morning"
    elif 10 <= hour < 14:
        return "midday"
    elif 14 <= hour < 18:
        return "afternoon"
    elif 18 <= hour < 22:
        return "evening"
    else:
        return "night"

def record_feedback(
    category: str,
    item: str,
    action: str,  # "done", "dismissed", "rescheduled", "ignored"
    time_spent: Optional[int] = None  # minutes
):
    """Record user feedback on a suggestion."""
    feedback = _load_json(FEEDBACK_FILE, {"interactions": []})
    
    feedback["interactions"].append({
        "timestamp": datetime.now().isoformat(),
        "category": category,
        "item": item,
        "action": action,
        "time_spent": time_spent,
        "time_of_day": _get_time_category()
    })
    
    # Keep only last 100 interactions
    if len(feedback["interactions"]) > 100:
        feedback["interactions"] = feedback["interactions"][-100:]
    
    _save_json(FEEDBACK_FILE, feedback)
    _update_preferences(category, item, action)

def _update_preferences(category: str, item: str, action: str):
    """Update preferences based on feedback."""
    prefs = _load_json(PREFERENCES_FILE, {"categories": {}, "items": {}})
    
    # Track item scores
    if item not in prefs["items"]:
        prefs["items"][item] = {"done": 0, "dismissed": 0, "rescheduled": 0, "count": 0}
    
    prefs["items"][item]["count"] += 1
    if action == "done":
        prefs["items"][item]["done"] += 1
    elif action == "dismissed":
        prefs["items"][item]["dismissed"] += 1
    elif action == "rescheduled":
        prefs["items"][item]["rescheduled"] += 1
    
    # Track category preferences
    time_cat = _get_time_category()
    if time_cat not in prefs["categories"]:
        prefs["categories"][time_cat] = {"done": 0, "total": 0}
    
    prefs["categories"][time_cat]["total"] += 1
    if action == "done":
        prefs["categories"][time_cat]["done"] += 1
    
    _save_json(PREFERENCES_FILE, prefs)

def get_preferred_items(category: str, min_score: float = 0.5) -> list:
    """Get items the user tends to do (score >= min_score)."""
    prefs = _load_json(PREFERENCES_FILE, {"items": {}})
    
    preferred = []
    for item, stats in prefs["items"].items():
        if stats["count"] >= 2:  # Need at least 2 interactions
            score = stats["done"] / stats["count"]
            if score >= min_score:
                preferred.append((item, score))
    
    return sorted(preferred, key=lambda x: x[1], reverse=True)

def get_time_preference() -> str:
    """Get the time category user is most productive in."""
    prefs = _load_json(PREFERENCES_FILE, {"categories": {}})
    
    best_time = None
    best_rate = 0
    
    for time_cat, stats in prefs["categories"].items():
        if stats["total"] >= 2:
            rate = stats["done"] / stats["total"]
            if rate > best_rate:
                best_rate = rate
                best_time = time_cat
    
    return best_time or _get_time_category()

def get_suggestion(type: str) -> str:
    """Get a suggestion, preferring learned preferences."""
    time_cat = _get_time_category()
    prefs = _load_json(PREFERENCES_FILE, {"items": {}})
    
    # Get preferred items first
    preferred = get_preferred_items(type, min_score=0.6)
    
    if preferred and random() < 0.6:  # 60% chance to use preference
        return choice([p[0] for p in preferred[:5]])
    
    # Otherwise load from source files
    if type == "tip":
        with open(Path(__file__).parent / "tips.md") as f:
            tips = [line.strip() for line in f if line.strip() and not line.startswith("#") and not line.startswith("##")]
        return choice(tips)
    elif type == "self_care":
        with open(Path(__file__).parent / "self_care.md") as f:
            care = [line.strip() for line in f if line.strip() and not line.startswith("#") and not line.startswith("##")]
        return choice(care)
    
    return "Take a moment to breathe."

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python3 time_management.py tip         # Get a time tip")
        print("  python3 time_management.py self_care    # Get self-care")
        print("  python3 time_management.py feedback <category> <item> <action>")
        sys.exit(1)
    
    if sys.argv[1] == "tip":
        print(get_suggestion("tip"))
    elif sys.argv[1] == "self_care":
        print(get_suggestion("self_care"))
    elif sys.argv[1] == "feedback" and len(sys.argv) >= 5:
        record_feedback(sys.argv[2], sys.argv[3], sys.argv[4])
        print("Feedback recorded")
    else:
        print("Unknown command")
