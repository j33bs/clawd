"""Tests for pause_check_diagnostic — _signal_tuple, _detect_runs, diagnose, render_text."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
TOOLS_DIR = REPO_ROOT / "workspace" / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import pause_check_diagnostic as pcd


def _make_entry(decision="silence", fills_space=0.85, value_add=0.0, silence_ok=True,
                rationale="test", ts="2026-03-08T00:00:00Z"):
    return {
        "decision": decision,
        "signals": {
            "fills_space": fills_space,
            "value_add": value_add,
            "silence_ok": silence_ok,
        },
        "rationale": rationale,
        "ts": ts,
    }


class TestSignalTuple(unittest.TestCase):
    """Tests for _signal_tuple() — pure extraction."""

    def test_extracts_all_fields(self):
        e = _make_entry("proceed", 0.5, 0.8, False, "ok")
        t = pcd._signal_tuple(e)
        self.assertEqual(t[0], "proceed")
        self.assertEqual(t[1], 0.5)
        self.assertEqual(t[2], 0.8)
        self.assertEqual(t[3], False)
        self.assertEqual(t[4], "ok")

    def test_missing_signals_returns_none(self):
        e = {"decision": "silence"}
        t = pcd._signal_tuple(e)
        self.assertEqual(t[0], "silence")
        self.assertIsNone(t[1])
        self.assertIsNone(t[2])
        self.assertIsNone(t[3])

    def test_missing_rationale_returns_empty_string(self):
        e = {"decision": "silence", "signals": {}}
        t = pcd._signal_tuple(e)
        self.assertEqual(t[4], "")

    def test_two_identical_entries_produce_equal_tuples(self):
        e1 = _make_entry()
        e2 = _make_entry()
        self.assertEqual(pcd._signal_tuple(e1), pcd._signal_tuple(e2))

    def test_different_decision_produces_different_tuples(self):
        e1 = _make_entry(decision="silence")
        e2 = _make_entry(decision="proceed")
        self.assertNotEqual(pcd._signal_tuple(e1), pcd._signal_tuple(e2))


class TestDetectRuns(unittest.TestCase):
    """Tests for _detect_runs() — consecutive run detection."""

    def test_empty_entries_returns_empty(self):
        self.assertEqual(pcd._detect_runs([]), [])

    def test_single_entry_returns_empty(self):
        self.assertEqual(pcd._detect_runs([_make_entry()]), [])

    def test_all_different_no_runs(self):
        entries = [
            _make_entry("silence"),
            _make_entry("proceed"),
            _make_entry("silence"),
        ]
        runs = pcd._detect_runs(entries)
        self.assertEqual(runs, [])

    def test_run_below_threshold_not_returned(self):
        # STUCK_THRESHOLD = 3; a run of 2 should not be returned
        entries = [_make_entry(), _make_entry()]
        runs = pcd._detect_runs(entries)
        self.assertEqual(runs, [])

    def test_run_at_threshold_returned(self):
        entries = [_make_entry(ts=f"t{i}") for i in range(pcd.STUCK_THRESHOLD)]
        runs = pcd._detect_runs(entries)
        self.assertEqual(len(runs), 1)
        self.assertEqual(runs[0]["length"], pcd.STUCK_THRESHOLD)

    def test_run_above_threshold_returned(self):
        entries = [_make_entry(ts=f"t{i}") for i in range(10)]
        runs = pcd._detect_runs(entries)
        self.assertEqual(len(runs), 1)
        self.assertEqual(runs[0]["length"], 10)

    def test_two_separate_runs_detected(self):
        same = [_make_entry(fills_space=0.85, ts=f"a{i}") for i in range(3)]
        different = [_make_entry(fills_space=0.5, decision="proceed", ts=f"b{i}") for i in range(3)]
        entries = same + different
        runs = pcd._detect_runs(entries)
        self.assertEqual(len(runs), 2)

    def test_run_contains_start_and_end_ts(self):
        entries = [_make_entry(ts=f"2026-03-08T0{i}:00:00Z") for i in range(5)]
        runs = pcd._detect_runs(entries)
        self.assertIn("start_ts", runs[0])
        self.assertIn("end_ts", runs[0])
        self.assertEqual(runs[0]["start_ts"], "2026-03-08T00:00:00Z")
        self.assertEqual(runs[0]["end_ts"], "2026-03-08T04:00:00Z")


class TestDiagnose(unittest.TestCase):
    """Tests for diagnose() — main diagnostic logic."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self._tmp = Path(self._tmpdir.name)
        self._orig_log = pcd.PAUSE_LOG
        pcd.PAUSE_LOG = self._tmp / "pause_check_log.jsonl"

    def tearDown(self):
        pcd.PAUSE_LOG = self._orig_log
        self._tmpdir.cleanup()

    def _write_entries(self, entries):
        with pcd.PAUSE_LOG.open("w", encoding="utf-8") as f:
            for e in entries:
                f.write(json.dumps(e) + "\n")

    def test_no_data_when_log_missing(self):
        result = pcd.diagnose()
        self.assertEqual(result["status"], "no_data")
        self.assertEqual(result["total_entries"], 0)

    def test_ok_status_when_varied_entries(self):
        entries = [
            _make_entry("silence", 0.85, 0.0),
            _make_entry("proceed", 0.3, 0.7),
            _make_entry("silence", 0.9, 0.1),
        ]
        self._write_entries(entries)
        result = pcd.diagnose()
        self.assertEqual(result["status"], "ok")

    def test_stuck_status_when_all_identical(self):
        # 10 identical entries → stuck
        entries = [_make_entry(ts=f"t{i}") for i in range(10)]
        self._write_entries(entries)
        result = pcd.diagnose()
        self.assertEqual(result["status"], "stuck")

    def test_total_entries_correct(self):
        entries = [_make_entry() for _ in range(7)]
        self._write_entries(entries)
        result = pcd.diagnose()
        self.assertEqual(result["total_entries"], 7)

    def test_decision_distribution_counted(self):
        entries = [
            _make_entry("silence"),
            _make_entry("silence"),
            _make_entry("proceed"),
        ]
        self._write_entries(entries)
        result = pcd.diagnose()
        dist = result["decision_distribution"]
        self.assertEqual(dist.get("silence"), 2)
        self.assertEqual(dist.get("proceed"), 1)

    def test_fills_space_variance_zero_when_constant(self):
        entries = [_make_entry(fills_space=0.85, ts=f"t{i}") for i in range(5)]
        self._write_entries(entries)
        result = pcd.diagnose()
        self.assertAlmostEqual(result["fills_space_variance"], 0.0)

    def test_fills_space_variance_nonzero_when_varied(self):
        entries = [
            _make_entry(fills_space=0.2),
            _make_entry(fills_space=0.8),
            _make_entry(fills_space=0.5),
        ]
        self._write_entries(entries)
        result = pcd.diagnose()
        self.assertGreater(result["fills_space_variance"], 0.0)

    def test_stuck_runs_in_result(self):
        entries = [_make_entry(ts=f"t{i}") for i in range(5)]
        self._write_entries(entries)
        result = pcd.diagnose()
        self.assertIn("stuck_runs", result)
        self.assertEqual(len(result["stuck_runs"]), 1)

    def test_diagnosis_text_contains_stuck_keyword_when_stuck(self):
        entries = [_make_entry(ts=f"t{i}") for i in range(5)]
        self._write_entries(entries)
        result = pcd.diagnose()
        self.assertIn("STUCK", result["diagnosis"])

    def test_diagnosis_text_contains_ok_keyword_when_ok(self):
        entries = [
            _make_entry("silence", 0.85, 0.0),
            _make_entry("proceed", 0.2, 0.9),
            _make_entry("silence", 0.6, 0.3),
        ]
        self._write_entries(entries)
        result = pcd.diagnose()
        self.assertIn("OK", result["diagnosis"])


class TestRenderText(unittest.TestCase):
    """Tests for render_text() — pure text rendering."""

    def test_no_data_returns_short_message(self):
        d = {"status": "no_data", "log_path": "/tmp/log", "total_entries": 0}
        text = pcd.render_text(d)
        self.assertIn("No data", text)

    def test_ok_status_shown_in_output(self):
        d = {
            "status": "ok",
            "log_path": "/tmp/log",
            "total_entries": 5,
            "decision_distribution": {"silence": 3, "proceed": 2},
            "identical_signal_fraction": 0.3,
            "fills_space_variance": 0.01,
            "value_add_variance": 0.02,
            "most_common_signal": {
                "decision": "silence", "fills_space": 0.85, "value_add": 0.0,
                "silence_ok": True, "rationale": "test", "count": 3,
            },
            "stuck_runs": [],
            "diagnosis": "OK: classifier appears responsive.",
            "recommendation": "No action required.",
        }
        text = pcd.render_text(d)
        self.assertIn("OK", text)
        self.assertIn("5", text)

    def test_stuck_runs_shown_when_present(self):
        d = {
            "status": "stuck",
            "log_path": "/tmp/log",
            "total_entries": 10,
            "decision_distribution": {"silence": 10},
            "identical_signal_fraction": 1.0,
            "fills_space_variance": 0.0,
            "value_add_variance": 0.0,
            "most_common_signal": {
                "decision": "silence", "fills_space": 0.85, "value_add": 0.0,
                "silence_ok": True, "rationale": "", "count": 10,
            },
            "stuck_runs": [{"start_ts": "t0", "end_ts": "t9", "length": 10}],
            "diagnosis": "STUCK: classifier returning identical signals.",
            "recommendation": "1. Check code.\n2. Reset log.",
        }
        text = pcd.render_text(d)
        self.assertIn("stuck", text.lower())
        self.assertIn("t0", text)
        self.assertIn("t9", text)


if __name__ == "__main__":
    unittest.main()
