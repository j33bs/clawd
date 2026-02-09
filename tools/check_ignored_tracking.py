from __future__ import annotations

import subprocess
import sys

IGNORED_ROOTS = (
    "scripts/",
    "pipelines/",
    "sim/",
    "market/",
    "itc/",
    "telegram/",
)

ALLOWLIST = {
    "scripts/sim_runner.py",
    "pipelines/system1_trading.features.yaml",
}


def run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True)


def main() -> int:
    proc = run(["git", "diff", "--name-only", "--cached"])
    if proc.returncode != 0:
        print("ERROR: git diff --cached failed", file=sys.stderr)
        return 1

    staged = [line.strip() for line in proc.stdout.splitlines() if line.strip()]
    if not staged:
        return 0

    violations = []
    for path in staged:
        norm = path.replace("\\", "/")
        if norm in ALLOWLIST:
            continue
        for root in IGNORED_ROOTS:
            if norm.startswith(root):
                violations.append(norm)
                break

    if violations:
        print("FAIL: attempted to track files under ignored roots", file=sys.stderr)
        for v in violations:
            print(f"  - {v}", file=sys.stderr)
        print("Allowlist updates require a [GOV] change.", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
