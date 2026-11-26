"""Release tooling: which tag a commit gets, and idempotent publishing of the assets."""
import io
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "release"))
import automatic  # noqa: E402


class TagTests(unittest.TestCase):
    TAGS = {"v1.0.0": "a" * 40, "v1.1.1": "b" * 40}

    def test_patch_bump_without_a_declared_version(self):
        self.assertEqual(automatic.choose_tag(self.TAGS, "c" * 40), "v1.1.2")
        self.assertEqual(automatic.choose_tag({}, "c" * 40), "v1.0.1")

    def test_declared_minor_version_wins_over_the_patch_bump(self):
        self.assertEqual(automatic.choose_tag(self.TAGS, "c" * 40, (1, 2, 0)), "v1.2.0")
        self.assertEqual(automatic.choose_tag(self.TAGS, "c" * 40, (2, 0, 0)), "v2.0.0")

    def test_an_old_declared_version_never_lowers_the_tag(self):
        self.assertEqual(automatic.choose_tag(self.TAGS, "c" * 40, (1, 1, 0)), "v1.1.2")
        self.assertEqual(automatic.choose_tag({**self.TAGS, "v1.2.0": "d" * 40}, "c" * 40, (1, 2, 0)), "v1.2.1")

    def test_a_reserved_tag_is_reused(self):
        self.assertEqual(automatic.choose_tag(self.TAGS, "b" * 40, (9, 0, 0)), "v1.1.1")

    def test_declared_version_reads_the_newest_released_heading(self):
        with tempfile.TemporaryDirectory() as directory:
            changelog = Path(directory) / "CHANGELOG.md"
            changelog.write_text("# Changelog\n\n## [Unreleased]\n\n## [1.10.0]\n\n## [1.9.0]\n\n## [1.0.0]\n",
                                 encoding="utf-8")
            self.assertEqual(automatic.declared_version(changelog), (1, 10, 0))
            changelog.write_text("# Changelog\n\n## [Unreleased]\n", encoding="utf-8")
            self.assertIsNone(automatic.declared_version(changelog))
            self.assertIsNone(automatic.declared_version(Path(directory) / "missing.md"))

    def test_this_repository_changelog_declares_a_version(self):
        self.assertIsNotNone(automatic.declared_version(Path(__file__).resolve().parent.parent / "CHANGELOG.md"))


class PublishTests(unittest.TestCase):
    def run_publish(self, exists, have=()):
        calls = []

        def fake_run(argv, **_kwargs):
            calls.append(argv)
            return mock.Mock(returncode=0 if (argv[1:3] != ["release", "view"] or exists) else 1)

        listing = '{"assets": [%s]}' % ",".join('{"name": "%s"}' % name for name in have)
        with tempfile.TemporaryDirectory() as directory:
            for name in ("a.zip", "install.sh", "SHA256SUMS"):
                (Path(directory) / name).write_text("x")
            env = {"GITHUB_REPOSITORY": "o/r", "RELEASE_TAG": "v1.2.3", "PREVIOUS_TAG": "v1.2.2",
                   "ASSETS_DIR": directory}
            with mock.patch.dict(os.environ, env), mock.patch.object(automatic.subprocess, "run", fake_run), \
                    mock.patch.object(automatic, "command", return_value=listing), redirect_stdout(io.StringIO()):
                automatic.publish()
        return calls

    def test_creates_the_release_with_every_asset(self):
        create = [c for c in self.run_publish(exists=False) if c[1:3] == ["release", "create"]]
        self.assertEqual(len(create), 1)
        for name in ("a.zip", "install.sh", "SHA256SUMS"):
            self.assertTrue(any(arg.endswith(name) for arg in create[0]), name)
        self.assertIn("--verify-tag", create[0])

    def test_a_rerun_only_uploads_missing_assets_and_never_clobbers(self):
        calls = self.run_publish(exists=True, have=["a.zip"])
        self.assertFalse([c for c in calls if c[1:3] == ["release", "create"]])
        upload = [c for c in calls if c[1:3] == ["release", "upload"]]
        self.assertEqual(len(upload), 1)
        self.assertFalse(any(arg.endswith("a.zip") for arg in upload[0]))
        self.assertTrue(any(arg.endswith("install.sh") for arg in upload[0]))
        self.assertNotIn("--clobber", upload[0])

    def test_a_rerun_with_everything_present_does_nothing(self):
        calls = self.run_publish(exists=True, have=["a.zip", "install.sh", "SHA256SUMS"])
        self.assertFalse([c for c in calls if c[1:3] in (["release", "create"], ["release", "upload"])])


if __name__ == "__main__":
    unittest.main()
