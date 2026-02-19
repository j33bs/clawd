from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import unittest


def _load_team_chat_module():
    repo_root = Path(__file__).resolve().parents[1]
    scripts_dir = repo_root / "workspace" / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    mod_path = repo_root / "workspace" / "scripts" / "team_chat.py"
    spec = importlib.util.spec_from_file_location("team_chat", str(mod_path))
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class TestTeamChatGuard(unittest.TestCase):
    def test_protected_branch_forces_disable(self):
        team_chat = _load_team_chat_module()
        out = team_chat._guard_controls("main", True, True, "I_UNDERSTAND", False, False)
        self.assertTrue(out["protected_branch"])
        self.assertFalse(out["final_auto_commit"])
        self.assertFalse(out["final_accept_patches"])

    def test_auto_commit_disabled_when_commit_arm_missing(self):
        team_chat = _load_team_chat_module()
        out = team_chat._guard_controls("feature/x", True, True, "", False, False)
        self.assertFalse(out["protected_branch"])
        self.assertTrue(out["commit_not_armed"])
        self.assertFalse(out["final_auto_commit"])
        self.assertFalse(out["final_accept_patches"])

    def test_auto_commit_enabled_when_armed_on_feature_branch(self):
        team_chat = _load_team_chat_module()
        out = team_chat._guard_controls("feature/x", True, True, "I_UNDERSTAND", False, False)
        self.assertFalse(out["protected_branch"])
        self.assertFalse(out["commit_not_armed"])
        self.assertTrue(out["final_auto_commit"])
        self.assertTrue(out["final_accept_patches"])

    def test_dirty_tree_blocks_auto_commit_without_allow_dirty(self):
        team_chat = _load_team_chat_module()
        out = team_chat._guard_controls("feature/x", True, True, "I_UNDERSTAND", False, True)
        self.assertTrue(out["dirty_tree_blocked"])
        self.assertFalse(out["final_auto_commit"])
        self.assertTrue(out["final_accept_patches"])

    def test_dirty_tree_allows_auto_commit_with_allow_dirty(self):
        team_chat = _load_team_chat_module()
        out = team_chat._guard_controls("feature/x", True, True, "I_UNDERSTAND", True, True)
        self.assertFalse(out["dirty_tree_blocked"])
        self.assertTrue(out["final_auto_commit"])
        self.assertTrue(out["final_accept_patches"])


if __name__ == "__main__":
    unittest.main()
