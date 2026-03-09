"""Tests for constants and logic in tools/check_ignored_tracking.py.

IGNORED_ROOTS and ALLOWLIST are pure data constants.
Also tests the violation detection logic (no subprocess needed).

Covers:
- IGNORED_ROOTS — tuple of forbidden directory prefixes
- ALLOWLIST — set of explicitly permitted paths
- Violation detection logic (simulated, no git subprocess)
"""
import importlib.util as _ilu
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
TOOL_PATH = REPO_ROOT / "tools" / "check_ignored_tracking.py"

_spec = _ilu.spec_from_file_location("check_ignored_tracking_real", str(TOOL_PATH))
cit = _ilu.module_from_spec(_spec)
sys.modules["check_ignored_tracking_real"] = cit
_spec.loader.exec_module(cit)

IGNORED_ROOTS = cit.IGNORED_ROOTS
ALLOWLIST = cit.ALLOWLIST


# ---------------------------------------------------------------------------
# IGNORED_ROOTS
# ---------------------------------------------------------------------------


class TestIgnoredRoots(unittest.TestCase):
    """Tests for IGNORED_ROOTS — tuple of forbidden directory prefixes."""

    def test_is_tuple(self):
        self.assertIsInstance(IGNORED_ROOTS, tuple)

    def test_contains_scripts(self):
        self.assertIn("scripts/", IGNORED_ROOTS)

    def test_contains_pipelines(self):
        self.assertIn("pipelines/", IGNORED_ROOTS)

    def test_contains_sim(self):
        self.assertIn("sim/", IGNORED_ROOTS)

    def test_contains_market(self):
        self.assertIn("market/", IGNORED_ROOTS)

    def test_contains_itc(self):
        self.assertIn("itc/", IGNORED_ROOTS)

    def test_contains_telegram(self):
        self.assertIn("telegram/", IGNORED_ROOTS)

    def test_all_end_with_slash(self):
        for root in IGNORED_ROOTS:
            self.assertTrue(root.endswith("/"), f"{root!r} does not end with '/'")

    def test_scripts_path_detected(self):
        path = "scripts/my_script.py"
        violation = any(path.startswith(r) for r in IGNORED_ROOTS)
        self.assertTrue(violation)

    def test_pipelines_path_detected(self):
        path = "pipelines/some_pipeline.yaml"
        violation = any(path.startswith(r) for r in IGNORED_ROOTS)
        self.assertTrue(violation)

    def test_workspace_path_not_detected(self):
        path = "workspace/scripts/runner.py"
        violation = any(path.startswith(r) for r in IGNORED_ROOTS)
        self.assertFalse(violation)

    def test_tools_path_not_detected(self):
        path = "tools/commit_gate.py"
        violation = any(path.startswith(r) for r in IGNORED_ROOTS)
        self.assertFalse(violation)

    def test_telegram_path_detected(self):
        path = "telegram/bot.py"
        violation = any(path.startswith(r) for r in IGNORED_ROOTS)
        self.assertTrue(violation)


# ---------------------------------------------------------------------------
# ALLOWLIST
# ---------------------------------------------------------------------------


class TestAllowlist(unittest.TestCase):
    """Tests for ALLOWLIST — set of explicitly permitted paths."""

    def test_is_set(self):
        self.assertIsInstance(ALLOWLIST, set)

    def test_contains_sim_runner(self):
        self.assertIn("scripts/sim_runner.py", ALLOWLIST)

    def test_contains_trading_features_yaml(self):
        self.assertIn("pipelines/system1_trading.features.yaml", ALLOWLIST)

    def test_not_empty(self):
        self.assertGreater(len(ALLOWLIST), 0)


# ---------------------------------------------------------------------------
# Violation detection logic (simulated — no git subprocess)
# ---------------------------------------------------------------------------


class TestViolationDetectionLogic(unittest.TestCase):
    """Simulated violation detection replicating main() logic."""

    def _check_violations(self, staged_paths):
        """Replicate the main() violation detection logic without subprocess."""
        violations = []
        for path in staged_paths:
            norm = path.replace("\\", "/")
            if norm in ALLOWLIST:
                continue
            for root in IGNORED_ROOTS:
                if norm.startswith(root):
                    violations.append(norm)
                    break
        return violations

    def test_allowlisted_sim_runner_no_violation(self):
        violations = self._check_violations(["scripts/sim_runner.py"])
        self.assertEqual(violations, [])

    def test_non_allowlisted_scripts_path_is_violation(self):
        violations = self._check_violations(["scripts/unknown_script.py"])
        self.assertIn("scripts/unknown_script.py", violations)

    def test_pipelines_allowlisted_no_violation(self):
        violations = self._check_violations(["pipelines/system1_trading.features.yaml"])
        self.assertEqual(violations, [])

    def test_pipelines_non_allowlisted_is_violation(self):
        violations = self._check_violations(["pipelines/other.yaml"])
        self.assertIn("pipelines/other.yaml", violations)

    def test_workspace_path_no_violation(self):
        violations = self._check_violations(["workspace/router/router.py"])
        self.assertEqual(violations, [])

    def test_empty_staged_no_violations(self):
        violations = self._check_violations([])
        self.assertEqual(violations, [])

    def test_backslash_path_normalized(self):
        # Windows-style paths with backslashes are normalized to forward slashes
        violations = self._check_violations(["scripts\\bad_file.py"])
        self.assertIn("scripts/bad_file.py", violations)

    def test_multiple_violations_detected(self):
        paths = ["scripts/a.py", "sim/b.py", "workspace/c.py"]
        violations = self._check_violations(paths)
        self.assertIn("scripts/a.py", violations)
        self.assertIn("sim/b.py", violations)
        self.assertNotIn("workspace/c.py", violations)

    def test_itc_path_is_violation(self):
        violations = self._check_violations(["itc/connector.py"])
        self.assertIn("itc/connector.py", violations)

    def test_market_path_is_violation(self):
        violations = self._check_violations(["market/data_feed.py"])
        self.assertIn("market/data_feed.py", violations)

    def test_telegram_path_is_violation(self):
        violations = self._check_violations(["telegram/handler.py"])
        self.assertIn("telegram/handler.py", violations)

    def test_each_violation_added_once(self):
        # A path matching one root should only appear once in violations
        violations = self._check_violations(["scripts/dup.py"])
        self.assertEqual(violations.count("scripts/dup.py"), 1)


if __name__ == "__main__":
    unittest.main()
