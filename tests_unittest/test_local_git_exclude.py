import io
import unittest

from workspace.scripts import local_git_exclude as lge


class TestLocalGitExclude(unittest.TestCase):
    def test_format_exclude_block_contains_markers_and_patterns(self):
        patterns = lge.get_recommended_excludes()
        block = lge.format_exclude_block(patterns)
        self.assertIn(lge.BEGIN_MARKER, block)
        self.assertIn(lge.END_MARKER, block)
        for item in patterns:
            self.assertIn(item, block)

    def test_merge_exclude_inserts_when_missing(self):
        existing = "alpha\nbeta\n"
        block = lge.format_exclude_block(lge.get_recommended_excludes())
        merged = lge.merge_exclude(existing, block)
        self.assertIn("alpha\nbeta\n", merged)
        self.assertIn(lge.BEGIN_MARKER, merged)

    def test_merge_exclude_replaces_existing_block_without_duplication(self):
        old_block = lge.format_exclude_block(["old/path/"])
        existing = "header\n" + old_block + "footer\n"
        new_block = lge.format_exclude_block(lge.get_recommended_excludes())
        merged = lge.merge_exclude(existing, new_block)
        self.assertEqual(merged.count(lge.BEGIN_MARKER), 1)
        self.assertEqual(merged.count(lge.END_MARKER), 1)
        self.assertIn("header\n", merged)
        self.assertIn("footer\n", merged)
        self.assertNotIn("old/path/", merged)

    def test_merge_exclude_is_idempotent(self):
        block = lge.format_exclude_block(lge.get_recommended_excludes())
        first = lge.merge_exclude("", block)
        second = lge.merge_exclude(first, block)
        self.assertEqual(first, second)

    def test_cli_print_contains_markers(self):
        out = io.StringIO()
        rc = lge.run(["--print"], out=out)
        rendered = out.getvalue()
        self.assertEqual(rc, 0)
        self.assertIn(lge.BEGIN_MARKER, rendered)
        self.assertIn(lge.END_MARKER, rendered)


if __name__ == "__main__":
    unittest.main()
