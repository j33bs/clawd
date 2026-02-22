import json
import os
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
GEN_SCRIPT = REPO_ROOT / "workspace" / "scripts" / "gen_build_stamp.sh"
WRAPPER_SCRIPT = REPO_ROOT / "workspace" / "scripts" / "openclaw_build_wrapper.sh"


class TestRuntimeBuildStamp(unittest.TestCase):
    def test_gen_build_stamp_emits_expected_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            stamp_path = Path(tmp) / "version_build.json"
            env = os.environ.copy()
            env["OPENCLAW_BUILD_SHA"] = "abc123def456"
            env["OPENCLAW_BUILD_TIME_UTC"] = "2026-02-22T05:00:00Z"
            env["OPENCLAW_BUILD_PACKAGE_VERSION"] = "2026.2.19-2"
            env["OPENCLAW_BUILD_STAMP_PATH"] = str(stamp_path)

            subprocess.run(["bash", str(GEN_SCRIPT)], check=True, cwd=REPO_ROOT, env=env)

            payload = json.loads(stamp_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["build_sha"], "abc123def456")
            self.assertEqual(payload["build_time_utc"], "2026-02-22T05:00:00Z")
            self.assertEqual(payload["package_version"], "2026.2.19-2")

    def test_wrapper_version_includes_build_sha(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            real_bin = tmp_path / "openclaw.real"
            stamp_path = tmp_path / "version_build.json"

            real_bin.write_text(
                "#!/usr/bin/env bash\n"
                "if [[ \"${1-}\" == \"--version\" || \"${1-}\" == \"version\" ]]; then\n"
                "  echo \"2026.2.19-2\"\n"
                "  exit 0\n"
                "fi\n"
                "echo \"real:$*\"\n",
                encoding="utf-8",
            )
            real_bin.chmod(real_bin.stat().st_mode | stat.S_IEXEC)
            stamp_path.write_text(
                json.dumps(
                    {
                        "build_sha": "feedface1234",
                        "build_time_utc": "2026-02-22T05:01:00Z",
                        "package_version": "2026.2.19-2",
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            env = os.environ.copy()
            env["OPENCLAW_REAL_BIN"] = str(real_bin)
            env["OPENCLAW_BUILD_STAMP_FILE"] = str(stamp_path)
            out = subprocess.check_output(
                ["bash", str(WRAPPER_SCRIPT), "--version"],
                cwd=REPO_ROOT,
                env=env,
                text=True,
            ).strip()
            self.assertIn("build_sha=feedface1234", out)
            self.assertIn("build_time=2026-02-22T05:01:00Z", out)
            self.assertIn("2026.2.19-2", out)

    def test_wrapper_gateway_emits_build_banner(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            real_bin = tmp_path / "openclaw.real"
            stamp_path = tmp_path / "version_build.json"

            real_bin.write_text(
                "#!/usr/bin/env bash\n"
                "echo \"gateway-real:$*\"\n",
                encoding="utf-8",
            )
            real_bin.chmod(real_bin.stat().st_mode | stat.S_IEXEC)
            stamp_path.write_text(
                json.dumps(
                    {
                        "build_sha": "deadbeef9876",
                        "build_time_utc": "2026-02-22T05:02:00Z",
                        "package_version": "2026.2.19-2",
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            env = os.environ.copy()
            env["OPENCLAW_REAL_BIN"] = str(real_bin)
            env["OPENCLAW_BUILD_STAMP_FILE"] = str(stamp_path)
            out = subprocess.check_output(
                ["bash", str(WRAPPER_SCRIPT), "gateway", "--port", "18789"],
                cwd=REPO_ROOT,
                env=env,
                text=True,
            )
            self.assertIn("openclaw_gateway build_sha=deadbeef9876", out)
            self.assertIn("version=2026.2.19-2", out)
            self.assertIn("gateway-real:gateway --port 18789", out)


if __name__ == "__main__":
    unittest.main()
