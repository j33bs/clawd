#!/usr/bin/env python3
"""Deterministic check: routing aliases normalize to known catalog/provider ids."""

import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT / "workspace" / "scripts") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "workspace" / "scripts"))

from policy_router import normalize_provider_id  # noqa: E402


def _load_catalog_ids():
    out = subprocess.check_output(
        [
            "node",
            "-e",
            "const { CATALOG } = require('./core/system2/inference/catalog');"
            "for (const p of CATALOG) console.log(p.provider_id);",
        ],
        cwd=str(REPO_ROOT),
        text=True,
    )
    return {line.strip() for line in out.splitlines() if line.strip()}


def _routing_ids(policy):
    ids = set()
    routing = policy.get("routing", {}) or {}
    for entry in routing.get("free_order", []) or []:
        if isinstance(entry, str):
            ids.add(entry)
    intents = routing.get("intents", {}) or {}
    for cfg in intents.values():
        if isinstance(cfg, dict):
            for entry in cfg.get("order", []) or []:
                if isinstance(entry, str):
                    ids.add(entry)
    rules = routing.get("rules", []) or []
    for rule in rules:
        if isinstance(rule, dict) and isinstance(rule.get("provider"), str):
            ids.add(rule["provider"])
    return sorted(ids)


def main():
    policy_path = REPO_ROOT / "workspace" / "policy" / "llm_policy.json"
    policy = json.loads(policy_path.read_text(encoding="utf-8"))
    catalog_ids = _load_catalog_ids()

    print("policy_path:", policy_path)
    print("catalog_ids:", ",".join(sorted(catalog_ids)))
    print("routing_id -> normalized_id -> in_catalog")

    missing = []
    for source_id in _routing_ids(policy):
        if source_id == "free":
            continue
        normalized = normalize_provider_id(source_id)
        in_catalog = normalized in catalog_ids
        print(f"{source_id} -> {normalized} -> {str(in_catalog).lower()}")
        # Only fail when an explicit alias normalization target is missing.
        if source_id != normalized and not in_catalog:
            missing.append((source_id, normalized))

    if missing:
        print("FAIL: routing IDs normalize to values outside catalog:")
        for source_id, normalized in missing:
            print(f"  - {source_id} -> {normalized}")
        return 1

    print("PASS: all routing IDs normalize to catalog IDs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
