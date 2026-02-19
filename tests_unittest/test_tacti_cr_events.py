from __future__ import annotations

import importlib.util
import tempfile
from datetime import datetime, timezone
from pathlib import Path
import unittest


def _load_events_module():
    repo_root = Path(__file__).resolve().parents[1]
    mod_path = repo_root / "workspace" / "tacti_cr" / "events.py"
    spec = importlib.util.spec_from_file_location("tacti_cr_events", str(mod_path))
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class TestTactiCrEvents(unittest.TestCase):
    def setUp(self):
        self.events = _load_events_module()
        self._tmp = tempfile.TemporaryDirectory()
        self.path = Path(self._tmp.name) / "events.jsonl"
        self._old_default = self.events.DEFAULT_PATH
        self.events.DEFAULT_PATH = self.path

    def tearDown(self):
        self.events.DEFAULT_PATH = self._old_default
        self._tmp.cleanup()

    def test_emit_and_read_deterministic_timestamp(self):
        fixed = datetime(2026, 2, 19, 12, 34, 56, tzinfo=timezone.utc)
        self.events.emit("tacti_cr.test.one", {"a": 1}, now=fixed, session_id="s-1")
        rows = list(self.events.read_events(self.path))
        self.assertEqual(1, len(rows))
        self.assertEqual("2026-02-19T12:34:56Z", rows[0]["ts"])
        self.assertEqual("tacti_cr.test.one", rows[0]["type"])
        self.assertEqual({"a": 1}, rows[0]["payload"])
        self.assertEqual("s-1", rows[0]["session_id"])
        self.assertEqual(1, rows[0]["schema"])

    def test_summarize_by_type(self):
        fixed = datetime(2026, 2, 19, 1, 2, 3, tzinfo=timezone.utc)
        self.events.emit("tacti_cr.alpha", {"x": 1}, now=fixed)
        self.events.emit("tacti_cr.beta", {"x": 2}, now=fixed)
        self.events.emit("tacti_cr.alpha", {"x": 3}, now=fixed)
        summary = self.events.summarize_by_type(self.path)
        self.assertEqual({"tacti_cr.alpha": 2, "tacti_cr.beta": 1}, summary)

    def test_non_serializable_payload(self):
        with self.assertRaises(TypeError):
            self.events._coerce_json({"bad": {1, 2, 3}})


if __name__ == "__main__":
    unittest.main()
