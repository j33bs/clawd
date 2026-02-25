from __future__ import annotations

import contextlib
import importlib.util
import io
import os
import unittest
from pathlib import Path
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[1]
PREFLIGHT_PATH = REPO_ROOT / "workspace" / "scripts" / "preflight_check.py"


def _load_preflight_module():
    spec = importlib.util.spec_from_file_location("preflight_check_requests_gate", PREFLIGHT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestPreflightRequestsGate(unittest.TestCase):
    def setUp(self) -> None:
        self.preflight = _load_preflight_module()

    def _run_main(self, *, network_mode: bool) -> tuple[int, str]:
        env_updates = {}
        if network_mode:
            env_updates["OPENCLAW_PREFLIGHT_NETWORK"] = "1"
        else:
            env_updates["OPENCLAW_PREFLIGHT_NETWORK"] = None

        stdout = io.StringIO()
        with mock.patch.dict(os.environ, {}, clear=False):
            if env_updates["OPENCLAW_PREFLIGHT_NETWORK"] is None:
                os.environ.pop("OPENCLAW_PREFLIGHT_NETWORK", None)
            else:
                os.environ["OPENCLAW_PREFLIGHT_NETWORK"] = "1"

            with mock.patch.object(self.preflight, "REQUESTS_OK", False), \
                mock.patch.object(self.preflight, "_auto_ingest_known_system2_strays", return_value=None), \
                mock.patch.object(self.preflight, "_auto_ingest_known_gov_root_strays", return_value=None), \
                mock.patch.object(self.preflight, "_auto_ingest_allowlisted_teammate_untracked", return_value=None), \
                mock.patch.object(self.preflight, "check_plugins_allowlist", return_value=None), \
                mock.patch.object(self.preflight, "check_policy", return_value={}), \
                mock.patch.object(self.preflight, "check_router", return_value=None), \
                mock.patch.object(self.preflight, "check_node_identity", return_value=None), \
                mock.patch.object(self.preflight, "check_telegram", return_value=None), \
                contextlib.redirect_stdout(stdout):
                try:
                    self.preflight.main()
                    code = 0
                except SystemExit as exc:
                    code = int(exc.code) if isinstance(exc.code, int) else 1
        return code, stdout.getvalue()

    def test_default_mode_missing_requests_is_warning_and_success(self) -> None:
        code, output = self._run_main(network_mode=False)
        self.assertEqual(code, 0)
        self.assertIn("WARNINGS:", output)
        self.assertIn("Python requests library missing", output)
        self.assertIn("Install requests: `python3 -m pip install requests`", output)
        self.assertIn("ok", output)

    def test_network_mode_missing_requests_is_failure(self) -> None:
        code, output = self._run_main(network_mode=True)
        self.assertEqual(code, 1)
        self.assertIn("FAILURES:", output)
        self.assertIn("Python requests library missing", output)
        self.assertIn("Install requests: `python3 -m pip install requests`", output)


if __name__ == "__main__":
    unittest.main()
