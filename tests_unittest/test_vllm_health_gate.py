import os
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
GATE_SCRIPT = REPO_ROOT / "workspace" / "scripts" / "vllm_health_gate.sh"


def make_executable_script(path: Path, body: str) -> None:
    path.write_text("#!/usr/bin/env bash\nset -euo pipefail\n" + body + "\n", encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR)


class VllmHealthGateTests(unittest.TestCase):
    def _run_gate(self, *, ss_output: str, ss_exit: int, curl_exit: int, mode: str) -> subprocess.CompletedProcess:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            ss_script = td_path / "fake_ss.sh"
            curl_script = td_path / "fake_curl.sh"
            make_executable_script(
                ss_script,
                f"cat <<'EOF'\n{ss_output}\nEOF\nexit {ss_exit}",
            )
            make_executable_script(curl_script, f"exit {curl_exit}")

            env = os.environ.copy()
            env["OPENCLAW_GATE_SS_CMD"] = str(ss_script)
            env["OPENCLAW_GATE_CURL_CMD"] = str(curl_script)
            proc = subprocess.run(
                ["bash", str(GATE_SCRIPT), mode],
                cwd=str(REPO_ROOT),
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            return proc

    def test_unknown_holder_fails_preflight_with_hint(self):
        proc = self._run_gate(
            ss_output=(
                "State Recv-Q Send-Q Local Address:Port Peer Address:Port Process\n"
                "LISTEN 0 128 0.0.0.0:8001 0.0.0.0:* users:((\"python3\",pid=999999,fd=3))"
            ),
            ss_exit=0,
            curl_exit=0,
            mode="--preflight",
        )
        combined = proc.stdout + proc.stderr
        self.assertEqual(proc.returncode, 42)
        self.assertIn("port_owner=unknown", combined)
        self.assertIn("HINT: vLLM blocked", combined)

    def test_vllm_like_holder_with_health_ok_passes_preflight(self):
        sleeper = subprocess.Popen(["bash", "-lc", "exec -a vllm-mock sleep 30"])
        try:
            proc = self._run_gate(
                ss_output=(
                    "State Recv-Q Send-Q Local Address:Port Peer Address:Port Process\n"
                    f"LISTEN 0 128 0.0.0.0:8001 0.0.0.0:* users:((\"python3\",pid={sleeper.pid},fd=3))"
                ),
                ss_exit=0,
                curl_exit=0,
                mode="--preflight",
            )
        finally:
            sleeper.terminate()
            sleeper.wait(timeout=5)
        combined = proc.stdout + proc.stderr
        self.assertEqual(proc.returncode, 0)
        self.assertIn("port_owner=vllm_like", combined)
        self.assertIn("health=ok", combined)

    def test_free_port_with_health_down_fails_preflight(self):
        proc = self._run_gate(
            ss_output="State Recv-Q Send-Q Local Address:Port Peer Address:Port Process",
            ss_exit=0,
            curl_exit=1,
            mode="--preflight",
        )
        combined = proc.stdout + proc.stderr
        self.assertEqual(proc.returncode, 42)
        self.assertIn("port_owner=free", combined)
        self.assertIn("health=down", combined)

    def test_nightly_mode_warns_but_returns_zero(self):
        proc = self._run_gate(
            ss_output=(
                "State Recv-Q Send-Q Local Address:Port Peer Address:Port Process\n"
                "LISTEN 0 128 0.0.0.0:8001 0.0.0.0:* users:((\"python3\",pid=999999,fd=3))"
            ),
            ss_exit=0,
            curl_exit=1,
            mode="--nightly",
        )
        combined = proc.stdout + proc.stderr
        self.assertEqual(proc.returncode, 0)
        self.assertIn("VLLM_GATE_WARN mode=nightly", combined)


if __name__ == "__main__":
    unittest.main()
