#!/usr/bin/env python3
"""
TACTI → OASIS Data Bridge
Exports TACTI relationship state to OASIS agent profiles for social simulation.

Usage:
    python3 tacti_oasis_bridge.py [--sessions SessionID] [--output path/to/profiles.json]
"""

import json
import argparse
from pathlib import Path
from datetime import datetime, timezone

# TACTI state paths
REPO_ROOT = Path(__file__).resolve().parents[2]
RELATIONSHIP_STATE_PATH = REPO_ROOT / "workspace" / "state_runtime" / "memory" / "relationship_state.json"
AROUSAL_STATE_PATH = REPO_ROOT / "workspace" / "memory" / "arousal_tracker.py"

# MBTI mapping based on trust/attunement
MBTI_MAPPING = {
    (0.0, 0.3): "ISTJ",   # Low trust, low attunement - cautious
    (0.3, 0.5): "ISFJ",   # Moderate trust
    (0.5, 0.7): "INFJ",   # Growing trust
    (0.7, 0.85): "ENFJ",  # High trust
    (0.85, 1.0): "ENTJ",  # Very high trust - confident
}

# Interest topics based on attunement
INTEREST_TOPICS = {
    "low": ["Technology", "News", "Practical Solutions"],
    "medium": ["Philosophy", "Science", "Innovation"],
    "high": ["Consciousness", "Relationships", "Future Studies"],
}


def _mbti_from_metrics(trust_score: float, attunement: float) -> str:
    """Map TACTI metrics to MBTI personality type."""
    for (trust_min, trust_max), mbti in MBTI_MAPPING.items():
        if trust_min <= trust_score < trust_max:
            return mbti
    return "INTP"  # Default


def _interests_from_attunement(attunement: float) -> list[str]:
    """Map attunement level to interest topics."""
    if attunement < 0.3:
        return INTEREST_TOPICS["low"]
    elif attunement < 0.7:
        return INTEREST_TOPICS["medium"]
    else:
        return INTEREST_TOPICS["high"]


def _persona_from_metrics(session_id: str, trust_score: float, attunement: float, user_events: int) -> dict:
    """Generate OASIS-compatible persona from TACTI session metrics."""
    
    mbti = _mbti_from_metrics(trust_score, attunement)
    interests = _interests_from_attunement(attunement)
    
    # Generate name based on session
    session_hash = hash(session_id) % 1000
    first_names = ["Alex", "Jordan", "Taylor", "Morgan", "Casey", "Riley", "Quinn", "Avery"]
    last_names = ["Smith", "Chen", "Williams", "Patel", "Kim", "Johnson", "Lee", "Davis"]
    first_name = first_names[session_hash % len(first_names)]
    last_name = last_names[(session_hash // 100) % len(last_names)]
    
    # Persona description based on trust level
    if trust_score >= 0.85:
        persona_desc = f"A thoughtful and engaged individual who values deep conversation and intellectual exploration. They are open to new ideas and enjoy discussing complex topics like {interests[0].lower()} and {interests[1].lower()}. With a track record of {user_events} meaningful interactions, they approach discussions with curiosity and good faith."
    elif trust_score >= 0.5:
        persona_desc = f"An interested learner who enjoys exploring ideas and perspectives. They bring a balanced approach to conversation, discussing topics like {interests[0].lower()} and {interests[1].lower()}. After {user_events} interactions, they've shown openness to collaboration and growth."
    else:
        persona_desc = f"A careful but curious individual who prefers to observe before engaging deeply. They have practical interests in {interests[0].lower()} and appreciate thoughtful discussion. With {user_events} interactions on record, they're building rapport gradually."
    
    return {
        "realname": f"{first_name} {last_name}",
        "username": f"{first_name.lower()}{session_hash}",
        "bio": f"Interested in {interests[0]} and {interests[1]}. Exploring ideas through conversation.",
        "persona": persona_desc,
        "age": 25 + (session_hash % 30),
        "gender": "non_binary",
        "mbti": mbti,
        "country": "Australia",
        "profession": "Technology",
        "interested_topics": interests,
        # TACTI-specific fields (for internal tracking)
        "_tacti": {
            "session_id": session_id,
            "trust_score": trust_score,
            "attunement_index": attunement,
            "interaction_count": user_events,
            "exported_at": datetime.now(timezone.utc).isoformat() + "Z"
        }
    }


def load_tacti_state():
    """Load TACTI relationship state."""
    if not RELATIONSHIP_STATE_PATH.exists():
        return {"schema": 1, "sessions": {}}
    
    try:
        return json.loads(RELATIONSHIP_STATE_PATH.read_text())
    except Exception:
        return {"schema": 1, "sessions": {}}


def export_to_oasis(sessions: list[str] = None, output_path: Path = None) -> list[dict]:
    """
    Export TACTI sessions to OASIS agent profiles.
    
    Args:
        sessions: Optional list of session IDs to export. If None, exports all.
        output_path: Optional path to write JSON file.
    
    Returns:
        List of OASIS-compatible agent profiles.
    """
    state = load_tacti_state()
    all_sessions = state.get("sessions", {})
    
    # Filter sessions if specified
    if sessions:
        all_sessions = {k: v for k, v in all_sessions.items() if k in sessions}
    
    profiles = []
    for session_id, session_data in all_sessions.items():
        trust = float(session_data.get("trust_score", 0.5))
        attunement = float(session_data.get("attunement_index", 0.5))
        user_events = int(session_data.get("user_events", 0))
        
        profile = _persona_from_metrics(session_id, trust, attunement, user_events)
        profiles.append(profile)
    
    # Write to file if output path specified
    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(profiles, indent=2))
        print(f"✓ Exported {len(profiles)} profiles to {output_path}")
    
    return profiles


def main():
    parser = argparse.ArgumentParser(description="TACTI → OASIS Data Bridge")
    parser.add_argument("--sessions", nargs="*", help="Session IDs to export (default: all)")
    parser.add_argument("--output", type=Path, help="Output JSON path")
    parser.add_argument("--limit", type=int, default=10, help="Max profiles to export")
    args = parser.parse_args()
    
    profiles = export_to_oasis(sessions=args.sessions, output_path=args.output)
    
    print(f"\n=== TACTI → OASIS Bridge ===")
    print(f"Exported {len(profiles)} agent profiles")
    if profiles:
        print(f"\nSample profile:")
        sample = profiles[0]
        print(f"  Name: {sample['realname']}")
        print(f"  Username: {sample['username']}")
        print(f"  MBTI: {sample['mbti']}")
        print(f"  Trust: {sample['_tacti']['trust_score']}")
        print(f"  Attunement: {sample['_tacti']['attunement_index']}")


if __name__ == "__main__":
    main()
