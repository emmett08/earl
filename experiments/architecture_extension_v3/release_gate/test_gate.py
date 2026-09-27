"""Behavioural checks for the distinct plain and real MCP decision routes."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import hashlib
from pathlib import Path
import sys
import tomllib
import unittest


HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2]))
from experiments.architecture_extension_v3.release_gate.run import run  # noqa: E402
from experiments.architecture_extension_v3.release_gate.tool import (  # noqa: E402
    CASE_IDS, collect, observe, plain_decision,
)


EXPECTED = {
    "applied_ready": "COMPLETE",
    "applied_unreconciled": "BLOCK_COMPLETION",
    "not_applied": "RETRY_SAME_KEY",
    "unknown": "BLOCK_COMPLETION",
    "unavailable": "BLOCK_COMPLETION",
    "stale_applied": "BLOCK_COMPLETION",
    "tool_error": "BLOCK_COMPLETION",
}


class GateTest(unittest.TestCase):
    def test_plain_rule_table_and_error_distinction(self) -> None:
        self.assertEqual(set(CASE_IDS), set(EXPECTED))
        for case, expected in EXPECTED.items():
            with self.subTest(case=case):
                self.assertEqual(plain_decision(case)["action"], expected)
        self.assertIn("acquisition_error", plain_decision("tool_error"))
        self.assertNotIn("acquisition_error", plain_decision("unavailable"))

    def test_observed_time_and_request_identity(self) -> None:
        now = datetime(2026, 9, 27, 12, 0, tzinfo=timezone.utc)
        fresh = observe("applied_ready", "provider", now)
        stale = observe("stale_applied", "provider", now)
        self.assertEqual(fresh["observed_at"], now.isoformat())
        self.assertEqual(stale["observed_at"], "2026-09-27T11:58:00+00:00")
        self.assertFalse(observe("stale_applied", "freshness", now)["value"]["fresh"])
        request = {"evidence_id": "provider_applied", "environment": "refund_case",
                   "tool": "refund_status", "tool_version": "1",
                   "input": {"record": "provider"},
                   "context": {"experiment": "architecture-extension-v3-release-gate",
                               "case_id": "applied_ready"}}
        self.assertEqual(collect(request)["request"], {
            key: request[key] for key in ("tool", "tool_version", "input", "context")})
        request["context"]["case_id"] = "tool_error"
        with self.assertRaisesRegex(ValueError, "acquisition failure"):
            collect(request)

    def test_pins_cover_tool_and_distinct_sources(self) -> None:
        config = tomllib.loads((HERE / "eal-tools.toml").read_text())
        pins = config["tools"]["refund_status"]["pinned_files"]
        self.assertEqual(len(pins), 1 + 2 * len(CASE_IDS))
        for pin in pins:
            path = HERE.parents[2] / pin["path"]
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), pin["sha256"])

    def test_mcp_formal_decision_and_defeat(self) -> None:
        report = asyncio.run(run())
        self.assertTrue(report["all_agree"])
        self.assertEqual({item["case_id"]: item["eal_action"] for item in report["cases"]}, EXPECTED)
        cases = {item["case_id"]: item for item in report["cases"]}
        self.assertEqual(cases["applied_ready"]["claim_status"]["completion_safe"]["grounded_label"],
                         "accepted")
        self.assertEqual(cases["applied_unreconciled"]["candidate_aspic_status"], "rejected")
        self.assertTrue(any(item["kind"] == "undercut"
                            for item in cases["applied_unreconciled"]["aspic_defeats"]))
        self.assertEqual(cases["stale_applied"]["evidence_status"]["provider_applied"], "unavailable")
        self.assertTrue(cases["tool_error"]["collection_errors"])
        self.assertEqual(cases["tool_error"]["claim_status"]["completion_safe"]["status"],
                         "unsupported")


if __name__ == "__main__":
    unittest.main()
