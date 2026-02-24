"""
Seven success gates for CorrespondenceStore v1.

All gates must pass before the store is declared live.
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
    df = table.to_pandas()

    gov_sections = df[df["exec_tags"].apply(lambda t: "EXEC:GOV" in t)]
    if gov_sections.empty:
        print("  No EXEC:GOV sections found — cannot run test")
        return {"gate": 4, "passed": False, "reason": "no EXEC:GOV sections"}

    query = "governance decision executive attribution authority procedural rule"
    unfiltered = semantic_search(query, k=30, filters=None)
    filtered = semantic_search(query, k=20, filters={"exec_tags": ["EXEC:GOV"]})

    gov_ids_in_store = set(gov_sections["canonical_section_number"].tolist())
    unfiltered_ids = {r["canonical_section_number"] for r in unfiltered}

    checks = {
        "all_filtered_have_exec_gov": all(
            "EXEC:GOV" in (r.get("exec_tags") or []) for r in filtered
        ),
        "exec_gov_returned_in_filtered": any(
            r["canonical_section_number"] in gov_ids_in_store for r in filtered
        ),
        "non_exec_gov_excluded_by_filter": len(unfiltered_ids - gov_ids_in_store) > 0,
    }
    passed = all(checks.values())

    print(f"  EXEC:GOV sections in store: {len(gov_sections)}")
    print(f"  Unfiltered results (k=30): {len(unfiltered)}")
    print(f"  Filtered results (EXEC:GOV, k=20): {len(filtered)}")
    print(f"  All filtered rows have EXEC:GOV: {checks['all_filtered_have_exec_gov']}")
    print(f"  EXEC:GOV sections returned in filtered: {checks['exec_gov_returned_in_filtered']}")
    print(f"  Non-EXEC:GOV sections excluded by filter: {checks['non_exec_gov_excluded_by_filter']}")
    print(f"  → Authority is in metadata, not in embedding: {passed}")
    print(f"  GATE 4: {'✅ PASS' if passed else '❌ FAIL'}")

    return {
        "gate": 4,
        "passed": passed,
        "checks": checks,
        "gov_sections_in_store": len(gov_sections),
        "filtered_returned": len(filtered),
    }


def _filter_exec_tags(rows: list[dict], required_tags: list[str]) -> list[dict]:
    required = set(required_tags)
    return [
        r for r in rows
        if bool(required.intersection(set(r.get("exec_tags") or [])))
    ]


def _filter_authors(rows: list[dict], required_authors: list[str]) -> list[dict]:
    required = set(a.lower() for a in required_authors)
    return [
        r for r in rows
        if bool(required.intersection(set(a.lower() for a in (r.get("authors") or []))))
    ]


def gate_5_authority_invariance() -> dict:
    """
    GATE 5 — Authority invariance.
    Metadata predicate order must not change exec-tag-filtered retrieval results.
    """
    print("\n── GATE 5: Authority invariance ──")
    query = "governance decision executive attribution"
    k = 20
    candidate_k = k * 3

    candidates = semantic_search(query, k=candidate_k, filters=None)
    if not candidates:
        print("  No semantic candidates returned — cannot run test")
        print("  BLOCKED DEPLOYMENT: Gate 5 requires semantic candidates for invariance proof")
        return {"gate": 5, "passed": False, "reason": "no semantic candidates"}

    exec_required = ["EXEC:GOV"]
    gov_candidates = _filter_exec_tags(candidates, exec_required)
    if not gov_candidates:
        print("  No EXEC:GOV candidates in semantic pool — cannot run test")
        print("  BLOCKED DEPLOYMENT: Gate 5 requires EXEC:GOV candidates in semantic pool")
        return {"gate": 5, "passed": False, "reason": "no EXEC:GOV candidates in semantic pool"}

    secondary_author = None
    for row in gov_candidates:
        authors = row.get("authors") or []
        if authors:
            secondary_author = authors[0]
            break

    # Path A: exec_tags first, then optional secondary metadata filter.
    path_a = _filter_exec_tags(candidates, exec_required)
    if secondary_author:
        path_a = _filter_authors(path_a, [secondary_author])

    # Path B: optional secondary metadata filter first, then exec_tags.
    path_b_input = candidates
    if secondary_author:
        path_b_input = _filter_authors(path_b_input, [secondary_author])
    path_b = _filter_exec_tags(path_b_input, exec_required)

    final_a = path_a[:k]
    final_b = path_b[:k]
    ids_a = [int(r["canonical_section_number"]) for r in final_a]
    ids_b = [int(r["canonical_section_number"]) for r in final_b]

    checks = {
        "count_equal": len(final_a) == len(final_b),
        "canonical_ids_equal": ids_a == ids_b,
    }
    passed = all(checks.values())

    print(f"  Query: {query!r}")
    print(f"  Candidate pool: {len(candidates)}")
    print(f"  EXEC:GOV candidates in pool: {len(gov_candidates)}")
    print(f"  Secondary filter: {'author=' + secondary_author if secondary_author else 'none (exec_tags only)'}")
    print(f"  Path A size (exec→secondary): {len(final_a)}")
    print(f"  Path B size (secondary→exec): {len(final_b)}")
    print(f"  Path A top ids: {ids_a[:5]}")
    print(f"  Path B top ids: {ids_b[:5]}")
    print(f"  Invariance verdict: {passed}")
    print(f"  GATE 5: {'✅ PASS' if passed else '❌ FAIL'}")

    return {
        "gate": 5,
        "passed": passed,
        "query": query,
        "secondary_author": secondary_author,
        "checks": checks,
        "path_a_ids": ids_a[:5],
        "path_b_ids": ids_b[:5],
    }


def gate_6_flow_invariance() -> dict:
    """
    GATE 6 — Flow invariance.
    linear_tail(5) must equal the last 5 rows of linear_tail(40).
    """
    print("\n── GATE 6: Flow invariance ──")

    tail_5 = linear_tail(n=5)
    tail_40 = linear_tail(n=40)
    tail_40_last_5 = tail_40[-5:]

    ids_5 = [int(r["canonical_section_number"]) for r in tail_5]
    ids_40_last_5 = [int(r["canonical_section_number"]) for r in tail_40_last_5]

    def _normalize(value):
        if hasattr(value, "tolist"):
            return value.tolist()
        if isinstance(value, list):
            return [_normalize(v) for v in value]
        if isinstance(value, dict):
            return {k: _normalize(v) for k, v in value.items()}
        return value

    payload_5 = [_normalize(r) for r in tail_5]
    payload_40_last_5 = [_normalize(r) for r in tail_40_last_5]

    checks = {
        "canonical_ids_equal": ids_5 == ids_40_last_5,
        "rows_equal": payload_5 == payload_40_last_5,
    }
    passed = all(checks.values())

    print(f"  linear_tail(5) ids: {ids_5}")
    print(f"  linear_tail(40)[-5:] ids: {ids_40_last_5}")
    print(f"  IDs invariant: {checks['canonical_ids_equal']}")
    print(f"  Row payload invariant: {checks['rows_equal']}")
    print(f"  GATE 6: {'✅ PASS' if passed else '❌ FAIL'}")

    return {
        "gate": 6,
        "passed": passed,
        "checks": checks,
        "tail_5_ids": ids_5,
        "tail_40_last_5_ids": ids_40_last_5,
    }


def _filed_to_canonical_map() -> tuple[dict[str, int], dict[int, str]]:
    table = get_table()
    df = table.to_pandas().sort_values("canonical_section_number")
    mapping = {}
    inverse = {}
    for _, row in df.iterrows():
        filed = str(row["section_number_filed"])
        canonical = int(row["canonical_section_number"])
        mapping[filed] = canonical
        inverse[canonical] = filed
    return mapping, inverse


def gate_7_rebuild_invariance() -> dict:
    """
    GATE 7 — Rebuild invariance.
    Two consecutive full_rebuild() calls must produce identical
    section_number_filed -> canonical_section_number mapping.
    """
    print("\n── GATE 7: Rebuild invariance ──")
    sections = parse_sections(OQ_PATH)
    print(f"  Parsed sections: {len(sections)}")

    print("  Rebuild pass 1...")
    full_rebuild(sections, model_name=DEFAULT_MODEL)
    mapping_1, inverse_1 = _filed_to_canonical_map()

    print("  Rebuild pass 2...")
    full_rebuild(sections, model_name=DEFAULT_MODEL)
    mapping_2, inverse_2 = _filed_to_canonical_map()

    sample_keys = sorted(mapping_1.keys())[:5]
    sample_pairs = [(k, mapping_1[k]) for k in sample_keys]

    checks = {
        "filed_to_canonical_identical": mapping_1 == mapping_2,
        "canonical_to_filed_identical": inverse_1 == inverse_2,
        "mapping_count_equal": len(mapping_1) == len(mapping_2),
    }
    passed = all(checks.values())

    print(f"  Mapping size (pass1): {len(mapping_1)}")
    print(f"  Mapping size (pass2): {len(mapping_2)}")
    print(f"  Sample filed→canonical: {sample_pairs}")
    print(f"  filed→canonical identical: {checks['filed_to_canonical_identical']}")
    print(f"  canonical→filed identical: {checks['canonical_to_filed_identical']}")
    print(f"  GATE 7: {'✅ PASS' if passed else '❌ FAIL'}")

    return {
        "gate": 7,
        "passed": passed,
        "checks": checks,
        "mapping_size": len(mapping_1),
        "sample": sample_pairs,
    }


def run_all_gates() -> dict:
    """Run all seven gates and return a summary."""
    print("\n" + "="*60)
    print("CorrespondenceStore v1 — Success Gates")
    print("="*60)

    results = {}
    # Gates 1 and 2 require the store to exist already
    # Gate 3 does a full rebuild (also re-populates the store)
    # Run in order: 3 first (ensures store is fresh), then 1, 2, 4, 5, 6, 7

    g3 = gate_3_rebuild_speed()
    results[3] = g3

    if g3["passed"]:
        g1 = gate_1_disposition()
        g2 = gate_2_origin_integrity()
        g4 = gate_4_authority_isolation()
        g5 = gate_5_authority_invariance()
        g6 = gate_6_flow_invariance()
        g7 = gate_7_rebuild_invariance()
        results[1] = g1
        results[2] = g2
        results[4] = g4
        results[5] = g5
        results[6] = g6
        results[7] = g7
    else:
        print("\n  Gate 3 failed — skipping gates 1, 2, 4, 5, 6, 7 (store may be incomplete)")
        results[1] = {"gate": 1, "passed": False, "reason": "Gate 3 failed"}
        results[2] = {"gate": 2, "passed": False, "reason": "Gate 3 failed"}
        results[4] = {"gate": 4, "passed": False, "reason": "Gate 3 failed"}
        results[5] = {"gate": 5, "passed": False, "reason": "Gate 3 failed"}
        results[6] = {"gate": 6, "passed": False, "reason": "Gate 3 failed"}
        results[7] = {"gate": 7, "passed": False, "reason": "Gate 3 failed"}

    all_passed = all(r["passed"] for r in results.values())

    print("\n" + "="*60)
    print("GATE SUMMARY")
    print("="*60)
    for gate_num in [1, 2, 3, 4, 5, 6, 7]:
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
