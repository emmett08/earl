"""Offline checks for the two follow-on model cohorts; no provider calls."""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import followup as study  # noqa: E402


def answer_for(case: dict) -> dict:
    gold = case["gold"]
    return {"status": gold["status"], "mechanism_id": gold["mechanism_id"],
            "evidence_ids": {role: gold["required_roles"].get(role, [])
                             for role in study.baseline.ROLES},
            "rival_id": gold["rival_id"], "defeater_id": gold["defeater_id"],
            "defect_id": gold["defect_id"], "correction_id": gold["correction_id"],
            "confidence": "moderate", "rationale": "Conditional synthetic assessment."}


class FollowupTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cases = study.baseline.load_cases()

    def test_graph_is_derived_and_rejects_semantic_mutation(self):
        for case in self.cases:
            graph = study.packet(case, "derived_json")["argument"]
            study.checked_graph(case["eal"], graph)
            self.assertEqual(graph["language"], "EAL/2")
            self.assertEqual(set(graph["declarations"]["arguments"]),
                             {"proposed_route", "hypothesis_route"})
        graph = study.packet(self.cases[0], "derived_json")["argument"]
        graph["declarations"]["claims"]["bias_hypothesis"]["statement"] = "Changed claim"
        with self.assertRaisesRegex(ValueError, "differs"):
            study.checked_graph(self.cases[0]["eal"], graph)

    def test_common_request_and_equal_allocated_call_matrix(self):
        case = self.cases[0]
        model = study.baseline.MODELS["luna"]
        mechanisms = sorted({c["mechanism"] for c in self.cases})
        eal = study.request(case, "eal2", model, "direct_1", mechanisms, 1200)
        graph = study.request(case, "derived_json", model, "direct_1", mechanisms, 1200)
        self.assertEqual(eal["input"][0], graph["input"][0])
        self.assertEqual(eal["text"], graph["text"])
        self.assertEqual(eal["model"], graph["model"])
        self.assertEqual(eal["max_output_tokens"], graph["max_output_tokens"])
        self.assertEqual(eal["input"][1]["content"].split("Episode: ")[0],
                         graph["input"][1]["content"].split("Episode: ")[0])
        for body in (eal, graph):
            self.assertNotIn(case["id"], json.dumps(body))
            self.assertNotIn("gold", json.dumps(body))
        cases, calls = study.planned(2, ["luna", "sol"], 240925, 1200)
        self.assertEqual((len(cases), len(calls)), (8, 128))
        by_cell = {}
        for call in calls:
            key = (call["case_id"], call["model_name"], call["representation"],
                   call["topology"])
            by_cell.setdefault(key, []).append(call)
        self.assertEqual({len(group) for group in by_cell.values()}, {2})
        self.assertEqual({c["request"]["max_output_tokens"] for c in calls}, {1200})

    def test_freeze_reloads_and_detects_tampering(self):
        with tempfile.TemporaryDirectory() as tmp:
            path, full_path = Path(tmp) / "pilot.json", Path(tmp) / "full.json"
            frozen = study.freeze(path, families=2, names=("luna",), max_usd=5)
            full = study.freeze(full_path, families=12, names=("luna",), max_usd=20)
            self.assertEqual(len(study.load_freeze(path)["calls"]), 64)
            self.assertEqual(len(study.load_freeze(full_path)["calls"]), 384)
            self.assertLess(sum(c["reserved_usd"] for c in frozen["calls"]), 5)
            index = {c["id"]: c for c in full["calls"]}
            self.assertTrue(all(c["request_sha256"] == index[c["id"]]["request_sha256"]
                                for c in frozen["calls"]))
            data = study.baseline.read_json(path)
            data["calls"][0]["request"]["input"][0]["content"] = "Tampered"
            data["calls"][0]["request_sha256"] = study.baseline.digest(data["calls"][0]["request"])
            data["freeze_sha256"] = study.baseline.digest({k: v for k, v in data.items()
                                                             if k != "freeze_sha256"})
            path.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "deterministic regeneration"):
                study.load_freeze(path)

    def test_mock_run_and_raw_analysis(self):
        with tempfile.TemporaryDirectory() as tmp:
            freeze = Path(tmp) / "one.json"
            ledger = Path(tmp) / "one.jsonl"
            data = study.freeze(freeze, families=1, names=("luna",), max_usd=5)
            cases = {study.baseline.opaque_episode_id(c["id"]): c for c in self.cases}

            def post(body, key):
                self.assertEqual(key, "fake-test-token")
                supplied = json.loads(body["input"][1]["content"].split("Episode: ", 1)[1])
                answer = answer_for(cases[supplied["episode_id"]])
                return ({"id": "synthetic_response", "status": "completed",
                         "model": body["model"],
                         "output": [{"type": "message", "content": [{"type": "output_text",
                                    "text": json.dumps(answer)}]}],
                         "usage": {"input_tokens": 100, "output_tokens": 50}}, "req_mock")

            with patch.dict(os.environ, {"OPENAI_API_KEY": "fake-test-token"}), \
                 patch.object(study.baseline, "preflight"), \
                 patch.object(study.baseline, "_post_response", side_effect=post) as sent:
                result = study.execute(freeze, ledger)
                self.assertEqual(result["valid"], 32)
                study.execute(freeze, ledger)
                self.assertEqual(sent.call_count, 32)
            report = study.analyse(freeze, ledger)
            self.assertEqual(report["state"], "complete")
            self.assertEqual(report["calls_planned"], 32)
            self.assertEqual(report["calls_valid"], 32)
            self.assertEqual(report["contrasts"]["luna/eal2/topology"], 0)
            self.assertEqual(report["contrasts"]["luna/repeat_direct/json_minus_eal"], 0)
            self.assertEqual(report["summary"]["luna/eal2/repeat_direct"]["input_tokens"], 800)
            self.assertNotIn("fake-test-token", ledger.read_text(encoding="utf-8"))
            self.assertEqual(len(data["calls"]), 32)

    def test_pending_blocks_retry_and_full_requires_complete_pilot(self):
        with tempfile.TemporaryDirectory() as tmp:
            pilot, full = Path(tmp) / "pilot.json", Path(tmp) / "full.json"
            ledger = Path(tmp) / "pilot.jsonl"
            p = study.freeze(pilot, families=2, names=("luna",), max_usd=5)
            study.freeze(full, families=12, names=("luna",), max_usd=20)
            with self.assertRaisesRegex(ValueError, "complete two-family pilot"):
                study.execute(full, Path(tmp) / "full.jsonl")
            call = p["calls"][0]
            study._append(ledger, {"kind": "pending", "call_id": call["id"],
                           "request_sha256": call["request_sha256"],
                           "reserved_usd": call["reserved_usd"]}, "0" * 64)
            self.assertEqual(study.analyse(pilot, ledger)["state"], "interrupted")
            with self.assertRaisesRegex(RuntimeError, "Unresolved pending"):
                study.execute(pilot, ledger)


if __name__ == "__main__":
    unittest.main()
