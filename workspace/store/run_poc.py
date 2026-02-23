"""
CorrespondenceStore v1 — PoC entry point.

Usage:
  python run_poc.py              # parse, index, run all gates
  python run_poc.py --parse-only # parse and print section summary
  python run_poc.py --gates-only # run gates (store must already exist)

Embedding model: all-MiniLM-L6-v2 (PoC default, fast local)
Production model: nomic-embed-text-v1.5 (set EMBED_MODEL env var for Dali)
"""
from __future__ import annotations
import sys
import os
import json
from datetime import datetime

WORKSPACE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(WORKSPACE, "store"))

from parser import parse_sections
from sync import full_rebuild, DEFAULT_MODEL
from gates import run_all_gates

OQ_PATH = os.path.join(WORKSPACE, "governance", "OPEN_QUESTIONS.md")
RESULTS_PATH = os.path.join(WORKSPACE, "store", "poc_results.json")


def print_section_summary(sections):
    print(f"\n{'='*60}")
    print(f"Parsed {len(sections)} sections from OPEN_QUESTIONS.md")
    print(f"{'='*60}")

    external = [s for s in sections if s.is_external_caller]
    with_exec = [s for s in sections if s.exec_tags]
    collisions = [s for s in sections if s.collision]
    authors = {}
    for s in sections:
        for a in s.authors:
            authors[a] = authors.get(a, 0) + 1

    print(f"  External callers: {len(external)}")
    print(f"  With exec_tags:   {len(with_exec)}")
    print(f"  Collisions:       {len(collisions)}")
    print(f"\nContributions per being:")
    for author, count in sorted(authors.items(), key=lambda x: -x[1]):
        print(f"    {author}: {count}")

    if collisions:
        print(f"\nCollision log:")
        for s in collisions:
            print(f"    Section {s.canonical_section_number}: filed as {s.section_number_filed}")

    print(f"\nExec-tagged sections:")
    for s in with_exec:
        print(f"    [{s.canonical_section_number}] {s.section_number_filed}. {s.title[:50]} — {s.exec_tags}")


def main():
    args = sys.argv[1:]
    parse_only = "--parse-only" in args
    gates_only = "--gates-only" in args

    print(f"\nCorrespondenceStore v1 — PoC Run")
    print(f"Timestamp: {datetime.now().isoformat()}")
    print(f"Source:    {OQ_PATH}")
    print(f"Model:     {DEFAULT_MODEL}")

    if not gates_only:
        print(f"\n[1/3] Parsing sections...")
        sections = parse_sections(OQ_PATH)
        print_section_summary(sections)

        if parse_only:
            return

        print(f"\n[2/3] Building store (this will download model on first run)...")
        table = full_rebuild(sections, model_name=DEFAULT_MODEL)
        print(f"  Store built at: workspace/store/lancedb_data/")

    print(f"\n[3/3] Running success gates...")
    results = run_all_gates()

    # Save results to JSON
    with open(RESULTS_PATH, 'w') as f:
        # Make serialisable
        serialisable = {
            "timestamp": datetime.now().isoformat(),
            "model": DEFAULT_MODEL,
            "all_passed": results["all_passed"],
            "gates": {
                str(k): {kk: vv for kk, vv in v.items() if kk != "checks" or True}
                for k, v in results["gates"].items()
            }
        }
        json.dump(serialisable, f, indent=2, default=str)
    print(f"\nResults saved to: workspace/store/poc_results.json")

    return 0 if results["all_passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
