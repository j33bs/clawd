"""Canonical Novel-10 fixture event contract and flag defaults."""

from __future__ import annotations

from pathlib import Path

EXPECTED_EVENTS = {
    "arousal": ["tacti_cr.arousal_multiplier"],
    "expression": ["tacti_cr.expression_profile"],
    "temporal_watchdog": ["tacti_cr.temporal.drift_detected", "tacti_cr.temporal_watchdog.temporal_reset"],
    "dream_consolidation": ["tacti_cr.dream.consolidation_started", "tacti_cr.dream.report_written"],
    "semantic_immune": ["tacti_cr.semantic_immune.accepted", "tacti_cr.semantic_immune.quarantined"],
    "stigmergy": ["tacti_cr.stigmergy.mark_deposited", "tacti_cr.stigmergy.query"],
    "prefetch": ["tacti_cr.prefetch.predicted_topics", "tacti_cr.prefetch.cache_put"],
    "mirror": ["tacti_cr.mirror.updated"],
    "valence": ["tacti_cr.valence.updated", "tacti_cr.valence_bias"],
    "trail_heatmap": ["tacti_cr.trails.topn_served"],
}

FEATURE_FLAGS = {
    "TACTI_CR_ENABLE": "0",
    "TACTI_CR_AROUSAL_OSC": "0",
    "TACTI_CR_DREAM_CONSOLIDATION": "0",
    "TACTI_CR_SEMANTIC_IMMUNE": "0",
    "TACTI_CR_STIGMERGY": "0",
    "TACTI_CR_EXPRESSION_ROUTER": "0",
    "TACTI_CR_PREFETCH": "0",
    "TACTI_CR_MIRROR": "0",
    "TACTI_CR_VALENCE": "0",
    "TACTI_CR_TEMPORAL_WATCHDOG": "0",
    "SOURCE_UI_HEATMAP": "0",
}


def required_for_fixture(*, repo_root: Path | None = None, include_ui: bool = False) -> dict[str, list[str]]:
    required = {k: list(v) for k, v in EXPECTED_EVENTS.items() if k != "trail_heatmap"}
    if include_ui:
        root = Path(repo_root or Path(__file__).resolve().parents[2])
        if (root / "workspace" / "source-ui").exists():
            required["trail_heatmap"] = list(EXPECTED_EVENTS["trail_heatmap"])
    return required


__all__ = ["EXPECTED_EVENTS", "FEATURE_FLAGS", "required_for_fixture"]
