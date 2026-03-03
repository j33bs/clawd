from __future__ import annotations

import json
import os
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Tuple


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


class PredictionError:
    @staticmethod
    def compute(predicted: Dict[str, float], observed: Dict[str, float]) -> float:
        shared = [key for key in predicted.keys() if key in observed]
        if not shared:
            return 1.0
        total = 0.0
        for key in shared:
            total += abs(float(predicted[key]) - float(observed[key]))
        return total / len(shared)


@dataclass
class PreferenceModel:
    """
    Lightweight preference priors updated by feedback and outcomes.
    """

    priors: Dict[str, float] = field(
        default_factory=lambda: {
            "verbosity_preference": 0.5,
            "format_preference": 0.5,
            "tool_use_tolerance": 0.5,
            "correction_tolerance": 0.5,
        }
    )
    interactions: int = 0
    learning_rate: float = 0.2
    last_prediction: Dict[str, float] = field(default_factory=dict)

    def predict(self, context: Dict[str, Any] | None) -> Tuple[Dict[str, float], float]:
        context = context or {}
        params = dict(self.priors)
        text = str(context.get("input_text", "") or "").lower()
        if "brief" in text or "concise" in text:
            params["verbosity_preference"] = _clamp01(params["verbosity_preference"] - 0.15)
        if "detailed" in text or "deep" in text:
            params["verbosity_preference"] = _clamp01(params["verbosity_preference"] + 0.2)
        if context.get("requires_tools") is True:
            params["tool_use_tolerance"] = _clamp01(params["tool_use_tolerance"] + 0.15)
        if context.get("strict_format") is True:
            params["format_preference"] = _clamp01(params["format_preference"] + 0.2)

        self.last_prediction = dict(params)
        confidence = min(0.95, 0.25 + (self.interactions * 0.05))
        return params, confidence

    def update(self, feedback: Dict[str, Any] | None, observed_outcome: Dict[str, Any] | None) -> Dict[str, Any]:
        feedback = feedback or {}
        observed_outcome = observed_outcome or {}

        observed = {
            "verbosity_preference": _clamp01(float(observed_outcome.get("verbosity_score", self.priors["verbosity_preference"]))),
            "format_preference": _clamp01(float(observed_outcome.get("format_score", self.priors["format_preference"]))),
            "tool_use_tolerance": _clamp01(float(observed_outcome.get("tool_score", self.priors["tool_use_tolerance"]))),
            "correction_tolerance": _clamp01(float(observed_outcome.get("correction_score", self.priors["correction_tolerance"]))),
        }
        pred = dict(self.last_prediction or self.priors)
        error = PredictionError.compute(pred, observed)

        liked = feedback.get("liked")
        for key in list(self.priors.keys()):
            target = observed[key]
            if key in feedback and isinstance(feedback[key], (int, float)):
                target = _clamp01(float(feedback[key]))
            elif liked is True:
                target = _clamp01((pred.get(key, self.priors[key]) + target) / 2.0 + 0.08)
            elif liked is False:
                target = _clamp01(target * 0.7)

            current = self.priors[key]
            self.priors[key] = _clamp01(current + (self.learning_rate * (target - current)))

        self.interactions += 1
        return {
            "ok": True,
            "prediction_error": error,
            "priors": dict(self.priors),
            "interactions": self.interactions,
        }

    def snapshot(self) -> Dict[str, Any]:
        return {
            "version": 1,
            "priors": dict(self.priors),
            "interactions": self.interactions,
            "learning_rate": self.learning_rate,
            "last_prediction": dict(self.last_prediction),
        }

    @classmethod
    def load(cls, payload: Dict[str, Any]) -> "PreferenceModel":
        model = cls()
        priors = payload.get("priors", {})
        if isinstance(priors, dict):
            for key in model.priors:
                if key in priors:
                    model.priors[key] = _clamp01(float(priors[key]))
        model.interactions = int(payload.get("interactions", 0))
        model.learning_rate = float(payload.get("learning_rate", 0.2))
        last = payload.get("last_prediction", {})
        if isinstance(last, dict):
            model.last_prediction = {k: _clamp01(float(v)) for k, v in last.items() if k in model.priors}
        return model

    @classmethod
    def load_path(cls, path: Path) -> "PreferenceModel":
        if not path.exists():
            return cls()
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return cls()
        if not isinstance(payload, dict):
            return cls()
        return cls.load(payload)

    def save_path(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.snapshot(), indent=2) + "\n", encoding="utf-8")


def counterfactual_replay_enabled() -> bool:
    value = str(
        os.environ.get(
            "OPENCLAW_AIF_COUNTERFACTUAL",
            os.environ.get("OPENCLAW_COUNTERFACTUAL_REPLAY", "0"),
        )
    ).strip().lower()
    return value in {"1", "true", "yes", "on"}


def generate_counterfactual_routings(event: Dict[str, Any], candidates: list[str] | None = None, max_items: int = 3) -> list[Dict[str, Any]]:
    """
    Deterministic heuristic alternatives for routing analysis without model calls.
    """
    if not counterfactual_replay_enabled():
        return []

    row = dict(event or {})
    provider = str(row.get("provider") or "")
    base_reason = str(row.get("reason_code") or "unknown")
    options = [str(x) for x in (candidates or row.get("candidates") or []) if str(x)]
    if provider and provider not in options:
        options.append(provider)
    options = sorted(dict.fromkeys(options))
    if not options:
        options = ["local_vllm_assistant", "groq", "ollama"]

    out: list[Dict[str, Any]] = []
    for idx, choice in enumerate(options[: max(1, int(max_items))]):
        latency_penalty = 0.1 if choice.startswith("local_") else 0.25
        failure_penalty = 0.35 if base_reason not in {"success", "none"} else 0.05
        score = max(0.0, min(1.0, 1.0 - latency_penalty - failure_penalty - (idx * 0.07)))
        out.append(
            {
                "provider": choice,
                "estimated_success": round(score, 6),
                "reason": f"counterfactual_from_{base_reason}",
            }
        )
    return out


def replay_counterfactuals(event: Dict[str, Any], k: int = 3, rng_seed: int | None = None) -> Dict[str, Any]:
    """
    Generate deterministic counterfactual routing alternatives and apply
    low-impact phantom updates to a free-energy landscape.
    """
    if not counterfactual_replay_enabled():
        return {"ok": True, "enabled": False, "counterfactuals": [], "updates": [], "free_energy": {}}

    row = dict(event or {})
    chosen = str(row.get("provider") or "")
    candidates = [str(x) for x in (row.get("candidates") or []) if str(x)]
    if chosen and chosen not in candidates:
        candidates.append(chosen)
    if not candidates:
        candidates = ["local_vllm_assistant", "groq", "ollama"]
    candidates = sorted(dict.fromkeys(candidates))
    alternatives = [c for c in candidates if c != chosen] or candidates

    seed = int(rng_seed) if rng_seed is not None else int(sum(ord(ch) for ch in "|".join(alternatives + [chosen])))
    rng = random.Random(seed)
    rng.shuffle(alternatives)
    selected = alternatives[: max(1, min(3, int(k)))]

    prior_scores = row.get("provider_priors") if isinstance(row.get("provider_priors"), dict) else {}
    free_energy = {
        str(key): float(value)
        for key, value in (row.get("free_energy") or {}).items()
        if isinstance(value, (int, float))
    }
    lr = float(row.get("learning_rate", 0.2) or 0.2) * 0.2
    updates = []
    counterfactuals = []
    for idx, provider in enumerate(selected):
        prior = float(prior_scores.get(provider, 0.5) or 0.5)
        novelty_penalty = 0.06 * idx
        predicted = max(0.0, min(1.0, prior - novelty_penalty))
        counterfactuals.append(
            {
                "provider": provider,
                "estimated_success": round(predicted, 6),
                "reason": "counterfactual_replay",
            }
        )
        prev = float(free_energy.get(provider, 0.5))
        next_val = max(0.0, min(2.0, prev + (lr * (1.0 - predicted))))
        free_energy[provider] = round(next_val, 6)
        updates.append({"provider": provider, "from": round(prev, 6), "to": round(next_val, 6), "lr": round(lr, 6)})

    return {
        "ok": True,
        "enabled": True,
        "counterfactuals": counterfactuals,
        "updates": updates,
        "free_energy": free_energy,
        "seed": seed,
    }
