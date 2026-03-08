"""Tests for pure helpers in tools/quarantine_review.py.

classify_path() is a pure function — no subprocess, no files.

Covers:
- classify_path() — path categorization into (category, priority) tuples
"""
import importlib.util as _ilu
import sys
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

REPO_ROOT = Path(__file__).resolve().parents[1]
QR_PATH = REPO_ROOT / "tools" / "quarantine_review.py"

_spec = _ilu.spec_from_file_location("quarantine_review_real", str(QR_PATH))
qr = _ilu.module_from_spec(_spec)
sys.modules["quarantine_review_real"] = qr
_spec.loader.exec_module(qr)

classify_path = qr.classify_path


# ---------------------------------------------------------------------------
# classify_path
# ---------------------------------------------------------------------------

class TestClassifyPath(unittest.TestCase):
    """Tests for classify_path() — (category, priority) classification."""

    def test_returns_tuple(self):
        result = classify_path("some/path.py")
        self.assertIsInstance(result, tuple)

    def test_returns_two_elements(self):
        result = classify_path("some/path.py")
        self.assertEqual(len(result), 2)

    def test_secrets_file_high_priority(self):
        cat, pri = classify_path("secrets/api_keys.json")
        self.assertEqual(cat, "secret-risk")
        self.assertEqual(pri, "high")

    def test_env_file_high_priority(self):
        cat, pri = classify_path(".env")
        self.assertEqual(cat, "secret-risk")
        self.assertEqual(pri, "high")

    def test_credentials_file_high_priority(self):
        cat, pri = classify_path("credentials/telegram.json")
        self.assertEqual(cat, "secret-risk")
        self.assertEqual(pri, "high")

    def test_workspace_path_gov_high(self):
        cat, pri = classify_path("workspace/governance/OPEN_QUESTIONS.md")
        self.assertEqual(cat, "gov")
        self.assertEqual(pri, "high")

    def test_reports_path_docs_low(self):
        cat, pri = classify_path("reports/daily_summary.md")
        self.assertEqual(cat, "docs")
        self.assertEqual(pri, "low")

    def test_docs_path_docs_low(self):
        cat, pri = classify_path("docs/architecture.md")
        self.assertEqual(cat, "docs")
        self.assertEqual(pri, "low")

    def test_pipelines_config_med(self):
        cat, pri = classify_path("pipelines/ingest.yaml")
        self.assertEqual(cat, "config")
        self.assertEqual(pri, "med")

    def test_openclaw_json_config_med(self):
        cat, pri = classify_path("openclaw.json")
        self.assertEqual(cat, "config")
        self.assertEqual(pri, "med")

    def test_secrets_env_template_is_secret_risk(self):
        # "secrets" is a substring → hits the secret-risk check first
        cat, pri = classify_path("secrets.env.template")
        self.assertEqual(cat, "secret-risk")
        self.assertEqual(pri, "high")

    def test_core_infra_code_med(self):
        cat, pri = classify_path("core_infra/runner.py")
        self.assertEqual(cat, "code")
        self.assertEqual(pri, "med")

    def test_tools_code_med(self):
        cat, pri = classify_path("tools/commit_gate.py")
        self.assertEqual(cat, "code")
        self.assertEqual(pri, "med")

    def test_scripts_code_med(self):
        cat, pri = classify_path("scripts/daily_brief.py")
        self.assertEqual(cat, "code")
        self.assertEqual(pri, "med")

    def test_economics_artifact_low(self):
        cat, pri = classify_path("economics/data.csv")
        self.assertEqual(cat, "artifact")
        self.assertEqual(pri, "low")

    def test_sim_artifact_low(self):
        cat, pri = classify_path("sim/results.json")
        self.assertEqual(cat, "artifact")
        self.assertEqual(pri, "low")

    def test_itc_artifact_low(self):
        cat, pri = classify_path("itc/pipeline.py")
        self.assertEqual(cat, "artifact")
        self.assertEqual(pri, "low")

    def test_unknown_path_other_low(self):
        cat, pri = classify_path("xyz/random_file.txt")
        self.assertEqual(cat, "other")
        self.assertEqual(pri, "low")

    def test_backslash_normalized(self):
        """Windows-style paths with backslashes are normalized to forward slashes."""
        cat, pri = classify_path("workspace\\governance\\file.md")
        self.assertEqual(cat, "gov")
        self.assertEqual(pri, "high")


if __name__ == "__main__":
    unittest.main()
