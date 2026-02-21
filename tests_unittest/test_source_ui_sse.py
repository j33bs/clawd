import http.client
import importlib.util
import threading
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
APP_PATH = REPO_ROOT / "workspace" / "source-ui" / "app.py"
SPEC = importlib.util.spec_from_file_location("source_ui_app", APP_PATH)
source_ui_app = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(source_ui_app)


class TestSourceUiSse(unittest.TestCase):
    def test_events_endpoint_emits_ticks(self):
        source_ui_app.SourceUIHandler._state = source_ui_app.State()
        source_ui_app.SourceUIHandler._config = source_ui_app.Config(
            static_dir=str(REPO_ROOT / "workspace" / "source-ui" / "static")
        )

        server = source_ui_app.ThreadedHTTPServer(("127.0.0.1", 0), source_ui_app.SourceUIHandler)
        port = server.server_address[1]
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()

        try:
            conn = http.client.HTTPConnection("127.0.0.1", port, timeout=6)
            conn.request("GET", "/events")
            resp = conn.getresponse()
            self.assertEqual(resp.status, 200)
            chunk = resp.read(512).decode("utf-8", errors="ignore")
            self.assertIn("event:", chunk)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)


if __name__ == "__main__":
    unittest.main()
