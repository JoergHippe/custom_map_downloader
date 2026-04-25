import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tests.integration.qgis_test_support import (
    REPO_ROOT,
    deployed_plugin_dir,
    ensure_plugin_import_path,
)


class IntegrationSupportTests(unittest.TestCase):
    def test_repo_import_mode_returns_repo_plugin_dir(self):
        with patch.dict(os.environ, {"CMD_PLUGIN_IMPORT_MODE": "repo"}, clear=False):
            plugin_dir = ensure_plugin_import_path()
        self.assertEqual(plugin_dir, REPO_ROOT / "custom_map_downloader")

    def test_profile_import_mode_uses_qgis_profile_path(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            profile_root = Path(tmpdir) / "profiles"
            plugin_dir = (
                profile_root / "qa-profile" / "python" / "plugins" / "custom_map_downloader"
            )
            plugin_dir.mkdir(parents=True)

            with patch.dict(
                os.environ,
                {
                    "CMD_PLUGIN_IMPORT_MODE": "profile",
                    "CMD_QGIS_PROFILE": "qa-profile",
                    "QGIS_CUSTOM_CONFIG_PATH": tmpdir,
                },
                clear=False,
            ):
                resolved = ensure_plugin_import_path()
                deployed = deployed_plugin_dir("qa-profile")

            self.assertEqual(resolved, plugin_dir)
            self.assertEqual(deployed, plugin_dir)
