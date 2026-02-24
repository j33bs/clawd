import hashlib
import tempfile
import unittest
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_TOOLS = REPO_ROOT / "workspace" / "tools"
if str(WORKSPACE_TOOLS) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_TOOLS))

from commit_gate import run_inv004


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

            self.assertAlmostEqual(one.dist_joint_dali, two.dist_joint_dali, places=12)
            self.assertAlmostEqual(one.dist_joint_clawd, two.dist_joint_clawd, places=12)
            self.assertAlmostEqual(one.min_dist, two.min_dist, places=12)
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

            pass_threshold = max(0.0, baseline.min_dist - 1e-9)
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
                theta=baseline.min_dist + 1e-9,
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
            self.assertIn("theta:", text)
            self.assertIn("dist_joint_dali:", text)
            self.assertIn("dist_joint_clawd:", text)
        finally:
            tempdir.cleanup()


if __name__ == "__main__":
    unittest.main()
