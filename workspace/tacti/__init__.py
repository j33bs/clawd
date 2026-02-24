"""TACTI(C)-R technical modules."""

from .arousal import ArousalLevel, ArousalState, ComputePlan, detect_arousal, get_compute_allocation, recommend_tier
from .collapse import CollapseDetector, HealthState
from .cross_timescale import (
    CrossTimescaleController,
    CrossTimescaleResult,
    DeliberativeDecision,
    MetaDecision,
    ReflexDecision,
)
from .hivemind_bridge import MemoryEntry, hivemind_query, hivemind_store
from .external_memory import append_event, read_events, healthcheck
from .efe_calculator import evaluate
from .curiosity import epistemic_value
from .active_inference_agent import ActiveInferenceAgent
from .repair import RepairAction, RepairEngine
from .temporal import TemporalEntry, TemporalMemory
from .arousal_oscillator import ArousalOscillator
from .expression import compute_expression
from .dream_consolidation import run_consolidation
from .semantic_immune import assess_content, approve_quarantine
from .mirror import update_from_event, behavioral_fingerprint
from .valence import current_valence, update_valence, routing_bias
from .prefetch import PrefetchCache, predict_topics, prefetch_context
from .temporal_watchdog import update_beacon, detect_temporal_drift, temporal_reset_event

__all__ = [
    "ArousalLevel",
    "ArousalState",
    "ComputePlan",
    "detect_arousal",
    "get_compute_allocation",
    "recommend_tier",
    "CollapseDetector",
    "HealthState",
    "CrossTimescaleController",
    "CrossTimescaleResult",
    "DeliberativeDecision",
    "MetaDecision",
    "ReflexDecision",
    "MemoryEntry",
    "hivemind_query",
    "hivemind_store",
    "append_event",
    "read_events",
    "healthcheck",
    "evaluate",
    "epistemic_value",
    "ActiveInferenceAgent",
    "RepairAction",
    "RepairEngine",
    "TemporalEntry",
    "TemporalMemory",
    "ArousalOscillator",
    "compute_expression",
    "run_consolidation",
    "assess_content",
    "approve_quarantine",
    "update_from_event",
    "behavioral_fingerprint",
    "current_valence",
    "update_valence",
    "routing_bias",
    "PrefetchCache",
    "predict_topics",
    "prefetch_context",
    "update_beacon",
    "detect_temporal_drift",
    "temporal_reset_event",
]
