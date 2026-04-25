import unittest

from scripts import run_windows_qgis_scenarios


class WindowsQgisScenarioRunnerTests(unittest.TestCase):
    def test_read_scenario_names_prefers_explicit_names(self):
        config = {
            "scenarios": [{"name": "a"}, {"name": "b"}],
            "scenario_groups": {"group1": ["x", "y"]},
        }

        names = run_windows_qgis_scenarios.read_scenario_names(config, "group1", ["explicit"])

        self.assertEqual(names, ["explicit"])

    def test_read_scenario_names_uses_group_when_given(self):
        config = {
            "scenarios": [{"name": "a"}, {"name": "b"}],
            "scenario_groups": {"group1": ["x", "y"]},
        }

        names = run_windows_qgis_scenarios.read_scenario_names(config, "group1", [])

        self.assertEqual(names, ["x", "y"])

    def test_read_scenario_names_falls_back_to_all_scenarios(self):
        config = {
            "scenarios": [{"name": "a"}, {"name": "b"}],
            "scenario_groups": {"group1": ["x", "y"]},
        }

        names = run_windows_qgis_scenarios.read_scenario_names(config, None, [])

        self.assertEqual(names, ["a", "b"])

    def test_config_contains_official_webmaps_catalog_group(self):
        config = run_windows_qgis_scenarios.load_config()
        groups = config.get("scenario_groups", {}) or {}

        self.assertIn("official_webmaps_catalog", groups)
        self.assertTrue(groups["official_webmaps_catalog"])


if __name__ == "__main__":
    unittest.main()
