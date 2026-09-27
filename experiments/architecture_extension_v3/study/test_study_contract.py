"""Adversarial checks for assessor replay, source binding and assignment lineage."""

from __future__ import annotations

import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import analyse
import freeze
from assess import source_digest


STUDY = Path(__file__).resolve().parent
BASE = freeze.BASE


class StudyContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        result = subprocess.run(
            [sys.executable, str(STUDY / "assess.py"), "--candidate", str(BASE),
             "--family", "W", "--stage", "B"],
            capture_output=True, text=True, check=True,
        )
        cls.assessment = json.loads(result.stdout)
        cls.tree = analyse.tree_manifest(BASE)["tree_sha256"]

    def record(self) -> dict:
        return {
            "family": "W", "arm": "P0", "stage": "B", "clone_id": "W-K1",
            "source_sha256": source_digest(BASE), "input_tree_sha256": self.tree,
            "output_tree_sha256": self.tree, "candidate_snapshot_path": str(BASE),
            "model_id": "gpt-6-sol", "model_revision": None,
            "agent_class": "local-coding-agent", "packet_sha256": None,
            "assessor": copy.deepcopy(self.assessment),
            "coding_elapsed_seconds": 10, "host_assessment_seconds": 0,
            "wall_cap_enforced": True,
        }

    def test_valid_retained_assessment_replays(self) -> None:
        row = analyse._record(self.record(), ("W", "P0", "B"))
        self.assertEqual((row["passed"], row["failed"], row["invalid"]), (10, 3, 0))

    def test_one_forged_pass_cannot_replace_due_case_set(self) -> None:
        row = self.record()
        row["assessor"]["findings"] = {
            "closed_warehouse_priority": {"status": "pass", "detail": "fabricated"}}
        row["assessor"].update(passed=1, failed=0, invalid=0)
        with self.assertRaisesRegex(ValueError, "differs from replay"):
            analyse._record(row, ("W", "P0", "B"))

    def test_substituted_source_digest_is_rejected(self) -> None:
        row = self.record()
        row["source_sha256"] = "0" * 64
        row["assessor"]["source_sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "differs from retained snapshot"):
            analyse._record(row, ("W", "P0", "B"))

    def test_stage_does_not_inherit_other_source(self) -> None:
        a = "a" * 64
        keyed = {}
        assigned = {f"R-K{index}": arm for index, arm in enumerate(analyse.ARMS, 1)}
        for index, arm in enumerate(analyse.ARMS, 1):
            for stage in analyse.STAGES:
                input_tree = a if stage == "B" else ("b" if stage == "C" else "c") * 64
                output_tree = ("b" if stage == "B" else "c" if stage == "C" else "d") * 64
                keyed[("R", arm, stage)] = {
                    "input_tree_sha256": input_tree, "output_tree_sha256": output_tree,
                    "clone_id": f"R-K{index}", "model_id": "gpt-6-sol",
                    "model_revision": None, "agent_class": "local-coding-agent",
                }
        analyse.validate_family_lineage("R", keyed, assigned, a)
        keyed[("R", "P2", "C")]["input_tree_sha256"] = "f" * 64
        with self.assertRaisesRegex(ValueError, "does not inherit"):
            analyse.validate_family_lineage("R", keyed, assigned, a)

    def test_freeze_inventory_excludes_paper_and_includes_semantics(self) -> None:
        if not all(path.is_file() for path in freeze.REQUIRED):
            self.skipTest("host/workflow not yet written")
        if freeze.ALLOCATION.is_file():
            names = {p.relative_to(freeze.REPO).as_posix() for p in freeze.tracked_inputs()}
            self.assertIn("experiments/architecture_extension_v3/study/allocation.json", names)
        else:
            # Dry-run the selection predicate without creating a pre-run
            # assignment, which must only be produced by freeze.py create.
            with tempfile.TemporaryDirectory() as temporary:
                placeholder = Path(temporary) / "allocation.json"
                placeholder.write_text("{}")
                original = freeze.ALLOCATION
                freeze.ALLOCATION = placeholder
                try:
                    names = {p.relative_to(freeze.REPO).as_posix() for p in freeze.tracked_inputs()}
                finally:
                    freeze.ALLOCATION = original
        self.assertIn("src/eal/runtime.py", names)
        self.assertIn("grammar/EAL.g4", names)
        self.assertIn("experiments/architecture_extension_v3/host.py", names)
        self.assertIn("experiments/architecture_extension_v3/study/assess.py", names)
        self.assertNotIn("experiments/architecture_extension_v3/paper.md", names)
        self.assertNotIn("experiments/architecture_extension_v3/study/freeze.json", names)


if __name__ == "__main__":
    unittest.main()
