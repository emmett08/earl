"""Check provider usage accounting and failure retention for the live harness."""

import json
from pathlib import Path
import tempfile
import unittest

from workflow_ledger import extract


class WorkflowLedgerTests(unittest.TestCase):
    def record(self, kind, events):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        trace = root / "trace.jsonl"
        trace.write_text("".join(json.dumps(item) + "\n" for item in events))
        invocation = root / "invocation.json"
        invocation.write_text(json.dumps({"schema": "architecture-v3-agent-invocation/1",
                                          "agent_class": kind, "exit_code": 0}))
        return extract(trace, invocation)

    def test_codex_sums_only_completed_turns_without_double_counting_reasoning(self):
        result = self.record("codex_cli", [
            {"type": "turn.completed", "usage": {"input_tokens": 100,
              "cached_input_tokens": 20, "output_tokens": 40,
              "reasoning_output_tokens": 10}},
            {"type": "turn.completed", "usage": {"input_tokens": 50,
              "output_tokens": 20}},
        ])
        self.assertEqual(result["usage"]["totals"]["input_tokens"], 150)
        self.assertEqual(result["usage"]["totals"]["output_tokens"], 60)
        self.assertEqual(result["usage"]["totals"]["reasoning_output_tokens"], 10)
        self.assertIsNone(result["monetary_cost"])

    def test_claude_records_client_estimate_separately(self):
        result = self.record("claude_cli", [
            {"type": "result", "usage": {"input_tokens": 80,
              "cache_read_input_tokens": 100, "output_tokens": 12},
             "total_cost_usd": 0.12}])
        self.assertEqual(result["usage"]["client_estimated_cost_usd"], 0.12)
        self.assertEqual(result["usage"]["totals"]["output_tokens"], 12)
        self.assertEqual(result["usage"]["totals"]["cached_input_tokens"], 100)
        self.assertIsNone(result["monetary_cost"])

    def test_failed_invocation_with_no_usage_is_missing(self):
        result = self.record("codex_cli", [{"type": "turn.failed"}])
        self.assertEqual(result["usage"]["status"], "missing")
        self.assertEqual(result["events"], 1)

    def test_malformed_usage_fails_closed(self):
        with self.assertRaises(ValueError):
            self.record("codex_cli", [{"type": "turn.completed",
                                       "usage": {"input_tokens": -1}}])


if __name__ == "__main__":
    unittest.main()
