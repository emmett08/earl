"""Synthetic administrative tests; these are not human observations."""

from __future__ import annotations

import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import trial  # noqa: E402


def demo_manifest() -> dict:
    cases = []
    for i in range(4):
        correct = "a" if i % 2 else "b"
        conventional = "a"
        cases.append({
            "id": f"demo_{i}", "family": f"family_{i}", "domain": "synthetic software",
            "question": f"Hypothetical task {i}: which change should be accepted?",
            "evidence": [{"id": "E1", "text": "The test record has a dated scope."},
                         {"id": "E2", "text": "The source record records a different state."}],
            "options": [{"id": "a", "text": "Option a"}, {"id": "b", "text": "Option b"}],
            "reference": {"correct_option_id": correct, "rationale": "Checked synthetic reference."},
            "review": {"initial_reviewers": ["R1", "R2"], "adjudicator": "R3", "approved": True},
            "assistance": {
                "conventional_ai": {
                    "fluent": {"text": "The answer is clearly option a.", "recommendation_id": conventional},
                    "plain": {"text": "Option a is suggested.", "recommendation_id": conventional}},
                "prose_challenge": {
                    "fluent": {"text": "The dated record challenges option a; inspect its scope.",
                               "recommendation_id": correct},
                    "plain": {"text": "Record date and scope challenge option a.",
                              "recommendation_id": correct}},
                "eal_structure": {
                    "fluent": {"text": "EAL/2 checked fixture with the dated-record objection.",
                               "recommendation_id": correct},
                    "plain": {"text": "EAL/2 record and objection fixture.",
                              "recommendation_id": correct}},
                "eal_agent": {
                    "fluent": {"text": "Inspect the dated record carefully before choosing.",
                               "recommendation_id": correct},
                    "plain": {"text": "Check record dates.", "recommendation_id": correct}},
                "evidence_only": {
                    "fluent": {"text": "The records have different dates.", "recommendation_id": None},
                    "plain": {"text": "Record dates differ.", "recommendation_id": None}},
                "no_assistance": {
                    "fluent": {"text": "", "recommendation_id": None},
                    "plain": {"text": "", "recommendation_id": None}},
            },
        })
    return {"schema": trial.SCHEMA, "cases": cases}


def response(packet: dict, answer_id: str) -> dict:
    return {"phase": packet["phase"], "freeze_sha256": packet["freeze_sha256"],
            "participant_id": packet["participant_id"], "case_id": packet["case_id"],
            "packet_sha256": packet["packet_sha256"], "answer_id": answer_id,
            "confidence": 60, "reason": "I checked the supplied synthetic record.",
            "elapsed_seconds": 25.0}


class TrialTests(unittest.TestCase):
    def setUp(self):
        self.manifest = demo_manifest()

    def test_balanced_allocation_and_masked_pre_packet(self):
        frozen = trial.allocate(self.manifest, 13, 421)
        trial.validate_freeze(frozen, self.manifest)
        counts = {(arm, wording): sum(p["arm"] == arm and p["wording"] == wording
                                   for p in frozen["participants"])
                  for arm in trial.ARMS for wording in trial.WORDINGS}
        self.assertEqual(max(counts.values()) - min(counts.values()), 1)
        packet = trial.pre_packet(frozen, self.manifest, "P00001", "demo_0")
        self.assertNotIn("arm", packet)
        self.assertNotIn("assistance", packet)
        self.assertNotIn("reference", packet)
        self.assertNotIn("correct_option_id", str(packet))
        self.assertEqual(len({p["participant_id"] for p in frozen["participants"]}), 13)

    def test_post_requires_bound_pre_response_and_preserves_arm(self):
        frozen = trial.allocate(self.manifest, 12, 1)
        pre = trial.pre_packet(frozen, self.manifest, "P00001", "demo_0")
        answer = response(pre, "a")
        after = trial.post_packet(frozen, self.manifest, answer)
        assigned = frozen["participants"][0]["arm"]
        wording = frozen["participants"][0]["wording"]
        self.assertEqual(after["assistance"],
                         self.manifest["cases"][0]["assistance"][assigned][wording])
        tampered = dict(answer, packet_sha256="0" * 64)
        with self.assertRaisesRegex(ValueError, "different packet"):
            trial.post_packet(frozen, self.manifest, tampered)
        changed = copy.deepcopy(self.manifest)
        changed["cases"][0]["reference"]["correct_option_id"] = "a"
        with self.assertRaisesRegex(ValueError, "changed"):
            trial.pre_packet(frozen, changed, "P00001", "demo_0")

    def test_complete_descriptive_scoring_and_duplicate_rejection(self):
        frozen = trial.allocate(self.manifest, 12, 2)
        records = []
        for participant in frozen["participants"]:
            for case in self.manifest["cases"]:
                pre_packet = trial.pre_packet(frozen, self.manifest,
                                              participant["participant_id"], case["id"])
                before = response(pre_packet, "a")
                post_packet = trial.post_packet(frozen, self.manifest, before)
                after = response(post_packet, case["reference"]["correct_option_id"])
                records.append({"pre": before, "post": after})
        result = trial.score(frozen, self.manifest, records)
        self.assertEqual(result["state"], "complete")
        self.assertEqual(result["recorded_tasks"], 48)
        self.assertTrue(result["descriptive_only"])
        self.assertEqual(sum(s["post_correct"] for s in result["summary"].values()), 48)
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            trial.score(frozen, self.manifest, records + [records[0]])
        self.assertEqual(trial.score(frozen, self.manifest, [records[0]])["state"],
                         "partial_or_unrun")

    def test_rejects_single_advice_truth_and_unreviewed_cases(self):
        changed = copy.deepcopy(self.manifest)
        for c in changed["cases"]:
            for wording in trial.WORDINGS:
                c["assistance"]["conventional_ai"][wording]["recommendation_id"] = c["reference"]["correct_option_id"]
        with self.assertRaisesRegex(ValueError, "both correct and incorrect"):
            trial.validate_manifest(changed)
        changed = copy.deepcopy(self.manifest)
        changed["cases"][0]["review"]["approved"] = False
        with self.assertRaisesRegex(ValueError, "approve"):
            trial.validate_manifest(changed)
        changed = copy.deepcopy(self.manifest)
        changed["cases"][0]["assistance"]["evidence_only"]["plain"]["recommendation_id"] = "a"
        changed["cases"][0]["assistance"]["evidence_only"]["fluent"]["recommendation_id"] = "a"
        with self.assertRaisesRegex(ValueError, "must not recommend"):
            trial.validate_manifest(changed)


if __name__ == "__main__":
    unittest.main()
