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
from .repair import RepairAction, RepairEngine
from .temporal import TemporalEntry, TemporalMemory

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
    "RepairAction",
    "RepairEngine",
    "TemporalEntry",
    "TemporalMemory",
]
