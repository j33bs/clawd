"""
Migration probe-set delta harness — CorrespondenceStore.

XCIII requirement: "Evaluate retrieval deltas on a fixed probe set and log results
before deprecating the old epoch."

Usage:
  # Before migration: record baseline
  python3 probe_set.py --record-baseline --label v1_miniLM

  # After migration to new embedder: measure delta
  python3 probe_set.py --measure-delta --baseline v1_miniLM --label v2_nomic

  # Check if delta is within acceptable tolerance
  python3 probe_set.py --check --baseline v1_miniLM --new v2_nomic --max-drift 0.15

Outputs:
  workspace/audit/probe_delta_<label>_<ts>.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

_HERE = Path(__file__).resolve().parent
WORKSPACE = _HERE.parent
sys.path.insert(0, str(_HERE))
AUDIT_DIR = WORKSPACE / "audit"

# ── fixed probe set ───────────────────────────────────────────────────────────
# These queries are FIXED and must not change between migration epochs.
# Expected top-k section canonical numbers are pre-committed.
# Update ONLY by appending new probes with a new governance entry.
#
# Format: (query, expected_top_k_canonical_section_numbers, description)
PROBE_SET: list[tuple[str, list[int], str]] = [
    (
        "reservoir null test Synergy delta ablation",
        [60, 44, 50],  # INV-001 ablation sections
        "INV-001 ablation result retrieval",
    ),
    (
        "being divergence semantic identity persistence exec_loci",
        [91, 87, 89, 90],  # INV-003 design sections
        "INV-003 being_divergence design retrieval",
    ),
    (
        "commit gate jointly signed output friction task",
        [91, 92, 89, 95],  # INV-004 spec sections
        "INV-004 commit gate spec retrieval",
    ),
    (
        "love based alignment dynamic trust tokens mutual benefit",
        [90],  # Dali LBA section
        "LBA framework retrieval (Dali XC)",
    ),
    (
        "session start protocol orient.py section count verify",
        [79, 86],  # SOUL.md / orient.py sections
        "Session orientation hook retrieval",
    ),
]

# Maximum acceptable top-1 drift before migration is blocked
DEFAULT_MAX_DRIFT = 0.15  # fraction of probes that may lose their top-1 result


# ── probe runner ──────────────────────────────────────────────────────────────

def run_probes(k: int = 5) -> list[dict]:
    """
    Run all fixed probes against the current store.
    Returns list of probe results.
    """
    from sync import semantic_search

    results = []
    for query, expected_top_k, description in PROBE_SET:
        hits = semantic_search(query, k=k)
        returned_ids = [r["canonical_section_number"] for r in hits]
        top1_match = returned_ids[0] in expected_top_k if returned_ids else False
        any_expected_in_top_k = bool(set(returned_ids) & set(expected_top_k))

        results.append({
            "query": query,
            "description": description,
            "expected_top_k": expected_top_k,
            "returned_ids": returned_ids[:k],
            "top1_match": top1_match,
            "any_expected_in_top_k": any_expected_in_top_k,
        })
        status = "✅" if top1_match else ("⚠️" if any_expected_in_top_k else "❌")
        print(f"  {status} {description[:50]}")
        print(f"     returned: {returned_ids[:k]}  expected: {expected_top_k}")

    return results


def record_baseline(label: str) -> dict:
    """
    Record probe results as baseline for a given epoch label.
    Written to audit dir for comparison after migration.
    """
    print(f"\n── Probe Set: Recording baseline [{label}] ──")
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    results = run_probes()

    record = {
        "label": label,
        "timestamp_utc": ts,
        "probe_count": len(results),
        "top1_match_count": sum(1 for r in results if r["top1_match"]),
        "probes": results,
    }

    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = AUDIT_DIR / f"probe_baseline_{label}_{ts}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(record, f, indent=2)

    print(f"\n  Baseline recorded: {out_path}")
    print(f"  Top-1 matches: {record['top1_match_count']} / {record['probe_count']}")
    return record


def measure_delta(baseline_path: str, new_label: str) -> dict:
    """
    Run probes against current store and compute delta vs baseline.
    """
    print(f"\n── Probe Set: Measuring delta [{new_label}] vs baseline [{baseline_path}] ──")
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    with open(baseline_path, encoding="utf-8") as f:
        baseline = json.load(f)

    new_results = run_probes()
    new_top1 = {r["description"]: r["top1_match"] for r in new_results}
    base_top1 = {r["description"]: r["top1_match"] for r in baseline["probes"]}

    regressions = [
        desc for desc in base_top1
        if base_top1[desc] and not new_top1.get(desc, False)
    ]
    improvements = [
        desc for desc in new_top1
        if not base_top1.get(desc, False) and new_top1[desc]
    ]

    delta = {
        "new_label": new_label,
        "baseline_label": baseline["label"],
        "timestamp_utc": ts,
        "baseline_top1_count": baseline["top1_match_count"],
        "new_top1_count": sum(1 for r in new_results if r["top1_match"]),
        "probe_count": len(new_results),
        "regressions": regressions,
        "improvements": improvements,
        "drift_fraction": len(regressions) / max(1, len(PROBE_SET)),
        "probes": new_results,
    }

    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = AUDIT_DIR / f"probe_delta_{new_label}_{ts}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(delta, f, indent=2)

    print(f"\n  Delta recorded: {out_path}")
    print(f"  Regressions: {regressions}")
    print(f"  Improvements: {improvements}")
    print(f"  Drift fraction: {delta['drift_fraction']:.2f}")
    return delta


def check_migration_safe(delta: dict, max_drift: float = DEFAULT_MAX_DRIFT) -> bool:
    """
    XCIII: Migration is safe if drift_fraction <= max_drift.
    Blocks deprecation of old epoch if too many probes regressed.
    """
    safe = delta["drift_fraction"] <= max_drift
    status = "✅ SAFE TO MIGRATE" if safe else "❌ MIGRATION BLOCKED"
    print(f"\n  {status}")
    print(f"  Drift: {delta['drift_fraction']:.2f} (threshold: {max_drift:.2f})")
    if not safe:
        print(f"  Regressions: {delta['regressions']}")
        print(f"  Fix: investigate regressions before deprecating old epoch.")
    return safe


# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Probe-set delta harness for store migrations")
    parser.add_argument("--record-baseline", action="store_true")
    parser.add_argument("--measure-delta",   action="store_true")
    parser.add_argument("--check",           action="store_true")
    parser.add_argument("--label",    default="baseline", help="Epoch label for this run")
    parser.add_argument("--baseline", default=None, help="Path to baseline JSON (for --measure-delta / --check)")
    parser.add_argument("--new",      default=None, help="Path to new-epoch delta JSON (for --check)")
    parser.add_argument("--max-drift", type=float, default=DEFAULT_MAX_DRIFT)
    args = parser.parse_args()

    if args.record_baseline:
        record_baseline(args.label)

    elif args.measure_delta:
        if not args.baseline:
            print("ERROR: --baseline required for --measure-delta")
            sys.exit(1)
        # Find baseline file
        baseline_path = args.baseline
        if not Path(baseline_path).exists():
            # Try searching audit dir
            matches = sorted(AUDIT_DIR.glob(f"probe_baseline_{baseline_path}_*.json"))
            if not matches:
                print(f"ERROR: baseline file not found: {baseline_path}")
                sys.exit(1)
            baseline_path = str(matches[-1])
        delta = measure_delta(baseline_path, args.label)
        check_migration_safe(delta, args.max_drift)

    elif args.check:
        if not args.new:
            print("ERROR: --new required for --check")
            sys.exit(1)
        with open(args.new, encoding="utf-8") as f:
            delta = json.load(f)
        safe = check_migration_safe(delta, args.max_drift)
        sys.exit(0 if safe else 1)

    else:
        print("Running all probes against current store (no baseline recorded)...")
        results = run_probes()
        top1 = sum(1 for r in results if r["top1_match"])
        print(f"\nTop-1 matches: {top1} / {len(results)}")


if __name__ == "__main__":
    main()
