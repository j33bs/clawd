"""Tests for workspace/scripts/run_novel10_fixture.py pure helper functions.

Covers (no subprocess, no tacti_cr at test time):
- _parse_now
- _load_messages (with tempfile)
- _set_offline_guards (env var side effects)
"""
import json
import os
import sys
import tempfile
import unittest
from datetime import timezone
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "workspace" / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from run_novel10_fixture import _load_messages, _parse_now, _set_offline_guards  # noqa: E402


# ---------------------------------------------------------------------------
# _parse_now
# ---------------------------------------------------------------------------

class TestParseNow(unittest.TestCase):
    """Tests for _parse_now() — ISO text → UTC-aware datetime."""

    def test_returns_utc_aware(self):
        result = _parse_now("2026-01-15T12:00:00Z")
        self.assertEqual(result.tzinfo, timezone.utc)

    def test_z_suffix(self):
        result = _parse_now("2026-03-08T10:30:00Z")
        self.assertEqual(result.hour, 10)
        self.assertEqual(result.minute, 30)

    def test_year_month_day(self):
        result = _parse_now("2026-01-15T00:00:00Z")
        self.assertEqual(result.year, 2026)
        self.assertEqual(result.month, 1)
        self.assertEqual(result.day, 15)

    def test_naive_treated_as_utc(self):
        result = _parse_now("2026-01-15T12:00:00")
        self.assertEqual(result.tzinfo, timezone.utc)

    def test_offset_converted_to_utc(self):
        # +02:00 offset → same UTC moment
        result = _parse_now("2026-01-15T14:00:00+02:00")
        self.assertEqual(result.hour, 12)  # 14 - 2 = 12 UTC


# ---------------------------------------------------------------------------
# _load_messages
# ---------------------------------------------------------------------------

class TestLoadMessages(unittest.TestCase):
    """Tests for _load_messages() — JSONL path → list of dicts."""

    def test_valid_jsonl(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "msgs.jsonl"
            path.write_text(
                '{"content": "hello"}\n{"content": "world"}\n', encoding="utf-8"
            )
            rows = _load_messages(path)
            self.assertEqual(len(rows), 2)

    def test_blank_lines_skipped(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "msgs.jsonl"
            path.write_text('\n{"content": "a"}\n\n', encoding="utf-8")
            rows = _load_messages(path)
            self.assertEqual(len(rows), 1)

    def test_returns_list(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "msgs.jsonl"
            path.write_text('{"x": 1}\n', encoding="utf-8")
            self.assertIsInstance(_load_messages(path), list)

    def test_content_field_accessible(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "msgs.jsonl"
            path.write_text('{"content": "test message"}\n', encoding="utf-8")
            rows = _load_messages(path)
            self.assertEqual(rows[0]["content"], "test message")


# ---------------------------------------------------------------------------
# _set_offline_guards
# ---------------------------------------------------------------------------

class TestSetOfflineGuards(unittest.TestCase):
    """Tests for _set_offline_guards() — sets env vars to disable live systems."""

    def test_sets_teamchat_live_to_zero(self):
        _set_offline_guards()
        self.assertEqual(os.environ.get("TEAMCHAT_LIVE"), "0")

    def test_sets_auto_commit_to_zero(self):
        _set_offline_guards()
        self.assertEqual(os.environ.get("TEAMCHAT_AUTO_COMMIT"), "0")

    def test_sets_accept_patches_to_zero(self):
        _set_offline_guards()
        self.assertEqual(os.environ.get("TEAMCHAT_ACCEPT_PATCHES"), "0")


if __name__ == "__main__":
    unittest.main()
