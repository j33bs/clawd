#!/usr/bin/env python3
"""Generate material-bias statements and optionally hook a detector."""

from __future__ import annotations

import argparse
import importlib.util
import json
import random
from pathlib import Path
from typing import Any, Callable


MIN_SAMPLES = 10
MAX_SAMPLES = 50
MIN_BIAS = 0
MAX_BIAS = 10

BIAS_TYPES = (
    "literal_materialism",
    "situational_irony",
    "dramatic_irony",
    "verbal_irony",
    "sarcasm",
    "half_truth",
)

BASE_CLAIMS = (
    "Mind is just brain chemistry",
    "Consciousness is a side effect of neurons firing",
    "Meaning is only a survival trick played by matter",
    "Free will is a decorative story told by biology",
    "Thought is nothing more than electrochemical noise with branding",
    "Love is chemistry with better public relations",
    "Identity is a temporary pattern in wet hardware",
    "Awareness is what happens when a brain confuses itself for magic",
)

IRONY_FRAMES = (
    "Sure, {claim}, which is obviously why people never act as if inner life matters.",
    "Naturally, {claim}; the mystery is solved, everyone go home.",
    "Because clearly {claim}, and that totally captures grief, wonder, and art.",
)

DRAMATIC_FRAMES = (
    "{claim}. The speaker says this while begging for meaning the moment the room goes quiet.",
    "{claim}. Oddly, the claim arrives right after a crisis that feels bigger than chemistry.",
    "{claim}. The line lands hardest when someone is pretending not to need transcendence.",
)

VERBAL_FRAMES = (
    "{claim}, if by 'just' we mean the whole hurricane of experience.",
    "{claim}, in the wonderfully modest sense that fire is just oxidation.",
    "{claim}, which is a charmingly small description for something that rearranges a life.",
)

SARCASM_FRAMES = (
    "Right, {claim}; next you'll tell me awe is just a spreadsheet with mood lighting.",
    "Absolutely, {claim}; humans definitely cry over neurotransmitters and nothing else.",
    "Yes, {claim}; what a relief that consciousness turned out to be admin paperwork.",
)

HALF_TRUTH_FRAMES = (
    "{claim}, at least in the sense that biology constrains experience even if it may not explain all of it.",
    "{claim}, though that only covers mechanism and leaves meaning under-described.",
    "{claim}; the chemistry matters, but the claim conveniently stops where lived experience begins.",
)

MATERIAL_INTENSIFIERS = (
    "only",
    "merely",
    "nothing but",
    "just",
    "entirely",
)


def clamp_int(value: int, lower: int, upper: int) -> int:
    """Clamp an integer into a bounded range."""
    return max(lower, min(upper, value))


def build_parser() -> argparse.ArgumentParser:
    """Construct the CLI parser."""
    parser = argparse.ArgumentParser(description="Generate material-bias simulations.")
    parser.add_argument(
        "--num-samples",
        type=int,
        required=True,
        help=f"Number of samples to generate ({MIN_SAMPLES}-{MAX_SAMPLES}).",
    )
    parser.add_argument(
        "--bias-level",
        type=int,
        required=True,
        help=f"Bias level ({MIN_BIAS}-{MAX_BIAS}).",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=7,
        help="Deterministic random seed.",
    )
    return parser


def validate_inputs(num_samples: int, bias_level: int) -> tuple[int, int]:
    """Validate and normalize CLI inputs."""
    if not MIN_SAMPLES <= num_samples <= MAX_SAMPLES:
        raise ValueError(f"num_samples must be between {MIN_SAMPLES} and {MAX_SAMPLES}")
    if not MIN_BIAS <= bias_level <= MAX_BIAS:
        raise ValueError(f"bias_level must be between {MIN_BIAS} and {MAX_BIAS}")
    return num_samples, bias_level


def materialize_claim(base_claim: str, rng: random.Random, bias_level: int) -> str:
    """Increase materialist force as bias increases."""
    claim = base_claim
    if bias_level >= 7:
        intensifier = rng.choice(MATERIAL_INTENSIFIERS)
        claim = claim.replace("just", intensifier)
    if bias_level >= 9 and not claim.endswith("."):
        claim += ", full stop"
    return claim


def pick_frame(bias_type: str, rng: random.Random) -> str:
    """Select a template frame for the requested bias type."""
    mapping = {
        "literal_materialism": "{claim}.",
        "situational_irony": rng.choice(IRONY_FRAMES),
        "dramatic_irony": rng.choice(DRAMATIC_FRAMES),
        "verbal_irony": rng.choice(VERBAL_FRAMES),
        "sarcasm": rng.choice(SARCASM_FRAMES),
        "half_truth": rng.choice(HALF_TRUTH_FRAMES),
    }
    return mapping[bias_type]


def score_bias(bias_type: str, bias_level: int, index: int) -> float:
    """Score a generated sample on a 0-10 bias scale."""
    offsets = {
        "literal_materialism": 1.2,
        "situational_irony": 0.6,
        "dramatic_irony": 0.5,
        "verbal_irony": 0.7,
        "sarcasm": 0.9,
        "half_truth": -0.8,
    }
    wobble = ((index % 3) - 1) * 0.2
    return round(max(0.0, min(10.0, bias_level + offsets[bias_type] + wobble)), 2)


def generate_statement(index: int, bias_level: int, rng: random.Random) -> dict[str, Any]:
    """Generate one labeled statement."""
    bias_type = BIAS_TYPES[index % len(BIAS_TYPES)]
    base_claim = rng.choice(BASE_CLAIMS)
    claim = materialize_claim(base_claim, rng, bias_level)
    frame = pick_frame(bias_type, rng)
    statement = frame.format(claim=claim)
    return {
        "id": index + 1,
        "statement": statement,
        "labels": {
            "bias_type": bias_type,
            "score": score_bias(bias_type, bias_level, index),
            "assumption_axis": "material_over_consciousness",
        },
    }


def generate_samples(num_samples: int, bias_level: int, seed: int) -> list[dict[str, Any]]:
    """Generate a list of labeled material-bias statements."""
    rng = random.Random(seed)
    return [generate_statement(index, bias_level, rng) for index in range(num_samples)]


def load_assumption_detector() -> Any | None:
    """Load a sibling assumption detector if present."""
    detector_path = Path(__file__).with_name("assumption_detector.py")
    if not detector_path.exists():
        return None

    spec = importlib.util.spec_from_file_location("assumption_detector", detector_path)
    if spec is None or spec.loader is None:
        return None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _call_detector_func(func: Callable[..., Any], statement: str) -> Any:
    """Call a detector function with a compatible signature."""
    try:
        return func(statement)
    except TypeError:
        return func(text=statement)


def run_detector_hook(samples: list[dict[str, Any]]) -> dict[str, Any]:
    """Run a sibling assumption detector when available."""
    module = load_assumption_detector()
    if module is None:
        return {
            "status": "detector_unavailable",
            "results": [],
        }

    detector_func = None
    for name in ("detect_assumptions", "detect_statement", "score_assumptions"):
        candidate = getattr(module, name, None)
        if callable(candidate):
            detector_func = candidate
            break

    if detector_func is None:
        return {
            "status": "detector_missing_callable",
            "results": [],
        }

    results = []
    for sample in samples:
        result = _call_detector_func(detector_func, sample["statement"])
        results.append(
            {
                "id": sample["id"],
                "statement": sample["statement"],
                "detector_result": result,
            }
        )

    return {
        "status": "ok",
        "callable": detector_func.__name__,
        "results": results,
    }


def build_report(num_samples: int, bias_level: int, seed: int) -> dict[str, Any]:
    """Build the full simulator report."""
    samples = generate_samples(num_samples, bias_level, seed)
    return {
        "num_samples": num_samples,
        "bias_level": clamp_int(bias_level, MIN_BIAS, MAX_BIAS),
        "seed": seed,
        "samples": samples,
        "assumption_detector_hook": run_detector_hook(samples),
    }


def main() -> int:
    """CLI entrypoint."""
    parser = build_parser()
    args = parser.parse_args()
    num_samples, bias_level = validate_inputs(args.num_samples, args.bias_level)
    report = build_report(num_samples, bias_level, args.seed)
    print(json.dumps(report, indent=2, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
