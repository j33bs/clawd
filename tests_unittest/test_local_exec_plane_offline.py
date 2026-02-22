from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from workspace.local_exec.model_client import OpenAICompatClient, ModelClientError, reject_disallowed_tool_calls
from workspace.local_exec.queue import enqueue_job, ledger_path
from workspace.local_exec.subprocess_harness import SubprocessPolicyError, run_argv
from workspace.local_exec.worker import run_once


class LocalExecPlaneOfflineTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.repo_root = Path(self._tmp.name)
        (self.repo_root / "workspace" / "local_exec" / "state").mkdir(parents=True, exist_ok=True)
        (self.repo_root / "workspace" / "local_exec" / "evidence").mkdir(parents=True, exist_ok=True)

        subprocess.run(["git", "init"], cwd=self.repo_root, check=True, capture_output=True)
        (self.repo_root / "README.md").write_text("hello\n", encoding="utf-8")
        subprocess.run(["git", "add", "README.md"], cwd=self.repo_root, check=True, capture_output=True)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _job(self, *, job_id: str, job_type: str, payload: dict, allow_subprocess: bool = False) -> dict:
        return {
            "job_id": job_id,
            "job_type": job_type,
            "created_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "payload": payload,
            "budgets": {
                "max_wall_time_sec": 30,
                "max_tool_calls": 10,
                "max_output_bytes": 65536,
                "max_concurrency_slots": 1,
            },
            "tool_policy": {
                "allow_network": False,
                "allow_subprocess": allow_subprocess,
                "allowed_tools": [],
            },
        }

    def test_append_only_ledger_grows_and_worker_completes(self) -> None:
        input_path = self.repo_root / "workspace" / "local_exec" / "input.txt"
        input_path.write_text("line-a\nline-b\n", encoding="utf-8")

        job = self._job(
            job_id="job-appendonly01",
            job_type="doc_compactor_task",
            payload={
                "inputs": ["workspace/local_exec/input.txt"],
                "max_input_bytes": 1024,
                "max_output_bytes": 2048,
            },
        )
        enqueue_job(self.repo_root, job)
        before = ledger_path(self.repo_root).read_text(encoding="utf-8").splitlines()
        result = run_once(self.repo_root, worker_id="t1")
        after = ledger_path(self.repo_root).read_text(encoding="utf-8").splitlines()

        self.assertEqual(result["status"], "complete")
        self.assertGreater(len(after), len(before))
        self.assertIn('"event": "enqueue"', before[0])

    def test_kill_switch_prevents_claims(self) -> None:
        kill_switch = self.repo_root / "workspace" / "local_exec" / "state" / "KILL_SWITCH"
        kill_switch.write_text("1\n", encoding="utf-8")

        job = self._job(
            job_id="job-killswitch01",
            job_type="doc_compactor_task",
            payload={"inputs": ["README.md"], "max_input_bytes": 1024, "max_output_bytes": 2048},
        )
        enqueue_job(self.repo_root, job)
        result = run_once(self.repo_root, worker_id="t1")
        self.assertEqual(result["status"], "kill_switch")

    def test_budget_enforcement_max_tool_calls(self) -> None:
        job = self._job(
            job_id="job-budget001",
            job_type="test_runner_task",
            payload={
                "commands": [["python3", "-c", "print('ok')"]],
                "timeout_sec": 20,
            },
            allow_subprocess=True,
        )
        job["budgets"]["max_tool_calls"] = 0
        enqueue_job(self.repo_root, job)
        result = run_once(self.repo_root, worker_id="t1")
        self.assertEqual(result["status"], "failed")
        self.assertIn("max_tool_calls exceeded", result["error"])

    def test_subprocess_policy_blocks_shell_string(self) -> None:
        with self.assertRaises(SubprocessPolicyError):
            run_argv(["echo hello"], repo_root=self.repo_root, cwd=self.repo_root)

    def test_model_client_stub_returns_no_tool_calls(self) -> None:
        client = OpenAICompatClient(base_url="", model="stub-model")
        resp = client.chat(messages=[{"role": "user", "content": "hello"}])
        self.assertTrue(resp["stub"])
        self.assertEqual(resp["choices"][0]["message"]["tool_calls"], [])

    def test_disallowed_tool_call_rejected(self) -> None:
        tool_calls = [{"function": {"name": "repo.delete_all"}}]
        with self.assertRaises(ModelClientError):
            reject_disallowed_tool_calls(tool_calls, allowed_tools={"repo.search"})

    def test_test_runner_requires_subprocess_permission(self) -> None:
        job = self._job(
            job_id="job-subprocdeny",
            job_type="test_runner_task",
            payload={"commands": [["python3", "-c", "print('no')"]], "timeout_sec": 20},
            allow_subprocess=False,
        )
        enqueue_job(self.repo_root, job)
        result = run_once(self.repo_root, worker_id="t1")
        self.assertEqual(result["status"], "failed")
        self.assertIn("subprocess_not_allowed", result["error"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
