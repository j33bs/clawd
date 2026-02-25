from __future__ import annotations

import hashlib
from collections import Counter
from datetime import datetime
from typing import Any, Dict, List, Optional

try:
    from ._common import append_jsonl, memory_ext_enabled, runtime_dir, utc_now_iso
except ImportError:  # pragma: no cover
    from _common import append_jsonl, memory_ext_enabled, runtime_dir, utc_now_iso

def _meta_loop_log():
    return runtime_dir("memory_ext", "meta_learning_loops.jsonl")


class FailureGuard:
    def __init__(self) -> None:
        self.guardrails: List[Dict[str, str]] = []

    def add_guardrail(self, failure_event: str, lesson: str) -> str:
        raw = "{evt}:{les}".format(evt=failure_event, les=lesson)
        guardrail_id = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]
        self.guardrails.append({"id": guardrail_id, "failure_event": failure_event, "lesson": lesson})
        return guardrail_id

    def check_guardrails(self, action: str) -> Dict[str, Any]:
        text = str(action or "").lower()
        triggered = []
        for g in self.guardrails:
            token = str(g.get("failure_event", "")).lower()
            if token and token in text:
                triggered.append(g.get("id", ""))
        return {"allowed": len(triggered) == 0, "guards_triggered": triggered}


class PredictionCalibrator:
    def __init__(self) -> None:
        self.records: List[Dict[str, float]] = []

    def log_prediction(self, prediction: float, expected_outcome: float) -> None:
        self.records.append(
            {
                "prediction": float(max(0.0, min(1.0, prediction))),
                "expected_outcome": float(max(0.0, min(1.0, expected_outcome))),
            }
        )

    def get_calibration_score(self) -> float:
        if not self.records:
            return 1.0
        err = [abs(r["prediction"] - r["expected_outcome"]) for r in self.records]
        return max(0.0, min(1.0, 1.0 - (sum(err) / float(len(err)))))

    def calibrate_confidence(self, raw_confidence: float) -> float:
        raw = float(max(0.0, min(1.0, raw_confidence)))
        return round(raw * self.get_calibration_score(), 6)


class FrictionSignal:
    def __init__(self) -> None:
        self.events: List[Dict[str, str]] = []

    def log_friction(self, context: str, resistance_type: str, response: str) -> None:
        self.events.append(
            {
                "context": str(context),
                "resistance_type": str(resistance_type),
                "response": str(response),
            }
        )

    def extract_signal(self) -> Dict[str, str]:
        if not self.events:
            return {"pattern": "none", "recommendation": "observe"}
        counts = Counter(e.get("resistance_type", "unknown") for e in self.events)
        pattern, _ = counts.most_common(1)[0]
        return {"pattern": pattern, "recommendation": "adjust_for_{0}".format(pattern)}


class MetaLoop:
    def __init__(self) -> None:
        self.failure_guard = FailureGuard()
        self.calibrator = PredictionCalibrator()
        self.friction = FrictionSignal()

    def process_interaction(self, outcome: Dict[str, Any], now: Optional[datetime] = None) -> Dict[str, Any]:
        updates: List[str] = []
        if bool(outcome.get("failed")):
            guardrail_id = self.failure_guard.add_guardrail(
                str(outcome.get("failure_event", "failure")),
                str(outcome.get("lesson", "tighten_check")),
            )
            updates.append("guardrail:{0}".format(guardrail_id))

        prediction = float(outcome.get("prediction", 0.5))
        observed = float(outcome.get("observed", 0.5))
        self.calibrator.log_prediction(prediction, observed)
        updates.append("calibration")

        if outcome.get("friction_type"):
            self.friction.log_friction(
                str(outcome.get("context", "")),
                str(outcome.get("friction_type", "")),
                str(outcome.get("response", "")),
            )
            updates.append("friction")

        signal = self.friction.extract_signal()
        payload: Dict[str, Any] = {
            "timestamp_utc": utc_now_iso(now),
            "updated": updates,
            "signals": [signal],
            "calibration_score": self.calibrator.get_calibration_score(),
        }
        if memory_ext_enabled():
            append_jsonl(_meta_loop_log(), payload)
        return payload


__all__ = ["FailureGuard", "PredictionCalibrator", "FrictionSignal", "MetaLoop"]
