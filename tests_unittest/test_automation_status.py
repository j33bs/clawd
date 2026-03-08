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

    def test_latest_run_uses_job_state_when_jsonl_missing(self):
        now_ms = int(time.time() * 1000)
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            runs_dir = root / "runs"
            jobs_file = root / "jobs.json"
            artifact = root / "latest.json"
            job_id = "job-state-fallback"

            self._write_json(
                jobs_file,
                {
                    "version": 1,
                    "jobs": [
                        {
                            "id": job_id,
                            "name": "Daily Morning Briefing",
                            "state": {
                                "lastRunAtMs": now_ms - 1000,
                                "lastStatus": "ok",
                                "nextRunAtMs": now_ms + 3600000,
                            },
                        }
                    ],
                },
            )

            proc = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "latest-run",
                    "--job-id",
                    job_id,
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
            self.assertEqual(report["status"], "ok")
            self.assertEqual(report.get("source"), "job-state")

    def test_latest_run_enforces_min_run_timestamp(self):
        now_ms = int(time.time() * 1000)
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            runs_dir = root / "runs"
            jobs_file = root / "jobs.json"
            artifact = root / "latest_min.json"
            job_id = "job-min-threshold"

            self._write_json(
                jobs_file,
                {
                    "version": 1,
                    "jobs": [
                        {
                            "id": job_id,
                            "name": "Daily Morning Briefing",
                            "state": {
                                "lastRunAtMs": now_ms - 120000,
                                "lastStatus": "ok",
                            },
                        }
                    ],
                },
            )

            proc = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "latest-run",
                    "--job-id",
                    job_id,
                    "--job-name",
                    "Daily Morning Briefing",
                    "--runs-dir",
                    str(runs_dir),
                    "--jobs-file",
                    str(jobs_file),
                    "--min-run-at-ms",
                    str(now_ms - 1000),
                    "--artifact",
                    str(artifact),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 1)
            report = json.loads(artifact.read_text(encoding="utf-8"))
            self.assertEqual(report["error"], "no-recent-run")


class TestPureFunctions(unittest.TestCase):
    """Unit tests for pure functions in automation_status — no subprocess needed."""

    def setUp(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("automation_status", SCRIPT)
        self.mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.mod)
        self._tmpdir = tempfile.TemporaryDirectory()
        self.tmpdir = Path(self._tmpdir.name)

    def tearDown(self):
        self._tmpdir.cleanup()

    # --- ms_to_iso ---

    def test_ms_to_iso_none_returns_none(self):
        self.assertIsNone(self.mod.ms_to_iso(None))

    def test_ms_to_iso_returns_string(self):
        result = self.mod.ms_to_iso(0)
        self.assertIsInstance(result, str)

    def test_ms_to_iso_known_epoch(self):
        result = self.mod.ms_to_iso(0)
        self.assertIn("1970", result)

    def test_ms_to_iso_ends_with_00(self):
        result = self.mod.ms_to_iso(1000 * 1000)
        self.assertIn("+00:00", result)

    # --- read_jsonl ---

    def test_read_jsonl_missing_returns_empty(self):
        result, invalid = self.mod.read_jsonl(self.tmpdir / "missing.jsonl")
        self.assertEqual(result, [])
        self.assertEqual(invalid, 0)

    def test_read_jsonl_valid_lines(self):
        p = self.tmpdir / "data.jsonl"
        p.write_text('{"a": 1}\n{"b": 2}\n', encoding="utf-8")
        result, invalid = self.mod.read_jsonl(p)
        self.assertEqual(len(result), 2)
        self.assertEqual(invalid, 0)

    def test_read_jsonl_invalid_lines_counted(self):
        p = self.tmpdir / "data.jsonl"
        p.write_text('{"a": 1}\nnot_json\n{"c": 3}\n', encoding="utf-8")
        result, invalid = self.mod.read_jsonl(p)
        self.assertEqual(len(result), 2)
        self.assertEqual(invalid, 1)

    def test_read_jsonl_skips_non_dict_lines(self):
        p = self.tmpdir / "data.jsonl"
        p.write_text('["list"]\n{"dict": true}\n', encoding="utf-8")
        result, invalid = self.mod.read_jsonl(p)
        self.assertEqual(len(result), 1)  # only dict lines

    def test_read_jsonl_blank_lines_ignored(self):
        p = self.tmpdir / "data.jsonl"
        p.write_text('{"a": 1}\n\n\n{"b": 2}\n', encoding="utf-8")
        result, invalid = self.mod.read_jsonl(p)
        self.assertEqual(len(result), 2)
        self.assertEqual(invalid, 0)

    # --- load_jobs_store ---

    def test_load_jobs_store_missing_returns_empty(self):
        result = self.mod.load_jobs_store(self.tmpdir / "missing.json")
        self.assertEqual(result, [])

    def test_load_jobs_store_extracts_jobs_list(self):
        p = self.tmpdir / "jobs.json"
        p.write_text('{"jobs": [{"id": "1", "name": "test"}]}', encoding="utf-8")
        result = self.mod.load_jobs_store(p)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["id"], "1")

    def test_load_jobs_store_filters_non_dicts(self):
        p = self.tmpdir / "jobs.json"
        p.write_text('{"jobs": [{"id": "1"}, "string", null, 42]}', encoding="utf-8")
        result = self.mod.load_jobs_store(p)
        self.assertEqual(len(result), 1)

    # --- find_job ---

    def test_find_job_by_id(self):
        jobs = [{"id": "abc", "name": "test"}, {"id": "xyz", "name": "other"}]
        result = self.mod.find_job(jobs, job_id="abc", job_name=None)
        self.assertEqual(result["id"], "abc")

    def test_find_job_by_name(self):
        jobs = [{"id": "abc", "name": "Test Job"}, {"id": "xyz", "name": "Other"}]
        result = self.mod.find_job(jobs, job_id=None, job_name="test job")
        self.assertEqual(result["id"], "abc")

    def test_find_job_name_case_insensitive(self):
        jobs = [{"id": "abc", "name": "Test Job"}]
        result = self.mod.find_job(jobs, job_id=None, job_name="TEST JOB")
        self.assertIsNotNone(result)

    def test_find_job_not_found_returns_none(self):
        jobs = [{"id": "abc", "name": "test"}]
        result = self.mod.find_job(jobs, job_id="zzz", job_name="nonexistent")
        self.assertIsNone(result)

    def test_find_job_empty_list_returns_none(self):
        result = self.mod.find_job([], job_id="abc", job_name=None)
        self.assertIsNone(result)

    def test_find_job_id_takes_priority_over_name(self):
        jobs = [{"id": "abc", "name": "by_id"}, {"id": "xyz", "name": "by_name"}]
        result = self.mod.find_job(jobs, job_id="abc", job_name="by_name")
        self.assertEqual(result["name"], "by_id")


if __name__ == "__main__":
    unittest.main()
