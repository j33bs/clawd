import unittest
from unittest import mock
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_PATH = REPO_ROOT / "workspace"
if str(WORKSPACE_PATH) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_PATH))

from cathedral.fishtank_renderer import FishTankRenderer


class TestCathedralRendererWindowClose(unittest.TestCase):
    def test_render_scene_ignores_window_close_request(self):
        renderer = FishTankRenderer.__new__(FishTankRenderer)
        renderer.gpu_mode = True
        renderer._window = object()
        renderer._ctx = mock.Mock()
        renderer.log = mock.Mock()
        renderer.require_gpu = True
        renderer.backend = "glfw-fullscreen"
        renderer._last_window_close_log_ts = 0.0
        renderer._ensure_nonzero_framebuffer = mock.Mock()
        renderer._ensure_post_buffers = mock.Mock()
        renderer._step_rd_field = mock.Mock()
        renderer._render_volume_to_scene = mock.Mock()
        renderer._render_particles_to_scene = mock.Mock()
        renderer._post_to_screen = mock.Mock()
        renderer._check_gl_error = mock.Mock()

        fake_glfw = mock.Mock()
        fake_glfw.window_should_close.return_value = True

        with mock.patch("cathedral.fishtank_renderer.glfw", fake_glfw), mock.patch(
            "cathedral.fishtank_renderer.time.monotonic",
            return_value=5.0,
        ):
            FishTankRenderer.render_scene(renderer)

        fake_glfw.set_window_should_close.assert_called_once_with(renderer._window, False)
        renderer.log.log.assert_called_once_with("render_window_close_ignored", backend="glfw-fullscreen")
        renderer._ensure_nonzero_framebuffer.assert_not_called()


if __name__ == "__main__":
    unittest.main()
