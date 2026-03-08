"""Tests for pure helpers in workspace/scripts/heavy_worker.py.

Stubs contract_policy to allow clean module load.
Covers (no network, no subprocess calls, minimal file I/O):
- utc_stamp
- parse_z
- append_jsonl
- read_jsonl
"""
import importlib.util as _ilu
import json
import sys
import tempfile
import types
import unittest
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "workspace" / "scripts"

# Stub contract_policy so the top-level import in heavy_worker doesn't fail.
# Include all attributes used by any script (idle_reaper, heavy_worker, etc.)
# so this stub remains safe regardless of test execution order.
if "contract_policy" not in sys.modules:
    _cp_stub = types.ModuleType("contract_policy")
    sys.modules["contract_policy"] = _cp_stub
else:
    _cp_stub = sys.modules["contract_policy"]

if not hasattr(_cp_stub, "gpu_tool_allowed_now"):
    _cp_stub.gpu_tool_allowed_now = lambda *a, **kw: {"allowed": False}
if not hasattr(_cp_stub, "load_contract"):
    _cp_stub.load_contract = lambda *a, **kw: {}
if not hasattr(_cp_stub, "contract_forces_code_override"):
    _cp_stub.contract_forces_code_override = lambda *a, **kw: False

if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

_spec = _ilu.spec_from_file_location(
    "heavy_worker_real",
    str(SCRIPTS_DIR / "heavy_worker.py"),
)
hw = _ilu.module_from_spec(_spec)
sys.modules["heavy_worker_real"] = hw
_spec.loader.exec_module(hw)

utc_stamp = hw.utc_stamp
parse_z = hw.parse_z
append_jsonl = hw.append_jsonl
read_jsonl = hw.read_jsonl


# ---------------------------------------------------------------------------
# utc_stamp
# ---------------------------------------------------------------------------

class TestUtcStamp(unittest.TestCase):
    """Tests for utc_stamp() — ISO UTC timestamp with Z suffix."""

    def test_returns_string(self):
        self.assertIsInstance(utc_stamp(), str)

    def test_ends_with_z(self):
        self.assertTrue(utc_stamp().endswith("Z"))

    def test_no_microseconds(self):
        self.assertNotIn(".", utc_stamp())

    def test_accepts_datetime_arg(self):
        dt = datetime(2026, 3, 7, 12, 0, 0, tzinfo=timezone.utc)
        result = utc_stamp(dt)
        self.assertIn("2026-03-07", result)
        self.assertTrue(result.endswith("Z"))

    def test_parseable(self):
        result = utc_stamp()
        # Remove Z and parse as +00:00
        datetime.fromisoformat(result.replace("Z", "+00:00"))


# ---------------------------------------------------------------------------
# parse_z
# ---------------------------------------------------------------------------

class TestParseZ(unittest.TestCase):
    """Tests for parse_z() — parse ISO timestamp (Z or +00:00 or naive)."""

    def test_z_suffix_parsed(self):
        result = parse_z("2026-03-07T12:00:00Z")
        self.assertIsNotNone(result)
        self.assertEqual(result.year, 2026)
        self.assertEqual(result.tzinfo, timezone.utc)

    def test_plus_offset_parsed(self):
        result = parse_z("2026-03-07T12:00:00+00:00")
        self.assertIsNotNone(result)
        self.assertEqual(result.tzinfo, timezone.utc)

    def test_none_returns_none(self):
        self.assertIsNone(parse_z(None))

    def test_empty_string_returns_none(self):
        self.assertIsNone(parse_z(""))

    def test_invalid_string_returns_none(self):
        self.assertIsNone(parse_z("not-a-date"))

    def test_naive_datetime_gets_utc(self):
        result = parse_z("2026-03-07T12:00:00")
        self.assertIsNotNone(result)
        self.assertEqual(result.tzinfo, timezone.utc)

    def test_returns_utc_datetime(self):
        result = parse_z("2026-01-01T00:00:00Z")
        self.assertIsInstance(result, datetime)


# ---------------------------------------------------------------------------
# append_jsonl
# ---------------------------------------------------------------------------

class TestAppendJsonl(unittest.TestCase):
    """Tests for append_jsonl() — append dict as JSON line to file."""

    def test_creates_file_and_parent_dirs(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "subdir" / "events.jsonl"
            append_jsonl(p, {"key": "value"})
            self.assertTrue(p.exists())

    def test_valid_json_written(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "events.jsonl"
            append_jsonl(p, {"x": 42})
            line = p.read_text(encoding="utf-8").strip()
            data = json.loads(line)
            self.assertEqual(data["x"], 42)

    def test_multiple_appends(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "events.jsonl"
            append_jsonl(p, {"n": 1})
            append_jsonl(p, {"n": 2})
            lines = [l for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]
            self.assertEqual(len(lines), 2)


# ---------------------------------------------------------------------------
# read_jsonl
# ---------------------------------------------------------------------------

class TestReadJsonl(unittest.TestCase):
    """Tests for read_jsonl() — read JSONL file to list of dicts."""

    def test_missing_file_returns_empty(self):
        result = read_jsonl(Path("/nonexistent/log.jsonl"))
        self.assertEqual(result, [])

    def test_valid_rows_returned(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "log.jsonl"
            p.write_text('{"a": 1}\n{"b": 2}\n', encoding="utf-8")
            result = read_jsonl(p)
            self.assertEqual(len(result), 2)
            self.assertEqual(result[0]["a"], 1)

    def test_blank_lines_skipped(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "log.jsonl"
            p.write_text('{"x": 1}\n\n{"y": 2}\n\n', encoding="utf-8")
            result = read_jsonl(p)
            self.assertEqual(len(result), 2)

    def test_invalid_json_lines_skipped(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "log.jsonl"
            p.write_text('{"ok": 1}\nNOT JSON\n{"also_ok": 2}\n', encoding="utf-8")
            result = read_jsonl(p)
            self.assertEqual(len(result), 2)

    def test_non_dict_rows_skipped(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "log.jsonl"
            p.write_text('[1, 2, 3]\n{"valid": true}\n', encoding="utf-8")
            result = read_jsonl(p)
            self.assertEqual(len(result), 1)

    def test_returns_list(self):
        result = read_jsonl(Path("/no/file.jsonl"))
        self.assertIsInstance(result, list)


if __name__ == "__main__":
    unittest.main()
