"""Finite EAL inference check and an optional, explicitly paid two-call pilot.

The original architecture_extension_v4 freeze and results are never modified.
This programme scores the engine before making any model request. A live pilot
uses one fresh Responses API invocation per arm, each answering all cases.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from eal.aspic_compiler import compile_eal_aspic
from eal.evaluator import canonical_digest, environment_fingerprint, evaluate
from eal.parser import parse


HERE = Path(__file__).resolve().parent
MODEL = "gpt-5.4-nano"
OUTPUT_CAP = 2200
REQUEST_BYTE_CAP = 32_000
SCENARIO_LIMIT = Decimal("0.03")
# Posted Standard rate snapshot, USD per million. The 1.25 input multiplier
# and 1.10 regional multiplier are conservative scenario allowances, not a bill.
INPUT_RATE = Decimal("0.20")
OUTPUT_RATE = Decimal("1.25")
UPLIFT = Decimal("1.10")
CACHE_WRITE_UPLIFT = Decimal("1.25")
STATUSES = ("supported", "contested", "unsupported", "out_of_scope")
FILES = ("argument.eal", "cases.json", "oracles.json", "run.py")


def _json_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _write(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True,
                               ensure_ascii=False, allow_nan=False) + "\n",
                    encoding="utf-8")


def verify_freeze() -> str:
    frozen = json.loads((HERE / "freeze.json").read_text(encoding="utf-8"))
    if frozen.get("schema") != "inference-machinery-freeze/1.1" or set(frozen.get("files", {})) != set(FILES):
        raise ValueError("invalid or incomplete inference study freeze")
    for name in FILES:
        if _sha((HERE / name).read_bytes()) != frozen["files"][name]:
            raise ValueError(f"frozen inference study input changed: {name}")
    return _sha(_json_bytes(frozen))


def load_inputs() -> tuple[str, Any, list[dict[str, Any]], dict[str, dict[str, Any]]]:
    source = (HERE / "argument.eal").read_text(encoding="utf-8")
    programme = parse(source)
    manifest = json.loads((HERE / "cases.json").read_text(encoding="utf-8"))
    oracle = json.loads((HERE / "oracles.json").read_text(encoding="utf-8"))
    if manifest.get("schema") != "inference-machinery-cases/1" or oracle.get("schema") != "inference-machinery-oracles/1":
        raise ValueError("wrong case/oracle schema")
    when = datetime.fromisoformat(manifest["evaluated_at"].replace("Z", "+00:00"))
    if when.utcoffset() != timedelta(0):
        raise ValueError("evaluation time must be UTC")
    cases = manifest["cases"]
    by_id = {item["id"]: item for item in oracle["cases"]}
    ids = [item["id"] for item in cases]
    if (not ids or len(ids) != len(set(ids)) or len(by_id) != len(oracle["cases"])
            or set(ids) != set(by_id)):
        raise ValueError("case and oracle IDs must be unique and identical")
    for case in cases:
        if set(case) != {"id", "site", "observations"} or not isinstance(case["site"], str):
            raise ValueError("invalid case shape")
        if not isinstance(case["observations"], dict) or not set(case["observations"]) <= set(programme.evidence):
            raise ValueError("invalid evidence names")
        if any(type(age) is not int or age < 0 for age in case["observations"].values()):
            raise ValueError("observation age must be a nonnegative integer")
        if by_id[case["id"]]["status"] not in STATUSES:
            raise ValueError("invalid oracle status")
    return source, programme, cases, by_id


def _record(programme: Any, name: str, instant: str,
            context: dict[str, Any], case_id: str) -> dict[str, Any]:
    declaration = programme.evidence[name]
    tool = programme.tools[declaration.tool]
    acquisition = {"tool": tool.name, "tool_version": tool.version,
                   "input": declaration.input, "context": context}
    request = {"evidence_id": name, "environment": declaration.environment,
               **acquisition}
    value = {"ok": True}
    return {"evidence_id": name, "source_digest": programme.source_digest,
            "tool": tool.name, "tool_version": tool.version,
            "evidence_kind": declaration.kind, "environment": declaration.environment,
            "environment_fingerprint": environment_fingerprint(declaration.environment, context),
            "input_digest": canonical_digest(declaration.input), "input": declaration.input,
            "context": context, "status": "ok", "collected_at": instant,
            "run_id": f"synthetic-{case_id}-{name}",
            "tool_binding_digest": _sha(b"inference-machinery-v1-synthetic-fixture"),
            "request_digest": canonical_digest(request),
            "acquisition_request": acquisition,
            "acquisition_request_digest": canonical_digest(acquisition),
            "value": value, "data_digest": canonical_digest(value)}


def _one_engine(source: str, programme: Any, case: dict[str, Any], now: datetime) -> dict[str, Any]:
    context = {"site": case["site"], "case_id": case["id"]}
    records = {name: _record(programme, name,
                             (now - timedelta(seconds=age)).isoformat().replace("+00:00", "Z"),
                             context, case["id"])
               for name, age in case["observations"].items()}
    instant = now.isoformat().replace("+00:00", "Z")
    authored = evaluate(programme, records, now=instant, context=context)
    if authored.get("valid") is not True:
        raise ValueError(f"EAL evaluation invalid for {case['id']}")
    compiled = compile_eal_aspic(source, records, goal="finding",
                                 now=instant, context=context).to_dict()
    if compiled["claim_status"] != authored["claims"]["finding"]["status"]:
        raise ValueError(f"EAL and ASPIC+ disagree in {case['id']}")
    return {"case_id": case["id"], "status": compiled["claim_status"],
            "grounded_status": compiled["formal"]["grounded_status"],
            "routes": {name: item["status"] for name, item in compiled["routes"].items()},
            "objections": {name: item["status"] for name, item in authored["objections"].items()},
            "unavailable": {name: item["availability_issues"]
                            for name, item in compiled["source_map"]["evidence"].items()
                            if not item["available"]},
            "snapshot_digest": compiled["snapshot_digest"]}


RULES = (
    "Synthetic bounded finding at evaluation time. The environment requires site=bench. "
    "An observation is usable only when present, ok and no older than 60 seconds; "
    "a missing or stale observation is unavailable, not a negative finding. "
    "A usable direct_test with usable calibration supports the finding by direct_route. "
    "A usable alternate_test independently supports it by alternate_route. "
    "A usable trace_gap attacks only direct_route; a usable gap_rebuttal defeats that objection. "
    "A usable global_blocker attacks the finding and hence both routes. "
    "Return supported if at least one route survives, contested if a constructed route "
    "is defeated and none survives, unsupported if no route is constructed, "
    "or out_of_scope for a different site. Use these four status labels only."
)


def prompts(cases: list[dict[str, Any]], results: list[dict[str, Any]]) -> dict[str, str]:
    common = {"question": "Assess the bounded finding for every case, in order.",
              "rules": RULES,
              "evaluation_time": "2026-09-27T21:00:00Z",
              "cases": [{"case_id": c["id"], "site": c["site"],
                         "observations": {name: {"age_seconds": age, "ok": True}
                                          for name, age in c["observations"].items()}}
                        for c in cases]}
    raw = json.dumps(common, sort_keys=True, ensure_ascii=False)
    aid = [{"case_id": row["case_id"], "status": row["status"],
            "routes": row["routes"], "objections": row["objections"],
            "unavailable": row["unavailable"],
            "snapshot_digest": row["snapshot_digest"]} for row in results]
    return {"raw": raw,
            "eal_assisted": raw + "\nChecked EAL/2 result and trace for the identical cases:\n"
            + json.dumps(aid, sort_keys=True, ensure_ascii=False)}


def _score(answer: Any, oracle: dict[str, dict[str, Any]], case_ids: list[str]) -> dict[str, Any]:
    if (not isinstance(answer, dict) or set(answer) != {"answers"}
            or not isinstance(answer["answers"], list)):
        return {"valid": False, "reason": "invalid envelope", "correct": 0}
    rows = answer["answers"]
    if (len(rows) != len(case_ids) or
            any(not isinstance(row, dict) or set(row) != {"case_id", "status"}
                for row in rows) or
            [row["case_id"] for row in rows] != case_ids or
            any(row["status"] not in STATUSES for row in rows)):
        return {"valid": False, "reason": "missing, reordered or invalid cases", "correct": 0}
    scored = [{"case_id": row["case_id"], "status": row["status"],
               "expected": oracle[row["case_id"]]["status"],
               "correct": row["status"] == oracle[row["case_id"]]["status"]}
              for row in rows]
    return {"valid": True, "correct": sum(row["correct"] for row in scored),
            "cases": scored}


def prepare(output: Path) -> dict[str, Any]:
    freeze_digest = verify_freeze()
    source, programme, cases, oracle = load_inputs()
    output.mkdir(parents=True, exist_ok=True)
    now = datetime.fromisoformat(json.loads((HERE / "cases.json").read_text())["evaluated_at"].replace("Z", "+00:00"))
    results = [_one_engine(source, programme, case, now) for case in cases]
    question = prompts(cases, results)
    expected_ids = [case["id"] for case in cases]
    if any('"source"' in question[arm] or '"expected"' in question[arm]
           or '"reason"' in question[arm] for arm in question):
        raise ValueError("oracle field leaked into visible prompt")
    for arm, prompt in question.items():
        (output / f"prompt-{arm}.txt").write_text(prompt + "\n", encoding="utf-8")
    engine = [{**row, "expected": oracle[row["case_id"]]["status"],
               "correct": row["status"] == oracle[row["case_id"]]["status"]}
              for row in results]
    report = {"schema": "inference-machinery-result/1.1", "freeze_sha256": freeze_digest,
              "source_sha256": _sha(source.encode("utf-8")), "model": MODEL,
              "case_ids": expected_ids, "engine": engine,
              "engine_correct": sum(row["correct"] for row in engine),
              "prompt_sha256": {arm: _sha(prompt.encode("utf-8")) for arm, prompt in question.items()},
              "arms": {}, "interpretation": "offline engine result; no agent result until explicit live call"}
    _write(output / "result.json", report)
    return report


def _schema() -> dict[str, Any]:
    return {"type": "object", "properties": {"answers": {"type": "array",
            "items": {"type": "object", "properties": {"case_id": {"type": "string"},
                                                    "status": {"type": "string", "enum": list(STATUSES)}},
                      "required": ["case_id", "status"], "additionalProperties": False}}},
            "required": ["answers"], "additionalProperties": False}


def _request(prompt: str) -> tuple[dict[str, Any], int]:
    body = {"model": MODEL, "store": False, "reasoning": {"effort": "low"},
            "max_output_tokens": OUTPUT_CAP,
            "input": [{"role": "developer", "content": "Answer each synthetic engineering finding using the supplied rules. Output every case exactly once in order."},
                      {"role": "user", "content": prompt}],
            "text": {"format": {"type": "json_schema", "name": "case_statuses",
                                "strict": True, "schema": _schema()}}}
    raw = _json_bytes(body)
    if len(raw) > REQUEST_BYTE_CAP:
        raise ValueError("request exceeds predeclared byte cap")
    key = os.environ.get("CODEX_API_KEY")
    if not key:
        raise ValueError("CODEX_API_KEY must be supplied only to an explicit live run")
    request = Request("https://api.openai.com/v1/responses", data=raw,
                      headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                      method="POST")
    start = time.monotonic_ns()
    with urlopen(request, timeout=120) as response:
        result = json.load(response)
    return result, time.monotonic_ns() - start


def _text(response: dict[str, Any]) -> str:
    chunks = [part["text"] for item in response.get("output", [])
              if item.get("type") == "message" for part in item.get("content", [])
              if part.get("type") == "output_text" and isinstance(part.get("text"), str)]
    return "".join(chunks)


def _scenario(input_tokens: int, output_tokens: int) -> Decimal:
    return UPLIFT * (CACHE_WRITE_UPLIFT * INPUT_RATE * input_tokens + OUTPUT_RATE * output_tokens) / Decimal(1_000_000)


def live(output: Path) -> dict[str, Any]:
    report = prepare(output)
    prompts_by_arm = {arm: (output / f"prompt-{arm}.txt").read_text(encoding="utf-8")
                      for arm in ("raw", "eal_assisted")}
    # A byte is a conservative upper allocation for an input token here; the
    # resulting figure is only a Standard-rate scenario, not a billing ceiling.
    worst = sum((_scenario(REQUEST_BYTE_CAP, OUTPUT_CAP) for _ in prompts_by_arm), Decimal(0))
    if worst > SCENARIO_LIMIT:
        raise ValueError("the two-call conservative scenario exceeds the declared limit")
    _, _, _, oracle = load_inputs()
    used = Decimal(0)
    for arm in ("raw", "eal_assisted"):
        try:
            response, elapsed_ns = _request(prompts_by_arm[arm])
            _write(output / f"response-{arm}.json", response)
            usage = response.get("usage") or {}
            n_input, n_output = usage.get("input_tokens"), usage.get("output_tokens")
            if type(n_input) is not int or type(n_output) is not int:
                raise ValueError("missing reported input/output usage; stop")
            used += _scenario(n_input, n_output)
            try:
                answer = json.loads(_text(response)) if response.get("status") == "completed" else None
            except json.JSONDecodeError:
                answer = None
            report["arms"][arm] = {"response_id": response.get("id"),
                                   "status": response.get("status"),
                                   "returned_model": response.get("model"),
                                   "elapsed_seconds": elapsed_ns / 1e9,
                                   "usage": usage,
                                   "conditional_high_list_scenario_usd": str(_scenario(n_input, n_output)),
                                   "score": _score(answer, oracle, report["case_ids"])}
            _write(output / "result.json", report)
            if used + _scenario(REQUEST_BYTE_CAP, OUTPUT_CAP) > SCENARIO_LIMIT and arm == "raw":
                report["interpretation"] = "second arm withheld by scenario guard; unpaired pilot"
                _write(output / "result.json", report)
                break
        except (HTTPError, URLError, TimeoutError, ValueError) as exc:
            report["arms"][arm] = {"status": "error", "error_type": type(exc).__name__,
                                   "message": str(exc)[:180]}
            report["interpretation"] = "provider or usage failure; no paired comparison"
            _write(output / "result.json", report)
            break  # no automatic paid retry
    if len(report["arms"]) == 2 and all(row.get("score", {}).get("valid") for row in report["arms"].values()):
        raw, aided = (report["arms"][arm]["score"] for arm in ("raw", "eal_assisted"))
        report["paired_agent_delta_correct"] = aided["correct"] - raw["correct"]
        report["interpretation"] = "one two-session pilot on 12 purposively authored synthetic cases; no population effect"
        _write(output / "result.json", report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("prepare", "live"))
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--live", action="store_true", help="required to authorise two paid model requests")
    args = parser.parse_args()
    if args.mode == "live" and not args.live:
        parser.error("paid execution requires mode live and --live")
    if args.mode == "prepare" and args.live:
        parser.error("--live is only for mode live")
    result = live(args.output) if args.mode == "live" else prepare(args.output)
    print(json.dumps({"engine_correct": result["engine_correct"],
                      "cases": len(result["case_ids"]),
                      "arms": {name: row.get("score", {}).get("correct")
                               for name, row in result["arms"].items()},
                      "interpretation": result["interpretation"]}, sort_keys=True))
    if args.mode == "live" and "paired_agent_delta_correct" not in result:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
