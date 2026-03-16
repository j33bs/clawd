import io
import json
import unittest
from unittest import mock
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCE_UI_ROOT = REPO_ROOT / "workspace" / "source-ui"
if str(SOURCE_UI_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_UI_ROOT))

import app as source_ui_app  # noqa: E402


class SourceUIWorldBetterEndpointTests(unittest.TestCase):
    def test_handle_api_returns_world_better_payload(self):
        handler = object.__new__(source_ui_app.SourceUIHandler)
        handler._config = source_ui_app.Config(static_dir=str(SOURCE_UI_ROOT / "static"))
        handler._state = source_ui_app.State()
        handler.wfile = io.BytesIO()
        handler.send_response = mock.Mock()
        handler.send_header = mock.Mock()
        handler.end_headers = mock.Mock()
        with mock.patch.object(
            source_ui_app,
            "portfolio_payload",
            return_value={"world_better": {"status": "active", "summary": "ready"}},
        ):
            handler.handle_api(source_ui_app.urlparse("/api/world-better"))
        body = json.loads(handler.wfile.getvalue().decode("utf-8"))
        self.assertEqual(body["status"], "active")
        self.assertEqual(body["summary"], "ready")


if __name__ == "__main__":
    unittest.main()
