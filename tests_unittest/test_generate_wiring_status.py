"""Tests for generate_wiring_status._enabled(), _status(), and generate()."""
import os
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "workspace" / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import generate_wiring_status as gws  # noqa: E402


class TestEnabled(unittest.TestCase):
    """Tests for _enabled() — env var boolean parsing."""

    def _with_env(self, key: str, value: str | None):
        """Context helper: set/unset an env var."""
        old = os.environ.pop(key, None)
        if value is not None:
            os.environ[key] = value
        return old

    def _restore(self, key: str, old) -> None:
        if old is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = old

    def test_missing_returns_false(self):
        key = "ENABLE_WIRING_TEST_NONEXISTENT"
        os.environ.pop(key, None)
        self.assertFalse(gws._enabled(key))

    def test_zero_returns_false(self):
        key = "ENABLE_WIRING_TEST_ZERO"
        old = self._with_env(key, "0")
        try:
            self.assertFalse(gws._enabled(key))
        finally:
            self._restore(key, old)

    def test_one_returns_true(self):
        key = "ENABLE_WIRING_TEST_ONE"
        old = self._with_env(key, "1")
        try:
            self.assertTrue(gws._enabled(key))
        finally:
            self._restore(key, old)

    def test_true_string_returns_true(self):
        key = "ENABLE_WIRING_TEST_TRUE"
        old = self._with_env(key, "true")
        try:
            self.assertTrue(gws._enabled(key))
        finally:
            self._restore(key, old)

    def test_yes_returns_true(self):
        key = "ENABLE_WIRING_TEST_YES"
        old = self._with_env(key, "yes")
        try:
            self.assertTrue(gws._enabled(key))
        finally:
            self._restore(key, old)


class TestStatus(unittest.TestCase):
    """Tests for _status() — module status classification."""

    def test_unknown_module_not_in_flag_map_is_decorative(self):
        status = gws._status("unknown_module_xyz", wired_modules=set())
        self.assertEqual(status, "decorative")

    def test_wired_module_without_flag_is_wired_but_passive(self):
        status = gws._status("trails", wired_modules={"trails"})
        # ENABLE_TRAIL_MEMORY not set
        os.environ.pop("ENABLE_TRAIL_MEMORY", None)
        status = gws._status("trails", wired_modules={"trails"})
        self.assertEqual(status, "wired but passive")

    def test_active_when_flag_set(self):
        os.environ["ENABLE_MURMURATION"] = "1"
        try:
            status = gws._status("peer_graph", wired_modules={"peer_graph"})
            self.assertEqual(status, "active")
        finally:
            del os.environ["ENABLE_MURMURATION"]

    def test_active_even_when_not_in_wired_set(self):
        """Flag enabled → active regardless of wired_modules membership."""
        os.environ["ENABLE_RESERVOIR"] = "1"
        try:
            status = gws._status("reservoir", wired_modules=set())
            self.assertEqual(status, "active")
        finally:
            del os.environ["ENABLE_RESERVOIR"]

    def test_decorative_when_in_flag_map_but_flag_off_and_not_wired(self):
        os.environ.pop("ENABLE_MURMURATION", None)
        status = gws._status("peer_graph", wired_modules=set())
        self.assertEqual(status, "decorative")


class TestGenerate(unittest.TestCase):
    """Tests for generate() — markdown output correctness."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self._tmp = Path(self._tmpdir.name)
        # Create a fake hivemind directory with a few .py files
        self._hive = self._tmp / "workspace" / "hivemind" / "hivemind"
        self._hive.mkdir(parents=True)
        (self._hive / "trails.py").write_text("# trails module\n")
        (self._hive / "reservoir.py").write_text("# reservoir module\n")
        (self._hive / "__init__.py").write_text("")
        # Patch module-level paths
        self._orig_hive = gws.HIVE_DIR
        self._orig_root = gws.REPO_ROOT
        gws.HIVE_DIR = self._hive
        gws.REPO_ROOT = self._tmp

    def tearDown(self):
        gws.HIVE_DIR = self._orig_hive
        gws.REPO_ROOT = self._orig_root
        self._tmpdir.cleanup()

    def test_output_file_created(self):
        out = self._tmp / "WIRING_STATUS.md"
        gws.generate(out)
        self.assertTrue(out.exists())

    def test_output_contains_module_names(self):
        out = self._tmp / "WIRING_STATUS.md"
        gws.generate(out)
        content = out.read_text(encoding="utf-8")
        self.assertIn("trails", content)
        self.assertIn("reservoir", content)

    def test_output_excludes_init(self):
        out = self._tmp / "WIRING_STATUS.md"
        gws.generate(out)
        content = out.read_text(encoding="utf-8")
        self.assertNotIn("__init__", content)

    def test_output_contains_header(self):
        out = self._tmp / "WIRING_STATUS.md"
        gws.generate(out)
        content = out.read_text(encoding="utf-8")
        self.assertIn("# Hivemind Wiring Status", content)
        self.assertIn("| module | status |", content)

    def test_decorative_when_no_flag_and_not_wired(self):
        """All modules with no flag set and not in dynamics_pipeline → decorative."""
        os.environ.pop("ENABLE_TRAIL_MEMORY", None)
        os.environ.pop("ENABLE_RESERVOIR", None)
        out = self._tmp / "WIRING_STATUS.md"
        gws.generate(out)
        content = out.read_text(encoding="utf-8")
        # Both should be 'decorative' (no dynamics_pipeline.py in fake dir)
        self.assertIn("decorative", content)

    def test_returns_relative_path_string(self):
        out = self._tmp / "out" / "WIRING_STATUS.md"
        rel = gws.generate(out)
        self.assertIsInstance(rel, str)
        self.assertFalse(Path(rel).is_absolute())


if __name__ == "__main__":
    unittest.main()
