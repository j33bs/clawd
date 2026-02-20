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
    policy_paid_ids = set()
    policy_free_ids = set()
    if isinstance(providers, dict):
        for pid, cfg in providers.items():
            if not isinstance(cfg, dict):
                continue
            if cfg.get("paid") is True:
                policy_paid_ids.add(pid)
            else:
                policy_free_ids.add(pid)
    catalog_unknown_cost_ids = set(catalog_ids) - set(policy_provider_ids)
    allowed_ids = set(catalog_ids) | set(policy_provider_ids)

    print("policy_path:", policy_path)
    print("catalog_ids:", ",".join(sorted(catalog_ids)))
    print(
        "policy_provider_ids:",
        ",".join(sorted(policy_provider_ids)) if policy_provider_ids else "<none>",
    )
    print("routing_id -> normalized_id -> allowed?")

    resolved_via_catalog_direct = set()
    resolved_via_alias_to_catalog = set()
    resolved_via_policy_paid = set()
    resolved_via_policy_free = set()
    unknown_set = set()
    checked = 0
    for source_id in _routing_ids(policy):
        if source_id == "free":
            continue
        checked += 1
        normalized = normalize_provider_id(source_id)
        is_allowed = normalized in allowed_ids
        if normalized in catalog_ids:
            if source_id == normalized:
                resolved_via_catalog_direct.add(normalized)
            else:
                resolved_via_alias_to_catalog.add(normalized)
        if normalized in policy_provider_ids:
            if normalized in policy_paid_ids:
                resolved_via_policy_paid.add(normalized)
            else:
                resolved_via_policy_free.add(normalized)
        if not is_allowed:
            print(f"{source_id} -> {normalized} -> false")
            unknown_set.add(normalized)

    sensitive_intents = ("governance", "security", "system2_audit")
    intent_orders_normalized = {}
    intent_paid_violations = {}
    intent_unknown_cost_violations = {}
    intent_cost_class = {}
    intents = (policy.get("routing", {}) or {}).get("intents", {}) or {}
    for intent in sensitive_intents:
        cfg = intents.get(intent)
        if not isinstance(cfg, dict):
            intent_orders_normalized[intent] = []
            intent_cost_class[intent] = {"free": [], "paid": [], "unknown": []}
            continue
        order = cfg.get("order", [])
        normalized_order = [normalize_provider_id(x) for x in order if isinstance(x, str)]
        intent_orders_normalized[intent] = normalized_order
        offenders_paid = sorted({pid for pid in normalized_order if pid in policy_paid_ids})
        offenders_unknown = sorted({pid for pid in normalized_order if pid in catalog_unknown_cost_ids})
        if offenders_paid:
            intent_paid_violations[intent] = offenders_paid
        if offenders_unknown:
            intent_unknown_cost_violations[intent] = offenders_unknown
        intent_cost_class[intent] = {
            "free": sorted({pid for pid in normalized_order if pid in policy_free_ids}),
            "paid": offenders_paid,
            "unknown": offenders_unknown,
        }

    unknown = sorted(unknown_set)
    print("diagnostics:")
    print(
        "  resolved_via_catalog_direct:",
        ",".join(sorted(resolved_via_catalog_direct)) if resolved_via_catalog_direct else "<none>",
    )
    print(
        "  resolved_via_alias_to_catalog:",
        ",".join(sorted(resolved_via_alias_to_catalog)) if resolved_via_alias_to_catalog else "<none>",
    )
    print(
        "  resolved_via_policy_paid:",
        ",".join(sorted(resolved_via_policy_paid)) if resolved_via_policy_paid else "<none>",
    )
    print(
        "  resolved_via_policy_free:",
        ",".join(sorted(resolved_via_policy_free)) if resolved_via_policy_free else "<none>",
    )
    print("  unknown:", ",".join(unknown) if unknown else "<none>")
    print("  intent_orders_normalized:")
    for intent in sensitive_intents:
        values = intent_orders_normalized.get(intent, [])
        print(f"    {intent}:", ",".join(values) if values else "<none>")
    print("  intent_cost_class:")
    for intent in sensitive_intents:
        classes = intent_cost_class.get(intent, {"free": [], "paid": [], "unknown": []})
        free_csv = ",".join(classes.get("free", [])) if classes.get("free") else "<none>"
        paid_csv = ",".join(classes.get("paid", [])) if classes.get("paid") else "<none>"
        unknown_csv = ",".join(classes.get("unknown", [])) if classes.get("unknown") else "<none>"
        print(f"    {intent}: free={free_csv} paid={paid_csv} unknown={unknown_csv}")
    print(f"summary: checked={checked} unknown={len(unknown)}")
    if unknown:
        print("FAIL: unknown normalized routing provider IDs:")
        for item in unknown:
            print(f"  - {item}")
        return 2
    if intent_paid_violations:
        for intent in sensitive_intents:
            offenders = intent_paid_violations.get(intent)
            if not offenders:
                continue
            print(f"FAIL: paid providers present in intent order: {intent}")
            print("  offending:", ",".join(offenders))
        return 2
    if intent_unknown_cost_violations:
        for intent in sensitive_intents:
            offenders = intent_unknown_cost_violations.get(intent)
            if not offenders:
                continue
            print(f"FAIL: unknown cost-class providers present in intent order: {intent}")
            print("  offending_unknown:", ",".join(offenders))
        return 2

    print("PASS: all normalized routing IDs are in catalog or policy providers")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
