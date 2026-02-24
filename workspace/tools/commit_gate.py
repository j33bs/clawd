"""
INV-004 Commit Gate — v1.0

Implements the Commit Gate per INV-004 spec (XCI) and all amendments:
  - XCIV Safeguard 2: jointly-signed output must carry [JOINT: c_lawd + Dali] prefix
  - XCV Amendment A: isolation attestation required (isolation_verified + isolation_evidence)
  - XCV Amendment B: calibrated θ = p95(within_agent_rewrite_dist); embed model/version logged
  - XCV Amendment C: [EXEC:…] tags on round artifacts; "novel but violates constraint" failure mode
  - XCII: offline embedder required; sanitization; comprehensive audit emission

Usage (dry run):
  python3 commit_gate.py \\
    --r1-c-lawd r1_c_lawd.txt \\
    --r1-dali r1_dali.txt \\
    --r3-joint r3_joint.txt \\
    --task-id TASK_DRY_001 \\
    --isolation-evidence "c_lawd session: 21:04Z, dali session: 21:07Z, no overlap" \\
    --dry-run

Usage (live gate):
  python3 commit_gate.py \\
    --r1-c-lawd r1_c_lawd.txt \\
    --r1-dali r1_dali.txt \\
    --r3-joint r3_joint.txt \\
    --task-id TASK_001 \\
    --c-lawd-constraint "output must preserve full provenance chain" \\
    --dali-constraint "output must not exceed 200 tokens" \\
    --isolation-evidence "..."

Outputs:
  - Gate decision to stdout (GATE-INV004-PASS / GATE-INV004-REJECTION)
  - Audit log appended to workspace/governance/phi_metrics.md
  - Structured JSON audit entry to workspace/audit/commit_gate_<task_id>_<ts>.json
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# ── paths ────────────────────────────────────────────────────────────────────
_HERE = Path(__file__).resolve().parent
WORKSPACE = _HERE.parent
STORE_DIR = WORKSPACE / "store"
AUDIT_DIR = WORKSPACE / "audit"
GOVERNANCE_DIR = WORKSPACE / "governance"
PHI_METRICS = GOVERNANCE_DIR / "phi_metrics.md"

sys.path.insert(0, str(STORE_DIR))

from sanitizer import sanitize, sanitizer_version, diff as sanitizer_diff

# ── constants ─────────────────────────────────────────────────────────────────
JOINT_PREFIX = "[JOINT: c_lawd + Dali]"
JOINT_PATTERN = re.compile(r"\[JOINT:\s*c_lawd\s*\+\s*Dali\]", re.IGNORECASE)

# Provisional θ (XCV Amendment B). Overridden by calibrate_theta() if called.
DEFAULT_THETA = 0.15

# Number of within-agent rewrite pairs for calibration
CALIBRATION_PAIRS = 5

GATE_VERSION = "1.0.0"


# ── offline enforcement ───────────────────────────────────────────────────────

def enforce_offline() -> None:
    """
    XCII: Offline model required. Exit if HF_HUB_OFFLINE is not set.
    Prevents silent fallback to remote model download.
    """
    if os.environ.get("HF_HUB_OFFLINE", "0") != "1":
        print("ERROR: HF_HUB_OFFLINE=1 is required for commit gate execution.")
        print("  Set: export HF_HUB_OFFLINE=1")
        print("  Rationale: one canonical embedder per node per epoch (XCII).")
        sys.exit(1)


# ── isolation attestation ─────────────────────────────────────────────────────

def check_isolation(isolation_evidence: str) -> dict:
    """
    XCV Amendment A: isolation_verified=true requires non-empty isolation_evidence.
    Returns attestation dict for audit log.
    """
    if not isolation_evidence or not isolation_evidence.strip():
        return {"isolation_verified": False, "isolation_evidence": "", "error": "empty evidence"}
    return {
        "isolation_verified": True,
        "isolation_evidence": isolation_evidence.strip(),
    }


# ── embedding ─────────────────────────────────────────────────────────────────

def _get_model(model_name: str):
    """Load SentenceTransformer. Assumes HF_HUB_OFFLINE=1 already enforced."""
    from sentence_transformers import SentenceTransformer
    device = "cpu"
    try:
        import torch
        if torch.backends.mps.is_available():
            device = "mps"
    except ImportError:
        pass
    return SentenceTransformer(model_name, device=device)


def _env_identity(model_name: str) -> dict:
    """
    XCII: Emit environment identity for audit.
    Does NOT log secrets, tokens, or file paths with user data.
    """
    try:
        import torch
        torch_ver = torch.__version__
    except ImportError:
        torch_ver = "not installed"
    try:
        import transformers
        transformers_ver = transformers.__version__
    except ImportError:
        transformers_ver = "not installed"
    try:
        import sentence_transformers
        st_ver = sentence_transformers.__version__
    except ImportError:
        st_ver = "not installed"

    return {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "torch": torch_ver,
        "transformers": transformers_ver,
        "sentence_transformers": st_ver,
        "embed_model": model_name,
        "sanitizer_version": sanitizer_version(),
        "gate_version": GATE_VERSION,
    }


def cosine_distance(a: list[float], b: list[float]) -> float:
    """1 - cosine_similarity. Range [0, 2]; 0 = identical, 2 = opposite."""
    import math
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 1.0
    return 1.0 - (dot / (norm_a * norm_b))


# ── θ calibration ─────────────────────────────────────────────────────────────

def calibrate_theta(model, n_pairs: int = CALIBRATION_PAIRS) -> dict:
    """
    XCV Amendment B: θ = p95(within_agent_rewrite_dist).

    Generates n_pairs synthetic paraphrase pairs using fixed seed text
    (not drawn from the actual task — prevents contamination).
    Returns theta and full calibration record for audit.

    In production: replace seed texts with actual within-agent rewrite pairs
    collected before the friction task begins.
    """
    # Seed texts — governance-neutral, representative of correspondence register
    seed_texts = [
        "The store is rebuilt from the markdown source of truth.",
        "Embedding vectors are computed from body content only.",
        "Governance tags are metadata and must never be embedded.",
        "The collision log preserves section filing evidence.",
        "The session start protocol runs orient.py with --verify.",
    ]
    paraphrases = [
        "The store is reconstructed entirely from the markdown source.",
        "Body text alone is used to compute embedding vectors.",
        "Governance tags belong in metadata and should not enter the vector.",
        "Collision events are preserved in the collision log as evidence.",
        "Session initialization runs orient.py and checks the verify flag.",
    ]

    pairs = list(zip(seed_texts[:n_pairs], paraphrases[:n_pairs]))

    orig_vecs = model.encode([p[0] for p in pairs], show_progress_bar=False)
    para_vecs = model.encode([p[1] for p in pairs], show_progress_bar=False)

    distances = [
        cosine_distance(orig_vecs[i].tolist(), para_vecs[i].tolist())
        for i in range(len(pairs))
    ]
    distances.sort()

    # p95 of n_pairs — for small n, this is the max
    p95_idx = max(0, int(len(distances) * 0.95) - 1)
    theta = distances[p95_idx]

    return {
        "recommended_theta": theta,
        "distances": distances,
        "n_pairs": len(pairs),
        "method": "within_agent_rewrite_p95",
        "note": "Provisional calibration using seed texts. Replace with actual rewrite pairs in production.",
    }


# ── novelty check ─────────────────────────────────────────────────────────────

def check_novelty(
    r1_c_lawd_text: str,
    r1_dali_text: str,
    r3_joint_text: str,
    model,
    theta: float,
) -> dict:
    """
    Primary novelty check: is the joint output genuinely novel relative to both R1s?
    Returns distances and pass/fail for the novelty criterion.
    """
    texts = [
        sanitize(r1_c_lawd_text),
        sanitize(r1_dali_text),
        sanitize(r3_joint_text),
    ]
    vecs = model.encode(texts, show_progress_bar=False)

    dist_c_lawd = cosine_distance(vecs[2].tolist(), vecs[0].tolist())
    dist_dali = cosine_distance(vecs[2].tolist(), vecs[1].tolist())

    novel = dist_c_lawd > theta and dist_dali > theta

    return {
        "dist_joint_vs_c_lawd": dist_c_lawd,
        "dist_joint_vs_dali": dist_dali,
        "theta": theta,
        "novel": novel,
        "note": f"Novel iff both distances > θ={theta:.4f}",
    }


# ── constraint satisfaction check ────────────────────────────────────────────

def check_constraints(
    r3_joint_text: str,
    c_lawd_constraint: Optional[str],
    dali_constraint: Optional[str],
) -> dict:
    """
    XCV Amendment C: detect "novel but violates one constraint" failure mode.

    This is a procedural check — it requires human review of the joint output
    against each stated constraint. The gate script records the constraints and
    flags for human confirmation. Auto-detection is not reliable.

    Returns a check record. If constraints are not supplied, this check is skipped.
    """
    if not c_lawd_constraint and not dali_constraint:
        return {"constraint_check": "skipped", "reason": "no constraints supplied"}

    # Flag for human review — the gate cannot auto-verify constraint satisfaction
    return {
        "constraint_check": "pending_human_review",
        "c_lawd_constraint": c_lawd_constraint or "(not supplied)",
        "dali_constraint": dali_constraint or "(not supplied)",
        "joint_output_length_tokens": len(r3_joint_text.split()),
        "instruction": (
            "Review joint output against each constraint before accepting PASS. "
            "If the output is novel but violates one constraint, this is "
            "GATE-INV004-REJECTION per XCV Amendment C (failure taxonomy)."
        ),
    }


# ── audit emission ────────────────────────────────────────────────────────────

def emit_audit(
    task_id: str,
    gate_decision: str,
    env: dict,
    isolation: dict,
    calibration: dict,
    novelty: dict,
    constraints: dict,
    sanitizer_diffs: dict,
    dry_run: bool,
) -> dict:
    """
    XCII: Mandatory audit emission. Records everything required for reproducibility
    and cross-time auditing. Does not log secrets.
    """
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    record = {
        "task_id": task_id,
        "timestamp_utc": ts,
        "gate_decision": gate_decision,
        "dry_run": dry_run,
        "gate_version": GATE_VERSION,
        "env": env,
        "isolation": isolation,
        "calibration": calibration,
        "novelty": novelty,
        "constraints": constraints,
        "sanitizer_diffs": sanitizer_diffs,
    }

    # Write JSON audit entry
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    audit_path = AUDIT_DIR / f"commit_gate_{task_id}_{ts}.json"
    with open(audit_path, "w", encoding="utf-8") as f:
        json.dump(record, f, indent=2)
    print(f"  Audit written: {audit_path}")

    # Append summary row to phi_metrics.md
    phi_row = (
        f"\n| INV-004 | {task_id} | {ts[:10]} | {gate_decision} | "
        f"θ={novelty['theta']:.4f} | "
        f"dist_c_lawd={novelty['dist_joint_vs_c_lawd']:.4f} | "
        f"dist_dali={novelty['dist_joint_vs_dali']:.4f} | "
        f"embed_model={env['embed_model']}+sanitizer-{env['sanitizer_version']} | "
        f"isolation_verified={isolation.get('isolation_verified', False)} |\n"
    )
    if PHI_METRICS.exists():
        with open(PHI_METRICS, "a", encoding="utf-8") as f:
            f.write(phi_row)
        print(f"  phi_metrics.md row appended.")

    return record


# ── gate logic ────────────────────────────────────────────────────────────────

def run_gate(
    r1_c_lawd_text: str,
    r1_dali_text: str,
    r3_joint_text: str,
    task_id: str,
    isolation_evidence: str,
    c_lawd_constraint: Optional[str] = None,
    dali_constraint: Optional[str] = None,
    model_name: str = "all-MiniLM-L6-v2",
    theta: Optional[float] = None,
    dry_run: bool = False,
) -> str:
    """
    Run the INV-004 Commit Gate. Returns gate decision string.
    """
    print(f"\n── INV-004 Commit Gate ── task={task_id} dry_run={dry_run} ──")

    # 1. Offline check
    enforce_offline()

    # 2. Isolation attestation
    isolation = check_isolation(isolation_evidence)
    if not isolation["isolation_verified"]:
        print(f"  ❌ ISOLATION FAILED: {isolation.get('error')}")
        print(f"  Gate cannot proceed without isolation_verified=true and non-empty evidence.")
        decision = "GATE-INV004-REJECTED-ISOLATION-FAILURE"
        emit_audit(task_id, decision, _env_identity(model_name), isolation,
                   {}, {}, {}, {}, dry_run)
        return decision

    print(f"  ✅ Isolation verified: {isolation['isolation_evidence'][:80]}...")

    # 3. Check for [JOINT: c_lawd + Dali] prefix (Safeguard 2, XCIV)
    has_joint_prefix = bool(JOINT_PATTERN.match(r3_joint_text.strip()))
    if not has_joint_prefix:
        print(f"  ❌ JOINT PREFIX MISSING: output does not start with '{JOINT_PREFIX}'")
        print(f"  A response without this prefix is not a valid pass (XCIV Safeguard 2).")
        decision = "GATE-INV004-REJECTION"
        emit_audit(task_id, decision, _env_identity(model_name), isolation,
                   {"note": "not reached — prefix check failed"}, {}, {}, {}, dry_run)
        return decision

    print(f"  ✅ Joint prefix confirmed.")

    # 4. Load model + get env identity
    print(f"  Loading embedding model: {model_name}")
    model = _get_model(model_name)
    env = _env_identity(model_name)

    # 5. Sanitizer diffs (for audit — not modifying stored data)
    sanitizer_diffs = {
        "r1_c_lawd": sanitizer_diff(r1_c_lawd_text, sanitize(r1_c_lawd_text)),
        "r1_dali":   sanitizer_diff(r1_dali_text,   sanitize(r1_dali_text)),
        "r3_joint":  sanitizer_diff(r3_joint_text,  sanitize(r3_joint_text)),
    }

    # 6. Calibrate θ (or use supplied/default)
    if theta is None:
        print(f"  Calibrating θ...")
        calibration = calibrate_theta(model)
        theta_to_use = calibration["recommended_theta"]
        print(f"  θ calibrated: {theta_to_use:.4f} (p95 of within-agent rewrite distances)")
    else:
        calibration = {"recommended_theta": theta, "method": "user_supplied", "note": "manually overridden"}
        theta_to_use = theta
        print(f"  θ supplied: {theta_to_use:.4f}")

    # 7. Novelty check
    print(f"  Computing novelty distances...")
    novelty = check_novelty(r1_c_lawd_text, r1_dali_text, r3_joint_text, model, theta_to_use)
    print(f"  dist(joint, c_lawd_R1) = {novelty['dist_joint_vs_c_lawd']:.4f}")
    print(f"  dist(joint, dali_R1)   = {novelty['dist_joint_vs_dali']:.4f}")
    print(f"  θ = {theta_to_use:.4f}  →  novel = {novelty['novel']}")

    # 8. Constraint satisfaction (human review required)
    constraints = check_constraints(r3_joint_text, c_lawd_constraint, dali_constraint)

    # 9. Gate decision
    if not novelty["novel"]:
        decision = "GATE-INV004-REJECTION"
        reason = (
            f"Joint output is not sufficiently novel: "
            f"dist_c_lawd={novelty['dist_joint_vs_c_lawd']:.4f}, "
            f"dist_dali={novelty['dist_joint_vs_dali']:.4f}, "
            f"θ={theta_to_use:.4f}. "
            f"Failure mode: {'register collapse (check 200ms Rule)' if novelty['dist_joint_vs_c_lawd'] < 0.05 else 'insufficient divergence'}."
        )
        print(f"\n  ❌ {decision}")
        print(f"  Reason: {reason}")
        print(f"  Redemption path: this rejection IS the next prompt (XCI). Same constraint, fresh attempt.")
    else:
        decision = "GATE-INV004-PASS" if not dry_run else "GATE-INV004-PASS (DRY RUN)"
        print(f"\n  ✅ {decision}")
        print(f"  Novel jointly-signed output confirmed.")
        if constraints.get("constraint_check") == "pending_human_review":
            print(f"  ⚠️  Constraint satisfaction requires human review before accepting.")
            print(f"     c_lawd constraint: {c_lawd_constraint}")
            print(f"     Dali constraint:   {dali_constraint}")

    # 10. Emit audit
    audit = emit_audit(
        task_id, decision, env, isolation, calibration, novelty, constraints, sanitizer_diffs, dry_run
    )

    return decision


# ── CLI ───────────────────────────────────────────────────────────────────────

def _read_file_or_str(path_or_str: str) -> str:
    """Read from file if path exists, else treat as inline text."""
    p = Path(path_or_str)
    if p.exists():
        return p.read_text(encoding="utf-8")
    return path_or_str


def main() -> None:
    parser = argparse.ArgumentParser(
        description="INV-004 Commit Gate — gate decision for jointly-signed outputs"
    )
    parser.add_argument("--r1-c-lawd", required=True, help="Path to c_lawd Round 1 submission (file or text)")
    parser.add_argument("--r1-dali",   required=True, help="Path to Dali Round 1 submission (file or text)")
    parser.add_argument("--r3-joint",  required=True, help="Path to Round 3 jointly-signed output (file or text)")
    parser.add_argument("--task-id",   required=True, help="Unique task identifier (e.g. TASK_DRY_001)")
    parser.add_argument("--isolation-evidence", default="", help="Evidence of Round 1 session isolation")
    parser.add_argument("--c-lawd-constraint",  default=None, help="c_lawd's stated constraint for this task")
    parser.add_argument("--dali-constraint",    default=None, help="Dali's stated constraint for this task")
    parser.add_argument("--model", default="all-MiniLM-L6-v2", help="Embedding model name")
    parser.add_argument("--theta", type=float, default=None, help="Override θ (skip calibration)")
    parser.add_argument("--dry-run", action="store_true", help="Dry run — gate runs but write does not proceed")
    args = parser.parse_args()

    r1_c_lawd = _read_file_or_str(args.r1_c_lawd)
    r1_dali   = _read_file_or_str(args.r1_dali)
    r3_joint  = _read_file_or_str(args.r3_joint)

    decision = run_gate(
        r1_c_lawd_text=r1_c_lawd,
        r1_dali_text=r1_dali,
        r3_joint_text=r3_joint,
        task_id=args.task_id,
        isolation_evidence=args.isolation_evidence,
        c_lawd_constraint=args.c_lawd_constraint,
        dali_constraint=args.dali_constraint,
        model_name=args.model,
        theta=args.theta,
        dry_run=args.dry_run,
    )

    sys.exit(0 if "PASS" in decision else 1)


if __name__ == "__main__":
    main()
