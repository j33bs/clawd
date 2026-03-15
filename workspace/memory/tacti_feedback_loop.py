#!/usr/bin/env python3
"""
TACTI ← OASIS Feedback Loop
Uses OASIS simulation outcomes to improve TACTI relationship predictions.

Usage:
    python3 tacti_feedback_loop.py --simulation-results /path/to/results.json
    python3 tacti_feedback_loop.py --test-run
"""

import json
import argparse
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional
import hashlib

# TACTI state paths
REPO_ROOT = Path(__file__).resolve().parents[2]
RELATIONSHIP_STATE_PATH = REPO_ROOT / "workspace" / "state_runtime" / "memory" / "relationship_state.json"
FEEDBACK_LOG_PATH = REPO_ROOT / "workspace" / "memory" / "oasis_feedback_log.jsonl"

# Prediction accuracy weights
WEIGHTS = {
    "trust_prediction_error": 0.4,
    "attunement_prediction_error": 0.3,
    "action_match_score": 0.3,
}


def load_relationship_state() -> dict:
    """Load current TACTI relationship state."""
    if not RELATIONSHIP_STATE_PATH.exists():
        return {"schema": 1, "sessions": {}}
    try:
        return json.loads(RELATIONSHIP_STATE_PATH.read_text())
    except:
        return {"schema": 1, "sessions": {}}


def save_relationship_state(state: dict) -> None:
    """Save TACTI relationship state."""
    RELATIONSHIP_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    RELATIONSHIP_STATE_PATH.write_text(json.dumps(state, indent=2))


def compute_prediction_error(predicted: float, actual: float) -> float:
    """Compute normalized prediction error (0-1, lower is better)."""
    return min(1.0, abs(predicted - actual))


def compute_action_match_score(predicted_actions: list, actual_actions: list) -> float:
    """Compute how well predicted actions matched actual actions."""
    if not predicted_actions or not actual_actions:
        return 0.5
    
    matches = 0
    for pred in predicted_actions:
        if pred in actual_actions:
            matches += 1
    
    return matches / max(len(predicted_actions), len(actual_actions))


def log_feedback(simulation_id: str, session_id: str, predictions: dict, 
                 outcomes: dict, model_adjustment: dict) -> None:
    """Log feedback for future learning."""
    FEEDBACK_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    
    entry = {
        "simulation_id": simulation_id,
        "session_id": session_id,
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "predictions": predictions,
        "outcomes": outcomes,
        "model_adjustment": model_adjustment,
    }
    
    with open(FEEDBACK_LOG_PATH, "a") as f:
        f.write(json.dumps(entry) + "\n")


def apply_feedback_to_tacti(simulation_results: dict, session_id: str) -> dict:
    """
    Apply OASIS simulation feedback to TACTI predictions.
    
    Args:
        simulation_results: Dict with predicted vs actual outcomes from OASIS
        session_id: TACTI session to update
    
    Returns:
        dict with model adjustments made
    """
    state = load_relationship_state()
    session = state.get("sessions", {}).get(session_id)
    
    if not session:
        # Create new session if doesn't exist
        session = {
            "user_events": 0,
            "assistant_events": 0,
            "trust_score": 0.5,
            "attunement_index": 0.5,
            "open_count": 0,
            "close_count": 0,
            "unresolved_threads": 0,
        }
        state.setdefault("sessions", {})[session_id] = session
    
    # Get prediction errors
    predicted_trust = simulation_results.get("predicted_trust", 0.5)
    actual_trust = simulation_results.get("actual_trust", 0.5)
    trust_error = compute_prediction_error(predicted_trust, actual_trust)
    
    predicted_attunement = simulation_results.get("predicted_attunement", 0.5)
    actual_attunement = simulation_results.get("actual_attunement", 0.5)
    attunement_error = compute_prediction_error(predicted_attunement, actual_attunement)
    
    predicted_actions = simulation_results.get("predicted_actions", [])
    actual_actions = simulation_results.get("actual_actions", [])
    action_score = compute_action_match_score(predicted_actions, actual_actions)
    
    # Compute overall model accuracy (1 - error)
    model_accuracy = 1.0 - (
        trust_error * WEIGHTS["trust_prediction_error"] +
        attunement_error * WEIGHTS["attunement_prediction_error"] +
        (1 - action_score) * WEIGHTS["action_match_score"]
    )
    
    # Adjust prediction model based on errors
    # If we consistently under/over-predict, add a bias term
    trust_bias = predicted_trust - actual_trust
    attunement_bias = predicted_attunement - actual_attunement
    
    # Store feedback in session
    session["_oasis_feedback"] = {
        "last_simulation": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "model_accuracy": round(model_accuracy, 3),
        "trust_error": round(trust_error, 3),
        "attunement_error": round(attunement_error, 3),
        "action_match": round(action_score, 3),
        "trust_bias": round(trust_bias, 3),
        "attunement_bias": round(attunement_bias, 3),
        "simulation_count": session.get("_oasis_feedback", {}).get("simulation_count", 0) + 1,
    }
    
    # Adjust prediction weights if accuracy is low
    if model_accuracy < 0.7:
        # Reduce confidence in predictions
        adjustment = {
            "action": "reduced_confidence",
            "reason": f"model_accuracy ({model_accuracy:.2f}) below threshold",
            "trust_bias_adjustment": trust_bias * 0.1,
            "attunement_bias_adjustment": attunement_bias * 0.1,
        }
    elif model_accuracy > 0.9:
        # Increase confidence
        adjustment = {
            "action": "increased_confidence",
            "reason": f"model_accuracy ({model_accuracy:.2f}) above threshold",
        }
    else:
        adjustment = {
            "action": "maintained",
            "reason": "model_accuracy within acceptable range",
        }
    
    # Save updated state
    save_relationship_state(state)
    
    return {
        "model_accuracy": round(model_accuracy, 3),
        "trust_error": round(trust_error, 3),
        "attunement_error": round(attunement_error, 3),
        "action_match": round(action_score, 3),
        "adjustment": adjustment,
        "simulation_id": simulation_results.get("simulation_id", "unknown"),
    }


def predict_with_feedback(session_id: str, current_metrics: dict) -> dict:
    """
    Make TACTI predictions with learned feedback adjustments.
    
    Uses historical feedback to bias predictions.
    """
    state = load_relationship_state()
    session = state.get("sessions", {}).get(session_id, {})
    feedback = session.get("_oasis_feedback", {})
    
    # Base predictions from current metrics
    predicted_trust = current_metrics.get("trust_score", 0.5)
    predicted_attunement = current_metrics.get("attunement_index", 0.5)
    
    # Apply learned biases
    if feedback:
        trust_bias = feedback.get("trust_bias", 0)
        attunement_bias = feedback.get("attunement_bias", 0)
        
        # Adjust predictions
        predicted_trust = max(0, min(1, predicted_trust - trust_bias * 0.5))
        predicted_attunement = max(0, min(1, predicted_attunement - attunement_bias * 0.5))
    
    simulation_count = feedback.get("simulation_count", 0)
    confidence = min(0.95, 0.5 + (simulation_count * 0.05))  # Increase with more data
    
    return {
        "session_id": session_id,
        "predicted_trust": round(predicted_trust, 3),
        "predicted_attunement": round(predicted_attunement, 3),
        "confidence": confidence,
        "simulations_used": simulation_count,
        "feedback_available": bool(feedback),
    }


def run_what_if_simulation(session_id: str, intervention: dict) -> dict:
    """
    Run a 'what-if' scenario:
    Given current state + proposed intervention → predict outcome.
    
    Args:
        session_id: Session to simulate
        intervention: Dict with proposed changes (e.g., {"trust_delta": 0.1})
    
    Returns:
        Predicted outcome
    """
    state = load_relationship_state()
    session = state.get("sessions", {}).get(session_id, {})
    
    current_trust = session.get("trust_score", 0.5)
    current_attunement = session.get("attunement_index", 0.5)
    
    # Apply intervention
    trust_delta = intervention.get("trust_delta", 0)
    attunement_delta = intervention.get("attunement_delta", 0)
    
    predicted_trust = max(0, min(1, current_trust + trust_delta))
    predicted_attunement = max(0, min(1, current_attunement + attunement_delta))
    
    # Get feedback adjustments
    feedback = session.get("_oasis_feedback", {})
    if feedback:
        trust_bias = feedback.get("trust_bias", 0)
        attunement_bias = feedback.get("attunement_bias", 0)
        
        # Apply learned corrections
        predicted_trust = max(0, min(1, predicted_trust - trust_bias * 0.3))
        predicted_attunement = max(0, min(1, predicted_attunement - attunement_bias * 0.3))
    
    return {
        "session_id": session_id,
        "current_trust": current_trust,
        "current_attunement": current_attunement,
        "intervention": intervention,
        "predicted_trust": round(predicted_trust, 3),
        "predicted_attunement": round(predicted_attunement, 3),
        "feedback_adjusted": bool(feedback),
    }


def test_feedback_loop() -> dict:
    """Run a test feedback loop with synthetic data."""
    
    # Simulate a prediction + actual outcome
    test_results = {
        "simulation_id": "test_" + hashlib.md5(str(datetime.now()).encode()).hexdigest()[:8],
        "session_id": "test_session",
        "predicted_trust": 0.8,
        "actual_trust": 0.75,
        "predicted_attunement": 0.6,
        "actual_attunement": 0.65,
        "predicted_actions": ["LIKE_POST", "FOLLOW"],
        "actual_actions": ["LIKE_POST", "CREATE_COMMENT"],
    }
    
    result = apply_feedback_to_tacti(test_results, "test_session")
    
    # Now predict with feedback
    prediction = predict_with_feedback("test_session", {
        "trust_score": 0.7,
        "attunement_index": 0.6,
    })
    
    # Run what-if
    whatif = run_what_if_simulation("test_session", {
        "trust_delta": 0.1,
        "attunement_delta": 0.05,
    })
    
    return {
        "feedback_result": result,
        "prediction_with_feedback": prediction,
        "what_if": whatif,
    }


def main():
    parser = argparse.ArgumentParser(description="TACTI ← OASIS Feedback Loop")
    parser.add_argument("--simulation-results", type=Path, 
                        help="Path to JSON file with simulation results")
    parser.add_argument("--session-id", type=str, default="default",
                        help="Session ID to update")
    parser.add_argument("--predicted-trust", type=float,
                        help="Predicted trust score (0-1)")
    parser.add_argument("--actual-trust", type=float,
                        help="Actual trust score after simulation (0-1)")
    parser.add_argument("--predicted-attunement", type=float,
                        help="Predicted attunement (0-1)")
    parser.add_argument("--actual-attunement", type=float,
                        help="Actual attunement after simulation (0-1)")
    parser.add_argument("--predict", action="store_true",
                        help="Make prediction with feedback")
    parser.add_argument("--what-if", type=str,
                        help="Run what-if: --what-if 'trust_delta=0.1,attunement=0.05'")
    parser.add_argument("--test", action="store_true",
                        help="Run test feedback loop")
    
    args = parser.parse_args()
    
    if args.test:
        results = test_feedback_loop()
        print("\n=== TACTI ← OASIS Feedback Loop Test ===")
        print(f"\nFeedback Result:")
        print(f"  Model accuracy: {results['feedback_result']['model_accuracy']}")
        print(f"  Trust error: {results['feedback_result']['trust_error']}")
        print(f"  Adjustment: {results['feedback_result']['adjustment']['action']}")
        
        print(f"\nPrediction with Feedback:")
        print(f"  Predicted trust: {results['prediction_with_feedback']['predicted_trust']}")
        print(f"  Confidence: {results['prediction_with_feedback']['confidence']}")
        
        print(f"\nWhat-If Scenario:")
        print(f"  Intervention: {results['what_if']['intervention']}")
        print(f"  Predicted trust: {results['what_if']['predicted_trust']}")
        return
    
    if args.simulation_results:
        with open(args.simulation_results) as f:
            results = json.load(f)
        result = apply_feedback_to_tacti(results, args.session_id)
        print(f"\n=== Feedback Applied ===")
        print(f"Model accuracy: {result['model_accuracy']}")
        print(f"Adjustment: {result['adjustment']['action']}")
        return
    
    if args.predicted_trust is not None and args.actual_trust is not None:
        results = {
            "simulation_id": "cli_" + datetime.now().strftime("%Y%m%d%H%M%S"),
            "session_id": args.session_id,
            "predicted_trust": args.predicted_trust,
            "actual_trust": args.actual_trust,
            "predicted_attunement": args.predicted_attunement or 0.5,
            "actual_attunement": args.actual_attunement or 0.5,
            "predicted_actions": [],
            "actual_actions": [],
        }
        result = apply_feedback_to_tacti(results, args.session_id)
        print(f"\n=== Feedback Applied ===")
        print(f"Model accuracy: {result['model_accuracy']}")
        return
    
    if args.predict:
        prediction = predict_with_feedback(args.session_id, {
            "trust_score": 0.5,
            "attunement_index": 0.5,
        })
        print(f"\n=== Prediction with Feedback ===")
        print(json.dumps(prediction, indent=2))
        return
    
    if args.what_if:
        # Parse what-if args
        params = {}
        for part in args.what_if.split(","):
            k, v = part.split("=")
            params[k.strip()] = float(v.strip())
        
        whatif = run_what_if_simulation(args.session_id, params)
        print(f"\n=== What-If Simulation ===")
        print(json.dumps(whatif, indent=2))
        return
    
    parser.print_help()


if __name__ == "__main__":
    main()
