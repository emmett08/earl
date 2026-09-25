"""Regression checks for study separation, arm parity and readiness gates."""

from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from validate import PLAN, validate


class ProspectivePlanTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.plan = json.loads(Path(PLAN).read_text(encoding="utf-8"))

    def test_current_specification_is_valid_but_unrun(self) -> None:
        errors, blockers = validate(self.plan)
        self.assertEqual(errors, [])
        self.assertIn("independent_case_manifest_sha256", blockers)
        self.assertIn("registration_sha256", blockers)
        self.assertIsNone(self.plan["execution"]["observed_results"])

    def test_reordered_stages_cannot_pass_as_the_proposed_sequence(self) -> None:
        changed = copy.deepcopy(self.plan)
        changed["stages"][1], changed["stages"][2] = changed["stages"][2], changed["stages"][1]
        errors, _ = validate(changed)
        self.assertTrue(any("Stages must follow" in error for error in errors))

    def test_prose_arm_cannot_lose_tool_access(self) -> None:
        changed = copy.deepcopy(self.plan)
        changed["conditions"]["core_arms"][0]["tool_permissions"] = "none"
        errors, _ = validate(changed)
        self.assertTrue(any("equal tool_permissions" in error for error in errors))

    def test_source_success_selection_cannot_replace_full_attempt_outcome(self) -> None:
        changed = copy.deepcopy(self.plan)
        changed["analysis"]["missingness"] = "Drop unvalidated EAL sources and tool failures"
        errors, _ = validate(changed)
        self.assertTrue(any("primary denominator" in error for error in errors))

    def test_no_fabricated_ready_or_completed_result(self) -> None:
        changed = copy.deepcopy(self.plan)
        changed["status"] = "complete"
        changed["execution"]["observed_results"] = {"success": True}
        errors, blockers = validate(changed)
        self.assertTrue(blockers)
        self.assertTrue(any("unrun specification" in error or "specification only" in error for error in errors))

    def test_digest_shaped_strings_never_certify_executability(self) -> None:
        changed = copy.deepcopy(self.plan)
        changed["required_receipts"] = {key: "0" * 64 for key in changed["required_receipts"]}
        changed["analysis"].update({
            "family_count_confirmatory": 1,
            "practical_gain_margin": 0.05,
            "false_support_margin": 0,
            "minimum_decision_coverage": 0.8,
        })
        errors, blockers = validate(changed)
        self.assertEqual(errors, [])
        self.assertIn("external_reviewed_receipts_and_ready_execution_plan_absent", blockers)

    def test_boolean_or_zero_coverage_cannot_replace_approved_threshold(self) -> None:
        changed = copy.deepcopy(self.plan)
        changed["analysis"]["minimum_decision_coverage"] = 0
        changed["analysis"]["family_count_confirmatory"] = True
        errors, _ = validate(changed)
        self.assertTrue(any("minimum_decision_coverage" in error for error in errors))
        self.assertTrue(any("family count" in error for error in errors))

    def test_cannot_mark_a_stage_complete_in_specification_version(self) -> None:
        changed = copy.deepcopy(self.plan)
        changed["stages"][0]["status"] = "complete"
        errors, _ = validate(changed)
        self.assertTrue(any("cannot report an executed stage" in error for error in errors))

    def test_receipts_must_be_sha256_and_not_assertions(self) -> None:
        changed = copy.deepcopy(self.plan)
        changed["required_receipts"]["reference_review_sha256"] = "reviewed"
        errors, _ = validate(changed)
        self.assertTrue(any("reference_review_sha256" in error for error in errors))

    def test_no_family_reuse_with_existing_bias_cohort(self) -> None:
        changed = copy.deepcopy(self.plan)
        changed["scope"]["family_namespace"] = "bias_mechanisms_001"
        errors, _ = validate(changed)
        self.assertTrue(any("overlaps an excluded cohort" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
