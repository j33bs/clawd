from __future__ import annotations

import subprocess
import sys


def run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True)


def branch_exists(name: str) -> bool:
    proc = run(["git", "show-ref", "--verify", "--quiet", f"refs/heads/{name}"])
    return proc.returncode == 0


def current_branch() -> str:
    proc = run(["git", "rev-parse", "--abbrev-ref", "HEAD"])
    if proc.returncode != 0:
        print("ERROR: unable to resolve current branch", file=sys.stderr)
        sys.exit(1)
    return proc.stdout.strip()


def main() -> int:
    cur = current_branch()
    default = None
    for candidate in ("develop", "main", "master"):
        if branch_exists(candidate):
            default = candidate
            break

    if default is None:
        print(f"CURRENT={cur}")
        print("DEFAULT=")
        print("ERROR: no default branch found", file=sys.stderr)
        return 1

    print(f"CURRENT={cur}")
    print(f"DEFAULT={default}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
