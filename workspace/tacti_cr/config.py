"""Configuration defaults and feature flags for TACTI(C)-R modules."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Tuple


@dataclass(frozen=True)
class ArousalThresholds:
    low_max: float = 0.33
    medium_max: float = 0.66


@dataclass(frozen=True)
class ComputeTierSettings:
    model_tier: str
    timeout_multiplier: float
    context_budget: int
    allow_paid: bool


@dataclass(frozen=True)
class CollapseSettings:
    degraded_threshold: int = 3
    collapse_threshold: int = 6
    window_size: int = 10


@dataclass(frozen=True)
class TemporalSettings:
    retention_days: int = 90
    default_decay_rate: float = 0.05


@dataclass(frozen=True)
class RepairSettings:
    max_retry_attempts: int = 2
    fallback_enabled: bool = True


@dataclass(frozen=True)
class TactiCRConfig:
    arousal_thresholds: ArousalThresholds = field(default_factory=ArousalThresholds)
    compute_plans: Dict[str, ComputeTierSettings] = field(
        default_factory=lambda: {
            "low": ComputeTierSettings("fast", 1.0, 2000, False),
            "medium": ComputeTierSettings("balanced", 1.4, 4000, False),
            "high": ComputeTierSettings("premium", 2.0, 8000, True),
        }
    )
    collapse: CollapseSettings = field(default_factory=CollapseSettings)
    temporal: TemporalSettings = field(default_factory=TemporalSettings)
    repair: RepairSettings = field(default_factory=RepairSettings)


DEFAULT_CONFIG = TactiCRConfig()


COMPLEXITY_KEYWORDS = (
    "analyze",
    "audit",
    "architecture",
    "debug",
    "failure",
    "incident",
    "security",
    "traceback",
    "regression",
    "integration",
    "routing",
    "verify",
    "cross-timescale",
)


FEATURE_FLAGS = {
    "master": "TACTI_CR_ENABLE",
    "arousal_osc": "TACTI_CR_AROUSAL_OSC",
    "dream_consolidation": "TACTI_CR_DREAM_CONSOLIDATION",
    "semantic_immune": "TACTI_CR_SEMANTIC_IMMUNE",
    "stigmergy": "TACTI_CR_STIGMERGY",
    "expression_router": "TACTI_CR_EXPRESSION_ROUTER",
    "prefetch": "TACTI_CR_PREFETCH",
    "mirror": "TACTI_CR_MIRROR",
    "valence": "TACTI_CR_VALENCE",
    "temporal_watchdog": "TACTI_CR_TEMPORAL_WATCHDOG",
    "source_ui_heatmap": "SOURCE_UI_HEATMAP",
    "gpu_telemetry": "TACTI_CR_GPU_TELEMETRY",
}


def _repo_root() -> Path:
    start = Path(__file__).resolve()
    for candidate in [start.parent, *start.parents]:
        if (candidate / ".git").exists():
            return candidate
    return Path.cwd()


def _policy_path() -> Path:
    env = os.environ.get("OPENCLAW_ROOT", "").strip()
    if env:
        return Path(env) / "workspace" / "policy" / "llm_policy.json"
    return _repo_root() / "workspace" / "policy" / "llm_policy.json"


def _parse_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    text = str(value or "").strip().lower()
    return text in {"1", "true", "yes", "on", "enabled"}


def _policy_knobs() -> Dict[str, Any]:
    path = _policy_path()
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    if not isinstance(raw, dict):
        return {}
    tacti_cfg = raw.get("tacti_cr")
    if isinstance(tacti_cfg, dict):
        return tacti_cfg
    routing_cfg = raw.get("routing", {})
    if isinstance(routing_cfg, dict) and isinstance(routing_cfg.get("tacti_cr"), dict):
        return routing_cfg["tacti_cr"]
    return {}


def _knob(name: str, default: Any) -> Any:
    env_name = f"TACTI_CR_{name.upper()}"
    if env_name in os.environ:
        return os.environ[env_name]
    knobs = _policy_knobs()
    return knobs.get(name, default)


def is_enabled(feature_name: str) -> bool:
    """Feature switch check: master gate AND sub-feature gate."""
    master_env = FEATURE_FLAGS["master"]
    if not _parse_bool(os.environ.get(master_env, "0")):
        return False

    if feature_name in {"TACTI_CR_ENABLE", "master"}:
        return True

    flag_name = FEATURE_FLAGS.get(feature_name, feature_name)
    if flag_name in FEATURE_FLAGS.values():
        return _parse_bool(os.environ.get(flag_name, "0"))

    policy_flags = _policy_knobs().get("flags", {})
    if isinstance(policy_flags, dict):
        return _parse_bool(policy_flags.get(feature_name, False))
    return False


def get_float(name: str, default: float, clamp: Tuple[float, float] | None = None) -> float:
    raw = _knob(name, default)
    try:
        value = float(raw)
    except Exception:
        value = float(default)
    if clamp:
        low, high = clamp
        value = max(float(low), min(float(high), value))
    return value


def get_int(name: str, default: int, clamp: Tuple[int, int] | None = None) -> int:
    raw = _knob(name, default)
    try:
        value = int(raw)
    except Exception:
        value = int(default)
    if clamp:
        low, high = clamp
        value = max(int(low), min(int(high), value))
    return value


def get_time_zone(default: str = "Australia/Brisbane") -> str:
    raw = _knob("time_zone", default)
    text = str(raw or "").strip()
    return text if text else default
