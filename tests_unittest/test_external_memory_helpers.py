"""Tests for workspace/tacti/external_memory.py pure helpers.

Stdlib-only (json, os, socket, subprocess, datetime, pathlib, uuid4).
Uses env var patching for _events_file_path.

Covers:
- _utc_now_iso
- _events_file_path
- _parse_ts
- read_events
"""
import importlib.util as _ilu
import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[1]

_spec = _ilu.spec_from_file_location(
    "external_memory_real",
    str(REPO_ROOT / "workspace" / "tacti" / "external_memory.py"),
)
em = _ilu.module_from_spec(_spec)
sys.modules["external_memory_real"] = em
_spec.loader.exec_module(em)


# ---------------------------------------------------------------------------
# _utc_now_iso
# ---------------------------------------------------------------------------

class TestUtcNowIso(unittest.TestCase):
    """Tests for _utc_now_iso() — current UTC time as ISO string."""

    def test_returns_string(self):
        result = em._utc_now_iso()
        self.assertIsInstance(result, str)

    def test_contains_date(self):
        result = em._utc_now_iso()
        self.assertIn("2026", result)  # we're in 2026

    def test_no_z_suffix(self):
        # external_memory._utc_now_iso uses .isoformat() without replace
        result = em._utc_now_iso()
        self.assertIn("+00:00", result)


# ---------------------------------------------------------------------------
# _events_file_path
# ---------------------------------------------------------------------------

class TestEventsFilePath(unittest.TestCase):
    """Tests for _events_file_path() — resolve events file via env or default."""

    def test_env_override_used(self):
        with patch.dict(os.environ, {"OPENCLAW_EXTERNAL_MEMORY_FILE": "/tmp/events.jsonl"}):
            result = em._events_file_path()
            self.assertEqual(result.name, "events.jsonl")

    def test_env_override_is_path(self):
        with patch.dict(os.environ, {"OPENCLAW_EXTERNAL_MEMORY_FILE": "/tmp/events.jsonl"}):
            result = em._events_file_path()
            self.assertIsInstance(result, Path)

    def test_default_contains_external_memory(self):
        env = {k: v for k, v in os.environ.items() if k != "OPENCLAW_EXTERNAL_MEMORY_FILE"}
        with patch.dict(os.environ, env, clear=True):
            result = em._events_file_path()
            self.assertIn("external_memory", str(result))

    def test_empty_env_uses_default(self):
        with patch.dict(os.environ, {"OPENCLAW_EXTERNAL_MEMORY_FILE": ""}):
            result = em._events_file_path()
            self.assertIn("external_memory", str(result))


# ---------------------------------------------------------------------------
# _parse_ts
# ---------------------------------------------------------------------------

class TestParseTs(unittest.TestCase):
    """Tests for _parse_ts() — parses ISO timestamp string to datetime."""

    def test_valid_z_string(self):
        result = em._parse_ts("2026-01-15T10:00:00Z")
        self.assertIsNotNone(result)
        self.assertEqual(result.year, 2026)

    def test_valid_offset_string(self):
        result = em._parse_ts("2026-06-01T12:00:00+00:00")
        self.assertIsNotNone(result)
        self.assertIsNotNone(result.tzinfo)

    def test_empty_string_returns_none(self):
        self.assertIsNone(em._parse_ts(""))

    def test_non_string_returns_none(self):
        self.assertIsNone(em._parse_ts(None))
        self.assertIsNone(em._parse_ts(42))

    def test_invalid_string_returns_none(self):
        self.assertIsNone(em._parse_ts("not-a-date"))

    def test_naive_datetime_gets_utc(self):
        result = em._parse_ts("2026-01-01T00:00:00")
        self.assertIsNotNone(result)
        self.assertIsNotNone(result.tzinfo)

    def test_returns_datetime(self):
        result = em._parse_ts("2026-01-01T00:00:00Z")
        self.assertIsInstance(result, datetime)


# ---------------------------------------------------------------------------
# read_events
# ---------------------------------------------------------------------------

class TestReadEvents(unittest.TestCase):
    """Tests for read_events() — reads JSONL events with optional filters."""

    def _write_events(self, td, events):
        p = Path(td) / "events.jsonl"
        lines = [json.dumps(ev) for ev in events]
        p.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return str(p)

    def test_missing_file_returns_empty(self):
        with patch.dict(os.environ, {"OPENCLAW_EXTERNAL_MEMORY_FILE": "/no/file.jsonl"}):
            result = em.read_events()
            self.assertEqual(result, [])

    def test_reads_all_events(self):
        with tempfile.TemporaryDirectory() as td:
            events = [{"event_type": "boot", "ts_utc": "2026-01-01T00:00:00Z"}] * 3
            path = self._write_events(td, events)
            with patch.dict(os.environ, {"OPENCLAW_EXTERNAL_MEMORY_FILE": path}):
                result = em.read_events()
            self.assertEqual(len(result), 3)

    def test_event_type_filter(self):
        with tempfile.TemporaryDirectory() as td:
            events = [
                {"event_type": "boot", "ts_utc": "2026-01-01T00:00:00Z"},
                {"event_type": "shutdown", "ts_utc": "2026-01-01T01:00:00Z"},
            ]
            path = self._write_events(td, events)
            with patch.dict(os.environ, {"OPENCLAW_EXTERNAL_MEMORY_FILE": path}):
                result = em.read_events(event_type="boot")
            self.assertEqual(len(result), 1)
            self.assertEqual(result[0]["event_type"], "boot")

    def test_limit_applied(self):
        with tempfile.TemporaryDirectory() as td:
            events = [{"event_type": f"e{i}", "ts_utc": "2026-01-01T00:00:00Z"} for i in range(10)]
            path = self._write_events(td, events)
            with patch.dict(os.environ, {"OPENCLAW_EXTERNAL_MEMORY_FILE": path}):
                result = em.read_events(limit=3)
            self.assertEqual(len(result), 3)

    def test_since_filter(self):
        with tempfile.TemporaryDirectory() as td:
            events = [
                {"event_type": "a", "ts_utc": "2026-01-01T00:00:00Z"},
                {"event_type": "b", "ts_utc": "2026-06-01T00:00:00Z"},
            ]
            path = self._write_events(td, events)
            with patch.dict(os.environ, {"OPENCLAW_EXTERNAL_MEMORY_FILE": path}):
                result = em.read_events(since_ts_utc="2026-03-01T00:00:00Z")
            self.assertEqual(len(result), 1)
            self.assertEqual(result[0]["event_type"], "b")

    def test_returns_list(self):
        with patch.dict(os.environ, {"OPENCLAW_EXTERNAL_MEMORY_FILE": "/no/file.jsonl"}):
            result = em.read_events()
            self.assertIsInstance(result, list)


if __name__ == "__main__":
    unittest.main()
