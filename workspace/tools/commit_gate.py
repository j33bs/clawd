#!/usr/bin/env python3
"""INV-004 Commit Gate (novelty + evidence + isolation logging)."""
from __future__ import annotations

import argparse
import json
import math
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from importlib import metadata
from pathlib import Path
from typing import Protocol, Sequence

DEFAULT_THETA = 0.15
DEFAULT_EMBEDDER = "sentence-transformers/all-MiniLM-L6-v2"
DEFAULT_FRICTION_TASK = (
    "Produce a 6-line governance memo that (a) preserves append-only/auditability and "
    "(b) must fit under 200 tokens, AND must include at least one falsifiable test plus "
    "one explicit non-goal."
)
JOINT_TAG = "[JOINT: c_lawd + dali]"


class Embedder(Protocol):
    model_name: str
    library_name: str
    library_version: str

    def encode(self, texts: Sequence[str]) -> list[list[float]]:
        """Return one embedding vector per input text."""


@dataclass
class GateDecision:
    mode: str
    theta: float
    isolation_verified: bool
    isolation_evidence: str
    joint_tag_present: bool
    dist_joint_dali: float
    dist_joint_clawd: float
    min_dist: float
    novelty_pass: bool
    overall_pass: bool
    failure_reasons: list[str]
    audit_note_path: Path
    run_artifact_dir: Path
    embed_model: str
    embed_version: str


class SentenceTransformersEmbedder:
    """Runtime embedder adapter with explicit model/version recording."""

    def __init__(self, embedder_name: str) -> None:
        if not embedder_name.startswith("sentence-transformers/"):
            raise ValueError(
                "Unsupported embedder. Expected sentence-transformers/<model>. "
                f"Got: {embedder_name}"
            )
        self.model_name = embedder_name
        self.model_id = embedder_name.split("/", 1)[1]
        self.library_name = "sentence-transformers"
        try:
            self.library_version = metadata.version("sentence-transformers")
        except metadata.PackageNotFoundError:
            self.library_version = "unknown"

        # Deferred import to keep CLI lightweight until embeddings are required.
        from sentence_transformers import SentenceTransformer  # type: ignore

        self._model = SentenceTransformer(self.model_id)

    def encode(self, texts: Sequence[str]) -> list[list[float]]:
        vectors = self._model.encode(list(texts), show_progress_bar=False)
        return [list(map(float, v)) for v in vectors]


def _repo_root_from_file(this_file: Path | None = None) -> Path:
    file_path = this_file or Path(__file__).resolve()
    return file_path.parents[2]


def _workspace_root_from_file(this_file: Path | None = None) -> Path:
    file_path = this_file or Path(__file__).resolve()
    return file_path.parents[1]


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _parse_bool(value: str) -> bool:
    lowered = value.strip().lower()
    if lowered in {"1", "true", "yes", "y"}:
        return True
    if lowered in {"0", "false", "no", "n"}:
        return False
    raise argparse.ArgumentTypeError(f"Invalid boolean value: {value}")


def _extract_memo_body(text: str) -> str:
    numbered = []
    for line in text.splitlines():
        stripped = line.strip()
        if len(stripped) >= 3 and stripped[0].isdigit() and stripped[1] == ")":
            numbered.append(stripped)
    if numbered:
        return "\n".join(numbered)
    return text.strip()


def _load_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _normalize(vec: Sequence[float]) -> list[float]:
    norm = math.sqrt(sum(v * v for v in vec))
    if norm == 0:
        return [0.0 for _ in vec]
    return [v / norm for v in vec]


def cosine_distance(vec_a: Sequence[float], vec_b: Sequence[float]) -> float:
    if len(vec_a) != len(vec_b):
        raise ValueError("Embedding dimension mismatch")
    a = _normalize(vec_a)
    b = _normalize(vec_b)
    similarity = sum(x * y for x, y in zip(a, b))
    similarity = max(-1.0, min(1.0, similarity))
    return 1.0 - similarity


def _extract_task_from_spec(spec_text: str) -> str:
    for line in spec_text.splitlines():
        stripped = line.strip()
        if stripped.startswith(">"):
            return stripped[1:].strip()
    return DEFAULT_FRICTION_TASK


def _resolve_input_files(inputs: str, repo_root: Path) -> tuple[Path, Path, Path]:
    raw = inputs.strip()
    candidate = Path(raw)
    if not candidate.is_absolute():
        candidate = repo_root / raw

    paths: list[Path]
    if candidate.exists() and candidate.is_dir():
        dali = candidate / "dali_output.md"
        clawd = candidate / "clawd_output.md"
        joint = candidate / "joint_output.md"
        paths = [dali, clawd, joint]
    else:
        entries = [p.strip() for p in raw.split(",") if p.strip()]
        if len(entries) != 3:
            raise ValueError(
                "--inputs must be a directory containing dali/clawd/joint files or a comma-separated list of three paths"
            )
        paths = []
        for entry in entries:
            p = Path(entry)
            if not p.is_absolute():
                p = repo_root / entry
            paths.append(p)

    for p in paths:
        if not p.exists():
            raise FileNotFoundError(f"Missing input file: {p}")

    mapped: dict[str, Path] = {}
    for p in paths:
        name = p.name.lower()
        if "joint" in name:
            mapped["joint"] = p
        elif "clawd" in name:
            mapped["clawd"] = p
        elif "dali" in name:
            mapped["dali"] = p

    if len(mapped) == 3:
        return mapped["dali"], mapped["clawd"], mapped["joint"]

    # Positional fallback for explicit path lists.
    return paths[0], paths[1], paths[2]


def _copy_inputs(run_dir: Path, dali_path: Path, clawd_path: Path, joint_path: Path) -> tuple[Path, Path, Path]:
    run_dir.mkdir(parents=True, exist_ok=True)
    dali_dst = run_dir / "dali_output.md"
    clawd_dst = run_dir / "clawd_output.md"
    joint_dst = run_dir / "joint_output.md"
    shutil.copy2(dali_path, dali_dst)
    shutil.copy2(clawd_path, clawd_dst)
    shutil.copy2(joint_path, joint_dst)
    return dali_dst, clawd_dst, joint_dst


def _write_audit(
    audit_path: Path,
    run_id: str,
    friction_task: str,
    mode: str,
    decision: GateDecision,
    dali_rel: Path,
    clawd_rel: Path,
    joint_rel: Path,
) -> None:
    results_table = (
        "| Check | Value |\n"
        "|---|---|\n"
        f"| mode | {mode} |\n"
        f"| isolation_verified | {str(decision.isolation_verified).lower()} |\n"
        f"| joint_tag_present | {str(decision.joint_tag_present).lower()} |\n"
        f"| embed_model | {decision.embed_model} |\n"
        f"| embed_version | {decision.embed_version} |\n"
        f"| theta | {decision.theta:.6f} |\n"
        f"| dist_joint_dali | {decision.dist_joint_dali:.12f} |\n"
        f"| dist_joint_clawd | {decision.dist_joint_clawd:.12f} |\n"
        f"| min_dist | {decision.min_dist:.12f} |\n"
        f"| novelty_pass | {str(decision.novelty_pass).lower()} |\n"
        f"| result | {'PASS' if decision.overall_pass else 'FAIL'} |\n"
    )

    reasons = "\n".join(f"- {reason}" for reason in decision.failure_reasons)
    if not reasons:
        reasons = "- none"

    body = f"""# INV-004 Commit Gate Run: {run_id}

- timestamp_utc: {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}
- run_id: {run_id}
- friction_task: {friction_task}
- mode: {mode}
- isolation_verified: {str(decision.isolation_verified).lower()}
- isolation_evidence: {decision.isolation_evidence}
- embed_model: {decision.embed_model}
- embed_version: {decision.embed_version}
- theta: {decision.theta:.6f}
- dist_joint_dali: {decision.dist_joint_dali:.12f}
- dist_joint_clawd: {decision.dist_joint_clawd:.12f}
- min_dist: {decision.min_dist:.12f}
- novelty_pass: {str(decision.novelty_pass).lower()}
- result: {'PASS' if decision.overall_pass else 'FAIL'}

## Inputs

- dali: `{dali_rel}`
- clawd: `{clawd_rel}`
- joint: `{joint_rel}`

## Results

{results_table}

## Failure Reasons

{reasons}
"""

    audit_path.write_text(body, encoding="utf-8")


def run_inv004(
    *,
    run_id: str,
    mode: str,
    theta: float,
    embedder_name: str,
    inputs: str,
    isolation_verified: bool,
    isolation_evidence: str,
    friction_task: str | None = None,
    spec_path: Path | None = None,
    repo_root: Path | None = None,
    workspace_root: Path | None = None,
    embedder: Embedder | None = None,
) -> GateDecision:
    if mode not in {"dry", "enforce"}:
        raise ValueError("mode must be one of: dry, enforce")
    if theta < 0:
        raise ValueError("theta must be >= 0")

    repo_root = repo_root or _repo_root_from_file()
    workspace_root = workspace_root or _workspace_root_from_file()
    spec_path = spec_path or (workspace_root / "governance" / "INV-004_commit_gate_spec.md")

    if not spec_path.exists():
        raise FileNotFoundError(
            f"Missing canonical spec: {spec_path}. Create it from the approved source before running INV-004 commit gate."
        )

    task_text = friction_task or _extract_task_from_spec(_load_text(spec_path))

    dali_src, clawd_src, joint_src = _resolve_input_files(inputs, repo_root)
    run_artifact_dir = workspace_root / "artifacts" / "inv004" / run_id
    dali_path, clawd_path, joint_path = _copy_inputs(run_artifact_dir, dali_src, clawd_src, joint_src)

    dali_text = _load_text(dali_path)
    clawd_text = _load_text(clawd_path)
    joint_text = _load_text(joint_path)

    dali_body = _extract_memo_body(dali_text)
    clawd_body = _extract_memo_body(clawd_text)
    joint_body = _extract_memo_body(joint_text)

    active_embedder = embedder or SentenceTransformersEmbedder(embedder_name)
    vectors = active_embedder.encode([joint_body, dali_body, clawd_body])
    dist_joint_dali = cosine_distance(vectors[0], vectors[1])
    dist_joint_clawd = cosine_distance(vectors[0], vectors[2])
    min_dist = min(dist_joint_dali, dist_joint_clawd)

    novelty_pass = min_dist >= theta
    joint_tag_present = JOINT_TAG in joint_text
    evidence_present = bool(isolation_evidence.strip())

    failure_reasons: list[str] = []
    if not novelty_pass:
        failure_reasons.append(
            f"Novelty threshold not met: min_dist={min_dist:.6f} < theta={theta:.6f}"
        )
    if not joint_tag_present:
        failure_reasons.append(f"Joint output missing required tag: {JOINT_TAG}")
    if not evidence_present:
        failure_reasons.append("Isolation evidence note is required")
    if mode == "enforce" and not isolation_verified:
        failure_reasons.append("Enforce mode requires isolation_verified=true")

    overall_pass = not failure_reasons

    timestamp = _utc_timestamp()
    audit_dir = workspace_root / "audit"
    audit_dir.mkdir(parents=True, exist_ok=True)
    audit_path = audit_dir / f"inv004_{run_id}_{timestamp}.md"

    embed_model = getattr(active_embedder, "model_name", embedder_name)
    embed_version = getattr(active_embedder, "library_version", "unknown")

    decision = GateDecision(
        mode=mode,
        theta=theta,
        isolation_verified=isolation_verified,
        isolation_evidence=isolation_evidence.strip(),
        joint_tag_present=joint_tag_present,
        dist_joint_dali=dist_joint_dali,
        dist_joint_clawd=dist_joint_clawd,
        min_dist=min_dist,
        novelty_pass=novelty_pass,
        overall_pass=overall_pass,
        failure_reasons=failure_reasons,
        audit_note_path=audit_path,
        run_artifact_dir=run_artifact_dir,
        embed_model=embed_model,
        embed_version=embed_version,
    )

    _write_audit(
        audit_path=audit_path,
        run_id=run_id,
        friction_task=task_text,
        mode=mode,
        decision=decision,
        dali_rel=dali_path.relative_to(workspace_root),
        clawd_rel=clawd_path.relative_to(workspace_root),
        joint_rel=joint_path.relative_to(workspace_root),
    )

    result_json = run_artifact_dir / "result.json"
    result_json.write_text(
        json.dumps(
            {
                "run_id": run_id,
                "mode": mode,
                "theta": theta,
                "isolation_verified": isolation_verified,
                "isolation_evidence": isolation_evidence.strip(),
                "joint_tag_present": joint_tag_present,
                "dist_joint_dali": dist_joint_dali,
                "dist_joint_clawd": dist_joint_clawd,
                "min_dist": min_dist,
                "novelty_pass": novelty_pass,
                "overall_pass": overall_pass,
                "failure_reasons": failure_reasons,
                "embed_model": embed_model,
                "embed_version": embed_version,
                "audit_note": str(audit_path.relative_to(workspace_root)),
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    return decision


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="INV-004 commit gate")
    subparsers = parser.add_subparsers(dest="command", required=True)

    inv004 = subparsers.add_parser("inv004", help="Run INV-004 commit gate")
    inv004.add_argument("--run-id", required=True, help="Unique run identifier")
    inv004.add_argument("--mode", choices=["dry", "enforce"], required=True)
    inv004.add_argument("--theta", type=float, default=DEFAULT_THETA)
    inv004.add_argument("--embedder", default=DEFAULT_EMBEDDER)
    inv004.add_argument(
        "--inputs",
        required=True,
        help=(
            "Directory containing dali_output.md/clawd_output.md/joint_output.md "
            "or comma-separated list of three file paths"
        ),
    )
    inv004.add_argument(
        "--isolation-verified",
        required=True,
        type=_parse_bool,
        help="Operator assertion for Amendment A isolation compliance (true/false)",
    )
    inv004.add_argument(
        "--isolation-evidence",
        required=True,
        help="Required operator evidence note for isolation claim",
    )
    inv004.add_argument(
        "--task",
        default=None,
        help="Optional explicit friction task statement; otherwise extracted from spec",
    )
    inv004.add_argument(
        "--spec-path",
        default="workspace/governance/INV-004_commit_gate_spec.md",
        help="Path to canonical in-repo spec",
    )

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command != "inv004":
        parser.error("Unsupported command")

    repo_root = _repo_root_from_file()
    workspace_root = _workspace_root_from_file()
    spec_path = Path(args.spec_path)
    if not spec_path.is_absolute():
        spec_path = repo_root / args.spec_path

    decision = run_inv004(
        run_id=args.run_id,
        mode=args.mode,
        theta=args.theta,
        embedder_name=args.embedder,
        inputs=args.inputs,
        isolation_verified=args.isolation_verified,
        isolation_evidence=args.isolation_evidence,
        friction_task=args.task,
        spec_path=spec_path,
        repo_root=repo_root,
        workspace_root=workspace_root,
    )

    print("INV-004 commit gate")
    print(f"  mode: {decision.mode}")
    print(f"  audit_note: {decision.audit_note_path}")
    print(f"  run_artifacts: {decision.run_artifact_dir}")
    print(f"  joint_tag_present: {'PASS' if decision.joint_tag_present else 'FAIL'}")
    print(f"  novelty: {'PASS' if decision.novelty_pass else 'FAIL'} (min_dist={decision.min_dist:.6f}, theta={decision.theta:.6f})")
    if args.mode == "enforce":
        print(f"  isolation_enforced: {'PASS' if decision.isolation_verified else 'FAIL'}")
    print(f"  result: {'PASS' if decision.overall_pass else 'FAIL'}")
    if decision.failure_reasons:
        print("  rationale:")
        for reason in decision.failure_reasons:
            print(f"    - {reason}")

    if args.mode == "enforce" and not decision.overall_pass:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
