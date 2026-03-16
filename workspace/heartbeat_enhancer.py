#!/usr/bin/env python3
"""
Heartbeat Enhancer
Enhanced heartbeat checks using TACTI modules.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / "memory"))
sys.path.insert(0, str(Path(__file__).parent / "scripts"))
from memory_maintenance import assess_memory_health, consolidate_memory_fragments

def run_memory_consolidation(memory_dir: Path, output_path: Path, *, today=None, window_days: int = 3):
    """Run bounded memory consolidation for recent daily files."""
    return consolidate_memory_fragments(
        Path(memory_dir),
        Path(output_path),
        today=today,
        window_days=max(1, int(window_days)),
    )


def run_memory_health(memory_dir: Path, memory_md_path: Path, output_path: Path, *, today=None, recent_days: int = 7):
    """Assess recent memory-system health and persist the report."""
    return assess_memory_health(
        Path(memory_dir),
        Path(memory_md_path),
        Path(output_path),
        today=today,
        recent_days=max(1, int(recent_days)),
    )

def enhanced_heartbeat():
    """Run enhanced heartbeat with TACTI awareness."""
    checks = []

    try:
        from tacti_core import get_core

        core = get_core()

        # 1. Arousal state check
        arousal = core.get_arousal_state()
        checks.append(f"Arousal: {arousal['state']}")
        if arousal['state'] in ['overload', 'recovering']:
            checks.append("⚠️ Consider context compaction")

        # 2. Relationship health check
        health = core.get_relationship_health()
        if health['trust'] < 0.7:
            checks.append(f"⚠️ Trust low: {health['trust']:.2f}")

        # 3. Pattern detection
        patterns = core.find_patterns(min_freq=2)
        if patterns:
            checks.append(f"Found {len(patterns)} new patterns")
    except Exception as exc:  # noqa: BLE001
        checks.append(f"⚠️ TACTI core unavailable: {exc.__class__.__name__}")
    
    # 4. Memory size check
    memory_path = Path("MEMORY.md")
    if memory_path.exists():
        lines = len(memory_path.read_text().splitlines())
        if lines > 180:
            checks.append(f"⚠️ MEMORY large: {lines} lines")

    # 5. Memory consolidation (merge fragmented notes across recent daily files)
    consolidation = run_memory_consolidation(
        Path("memory"),
        Path("workspace/state_runtime/memory/heartbeat_consolidation.json"),
    )
    checks.append(f"Memory consolidation: {consolidation['consolidated_count']} fragments")
    if consolidation["changed"]:
        checks.append("Memory consolidation updated")

    memory_health = run_memory_health(
        Path("memory"),
        Path("MEMORY.md"),
        Path("workspace/state_runtime/memory/memory_health.json"),
    )
    checks.append(
        f"Memory compounding: {memory_health['compounding_score']}/100"
        + (" ready" if memory_health["compounding_ready"] else " not-ready")
    )
    if memory_health["missing_recent_dates"]:
        checks.append(f"⚠️ Missing memory dates: {', '.join(memory_health['missing_recent_dates'])}")
    if memory_health["files_with_literal_escaped_newlines"]:
        checks.append("⚠️ Memory files contain escaped newlines")
    
    return checks


if __name__ == "__main__":
    print("Enhanced Heartbeat:")
    for check in enhanced_heartbeat():
        print(f"  {check}")
