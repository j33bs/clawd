from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Tuple

ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT / "reports" / "reviews"


def run(cmd: List[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True)


def get_branch() -> str:
    proc = run(["git", "rev-parse", "--abbrev-ref", "HEAD"])
    return proc.stdout.strip() if proc.returncode == 0 else "unknown"


def get_status() -> List[str]:
    proc = run(["git", "status", "--porcelain"])
    if proc.returncode != 0:
        return []
    return [line.rstrip() for line in proc.stdout.splitlines() if line.strip()]


def get_diff_stat() -> str:
    proc = run(["git", "diff", "--stat"])
    if proc.returncode != 0:
        return ""
    return proc.stdout.strip()


def get_untracked(limit: int = 200) -> List[str]:
    proc = run(["git", "ls-files", "--others", "--exclude-standard"])
    if proc.returncode != 0:
        return []
    files = [line.strip() for line in proc.stdout.splitlines() if line.strip()]
    return files[:limit]


def classify_path(path: str) -> Tuple[str, str]:
    norm = path.replace("\\", "/")
    if "secrets" in norm or norm.endswith(".env") or "credentials" in norm:
        return ("secret-risk", "high")
    if norm.startswith("workspace/"):
        return ("gov", "high")
    if norm.startswith("reports/") or norm.startswith("docs/"):
        return ("docs", "low")
    if norm.startswith("pipelines/") or norm == "openclaw.json" or norm == "secrets.env.template":
        return ("config", "med")
    if norm.startswith("core_infra/") or norm.startswith("tools/") or norm.startswith("scripts/"):
        return ("code", "med")
    if norm.startswith("economics/") or norm.startswith("sim/") or norm.startswith("market/") or norm.startswith("itc/"):
        return ("artifact", "low")
    return ("other", "low")


def main() -> int:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    now = datetime.now(timezone.utc)
    stamp = now.strftime("%Y%m%d-%H%M")
    quarantine_branch = f"quarantine/incoming-{stamp}"

    # Create quarantine branch name (no checkout)
    run(["git", "branch", quarantine_branch])

    status = get_status()
    diff_stat = get_diff_stat()
    untracked = get_untracked()

    paths = set()
    for line in status:
        parts = line.split()
        if len(parts) >= 2:
            paths.add(parts[-1])
    for p in untracked:
        paths.add(p)

    report_path = REPORT_DIR / f"review-{stamp}.md"

    meta = {
        "generated_at": now.isoformat(),
        "current_branch": get_branch(),
        "quarantine_branch": quarantine_branch,
        "status_count": len(status),
        "untracked_count": len(untracked),
    }

    lines: List[str] = []
    lines.append("# Quarantine Review")
    lines.append("")
    lines.append("```json")
    lines.append(json.dumps(meta, indent=2))
    lines.append("```")
    lines.append("")
    lines.append(f"**Current branch**: `{meta['current_branch']}`")
    lines.append(f"**Quarantine branch**: `{quarantine_branch}`")
    lines.append("")

    lines.append("## git status --porcelain")
    lines.append("```")
    lines.extend(status if status else ["<clean>"])
    lines.append("```")
    lines.append("")

    lines.append("## git diff --stat")
    lines.append("```")
    lines.append(diff_stat if diff_stat else "<no diff>")
    lines.append("```")
    lines.append("")

    lines.append("## Untracked (first 200)")
    lines.append("```")
    lines.extend(untracked if untracked else ["<none>"])
    lines.append("```")
    lines.append("")

    lines.append("## Classification")
    lines.append("| path | type | risk | admit/reject/defer | rationale |")
    lines.append("|---|---|---|---|---|")
    if paths:
        for p in sorted(paths):
            typ, risk = classify_path(p)
            lines.append(f"| {p} | {typ} | {risk} | defer | TBD |")
    else:
        lines.append("| <none> | - | - | - | - |")

    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"REPORT={report_path}")
    print(f"QUARANTINE_BRANCH={quarantine_branch}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
