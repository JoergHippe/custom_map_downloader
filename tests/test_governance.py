import tempfile
import unittest
from pathlib import Path

from custom_map_downloader.core.release_governance import (
    changelog_has_version,
    validate_release_governance,
)


class ReleaseGovernanceTests(unittest.TestCase):
    def test_changelog_has_version_heading(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            changelog = Path(tmpdir) / "CHANGELOG.md"
            changelog.write_text("# Changelog\n\n## [1.2.3] - 2026-03-07\n", encoding="utf-8")
            self.assertTrue(changelog_has_version(changelog, "1.2.3"))
            self.assertFalse(changelog_has_version(changelog, "1.2.4"))

    def test_validate_release_governance_detects_missing_fields(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            metadata = root / "metadata.txt"
            changelog = root / "CHANGELOG.md"
            metadata.write_text("version=1.2.3\n", encoding="utf-8")
            changelog.write_text("# Changelog\n\n## [0.9.0] - 2026-03-07\n", encoding="utf-8")
            errors = validate_release_governance(metadata, changelog)
            self.assertEqual(len(errors), 2)
            self.assertIn("CHANGELOG.md does not contain an entry for version 1.2.3", errors)
            self.assertIn("metadata.txt is missing a changelog= entry", errors)

    def test_validate_release_governance_accepts_consistent_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            metadata = root / "metadata.txt"
            changelog = root / "CHANGELOG.md"
            metadata.write_text(
                "version=1.2.3\nchangelog=1.2.3: sample release notes.\n",
                encoding="utf-8",
            )
            changelog.write_text("# Changelog\n\n## [1.2.3] - 2026-03-07\n", encoding="utf-8")
            self.assertEqual(validate_release_governance(metadata, changelog), [])
