import importlib.util
import tempfile
import time
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_policy_router_module():
    mod_path = REPO_ROOT / "workspace" / "scripts" / "policy_router.py"
    spec = importlib.util.spec_from_file_location("policy_router_cache_test", str(mod_path))
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class TestPolicyRouterPolicyCache(unittest.TestCase):
    def test_load_policy_cache_hit_without_mtime_change(self):
        policy_router = _load_policy_router_module()
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "llm_policy.json"
            path.write_text('{"defaults":{"maxTokensPerRequest":111}}\n', encoding="utf-8")
            p1 = policy_router.load_policy(path)
            p2 = policy_router.load_policy(path)
            self.assertEqual(p1["defaults"]["maxTokensPerRequest"], 111)
            self.assertEqual(p2["defaults"]["maxTokensPerRequest"], 111)
            self.assertGreaterEqual(int(policy_router._POLICY_CACHE_STATS["hits"]), 1)

    def test_load_policy_reload_on_mtime_change(self):
        policy_router = _load_policy_router_module()
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "llm_policy.json"
            path.write_text('{"defaults":{"maxTokensPerRequest":111}}\n', encoding="utf-8")
            _ = policy_router.load_policy(path)
            time.sleep(0.02)
            path.write_text('{"defaults":{"maxTokensPerRequest":222}}\n', encoding="utf-8")
            refreshed = policy_router.load_policy(path)
            self.assertEqual(refreshed["defaults"]["maxTokensPerRequest"], 222)
            self.assertGreaterEqual(int(policy_router._POLICY_CACHE_STATS["misses"]), 2)

    def test_repo_root_lookup_cache_hits(self):
        policy_router = _load_policy_router_module()
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "repo"
            nested = root / "a" / "b"
            (root / ".git").mkdir(parents=True, exist_ok=True)
            nested.mkdir(parents=True, exist_ok=True)
            first = policy_router._resolve_repo_root(nested)
            second = policy_router._resolve_repo_root(nested)
            self.assertEqual(first.resolve(), root.resolve())
            self.assertEqual(second.resolve(), root.resolve())
            self.assertGreaterEqual(int(policy_router._REPO_ROOT_CACHE_STATS["hits"]), 1)


if __name__ == "__main__":
    unittest.main()
