import unittest
from unittest import mock
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_PATH = REPO_ROOT / "workspace"
if str(WORKSPACE_PATH) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_PATH))

from cathedral.runtime import DaliCathedralRuntime
from cathedral.fishtank_renderer import FishTankRenderer


class TestCathedralIdlePythonRenderer(unittest.TestCase):
    def test_python_frontend_starts_headless_when_idle_gated(self):
        fake_renderer = mock.Mock()
        fake_renderer.set_runtime_context = mock.Mock()
        fake_renderer.headless = True
        fake_renderer.active_renderer_id = "renderer:test"

        with mock.patch.dict(
            "os.environ",
            {
                "DALI_FISHTANK_FRONTEND": "python",
                "DALI_FISHTANK_IDLE_ENABLE": "1",
            },
            clear=False,
        ), mock.patch(
            "cathedral.runtime.GPULease.acquire",
            return_value=True,
        ), mock.patch(
            "cathedral.runtime.GPULease.release",
            return_value=True,
        ), mock.patch.object(
            DaliCathedralRuntime,
            "_quiesce_inference_mode",
            return_value=None,
        ), mock.patch.object(
            DaliCathedralRuntime,
            "_unquiesce_inference_mode",
            return_value=None,
        ), mock.patch.object(
            DaliCathedralRuntime,
            "_warn_if_headless_without_consumer",
            return_value=None,
        ), mock.patch(
            "cathedral.runtime.FishTankRenderer",
            return_value=fake_renderer,
        ) as renderer_cls:
            runtime = DaliCathedralRuntime(
                headless=False,
                require_gpu=False,
                telegram_enabled=False,
            )

        self.assertEqual(runtime.frontend, "python")
        self.assertTrue(renderer_cls.call_args.kwargs["headless"])
        self.assertFalse(renderer_cls.call_args.kwargs["allow_visible_attach"])

    def test_runtime_context_rebuilds_backend_when_display_mode_changes(self):
        renderer = FishTankRenderer.__new__(FishTankRenderer)
        renderer.lease_mode = "exclusive"
        renderer.inference_quiesced = False
        renderer.idle_mode_enabled = True
        renderer.idle_trigger_source = "session"
        renderer.idle_triggered_at = ""
        renderer.display_mode_active = False
        renderer.idle_inhibit_enabled = True
        renderer.display_inhibitor_active = False
        renderer.inhibitor_backend = "none"
        renderer.headless = True
        renderer.allow_visible_attach = True
        renderer.log = mock.Mock()
        renderer._rebuild_gpu_backend = mock.Mock()

        FishTankRenderer.set_runtime_context(
            renderer,
            lease_mode="exclusive",
            inference_quiesced=True,
            idle_mode_enabled=True,
            display_mode_active=True,
        )

        renderer._rebuild_gpu_backend.assert_called_once_with(headless=False)

    def test_runtime_context_blocks_visible_attach_when_disabled(self):
        renderer = FishTankRenderer.__new__(FishTankRenderer)
        renderer.lease_mode = "exclusive"
        renderer.inference_quiesced = False
        renderer.idle_mode_enabled = True
        renderer.idle_trigger_source = "session"
        renderer.idle_triggered_at = ""
        renderer.display_mode_active = False
        renderer.idle_inhibit_enabled = True
        renderer.display_inhibitor_active = False
        renderer.inhibitor_backend = "none"
        renderer.headless = True
        renderer.allow_visible_attach = False
        renderer._visible_attach_blocked_logged = False
        renderer.backend = "egl-headless"
        renderer.log = mock.Mock()
        renderer._rebuild_gpu_backend = mock.Mock()

        FishTankRenderer.set_runtime_context(
            renderer,
            lease_mode="exclusive",
            inference_quiesced=True,
            idle_mode_enabled=True,
            display_mode_active=True,
        )

        renderer._rebuild_gpu_backend.assert_not_called()
        renderer.log.log.assert_called_once_with(
            "visible_attach_blocked",
            reason="python_visible_attach_disabled",
            backend="egl-headless",
        )

    def test_runtime_blocks_python_display_mode_when_visible_attach_disabled(self):
        runtime = DaliCathedralRuntime.__new__(DaliCathedralRuntime)
        runtime.frontend = "python"
        runtime.python_visible_attach_enabled = False
        runtime.display_mode_active = False
        runtime.display_mode_reason = ""
        runtime.idle_trigger_source = "session"
        runtime.idle_seconds = 30.0
        runtime.log = mock.Mock()
        runtime._python_visible_attach_block_log_ts = 0.0
        runtime._start_display_inhibitor = mock.Mock()
        runtime._start_frontend = mock.Mock()

        with mock.patch("cathedral.runtime.time.monotonic", return_value=10.0):
            DaliCathedralRuntime._enter_display_mode(runtime, reason="session_idle")

        self.assertFalse(runtime.display_mode_active)
        runtime._start_display_inhibitor.assert_not_called()
        runtime._start_frontend.assert_not_called()
        runtime.log.log.assert_called_once_with(
            "DISPLAY_MODE_BLOCKED",
            reason="session_idle",
            frontend="python",
            blocker="python_visible_attach_disabled",
        )


if __name__ == "__main__":
    unittest.main()
