#!/usr/bin/env python3
"""Validate OpenClaw config invariants used by automation gates."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple


def _repo_root() -> Path:
    env_root = os.environ.get("OPENCLAW_ROOT")
    if env_root:
        return Path(env_root).expanduser().resolve()

    current = Path(__file__).resolve()
    for parent in current.parents:
        if (parent / ".git").exists():
            return parent
    return Path.cwd().resolve()


def _candidate_paths(repo_root: Path, explicit: Optional[str]) -> List[Path]:
    candidates: List[Path] = []
    if explicit:
        candidates.append(Path(explicit).expanduser())
    elif os.environ.get("OPENCLAW_CONFIG_PATH"):
        candidates.append(Path(os.environ["OPENCLAW_CONFIG_PATH"]).expanduser())
    candidates.append(repo_root / "workspace" / "config" / "openclaw.json")
    candidates.append(repo_root / "openclaw.json")
    candidates.append(Path.home() / ".openclaw" / "openclaw.json")

    deduped: List[Path] = []
    seen = set()
    for path in candidates:
        key = str(path)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(path)
    return deduped


def _resolve_config_path(repo_root: Path, explicit: Optional[str]) -> Tuple[Optional[Path], str]:
    for path in _candidate_paths(repo_root, explicit):
        if path.exists():
            return path.resolve(), "found"
    return None, "missing"


def _load_json(path: Path) -> Dict[str, object]:
    raw = path.read_text(encoding="utf-8")
    data = json.loads(raw)
    if isinstance(data, dict):
        return data
    raise ValueError("config root must be a JSON object")


def _enabled_entry_ids(plugins_cfg: Dict[str, object]) -> List[str]:
    entries = plugins_cfg.get("entries")
    if not isinstance(entries, dict):
        return []
    out: List[str] = []
    for plugin_id, entry in entries.items():
        enabled = True
        if isinstance(entry, dict):
            enabled = bool(entry.get("enabled", True))
        elif isinstance(entry, bool):
            enabled = entry
        if enabled and str(plugin_id).strip():
            out.append(str(plugin_id).strip())
    return out


def _ids_from_load_paths(plugins_cfg: Dict[str, object]) -> List[str]:
    load_cfg = plugins_cfg.get("load")
    if not isinstance(load_cfg, dict):
        return []
    paths = load_cfg.get("paths")
    if not isinstance(paths, list):
        return []
    out: List[str] = []
    for raw in paths:
        if not isinstance(raw, str) or not raw.strip():
            continue
        plugin_id = Path(raw.strip()).stem.strip()
        if plugin_id:
            out.append(plugin_id)
    return out


def _normalized_allow(plugins_cfg: Dict[str, object]) -> Tuple[List[str], bool]:
    allow = plugins_cfg.get("allow")
    if allow is None:
        return [], False
    if not isinstance(allow, list):
        return [], False
    out: List[str] = []
    for item in allow:
        if isinstance(item, str) and item.strip():
            out.append(item.strip())
    return sorted(set(out)), True


def validate_config(cfg: Dict[str, object]) -> Dict[str, object]:
    plugins_cfg = cfg.get("plugins")
    if not isinstance(plugins_cfg, dict):
        return {
            "ok": True,
            "issues": [],
            "allow": [],
            "allow_declared": False,
            "enabled_plugins": [],
        }

    allow, allow_declared = _normalized_allow(plugins_cfg)
    enabled = sorted(set(_enabled_entry_ids(plugins_cfg) + _ids_from_load_paths(plugins_cfg)))
    issues: List[str] = []

    # Deny-by-default for configured plugin loads.
    if enabled and not allow:
        issues.append("plugins.allow missing_or_empty while plugins are configured")

    allow_set = set(allow)
    for plugin_id in enabled:
        if plugin_id not in allow_set:
            issues.append(f"plugin_not_allowlisted:{plugin_id}")

    return {
        "ok": len(issues) == 0,
        "issues": issues,
        "allow": allow,
        "allow_declared": allow_declared,
        "enabled_plugins": enabled,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="OpenClaw config guard")
    parser.add_argument("--config", help="Explicit config path", default=None)
    parser.add_argument("--strict", action="store_true", help="Exit non-zero on validation issues")
    args = parser.parse_args()

    repo_root = _repo_root()
    path, state = _resolve_config_path(repo_root, args.config)

    if not path:
        print(
            json.dumps(
                {
                    "ok": True,
                    "state": state,
                    "config_path": None,
                    "issues": [],
                    "allow": [],
                    "enabled_plugins": [],
                },
                sort_keys=True,
            )
        )
        return 0

    try:
        cfg = _load_json(path)
    except Exception as exc:
        payload = {
            "ok": False,
            "state": "invalid_json",
            "config_path": str(path),
            "issues": [f"invalid_json:{exc}"],
            "allow": [],
            "enabled_plugins": [],
        }
        print(json.dumps(payload, sort_keys=True))
        return 2

    result = validate_config(cfg)
    payload = {
        "ok": bool(result.get("ok", False)),
        "state": "found",
        "config_path": str(path),
        "issues": result.get("issues", []),
        "allow": result.get("allow", []),
        "allow_declared": bool(result.get("allow_declared", False)),
        "enabled_plugins": result.get("enabled_plugins", []),
    }
    print(json.dumps(payload, sort_keys=True))
    if args.strict and payload["issues"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
