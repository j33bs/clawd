#!/usr/bin/env python3
"""
TACTI ↔ OASIS Runtime Integration
Wires OASIS modules into the live TACTI runtime.

Hooks into: message_hooks.py
- Pre-process: Suggest response strategy based on relationship state
- Post-process: Learn from interaction outcomes
"""

import json
from pathlib import Path
from datetime import datetime, timezone
from typing import Any, Optional

# Import OASIS modules
from tacti_oasis_bridge import load_tacti_state, export_to_oasis
from tacti_action_mapper import map_tacti_to_oasis, create_oasis_action_payload
from tacti_feedback_loop import apply_feedback_to_tacti, predict_with_feedback, run_what_if_simulation

# Config
REPO_ROOT = Path(__file__).resolve().parents[2]
OASIS_INTEGRATION_ENABLED = True
USE_LOCAL_LLM = True  # Set to False to use template-only


def get_current_session_state(session_id: str) -> dict:
    """Get current relationship state for a session."""
    state = load_tacti_state()
    return state.get("sessions", {}).get(session_id, {})


def suggest_response_strategy(session_id: str, user_message: str = "") -> dict:
    """
    Pre-process hook: Suggest how to respond based on relationship state.
    
    Returns:
        {
            "strategy": "empathetic" | "direct" | "cautious" | "neutral",
            "confidence": 0.0-1.0,
            "suggested_action": "LIKE_COMMENT" | "CREATE_COMMENT" | etc,
            "reasoning": "..."
        }
    """
    session = get_current_session_state(session_id)
    
    if not session:
        return {
            "strategy": "neutral",
            "confidence": 0.5,
            "suggested_action": "DO_NOTHING",
            "reasoning": "No session history, using neutral default"
        }
    
    trust = session.get("trust_score", 0.5)
    attunement = session.get("attunement_index", 0.5)
    user_events = session.get("user_events", 0)
    
    # Determine strategy based on relationship metrics
    if trust >= 0.8:
        strategy = "empathetic"
        suggested_action = "CREATE_COMMENT"
    elif trust >= 0.5:
        strategy = "direct"
        suggested_action = "CREATE_COMMENT"
    elif trust >= 0.3:
        strategy = "cautious"
        suggested_action = "DO_NOTHING"
    else:
        strategy = "neutral"
        suggested_action = "DO_NOTHING"
    
    # Use LLM for nuanced mapping if available
    if USE_LOCAL_LLM:
        try:
            result = map_tacti_to_oasis(
                trust_delta=0,  # No change yet
                arousal=0.5,
                attunement_delta=0,
                session_context={
                    "session_id": session_id,
                    "trust_score": trust,
                    "attunement_index": attunement,
                    "user_events": user_events
                },
                use_llm=True
            )
            return {
                "strategy": strategy,
                "confidence": result.get("confidence", 0.7),
                "suggested_action": result.get("action_type", suggested_action),
                "reasoning": result.get("reasoning", "")[:200],
                "llm_used": True
            }
        except Exception as e:
            pass
    
    # Fallback to template
    return {
        "strategy": strategy,
        "confidence": 0.6,
        "suggested_action": suggested_action,
        "reasoning": f"Trust={trust:.2f}, Attunement={attunement:.2f}",
        "llm_used": False
    }


def record_interaction_outcome(
    session_id: str,
    user_message: str,
    assistant_response: str,
    outcome: str = "success"
) -> dict:
    """
    Post-process hook: Record interaction and learn from it.
    
    Args:
        session_id: The session
        user_message: What the user said
        assistant_response: How we responded
        outcome: "success" | "failure" | "neutral"
    
    Returns:
        Feedback result with model adjustments
    """
    # Estimate trust change based on outcome
    trust_delta = 0.02 if outcome == "success" else -0.02
    
    # Get current state
    session = get_current_session_state(session_id)
    current_trust = session.get("trust_score", 0.5)
    predicted_trust = current_trust + trust_delta
    
    # Create simulation result
    simulation_result = {
        "session_id": session_id,
        "predicted_trust": predicted_trust,
        "actual_trust": current_trust,  # Will update after we see actual
        "predicted_attunement": session.get("attunement_index", 0.5),
        "actual_attunement": session.get("attunement_index", 0.5),
        "predicted_actions": [],  # Could track suggested vs actual
        "actual_actions": [],
    }
    
    # Apply feedback
    try:
        feedback = apply_feedback_to_tacti(simulation_result, session_id)
        return feedback
    except Exception as e:
        return {"error": str(e)}


def what_if_response(session_id: str, intervention: dict) -> dict:
    """
    Run a what-if scenario to test response strategies.
    
    Example:
        what_if_response("telegram:123", {"trust_delta": 0.1, "attunement": 0.05})
    """
    return run_what_if_simulation(session_id, intervention)


def export_session_to_oasis(session_id: str, output_path: Path = None) -> list:
    """Export a session's relationship state to OASIS agent profile."""
    return export_to_oasis(sessions=[session_id], output_path=output_path)


def get_relationship_prediction(session_id: str) -> dict:
    """Get relationship prediction with feedback adjustments."""
    session = get_current_session_state(session_id)
    return predict_with_feedback(session_id, {
        "trust_score": session.get("trust_score", 0.5),
        "attunement_index": session.get("attunement_index", 0.5)
    })


# Integration with message_hooks
def integrated_process_message(event: dict, *, repo_root: Path | str) -> dict:
    """
    Enhanced message processing with OASIS integration.
    
    This replaces the basic process_message_event from message_hooks
    when OASIS integration is enabled.
    """
    from message_hooks import process_message_event, build_message_event
    
    session_id = event.get("session_id", "unknown")
    
    # 1. Pre-process: Get response strategy
    pre_insight = suggest_response_strategy(session_id, event.get("content", ""))
    
    # 2. Process: Standard TACTI tracking
    tacti_result = process_message_event(event, repo_root=repo_root)
    
    # 3. Post-process: Could record outcome (called separately)
    
    return {
        "pre_insight": pre_insight,
        "tacti_result": tacti_result,
        "oasis_enabled": OASIS_INTEGRATION_ENABLED
    }


# CLI for testing
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="TACTI ↔ OASIS Runtime Integration")
    parser.add_argument("--session", default="telegram:test", help="Session ID")
    parser.add_argument("--suggest", action="store_true", help="Get response strategy")
    parser.add_argument("--predict", action="store_true", help="Get relationship prediction")
    parser.add_argument("--what-if", help="What-if: trust_delta=0.1,attunement=0.05")
    parser.add_argument("--export", action="store_true", help="Export to OASIS")
    
    args = parser.parse_args()
    
    if args.suggest:
        result = suggest_response_strategy(args.session)
        print(f"\n=== Response Strategy ===")
        print(f"Strategy: {result['strategy']}")
        print(f"Confidence: {result['confidence']:.2f}")
        print(f"Suggested: {result['suggested_action']}")
        print(f"Reasoning: {result['reasoning']}")
    
    if args.predict:
        result = get_relationship_prediction(args.session)
        print(f"\n=== Relationship Prediction ===")
        print(json.dumps(result, indent=2))
    
    if args.what_if:
        params = {}
        for part in args.what_if.split(","):
            k, v = part.split("=")
            params[k.strip()] = float(v.strip())
        result = what_if_response(args.session, params)
        print(f"\n=== What-If ===")
        print(json.dumps(result, indent=2))
    
    if args.export:
        result = export_session_to_oasis(args.session)
        print(f"\n=== Exported to OASIS ===")
        print(f"Profiles: {len(result)}")
