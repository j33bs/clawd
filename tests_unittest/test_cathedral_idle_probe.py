import types
import unittest
from unittest import mock
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_PATH = REPO_ROOT / "workspace"
if str(WORKSPACE_PATH) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_PATH))

from cathedral.runtime import DaliCathedralRuntime


class TestCathedralIdleProbe(unittest.TestCase):
    def _make_runtime(self) -> DaliCathedralRuntime:
        runtime = DaliCathedralRuntime.__new__(DaliCathedralRuntime)
        runtime.log = mock.Mock()
        runtime.idle_trigger_source = "session"
        runtime._last_idle_probe_ts = 0.0
        runtime._last_idle_probe_idle_s = None
        runtime._last_idle_probe_ok = False
        runtime._last_idle_probe_error_log_ts = 0.0
        runtime.session_idle_supported = False
        runtime.session_idle_seconds = 0.0
        runtime.idle_supported = False
        runtime.idle_last_error = ""
        runtime.idle_source = "session"
        runtime._idle_session_id_hint = ""
        runtime._idle_session_id_hint_ts = 0.0
        return runtime

    def test_loginctl_probe_marks_session_idle_supported(self):
        runtime = self._make_runtime()
        loginctl_ok = types.SimpleNamespace(
            returncode=0,
            stdout="IdleHint=no\nIdleSinceHintMonotonic=225072960258\n",
            stderr="",
        )

        with mock.patch("cathedral.runtime.subprocess.run", return_value=loginctl_ok):
            ok, idle_s = DaliCathedralRuntime._probe_session_idle_seconds(runtime)

        self.assertTrue(ok)
        self.assertEqual(idle_s, 0.0)
        self.assertTrue(runtime.session_idle_supported)
        self.assertEqual(runtime.session_idle_seconds, 0.0)
        self.assertTrue(runtime.idle_supported)
        self.assertEqual(runtime.idle_source, "session")
        self.assertEqual(runtime.idle_last_error, "")

    def test_loginctl_failure_falls_back_to_gnome_idle_monitor(self):
        runtime = self._make_runtime()
        loginctl_fail = types.SimpleNamespace(returncode=1, stdout="", stderr="no session")
        gnome_ok = types.SimpleNamespace(returncode=0, stdout="(uint64 171536,)\n", stderr="")

        with mock.patch.dict("cathedral.runtime.os.environ", {"XDG_SESSION_ID": "2"}, clear=True):
            with mock.patch("cathedral.runtime.subprocess.run", side_effect=[loginctl_fail, gnome_ok]):
                ok, idle_s = DaliCathedralRuntime._probe_session_idle_seconds(runtime)

        self.assertTrue(ok)
        self.assertAlmostEqual(idle_s or 0.0, 171.536, places=3)
        self.assertFalse(runtime.session_idle_supported)
        self.assertEqual(runtime.session_idle_seconds, 0.0)
        self.assertTrue(runtime.idle_supported)
        self.assertEqual(runtime.idle_source, "gnome")
        self.assertEqual(runtime.idle_last_error, "")

    def test_session_resolution_prefers_local_graphical_session(self):
        runtime = self._make_runtime()
        list_sessions = types.SimpleNamespace(
            returncode=0,
            stdout="1005 1000 jeebs - - closing no -\n1023 1000 jeebs - pts/3 active yes 37min ago\n2 1000 jeebs seat0 tty2 active no -\n",
            stderr="",
        )
        show_remote_tty = types.SimpleNamespace(
            returncode=0,
            stdout="Remote=yes\nType=tty\nActive=yes\nState=active\n",
            stderr="",
        )
        show_closing = types.SimpleNamespace(
            returncode=0,
            stdout="Remote=no\nType=unspecified\nActive=no\nState=closing\n",
            stderr="",
        )
        show_graphical = types.SimpleNamespace(
            returncode=0,
            stdout="Remote=no\nType=x11\nActive=yes\nState=active\n",
            stderr="",
        )

        with mock.patch.dict("cathedral.runtime.os.environ", {}, clear=True):
            with mock.patch(
                "cathedral.runtime.subprocess.run",
                side_effect=[list_sessions, show_closing, show_remote_tty, show_graphical],
            ):
                session_id = DaliCathedralRuntime._resolve_idle_session_id(runtime)

        self.assertEqual(session_id, "2")
        self.assertEqual(runtime._idle_session_id_hint, "2")

    def test_probe_idle_seconds_uses_gnome_when_requested(self):
        runtime = self._make_runtime()
        runtime.idle_trigger_source = "gnome"

        with mock.patch.object(runtime, "_probe_gnome_idle_seconds", return_value=(True, 42.5)):
            ok, idle_s = DaliCathedralRuntime._probe_idle_seconds(runtime)

        self.assertTrue(ok)
        self.assertEqual(idle_s, 42.5)
        self.assertFalse(runtime.session_idle_supported)
        self.assertEqual(runtime.idle_source, "gnome")


if __name__ == "__main__":
    unittest.main()
