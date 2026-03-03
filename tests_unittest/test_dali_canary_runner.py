import io
import re
import unittest
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[1]

import sys

if str(REPO_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "scripts"))

import dali_canary_runner as canary  # noqa: E402


class TestDaliCanaryRunner(unittest.TestCase):
    def test_line_format_and_no_forbidden_fields(self):
        line = canary.format_line(
            status="DEGRADED",
            coder="DEGRADED",
            replay="NOACCESS",
            pairing="OK",
            ts="2026-02-23T00:45:00Z",
        )
        self.assertRegex(
            line,
            re.compile(
                r"^CANARY status=(OK|DEGRADED|FAIL) coder=(UP|DOWN|DEGRADED) replay=(WRITABLE|NOACCESS) pairing=(OK|UNHEALTHY) ts=[0-9TZ:\-]+$"
            ),
        )
        self.assertNotIn("prompt=", line)
        self.assertNotIn("text=", line)
        self.assertNotIn("body=", line)

    def test_exit_code_mapping(self):
        self.assertEqual(canary.exit_code_for_status("OK"), 0)
        self.assertEqual(canary.exit_code_for_status("DEGRADED"), 10)
        self.assertEqual(canary.exit_code_for_status("FAIL"), 20)

    def test_main_exit_code_with_mocked_checks(self):
        with patch.object(canary, "run_provider_diag", return_value={"ok": True, "coder": "UP", "markers": {}}), patch.object(
            canary, "replay_writable", return_value=("WRITABLE", None)
        ), patch.object(canary, "pairing_canary", return_value=("OK", None)), patch.object(
            canary, "now_iso", return_value="2026-02-23T00:50:00Z"
        ), patch.object(canary, "append_line", return_value=None), patch.object(
            canary, "append_envelope", return_value={"ok": True}
        ), patch("sys.stdout", new_callable=io.StringIO) as mock_out:
            rc = canary.main()
        self.assertEqual(rc, 0)
        self.assertIn("CANARY status=OK coder=UP replay=WRITABLE pairing=OK ts=2026-02-23T00:50:00Z", mock_out.getvalue())

    def test_main_degraded_when_coder_down(self):
        with patch.object(canary, "run_provider_diag", return_value={"ok": True, "coder": "DOWN", "markers": {}}), patch.object(
            canary, "replay_writable", return_value=("WRITABLE", None)
        ), patch.object(canary, "pairing_canary", return_value=("OK", None)), patch.object(
            canary, "now_iso", return_value="2026-02-23T00:50:00Z"
        ), patch.object(canary, "append_line", return_value=None), patch.object(
            canary, "append_envelope", return_value={"ok": True}
        ), patch("sys.stdout", new_callable=io.StringIO):
            rc = canary.main()
        self.assertEqual(rc, 10)

    def test_main_fail_when_pairing_unhealthy(self):
        with patch.object(canary, "run_provider_diag", return_value={"ok": True, "coder": "UP", "markers": {}}), patch.object(
            canary, "replay_writable", return_value=("WRITABLE", None)
        ), patch.object(canary, "pairing_canary", return_value=("UNHEALTHY", "x")), patch.object(
            canary, "now_iso", return_value="2026-02-23T00:50:00Z"
        ), patch.object(canary, "append_line", return_value=None), patch.object(
            canary, "append_envelope", return_value={"ok": True}
        ), patch("sys.stdout", new_callable=io.StringIO):
            rc = canary.main()
        self.assertEqual(rc, 20)


if __name__ == "__main__":
    unittest.main()
