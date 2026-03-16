#!/usr/bin/env python3
"""
Dream Consolidation - Nightly replay and analysis of day's events
"""
import json
from pathlib import Path
from datetime import datetime, timedelta, timezone
from collections import Counter

REPO_ROOT = Path(__file__).resolve().parents[2]


def _parse_ts(ts_str: str) -> datetime | None:
    """Parse ISO-8601 timestamp string to aware datetime. Returns None on failure."""
    if not ts_str:
        return None
    try:
        # Handle both Z suffix and +00:00
        normalized = ts_str.replace("Z", "+00:00")
        return datetime.fromisoformat(normalized)
    except (ValueError, AttributeError):
        return None


def analyze_day(window_hours: int = 24):
    """Analyze the last window_hours of events from tacti_cr events.jsonl.

    Only processes events whose 'ts' timestamp falls within the window.
    Events without a parseable timestamp are excluded (not included in
    total_events) so that stale historical data does not pollute daily
    dream summaries.
    """
    events_file = REPO_ROOT / "workspace" / "state" / "tacti_cr" / "events.jsonl"
    if not events_file.exists():
        return {"error": "No events file"}

    cutoff = datetime.now(timezone.utc) - timedelta(hours=window_hours)

    # Load events within the time window
    events = []
    skipped_stale = 0
    skipped_parse_error = 0
    with open(events_file, encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                e = json.loads(line)
            except Exception:
                skipped_parse_error += 1
                continue
            ts = _parse_ts(e.get("ts", ""))
            if ts is None:
                skipped_parse_error += 1
                continue
            if ts < cutoff:
                skipped_stale += 1
                continue
            events.append(e)

    # Analyze patterns — categorize by event type name rather than full serialized string
    event_types = Counter(e.get("event", e.get("type", "unknown")) for e in events)

    _SUCCESS_FRAGMENTS = ("accept", "approved", "success", "pass")
    _FAILURE_FRAGMENTS = ("quarantin", "fail", "reject", "error")

    def _categorize(etype: str) -> str:
        el = etype.lower()
        if any(f in el for f in _SUCCESS_FRAGMENTS):
            return "success"
        if any(f in el for f in _FAILURE_FRAGMENTS):
            return "failure"
        return "neutral"

    success_count = sum(c for et, c in event_types.items() if _categorize(et) == "success")
    failure_count = sum(c for et, c in event_types.items() if _categorize(et) == "failure")

    # Build a readable pattern summary for MEMORY.md ingest
    top_types = event_types.most_common(6)
    if top_types:
        immune_accepted = event_types.get("tacti_cr.semantic_immune.accepted", 0)
        immune_quarantined = event_types.get("tacti_cr.semantic_immune.quarantined", 0)
        immune_total = immune_accepted + immune_quarantined
        acceptance_str = (
            f"{immune_accepted}/{immune_total} immune_accepted"
            if immune_total > 0
            else ""
        )
        prefetch = event_types.get("tacti_cr.prefetch.hit_rate", 0)
        top_str = ", ".join(f"{et}×{c}" for et, c in top_types[:4])
        parts = [f"top_events=[{top_str}]"]
        if acceptance_str:
            parts.append(acceptance_str)
        if prefetch:
            parts.append(f"prefetch_samples={prefetch}")
        patterns = "; ".join(parts)
    else:
        patterns = "no events in window"

    return {
        "total_events": len(events),
        "event_types": dict(event_types),
        "successes": success_count,
        "failures": failure_count,
        "window_hours": window_hours,
        "cutoff_utc": cutoff.isoformat().replace("+00:00", "Z"),
        "skipped_stale": skipped_stale,
        "patterns": patterns,
    }

def dream_consolidation():
    """Run nightly consolidation."""
    analysis = analyze_day()
    
    # Save to dream log
    dream_file = REPO_ROOT / "workspace" / "state" / "dreams" / f"{datetime.now(timezone.utc).date()}.json"
    dream_file.parent.mkdir(parents=True, exist_ok=True)
    
    with open(dream_file, "w") as f:
        json.dump(analysis, f, indent=2)
    
    print(f"Dream consolidation: {analysis['total_events']} events analyzed")
    return analysis

if __name__ == "__main__":
    dream_consolidation()
