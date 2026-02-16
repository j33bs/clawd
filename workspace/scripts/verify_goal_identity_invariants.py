#!/usr/bin/env python3
"""
Fail-closed verifier for repo-level security/governance invariants.
No network. No secret output. Deterministic checks only.
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT_GOV_FILES = (
    "AGENTS.md",
    "BOOTSTRAP.md",
    "HEARTBEAT.md",
    "IDENTITY.md",
    "SOUL.md",
    "TOOLS.md",
    "USER.md",
)

BANNED_PROVIDER_STRINGS = (
    "system2-litellm",
    "openai-codex",
    "openai_codex",
)

LADDER_ORDER = ["google-gemini-cli", "qwen-portal", "groq", "ollama"]
LADDER_SET = set(LADDER_ORDER)


def die(msg: str) -> None:
    print(f"FAIL: {msg}")
    raise SystemExit(2)


def git(repo: Path, args):
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=False,
    )


def read_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        die(f"invalid JSON: {path} ({exc})")


def assert_required_strings(path: Path, required):
    text = path.read_text(encoding="utf-8", errors="replace")
    for s in required:
        if s not in text:
            die(f"missing required string {s!r} in {path}")


def walk_strings(obj):
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, list):
        for item in obj:
            yield from walk_strings(item)
    elif isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(k, str):
                yield k
            yield from walk_strings(v)

def warn(msg: str) -> None:
    print(f"WARN: {msg}", file=sys.stderr)


def parse_args(argv):
    ap = argparse.ArgumentParser(add_help=True)
    ap.add_argument("--repo-root", default=None, help="override repo root for testing/fixtures")
    ap.add_argument("--strict", action="store_true", help="treat warnings as failures")
    return ap.parse_args(argv)


def bypass_scan(repo: Path):
    """
    Warn-only scan for likely bypass patterns.
    This is intentionally conservative and not exhaustive.
    """
    warnings = []

    # Scan tracked JS/TS in a small, high-risk surface area only.
    r = git(repo, ["ls-files", "--", "core", "scripts", "workspace/scripts"])
    if r.returncode != 0:
        return warnings
    paths = [p for p in (r.stdout or "").splitlines() if p]

    needles = (
        "child_process.exec(",
        "child_process.execSync(",
        "child_process.spawn(",
    )

    for rel in paths:
        p = repo / rel
        if p.suffix not in (".js", ".mjs", ".cjs", ".ts"):
            continue
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue

        if any(n in text for n in needles):
            warnings.append(f"bypass_scan child_process use in {rel}")

        # Flag obvious "never log auth headers" violations.
        for line in text.splitlines():
            if "console.log" in line and ("Bearer " in line or "authorization" in line.lower()):
                warnings.append(f"bypass_scan console.log auth-ish line in {rel}")
                break

    return warnings


def main() -> int:
    args = parse_args(sys.argv[1:])
    repo = Path(args.repo_root).resolve() if args.repo_root else Path(__file__).resolve().parents[2]

    # Governance anchors must exist and include identity/objective strings.
    contract = repo / "workspace" / "governance" / "SECURITY_GOVERNANCE_CONTRACT.md"
    anchor = repo / "workspace" / "governance" / "GOAL_ANCHOR.md"
    aspirations = repo / "workspace" / "governance" / "ASPIRATIONS_THREAT_MODEL.md"
    for p in (contract, anchor, aspirations):
        if not p.exists():
            die(f"missing required governance doc: {p}")
    for p in (contract, anchor):
        assert_required_strings(p, ("C_Lawd", "TACTI(C)-R", "System Regulation"))

    # Repo-root governance files must not exist on disk (tracked or untracked).
    for name in REPO_ROOT_GOV_FILES:
        if (repo / name).exists():
            die(f"repo-root governance file present: {name}")
        r = git(repo, ["ls-files", "--", name])
        if r.returncode == 0 and (r.stdout or "").strip():
            die(f"repo-root governance file tracked: {name}")

    # Policy routing invariants.
    policy_path = repo / "workspace" / "policy" / "llm_policy.json"
    policy = read_json(policy_path)
    routing = policy.get("routing") or {}
    free_order = routing.get("free_order")
    if free_order != LADDER_ORDER:
        die(f"policy routing.free_order must be {LADDER_ORDER!r} (got {free_order!r})")
    intents = (routing.get("intents") or {})
    for intent in ("system2_audit", "governance", "security"):
        order = ((intents.get(intent) or {}).get("order"))
        if order != LADDER_ORDER:
            die(f"policy routing.intents.{intent}.order must be {LADDER_ORDER!r} (got {order!r})")
        allow_paid = (intents.get(intent) or {}).get("allowPaid")
        if allow_paid is not False:
            die(f"policy routing.intents.{intent}.allowPaid must be false")

    # Ban provider strings in policy (string walk, fail-closed).
    policy_text = policy_path.read_text(encoding="utf-8", errors="replace")
    for s in BANNED_PROVIDER_STRINGS:
        if s in policy_text:
            die(f"banned provider string present in policy: {s}")

    # Canonical models invariants.
    models_path = repo / "agents" / "main" / "agent" / "models.json"
    models = read_json(models_path)
    providers = (models.get("providers") or {})
    if set(providers.keys()) != LADDER_SET:
        die(f"canonical models providers set must be {sorted(LADDER_SET)!r} (got {sorted(providers.keys())!r})")
    for banned in ("openai", "openai-codex", "openai_codex", "system2-litellm"):
        if banned in providers:
            die(f"banned provider key present in canonical models: {banned}")

    # Groq base URL must retain /openai/v1 (do not substring-scrub).
    groq = providers.get("groq") or {}
    groq_base = (groq.get("baseUrl") or "")
    if "/openai/v1" not in groq_base:
        die("groq baseUrl must contain '/openai/v1'")

    # Ollama must not require API keys/sentinels in canonical models.
    ollama = providers.get("ollama") or {}
    for k in ("apiKey", "apiKeyEnv", "auth", "authEnv"):
        if k in ollama:
            die(f"ollama must not contain auth fields in canonical models (found key {k!r})")

    # No OpenAI/Codex model-id prefixes anywhere in canonical models string tree.
    removed = 0
    for s in walk_strings(models):
        if isinstance(s, str) and (s.startswith("openai/") or s.startswith("openai-codex/")):
            removed += 1
    if removed:
        die("canonical models contains openai/openai-codex model-id prefixes")

    # Warn-only bypass scans (promotable via --strict).
    warnings = bypass_scan(repo)
    if warnings:
        warn("BYPASS SCAN WARNINGS:")
        for w in warnings:
            warn(w)
        if args.strict:
            die("strict mode: bypass scan warnings present")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
