# coding=utf-8
"""Dialog test.

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
    from qgis.PyQt.QtGui import QDialogButtonBox, QDialog
    from CustomMapDownloader_dialog import CustomMapDownloaderDialog
    from utilities import get_qgis_app
    QGIS_APP = get_qgis_app()
    HAS_QGIS = True
except Exception:  # pragma: no cover - skip when QGIS unavailable
    HAS_QGIS = False
    QDialogButtonBox = None
    QDialog = None
    CustomMapDownloaderDialog = None
    QGIS_APP = None


@unittest.skipUnless(HAS_QGIS, "QGIS not available; skipping dialog tests")
class CustomMapDownloaderDialogTest(unittest.TestCase):
    """Test dialog works."""

    def setUp(self):
        """Runs before each test."""
        self.dialog = CustomMapDownloaderDialog(None)

    def tearDown(self):
        """Runs after each test."""
        self.dialog = None

    def test_dialog_ok(self):
        """Test we can click OK."""

        button = self.dialog.button_box.button(QDialogButtonBox.Ok)
        button.click()
        result = self.dialog.result()
        self.assertEqual(result, QDialog.Accepted)

    def test_dialog_cancel(self):
        """Test we can click cancel."""
        button = self.dialog.button_box.button(QDialogButtonBox.Cancel)
        button.click()
        result = self.dialog.result()
        self.assertEqual(result, QDialog.Rejected)

if __name__ == "__main__":
    suite = unittest.makeSuite(CustomMapDownloaderDialogTest)
    runner = unittest.TextTestRunner(verbosity=2)
    runner.run(suite)

