"""Runtime regression checks for Qt-owned raster memory.

Requires real QGIS/Qt bindings; executed only in the QGIS runtime matrix.
"""

from __future__ import annotations

import os
import unittest

try:
    from qgis.PyQt.QtGui import QColor, QImage

    from custom_map_downloader.core.raster_ops import qimage_to_rgba_array
except ImportError:
    if os.environ.get("CMD_REQUIRE_QGIS") == "1":
        raise
    QColor = QImage = None
    qimage_to_rgba_array = None


@unittest.skipIf(QImage is None, "real QGIS/Qt bindings required")
class QImageMemoryTests(unittest.TestCase):
    def test_rgba_values_and_detached_lifetime(self):
        # A three-pixel row ensures that the image stride is not assumed.
        image = QImage(3, 2, QImage.Format.Format_RGBA8888)
        image.fill(QColor(0, 0, 0, 0))
        image.setPixelColor(0, 0, QColor(15, 25, 35, 45))
        image.setPixelColor(2, 1, QColor(105, 115, 125, 135))

        array = qimage_to_rgba_array(image, width=3, height=2)
        del image

        self.assertEqual(array.shape, (2, 3, 4))
        self.assertEqual(array[0, 0].tolist(), [15, 25, 35, 45])
        self.assertEqual(array[1, 2].tolist(), [105, 115, 125, 135])
        self.assertTrue(array.flags.owndata)

    def test_modifying_array_does_not_modify_qimage(self):
        image = QImage(2, 1, QImage.Format.Format_RGBA8888)
        image.fill(QColor(1, 2, 3, 4))
        result = qimage_to_rgba_array(image, width=2, height=1)
        result[0, 0, 0] = 255
        self.assertEqual(image.pixelColor(0, 0).red(), 1)


if __name__ == "__main__":
    unittest.main()
