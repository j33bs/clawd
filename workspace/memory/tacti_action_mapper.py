#!/usr/bin/env python3
"""
TACTI → OASIS Action Mapper
Maps TACTI relationship events to OASIS social actions using local LLM.

Usage:
    python3 tacti_action_mapper.py --trust-delta 0.05 --arousal 0.8
    python3 tacti_action_mapper.py --session-id telegram:12345 --event-type trust_change
"""

import json
import argparse
import os
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional

import requests

# Local LLM endpoint (llama.cpp)
LOCAL_LLM_URL = os.environ.get("LOCAL_LLM_URL", "http://localhost:8001/v1/chat/completions")
LOCAL_MODEL = os.environ.get("LOCAL_MODEL", "local-assistant")

# OASIS action types
OASIS_ACTIONS = {
    "LIKE_POST": "Express approval by liking a post",
    "DISLIKE_POST": "Express disapproval by disliking a post",
    "CREATE_POST": "Start a new discussion thread",
    "CREATE_COMMENT": "Reply to existing content",
    "LIKE_COMMENT": "Agree with a comment",
    "DISLIKE_COMMENT": "Disagree with a comment",
    "FOLLOW": "Subscribe to another user",
    "MUTE": "Stop following / ignore a user",
    "SEARCH_POSTS": "Look for relevant content",
    "SEARCH_USER": "Find specific users",
    "TREND": "Check trending topics",
    "REFRESH": "Update feed",
    "DO_NOTHING": "Passive observation",
    "REPOST": "Share content unchanged",
    "QUOTE": "Share with commentary",
    "REPORT": "Flag inappropriate content",
}

# Action templates based on TACTI metrics
ACTION_TEMPLATES = {
    "trust_increase": {
        "primary": ["LIKE_POST", "FOLLOW", "CREATE_COMMENT"],
        "secondary": ["LIKE_COMMENT", "REPOST"],
        "intensity": "high"
    },
    "trust_decrease": {
        "primary": ["MUTE", "DISLIKE_POST"],
        "secondary": ["DO_NOTHING"],
        "intensity": "medium"
    },
    "arousal_spike": {
        "primary": ["CREATE_POST", "CREATE_COMMENT"],
        "secondary": ["QUOTE"],
        "intensity": "high"
    },
    "arousal_low": {
        "primary": ["DO_NOTHING", "REFRESH"],
        "secondary": ["SEARCH_POSTS", "TREND"],
        "intensity": "low"
    },
    "attunement_increase": {
        "primary": ["CREATE_COMMENT", "LIKE_COMMENT"],
        "secondary": ["FOLLOW"],
        "intensity": "medium"
    },
    "neutral": {"primary": ["REFRESH", "DO_NOTHING"], "secondary": ["SEARCH_POSTS"], "intensity": "low"}, "attunement_decrease": {
        "primary": ["DO_NOTHING"],
        "secondary": ["MUTE"],
        "intensity": "medium"
    },
}


def call_local_llm(prompt: str, system_prompt: str = None) -> str:
    """Call local LLM for action reasoning."""
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})
    
    payload = {
        "model": LOCAL_MODEL,
        "messages": messages,
        "temperature": 0.7,
        "max_tokens": 200,
    }
    
    try:
        response = requests.post(LOCAL_LLM_URL, json=payload, timeout=30)
        response.raise_for_status()
        result = response.json()
        return result["choices"][0]["message"]["content"]
    except Exception as e:
        return f"[LLM unavailable: {e}]"


def determine_event_type(trust_delta: float = 0, arousal: float = 0.5, 
                        attunement_delta: float = 0) -> str:
    """Determine the primary event type from TACTI metrics."""
    if trust_delta > 0.03:
        return "trust_increase"
    elif trust_delta < -0.03:
        return "trust_decrease"
    elif arousal > 0.8:
        return "arousal_spike"
    elif arousal < 0.2:
        return "arousal_low"
    elif attunement_delta > 0.05:
        return "attunement_increase"
    elif attunement_delta < -0.05:
        return "attunement_decrease"
    else:
        return "neutral"


def generate_action_with_llm(event_type: str, session_context: dict, 
                            use_llm: bool = True) -> dict:
    """Use LLM to generate contextually appropriate OASIS action."""
    
    template = ACTION_TEMPLATES.get(event_type, ACTION_TEMPLATES["neutral"])
    primary_actions = template["primary"]
    secondary_actions = template["secondary"]
    
    if not use_llm:
        # Fallback to simple template
        return {
            "action_type": primary_actions[0],
            "confidence": 0.7,
            "reasoning": f"Template-based: {event_type}",
            "intensity": template["intensity"]
        }
    
    # Build prompt for LLM
    trust = session_context.get("trust_score", 0.5)
    attunement = session_context.get("attunement_index", 0.5)
    user_events = session_context.get("user_events", 0)
    
    system_prompt = """You are a social behavior mapper. Given TACTI relationship metrics, 
select the most appropriate OASIS social action. Respond with ONLY JSON:
{"action_type": "ACTION_NAME", "confidence": 0.0-1.0, "reasoning": "brief explanation"}"""
    
    prompt = f"""Given this TACTI session context:
- Trust score: {trust} (0=distrust, 1=full trust)
- Attunement: {attunement} (0=disconnected, 1=highly connected)
- Interaction count: {user_events}
- Event type: {event_type}

Available actions: {', '.join(primary_actions + secondary_actions)}

Select the best action and respond with JSON only."""
    
    llm_response = call_local_llm(prompt, system_prompt)
    
    # Parse LLM response
    try:
        # Try to extract JSON from response
        if "{" in llm_response:
            json_start = llm_response.find("{")
            json_end = llm_response.rfind("}") + 1
            action_data = json.loads(llm_response[json_start:json_end])
            action_data["reasoning"] = llm_response
            action_data["llm_used"] = True
            return action_data
    except:
        pass
    
    # Fallback if LLM parsing fails
    return {
        "action_type": primary_actions[0],
        "confidence": 0.6,
        "reasoning": f"LLM response parse failed, using template: {event_type}",
        "llm_used": True,
        "llm_raw": llm_response[:100]
    }


def create_oasis_action_payload(action_type: str, agent_id: str, 
                                content: str = None, target_id: str = None) -> dict:
    """Create OASIS-compatible action payload."""
    payload = {
        "action_type": action_type,
        "agent_id": agent_id,
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    }
    
    if content:
        payload["action_args"] = {"content": content}
    if target_id:
        if "action_args" not in payload:
            payload["action_args"] = {}
        payload["action_args"]["target_id"] = target_id
    
    return payload


def map_tacti_to_oasis(
    trust_delta: float = 0,
    arousal: float = 0.5,
    attunement_delta: float = 0,
    session_context: dict = None,
    use_llm: bool = True
) -> dict:
    """
    Main function: Map TACTI metrics to OASIS actions.
    
    Returns:
        dict with action_type, confidence, reasoning, and OASIS payload
    """
    session_context = session_context or {}
    
    # Determine event type
    event_type = determine_event_type(trust_delta, arousal, attunement_delta)
    
    # Get action from LLM or template
    action_data = generate_action_with_llm(event_type, session_context, use_llm)
    
    # Create OASIS payload
    agent_id = session_context.get("session_id", "unknown")
    oasis_payload = create_oasis_action_payload(
        action_data["action_type"],
        agent_id,
        content=action_data.get("content")
    )
    
    return {
        "event_type": event_type,
        "action_type": action_data["action_type"],
        "confidence": action_data.get("confidence", 0.5),
        "reasoning": action_data.get("reasoning", ""),
        "llm_used": action_data.get("llm_used", False),
        "oasis_payload": oasis_payload
    }


def simulate_conversation_flow(session_context: dict, events: list) -> list:
    """Simulate a sequence of TACTI events and their OASIS actions."""
    results = []
    
    for i, event in enumerate(events):
        trust_delta = event.get("trust_delta", 0)
        arousal = event.get("arousal", 0.5)
        attunement_delta = event.get("attunement_delta", 0)
        
        result = map_tacti_to_oasis(
            trust_delta=trust_delta,
            arousal=arousal,
            attunement_delta=attunement_delta,
            session_context=session_context,
            use_llm=True
        )
        
        # Update session context based on event
        if "trust_score" in session_context:
            session_context["trust_score"] = max(0, min(1, 
                session_context["trust_score"] + trust_delta))
        
        results.append({
            "step": i + 1,
            "input": event,
            "output": result
        })
    
    return results


def main():
    parser = argparse.ArgumentParser(description="TACTI → OASIS Action Mapper")
    parser.add_argument("--trust-delta", type=float, default=0, 
                        help="Change in trust score (-1 to 1)")
    parser.add_argument("--arousal", type=float, default=0.5,
                        help="Arousal level (0 to 1)")
    parser.add_argument("--attunement-delta", type=float, default=0,
                        help="Change in attunement (-1 to 1)")
    parser.add_argument("--session-id", type=str, default="default",
                        help="Session identifier")
    parser.add_argument("--user-events", type=int, default=10,
                        help="Number of user events in session")
    parser.add_argument("--trust", type=float, default=0.5,
                        help="Current trust score")
    parser.add_argument("--attunement", type=float, default=0.5,
                        help="Current attunement index")
    parser.add_argument("--no-llm", action="store_true",
                        help="Use template fallback instead of LLM")
    parser.add_argument("--simulate", type=str,
                        help="Run simulation: trust_increase, trust_decrease, arousal_spike, etc.")
    
    args = parser.parse_args()
    
    session_context = {
        "session_id": args.session_id,
        "trust_score": args.trust,
        "attunement_index": args.attunement,
        "user_events": args.user_events
    }
    
    if args.simulate:
        # Run predefined simulation
        events = [
            {"trust_delta": 0.05, "arousal": 0.6, "attunement_delta": 0.02},
            {"trust_delta": 0.08, "arousal": 0.7, "attunement_delta": 0.05},
            {"trust_delta": -0.04, "arousal": 0.3, "attunement_delta": -0.03},
            {"trust_delta": 0.02, "arousal": 0.9, "attunement_delta": 0.01},
        ]
        results = simulate_conversation_flow(session_context, events)
        
        print(f"\n=== TACTI → OASIS Action Simulation ===")
        for r in results:
            print(f"\nStep {r['step']}: {r['input']}")
            print(f"  → Action: {r['output']['action_type']}")
            print(f"  → Confidence: {r['output']['confidence']:.2f}")
            print(f"  → Reasoning: {r['output']['reasoning'][:80]}...")
    else:
        result = map_tacti_to_oasis(
            trust_delta=args.trust_delta,
            arousal=args.arousal,
            attunement_delta=args.attunement_delta,
            session_context=session_context,
            use_llm=not args.no_llm
        )
        
        print(f"\n=== TACTI → OASIS Action Mapping ===")
        print(f"Event type: {result['event_type']}")
        print(f"Action: {result['action_type']}")
        print(f"Confidence: {result['confidence']:.2f}")
        print(f"LLM used: {result['llm_used']}")
        print(f"Reasoning: {result['reasoning'][:100]}...")
        print(f"\nOASIS Payload:")
        print(json.dumps(result["oasis_payload"], indent=2))


if __name__ == "__main__":
    main()
