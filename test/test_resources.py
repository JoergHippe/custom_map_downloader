# coding=utf-8
"""Resources test.

.. note:: This program is free software; you can redistribute it and/or modify
     it under the terms of the GNU General Public License as published by
     the Free Software Foundation; either version 2 of the License, or
     (at your option) any later version.

"""

__author__ = 'abhinavjayaswal10@gmail.com'
__date__ = '2025-11-18'
__copyright__ = 'Copyright 2025, Abhinav Jayswal'

import unittest

try:
    from qgis.PyQt.QtGui import QIcon
    HAS_QGIS = True
except Exception:
    HAS_QGIS = False



@unittest.skipUnless(HAS_QGIS, "QGIS not available; skipping resources test")
class CustomMapDownloaderResourcesTest(unittest.TestCase):
    """Test rerources work."""

    def setUp(self):
        """Runs before each test."""
        pass

    def tearDown(self):
        """Runs after each test."""
        pass

    def test_icon_png(self):
        """Test we can click OK."""
        path = ':/plugins/CustomMapDownloader/icon.png'
        icon = QIcon(path)
        self.assertFalse(icon.isNull())

if __name__ == "__main__":
    suite = unittest.makeSuite(CustomMapDownloaderResourcesTest)
    runner = unittest.TextTestRunner(verbosity=2)
    runner.run(suite)



