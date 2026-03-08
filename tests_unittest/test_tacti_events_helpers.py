"""Tests for workspace/tacti/events.py pure helpers.

No external deps — stdlib only. Loaded with a unique module name.

Covers:
- _utc_iso_z
- _coerce_json
- _resolve
- _is_quiesced
- read_events
- summarize_by_type
"""
import importlib.util as _ilu
import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[1]

_spec = _ilu.spec_from_file_location(
    "tacti_events_real",
    str(REPO_ROOT / "workspace" / "tacti" / "events.py"),
)
ev = _ilu.module_from_spec(_spec)
sys.modules["tacti_events_real"] = ev
_spec.loader.exec_module(ev)


# ---------------------------------------------------------------------------
# _utc_iso_z
# ---------------------------------------------------------------------------

class TestUtcIsoZ(unittest.TestCase):
    """Tests for _utc_iso_z() — formats a datetime as UTC ISO 8601 with Z."""

    def test_returns_string_ending_with_z(self):
        result = ev._utc_iso_z()
        self.assertTrue(result.endswith("Z"))

    def test_explicit_utc_datetime(self):
        dt = datetime(2026, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        result = ev._utc_iso_z(dt)
        self.assertEqual(result, "2026-01-15T12:00:00Z")

    def test_naive_datetime_treated_as_utc(self):
        dt = datetime(2026, 6, 1, 8, 30, 0)
        result = ev._utc_iso_z(dt)
        self.assertIn("2026-06-01", result)
        self.assertTrue(result.endswith("Z"))

    def test_offset_aware_converted_to_utc(self):
        # +02:00 → subtract 2 hours → 10:00 UTC
        dt = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone(timedelta(hours=2)))
        result = ev._utc_iso_z(dt)
        self.assertIn("10:00:00Z", result)

    def test_no_plus_offset_in_result(self):
        result = ev._utc_iso_z()
        self.assertNotIn("+00:00", result)

    def test_returns_string(self):
        self.assertIsInstance(ev._utc_iso_z(), str)


# ---------------------------------------------------------------------------
# _coerce_json
# ---------------------------------------------------------------------------

class TestCoerceJson(unittest.TestCase):
    """Tests for _coerce_json() — validates dict is JSON-serializable."""

    def test_valid_dict_returned(self):
        d = {"key": "value", "n": 42}
        result = ev._coerce_json(d)
        self.assertEqual(result, d)

    def test_non_dict_raises(self):
        with self.assertRaises(TypeError):
            ev._coerce_json([1, 2, 3])

    def test_string_raises(self):
        with self.assertRaises(TypeError):
            ev._coerce_json("not a dict")

    def test_none_raises(self):
        with self.assertRaises(TypeError):
            ev._coerce_json(None)

    def test_non_serializable_raises(self):
        with self.assertRaises(TypeError):
            ev._coerce_json({"obj": object()})

    def test_nested_dict_ok(self):
        d = {"a": {"b": [1, 2, 3]}, "c": None}
        result = ev._coerce_json(d)
        self.assertEqual(result["a"]["b"], [1, 2, 3])


# ---------------------------------------------------------------------------
# _resolve
# ---------------------------------------------------------------------------

class TestResolve(unittest.TestCase):
    """Tests for _resolve() — resolves a path relative to repo root."""

    def test_absolute_path_returned_as_is(self):
        p = Path("/tmp/absolute/path.jsonl")
        result = ev._resolve(p)
        self.assertEqual(result, p)

    def test_none_uses_default_path(self):
        result = ev._resolve(None)
        self.assertIsInstance(result, Path)
        self.assertTrue(result.is_absolute())

    def test_string_path_resolved(self):
        result = ev._resolve("workspace/state/something.jsonl")
        self.assertIsInstance(result, Path)
        self.assertTrue(result.is_absolute())

    def test_relative_path_resolved_from_repo(self):
        result = ev._resolve("workspace/state/something.jsonl")
        self.assertIn("workspace", str(result))

    def test_returns_path(self):
        result = ev._resolve(None)
        self.assertIsInstance(result, Path)


# ---------------------------------------------------------------------------
# _is_quiesced
# ---------------------------------------------------------------------------

class TestIsQuiesced(unittest.TestCase):
    """Tests for _is_quiesced() — reads OPENCLAW_QUIESCE env var."""

    def test_unset_returns_false(self):
        env = {k: v for k, v in os.environ.items() if k != "OPENCLAW_QUIESCE"}
        with patch.dict(os.environ, env, clear=True):
            self.assertFalse(ev._is_quiesced())

    def test_set_to_one_returns_true(self):
        with patch.dict(os.environ, {"OPENCLAW_QUIESCE": "1"}):
            self.assertTrue(ev._is_quiesced())

    def test_set_to_zero_returns_false(self):
        with patch.dict(os.environ, {"OPENCLAW_QUIESCE": "0"}):
            self.assertFalse(ev._is_quiesced())

    def test_empty_string_returns_false(self):
        with patch.dict(os.environ, {"OPENCLAW_QUIESCE": ""}):
            self.assertFalse(ev._is_quiesced())

    def test_returns_bool(self):
        with patch.dict(os.environ, {"OPENCLAW_QUIESCE": "1"}):
            result = ev._is_quiesced()
            self.assertIsInstance(result, bool)


# ---------------------------------------------------------------------------
# read_events
# ---------------------------------------------------------------------------

class TestReadEvents(unittest.TestCase):
    """Tests for read_events() — reads JSONL event file."""

    def test_missing_file_returns_empty(self):
        result = ev.read_events(Path("/nonexistent/events.jsonl"))
        self.assertEqual(list(result), [])

    def test_valid_jsonl_returned(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "events.jsonl"
            p.write_text(
                json.dumps({"type": "test", "payload": {}}) + "\n",
                encoding="utf-8",
            )
            result = list(ev.read_events(p))
            self.assertEqual(len(result), 1)
            self.assertEqual(result[0]["type"], "test")

    def test_multiple_events(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "events.jsonl"
            lines = [json.dumps({"type": f"t{i}"}) for i in range(3)]
            p.write_text("\n".join(lines) + "\n", encoding="utf-8")
            result = list(ev.read_events(p))
            self.assertEqual(len(result), 3)

    def test_blank_lines_skipped(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "events.jsonl"
            p.write_text("\n\n" + json.dumps({"type": "x"}) + "\n\n", encoding="utf-8")
            result = list(ev.read_events(p))
            self.assertEqual(len(result), 1)

    def test_invalid_json_raises(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "events.jsonl"
            p.write_text("NOT JSON\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                list(ev.read_events(p))


# ---------------------------------------------------------------------------
# summarize_by_type
# ---------------------------------------------------------------------------

class TestSummarizeByType(unittest.TestCase):
    """Tests for summarize_by_type() — count events by type key."""

    def test_empty_file_returns_empty_dict(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "events.jsonl"
            p.write_text("", encoding="utf-8")
            result = ev.summarize_by_type(p)
            self.assertEqual(result, {})

    def test_single_event_counted(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "events.jsonl"
            p.write_text(json.dumps({"type": "boot", "payload": {}}) + "\n", encoding="utf-8")
            result = ev.summarize_by_type(p)
            self.assertEqual(result["boot"], 1)

    def test_multiple_same_type(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "events.jsonl"
            lines = [json.dumps({"type": "ping"}) for _ in range(5)]
            p.write_text("\n".join(lines) + "\n", encoding="utf-8")
            result = ev.summarize_by_type(p)
            self.assertEqual(result["ping"], 5)

    def test_multiple_types(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "events.jsonl"
            p.write_text(
                json.dumps({"type": "a"}) + "\n"
                + json.dumps({"type": "b"}) + "\n"
                + json.dumps({"type": "a"}) + "\n",
                encoding="utf-8",
            )
            result = ev.summarize_by_type(p)
            self.assertEqual(result["a"], 2)
            self.assertEqual(result["b"], 1)

    def test_missing_file_returns_empty(self):
        result = ev.summarize_by_type(Path("/no/file/here.jsonl"))
        self.assertEqual(result, {})

    def test_returns_dict(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "events.jsonl"
            p.write_text("", encoding="utf-8")
            result = ev.summarize_by_type(p)
            self.assertIsInstance(result, dict)


if __name__ == "__main__":
    unittest.main()
