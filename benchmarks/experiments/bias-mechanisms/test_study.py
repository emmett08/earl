"""Offline adversarial checks; no network or paid model calls."""

from __future__ import annotations

import json
import os
import fcntl
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import analyse  # noqa: E402
import run  # noqa: E402


def answer_for(case: dict) -> dict:
    gold = case["gold"]
    return {
        "status": gold["status"], "mechanism_id": gold["mechanism_id"],
        "evidence_ids": {role: gold["required_roles"].get(role, []) for role in run.ROLES},
        "rival_id": gold["rival_id"], "defeater_id": gold["defeater_id"],
        "defect_id": gold["defect_id"], "correction_id": gold["correction_id"],
        "confidence": "moderate", "rationale": "This is a synthetic conditional assessment.",
    }


def provider_response(answer: dict, model: str) -> dict:
    return {
        "id": "resp_synthetic_test", "status": "completed", "model": model,
        "output": [{"type": "message", "content": [{"type": "output_text",
                    "text": json.dumps(answer)}]}],
        "usage": {"input_tokens": 200, "output_tokens": 90,
                  "input_tokens_details": {"cached_tokens": 0},
                  "output_tokens_details": {"reasoning_tokens": 0}},
    }


class StudyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cases = run.load_cases()

    def test_cases_have_discriminating_four_class_gold(self):
        self.assertEqual(len(self.cases), 48)
        self.assertEqual(len({case["family"] for case in self.cases}), 12)
        self.assertEqual({case["missing_link"] for case in self.cases
                          if case["variant"] == "missing_link"},
                         {"exposure", "opportunity", "uptake"})
        for case in self.cases:
            self.assertEqual(case["eal"].count("objection alternative_challenge"), 1)
            self.assertIn("evidence record_e0;", case["eal"])
            if case["variant"] == "process":
                self.assertEqual(case["gold"]["status"], "COMPARATIVELY-SUPPORTED")
                self.assertEqual(set(case["role_evidence"]), set(run.ROLES))
            if case["missing_link"] == "uptake":
                self.assertEqual(case["gold"]["status"], "REJECTED")
            if case["missing_link"] in ("exposure", "opportunity"):
                self.assertEqual(case["gold"]["status"], "NOT-APPLICABLE")
            if case["missing_link"] == "exposure":
                self.assertEqual({r["id"] for r in case["records"]},
                                 {"E0", "E1", "E2", "E3", "E4"})
            public = run.request_body(case, run.MODELS["nano"], "direct",
                                      sorted({c["mechanism"] for c in self.cases}), 1200)
            payload = json.dumps(public)
            self.assertNotIn("gold", payload)
            self.assertNotIn(case["id"], payload)
            self.assertNotIn(case["family"] + "_" + case["variant"], payload)
            self.assertIn(run.opaque_episode_id(case["id"]), payload)
            self.assertIn("bias_hypothesis", payload)
        self.assertEqual(len({run.opaque_episode_id(c["id"]) for c in self.cases}), 48)
        for group, gold_key, prefix in (("defects", "defect_id", "d"),
                                        ("corrections", "correction_id", "a")):
            self.assertEqual({c["gold"][gold_key] for c in self.cases},
                             {prefix + str(i) for i in range(1, 4)})
            for case in self.cases:
                self.assertEqual({o["id"] for o in case["options"][group]},
                                 {prefix + str(i) for i in range(1, 4)})
        self.assertIn("grammar/EAL.g4", run.validate_eal_sources(self.cases))

    def test_independent_synthesis_requires_shared_citations(self):
        case = self.cases[0]
        mechanism = answer_for(case)
        rival = answer_for(case)
        mechanism["evidence_ids"]["uptake"] = []
        rival["evidence_ids"]["contrast"] = []
        combined = analyse._synthesise(mechanism, rival)
        self.assertEqual(combined["status"], "COMPARATIVELY-SUPPORTED")
        self.assertEqual(combined["evidence_ids"]["uptake"], [])
        self.assertEqual(combined["evidence_ids"]["contrast"], [])
        gated, reasons = run.gate_answer(combined, case)
        self.assertEqual(gated["status"], "UNDECIDED")
        self.assertIn("missing_supported_role:uptake", reasons)
        self.assertIn("missing_supported_role:contrast", reasons)

    def test_synthesis_does_not_hide_analyst_harm(self):
        case = next(c for c in self.cases if c["variant"] == "rival")
        erroneous = answer_for(case)
        erroneous["status"] = "COMPARATIVELY-SUPPORTED"
        erroneous["correction_id"] = "a2"
        correct = answer_for(case)
        result = {
            f"{case['id']}__nano__independent__{stage}": {
                "result": "ok", "answer": answer, "cost_usd": 0.0,
                "latency_seconds": 0.0,
            }
            for stage, answer in (("mechanism", erroneous), ("rival", correct))
        }
        row = analyse._row(case, "nano", "independent", result)
        self.assertEqual(row["raw_status"], "UNDECIDED")
        self.assertEqual(row["analyst_strong_false_attribution"], 1)
        self.assertEqual(row["analyst_wrong_correction"], 1)
        self.assertFalse(row["wrong_correction"])

    def test_primary_score_uses_raw_answer_not_private_gate(self):
        case = self.cases[0]
        raw = answer_for(case)
        result = {f"{case['id']}__nano__direct__direct": {
            "result": "ok", "answer": raw, "cost_usd": 0.0,
            "latency_seconds": 0.0,
        }}
        abstaining = {**raw, "status": "UNDECIDED"}
        with patch.object(run, "gate_answer", return_value=(abstaining, ["private_gate"])):
            row = analyse._row(case, "nano", "direct", result)
        self.assertEqual(row["raw_status"], "COMPARATIVELY-SUPPORTED")
        self.assertEqual(row["published_status"], "UNDECIDED")
        self.assertTrue(row["fully_warranted"])
        self.assertFalse(row["gated_fully_warranted"])

    def test_freeze_pilot_full_and_tampering(self):
        with tempfile.TemporaryDirectory() as tmp:
            pilot_path, full_path = Path(tmp) / "pilot.json", Path(tmp) / "full.json"
            pilot = run.freeze(pilot_path, families=2, model_names=list(run.MODELS),
                               seed=240924, max_usd=5, max_output_tokens=1200)
            full = run.freeze(full_path, families=12, model_names=list(run.MODELS),
                              seed=240924, max_usd=25, max_output_tokens=1200)
            self.assertEqual((len(pilot["calls"]), len(full["calls"])), (72, 432))
            for material_name in ("analyse.py", "PROTOCOL.md", "AMENDMENT-0.1.1.md"):
                self.assertEqual(pilot["materials"][material_name],
                                 run.digest((run.HERE / material_name).read_bytes()))
            full_index = {call["id"]: call for call in full["calls"]}
            for call in pilot["calls"]:
                self.assertEqual(call["request_sha256"], full_index[call["id"]]["request_sha256"])
            tampered = run.read_json(full_path)
            tampered["calls"][0]["request"]["input"][0]["content"] = "Altered prompt"
            tampered["calls"][0]["request_sha256"] = run.digest(tampered["calls"][0]["request"])
            tampered["freeze_sha256"] = run.digest({k: v for k, v in tampered.items()
                                                     if k != "freeze_sha256"})
            full_path.write_text(json.dumps(tampered), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "deterministic regeneration"):
                run.load_freeze(full_path)
            tampered = run.read_json(pilot_path)
            tampered["materials"]["analyse.py"] = "0" * 64
            tampered["freeze_sha256"] = run.digest({k: v for k, v in tampered.items()
                                                     if k != "freeze_sha256"})
            pilot_path.write_text(json.dumps(tampered), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "materials changed"):
                run.load_freeze(pilot_path)

    def test_response_refusal_incomplete_and_duplicate_keys(self):
        good = provider_response(answer_for(self.cases[0]), run.MODELS["nano"]["id"])
        self.assertIsNotNone(run.parse_response(good)[0])
        self.assertEqual(run.parse_response({"status": "incomplete", "output": []})[1],
                         "non_completed:incomplete")
        refused = {**good, "output": [{"type": "message", "content": [{"type": "refusal"}]}]}
        self.assertEqual(run.parse_response(refused)[1], "refusal")
        duplicate = {**good, "output": [{"type": "message", "content": [{
            "type": "output_text", "text": '{"status":"REJECTED","status":"UNDECIDED"}'}]}]}
        self.assertEqual(run.parse_response(duplicate)[1], "invalid_json")

    def test_role_gate_rejects_unsupported_strong_attribution(self):
        negative = next(case for case in self.cases if case["variant"] == "rival")
        bad = answer_for(negative)
        bad["status"] = "COMPARATIVELY-SUPPORTED"
        bad["evidence_ids"] = {role: [negative["records"][0]["id"]] for role in run.ROLES}
        gated, reasons = run.gate_answer(bad, negative)
        self.assertEqual(gated["status"], "UNDECIDED")
        self.assertTrue(any("missing_supported_role" in error for error in reasons))
        positive = self.cases[0]
        self.assertEqual(run.gate_answer(answer_for(positive), positive)[1], [])

    def test_ledger_no_retry_raw_retention_and_analysis(self):
        with tempfile.TemporaryDirectory() as tmp:
            path, ledger = Path(tmp) / "pilot.json", Path(tmp) / "pilot.jsonl"
            frozen = run.freeze(path, families=1, model_names=["nano"], seed=7,
                                max_usd=5, max_output_tokens=1200)
            cases = {run.opaque_episode_id(case["id"]): case for case in self.cases}
            fake_key = "sk-proj-unit-test-secret-string"
            def post(body, key):
                self.assertEqual(key, fake_key)
                episode = json.loads(body["input"][1]["content"].split("Episode: ", 1)[1])
                answer = answer_for(cases[episode["episode_id"]])
                answer["rationale"] = fake_key
                return provider_response(answer, body["model"]), "req_local"
            with patch.dict(os.environ, {"OPENAI_API_KEY": fake_key}), \
                 patch.object(run, "preflight"), patch.object(run, "_post_response", side_effect=post) as calls:
                result = run.execute(path, ledger)
                self.assertEqual(result["attempted"], 12)
                run.execute(path, ledger)
                self.assertEqual(calls.call_count, 12)
            self.assertNotIn(fake_key, ledger.read_text(encoding="utf-8"))
            events = run.ledger_events(ledger)
            self.assertEqual(len(events), 24)
            self.assertEqual(sum("provider_response" in event for event in events), 12)
            report = analyse.analyse(path, ledger)
            self.assertEqual(report["state"], "complete")
            self.assertEqual(report["calls_terminal"], 12)
            self.assertEqual(report["summary"]["nano/direct"]["assignments"], 4)
            self.assertEqual(report["summary"]["nano/independent"]["assignments"], 4)
            self.assertEqual(report["never_attribute_baseline"]["positive_supported_recall"], 0)

    def test_pending_call_blocks_resumption_and_empty_analysis_has_no_estimate(self):
        with tempfile.TemporaryDirectory() as tmp:
            path, ledger = Path(tmp) / "pilot.json", Path(tmp) / "pilot.jsonl"
            frozen = run.freeze(path, families=1, model_names=["nano"], seed=1,
                                max_usd=5, max_output_tokens=1200)
            report = analyse.analyse(path, ledger)
            self.assertEqual(report["state"], "unrun")
            self.assertIsNone(report["paired"])
            call = frozen["calls"][0]
            run.append_event(ledger, {"kind": "pending", "call_id": call["id"],
                                      "request_sha256": call["request_sha256"],
                                      "reserved_usd": call["reserved_usd"], "utc": run.utc_now()}, "0" * 64)
            with patch.object(run, "preflight"):
                with self.assertRaisesRegex(RuntimeError, "Unresolved pending"):
                    run.execute(path, ledger)
            self.assertEqual(analyse.analyse(path, ledger)["state"], "interrupted")

    def test_second_executor_cannot_enter_locked_ledger(self):
        with tempfile.TemporaryDirectory() as tmp:
            ledger = Path(tmp) / "pilot.jsonl"
            lock = ledger.with_name(ledger.name + ".lock")
            fd = os.open(lock, os.O_CREAT | os.O_RDWR, 0o600)
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                with self.assertRaisesRegex(RuntimeError, "locked by another"):
                    run.execute(Path(tmp) / "unused.json", ledger)
            finally:
                fcntl.flock(fd, fcntl.LOCK_UN)
                os.close(fd)

    def test_full_executor_cannot_read_active_pilot_ledger(self):
        with tempfile.TemporaryDirectory() as tmp:
            pilot, full = Path(tmp) / "pilot.jsonl", Path(tmp) / "full.jsonl"
            lock = pilot.with_name(pilot.name + ".lock")
            fd = os.open(lock, os.O_CREAT | os.O_RDWR, 0o600)
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                with self.assertRaisesRegex(RuntimeError, "locked by another"):
                    run.execute(Path(tmp) / "unused.json", full, prior_path=pilot)
            finally:
                fcntl.flock(fd, fcntl.LOCK_UN)
                os.close(fd)

    def test_full_schedule_requires_finished_pilot_before_preflight(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            full = root / "full.json"
            run.freeze(full, families=12, model_names=["nano"], seed=240924,
                       max_usd=25, max_output_tokens=1200)
            with patch.object(run, "preflight") as preflight:
                with self.assertRaisesRegex(ValueError, "completed two-family pilot"):
                    run.execute(full, root / "full.jsonl")
                with self.assertRaisesRegex(RuntimeError, "exactly the complete"):
                    run.execute(full, root / "full.jsonl", root / "pilot.jsonl")
                preflight.assert_not_called()

    def test_missing_usage_is_retained_and_stops_before_second_charge(self):
        with tempfile.TemporaryDirectory() as tmp:
            path, ledger = Path(tmp) / "pilot.json", Path(tmp) / "pilot.jsonl"
            frozen = run.freeze(path, families=1, model_names=["nano"], seed=2,
                                max_usd=5, max_output_tokens=1200)
            first = frozen["calls"][0]
            case = next(c for c in self.cases if c["id"] == first["case_id"])
            response = provider_response(answer_for(case), run.MODELS["nano"]["id"])
            response.pop("usage")
            with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-proj-unit-test-secret-string"}), \
                 patch.object(run, "preflight"), \
                 patch.object(run, "_post_response", return_value=(response, "req_local")) as post:
                with self.assertRaisesRegex(RuntimeError, "validation failed"):
                    run.execute(path, ledger)
                self.assertEqual(post.call_count, 1)
                with self.assertRaisesRegex(RuntimeError, "Invalid or failed prior call"):
                    run.execute(path, ledger)
                self.assertEqual(post.call_count, 1)
            events = run.ledger_events(ledger)
            self.assertEqual(events[-1]["result"], "invalid")
            self.assertIn("missing_usage", events[-1]["validation"])


if __name__ == "__main__":
    unittest.main()
