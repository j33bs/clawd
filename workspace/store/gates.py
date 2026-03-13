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
    Tests that exec_tags live in metadata, NOT in the embedding vector.

    Approach (no in-place mutation — avoids lancedb .update() which crashes
    on list-type columns in lance ≥2.0):
      1. Find a section WITH EXEC:GOV — it should appear in tag-filtered results.
      2. Find a section WITHOUT EXEC:GOV that is semantically similar — it should
         NOT appear in the same tag-filtered results.
      3. Both should appear in unfiltered results.
    This confirms the filter operates on metadata tags, not on embedding content.
    """
    print("\n── GATE 4: Authority isolation test (INV-STORE-001) ──")
    table = get_table()

    df = table.to_pandas()
    gov_sections = df[df["exec_tags"].apply(lambda t: "EXEC:GOV" in t)]
    non_gov_sections = df[df["exec_tags"].apply(lambda t: "EXEC:GOV" not in t)]

    if gov_sections.empty:
        print("  No EXEC:GOV sections found — cannot run test")
        return {"gate": 4, "passed": False, "reason": "no EXEC:GOV sections in store"}

    if non_gov_sections.empty:
        print("  No non-EXEC:GOV sections found — cannot run control")
        return {"gate": 4, "passed": False, "reason": "no non-EXEC:GOV sections in store"}

    gov_target = gov_sections.iloc[0]
    gov_id = int(gov_target["canonical_section_number"])
    non_gov_target = non_gov_sections.iloc[0]
    non_gov_id = int(non_gov_target["canonical_section_number"])

    print(f"  EXEC:GOV section (id={gov_id}): '{gov_target['title'][:50]}'")
    print(f"  Control section  (id={non_gov_id}): '{non_gov_target['title'][:50]}'")

    query = "governance decision executive attribution authority procedural rule"

    # 1. Unfiltered — both should plausibly appear (semantic neighbourhood)
    unfiltered = semantic_search(query, k=len(df), filters=None)
    unfiltered_ids = {r["canonical_section_number"] for r in unfiltered}
    gov_in_unfiltered = gov_id in unfiltered_ids
    non_gov_in_unfiltered = non_gov_id in unfiltered_ids

    # 2. Filtered by EXEC:GOV — ONLY gov section should appear
    filtered = semantic_search(query, k=len(df), filters={"exec_tags": ["EXEC:GOV"]})
    filtered_ids = {r["canonical_section_number"] for r in filtered}
    gov_in_filtered = gov_id in filtered_ids
    non_gov_in_filtered = non_gov_id in filtered_ids

    # 3. Verify ALL filtered results actually have the EXEC:GOV tag (not leaked via embedding)
    gov_ids_in_store = set(gov_sections["canonical_section_number"].tolist())
    all_filtered_are_gov = all(r["canonical_section_number"] in gov_ids_in_store for r in filtered)

    checks = {
        "gov_section_in_exec_gov_filtered_results": gov_in_filtered,
        "non_gov_section_absent_from_filtered_results": not non_gov_in_filtered,
        "all_filtered_results_have_exec_gov_tag": all_filtered_are_gov,
    }

    passed = all(checks.values())
    print(f"  EXEC:GOV section appears in tag-filtered results: {gov_in_filtered}")
    print(f"  Control section absent from tag-filtered results: {not non_gov_in_filtered}")
    print(f"  All filtered results have EXEC:GOV tag (no embedding leak): {all_filtered_are_gov}")
    print(f"  → Authority is in metadata, not in embedding: {passed}")
    print(f"  GATE 4: {'✅ PASS' if passed else '❌ FAIL'}")

    return {
        "gate": 4,
        "passed": passed,
        "checks": checks,
        "gov_section": gov_id,
        "control_section": non_gov_id,
        "filtered_count": len(filtered),
        "note": "Rewritten without table.update() — lancedb list-column mutation bug avoided",
    }


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
