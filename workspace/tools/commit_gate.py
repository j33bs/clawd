#!/usr/bin/env python3
"""INV-004 Commit Gate (novelty + evidence + isolation logging)."""
from __future__ import annotations

import argparse
import json
import math
import os
import platform
import re
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from importlib import metadata
from pathlib import Path
from typing import Any, Protocol, Sequence

DEFAULT_THETA = 0.15
DEFAULT_EMBEDDER = "sentence-transformers/all-MiniLM-L6-v2"
DEFAULT_FRICTION_TASK = (
    "Produce a 6-line governance memo that (a) preserves append-only/auditability and "
    "(b) must fit under 200 tokens, AND must include at least one falsifiable test plus "
    "one explicit non-goal."
)
JOINT_TAG = "[JOINT: c_lawd + dali]"
SANITIZER_RULES_VERSION = "inv004-sanitizer-v1"
STATUS_TAG_PATTERNS = (
    "EXPERIMENT PENDING",
    "GOVERNANCE RULE CANDIDATE",
    "PHILOSOPHICAL ONLY",
)


class OfflineModelUnavailableError(RuntimeError):
    """Raised when offline model loading is required but unavailable."""


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
    require_offline_model: bool
    joint_tag_present: bool
    dist_joint_dali: float | None
    dist_joint_clawd: float | None
    min_dist: float | None
    novelty_pass: bool
    overall_pass: bool
    failure_reasons: list[str]
    audit_note_path: Path
    run_artifact_dir: Path
    embed_model: str
    embed_version: str
    embed_error: str | None
    embedding_input_sanitized: bool
    sanitizer_rules_version: str
    python_version: str
    platform: str
    sentence_transformers_version: str
    transformers_version: str
    torch_version: str


class SentenceTransformersEmbedder:
    """Runtime embedder adapter with explicit model/version recording."""

    def __init__(self, embedder_name: str, require_offline_model: bool = False) -> None:
        if not embedder_name.startswith("sentence-transformers/"):
            raise ValueError(
                "Unsupported embedder. Expected sentence-transformers/<model>. "
                f"Got: {embedder_name}"
            )
        self.model_name = embedder_name
        self.model_id = embedder_name.split("/", 1)[1]
        self.library_name = "sentence-transformers"
        self.library_version = _pkg_version("sentence-transformers")

        if require_offline_model:
            # Explicit offline enforcement, no network downloads.
            os.environ["HF_HUB_OFFLINE"] = "1"
            os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

        # Deferred import to keep CLI lightweight until embeddings are required.
        from sentence_transformers import SentenceTransformer  # type: ignore

        try:
            kwargs: dict[str, Any] = {}
            if require_offline_model:
                kwargs["local_files_only"] = True
            self._model = SentenceTransformer(self.model_id, **kwargs)
        except Exception as exc:  # pragma: no cover - exercised via run_inv004 tests.
            if require_offline_model:
                raise OfflineModelUnavailableError(
                    f"offline model not available for embedder '{embedder_name}': {exc}"
                ) from exc
            raise

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


def _parse_optional_bool(value: str | None) -> bool | None:
    if value is None:
        return None
    return _parse_bool(value)


def _extract_memo_body(text: str) -> str:
    numbered = []
    for line in text.splitlines():
        stripped = line.strip()
        if len(stripped) >= 3 and stripped[0].isdigit() and stripped[1] == ")":
            numbered.append(stripped)
    if numbered:
        return "\n".join(numbered)
    return text.strip()


def sanitize_for_embedding(text: str) -> str:
    """Remove governance tags/status phrases to avoid tag-Goodhart leakage."""
    lines: list[str] = []
    status_pattern = re.compile(
        "|".join(re.escape(tag) for tag in STATUS_TAG_PATTERNS),
        flags=re.IGNORECASE,
    )

    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        # Remove one or more leading [UPPER:...] tokens.
        line = re.sub(r"^(?:\[[A-Z][A-Z0-9_-]*:[^\]]+\]\s*)+", "", line)
        # Remove inline EXEC/JOINT tags and generic bracket governance tags.
        line = re.sub(r"\[(?:EXEC|JOINT):[^\]]+\]", "", line, flags=re.IGNORECASE)
        line = re.sub(r"\[[A-Z][A-Z0-9_-]*:[^\]]+\]", "", line)
        # Remove known governance status strings.
        line = status_pattern.sub("", line)
        line = " ".join(line.split())
        if line:
            lines.append(line)

    return "\n".join(lines).strip()


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


def _resolve_calibration_inputs(inputs: str, repo_root: Path) -> tuple[Path, Path, Path | None]:
    raw = inputs.strip()
    candidate = Path(raw)
    if not candidate.is_absolute():
        candidate = repo_root / raw

    if not candidate.exists() or not candidate.is_dir():
        raise ValueError("--inputs must point to a directory for inv004-calibrate")

    dali = candidate / "dali_output.md"
    clawd = candidate / "clawd_output.md"
    joint = candidate / "joint_output.md"

    if not dali.exists() or not clawd.exists():
        raise FileNotFoundError(
            f"Calibration requires dali_output.md and clawd_output.md in {candidate}"
        )

    return dali, clawd, (joint if joint.exists() else None)


def _copy_inputs(run_dir: Path, dali_path: Path, clawd_path: Path, joint_path: Path) -> tuple[Path, Path, Path]:
    run_dir.mkdir(parents=True, exist_ok=True)
    dali_dst = run_dir / "dali_output.md"
    clawd_dst = run_dir / "clawd_output.md"
    joint_dst = run_dir / "joint_output.md"
    shutil.copy2(dali_path, dali_dst)
    shutil.copy2(clawd_path, clawd_dst)
    shutil.copy2(joint_path, joint_dst)
    return dali_dst, clawd_dst, joint_dst


def _pkg_version(package_name: str) -> str:
    try:
        return metadata.version(package_name)
    except metadata.PackageNotFoundError:
        return "unknown"


def _runtime_identity(embedder_id: str) -> dict[str, str]:
    return {
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "sentence_transformers_version": _pkg_version("sentence-transformers"),
        "transformers_version": _pkg_version("transformers"),
        "torch_version": _pkg_version("torch"),
        "embedder_id": embedder_id,
    }


def load_embedder(
    embedder_name: str,
    *,
    require_offline_model: bool,
    embedder: Embedder | None = None,
) -> Embedder:
    if embedder is not None:
        return embedder
    return SentenceTransformersEmbedder(
        embedder_name,
        require_offline_model=require_offline_model,
    )


def _fmt_num(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:.12f}"


def _write_audit(
    audit_path: Path,
    run_id: str,
    friction_task: str,
    decision: GateDecision,
    dali_rel: Path,
    clawd_rel: Path,
    joint_rel: Path,
) -> None:
    results_table = (
        "| Check | Value |\n"
        "|---|---|\n"
        f"| mode | {decision.mode} |\n"
        f"| isolation_verified | {str(decision.isolation_verified).lower()} |\n"
        f"| joint_tag_present | {str(decision.joint_tag_present).lower()} |\n"
        f"| require_offline_model | {str(decision.require_offline_model).lower()} |\n"
        f"| embedding_input_sanitized | {str(decision.embedding_input_sanitized).lower()} |\n"
        f"| sanitizer_rules_version | {decision.sanitizer_rules_version} |\n"
        f"| embed_model | {decision.embed_model} |\n"
        f"| embed_version | {decision.embed_version} |\n"
        f"| theta | {decision.theta:.6f} |\n"
        f"| dist_joint_dali | {_fmt_num(decision.dist_joint_dali)} |\n"
        f"| dist_joint_clawd | {_fmt_num(decision.dist_joint_clawd)} |\n"
        f"| min_dist | {_fmt_num(decision.min_dist)} |\n"
        f"| novelty_pass | {str(decision.novelty_pass).lower()} |\n"
        f"| result | {'PASS' if decision.overall_pass else 'FAIL'} |\n"
    )

    reasons = "\n".join(f"- {reason}" for reason in decision.failure_reasons)
    if not reasons:
        reasons = "- none"

    embed_error_line = decision.embed_error or "none"

    body = f"""# INV-004 Commit Gate Run: {run_id}

- timestamp_utc: {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}
- run_id: {run_id}
- friction_task: {friction_task}
- mode: {decision.mode}
- isolation_verified: {str(decision.isolation_verified).lower()}
- isolation_evidence: {decision.isolation_evidence}
- require_offline_model: {str(decision.require_offline_model).lower()}
- embedding_input_sanitized: {str(decision.embedding_input_sanitized).lower()}
- sanitizer_rules_version: {decision.sanitizer_rules_version}
- embed_model: {decision.embed_model}
- embed_version: {decision.embed_version}
- theta: {decision.theta:.6f}
- dist_joint_dali: {_fmt_num(decision.dist_joint_dali)}
- dist_joint_clawd: {_fmt_num(decision.dist_joint_clawd)}
- min_dist: {_fmt_num(decision.min_dist)}
- novelty_pass: {str(decision.novelty_pass).lower()}
- result: {'PASS' if decision.overall_pass else 'FAIL'}
- embed_error: {embed_error_line}

## Environment

- python_version: {decision.python_version}
- platform: {decision.platform}
- sentence_transformers_version: {decision.sentence_transformers_version}
- transformers_version: {decision.transformers_version}
- torch_version: {decision.torch_version}
- embedder_id: {decision.embed_model}

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


def _write_calibration_audit(
    *,
    workspace_root: Path,
    embedder_id: str,
    out_rel: Path,
    recommended_theta: float,
    runtime: dict[str, str],
) -> Path:
    audit_dir = workspace_root / "audit"
    audit_dir.mkdir(parents=True, exist_ok=True)
    audit_path = audit_dir / f"inv004_calibration_{_utc_timestamp()}.md"
    body = f"""# INV-004 Calibration Run

- timestamp_utc: {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}
- embedder_id: {embedder_id}
- recommended_theta: {recommended_theta:.12f}
- baseline_path: {out_rel}
- embedding_input_sanitized: true
- sanitizer_rules_version: {SANITIZER_RULES_VERSION}

## Environment

- python_version: {runtime['python_version']}
- platform: {runtime['platform']}
- sentence_transformers_version: {runtime['sentence_transformers_version']}
- transformers_version: {runtime['transformers_version']}
- torch_version: {runtime['torch_version']}
"""
    audit_path.write_text(body, encoding="utf-8")
    return audit_path


def run_inv004(
    *,
    run_id: str,
    mode: str,
    theta: float,
    embedder_name: str,
    inputs: str,
    isolation_verified: bool,
    isolation_evidence: str,
    require_offline_model: bool | None = None,
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

    effective_require_offline = (
        mode == "enforce" if require_offline_model is None else require_offline_model
    )
    if mode == "enforce":
        effective_require_offline = True

    repo_root = repo_root or _repo_root_from_file()
    workspace_root = workspace_root or _workspace_root_from_file()
    spec_path = spec_path or (workspace_root / "governance" / "INV-004_commit_gate_spec.md")

    if not spec_path.exists():
        raise FileNotFoundError(
            f"Missing canonical spec: {spec_path}. Create it from the approved source before running INV-004 commit gate."
        )

    runtime = _runtime_identity(embedder_name)
    task_text = friction_task or _extract_task_from_spec(_load_text(spec_path))

    dali_src, clawd_src, joint_src = _resolve_input_files(inputs, repo_root)
    run_artifact_dir = workspace_root / "artifacts" / "inv004" / run_id
    dali_path, clawd_path, joint_path = _copy_inputs(run_artifact_dir, dali_src, clawd_src, joint_src)

    dali_text = _load_text(dali_path)
    clawd_text = _load_text(clawd_path)
    joint_text = _load_text(joint_path)

    dali_body = sanitize_for_embedding(_extract_memo_body(dali_text))
    clawd_body = sanitize_for_embedding(_extract_memo_body(clawd_text))
    joint_body = sanitize_for_embedding(_extract_memo_body(joint_text))

    joint_tag_present = JOINT_TAG in joint_text
    evidence_present = bool(isolation_evidence.strip())

    failure_reasons: list[str] = []
    if mode == "enforce" and not isolation_verified:
        failure_reasons.append("Enforce mode requires isolation_verified=true")
    if mode == "enforce" and not evidence_present:
        failure_reasons.append("Enforce mode requires non-empty isolation_evidence")
    if not joint_tag_present:
        failure_reasons.append(f"Joint output missing required tag: {JOINT_TAG}")

    dist_joint_dali: float | None = None
    dist_joint_clawd: float | None = None
    min_dist: float | None = None
    novelty_pass = False
    embed_error: str | None = None

    active_embedder: Embedder | None = None
    try:
        active_embedder = load_embedder(
            embedder_name,
            require_offline_model=effective_require_offline,
            embedder=embedder,
        )
        vectors = active_embedder.encode([joint_body, dali_body, clawd_body])
        dist_joint_dali = cosine_distance(vectors[0], vectors[1])
        dist_joint_clawd = cosine_distance(vectors[0], vectors[2])
        min_dist = min(dist_joint_dali, dist_joint_clawd)
        novelty_pass = min_dist >= theta
        if not novelty_pass:
            failure_reasons.append(
                f"Novelty threshold not met: min_dist={min_dist:.6f} < theta={theta:.6f}"
            )
    except OfflineModelUnavailableError as exc:
        embed_error = str(exc)
        failure_reasons.append(embed_error)
    except Exception as exc:
        embed_error = f"embedding execution failed: {exc}"
        failure_reasons.append(embed_error)

    overall_pass = not failure_reasons

    timestamp = _utc_timestamp()
    audit_dir = workspace_root / "audit"
    audit_dir.mkdir(parents=True, exist_ok=True)
    audit_path = audit_dir / f"inv004_{run_id}_{timestamp}.md"

    embed_model = getattr(active_embedder, "model_name", embedder_name)
    embed_version = getattr(active_embedder, "library_version", runtime["sentence_transformers_version"])

    decision = GateDecision(
        mode=mode,
        theta=theta,
        isolation_verified=isolation_verified,
        isolation_evidence=isolation_evidence.strip(),
        require_offline_model=effective_require_offline,
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
        embed_error=embed_error,
        embedding_input_sanitized=True,
        sanitizer_rules_version=SANITIZER_RULES_VERSION,
        python_version=runtime["python_version"],
        platform=runtime["platform"],
        sentence_transformers_version=runtime["sentence_transformers_version"],
        transformers_version=runtime["transformers_version"],
        torch_version=runtime["torch_version"],
    )

    _write_audit(
        audit_path=audit_path,
        run_id=run_id,
        friction_task=task_text,
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
                "require_offline_model": effective_require_offline,
                "joint_tag_present": joint_tag_present,
                "dist_joint_dali": dist_joint_dali,
                "dist_joint_clawd": dist_joint_clawd,
                "min_dist": min_dist,
                "novelty_pass": novelty_pass,
                "overall_pass": overall_pass,
                "failure_reasons": failure_reasons,
                "embed_model": embed_model,
                "embed_version": embed_version,
                "embed_error": embed_error,
                "embedding_input_sanitized": True,
                "sanitizer_rules_version": SANITIZER_RULES_VERSION,
                "python_version": runtime["python_version"],
                "platform": runtime["platform"],
                "sentence_transformers_version": runtime["sentence_transformers_version"],
                "transformers_version": runtime["transformers_version"],
                "torch_version": runtime["torch_version"],
                "audit_note": str(audit_path.relative_to(workspace_root)),
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    return decision


def _deterministic_rewrite_proxy(text: str) -> str:
    """Deterministic transform for calibration without LLM calls."""
    pieces = [part.strip() for part in re.split(r"(?<=[.!?])\s+|\n+", text) if part.strip()]
    if len(pieces) > 1:
        # Rotate sentence order to preserve semantics while changing surface form.
        return " ".join(pieces[1:] + pieces[:1])

    words = text.split()
    if len(words) > 3:
        pivot = max(1, len(words) // 3)
        return " ".join(words[pivot:] + words[:pivot])
    return text


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    rank = (len(ordered) - 1) * percentile
    lower = math.floor(rank)
    upper = math.ceil(rank)
    if lower == upper:
        return ordered[lower]
    weight = rank - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * weight


def _bucket_summary(values: list[float]) -> dict[str, float]:
    return {
        "p50": _percentile(values, 0.50),
        "p90": _percentile(values, 0.90),
        "p95": _percentile(values, 0.95),
        "p99": _percentile(values, 0.99),
    }


def run_inv004_calibrate(
    *,
    inputs: str,
    embedder_name: str,
    out_path: Path,
    require_offline_model: bool = True,
    repo_root: Path | None = None,
    workspace_root: Path | None = None,
    embedder: Embedder | None = None,
) -> dict[str, Any]:
    repo_root = repo_root or _repo_root_from_file()
    workspace_root = workspace_root or _workspace_root_from_file()

    dali_path, clawd_path, joint_path = _resolve_calibration_inputs(inputs, repo_root)

    dali_body = sanitize_for_embedding(_extract_memo_body(_load_text(dali_path)))
    clawd_body = sanitize_for_embedding(_extract_memo_body(_load_text(clawd_path)))
    joint_body = (
        sanitize_for_embedding(_extract_memo_body(_load_text(joint_path)))
        if joint_path is not None
        else None
    )

    runtime = _runtime_identity(embedder_name)
    active_embedder = load_embedder(
        embedder_name,
        require_offline_model=require_offline_model,
        embedder=embedder,
    )

    def _distance(a: str, b: str) -> float:
        vectors = active_embedder.encode([a, b])
        return cosine_distance(vectors[0], vectors[1])

    within_agent_rewrite_dist: list[float] = []
    for base in (dali_body, clawd_body, joint_body):
        if base:
            within_agent_rewrite_dist.append(
                _distance(base, _deterministic_rewrite_proxy(base))
            )

    trivial_joint = f"{dali_body}\n---\n{clawd_body}".strip()
    trivial_concat_dist = [
        _distance(trivial_joint, dali_body),
        _distance(trivial_joint, clawd_body),
    ]

    true_joint_dist: list[float] = []
    if joint_body:
        true_joint_dist.extend(
            [
                _distance(joint_body, dali_body),
                _distance(joint_body, clawd_body),
            ]
        )

    within_summary = _bucket_summary(within_agent_rewrite_dist)
    trivial_summary = _bucket_summary(trivial_concat_dist)
    true_summary = _bucket_summary(true_joint_dist) if true_joint_dist else {}
    recommended_theta = within_summary["p95"]

    out_final = out_path
    if not out_final.is_absolute():
        out_final = repo_root / out_final
    out_final.parent.mkdir(parents=True, exist_ok=True)

    baseline = {
        "created_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "embedder_id": getattr(active_embedder, "model_name", embedder_name),
        "embedder_library_version": getattr(
            active_embedder,
            "library_version",
            runtime["sentence_transformers_version"],
        ),
        "python_version": runtime["python_version"],
        "platform": runtime["platform"],
        "sentence_transformers_version": runtime["sentence_transformers_version"],
        "transformers_version": runtime["transformers_version"],
        "torch_version": runtime["torch_version"],
        "embedding_input_sanitized": True,
        "sanitizer_rules_version": SANITIZER_RULES_VERSION,
        "recommended_theta": recommended_theta,
        "buckets": {
            "within_agent_rewrite_dist": {
                "values": within_agent_rewrite_dist,
                **within_summary,
            },
            "trivial_concat_dist": {
                "values": trivial_concat_dist,
                **trivial_summary,
            },
            "true_joint_dist": {
                "values": true_joint_dist,
                **true_summary,
            },
        },
    }

    out_final.write_text(json.dumps(baseline, indent=2), encoding="utf-8")

    out_rel = out_final
    if out_final.is_absolute() and out_final.is_relative_to(workspace_root):
        out_rel = out_final.relative_to(workspace_root)

    audit_note = _write_calibration_audit(
        workspace_root=workspace_root,
        embedder_id=baseline["embedder_id"],
        out_rel=Path(out_rel),
        recommended_theta=recommended_theta,
        runtime=runtime,
    )
    baseline["audit_note"] = str(audit_note)

    return baseline


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
        "--require-offline-model",
        default=None,
        type=_parse_optional_bool,
        help="Require local/offline model availability (default true in enforce, false in dry)",
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

    calibrate = subparsers.add_parser(
        "inv004-calibrate",
        help="Compute baseline novelty calibration metrics for INV-004",
    )
    calibrate.add_argument("--inputs", required=True, help="Input directory with dali/clawd/joint outputs")
    calibrate.add_argument("--embedder", default=DEFAULT_EMBEDDER)
    calibrate.add_argument("--out", required=True, help="Output baseline.json path")
    calibrate.add_argument(
        "--require-offline-model",
        default=True,
        type=_parse_bool,
        help="Require local/offline model availability (default true)",
    )

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    repo_root = _repo_root_from_file()
    workspace_root = _workspace_root_from_file()

    if args.command == "inv004":
        spec_path = Path(args.spec_path)
        if not spec_path.is_absolute():
            spec_path = repo_root / args.spec_path

        default_offline = args.mode == "enforce"
        require_offline = default_offline if args.require_offline_model is None else args.require_offline_model

        decision = run_inv004(
            run_id=args.run_id,
            mode=args.mode,
            theta=args.theta,
            embedder_name=args.embedder,
            inputs=args.inputs,
            isolation_verified=args.isolation_verified,
            isolation_evidence=args.isolation_evidence,
            require_offline_model=require_offline,
            friction_task=args.task,
            spec_path=spec_path,
            repo_root=repo_root,
            workspace_root=workspace_root,
        )

        print("INV-004 commit gate")
        print(f"  mode: {decision.mode}")
        print(f"  audit_note: {decision.audit_note_path}")
        print(f"  run_artifacts: {decision.run_artifact_dir}")
        print(f"  require_offline_model: {str(decision.require_offline_model).lower()}")
        print(f"  embedding_input_sanitized: {str(decision.embedding_input_sanitized).lower()} ({decision.sanitizer_rules_version})")
        print(f"  joint_tag_present: {'PASS' if decision.joint_tag_present else 'FAIL'}")
        min_dist_text = _fmt_num(decision.min_dist)
        print(
            f"  novelty: {'PASS' if decision.novelty_pass else 'FAIL'} "
            f"(min_dist={min_dist_text}, theta={decision.theta:.6f})"
        )
        if decision.mode == "enforce":
            print(f"  isolation_enforced: {'PASS' if decision.isolation_verified and bool(decision.isolation_evidence) else 'FAIL'}")
        print(f"  result: {'PASS' if decision.overall_pass else 'FAIL'}")
        if decision.failure_reasons:
            print("  rationale:")
            for reason in decision.failure_reasons:
                print(f"    - {reason}")

        if decision.overall_pass:
            return 0
        return 2 if decision.mode == "enforce" else 1

    if args.command == "inv004-calibrate":
        out_path = Path(args.out)
        if not out_path.is_absolute():
            out_path = repo_root / out_path

        baseline = run_inv004_calibrate(
            inputs=args.inputs,
            embedder_name=args.embedder,
            out_path=out_path,
            require_offline_model=args.require_offline_model,
            repo_root=repo_root,
            workspace_root=workspace_root,
        )
        print("INV-004 calibration")
        print(f"  embedder: {baseline['embedder_id']}")
        print(f"  recommended_theta: {baseline['recommended_theta']:.12f}")
        print(f"  baseline: {out_path}")
        print(f"  audit_note: {baseline['audit_note']}")
        return 0

    parser.error("Unsupported command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
