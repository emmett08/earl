"""Conservative request-level list-price estimate for the v4 EAL experiment.

The returned ``list_price_usd`` is a deterministic estimate at the frozen
published Standard API rate, never a provider invoice. ``billed_usd`` stays
null pending independently retained account/project billing reconciliation.
Codex subscription-credit accounting and completed-turn aggregates are not API
requests and cannot be priced with this contract.

Expected episode record::

    {
      "schema": "architecture-v4-usage/1",
      "billing_channel": "openai_api_key",
      "model": "gpt-6-sol",
      "request_trace_complete": true,
      "expected_request_count": 1,
      "requests": [{
        "request_id": "provider-or-collector-request-id",
        "source_schema": "openai-api-input-partition/2026-09-27",
        "service_tier": "standard",
        "region": "global",
        "context_input_tokens": 42,
        "usage": {
          "input_tokens": 42, "cached_input_tokens": 10,
          "cache_write_input_tokens": 5, "output_tokens": 3,
          "reasoning_output_tokens": 1
        }
      }]
    }

``input_tokens`` contains both cached-input and cache-write tokens for this
*verified* source schema. A distinct source schema needs independent billing
validation, then an explicit new mapping. Absence is never interpreted as zero.
All monetary values are decimal strings in USD, without premature rounding.
"""

from __future__ import annotations

import argparse
from decimal import Decimal, InvalidOperation
import json
from pathlib import Path
from typing import Any


RATE_CARD = Path(__file__).with_name("rate-card.json")
USAGE_SCHEMA = "architecture-v4-usage/1"
VERIFIED_SOURCE_SCHEMA = "openai-api-input-partition/2026-09-27"
BILLABLE_FIELDS = (
    "input_tokens", "cached_input_tokens", "cache_write_input_tokens",
    "output_tokens",
)
DETAIL_FIELDS = ("reasoning_output_tokens",)
AMBIGUOUS_FIELDS = ("cache_creation_input_tokens",)


def _natural(value: Any, field: str) -> int:
    if type(value) is not int or value < 0:
        raise ValueError(f"{field} must be a non-negative integer")
    return value


def _money(value: Any, field: str) -> Decimal:
    if not isinstance(value, str):
        raise ValueError(f"{field} must be a decimal string")
    try:
        number = Decimal(value)
    except InvalidOperation as error:
        raise ValueError(f"{field} must be a decimal string") from error
    if not number.is_finite() or number < 0:
        raise ValueError(f"{field} must be a finite non-negative rate")
    return number


def _card(data: dict[str, Any]) -> dict[str, Any]:
    if data.get("schema") != "architecture-v4-rate-card/1":
        raise ValueError("unexpected rate-card schema")
    if data.get("model") != "gpt-6-sol" or data.get("billing_channel") != "openai_api_key":
        raise ValueError("rate card differs from declared model and billing channel")
    if data.get("service_tier") != "standard" or data.get("currency") != "USD":
        raise ValueError("rate card must describe Standard API rates in USD")
    _natural(data.get("denominator_tokens"), "denominator_tokens")
    if data["denominator_tokens"] == 0:
        raise ValueError("rate denominator cannot be zero")
    _natural(data.get("long_context_if_input_tokens_greater_than"), "context threshold")
    for size in ("short", "long"):
        rates = data.get("rates_usd_per_million", {}).get(size, {})
        for field in ("uncached_input_tokens", *BILLABLE_FIELDS[1:]):
            _money(rates.get(field), f"{size}.{field}")
    for region in ("global", "regional"):
        _money(data.get("region_multipliers", {}).get(region), f"region.{region}")
    if (not data.get("price_source") or not data.get("recorded_at_utc")
            or not data.get("study_effective_from_utc")
            or "provider_rate_effective_date_utc" not in data):
        raise ValueError("rate card provenance missing")
    return data


def load_card(path: Path = RATE_CARD) -> dict[str, Any]:
    """Load and validate the frozen, human-reviewable posted-rate snapshot."""
    return _card(json.loads(path.read_text(encoding="utf-8")))


def raw_field_status(usage: dict[str, Any]) -> dict[str, str]:
    """Retain absent versus observed-zero versus observed-positive usage."""
    if not isinstance(usage, dict):
        raise ValueError("usage must be an object")
    statuses: dict[str, str] = {}
    for field in (*BILLABLE_FIELDS, *DETAIL_FIELDS, *AMBIGUOUS_FIELDS):
        if field not in usage:
            statuses[field] = "missing"
        else:
            count = _natural(usage[field], field)
            statuses[field] = "reported_zero" if count == 0 else "reported_positive"
    return statuses


def _unpriced(reasons: list[str], *, requests: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    return {
        "schema": "architecture-v4-price-result/1",
        "status": "unpriced",
        "list_price_usd": None,
        "billed_usd": None,
        "reasons": reasons,
        "requests": requests or [],
    }


def price_episode(record: dict[str, Any], rate_card: dict[str, Any] | None = None) -> dict[str, Any]:
    """Price complete API requests under known Standard terms only.

    This function declines exact list-price estimation on an incomplete trace,
    unknown tier/region or unverified usage partition. It does not infer bill
    payment from public rates. Invalid numerical data, duplicate IDs or
    inconsistent parent/child token counts are errors, even if another field
    also makes the episode unpriceable.
    """
    if not isinstance(record, dict) or record.get("schema") != USAGE_SCHEMA:
        raise ValueError("unexpected usage schema")
    card = _card(rate_card) if rate_card is not None else load_card()
    reasons: list[str] = []
    if record.get("billing_channel") != card["billing_channel"]:
        reasons.append("API-key billing channel not verified; subscription credits and API rates differ")
    if record.get("model") != card["model"]:
        reasons.append("model differs from rate-card model or is unknown")
    requests = record.get("requests")
    if not isinstance(requests, list) or not requests:
        return _unpriced(reasons + ["no request-level usage; completed-turn aggregate cannot establish request pricing"])
    if record.get("request_trace_complete") is not True:
        reasons.append("request trace completeness was not independently attested")
    expected_count = record.get("expected_request_count")
    if expected_count is None:
        reasons.append("expected request count is unknown")
    else:
        _natural(expected_count, "expected_request_count")
        if expected_count != len(requests):
            reasons.append("retained requests differ from the attested request count")

    priced: list[dict[str, Any]] = []
    seen: set[str] = set()
    denominator = Decimal(card["denominator_tokens"])
    total = Decimal(0)
    for index, request in enumerate(requests):
        if not isinstance(request, dict):
            raise ValueError(f"request {index} must be an object")
        request_id = request.get("request_id")
        if not isinstance(request_id, str) or not request_id:
            reasons.append(f"request {index} has no stable request ID")
        elif request_id in seen:
            raise ValueError(f"duplicate request ID {request_id}")
        else:
            seen.add(request_id)
        usage = request.get("usage")
        if usage is None:
            usage = {}
        status = raw_field_status(usage)
        item: dict[str, Any] = {"request_id": request_id, "field_status": status,
                                "list_price_usd": None}
        priced.append(item)
        missing = [field for field in BILLABLE_FIELDS if status[field] == "missing"]
        if missing:
            reasons.append(f"request {index} missing billed token classes: {', '.join(missing)}")
        if status["cache_creation_input_tokens"] == "reported_positive":
            reasons.append(f"request {index} has an additional unmapped cache-creation token class")
        if request.get("source_schema") != VERIFIED_SOURCE_SCHEMA:
            reasons.append(f"request {index} input-token partition is unverified")
        if request.get("service_tier") != card["service_tier"]:
            reasons.append(f"request {index} service tier is unknown or outside frozen rate card")
        region = request.get("region")
        if region not in card["region_multipliers"]:
            reasons.append(f"request {index} processing region is unknown")
        context = request.get("context_input_tokens")
        if context is None:
            reasons.append(f"request {index} input context length is unknown")
        else:
            _natural(context, f"request {index} context_input_tokens")

        if not missing:
            input_tokens = usage["input_tokens"]
            cached = usage["cached_input_tokens"]
            writes = usage["cache_write_input_tokens"]
            if cached + writes > input_tokens:
                raise ValueError(f"request {index} cached read and write exceed parent input total")
            if (context is not None and request.get("source_schema") == VERIFIED_SOURCE_SCHEMA
                    and context != input_tokens):
                raise ValueError(f"request {index} context count differs from input total")
            if status["reasoning_output_tokens"] != "missing" and (
                    usage["reasoning_output_tokens"] > usage["output_tokens"]):
                raise ValueError(f"request {index} reasoning output exceeds parent output")
        if (missing or status["cache_creation_input_tokens"] == "reported_positive"
                or request.get("source_schema") != VERIFIED_SOURCE_SCHEMA
                or request.get("service_tier") != card["service_tier"]
                or region not in card["region_multipliers"] or context is None
                or not isinstance(request_id, str) or not request_id):
            continue
        kind = ("long" if context > card["long_context_if_input_tokens_greater_than"]
                else "short")
        rates = card["rates_usd_per_million"][kind]
        units = {
            "uncached_input_tokens": input_tokens - cached - writes,
            "cached_input_tokens": cached,
            "cache_write_input_tokens": writes,
            "output_tokens": usage["output_tokens"],
        }
        subtotal = sum(Decimal(count) * _money(rates[field], field)
                       for field, count in units.items())
        amount = subtotal * _money(card["region_multipliers"][region], f"region.{region}") / denominator
        item.update({"context_class": kind, "token_partition": units,
                     "list_price_usd": format(amount, "f")})
        total += amount

    if reasons:
        return _unpriced(reasons, requests=priced)
    return {
        "schema": "architecture-v4-price-result/1",
        "status": "posted_rate_estimate",
        "list_price_usd": format(total, "f"),
        "billed_usd": None,
        "reasons": ["provider invoice, discounts, tax and account credits not reconciled"],
        "rate_card_source": card["price_source"],
        "rate_card_recorded_at_utc": card["recorded_at_utc"],
        "rate_card_study_effective_from_utc": card["study_effective_from_utc"],
        "requests": priced,
    }


def scenario_from_cli_turns(usage: dict[str, Any],
                            rate_card: dict[str, Any] | None = None) -> dict[str, Any]:
    """Bound a *counterfactual list-price scenario* from CLI turn aggregates.

    The CLI does not identify API requests, their context lengths, tier,
    processing region or billed channel. The lower number assumes every
    reported token is charged at the Standard short/global API rate; the
    upper assumes Standard long/regional rates. Neither is a bound on a real
    invoice, which may use a different contract, tier, or credits.
    """
    card = _card(rate_card) if rate_card is not None else load_card()
    result: dict[str, Any] = {
        "schema": "architecture-v4-cli-rate-scenario/1",
        "status": "unavailable", "low_usd": None, "high_usd": None,
        "billed_usd": None, "assumptions": [
            "hypothetical Standard API list rates; billing channel and request context unknown",
            "low uses short/global; high uses long/regional; no discounts, credits or taxes",
        ],
        "reason": None, "rate_card_source": card["price_source"],
    }
    if not isinstance(usage, dict) or usage.get("status") != "reported":
        result["reason"] = "completed-turn usage not reported"
        return result
    totals = usage.get("totals")
    if not isinstance(totals, dict):
        result["reason"] = "token totals unavailable"
        return result
    fields = ("input_tokens", "cached_input_tokens", "output_tokens")
    if any(totals.get(field) is None for field in fields):
        result["reason"] = "one or more necessary token classes are unknown"
        return result
    values = {field: _natural(totals[field], field) for field in fields}
    raw_write = totals.get("cache_write_input_tokens")
    writes = _natural(raw_write, "cache_write_input_tokens") if raw_write is not None else None
    if values["cached_input_tokens"] + (writes or 0) > values["input_tokens"]:
        raise ValueError("CLI cache partitions exceed reported input")
    extra = totals.get("cache_creation_input_tokens")
    if extra is not None and _natural(extra, "cache_creation_input_tokens") > 0:
        result["reason"] = "additional cache creation tokens have no verified partition"
        return result
    components = {
        "uncached_input_tokens": (values["input_tokens"] - values["cached_input_tokens"] - writes)
                                 if writes is not None else None,
        "cached_input_tokens": values["cached_input_tokens"],
        "cache_write_input_tokens": writes,
        "output_tokens": values["output_tokens"],
    }
    def amount(kind: str, region: str) -> Decimal:
        rates = card["rates_usd_per_million"][kind]
        if writes is None:
            # Unknown cache-write is not zero. Assign all non-read input to
            # the cheapest eligible input class for the low scenario and the
            # dearer class for the high scenario under this rate card.
            remainder = values["input_tokens"] - values["cached_input_tokens"]
            input_rate = min(_money(rates["uncached_input_tokens"], "uncached"),
                             _money(rates["cache_write_input_tokens"], "write")) if kind == "short" else max(
                                 _money(rates["uncached_input_tokens"], "uncached"),
                                 _money(rates["cache_write_input_tokens"], "write"))
            subtotal = (Decimal(remainder) * input_rate +
                        Decimal(values["cached_input_tokens"]) * _money(rates["cached_input_tokens"], "cached") +
                        Decimal(values["output_tokens"]) * _money(rates["output_tokens"], "output"))
        else:
            subtotal = sum(Decimal(count) * _money(rates[field], field)
                           for field, count in components.items())
        return subtotal * _money(card["region_multipliers"][region], f"region.{region}") / Decimal(card["denominator_tokens"])
    result.update(status="conditional_scenario", low_usd=format(amount("short", "global"), "f"),
                  high_usd=format(amount("long", "regional"), "f"),
                  token_partition=components,
                  partition_status="complete" if writes is not None else "cache_write_unknown_bounded_under_assumed_rates")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("usage_record", type=Path)
    parser.add_argument("--rate-card", type=Path, default=RATE_CARD)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = price_episode(json.loads(args.usage_record.read_text(encoding="utf-8")),
                           load_card(args.rate_card))
    payload = json.dumps(result, sort_keys=True, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
    else:
        print(payload, end="")


if __name__ == "__main__":
    main()
