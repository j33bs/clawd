"""Tests for pure helpers in workspace/runtime/heavy_node/logging.py.

Pure stdlib (json, pathlib, time) — no stubs needed.
Uses tempfile for filesystem isolation.

Covers:
- HeavyNodeTelemetry.__init__
- HeavyNodeTelemetry.write (strips prompt/messages, appends JSON)
- HeavyNodeTelemetry._rollup (metrics accumulation)
"""
import importlib.util as _ilu
import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
HN_LOGGING_PATH = REPO_ROOT / "workspace" / "runtime" / "heavy_node" / "logging.py"

_spec = _ilu.spec_from_file_location("heavy_node_logging_real", str(HN_LOGGING_PATH))
hn = _ilu.module_from_spec(_spec)
sys.modules["heavy_node_logging_real"] = hn
_spec.loader.exec_module(hn)


def _make_telemetry(tmp: str) -> "hn.HeavyNodeTelemetry":
    log_p = Path(tmp) / "logs" / "heavy_node_calls.jsonl"
    met_p = Path(tmp) / "metrics" / "heavy_node_rollup.json"
    return hn.HeavyNodeTelemetry(log_path=log_p, metrics_path=met_p)


# ---------------------------------------------------------------------------
# __init__
# ---------------------------------------------------------------------------

class TestHeavyNodeTelemetryInit(unittest.TestCase):
    """Tests for HeavyNodeTelemetry.__init__ — paths created."""

    def test_log_parent_created(self):
        with tempfile.TemporaryDirectory() as tmp:
            tel = _make_telemetry(tmp)
            self.assertTrue(tel.log_path.parent.exists())

    def test_metrics_parent_created(self):
        with tempfile.TemporaryDirectory() as tmp:
            tel = _make_telemetry(tmp)
            self.assertTrue(tel.metrics_path.parent.exists())

    def test_log_path_is_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            tel = _make_telemetry(tmp)
            self.assertIsInstance(tel.log_path, Path)

    def test_metrics_path_is_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            tel = _make_telemetry(tmp)
            self.assertIsInstance(tel.metrics_path, Path)


# ---------------------------------------------------------------------------
# write
# ---------------------------------------------------------------------------

class TestHeavyNodeTelemetryWrite(unittest.TestCase):
    """Tests for HeavyNodeTelemetry.write() — strips sensitive keys, appends log."""

    def test_strips_prompt_key(self):
        with tempfile.TemporaryDirectory() as tmp:
            tel = _make_telemetry(tmp)
            row = {"endpoint": "chat", "prompt": "secret prompt", "latency_ms": 100}
            tel.write(row)
            line = tel.log_path.read_text(encoding="utf-8").strip()
            logged = json.loads(line)
            self.assertNotIn("prompt", logged)

    def test_strips_messages_key(self):
        with tempfile.TemporaryDirectory() as tmp:
            tel = _make_telemetry(tmp)
            row = {"endpoint": "chat", "messages": [{"role": "user"}], "latency_ms": 50}
            tel.write(row)
            line = tel.log_path.read_text(encoding="utf-8").strip()
            logged = json.loads(line)
            self.assertNotIn("messages", logged)

    def test_appends_valid_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            tel = _make_telemetry(tmp)
            tel.write({"endpoint": "infer", "latency_ms": 200})
            raw = tel.log_path.read_text(encoding="utf-8").strip()
            self.assertIsInstance(json.loads(raw), dict)

    def test_multiple_writes_append_lines(self):
        with tempfile.TemporaryDirectory() as tmp:
            tel = _make_telemetry(tmp)
            tel.write({"endpoint": "a", "latency_ms": 10})
            tel.write({"endpoint": "b", "latency_ms": 20})
            lines = [l for l in tel.log_path.read_text(encoding="utf-8").splitlines() if l.strip()]
            self.assertEqual(len(lines), 2)

    def test_log_line_is_sorted_keys(self):
        with tempfile.TemporaryDirectory() as tmp:
            tel = _make_telemetry(tmp)
            tel.write({"z_key": 1, "a_key": 2, "latency_ms": 0})
            raw = tel.log_path.read_text(encoding="utf-8").strip()
            # json.dumps with sort_keys=True produces alphabetically sorted keys
            data = json.loads(raw)
            self.assertEqual(list(data.keys()), sorted(data.keys()))

    def test_non_sensitive_keys_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            tel = _make_telemetry(tmp)
            tel.write({"endpoint": "chat", "status": "ok", "latency_ms": 42})
            raw = json.loads(tel.log_path.read_text(encoding="utf-8").strip())
            self.assertEqual(raw["endpoint"], "chat")
            self.assertEqual(raw["status"], "ok")


# ---------------------------------------------------------------------------
# _rollup (via write)
# ---------------------------------------------------------------------------

class TestHeavyNodeTelemetryRollup(unittest.TestCase):
    """Tests for HeavyNodeTelemetry._rollup() — metrics accumulation."""

    def _read_metrics(self, tel: "hn.HeavyNodeTelemetry") -> dict:
        return json.loads(tel.metrics_path.read_text(encoding="utf-8"))

    def test_calls_total_increments(self):
        with tempfile.TemporaryDirectory() as tmp:
            tel = _make_telemetry(tmp)
            tel.write({"latency_ms": 100})
            tel.write({"latency_ms": 200})
            m = self._read_metrics(tel)
            self.assertEqual(m["calls_total"], 2)

    def test_latency_avg_ms_computed(self):
        with tempfile.TemporaryDirectory() as tmp:
            tel = _make_telemetry(tmp)
            tel.write({"latency_ms": 100})
            tel.write({"latency_ms": 200})
            m = self._read_metrics(tel)
            # avg of 100 and 200 = 150
            self.assertAlmostEqual(m["latency_avg_ms"], 150.0, places=1)

    def test_tokens_in_total_accumulates(self):
        with tempfile.TemporaryDirectory() as tmp:
            tel = _make_telemetry(tmp)
            tel.write({"tokens_in": 50, "latency_ms": 0})
            tel.write({"tokens_in": 30, "latency_ms": 0})
            m = self._read_metrics(tel)
            self.assertEqual(m["tokens_in_total"], 80)

    def test_tokens_out_total_accumulates(self):
        with tempfile.TemporaryDirectory() as tmp:
            tel = _make_telemetry(tmp)
            tel.write({"tokens_out": 15, "latency_ms": 0})
            tel.write({"tokens_out": 25, "latency_ms": 0})
            m = self._read_metrics(tel)
            self.assertEqual(m["tokens_out_total"], 40)

    def test_errors_total_increments_on_non_ok(self):
        with tempfile.TemporaryDirectory() as tmp:
            tel = _make_telemetry(tmp)
            tel.write({"status": "ok", "latency_ms": 0})
            tel.write({"status": "error", "latency_ms": 0})
            m = self._read_metrics(tel)
            self.assertEqual(m["errors_total"], 1)

    def test_ok_status_does_not_increment_errors(self):
        with tempfile.TemporaryDirectory() as tmp:
            tel = _make_telemetry(tmp)
            tel.write({"status": "ok", "latency_ms": 0})
            m = self._read_metrics(tel)
            self.assertEqual(m["errors_total"], 0)

    def test_by_endpoint_tracks_count(self):
        with tempfile.TemporaryDirectory() as tmp:
            tel = _make_telemetry(tmp)
            tel.write({"endpoint": "chat", "latency_ms": 0})
            tel.write({"endpoint": "chat", "latency_ms": 0})
            tel.write({"endpoint": "embed", "latency_ms": 0})
            m = self._read_metrics(tel)
            self.assertEqual(m["by_endpoint"]["chat"]["count"], 2)
            self.assertEqual(m["by_endpoint"]["embed"]["count"], 1)

    def test_unknown_endpoint_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            tel = _make_telemetry(tmp)
            tel.write({"latency_ms": 0})  # no endpoint key
            m = self._read_metrics(tel)
            self.assertIn("unknown", m["by_endpoint"])

    def test_by_endpoint_tracks_latency_average(self):
        with tempfile.TemporaryDirectory() as tmp:
            tel = _make_telemetry(tmp)
            tel.write({"endpoint": "chat", "latency_ms": 100})
            tel.write({"endpoint": "chat", "latency_ms": 200})
            m = self._read_metrics(tel)
            self.assertAlmostEqual(m["by_endpoint"]["chat"]["latency_avg_ms"], 150.0, places=1)

    def test_by_endpoint_tracks_token_totals(self):
        with tempfile.TemporaryDirectory() as tmp:
            tel = _make_telemetry(tmp)
            tel.write({"endpoint": "chat", "tokens_in": 5, "tokens_out": 7, "latency_ms": 0})
            tel.write({"endpoint": "chat", "tokens_in": 3, "tokens_out": 2, "latency_ms": 0})
            m = self._read_metrics(tel)
            self.assertEqual(m["by_endpoint"]["chat"]["tokens_in_total"], 8)
            self.assertEqual(m["by_endpoint"]["chat"]["tokens_out_total"], 9)

    def test_by_endpoint_tracks_errors_and_last_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            tel = _make_telemetry(tmp)
            tel.write({"endpoint": "chat", "status": "ok", "latency_ms": 0})
            tel.write({"endpoint": "chat", "status": "error", "latency_ms": 0})
            m = self._read_metrics(tel)
            self.assertEqual(m["by_endpoint"]["chat"]["errors_total"], 1)
            self.assertEqual(m["by_endpoint"]["chat"]["last_status"], "error")

    def test_last_updated_utc_set(self):
        with tempfile.TemporaryDirectory() as tmp:
            tel = _make_telemetry(tmp)
            tel.write({"latency_ms": 0})
            m = self._read_metrics(tel)
            self.assertIsNotNone(m["last_updated_utc"])

    def test_metrics_survive_corrupt_file(self):
        """Corrupt metrics file is silently ignored; fresh baseline used."""
        with tempfile.TemporaryDirectory() as tmp:
            tel = _make_telemetry(tmp)
            tel.metrics_path.write_text("NOT JSON", encoding="utf-8")
            tel.write({"latency_ms": 50})  # should not raise
            m = self._read_metrics(tel)
            self.assertEqual(m["calls_total"], 1)


if __name__ == "__main__":
    unittest.main()
