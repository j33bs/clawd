import json
import os
import stat
import subprocess
import sys
import tempfile
import textwrap
import time
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "workspace" / "scripts"))

import ensure_cron_jobs  # noqa: E402


class FakeRunner:
    def __init__(self):
        self.jobs = []
        self.calls = []
        self.next_id = 1

    def _json(self):
        return {"jobs": [self._to_raw(job) for job in self.jobs]}

    @staticmethod
    def _to_raw(job):
        payload = {"kind": job["payload_kind"]}
        if payload["kind"] == "systemEvent":
            payload["text"] = job["command"]
        else:
            payload["message"] = job["command"]
        return {
            "id": job["id"],
            "name": job["name"],
            "enabled": job.get("enabled", True),
            "sessionTarget": job["sessionTarget"],
            "wakeMode": job["wakeMode"],
            "schedule": {"expr": job["expr"], "tz": job["tz"]},
            "payload": payload,
        }

    def _parse_flags(self, args):
        data = {}
        i = 0
        while i < len(args):
            token = args[i]
            if not token.startswith("--"):
                i += 1
                continue
            key = token[2:]
            if key == "no-deliver":
                data[key] = True
                i += 1
                continue
            data[key] = args[i + 1]
            i += 2
        return data

    def __call__(self, args, _openclaw_bin):
        self.calls.append(list(args))
        if args[:4] == ["cron", "list", "--all", "--json"]:
            return self._json()
        if args[:2] == ["cron", "add"]:
            flags = self._parse_flags(args[2:])
            payload_kind = "systemEvent" if "system-event" in flags else "agentTurn"
            command = flags.get("system-event") or flags.get("message") or ""
            job = {
                "id": f"job-{self.next_id}",
                "name": flags["name"],
                "expr": flags["cron"],
                "tz": flags["tz"],
                "sessionTarget": flags["session"],
                "wakeMode": flags["wake"],
                "payload_kind": payload_kind,
                "command": command,
                "enabled": True,
            }
            self.next_id += 1
            self.jobs.append(job)
            return {"id": job["id"]}
        if args[:2] == ["cron", "edit"]:
            job_id = args[2]
            flags = self._parse_flags(args[3:])
            for job in self.jobs:
                if job["id"] != job_id:
                    continue
                job["name"] = flags.get("name", job["name"])
                job["expr"] = flags.get("cron", job["expr"])
                job["tz"] = flags.get("tz", job["tz"])
                job["sessionTarget"] = flags.get("session", job["sessionTarget"])
                job["wakeMode"] = flags.get("wake", job["wakeMode"])
                if "system-event" in flags:
                    job["payload_kind"] = "systemEvent"
                    job["command"] = flags["system-event"]
                if "message" in flags:
                    job["payload_kind"] = "agentTurn"
                    job["command"] = flags["message"]
                job["enabled"] = True
                break
            return {"id": job_id}
        raise AssertionError(f"Unexpected command: {args}")


class TestEnsureCronJobs(unittest.TestCase):
    def test_load_templates_and_heartbeat_dependency(self):
        templates = ensure_cron_jobs.load_templates(
            REPO_ROOT / "workspace" / "automation" / "cron_jobs.json"
        )
        self.assertEqual(len(templates), 2)
        names = {item["name"] for item in templates}
        self.assertIn("Daily Morning Briefing", names)
        self.assertIn("HiveMind Ingest", names)
        self.assertTrue(ensure_cron_jobs.template_requires_heartbeat(templates))

    def test_ensure_jobs_create_then_unchanged_then_update(self):
        templates = ensure_cron_jobs.load_templates(
            REPO_ROOT / "workspace" / "automation" / "cron_jobs.json"
        )
        runner = FakeRunner()
        created = ensure_cron_jobs.ensure_jobs(
            templates,
            apply=True,
            runner=runner,
            openclaw_bin="openclaw",
        )
        self.assertEqual([a["operation"] for a in created["actions"]], ["create", "create"])

        unchanged = ensure_cron_jobs.ensure_jobs(
            templates,
            apply=True,
            runner=runner,
            openclaw_bin="openclaw",
        )
        self.assertEqual([a["operation"] for a in unchanged["actions"]], ["unchanged", "unchanged"])

        mutated_templates = [dict(item) for item in templates]
        mutated_templates[1]["command"] = "Run HiveMind ingest pipelines (updated)"
        updated = ensure_cron_jobs.ensure_jobs(
            mutated_templates,
            apply=True,
            runner=runner,
            openclaw_bin="openclaw",
        )
        self.assertEqual(updated["actions"][0]["operation"], "unchanged")
        self.assertEqual(updated["actions"][1]["operation"], "update")


class TestRunJobNowEnsure(unittest.TestCase):
    def test_run_job_now_ensures_templates_and_records_snapshot(self):
        with tempfile.TemporaryDirectory() as td:
            temp_root = Path(td)
            home = temp_root / "home"
            store = home / ".openclaw" / "cron" / "jobs.json"
            runs_dir = home / ".openclaw" / "cron" / "runs"
            cadence_file = home / ".openclaw" / "heartbeat_every.txt"
            store.parent.mkdir(parents=True, exist_ok=True)
            runs_dir.mkdir(parents=True, exist_ok=True)
            store.write_text(json.dumps({"version": 1, "jobs": []}), encoding="utf-8")
            cadence_file.write_text("0m\n", encoding="utf-8")

            fake_openclaw = temp_root / "fake_openclaw.py"
            fake_openclaw.write_text(
                textwrap.dedent(
                    """\
                    #!/usr/bin/env python3
                    import json
                    import os
                    import sys
                    import time
                    from pathlib import Path

                    home = Path.home()
                    store = home / ".openclaw" / "cron" / "jobs.json"
                    runs = home / ".openclaw" / "cron" / "runs"
                    cadence_file = home / ".openclaw" / "heartbeat_every.txt"
                    runs.mkdir(parents=True, exist_ok=True)
                    if not store.exists():
                        store.parent.mkdir(parents=True, exist_ok=True)
                        store.write_text(json.dumps({"version": 1, "jobs": []}), encoding="utf-8")
                    if not cadence_file.exists():
                        cadence_file.write_text("0m\\n", encoding="utf-8")

                    args = sys.argv[1:]
                    data = json.loads(store.read_text(encoding="utf-8"))
                    jobs = data.get("jobs", [])

                    def save():
                        store.write_text(json.dumps(data, indent=2), encoding="utf-8")

                    def parse_flags(items):
                        out = {}
                        i = 0
                        while i < len(items):
                            token = items[i]
                            if token == "--no-deliver":
                                out["no-deliver"] = True
                                i += 1
                                continue
                            if token.startswith("--"):
                                out[token[2:]] = items[i + 1]
                                i += 2
                                continue
                            i += 1
                        return out

                    if args[:3] == ["config", "get", "agents.defaults.heartbeat.every"]:
                        sys.stdout.write(cadence_file.read_text(encoding="utf-8").strip() + "\\n")
                        raise SystemExit(0)
                    if args[:3] == ["config", "set", "agents.defaults.heartbeat.every"]:
                        cadence_file.write_text(args[3] + "\\n", encoding="utf-8")
                        sys.stdout.write("ok\\n")
                        raise SystemExit(0)
                    if args[:4] == ["cron", "list", "--all", "--json"]:
                        sys.stdout.write(json.dumps({"jobs": jobs}))
                        raise SystemExit(0)
                    if args[:2] == ["cron", "add"]:
                        flags = parse_flags(args[2:])
                        new_id = f"job-{len(jobs)+1}"
                        payload = {"kind": "systemEvent", "text": flags.get("system-event", "")}
                        if "message" in flags:
                            payload = {"kind": "agentTurn", "message": flags.get("message", "")}
                        jobs.append(
                            {
                                "id": new_id,
                                "name": flags.get("name"),
                                "enabled": True,
                                "schedule": {"kind": "cron", "expr": flags.get("cron"), "tz": flags.get("tz")},
                                "sessionTarget": flags.get("session"),
                                "wakeMode": flags.get("wake"),
                                "payload": payload,
                                "state": {},
                            }
                        )
                        save()
                        sys.stdout.write(json.dumps({"id": new_id}))
                        raise SystemExit(0)
                    if args[:2] == ["cron", "edit"]:
                        job_id = args[2]
                        flags = parse_flags(args[3:])
                        for job in jobs:
                            if job.get("id") != job_id:
                                continue
                            job["name"] = flags.get("name", job.get("name"))
                            job["schedule"]["expr"] = flags.get("cron", job["schedule"].get("expr"))
                            job["schedule"]["tz"] = flags.get("tz", job["schedule"].get("tz"))
                            job["sessionTarget"] = flags.get("session", job.get("sessionTarget"))
                            job["wakeMode"] = flags.get("wake", job.get("wakeMode"))
                            if "system-event" in flags:
                                job["payload"] = {"kind": "systemEvent", "text": flags.get("system-event", "")}
                            if "message" in flags:
                                job["payload"] = {"kind": "agentTurn", "message": flags.get("message", "")}
                            job["enabled"] = True
                        save()
                        sys.stdout.write(json.dumps({"id": job_id}))
                        raise SystemExit(0)
                    if args[:2] == ["cron", "run"]:
                        job_id = args[2]
                        now_ms = int(time.time() * 1000)
                        selected = None
                        for job in jobs:
                            if job.get("id") == job_id:
                                selected = job
                                break
                        if selected is None:
                            sys.stderr.write("missing job\\n")
                            raise SystemExit(1)
                        run_entry = {
                            "ts": now_ms,
                            "jobId": job_id,
                            "action": "finished",
                            "status": "ok",
                            "summary": selected.get("name", ""),
                            "runAtMs": now_ms,
                            "durationMs": 1,
                            "nextRunAtMs": now_ms + 86400000,
                        }
                        run_file = runs / f"{job_id}.jsonl"
                        with run_file.open("a", encoding="utf-8") as handle:
                            handle.write(json.dumps(run_entry) + "\\n")
                        selected.setdefault("state", {})
                        selected["state"]["lastRunAtMs"] = now_ms
                        selected["state"]["lastStatus"] = "ok"
                        save()
                        sys.stdout.write(json.dumps({"ok": True, "ran": True}))
                        raise SystemExit(0)

                    sys.stderr.write("unsupported command\\n")
                    raise SystemExit(1)
                    """
                ),
                encoding="utf-8",
            )
            fake_openclaw.chmod(stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)

            env = os.environ.copy()
            env["HOME"] = str(home)
            env["OPENCLAW_BIN"] = str(fake_openclaw)
            env["OPENCLAW_REPORT_DIR"] = str(temp_root / "reports" / "automation")
            env["OPENCLAW_CRON_STORE_FILE"] = str(store)

            run = subprocess.run(
                ["bash", str(REPO_ROOT / "scripts" / "run_job_now.sh"), "briefing"],
                cwd=str(REPO_ROOT),
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(run.returncode, 0, run.stderr + run.stdout)

            saved = json.loads(store.read_text(encoding="utf-8"))
            names = [job.get("name") for job in saved.get("jobs", [])]
            self.assertEqual(names.count("Daily Morning Briefing"), 1)
            self.assertEqual(names.count("HiveMind Ingest"), 1)

            snapshot = json.loads(
                (temp_root / "reports" / "automation" / "heartbeat_config_snapshot.json").read_text(encoding="utf-8")
            )
            self.assertEqual(snapshot["before_value"], "0m")
            self.assertEqual(snapshot["after_value"], "30m")
            self.assertTrue(snapshot["mutated"])


if __name__ == "__main__":
    unittest.main()
