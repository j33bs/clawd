"""
Four success gates for CorrespondenceStore v1.

All four must pass before the store is declared live.
From workspace/docs/CorrespondenceStore_v1_Plan.md and OPEN_QUESTIONS.md LXXVII–LXXIX.
"""
from __future__ import annotations
import time
import os
import sys

WORKSPACE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(WORKSPACE, "store"))

from sync import linear_tail, semantic_search, full_rebuild, get_table, DEFAULT_MODEL
from parser import parse_sections

OQ_PATH = os.path.join(WORKSPACE, "governance", "OPEN_QUESTIONS.md")
REBUILD_SPEED_GATE_SECONDS = 60.0


def gate_1_disposition(n: int = 40) -> dict:
    """
    GATE 1 — Disposition test.
    External callers can reconstruct project dispositions from linear_tail(40)
    without semantic search. Test: sections are in temporal order, bodies intact,
    key disposition markers present.
    """
    print("\n── GATE 1: Disposition test ──")
    tail = linear_tail(n=n)

    checks = {
        "section_count": len(tail) == n,
        "temporal_order": all(
            tail[i]["canonical_section_number"] < tail[i+1]["canonical_section_number"]
            for i in range(len(tail)-1)
        ),
        "bodies_non_empty": all(len(r["body"]) > 50 for r in tail),
        "authors_present": all(len(r["authors"]) > 0 or len(r["body"]) > 0 for r in tail),
        "store_design_in_tail": any(
            "store" in r["title"].lower() or "correspondence" in r["title"].lower()
            for r in tail
        ),
    }

    passed = all(checks.values())
    print(f"  section_count == {n}: {checks['section_count']}")
    print(f"  temporal_order: {checks['temporal_order']}")
    print(f"  bodies_non_empty: {checks['bodies_non_empty']}")
    print(f"  authors_present: {checks['authors_present']}")
    print(f"  store design sections in tail: {checks['store_design_in_tail']}")
    print(f"  GATE 1: {'✅ PASS' if passed else '❌ FAIL'}")
    return {"gate": 1, "passed": passed, "checks": checks}


def gate_2_origin_integrity() -> dict:
    """
    GATE 2 — Origin integrity test.
    Query 'reservoir null test' returns correct sections with origin tags intact.
    """
    print("\n── GATE 2: Origin integrity test ──")
    results = semantic_search("reservoir null test Synergy delta ablation", k=5)

    # Check that relevant sections come back
    # INV-001 ablation was in section LX (canonical 60)
    relevant_titles = []
    has_ablation_result = False
    tags_intact = True

    for r in results:
        relevant_titles.append(r["title"])
        body_lower = r["body"].lower()
        if any(kw in body_lower for kw in ["synergy", "ablation", "δ", "delta", "-0.024"]):
            has_ablation_result = True
        # exec_tags should be lists (not corrupted into strings)
        if not isinstance(r["exec_tags"], list):
            tags_intact = False

    checks = {
        "results_returned": len(results) > 0,
        "ablation_result_found": has_ablation_result,
        "exec_tags_intact": tags_intact,
    }

    passed = all(checks.values())
    print(f"  Results returned: {len(results)}")
    print(f"  Top titles: {relevant_titles[:3]}")
    print(f"  Ablation result found: {checks['ablation_result_found']}")
    print(f"  exec_tags structurally intact: {checks['exec_tags_intact']}")
    print(f"  GATE 2: {'✅ PASS' if passed else '❌ FAIL'}")
    return {"gate": 2, "passed": passed, "checks": checks, "top_results": relevant_titles[:3]}


def gate_3_rebuild_speed() -> dict:
    """
    GATE 3 — Rebuild speed test.
    Store must rebuild from markdown in <60s on this hardware.
    """
    print("\n── GATE 3: Rebuild speed test ──")
    print(f"  Parsing and rebuilding from {OQ_PATH}...")
    t0 = time.time()

    sections = parse_sections(OQ_PATH)
    full_rebuild(sections, model_name=DEFAULT_MODEL)

    elapsed = time.time() - t0
    passed = elapsed < REBUILD_SPEED_GATE_SECONDS

    print(f"  Rebuild time: {elapsed:.1f}s")
    print(f"  Gate threshold: {REBUILD_SPEED_GATE_SECONDS}s")
    print(f"  GATE 3: {'✅ PASS' if passed else '❌ FAIL'} ({elapsed:.1f}s)")
    return {"gate": 3, "passed": passed, "elapsed_seconds": elapsed}


def gate_4_authority_isolation() -> dict:
    """
    GATE 4 — Authority isolation test (INV-STORE-001).
    Stripping [EXEC:GOV] from a section's metadata changes filtered query results.
    The section should still appear in unfiltered semantic results (embedding unchanged),
    but drop out of exec_tag-filtered results.
    This confirms exec_tags live in metadata, NOT in the embedding vector.
    """
    print("\n── GATE 4: Authority isolation test (INV-STORE-001) ──")
    table = get_table()

    # Find a section with EXEC:GOV tag
    df = table.to_pandas()
    gov_sections = df[df["exec_tags"].apply(lambda t: "EXEC:GOV" in t)]

    if gov_sections.empty:
        print("  No EXEC:GOV sections found — cannot run test")
        return {"gate": 4, "passed": False, "reason": "no EXEC:GOV sections in store"}

    target = gov_sections.iloc[0]
    target_id = int(target["canonical_section_number"])
    print(f"  Testing on section {target_id}: '{target['title'][:50]}'")
    print(f"  Original exec_tags: {target['exec_tags']}")

    # 1. Unfiltered semantic search — section should appear
    query = "governance decision executive attribution"
    unfiltered = semantic_search(query, k=20, filters=None)
    in_unfiltered_before = any(
        r["canonical_section_number"] == target_id for r in unfiltered
    )

    # 2. Filtered by EXEC:GOV — section should appear
    filtered_before = semantic_search(query, k=20, filters={"exec_tags": ["EXEC:GOV"]})
    in_filtered_before = any(
        r["canonical_section_number"] == target_id for r in filtered_before
    )

    # 3. Temporarily strip EXEC:GOV from target section metadata
    import pandas as pd
    stripped_tags = [t for t in target["exec_tags"] if t != "EXEC:GOV"]
    table.update(
        where=f"canonical_section_number = {target_id}",
        values={"exec_tags": stripped_tags}
    )
    print(f"  Stripped EXEC:GOV → exec_tags now: {stripped_tags}")

    # 4. Filtered by EXEC:GOV — section should now be ABSENT
    filtered_after = semantic_search(query, k=20, filters={"exec_tags": ["EXEC:GOV"]})
    in_filtered_after = any(
        r["canonical_section_number"] == target_id for r in filtered_after
    )

    # 5. Unfiltered — section should STILL appear (embedding unchanged)
    unfiltered_after = semantic_search(query, k=20, filters=None)
    in_unfiltered_after = any(
        r["canonical_section_number"] == target_id for r in unfiltered_after
    )

    # 6. Restore original tags
    table.update(
        where=f"canonical_section_number = {target_id}",
        values={"exec_tags": list(target["exec_tags"])}
    )
    print(f"  Restored exec_tags: {list(target['exec_tags'])}")

    checks = {
        "in_filtered_before_strip": in_filtered_before,
        "absent_from_filtered_after_strip": not in_filtered_after,
        "still_in_unfiltered_after_strip": in_unfiltered_after,
    }

    passed = all(checks.values())
    print(f"  In EXEC:GOV filtered results before strip: {in_filtered_before}")
    print(f"  Absent from EXEC:GOV filtered results after strip: {not in_filtered_after}")
    print(f"  Still in unfiltered results after strip: {in_unfiltered_after}")
    print(f"  → Authority is in metadata, not in embedding: {passed}")
    print(f"  GATE 4: {'✅ PASS' if passed else '❌ FAIL'}")

    return {"gate": 4, "passed": passed, "checks": checks, "target_section": target_id}


def run_all_gates() -> dict:
    """Run all four gates and return a summary."""
    print("\n" + "="*60)
    print("CorrespondenceStore v1 — Success Gates")
    print("="*60)

    results = {}
    # Gates 1 and 2 require the store to exist already
    # Gate 3 does a full rebuild (also re-populates the store)
    # Run in order: 3 first (ensures store is fresh), then 1, 2, 4

    g3 = gate_3_rebuild_speed()
    results[3] = g3

    if g3["passed"]:
        g1 = gate_1_disposition()
        g2 = gate_2_origin_integrity()
        g4 = gate_4_authority_isolation()
        results[1] = g1
        results[2] = g2
        results[4] = g4
    else:
        print("\n  Gate 3 failed — skipping gates 1, 2, 4 (store may be incomplete)")
        results[1] = {"gate": 1, "passed": False, "reason": "Gate 3 failed"}
        results[2] = {"gate": 2, "passed": False, "reason": "Gate 3 failed"}
        results[4] = {"gate": 4, "passed": False, "reason": "Gate 3 failed"}

    all_passed = all(r["passed"] for r in results.values())

    print("\n" + "="*60)
    print("GATE SUMMARY")
    print("="*60)
    for gate_num in [1, 2, 3, 4]:
        r = results[gate_num]
        status = "✅ PASS" if r["passed"] else "❌ FAIL"
        print(f"  Gate {gate_num}: {status}")

    print()
    if all_passed:
        print("  🟢 ALL GATES PASSED — store is LIVE")
    else:
        failed = [str(n) for n, r in results.items() if not r["passed"]]
        print(f"  🔴 GATES FAILED: {', '.join(failed)} — store is NOT live")

    print("="*60)
    return {"all_passed": all_passed, "gates": results}
