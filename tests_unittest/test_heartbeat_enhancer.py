import importlib.util
import os
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "workspace" / "heartbeat_enhancer.py"


def load_module():
    spec = importlib.util.spec_from_file_location("heartbeat_enhancer", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class HeartbeatEnhancerTests(unittest.TestCase):
    def setUp(self):
        self.mod = load_module()

    def test_enhanced_heartbeat_reports_memory_health_when_tacti_core_unavailable(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "memory").mkdir(parents=True, exist_ok=True)
            (root / "workspace" / "state_runtime" / "memory").mkdir(parents=True, exist_ok=True)
            (root / "MEMORY.md").write_text(
                "# MEMORY.md - Long-Term Context\n\n## Daily Distillations\n\n## Weekly Distillations\n",
                encoding="utf-8",
            )
            (root / "memory" / "2026-03-09.md").write_text(
                "# Daily Memory - 2026-03-09\n\n## Actions\n- checked memory health\n",
                encoding="utf-8",
            )

            previous = Path.cwd()
            os.chdir(root)
            try:
                checks = self.mod.enhanced_heartbeat()
            finally:
                os.chdir(previous)

            self.assertTrue(any(item.startswith("⚠️ TACTI core unavailable:") for item in checks))
            self.assertTrue(any(item.startswith("Memory compounding: ") for item in checks))


if __name__ == "__main__":
    unittest.main()
