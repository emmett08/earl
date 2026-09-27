"""A CLI turn gives a conditional tariff scenario, never an invoice."""

import unittest

from experiments.architecture_extension_v4.study.price import scenario_from_cli_turns


class CLIScenarioTests(unittest.TestCase):
    def test_reported_partition_yields_labelled_range(self):
        report = scenario_from_cli_turns({"status": "reported", "totals": {
            "input_tokens": 100, "cached_input_tokens": 20,
            "cache_write_input_tokens": 30, "output_tokens": 10,
            "cache_creation_input_tokens": None}})
        self.assertEqual(report["status"], "conditional_scenario")
        self.assertEqual(report["token_partition"]["uncached_input_tokens"], 50)
        self.assertEqual(report["low_usd"], "0.000279")
        self.assertEqual(report["high_usd"], "0.0005588")
        self.assertIsNone(report["billed_usd"])

    def test_missing_cache_write_stays_unknown_but_has_a_rate_scenario(self):
        report = scenario_from_cli_turns({"status": "reported", "totals": {
            "input_tokens": 100, "cached_input_tokens": 0, "output_tokens": 0}})
        self.assertEqual(report["status"], "conditional_scenario")
        self.assertEqual(report["partition_status"], "cache_write_unknown_bounded_under_assumed_rates")
        self.assertIsNone(report["token_partition"]["cache_write_input_tokens"])
        self.assertEqual(report["low_usd"], "0.0002")
        self.assertEqual(report["high_usd"], "0.00055")

    def test_missing_total_input_remains_unpriceable(self):
        report = scenario_from_cli_turns({"status": "reported", "totals": {
            "cached_input_tokens": 0, "output_tokens": 0}})
        self.assertEqual(report["status"], "unavailable")
        self.assertIsNone(report["high_usd"])

    def test_overlapping_partition_rejected(self):
        with self.assertRaises(ValueError):
            scenario_from_cli_turns({"status": "reported", "totals": {
                "input_tokens": 100, "cached_input_tokens": 80,
                "cache_write_input_tokens": 50, "output_tokens": 0}})


if __name__ == "__main__":
    unittest.main()
