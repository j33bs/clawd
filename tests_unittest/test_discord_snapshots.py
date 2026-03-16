import unittest
import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from workspace.discord_surface.snapshots import (
    _service_status,
    build_ops_snapshot,
    build_sim_snapshot,
    format_ops_message,
    format_sim_message,
)


class TestDiscordSnapshots(unittest.TestCase):
    @patch("workspace.discord_surface.snapshots.platform.system", return_value="Darwin")
    @patch("workspace.discord_surface.snapshots.os.getuid", return_value=501)
    @patch("workspace.discord_surface.snapshots.subprocess.run")
    def test_service_status_uses_launchctl_on_darwin(self, run_mock, _getuid, _system):
        run_mock.return_value.returncode = 0
        run_mock.return_value.stdout = "state = running\npid = 123\n"
        self.assertEqual(_service_status("ai.openclaw.qmd-mcp"), "running")
        run_mock.assert_called_once()
        self.assertEqual(run_mock.call_args.args[0], ["launchctl", "print", "gui/501/ai.openclaw.qmd-mcp"])

    @patch("workspace.discord_surface.snapshots.platform.system", return_value="Darwin")
    @patch("workspace.discord_surface.snapshots.os.getuid", return_value=501)
    @patch("workspace.discord_surface.snapshots.subprocess.run")
    def test_service_status_reports_not_loaded_on_missing_darwin_label(self, run_mock, _getuid, _system):
        run_mock.return_value.returncode = 113
        run_mock.return_value.stdout = ""
        run_mock.return_value.stderr = "Could not find service"
        self.assertEqual(_service_status("missing.label"), "not_loaded")

    def test_build_sim_snapshot_marks_old_payload_stale(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            sim_path = Path(tmpdir) / "sim.json"
            sim_path.write_text(
                json.dumps(
                    {
                        "generated_at": "2026-02-09T02:50:00Z",
                        "SIM_A": {"equity": 1, "pnl_pct": 0, "dd_pct": 0, "trades_total": 1},
                    }
                ),
                encoding="utf-8",
            )
            snapshot = build_sim_snapshot(sim_path)
            self.assertEqual(snapshot["status"], "stale")
            self.assertEqual(snapshot["generated_at"], "2026-02-09T02:50:00Z")

    @patch("workspace.discord_surface.snapshots._service_status", return_value="running")
    def test_build_ops_snapshot_marks_stale_sim_in_file_line(self, _service_status_mock):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            tasks = root / "tasks.json"
            projects = root / "projects.json"
            sim = root / "sim.json"
            tasks.write_text("{}", encoding="utf-8")
            projects.write_text("{}", encoding="utf-8")
            sim.write_text(json.dumps({"generated_at": "2026-02-09T02:50:00Z"}), encoding="utf-8")
            snapshot = build_ops_snapshot(
                tasks_path=tasks,
                projects_path=projects,
                sim_path=sim,
                health_services=["svc"],
                log_paths=[],
            )
            rendered = format_ops_message(snapshot)
            self.assertIn("sim_json:2026-02-09T02:50:00Z stale", rendered)

    def test_build_sim_snapshot_supports_dali_consensus_payload(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            sim_path = Path(tmpdir) / "dali_consensus.json"
            generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            sim_path.write_text(
                json.dumps(
                    {
                        "generated_at": generated_at,
                        "external_signal": {
                            "inputs": {
                                "macbook_sentiment": {"status": "ok"},
                                "fingpt_sentiment": {"status": "missing"},
                            }
                        },
                        "symbols": {
                            "BTCUSDT": {
                                "decision": {"action": "hold", "bias": 0.0501, "confidence": 0.8458, "risk_state": "normal"},
                                "agents": {"sentiment": {"score": 0.1764}},
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )
            snapshot = build_sim_snapshot(sim_path)
            self.assertEqual(snapshot["status"], "ok")
            self.assertEqual(snapshot["kind"], "consensus")
            rendered = format_sim_message(snapshot)
            self.assertIn("source=dali-feedback", rendered)
            self.assertIn("BTCUSDT action=hold", rendered)


if __name__ == "__main__":
    unittest.main()
