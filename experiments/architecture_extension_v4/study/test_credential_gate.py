"""The credential check releases only a bounded, allowlisted record."""

import json
import unittest

from credential_gate import MAX_OUTPUT_TOKENS, sanitized_result


class CredentialGateRecordTests(unittest.TestCase):
    def test_success_retains_usage_but_not_arbitrary_provider_fields(self):
        raw = json.dumps({"status": "pass", "category": "completed_request",
                          "response_status": "incomplete", "input_tokens": 13,
                          "output_tokens": 64, "account": "sensitive"}).encode()
        record = sanitized_result(0, raw, 0.3)
        self.assertEqual(record["status"], "pass")
        self.assertEqual((record["input_tokens"], record["output_tokens"]), (13, 64))
        self.assertNotIn("account", json.dumps(record))

    def test_unbounded_or_untrusted_output_fails_closed(self):
        raw = json.dumps({"status": "pass", "category": "completed_request",
                          "response_status": "completed", "input_tokens": 13,
                          "output_tokens": MAX_OUTPUT_TOKENS + 1}).encode()
        self.assertEqual(sanitized_result(0, raw, 0.3)["status"], "fail")
        zero = json.dumps({"status": "pass", "category": "completed_request",
                           "response_status": "completed", "input_tokens": 0,
                           "output_tokens": 0}).encode()
        self.assertEqual(sanitized_result(0, zero, 0.3)["status"], "fail")
        self.assertEqual(sanitized_result(0, b"secret=" + b"x" * 2000, 0.3)["status"], "fail")

    def test_credit_failure_is_classified_without_provider_message(self):
        raw = json.dumps({"status": "fail", "category": "credit_exhausted",
                          "message": "sensitive account details"}).encode()
        record = sanitized_result(2, raw, 0.2)
        self.assertEqual((record["status"], record["category"]),
                         ("fail", "credit_exhausted"))
        self.assertNotIn("sensitive", json.dumps(record))


if __name__ == "__main__":
    unittest.main()
