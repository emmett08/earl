import importlib.util
import json
from pathlib import Path
import re
import unittest

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("bias_next_validate", HERE / "validate.py")
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class NextExperimentPlansTest(unittest.TestCase):
    def test_three_plans_are_separate_and_not_ready(self):
        result = MODULE.validate()
        self.assertTrue(result["valid"])
        self.assertEqual(len(result["experiments"]), 3)
        self.assertTrue(all(not item["ready"] for item in result["experiments"].values()))

    def test_api_secret_and_human_boundary(self):
        representation, topology, human = MODULE.load_plans()
        self.assertEqual(representation["credential_env"], "OPENAI_API_TOKEN")
        self.assertEqual(topology["credential_env"], "OPENAI_API_TOKEN")
        self.assertIsNone(human["credential_env"])
        self.assertFalse(human["live_api_during_observation"])

    def test_equal_compute_is_structural(self):
        topology = MODULE.load_plans()[1]
        contract = topology["compute_contract"]
        self.assertEqual(contract["calls_per_case"], 2)
        self.assertEqual(len(contract["repeated_direct_roles"]), 2)
        self.assertEqual(len(contract["independent_roles"]), 2)
        self.assertTrue(contract["same_returned_model_required"])
        self.assertIn("same deterministic", contract["synthesis"])

    def test_plans_contain_no_outcomes_or_secret_values(self):
        for path in MODULE.PLAN_PATHS:
            text = path.read_text(encoding="utf-8")
            plan = json.loads(text)
            self.assertIsNone(plan["outcomes"])
            self.assertIsNone(re.search(r"sk-(?:proj-)?[A-Za-z0-9_-]{12,}", text))


if __name__ == "__main__":
    unittest.main()
