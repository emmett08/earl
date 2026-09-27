"""Model arithmetic, stability, missingness and EAL acquisition contract."""

from __future__ import annotations

from copy import deepcopy
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import sys
import unittest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import tool  # noqa: E402


def fixture(name: str = "attached-synthetic") -> tuple[dict, str]:
    data = (HERE / "scenarios" / f"{name}.json").read_bytes()
    return json.loads(data, parse_float=Decimal), hashlib.sha256(data).hexdigest()


class TechnicalDebtToolTests(unittest.TestCase):
    def test_attached_synthetic_calculation_and_certificates(self) -> None:
        scenario, digest = fixture()
        result = tool.evaluate(scenario, digest)
        self.assertEqual(result["status"], "estimated")
        self.assertEqual(result["basis"], "synthetic")
        self.assertAlmostEqual(result["J"], 3365.4363805593175, places=8)
        self.assertAlmostEqual(result["principal_pv"], 11302.864075991034, places=8)
        self.assertAlmostEqual(result["interest_pv"], 39298.290564315794, places=8)
        self.assertAlmostEqual(result["D_H"], 50601.15464030683, places=8)
        for arm in ("actual", "reference"):
            certificate = result["stability"][arm]
            self.assertLess(certificate["weighted_norm_beta"], 1)
            self.assertEqual(certificate["linear_solve_residual_max_abs"], 0)

    def test_horizon_zero_and_undiscounted_identity(self) -> None:
        scenario, digest = fixture()
        scenario["remediation"].update(H=0, delta=Decimal("1"))
        now = tool.evaluate(scenario, digest)
        self.assertEqual(now["principal_pv"], 12000)
        self.assertEqual(now["interest_pv"], 0)
        self.assertEqual(now["D_H"], 12000)
        scenario["remediation"]["H"] = 12
        later = tool.evaluate(scenario, digest)
        self.assertAlmostEqual(later["D_H"], 12000 + 12 * later["J"], places=7)

    def test_signed_carrying_difference_is_not_clamped(self) -> None:
        scenario, digest = fixture()
        scenario["actual"], scenario["reference"] = scenario["reference"], scenario["actual"]
        scenario["remediation"].update(P=0, H=1, delta=1)
        result = tool.evaluate(scenario, digest)
        self.assertLess(result["J"], 0)
        self.assertEqual(result["D_H"], result["J"])

    def test_singular_and_supercritical_are_rejected(self) -> None:
        scenario, digest = fixture()
        scenario["actual"] = {"work_categories": ["one"], "M": [[1, 0]],
                              "B": [[1]], "c": [1], "ell": 0}
        with self.assertRaisesRegex(ValueError, "singular"):
            tool.evaluate(scenario, digest)
        scenario["actual"]["B"] = [[2]]
        with self.assertRaisesRegex(ValueError, "subcritical"):
            tool.evaluate(scenario, digest)

    def test_acyclic_large_edge_is_stable_despite_row_sum(self) -> None:
        scenario, digest = fixture()
        scenario["actual"] = {"work_categories": ["child", "parent"],
                              "M": [[0, 0], [1, 0]], "B": [[100, 0], [0, 0]],
                              "c": [1, 1], "ell": 0}
        # A self-loop of 100 is unstable; the acyclic edge has radius zero.
        scenario["actual"]["B"] = [[0, 100], [0, 0]]
        result = tool.evaluate(scenario, digest)
        self.assertEqual(result["actual_period_cost"], 1212)
        self.assertLess(result["stability"]["actual"]["weighted_norm_beta"], 1)

    def test_permutation_and_work_unit_scaling_preserve_cost(self) -> None:
        scenario, digest = fixture()
        baseline = tool.evaluate(scenario, digest)
        original = deepcopy(scenario["actual"])
        permutation = [2, 0, 3, 1]
        scenario["actual"]["work_categories"] = [original["work_categories"][i] for i in permutation]
        scenario["actual"]["M"] = [original["M"][i] for i in permutation]
        scenario["actual"]["B"] = [[original["B"][i][j] for j in permutation]
                                   for i in permutation]
        scenario["actual"]["c"] = [original["c"][i] for i in permutation]
        relabelled = tool.evaluate(scenario, digest)
        self.assertEqual(relabelled["exact"]["J"], baseline["exact"]["J"])
        factors = [Decimal("2"), Decimal("0.5"), Decimal("5"), Decimal("0.2")]
        permuted = deepcopy(scenario["actual"])
        scenario["actual"]["M"] = [[factors[i] * value for value in row]
                                   for i, row in enumerate(permuted["M"])]
        scenario["actual"]["B"] = [[factors[i] * value / factors[j]
                                      for j, value in enumerate(row)]
                                   for i, row in enumerate(permuted["B"])]
        scenario["actual"]["c"] = [value / factors[i]
                                   for i, value in enumerate(permuted["c"])]
        scaled = tool.evaluate(scenario, digest)
        self.assertEqual(scaled["exact"]["J"], baseline["exact"]["J"])

    def test_missing_empirical_inputs_are_not_zero_or_false(self) -> None:
        scenario, digest = fixture("incomplete-empirical")
        result = tool.evaluate(scenario, digest)
        self.assertEqual(result["status"], "not_estimable")
        self.assertIn("actual.B", result["missing_fields"])
        self.assertIn("lambda", result["missing_fields"])
        self.assertIn("remediation.P", result["missing_fields"])
        self.assertIn("candidate_sha256", result["missing_fields"])
        self.assertIn("context.candidate_sha256", result["missing_fields"])
        self.assertNotIn("J", result)
        self.assertNotIn("D_H", result)

    def test_malformed_inputs_and_mismatched_candidate_fail(self) -> None:
        scenario, digest = fixture()
        scenario["lambda"][0] = True
        with self.assertRaisesRegex(ValueError, "JSON number"):
            tool.evaluate(scenario, digest)
        scenario, _ = fixture()
        scenario["actual"]["B"][0] = [0]
        with self.assertRaisesRegex(ValueError, "4 entries"):
            tool.evaluate(scenario, digest)
        scenario, _ = fixture()
        scenario["candidate_sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "differs"):
            tool.evaluate(scenario, digest, {"candidate_sha256": "1" * 64})
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            json.loads('{"schema":1,"schema":2}', object_pairs_hook=tool._unique_object)

    def test_eal_envelope_is_pinned_and_not_estimable_is_successful_observation(self) -> None:
        _, digest = fixture("incomplete-empirical")
        request = {"evidence_id": "empirical_gap", "environment": "fulfilment_v3",
                   "tool": "technical_debt", "tool_version": "1",
                   "input": {"scenario_path": "experiments/architecture_extension_v3/technical_debt/scenarios/incomplete-empirical.json",
                             "expected_sha256": digest},
                   "context": {"experiment": "architecture-extension-v3", "stage": "post-B"}}
        envelope = tool.collect(request)
        self.assertEqual(envelope["value"]["status"], "not_estimable")
        self.assertEqual(envelope["request"]["input"], request["input"])
        self.assertEqual(envelope["details"]["input_sha256"], digest)
        request["input"]["expected_sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "differs"):
            tool.collect(request)
        request["input"]["scenario_path"] = "../escape.json"
        with self.assertRaisesRegex(ValueError, "escape"):
            tool.collect(request)

    def test_agent_facing_estimate_is_compact_and_replayable(self) -> None:
        _, digest = fixture()
        request = {"evidence_id": "synthetic_calculation", "environment": "fulfilment_v3",
                   "tool": "technical_debt", "tool_version": "1",
                   "input": {"scenario_path": "experiments/architecture_extension_v3/technical_debt/scenarios/attached-synthetic.json",
                             "expected_sha256": digest},
                   "context": {"experiment": "architecture-extension-v3", "stage": "post-B"}}
        value = tool.collect(request)["value"]
        self.assertEqual(value["status"], "estimated")
        self.assertNotIn("exact", value)
        self.assertNotIn("positive_witness_exact", value["stability"]["actual"])
        self.assertEqual(len(value["audit_sha256"]), 64)
        self.assertLess(len(json.dumps(value)), 2000)


if __name__ == "__main__":
    unittest.main()
