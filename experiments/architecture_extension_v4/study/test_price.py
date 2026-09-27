"""Adversarial checks of v4 request-level pricing and missingness semantics."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import unittest


HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("architecture_v4_price", HERE / "price.py")
assert spec and spec.loader
price = importlib.util.module_from_spec(spec)
spec.loader.exec_module(price)


def episode(**changes):
    result = {
        "schema": "architecture-v4-usage/1",
        "billing_channel": "openai_api_key",
        "model": "gpt-6-sol",
        "request_trace_complete": True,
        "expected_request_count": 1,
        "requests": [{
            "request_id": "request-1",
            "source_schema": price.VERIFIED_SOURCE_SCHEMA,
            "service_tier": "standard",
            "region": "global",
            "context_input_tokens": 1000,
            "usage": {
                "input_tokens": 1000,
                "cached_input_tokens": 200,
                "cache_write_input_tokens": 100,
                "output_tokens": 100,
                "reasoning_output_tokens": 30,
            },
        }],
    }
    result.update(changes)
    return result


class PriceContractTests(unittest.TestCase):
    def test_short_request_partitions_parent_totals(self):
        result = price.price_episode(episode())
        self.assertEqual(result["status"], "posted_rate_estimate")
        self.assertEqual(result["list_price_usd"], "0.00269")
        self.assertEqual(result["requests"][0]["token_partition"], {
            "uncached_input_tokens": 700,
            "cached_input_tokens": 200,
            "cache_write_input_tokens": 100,
            "output_tokens": 100,
        })
        self.assertIsNone(result["billed_usd"])

    def test_context_cutoff_is_strictly_greater_and_per_request(self):
        records = episode()
        first = records["requests"][0]
        first.update(request_id="request-1", context_input_tokens=272000)
        first["usage"] = {
            "input_tokens": 272000, "cached_input_tokens": 72000,
            "cache_write_input_tokens": 20000, "output_tokens": 1000,
        }
        second = json.loads(json.dumps(first))
        second["request_id"] = "request-2"
        second["context_input_tokens"] = 272001
        second["usage"]["input_tokens"] = 272001
        records["requests"].append(second)
        records["expected_request_count"] = 2
        result = price.price_episode(records)
        self.assertEqual([r["context_class"] for r in result["requests"]], ["short", "long"])
        self.assertEqual([r["list_price_usd"] for r in result["requests"]],
                         ["0.4344", "0.863804"])
        self.assertEqual(result["list_price_usd"], "1.298204")

    def test_missing_field_is_not_observed_zero(self):
        record = episode()
        del record["requests"][0]["usage"]["cache_write_input_tokens"]
        result = price.price_episode(record)
        self.assertIsNone(result["list_price_usd"])
        self.assertEqual(result["requests"][0]["field_status"]["cache_write_input_tokens"], "missing")
        record["requests"][0]["usage"]["cache_write_input_tokens"] = 0
        record["requests"][0]["usage"]["reasoning_output_tokens"] = 0
        priced = price.price_episode(record)
        self.assertEqual(priced["requests"][0]["field_status"]["cache_write_input_tokens"],
                         "reported_zero")
        self.assertEqual(priced["requests"][0]["field_status"]["reasoning_output_tokens"],
                         "reported_zero")
        self.assertEqual(priced["status"], "posted_rate_estimate")

    def test_turn_aggregate_and_subscription_credit_route_are_unpriced(self):
        aggregate = episode(requests=[], turn_aggregate={"input_tokens": 200000,
                                                       "cache_write_input_tokens": 20000})
        self.assertIsNone(price.price_episode(aggregate)["list_price_usd"])
        credit = episode(billing_channel="codex_subscription_credits")
        self.assertIsNone(price.price_episode(credit)["list_price_usd"])
        self.assertIn("subscription credits", price.price_episode(credit)["reasons"][0])

    def test_unknown_tier_region_context_or_partition_declines_price(self):
        for key, value in (("service_tier", None), ("service_tier", "fast"),
                           ("region", None), ("region", "mars"),
                           ("context_input_tokens", None), ("source_schema", "codex-turn/1")):
            with self.subTest(key=key, value=value):
                record = episode()
                record["requests"][0][key] = value
                result = price.price_episode(record)
                self.assertEqual(result["status"], "unpriced")
                self.assertIsNone(result["list_price_usd"])

    def test_regional_uplift_is_separate_from_tier(self):
        record = episode()
        record["requests"][0]["region"] = "regional"
        self.assertEqual(price.price_episode(record)["list_price_usd"], "0.002959")

    def test_corrupt_counts_and_duplicate_request_id_fail_closed(self):
        mutations = [
            ("input_tokens", -1, "non-negative"),
            ("cached_input_tokens", 1001, "exceed parent"),
            ("cache_write_input_tokens", 801, "exceed parent"),
            ("output_tokens", True, "non-negative"),
            ("reasoning_output_tokens", 101, "exceeds parent output"),
            ("cache_creation_input_tokens", -4, "non-negative"),
        ]
        for key, value, expected in mutations:
            with self.subTest(key=key):
                record = episode()
                record["requests"][0]["usage"][key] = value
                with self.assertRaisesRegex(ValueError, expected):
                    price.price_episode(record)
        record = episode()
        record["requests"].append(json.loads(json.dumps(record["requests"][0])))
        with self.assertRaisesRegex(ValueError, "duplicate request ID"):
            price.price_episode(record)
        record = episode()
        record["requests"][0]["usage"]["cache_creation_input_tokens"] = 7
        self.assertIsNone(price.price_episode(record)["list_price_usd"])

    def test_context_must_match_verified_input_and_full_trace_needed(self):
        record = episode()
        record["requests"][0]["context_input_tokens"] = 1001
        with self.assertRaisesRegex(ValueError, "context count differs"):
            price.price_episode(record)
        record = episode()
        record["requests"].append({"request_id": "request-2", "usage": {"input_tokens": 0}})
        result = price.price_episode(record)
        self.assertEqual(result["status"], "unpriced")
        self.assertIsNone(result["list_price_usd"])
        record = episode(request_trace_complete=False)
        self.assertIsNone(price.price_episode(record)["list_price_usd"])
        record = episode(expected_request_count=2)
        self.assertIsNone(price.price_episode(record)["list_price_usd"])

    def test_rates_and_provenance_are_frozen(self):
        card = price.load_card()
        self.assertEqual(card["recorded_at_utc"], "2026-09-27")
        self.assertEqual(card["rates_usd_per_million"]["long"]["output_tokens"], "15.00")
        tampered = json.loads(json.dumps(card))
        tampered["rates_usd_per_million"]["short"]["output_tokens"] = None
        with self.assertRaisesRegex(ValueError, "decimal string"):
            price.price_episode(episode(), tampered)


if __name__ == "__main__":
    unittest.main()
