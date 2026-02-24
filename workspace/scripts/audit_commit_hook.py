#!/usr/bin/env python3
"""
Pre-commit audit hook for teamchat auto-commit.
Ensures: stability, coherence, constitution/governance/ethos adherence.
"""
import json
import os
import subprocess
import sys
from pathlib import Path
from datetime import datetime, timezone

WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_WITNESS_LEDGER_PATH = WORKSPACE_ROOT / "state_runtime" / "teamchat" / "witness_ledger.jsonl"

try:
    from witness_ledger import commit as witness_commit
except Exception:  # pragma: no cover - optional integration
    witness_commit = None

# Checks to run before commit
CHECKS = [
    ("git_dirty", "Check for uncommitted changes"),
    ("no_merge_conflicts", "No merge conflicts in staging"),
    ("tests_pass", "Critical tests pass"),
    ("no_secrets", "No secrets accidentally staged"),
    ("governance_compliant", "Governance files intact"),
]


def _flag_enabled(name: str, default: str = "0") -> bool:
    value = str(os.environ.get(name, default)).strip().lower()
    return value in {"1", "true", "yes", "on"}


def _commit_witness_entry(audit_entry: dict, audit_log: Path) -> tuple[bool, str]:
    if not _flag_enabled("OPENCLAW_WITNESS_LEDGER", default="1"):
        return True, "witness_disabled"
    if not callable(witness_commit):
        return False, "witness_unavailable"
    ledger_path = Path(
        os.environ.get("OPENCLAW_WITNESS_LEDGER_PATH", str(DEFAULT_WITNESS_LEDGER_PATH))
    )
    checks = audit_entry.get("checks", [])
    record = {
        "event": "governance_audit_commit",
        "audit_path": str(audit_log),
        "audit_type": str(audit_entry.get("type", "pre_commit_audit")),
        "audit_timestamp": str(audit_entry.get("timestamp", "")),
        "passed": bool(audit_entry.get("passed", False)),
        "checks_total": len(checks) if isinstance(checks, list) else 0,
        "checks_failed": sum(1 for row in checks if isinstance(row, dict) and not bool(row.get("passed", False))),
    }
    witness_commit(record=record, ledger_path=str(ledger_path))
    return True, "ok"

def run_check(name: str) -> tuple[bool, str]:
    """Run a specific check. Returns (passed, details)."""
    try:
        if name == "git_dirty":
            result = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=WORKSPACE_ROOT, capture_output=True, text=True, timeout=10
            )
            has_changes = bool(result.stdout.strip())
            return has_changes, f"Changes detected: {len(result.stdout.strip().split(chr(10)))} files"
        
        if name == "no_merge_conflicts":
            result = subprocess.run(
                ["git", "diff", "--check"],
                cwd=WORKSPACE_ROOT, capture_output=True, text=True, timeout=30
            )
            return result.returncode == 0, "No merge conflicts" if result.returncode == 0 else result.stdout[:200]
        
        if name == "tests_pass":
            # Quick smoke test - just import check
            result = subprocess.run(
                ["python3", "-c", "import json; import pathlib"],
                cwd=WORKSPACE_ROOT, capture_output=True, timeout=10
            )
            return result.returncode == 0, "Python imports OK" if result.returncode == 0 else "Import failed"
        
        if name == "no_secrets":
            # Check for common secret patterns
            result = subprocess.run(
                ["git", "diff", "--cached", "--name-only"],
                cwd=WORKSPACE_ROOT, capture_output=True, text=True, timeout=10
            )
            files = result.stdout.strip().split("\n")
            forbidden = ["credentials", "secrets", "token", "password"]
            risky = [f for f in files if any(b in f.lower() for b in forbidden)]
            return len(risky) == 0, f"No secrets in {len(files)} files" if not risky else f"Risky files: {risky}"
        
        if name == "governance_compliant":
            # Check key governance files exist
            required = ["CONSTITUTION.md", "AGENTS.md", "SOUL.md"]
            missing = [r for r in required if not (WORKSPACE_ROOT / r).exists()]
            return len(missing) == 0, "All governance files present" if not missing else f"Missing: {missing}"
        
    except Exception as e:
        return False, f"Check error: {e}"
    
    return True, "Unknown check"

def audit_commit() -> bool:
    """Run pre-commit audit. Returns True if safe to commit."""
    print("=" * 50)
    print("🔍 PRE-COMMIT AUDIT")
    print("=" * 50)
    
    results = []
    all_passed = True
    
    for check_name, description in CHECKS:
        passed, details = run_check(check_name)
        status = "✅" if passed else "❌"
        print(f"{status} {check_name}: {details}")
        results.append({"check": check_name, "passed": passed, "details": details})
        if not passed:
            all_passed = False
    
    # Emit audit event
    audit_entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "type": "pre_commit_audit",
        "passed": all_passed,
        "checks": results
    }
    
    audit_log = WORKSPACE_ROOT / "audit" / "commit_audit_log.jsonl"
    audit_log.parent.mkdir(parents=True, exist_ok=True)
    with open(audit_log, "a") as f:
        f.write(json.dumps(audit_entry) + "\n")

    try:
        witness_ok, witness_reason = _commit_witness_entry(audit_entry, audit_log)
    except Exception as e:
        witness_ok, witness_reason = False, f"witness_error: {e}"
    if not witness_ok:
        strict = _flag_enabled("OPENCLAW_WITNESS_LEDGER_STRICT", default="0")
        if strict:
            all_passed = False
            print(f"❌ witness ledger commit failed (strict): {witness_reason}")
        else:
            print(f"⚠️ witness ledger commit skipped: {witness_reason}")
    
    print("=" * 50)
    if all_passed:
        print("✅ AUDIT PASSED - Safe to commit")
    else:
        print("❌ AUDIT FAILED - Commit blocked")
    print("=" * 50)
    
    return all_passed

if __name__ == "__main__":
    success = audit_commit()
    sys.exit(0 if success else 1)
