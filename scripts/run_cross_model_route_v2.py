#!/usr/bin/env python3
"""Versioned developmental route experiment with an unambiguous second turn.

The original runner and its two paid freezes are immutable. This wrapper
reuses its bounded acquisition and ledger logic in a dedicated process, pins
this new source in the freeze, and changes only the routed final-answer system
instruction. It is not safe to run both versions concurrently in one Python
interpreter because the legacy function is temporarily patched during a run.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from typing import Any

import run_cross_model_campaign as legacy


ROOT = Path(__file__).resolve().parents[1]
ROUTING_REVISION = "skill-route-second-turn/2"
FREEZE_SCHEMA = "eal2-cross-model-route-v2-freeze/1"
FINAL_SYSTEM = (
    "The host validated the earlier assessment request. Assess only the named claim using the "
    "host result. Reply with exactly one JSON object with two fields: claims (the claim ID mapped "
    "to supported, contested, unsupported, or out_of_scope) and explanation (one concise sentence). "
    "Use the host status as authoritative and explain only what the checked packet warrants. "
    "Do not return another operation request."
)
_ORIGINAL_PREPARE = legacy.prepare
_ORIGINAL_SECOND = legacy._route_second_messages
_ORIGINAL_VERIFY = legacy.verify_freeze


def second_messages(case: dict, request_text: str, packet: dict) -> list[dict[str, str]]:
    if case["arm"] != "skill_route" or packet.get("claim") != case["claim"]:
        raise ValueError("Versioned route final answer needs the selected claim")
    return [{"role": "system", "content": FINAL_SYSTEM}, *case["messages"][1:],
            {"role": "assistant", "content": request_text},
            {"role": "user", "content": "Host assessment result (the status remains authoritative):\n"
             + json.dumps(packet, sort_keys=True, ensure_ascii=False)
             + "\nReturn one JSON object with claims mapping the named claim to the checked status "
               "and explanation as one concise sentence."}]


def prepare(plan_path: Path, providers: dict[str, Any] | None = None, *, allow_unreviewed: bool = False) -> dict:
    frozen = _ORIGINAL_PREPARE(plan_path, providers, allow_unreviewed=allow_unreviewed)
    if {case["arm"] for case in frozen["cases"]} != {"skill_route"}:
        raise ValueError("Route-v2 runner requires a route-only developmental plan")
    if frozen["study_kind"] != "developmental":
        raise ValueError("Route-v2 is a developmental correction, not a confirmatory plan")
    source = Path(__file__).resolve()
    frozen["schema"] = FREEZE_SCHEMA
    frozen["routing_revision"] = ROUTING_REVISION
    frozen["plan_path"] = str(Path(plan_path).resolve())
    frozen["materials"][str(source)] = legacy.digest(source.read_bytes())
    for companion in ("audit_cross_model_ledger.py", "analyse_cross_model_campaign_v2.py"):
        path = ROOT / "scripts" / companion
        frozen["materials"][str(path)] = legacy.digest(path.read_bytes())
    frozen["freeze_sha256"] = legacy.digest({key: value for key, value in frozen.items()
                                             if key != "freeze_sha256"})
    verify_freeze(frozen)
    return frozen


def verify_freeze(frozen: dict) -> None:
    if (frozen.get("schema") != FREEZE_SCHEMA or frozen.get("routing_revision") != ROUTING_REVISION
            or frozen.get("study_kind") != "developmental"
            or frozen.get("plan", {}).get("study_kind") != "developmental"
            or not isinstance(frozen.get("plan_path"), str)
            or not frozen["plan_path"]
            or frozen.get("freeze_sha256") != legacy.digest({k: v for k, v in frozen.items()
                                                            if k != "freeze_sha256"})):
        raise ValueError("Expected an intact route-v2 developmental freeze")
    if (not frozen.get("cases") or not frozen["plan"].get("conditions")
            or any(condition.get("arm") != "skill_route" for condition in frozen["plan"]["conditions"])
            or any(case.get("arm") != "skill_route" for case in frozen["cases"])):
        raise ValueError("Route-v2 freeze must contain only skill_route cases")
    source = Path(__file__).resolve()
    if frozen.get("materials", {}).get(str(source)) != legacy.digest(source.read_bytes()):
        raise ValueError("Route-v2 wrapper differs from its frozen code")
    for case in frozen["cases"]:
        if (case.get("prompt_sha256") != legacy.digest(case.get("messages"))
                or case.get("prompt_bytes") != len(legacy.canonical(case["messages"]))
                or case.get("route_packet") is None):
            raise ValueError("Route-v2 prompt or bounded assessment link was altered")
        snapshot = frozen["snapshots"][case["root_id"] + "/" + case["state_id"]]
        if (case["expected"] != snapshot["expected"]
                or case["host_status"] != snapshot["eal"]["status"]
                or case["checker_status"] != snapshot["checker"]["status"]):
            raise ValueError("Route-v2 oracle or checked snapshot differs from its frozen case")


async def run(plan_path: Path, output: Path, *, freeze_only: bool = False, resume: bool = False,
              providers: dict[str, Any] | None = None) -> dict:
    if (legacy.prepare is not _ORIGINAL_PREPARE or legacy._route_second_messages is not _ORIGINAL_SECOND
            or legacy.verify_freeze is not _ORIGINAL_VERIFY):
        raise RuntimeError("Another route runner is already active in this interpreter")
    if (Path(output) / "freeze.json").exists():
        frozen = legacy.read_json(Path(output) / "freeze.json")
        verify_freeze(frozen)
        if (frozen["plan_path"] != str(Path(plan_path).resolve())
                or frozen["plan"] != legacy.load_plan(Path(plan_path))):
            raise ValueError("Route-v2 resume requires the same exact plan path and contents")
        if (Path(output) / "ledger.json").exists():
            from audit_cross_model_ledger import inspect
            checked = inspect(Path(output))
            if (set(checked["attempts_by_status"]) - {"completed"}
                    or checked["recorded_calls_with_unknown_usage"]):
                raise ValueError("Route-v2 resume requires a fully reconciled, priced completed prefix")
    legacy.prepare = prepare
    legacy._route_second_messages = second_messages
    legacy.verify_freeze = verify_freeze
    try:
        return await legacy.run(plan_path, output, freeze_only=freeze_only, resume=resume, providers=providers)
    finally:
        legacy.prepare = _ORIGINAL_PREPARE
        legacy._route_second_messages = _ORIGINAL_SECOND
        legacy.verify_freeze = _ORIGINAL_VERIFY


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--freeze-only", action="store_true")
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    print(json.dumps(asyncio.run(run(args.plan, args.output, freeze_only=args.freeze_only,
                                     resume=args.resume)), sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()
