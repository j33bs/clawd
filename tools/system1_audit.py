#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Step:
    name: str
    command: list[str]


@dataclass
class StepResult:
    step: Step
    returncode: int
    output: str


def run_step(step: Step, repo_root: Path) -> StepResult:
    proc = subprocess.run(
        step.command,
        cwd=repo_root,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    return StepResult(step=step, returncode=proc.returncode, output=proc.stdout)


def build_log(results: list[StepResult]) -> str:
    chunks: list[str] = []
    for result in results:
        chunks.append(f"$ {' '.join(result.step.command)}")
        chunks.append(f"exit_code={result.returncode}")
        if result.output:
            chunks.append(result.output.rstrip())
        chunks.append("")
    return "\n".join(chunks).rstrip() + "\n"


def build_evidence(results: list[StepResult]) -> dict[str, object]:
    total = len(results)
    passed = sum(1 for r in results if r.returncode == 0)
    gate_result = "pass" if passed == total else "fail"
    completion_rate = float(passed / total) if total else 0.0
    return {
        "gate_result": gate_result,
        "completion_rate": completion_rate,
        "traces": total,
        "smoke_log_truncated": False,
        "steps": [
            {
                "name": r.step.name,
                "returncode": r.returncode,
                "command": r.step.command,
            }
            for r in results
        ],
    }


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the System-1 local audit gate.")
    parser.add_argument("--repo-root", default=".", help="Repository root path.")
    parser.add_argument(
        "--output-json",
        default=".tmp/system1_evidence/system1_audit_evidence.json",
        help="Path for machine-readable evidence JSON.",
    )
    parser.add_argument(
        "--output-log",
        default=".tmp/system1_evidence/system1_audit_output.txt",
        help="Path for audit command output log.",
    )
    parser.add_argument(
        "--summary-text",
        default=".tmp/system1_evidence/system1_audit_summary.txt",
        help="Path for human summary text.",
    )
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    output_json = (repo_root / args.output_json).resolve() if not Path(args.output_json).is_absolute() else Path(args.output_json)
    output_log = (repo_root / args.output_log).resolve() if not Path(args.output_log).is_absolute() else Path(args.output_log)
    summary_text = (repo_root / args.summary_text).resolve() if not Path(args.summary_text).is_absolute() else Path(args.summary_text)

    steps = [
        Step("preflight", ["python3", "workspace/scripts/preflight_check.py"]),
        Step("unit_tests", ["python3", "-m", "unittest", "discover", "-s", "tests_unittest"]),
        Step("verify", ["bash", "workspace/scripts/verify.sh"]),
    ]
    results: list[StepResult] = []
    for step in steps:
        result = run_step(step, repo_root)
        results.append(result)

    evidence = build_evidence(results)
    write_json(output_json, evidence)
    write_text(output_log, build_log(results))
    summary = (
        f"gate_result: {evidence['gate_result']}\n"
        f"completion_rate: {evidence['completion_rate']}\n"
        f"traces: {evidence['traces']}\n"
        f"smoke_log_truncated: {str(evidence['smoke_log_truncated']).lower()}\n"
    )
    write_text(summary_text, summary)
    sys.stdout.write(summary)

    return 0 if evidence["gate_result"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
