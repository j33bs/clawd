import importlib.util
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "workspace" / "scripts" / "c_lawd_conversation_kernel.py"


def load_module(name: str, path: Path):
    script_dir = str(path.parent)
    if script_dir not in sys.path:
        sys.path.insert(0, script_dir)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class CLawdConversationKernelTests(unittest.TestCase):
    def setUp(self):
        self.mod = load_module("c_lawd_conversation_kernel_test", MODULE_PATH)

    def test_packet_includes_identity_overlay_and_hash(self):
        packet = self.mod.build_c_lawd_surface_kernel_packet(
            surface="telegram",
            include_memory=True,
            mode="conversation",
        )
        self.assertTrue(packet.kernel_id.startswith("c_lawd:surface:telegram"))
        self.assertEqual(packet.surface_overlay, "surface:telegram|mode:conversation|memory:on")
        self.assertRegex(packet.kernel_hash, r"^[0-9a-f]{64}$")
        self.assertIn("c_lawd Conversation Kernel", packet.prompt_text)
        self.assertIn("## USER profile", packet.prompt_text)
        self.assertIn("## Active surface", packet.prompt_text)

    def test_string_builder_stays_backward_compatible(self):
        text = self.mod.build_c_lawd_surface_kernel(
            surface="telegram",
            include_memory=False,
            mode="conversation",
        )
        self.assertIsInstance(text, str)
        self.assertIn("surface: telegram", text)
        self.assertNotIn("## MEMORY", text)


if __name__ == "__main__":
    unittest.main()
