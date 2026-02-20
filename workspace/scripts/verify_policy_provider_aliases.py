#!/usr/bin/env python3
"""Deterministic fail-closed check for routing/provider alias consistency."""

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
    providers = policy.get("providers", {})
    policy_provider_ids = set(providers.keys()) if isinstance(providers, dict) else set()
    allowed_ids = set(catalog_ids) | set(policy_provider_ids)

    print("policy_path:", policy_path)
    print("catalog_ids:", ",".join(sorted(catalog_ids)))
    print(
        "policy_provider_ids:",
        ",".join(sorted(policy_provider_ids)) if policy_provider_ids else "<none>",
    )
    print("routing_id -> normalized_id -> allowed?")

    unknown = []
    seen_unknown = set()
    checked = 0
    for source_id in _routing_ids(policy):
        if source_id == "free":
            continue
        checked += 1
        normalized = normalize_provider_id(source_id)
        is_allowed = normalized in allowed_ids
        if not is_allowed:
            print(f"{source_id} -> {normalized} -> false")
            if normalized not in seen_unknown:
                unknown.append(normalized)
                seen_unknown.add(normalized)

    print(f"summary: checked={checked} unknown={len(unknown)}")
    if unknown:
        print("FAIL: unknown normalized routing provider IDs:")
        for item in sorted(unknown):
            print(f"  - {item}")
        return 2

    print("PASS: all normalized routing IDs are in catalog or policy providers")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
