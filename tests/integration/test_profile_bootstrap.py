import unittest
from pathlib import Path

from tests.integration.qgis_test_support import ensure_plugin_import_path, plugin_import_mode

try:
    from qgis.core import QgsProject  # type: ignore  # noqa: F401

    HAS_QGIS = True
except Exception:
    HAS_QGIS = False


@unittest.skipUnless(HAS_QGIS, "QGIS not available; skipping profile bootstrap test")
class PluginProfileBootstrapTest(unittest.TestCase):
    def test_plugin_import_source_matches_requested_mode(self):
        plugin_root = ensure_plugin_import_path()
        import custom_map_downloader  # type: ignore

        module_path = Path(custom_map_downloader.__file__).resolve()
        self.assertTrue(module_path.exists())

        if plugin_import_mode() == "profile":
            resolved_plugin_root = plugin_root.resolve()
            accepted_paths = {
                plugin_root,
                resolved_plugin_root,
            }
            self.assertTrue(
                any(
                    str(candidate) in str(module_path.parent)
                    or str(candidate) in str(module_path.resolve().parent)
                    for candidate in accepted_paths
                ),
                (
                    f"Expected deployed plugin import under {plugin_root} "
                    f"(resolved {resolved_plugin_root}), got {module_path}"
                ),
            )
        else:
            self.assertIn("custom_map_downloader", str(module_path))

    def test_class_factory_is_available(self):
        ensure_plugin_import_path()
        import custom_map_downloader  # type: ignore

        self.assertTrue(hasattr(custom_map_downloader, "classFactory"))
