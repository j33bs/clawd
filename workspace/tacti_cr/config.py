"""Configuration defaults for TACTI(C)-R modules."""

from dataclasses import dataclass, field
from typing import Dict


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
