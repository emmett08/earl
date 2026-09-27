"""Synthetic packaging controls; these are never human review outcomes."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from masked_review import FIXTURES, prepare  # noqa: E402
from runner_capture import copy_source, digest, json_write, tree_digest, tree_entries  # noqa: E402


class MaskedReviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.run = self.root / "run"
        self.run.mkdir()
        self.release = self.root / "released"
        self.mapping = self.root / "host-only" / "mapping.json"
        baseline = FIXTURES / "entitlement" / "source"
        baseline_sha = tree_digest(tree_entries(baseline))
        rows = []
        for stage in "BCD":
            episode = self.run / "blocks" / "test-block" / "hidden-clone" / stage
            episode.mkdir(parents=True)
            source_sha, _ = copy_source(baseline, episode / "source")
            row = {"system": "entitlement", "block": "test-block", "clone": "hidden-clone",
                   "arm": "P0", "stage": stage, "output_source_tree_sha256": source_sha}
            rows.append(row)
            json_write(episode / "episode.json", row)
            json_write(episode / "input.json", {
                "source_tree_sha256": baseline_sha,
                "brief_sha256": digest(FIXTURES / "entitlement" / "features" / f"{stage}.md")})
        json_write(self.run / "summary.json", {"status": "completed_smoke_only",
                                                   "smoke_only": True, "episodes": rows})

    def test_two_independent_blank_forms_and_held_arm_mapping(self):
        result = prepare(self.run, FIXTURES, self.release, self.mapping, allow_smoke=True)
        self.assertEqual(result["cases"], 3)
        mapping = json.loads(self.mapping.read_text())
        self.assertEqual({row["arm"] for row in mapping["cases"]}, {"P0"})
        self.assertEqual({row["stage"] for row in mapping["cases"]}, {"B", "C", "D"})
        self.assertEqual(len({row["sequence_id"] for row in mapping["cases"]}), 1)
        for reviewer in ("reviewer-1", "reviewer-2"):
            form = json.loads((self.release / reviewer / "form.json").read_text())
            self.assertIsNone(form["sealed_at_utc"])
            self.assertTrue(all(all(finding["status"] is None for finding in case["findings"].values())
                                for case in form["cases"]))
            for case in form["cases"]:
                packet = self.release / reviewer / "packets" / case["candidate_id"]
                self.assertTrue((packet / "baseline/service.py").is_file())
                self.assertTrue((packet / "candidate/service.py").is_file())
                self.assertTrue((packet / "CURRENT-FEATURE.md").is_file())
                self.assertTrue((packet / "RUBRIC.md").is_file())
        release_text = "\n".join(p.read_text(errors="replace") for p in self.release.rglob("*") if p.is_file())
        self.assertNotIn("hidden-clone", release_text)
        self.assertNotIn("test-block", release_text)
        self.assertNotIn('"P0"', release_text)
        adjudication = json.loads((self.release / "adjudication-template.json").read_text())
        self.assertTrue(all(case["resolution"] is None for case in adjudication["cases"]))

    def test_label_in_candidate_source_blocks_release(self):
        path = self.run / "blocks/test-block/hidden-clone/D/source/service.py"
        path.write_text(path.read_text() + "\n# P2 treatment\n")
        sha = tree_digest(tree_entries(path.parent))
        episode = path.parents[1]
        row = json.loads((episode / "episode.json").read_text())
        row["output_source_tree_sha256"] = sha
        json_write(episode / "episode.json", row)
        summary = json.loads((self.run / "summary.json").read_text())
        summary["episodes"][-1] = row
        json_write(self.run / "summary.json", summary)
        with self.assertRaisesRegex(ValueError, "unmasking"):
            prepare(self.run, FIXTURES, self.release, self.mapping, allow_smoke=True)
        self.assertFalse(self.release.exists())

    def test_digest_and_smoke_gates(self):
        with self.assertRaisesRegex(ValueError, "smoke"):
            prepare(self.run, FIXTURES, self.release, self.mapping)
        path = self.run / "blocks/test-block/hidden-clone/D/source/service.py"
        path.write_text(path.read_text() + "\n# harmless modification\n")
        with self.assertRaisesRegex(ValueError, "digest mismatch"):
            prepare(self.run, FIXTURES, self.release, self.mapping, allow_smoke=True)


if __name__ == "__main__":
    unittest.main()
