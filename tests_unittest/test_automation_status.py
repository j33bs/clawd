import json
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "workspace" / "scripts" / "automation_status.py"


class TestAutomationStatus(unittest.TestCase):
    def _write_json(self, path: Path, payload: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    def _write_jsonl(self, path: Path, entries: list[dict]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as handle:
            for entry in entries:
                handle.write(json.dumps(entry) + "\n")

    def test_cron_health_passes_for_recent_success(self):
        now_ms = int(time.time() * 1000)
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            runs_dir = root / "runs"
            jobs_file = root / "jobs.json"
            artifact = root / "briefing_health.json"
            job_id = "job-1"

            self._write_json(
                jobs_file,
                {
                    "version": 1,
                    "jobs": [
                        {
                            "id": job_id,
                            "name": "Daily Morning Briefing",
                            "state": {"nextRunAtMs": now_ms + 1000},
                        }
                    ],
                },
            )
            self._write_jsonl(
                runs_dir / f"{job_id}.jsonl",
                [
                    {
                        "jobId": job_id,
                        "status": "ok",
                        "runAtMs": now_ms - (2 * 60 * 60 * 1000),
                        "nextRunAtMs": now_ms + (22 * 60 * 60 * 1000),
                    }
                ],
            )

            proc = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "cron-health",
                    "--job-name",
                    "Daily Morning Briefing",
                    "--runs-dir",
                    str(runs_dir),
                    "--jobs-file",
                    str(jobs_file),
                    "--artifact",
                    str(artifact),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            report = json.loads(artifact.read_text(encoding="utf-8"))
            self.assertTrue(report["pass"])
            self.assertEqual(report["last_status"], "ok")

    def test_cron_health_fails_for_disabled_skip(self):
        now_ms = int(time.time() * 1000)
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            runs_dir = root / "runs"
            jobs_file = root / "jobs.json"
            artifact = root / "hivemind_health.json"
            job_id = "job-2"

            self._write_json(
                jobs_file,
                {
                    "version": 1,
                    "jobs": [
                        {
                            "id": job_id,
                            "name": "HiveMind Ingest",
                            "state": {"nextRunAtMs": now_ms + 1000},
                        }
                    ],
                },
            )
            self._write_jsonl(
                runs_dir / f"{job_id}.jsonl",
                [
                    {
                        "jobId": job_id,
                        "status": "skipped",
                        "error": "disabled",
                        "runAtMs": now_ms - (30 * 60 * 60 * 1000),
                        "nextRunAtMs": now_ms + (18 * 60 * 60 * 1000),
                    }
                ],
            )

            proc = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "cron-health",
                    "--job-name",
                    "HiveMind Ingest",
                    "--runs-dir",
                    str(runs_dir),
                    "--jobs-file",
                    str(jobs_file),
                    "--artifact",
                    str(artifact),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 1)
            report = json.loads(artifact.read_text(encoding="utf-8"))
            self.assertFalse(report["pass"])
            self.assertEqual(report["last_error"], "disabled")

    def test_memory_size_guard_flags_large_memory_file(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            memory_file = root / "MEMORY.md"
            artifact = root / "memory_size_guard.json"
            memory_file.write_text("\n".join(f"line {i}" for i in range(200)) + "\n", encoding="utf-8")

            proc = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "memory-size-guard",
                    "--memory-file",
                    str(memory_file),
                    "--threshold-lines",
                    "180",
                    "--artifact",
                    str(artifact),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            report = json.loads(artifact.read_text(encoding="utf-8"))
            self.assertTrue(report["needs_prune"])
            self.assertEqual(report["line_count"], 200)


if __name__ == "__main__":
    unittest.main()
