import unittest

from custom_map_downloader.core.locale import resolve_locale_code


class LocaleResolutionTests(unittest.TestCase):
    def test_defaults_to_english_for_missing_values(self):
        self.assertEqual(resolve_locale_code(None), "en")
        self.assertEqual(resolve_locale_code(""), "en")
        self.assertEqual(resolve_locale_code("   "), "en")

    def test_extracts_two_letter_code_from_qgis_style_values(self):
        self.assertEqual(resolve_locale_code("de_DE"), "de")
        self.assertEqual(resolve_locale_code("fr-FR"), "fr")
        self.assertEqual(resolve_locale_code("pt"), "pt")

    def test_falls_back_for_invalid_short_values(self):
        self.assertEqual(resolve_locale_code("_"), "en")
        self.assertEqual(resolve_locale_code("x"), "en")


if __name__ == "__main__":
    unittest.main()
