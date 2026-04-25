import tempfile
import unittest
from pathlib import Path

from custom_map_downloader.core.profile_io import (
    normalize_profile_data,
    read_profile,
    write_profile,
)


class ProfileIoTests(unittest.TestCase):
    def test_normalize_profile_data_sanitizes_values(self):
        profile = normalize_profile_data(
            {
                "output_path": " /tmp/out/demo.tif ",
                "resolution_mode": "SCALE",
                "gsd": "2.5",
                "target_scale_denominator": "5000",
                "load_as_layer": "yes",
                "create_vrt": 1,
                "vrt_max_cols": "1024",
                "vrt_max_rows": "2048",
                "vrt_preset_size": "512",
                "layer_id": "abc",
                "layer_name": "Layer",
                "output_crs_authid": "EPSG:25833",
                "extent": {"west": "1", "south": "2", "east": "3", "north": "4"},
            }
        )
        self.assertEqual(profile["output_path"], "/tmp/out/demo.tif")
        self.assertEqual(profile["resolution_mode"], "scale")
        self.assertEqual(profile["gsd"], 2.5)
        self.assertEqual(profile["target_scale_denominator"], 5000.0)
        self.assertTrue(profile["load_as_layer"])
        self.assertTrue(profile["create_vrt"])
        self.assertEqual(profile["vrt_max_cols"], 1024)
        self.assertEqual(profile["vrt_max_rows"], 2048)
        self.assertEqual(profile["vrt_preset_size"], 512)
        self.assertEqual(profile["extent"]["east"], 3.0)

    def test_profile_roundtrip_supports_wrapped_format(self):
        path = Path(tempfile.gettempdir()) / "cmd_profile_roundtrip.json"
        if path.exists():
            path.unlink()

        try:
            write_profile(
                path,
                {
                    "output_path": "/tmp/export/tile.png",
                    "resolution_mode": "gsd",
                    "gsd": 1.0,
                },
            )
            restored = read_profile(path)
        finally:
            if path.exists():
                path.unlink()

        self.assertEqual(restored["output_path"], "/tmp/export/tile.png")
        self.assertEqual(restored["resolution_mode"], "gsd")
        self.assertEqual(restored["gsd"], 1.0)

    def test_profile_roundtrip_supports_bare_format(self):
        path = Path(tempfile.gettempdir()) / "cmd_profile_bare.json"
        if path.exists():
            path.unlink()

        try:
            path.write_text('{"output_path": "/tmp/export/bare.vrt"}', encoding="utf-8")
            restored = read_profile(path)
        finally:
            if path.exists():
                path.unlink()

        self.assertEqual(restored["output_path"], "/tmp/export/bare.vrt")


if __name__ == "__main__":
    unittest.main()
