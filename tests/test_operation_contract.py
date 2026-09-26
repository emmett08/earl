"""Provider schemas and replayed visible failures from run 36231666497."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import httpx
import pytest
from jsonschema import Draft202012Validator

from eal.http_provider import (native_operation_schema, restore_optional_fields,
                               strict_operation_schema)
from eal.providers import ProviderError
from eal.responses_provider import ResponsesProvider
from experiments.api_load_test.materials import finish_schema


FINISH = {"operation": "finish", "input_schema": finish_schema()}
FIXTURE = json.loads((Path(__file__).parent / "fixtures" /
                      "run-36231666497-provider.json").read_text())


def test_strict_transport_preserves_host_optional_field_semantics():
    native = strict_operation_schema(FINISH, native=True)
    assert set(native["required"]) == set(native["properties"])
    assert native["additionalProperties"] is False
    assert native["properties"]["scope"]["anyOf"][0]["additionalProperties"] is False
    assert "uniqueItems" not in native["properties"]["failed_checks"]
    transport = {"report_id": None, "scope": None, "explanation": None,
                 "status": "unavailable", "failed_checks": ["freshness"],
                 "unknown_checks": [], "metrics": {"request_count": 100, "p95_ms": 6.5,
                                                     "error_rate_percent": 0.0}}
    assert Draft202012Validator(native).is_valid(transport)
    arguments = restore_optional_fields(transport, native_operation_schema(FINISH))
    assert set(arguments) == {"status", "failed_checks", "unknown_checks", "metrics"}
    assert Draft202012Validator(finish_schema()).is_valid({"operation": "finish", **arguments})


def test_strict_transport_rejects_open_or_ambiguous_optional_schema():
    for schema in (
        {"type": "object", "properties": {"operation": {"const": "x"}},
         "required": ["operation"]},
        {"type": "object", "additionalProperties": False,
         "properties": {"operation": {"const": "x"}, "value": {"type": ["string", "null"]}},
         "required": ["operation"]},
    ):
        with pytest.raises(ValueError):
            strict_operation_schema({"operation": "x", "input_schema": schema}, native=True)


def test_strict_transport_restores_optional_fields_inside_arrays():
    entry = {"operation": "record", "input_schema": {"type": "object", "additionalProperties": False,
        "properties": {"operation": {"const": "record"}, "rows": {"type": "array", "items": {
            "type": "object", "additionalProperties": False,
            "properties": {"value": {"type": "integer"}, "comment": {"type": "string"}},
            "required": ["value"]}}}, "required": ["operation", "rows"]}}
    transport = {"rows": [{"value": 1, "comment": None}, {"value": 2, "comment": "observed"}]}
    assert Draft202012Validator(strict_operation_schema(entry, native=True)).is_valid(transport)
    assert restore_optional_fields(transport, native_operation_schema(entry)) == {
        "rows": [{"value": 1}, {"value": 2, "comment": "observed"}]}


@pytest.mark.parametrize("record", FIXTURE["records"], ids=lambda record:
                         f"{record['trial_id']}-{record['turn']}")
def test_retained_run_provider_failure_never_issues_an_operation(record):
    response = record["response"]
    provider = ResponsesProvider(model=response["model"], api_key_env=None,
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json={
            "model": response["model"], "status": response["status"],
            "incomplete_details": response["incomplete_details"],
            "output": response["output"], "usage": response["usage"]})))
    with pytest.raises(ProviderError) as failure:
        asyncio.run(provider.complete_request([], 4096, operations=[{
            "operation": "assess_load_test", "input_schema": {
                "type": "object", "properties": {"operation": {"const": "assess_load_test"},
                                                   "report_id": {"type": "string"}},
                "required": ["operation", "report_id"], "additionalProperties": False}}]))
    assert failure.value.category == record["expected_category"]
    assert failure.value.response.text == ""
    assert provider._replay_items == {}


def test_fixture_retains_every_recorded_boundary_failure_without_private_reasoning():
    assert FIXTURE["source_run"] == 36231666497
    assert sum(row["expected_category"] == "multiple_messages" for row in FIXTURE["records"]) == 59
    assert sum(row["expected_category"] == "output_truncated" for row in FIXTURE["records"]) == 10
    assert all(item["type"] != "reasoning" for row in FIXTURE["records"]
               for item in row["response"]["output"])
