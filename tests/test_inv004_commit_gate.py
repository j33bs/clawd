import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_TOOLS = REPO_ROOT / "workspace" / "tools"
if str(WORKSPACE_TOOLS) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_TOOLS))

from commit_gate import (
    SANITIZER_RULES_VERSION,
    run_inv004,
    run_inv004_calibrate,
    sanitize_for_embedding,
)


class DeterministicEmbedder:
    model_name = "deterministic-hash"
    library_name = "test"
    library_version = "1.0"

    def encode(self, texts):
        vectors = []
        for text in texts:
            digest = hashlib.sha256(text.encode("utf-8")).digest()
            vectors.append([float(byte) / 255.0 for byte in digest])
        return vectors


class TestINV004CommitGate(unittest.TestCase):
    fixtures_dir = REPO_ROOT / "tests" / "fixtures" / "inv004"

    def _build_workspace(self):
        tempdir = tempfile.TemporaryDirectory()
        root = Path(tempdir.name)
        (root / "workspace" / "audit").mkdir(parents=True, exist_ok=True)
        (root / "workspace" / "artifacts").mkdir(parents=True, exist_ok=True)
        (root / "workspace" / "governance").mkdir(parents=True, exist_ok=True)
        (root / "inputs").mkdir(parents=True, exist_ok=True)

        for name in ("dali_output.md", "clawd_output.md", "joint_output.md"):
            (root / "inputs" / name).write_text(
                (self.fixtures_dir / name).read_text(encoding="utf-8"),
                encoding="utf-8",
            )

        spec = root / "workspace" / "governance" / "INV-004_commit_gate_spec.md"
        spec.write_text(
            "# INV-004\n\nExample task:\n> Produce a 6-line governance memo.\n",
            encoding="utf-8",
        )
        return tempdir, root, spec

    def test_joint_tag_enforcement(self):
        tempdir, root, spec = self._build_workspace()
        try:
            joint_path = root / "inputs" / "joint_output.md"
            joint_path.write_text(
                joint_path.read_text(encoding="utf-8").replace("[JOINT: c_lawd + dali]", "[JOINT:MISSING]"),
                encoding="utf-8",
            )

            result = run_inv004(
                run_id="joint-tag-fail",
                mode="enforce",
                theta=0.0,
                embedder_name="sentence-transformers/all-MiniLM-L6-v2",
                inputs=str(root / "inputs"),
                isolation_verified=True,
                isolation_evidence="separate sessions, timestamped",
                spec_path=spec,
                repo_root=root,
                workspace_root=root / "workspace",
                embedder=DeterministicEmbedder(),
            )

            self.assertFalse(result.overall_pass)
            self.assertTrue(any("missing required tag" in r.lower() for r in result.failure_reasons))
        finally:
            tempdir.cleanup()

    def test_distance_determinism_within_tolerance(self):
        tempdir, root, spec = self._build_workspace()
        try:
            one = run_inv004(
                run_id="determinism-a",
                mode="dry",
                theta=0.15,
                embedder_name="sentence-transformers/all-MiniLM-L6-v2",
                inputs=str(root / "inputs"),
                isolation_verified=True,
                isolation_evidence="recorded independently",
                spec_path=spec,
                repo_root=root,
                workspace_root=root / "workspace",
                embedder=DeterministicEmbedder(),
            )
            two = run_inv004(
                run_id="determinism-b",
                mode="dry",
                theta=0.15,
                embedder_name="sentence-transformers/all-MiniLM-L6-v2",
                inputs=str(root / "inputs"),
                isolation_verified=True,
                isolation_evidence="recorded independently",
                spec_path=spec,
                repo_root=root,
                workspace_root=root / "workspace",
                embedder=DeterministicEmbedder(),
            )

            self.assertAlmostEqual(one.dist_joint_dali or 0.0, two.dist_joint_dali or 0.0, places=12)
            self.assertAlmostEqual(one.dist_joint_clawd or 0.0, two.dist_joint_clawd or 0.0, places=12)
            self.assertAlmostEqual(one.min_dist or 0.0, two.min_dist or 0.0, places=12)
        finally:
            tempdir.cleanup()

    def test_theta_logic_pass_and_fail(self):
        tempdir, root, spec = self._build_workspace()
        try:
            baseline = run_inv004(
                run_id="theta-baseline",
                mode="enforce",
                theta=0.0,
                embedder_name="sentence-transformers/all-MiniLM-L6-v2",
                inputs=str(root / "inputs"),
                isolation_verified=True,
                isolation_evidence="operator attestation",
                spec_path=spec,
                repo_root=root,
                workspace_root=root / "workspace",
                embedder=DeterministicEmbedder(),
            )
            self.assertTrue(baseline.overall_pass)
            self.assertIsNotNone(baseline.min_dist)

            pass_threshold = max(0.0, (baseline.min_dist or 0.0) - 1e-9)
            pass_case = run_inv004(
                run_id="theta-pass",
                mode="enforce",
                theta=pass_threshold,
                embedder_name="sentence-transformers/all-MiniLM-L6-v2",
                inputs=str(root / "inputs"),
                isolation_verified=True,
                isolation_evidence="operator attestation",
                spec_path=spec,
                repo_root=root,
                workspace_root=root / "workspace",
                embedder=DeterministicEmbedder(),
            )
            self.assertTrue(pass_case.overall_pass)

            fail_case = run_inv004(
                run_id="theta-fail",
                mode="enforce",
                theta=(baseline.min_dist or 0.0) + 1e-9,
                embedder_name="sentence-transformers/all-MiniLM-L6-v2",
                inputs=str(root / "inputs"),
                isolation_verified=True,
                isolation_evidence="operator attestation",
                spec_path=spec,
                repo_root=root,
                workspace_root=root / "workspace",
                embedder=DeterministicEmbedder(),
            )
            self.assertFalse(fail_case.overall_pass)
            self.assertTrue(any("novelty threshold" in r.lower() for r in fail_case.failure_reasons))
        finally:
            tempdir.cleanup()

    def test_audit_contains_required_fields(self):
        tempdir, root, spec = self._build_workspace()
        try:
            result = run_inv004(
                run_id="audit-fields",
                mode="enforce",
                theta=0.15,
                embedder_name="sentence-transformers/all-MiniLM-L6-v2",
                inputs=str(root / "inputs"),
                isolation_verified=True,
                isolation_evidence="timestamps logged in separate sessions",
                spec_path=spec,
                repo_root=root,
                workspace_root=root / "workspace",
                embedder=DeterministicEmbedder(),
            )

            text = result.audit_note_path.read_text(encoding="utf-8")
            self.assertIn("isolation_verified: true", text)
            self.assertIn("embed_model: deterministic-hash", text)
            self.assertIn("embed_version: 1.0", text)
            self.assertIn("embedding_input_sanitized: true", text)
            self.assertIn(f"sanitizer_rules_version: {SANITIZER_RULES_VERSION}", text)
            self.assertIn("python_version:", text)
            self.assertIn("platform:", text)
            self.assertIn("transformers_version:", text)
            self.assertIn("torch_version:", text)
        finally:
            tempdir.cleanup()

    def test_enforce_fails_when_isolation_missing(self):
        tempdir, root, spec = self._build_workspace()
        try:
            result = run_inv004(
                run_id="iso-missing",
                mode="enforce",
                theta=0.0,
                embedder_name="sentence-transformers/all-MiniLM-L6-v2",
                inputs=str(root / "inputs"),
                isolation_verified=False,
                isolation_evidence="",
                spec_path=spec,
                repo_root=root,
                workspace_root=root / "workspace",
                embedder=DeterministicEmbedder(),
            )

            self.assertFalse(result.overall_pass)
            reasons = "\n".join(result.failure_reasons).lower()
            self.assertIn("isolation_verified", reasons)
            self.assertIn("isolation_evidence", reasons)
        finally:
            tempdir.cleanup()

    def test_enforce_fails_when_model_unavailable_offline(self):
        tempdir, root, spec = self._build_workspace()
        try:
            with mock.patch.dict(os.environ, {"HF_HUB_OFFLINE": "1"}, clear=False):
                result = run_inv004(
                    run_id="offline-missing-model",
                    mode="enforce",
                    theta=0.15,
                    embedder_name="sentence-transformers/nonexistent-inv004-model",
                    inputs=str(root / "inputs"),
                    isolation_verified=True,
                    isolation_evidence="timestamps captured",
                    spec_path=spec,
                    repo_root=root,
                    workspace_root=root / "workspace",
                    require_offline_model=True,
                )
            self.assertFalse(result.overall_pass)
            reasons = "\n".join(result.failure_reasons).lower()
            self.assertIn("offline", reasons)
            self.assertIn("model not available", reasons)
        finally:
            tempdir.cleanup()

    def test_sanitizer_removes_governance_tags(self):
        raw = """[EXEC:HUMAN_OK] Keep this control line.
[JOINT: c_lawd + dali] EXPERIMENT PENDING
[ALERT:TAG] GOVERNANCE RULE CANDIDATE remains testable.
PHILOSOPHICAL ONLY should vanish phrase.
[UPPER:XYZ] payload survives
"""
        cleaned = sanitize_for_embedding(raw)
        self.assertNotIn("[EXEC:", cleaned)
        self.assertNotIn("[JOINT:", cleaned)
        self.assertNotIn("EXPERIMENT PENDING", cleaned)
        self.assertNotIn("GOVERNANCE RULE CANDIDATE", cleaned)
        self.assertNotIn("PHILOSOPHICAL ONLY", cleaned)
        self.assertIn("payload survives", cleaned)

    def test_calibration_writes_baseline_with_required_fields(self):
        tempdir, root, _ = self._build_workspace()
        try:
            baseline_path = root / "workspace" / "artifacts" / "inv004" / "calibration" / "test-run" / "baseline.json"
            baseline = run_inv004_calibrate(
                inputs=str(root / "inputs"),
                embedder_name="sentence-transformers/all-MiniLM-L6-v2",
                out_path=baseline_path,
                require_offline_model=False,
                repo_root=root,
                workspace_root=root / "workspace",
                embedder=DeterministicEmbedder(),
            )
            self.assertTrue(baseline_path.exists())
            loaded = json.loads(baseline_path.read_text(encoding="utf-8"))
            self.assertIn("recommended_theta", loaded)
            self.assertIn("sentence_transformers_version", loaded)
            self.assertIn("transformers_version", loaded)
            self.assertIn("torch_version", loaded)
            self.assertIn("embedder_id", loaded)
            self.assertIn("buckets", loaded)
            self.assertIn("within_agent_rewrite_dist", loaded["buckets"])
            self.assertEqual(loaded["sanitizer_rules_version"], SANITIZER_RULES_VERSION)
            self.assertGreaterEqual(loaded["recommended_theta"], 0.0)
            self.assertIn("audit_note", baseline)
        finally:
            tempdir.cleanup()


if __name__ == "__main__":
    unittest.main()
