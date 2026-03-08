"""Tests for workspace/tacti/mirror.py pure helper functions.

Covers (tempfile-backed where needed):
- behavioral_fingerprint
- write_weekly_report
"""
import sys
import tempfile
import types
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

# Build minimal tacti package stubs before importing the module.
def _build_tacti_stubs():
    tacti_pkg = sys.modules.get("tacti")
    if tacti_pkg is None:
        tacti_pkg = types.ModuleType("tacti")
        tacti_pkg.__path__ = [str(REPO_ROOT / "workspace" / "tacti")]
        sys.modules["tacti"] = tacti_pkg

    if "tacti.config" not in sys.modules:
        config_mod = types.ModuleType("tacti.config")
        config_mod.get_int = lambda key, default, clamp=None: default
        config_mod.is_enabled = lambda key: False
        sys.modules["tacti.config"] = config_mod

    if "tacti.events" not in sys.modules:
        events_mod = types.ModuleType("tacti.events")
        events_mod.emit = lambda *a, **kw: None
        sys.modules["tacti.events"] = events_mod

_build_tacti_stubs()

if str(REPO_ROOT / "workspace") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "workspace"))

from tacti import mirror as mi  # noqa: E402


# ---------------------------------------------------------------------------
# behavioral_fingerprint
# ---------------------------------------------------------------------------

class TestBehavioralFingerprint(unittest.TestCase):
    """Tests for behavioral_fingerprint() — returns metrics dict from state."""

    def test_returns_dict(self):
        with tempfile.TemporaryDirectory() as td:
            result = mi.behavioral_fingerprint("agentX", repo_root=Path(td))
            self.assertIsInstance(result, dict)

    def test_agent_field_matches(self):
        with tempfile.TemporaryDirectory() as td:
            result = mi.behavioral_fingerprint("agentY", repo_root=Path(td))
            self.assertEqual(result["agent"], "agentY")

    def test_metrics_key_present(self):
        with tempfile.TemporaryDirectory() as td:
            result = mi.behavioral_fingerprint("a1", repo_root=Path(td))
            self.assertIn("metrics", result)

    def test_metrics_has_escalation_rate(self):
        with tempfile.TemporaryDirectory() as td:
            result = mi.behavioral_fingerprint("a2", repo_root=Path(td))
            self.assertIn("escalation_rate", result["metrics"])

    def test_metrics_has_p50_latency(self):
        with tempfile.TemporaryDirectory() as td:
            result = mi.behavioral_fingerprint("a3", repo_root=Path(td))
            self.assertIn("p50_latency_ms", result["metrics"])

    def test_fresh_state_zero_escalation(self):
        with tempfile.TemporaryDirectory() as td:
            result = mi.behavioral_fingerprint("a4", repo_root=Path(td))
            self.assertAlmostEqual(result["metrics"]["escalation_rate"], 0.0)

    def test_events_field_present(self):
        with tempfile.TemporaryDirectory() as td:
            result = mi.behavioral_fingerprint("a5", repo_root=Path(td))
            self.assertIn("events", result)


# ---------------------------------------------------------------------------
# write_weekly_report
# ---------------------------------------------------------------------------

class TestWriteWeeklyReport(unittest.TestCase):
    """Tests for write_weekly_report() — writes markdown report."""

    def _prep_root(self, td: str) -> Path:
        """Create required workspace/audit subdir so write_weekly_report doesn't fail."""
        root = Path(td)
        (root / "workspace" / "audit").mkdir(parents=True, exist_ok=True)
        return root

    def test_creates_file(self):
        with tempfile.TemporaryDirectory() as td:
            root = self._prep_root(td)
            path = mi.write_weekly_report(root, "2026-W10", ["agentA"])
            self.assertTrue(path.exists())

    def test_returns_path(self):
        with tempfile.TemporaryDirectory() as td:
            root = self._prep_root(td)
            result = mi.write_weekly_report(root, "2026-W11", ["agentB"])
            self.assertIsInstance(result, Path)

    def test_file_contains_week_id(self):
        with tempfile.TemporaryDirectory() as td:
            root = self._prep_root(td)
            path = mi.write_weekly_report(root, "2026-W12", ["agentC"])
            content = path.read_text(encoding="utf-8")
            self.assertIn("2026-W12", content)

    def test_file_contains_agent_name(self):
        with tempfile.TemporaryDirectory() as td:
            root = self._prep_root(td)
            path = mi.write_weekly_report(root, "2026-W13", ["myagent"])
            content = path.read_text(encoding="utf-8")
            self.assertIn("myagent", content)

    def test_multiple_agents_all_in_report(self):
        with tempfile.TemporaryDirectory() as td:
            root = self._prep_root(td)
            path = mi.write_weekly_report(root, "2026-W14", ["agent1", "agent2"])
            content = path.read_text(encoding="utf-8")
            self.assertIn("agent1", content)
            self.assertIn("agent2", content)

    def test_file_is_markdown(self):
        with tempfile.TemporaryDirectory() as td:
            root = self._prep_root(td)
            path = mi.write_weekly_report(root, "2026-W15", ["a"])
            self.assertTrue(path.suffix == ".md")


if __name__ == "__main__":
    unittest.main()
