"""Calibrate the revised instrument against immutable v3 candidate snapshots.

Set EARL_V3_RETAINED_RUN_ROOT to the extracted run-36334071057 directory.
Locally, the sibling run directory is used when present. The archive is not
checked into the source tree or shown to coding agents in subsequent trials.
"""

from __future__ import annotations

import importlib.util
import os
import tempfile
import unittest
from pathlib import Path


STUDY = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("architecture_extension_v4_assessor", STUDY / "assess.py")
assert _spec is not None and _spec.loader is not None
assessor = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(assessor)


class AssessorContractTests(unittest.TestCase):
    def test_version_and_case_inventory(self) -> None:
        self.assertEqual(len(assessor.cases_for("R", "B")), 15)
        self.assertEqual(len(assessor.cases_for("R", "C")), 20)
        names = set(assessor.cases_for("R", "D"))
        self.assertEqual(len(names), 26)
        self.assertNotIn("unknown_refund_outcome", names)
        self.assertTrue({"unknown_before_refund_request", "applied_refund_status_unknown",
                         "not_applied_refund_retry", "split_dispatch_save_failure"} <= names)
        for stage in "BCD":
            self.assertEqual(assessor.cases_for("W", stage), assessor.V3.cases_for("W", stage))

    def test_invalid_family_or_stage_rejected(self) -> None:
        for family, stage in (("X", "D"), ("R", "A")):
            with self.assertRaises(ValueError):
                assessor.assess(Path("."), family, stage)

    def test_candidate_import_failure_is_invalid_not_failed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            package = Path(temporary) / "fulfilment"
            package.mkdir()
            (package / "__init__.py").write_text("def broken(:\n", encoding="utf-8")
            record = assessor.assess(Path(temporary), "R", "D")
        self.assertEqual(record["failed"], 0)
        self.assertEqual(record["passed"], 0)
        self.assertEqual(record["invalid"], len(assessor.cases_for("R", "D")))


class RetainedCandidateCalibration(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        default = STUDY.parents[3] / "run-36334071057"
        cls.archive = Path(os.environ.get("EARL_V3_RETAINED_RUN_ROOT", default))
        if not (cls.archive / "raw/attempt-1-host-D-sandbox-repair-R-K1/source").is_dir():
            raise unittest.SkipTest("extracted immutable run 36334071057 artefacts not supplied")

    def candidate(self, stage: str, clone: int) -> Path:
        return self.archive / "raw" / f"attempt-1-host-{stage}-sandbox-repair-R-K{clone}" / "source"

    def test_three_retained_sequences_expose_only_substantiated_defect(self) -> None:
        expected_failures = {
            ("C", 3): {"split_dispatch_save_failure"},
            ("D", 3): {"split_dispatch_save_failure", "checkout_rollback_acknowledgement_loss"},
        }
        for stage in "BCD":
            for clone in (1, 2, 3):
                with self.subTest(stage=stage, clone=clone):
                    source = self.candidate(stage, clone)
                    self.assertTrue(source.is_dir())
                    record = assessor.assess(source, "R", stage)
                    failures = {name for name, finding in record["findings"].items()
                                if finding["status"] == "fail"}
                    self.assertEqual(record["schema_version"], "architecture-extension-v4/assessor/1")
                    self.assertEqual(record["source_sha256"], assessor.source_digest(source))
                    self.assertEqual(record["invalid"], 0)
                    self.assertEqual(failures, expected_failures.get((stage, clone), set()))
                    self.assertEqual(record["passed"] + record["failed"], len(assessor.cases_for("R", stage)))

    def test_retained_d_sources_match_archived_hashes(self) -> None:
        archived = {
            1: "94ae7d4198c3acbe1e62e4904052378753b12f9f4e6c2d1daace7b1ba6b5f05a",
            2: "e347b04e62784797112befe8fc4335eb82f42717a74a5bd447dfb3a8d3800ada",
            3: "6ccdc234f0646a911fe68bf43e78fcfde7efed07d433ec814d4c7a2e7d8cb404",
        }
        for clone, digest in archived.items():
            self.assertEqual(assessor.source_digest(self.candidate("D", clone)), digest)


if __name__ == "__main__":
    unittest.main()
