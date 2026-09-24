#!/usr/bin/env python3
"""Matched EAL/2–JSON and equal-call bias-agent developmental cohorts.

This reuses the author-created Stage A cases for an exploratory calibration.
It does not supply an independent confirmation set or human observations.
"""

from __future__ import annotations

import argparse
from contextlib import ExitStack
from dataclasses import asdict
import fcntl
import json
import os
from pathlib import Path
import random
import sys
import time
import urllib.error

HERE = Path(__file__).resolve().parent
BASE = HERE.parent / "bias-mechanisms"
sys.path.insert(0, str(BASE))
import run as baseline  # noqa: E402
import analyse as baseline_analysis  # noqa: E402

SCHEMA = "eal2-bias-followups-freeze/1"
LEDGER_SCHEMA = "eal2-bias-followups-ledger/1"
REPRESENTATIONS = ("eal2", "derived_json")
TOPOLOGIES = {"repeat_direct": ("direct_1", "direct_2"),
              "specialised_challenge": ("mechanism", "rival")}
SYSTEM = (
    "Assess this hypothetical engineering decision episode. The supplied argument is authored, "
    "and its declared evidence is not proof of a person's cognitive cause. A bad outcome or "
    "fluent recommendation alone does not establish human bias. Examine cue exposure, an "
    "opportunity to decide otherwise, actual uptake, directional signature, time order, a "
    "comparison and technical or organisational rivals. Cite only supplied record IDs under "
    "the roles they support. Correct the engineering defect without diagnosing a lasting "
    "personal trait. Select only supplied option IDs. Give a rationale of at most 300 characters."
)


def projection(source: str) -> dict:
    """Derive a typed declaration graph from the repository's checked parser."""
    root = HERE.parents[2]
    sys.path.insert(0, str(root / "src"))
    from eal.parser import parse
    from eal.semantics import validate
    program = parse(source)
    diagnostics = validate(program)
    if diagnostics:
        raise ValueError(f"EAL source failed static validation: {diagnostics}")
    groups = ("environments", "tools", "evidence", "assumptions", "reasoning",
              "claims", "arguments", "objections")
    if program.patterns or program.applications or program.lowering_diagnostics:
        raise ValueError("This experiment does not render pattern expansion")
    return {"schema": "eal2-typed-declarations/1", "language": program.language,
            "declarations": {name: {key: asdict(value) for key, value in
                                    sorted(getattr(program, name).items())} for name in groups}}


def checked_graph(source: str, graph: dict) -> None:
    """Check every declaration and reference field against a fresh source parse."""
    if graph != projection(source):
        raise ValueError("Derived JSON graph differs from the typed EAL declarations")


def packet(case: dict, representation: str) -> dict:
    if representation not in REPRESENTATIONS:
        raise ValueError("Unknown representation")
    argument = case["eal"] if representation == "eal2" else projection(case["eal"])
    return {"episode_id": baseline.opaque_episode_id(case["id"]),
            "argument": argument, "records": case["records"], "options": case["options"]}


def request(case: dict, representation: str, model: dict, stage: str,
            mechanisms: list[str], max_output_tokens: int) -> dict:
    emphasis = {"direct_1": "Assess all explanations and give your disposition.",
                "direct_2": "Assess all explanations and give your disposition.",
                "mechanism": "Independently test the proposed mechanism and every required process link.",
                "rival": "Independently seek the strongest alternative and missing premise."}[stage]
    body = {"model": model["id"], "store": False,
            "max_output_tokens": max_output_tokens,
            "input": [{"role": "system", "content": SYSTEM},
                      {"role": "user", "content": emphasis + "\nCandidate mechanisms: " +
                       json.dumps(mechanisms, separators=(",", ":")) + "\nEpisode: " +
                       baseline.canonical(packet(case, representation)).decode("utf-8")}],
            "text": {"format": {"type": "json_schema", "name": "bias_episode_disposition",
                                "strict": True, "schema": baseline.ANSWER_SCHEMA}}}
    if model["reasoning"] is not None:
        body["reasoning"] = {"effort": model["reasoning"]}
    return body


def material_hashes(cases: list[dict]) -> dict[str, str]:
    root = HERE.parents[2]
    hashes = baseline.validate_eal_sources(cases)
    files = [BASE / "cases.json", BASE / "run.py", BASE / "analyse.py",
             HERE / "followup.py", HERE / "PROTOCOL.md"]
    return {**hashes, **{p.relative_to(root).as_posix(): baseline.digest(p.read_bytes())
                        for p in files}}


def planned(families: int, names: list[str], seed: int, output_limit: int) -> tuple[list[dict], list[dict]]:
    cases = baseline.load_cases()[:4 * families]
    mechanisms = sorted({c["mechanism"] for c in baseline.load_cases()})
    calls = []
    for case in cases:
        for name in names:
            for representation in REPRESENTATIONS:
                for topology, stages in TOPOLOGIES.items():
                    for stage in stages:
                        body = request(case, representation, baseline.MODELS[name], stage,
                                       mechanisms, output_limit)
                        calls.append({"id": "__".join((case["id"], name, representation,
                                                           topology, stage)),
                                      "case_id": case["id"], "family": case["family"],
                                      "model_name": name, "representation": representation,
                                      "topology": topology, "stage": stage,
                                      "request": body, "request_sha256": baseline.digest(body),
                                      "reserved_usd": baseline.reserved_cost(body, baseline.MODELS[name])})
    random.Random(seed).shuffle(calls)
    return cases, calls


def freeze(path: Path, *, families: int = 2, names: tuple[str, ...] = ("luna", "sol"),
           seed: int = 240925, max_usd: float = 20, output_limit: int = 1200) -> dict:
    if (not 1 <= families <= 12 or not names or len(set(names)) != len(names)
            or set(names) - set(baseline.MODELS) or not 256 <= output_limit <= 4096
            or not 0 < max_usd <= 200):
        raise ValueError("Invalid frozen configuration")
    cases, calls = planned(families, list(names), seed, output_limit)
    materials = material_hashes(cases)
    for case in cases:
        checked_graph(case["eal"], packet(case, "derived_json")["argument"])
    reserve = sum(c["reserved_usd"] for c in calls)
    if reserve > max_usd:
        raise ValueError(f"Conservative reserve ${reserve:.4f} exceeds cap ${max_usd:.2f}")
    data = {"schema": SCHEMA, "created_utc": baseline.utc_now(),
            "developmental_reuse_of_stage_a": True, "materials": materials,
            "families": families, "case_count": len(cases), "seed": seed,
            "models": {name: baseline.MODELS[name] for name in names},
            "max_usd": max_usd, "max_output_tokens": output_limit,
            "calls": calls}
    data["freeze_sha256"] = baseline.digest(data)
    fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, allow_nan=False)
        f.write("\n")
        f.flush()
        os.fsync(f.fileno())
    return data


def load_freeze(path: Path) -> dict:
    data = baseline.read_json(path)
    supplied = data.get("freeze_sha256")
    if data.get("schema") != SCHEMA or supplied != baseline.digest(
            {key: val for key, val in data.items() if key != "freeze_sha256"}):
        raise ValueError("Invalid or modified follow-up freeze")
    names = list(data["models"])
    if (not 1 <= data["families"] <= 12 or not names or set(names) - set(baseline.MODELS)
            or data["models"] != {name: baseline.MODELS[name] for name in names}
            or not 256 <= data["max_output_tokens"] <= 4096
            or not 0 < data["max_usd"] <= 200):
        raise ValueError("Frozen model, budget or output configuration differs")
    cases, calls = planned(data["families"], names, data["seed"], data["max_output_tokens"])
    if data["materials"] != material_hashes(cases):
        raise ValueError("Follow-up study materials changed since freeze")
    if data["calls"] != calls or data["case_count"] != len(cases):
        raise ValueError("Frozen requests differ from deterministic regeneration")
    if sum(c["reserved_usd"] for c in calls) > data["max_usd"]:
        raise ValueError("Frozen reserve exceeds cap")
    return data


def _events(path: Path) -> list[dict]:
    if not path.exists():
        return []
    previous, result = "0" * 64, []
    for line in path.read_text(encoding="utf-8").splitlines():
        item = baseline.strict_json(line)
        sha = item.pop("event_sha256", None)
        if (item.get("schema") != LEDGER_SCHEMA or item.get("previous_sha256") != previous
                or baseline.digest(item) != sha):
            raise ValueError("Follow-up ledger hash chain is invalid")
        item["event_sha256"] = sha
        result.append(item)
        previous = sha
    return result


def _append(path: Path, event: dict, previous: str) -> str:
    item = baseline.redact({"schema": LEDGER_SCHEMA, "previous_sha256": previous, **event})
    item["event_sha256"] = baseline.digest(item)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(baseline.canonical(item).decode("utf-8") + "\n")
        f.flush()
        os.fsync(f.fileno())
    return item["event_sha256"]


def _outcomes(events: list[dict], freeze_data: dict, *, allow_pending: bool = False) -> dict[str, dict]:
    calls = {c["id"]: c for c in freeze_data["calls"]}
    pending, result = set(), {}
    for e in events:
        call = calls.get(e.get("call_id"))
        if not call or e.get("request_sha256") != call["request_sha256"]:
            raise ValueError("Ledger event is outside the frozen plan")
        if e["kind"] == "pending":
            if e["call_id"] in pending:
                raise ValueError("Duplicate request attempt")
            pending.add(e["call_id"])
        elif e["kind"] == "outcome":
            if e["call_id"] not in pending or e["call_id"] in result:
                raise ValueError("Orphan or duplicate outcome")
            result[e["call_id"]] = e
        else:
            raise ValueError("Unknown ledger event kind")
    if pending - set(result) and not allow_pending:
        raise RuntimeError("Unresolved pending call; reconcile provider before continuing")
    return result


def execute(freeze_path: Path, ledger_path: Path, *, prior_freeze: Path | None = None,
            prior_ledger: Path | None = None) -> dict:
    frozen = load_freeze(freeze_path)
    if bool(prior_freeze) != bool(prior_ledger):
        raise ValueError("Pilot freeze and ledger must be supplied together")
    if frozen["families"] > 2 and not prior_freeze:
        raise ValueError("Full cohort requires an unchanged complete two-family pilot")
    if prior_ledger and prior_ledger.resolve() == ledger_path.resolve():
        raise ValueError("Pilot and full ledgers must be distinct")
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    paths = sorted({ledger_path, *(tuple([prior_ledger]) if prior_ledger else ())})
    with ExitStack() as stack:
        for path in paths:
            fd = os.open(path.with_name(path.name + ".lock"), os.O_CREAT | os.O_RDWR, 0o600)
            stack.callback(os.close, fd)
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise RuntimeError("Study ledger locked by another executor") from None
            stack.callback(fcntl.flock, fd, fcntl.LOCK_UN)
        prior = load_freeze(prior_freeze) if prior_freeze else None
        if prior and (prior["families"] != 2 or prior["models"] != frozen["models"]
                      or {c["id"]: c["request_sha256"] for c in prior["calls"]}
                      != {c["id"]: c["request_sha256"] for c in frozen["calls"]
                          if c["id"] in {p["id"] for p in prior["calls"]}}):
            raise ValueError("Prior pilot does not match this full plan")
        prior_events = _events(prior_ledger) if prior_ledger else []
        current_events = _events(ledger_path)
        prior_done = _outcomes(prior_events, prior) if prior else {}
        current_done = _outcomes(current_events, frozen)
        if prior and (len(prior_done) != len(prior["calls"])
                      or any(e["result"] != "ok" for e in prior_done.values())):
            raise RuntimeError("Pilot must finish validly before full execution")
        if set(prior_done) & set(current_done):
            raise ValueError("Call attempted in both ledgers")
        if any(e["result"] != "ok" for e in current_done.values()):
            raise RuntimeError("Existing invalid provider outcome requires review")
        # No-key connectivity probe precedes credential lookup and every charge.
        baseline.preflight()
        key = os.environ.get("OPENAI_API_KEY", "")
        if not key:
            raise RuntimeError("OPENAI_API_KEY is not set")
        previous = current_events[-1]["event_sha256"] if current_events else "0" * 64
        spent = sum((e.get("cost_usd") if e.get("cost_usd") is not None else
                     frozen_call["reserved_usd"]) for plan, outcomes in
                    ((prior, prior_done), (frozen, current_done)) if plan
                    for cid, e in outcomes.items()
                    for frozen_call in [next(c for c in plan["calls"] if c["id"] == cid)])
        cases = {c["id"]: c for c in baseline.load_cases()}
        returned_models = {}
        for plan, outcomes in ((prior, prior_done), (frozen, current_done)):
            if not plan:
                continue
            index = {c["id"]: c for c in plan["calls"]}
            for cid, e in outcomes.items():
                name = index[cid]["model_name"]
                if e.get("returned_model"):
                    old = returned_models.setdefault(name, e["returned_model"])
                    if old != e["returned_model"]:
                        raise RuntimeError("Returned model identity drift")
        newly_completed = 0
        for call in frozen["calls"]:
            if call["id"] in prior_done or call["id"] in current_done:
                continue
            if spent + call["reserved_usd"] > frozen["max_usd"]:
                raise RuntimeError("Frozen cumulative budget reached before next call")
            previous = _append(ledger_path, {"kind": "pending", "call_id": call["id"],
                       "request_sha256": call["request_sha256"], "utc": baseline.utc_now(),
                       "reserved_usd": call["reserved_usd"]}, previous)
            spent += call["reserved_usd"]
            start = time.monotonic()
            try:
                response, request_id = baseline._post_response(call["request"], key)
                answer, failure = baseline.parse_response(response)
                validation = baseline.validate_answer(answer, cases[call["case_id"]]) if answer else []
                usage = response.get("usage") or {}
                i, o = usage.get("input_tokens"), usage.get("output_tokens")
                rate = frozen["models"][call["model_name"]]
                cost = ((i * rate["input_usd_per_million"] +
                         o * rate["output_usd_per_million"]) / 1_000_000
                        if type(i) is int and type(o) is int and i >= 0 and o >= 0 else None)
                if cost is None:
                    validation.append("missing_usage")
                model_id = response.get("model")
                if not isinstance(model_id, str) or not model_id.startswith(rate["id"]):
                    validation.append("wrong_returned_model")
                elif model_id != returned_models.setdefault(call["model_name"], model_id):
                    validation.append("returned_model_identity_drift")
                outcome = {"result": "ok" if answer is not None and not validation else "invalid",
                           "answer": answer, "failure": failure, "validation": validation,
                           "provider_response": response, "response_id": response.get("id"),
                           "http_request_id": request_id, "returned_model": model_id,
                           "usage": usage, "cost_usd": cost}
            except urllib.error.HTTPError as exc:
                outcome = {"result": "provider_error", "failure": f"HTTP {exc.code}",
                           "provider_error_body": exc.read(2_000_000).decode("utf-8", "replace"),
                           "answer": None, "returned_model": None, "cost_usd": None}
            except (urllib.error.URLError, OSError, ValueError, TimeoutError) as exc:
                outcome = {"result": "transport_error", "failure": str(exc)[:300],
                           "answer": None, "returned_model": None, "cost_usd": None}
            previous = _append(ledger_path, {"kind": "outcome", "call_id": call["id"],
                       "request_sha256": call["request_sha256"], "utc": baseline.utc_now(),
                       "reserved_usd": call["reserved_usd"],
                       "latency_seconds": round(time.monotonic() - start, 4), **outcome}, previous)
            spent += (outcome["cost_usd"] if outcome["cost_usd"] is not None else
                      call["reserved_usd"]) - call["reserved_usd"]
            if outcome["result"] != "ok":
                raise RuntimeError("Provider/response failure retained without automatic retry")
            newly_completed += 1
        return {"calls": len(frozen["calls"]),
                "valid": len(prior_done) + len(current_done) + newly_completed,
                "estimated_spend_usd": round(spent, 5)}


def analyse(freeze_path: Path, ledger_path: Path, *, prior_freeze: Path | None = None,
            prior_ledger: Path | None = None) -> dict:
    frozen = load_freeze(freeze_path)
    if bool(prior_freeze) != bool(prior_ledger):
        raise ValueError("Pilot freeze and ledger must be supplied together")
    prior = load_freeze(prior_freeze) if prior_freeze else None
    prior_events = _events(prior_ledger) if prior else []
    current_events = _events(ledger_path)
    prior_out = _outcomes(prior_events, prior, allow_pending=True) if prior else {}
    current_out = _outcomes(current_events, frozen, allow_pending=True)
    if set(prior_out) & set(current_out):
        raise ValueError("Duplicate pilot/full outcome")
    outcomes = {**prior_out, **current_out}
    cases = {c["id"]: c for c in baseline.load_cases()}
    rows = []
    for case_id in sorted({c["case_id"] for c in frozen["calls"]}):
        case = cases[case_id]
        gold = case["gold"]
        for name in frozen["models"]:
            for rep in REPRESENTATIONS:
                for topology, stages in TOPOLOGIES.items():
                    ids = ["__".join((case_id, name, rep, topology, stage)) for stage in stages]
                    events = [outcomes.get(cid) for cid in ids]
                    answers = [e.get("answer") if e and e["result"] == "ok" else None for e in events]
                    answer = baseline_analysis._synthesise(*answers)
                    valid = answer is not None and not baseline.validate_answer(answer, case)
                    cited = bool(valid and all(set(required).issubset(answer["evidence_ids"][role])
                                               for role, required in gold["required_roles"].items()))
                    correct = bool(cited and answer["status"] == gold["status"] and
                                   answer["defect_id"] == gold["defect_id"] and
                                   answer["correction_id"] == gold["correction_id"] and
                                   answer["rival_id"] == gold["rival_id"] and
                                   answer["defeater_id"] == gold["defeater_id"] and
                                   (answer["mechanism_id"] == gold["mechanism_id"] or
                                    (gold["status"] in ("NOT-APPLICABLE", "REJECTED", "UNDECIDED")
                                     and answer["mechanism_id"] is None)))
                    negative = gold["status"] not in baseline_analysis.SUPPORT
                    usage = [e.get("usage") or {} for e in events if e]
                    analyst_false = sum(bool(a and a["status"] in baseline_analysis.SUPPORT
                                             and (negative or a["mechanism_id"] != gold["mechanism_id"]))
                                        for a in answers)
                    analyst_wrong_correction = sum(bool(a and a["correction_id"] is not None
                                                      and a["correction_id"] != gold["correction_id"])
                                                   for a in answers)
                    rows.append({"case_id": case_id, "family": case["family"],
                                 "model": name, "representation": rep, "topology": topology,
                                 "calls_valid": sum(e is not None and e["result"] == "ok" for e in events),
                                 "calls_expected": 2, "fully_warranted": correct,
                                 "strong_false_attribution": bool(valid and
                                    answer["status"] in baseline_analysis.SUPPORT and
                                    (negative or answer["mechanism_id"] != gold["mechanism_id"])),
                                 "supported_recall": bool(not negative and valid and
                                    answer["status"] in baseline_analysis.SUPPORT and
                                    answer["mechanism_id"] == gold["mechanism_id"]),
                                 "wrong_correction": bool(valid and answer["correction_id"] is not None
                                                          and answer["correction_id"] != gold["correction_id"]),
                                 "analyst_strong_false_attribution": analyst_false,
                                 "analyst_wrong_correction": analyst_wrong_correction,
                                 "status": answer["status"] if valid else None,
                                 "planned_input_bytes": sum(len(baseline.canonical(c["request"]["input"]))
                                                            for c in frozen["calls"] if c["id"] in ids),
                                 "input_tokens": sum(u.get("input_tokens", 0) for u in usage),
                                 "output_tokens": sum(u.get("output_tokens", 0) for u in usage),
                                 "cost_usd": sum(e.get("cost_usd") or 0 for e in events if e),
                                 "latency_seconds": sum(e.get("latency_seconds") or 0 for e in events if e)})
    complete = len(outcomes) == len(frozen["calls"])
    valid = complete and all(e["result"] == "ok" for e in outcomes.values())
    pending = sum(e["kind"] == "pending" for e in prior_events + current_events) - len(outcomes)
    grouped = {}
    for name in frozen["models"]:
        for rep in REPRESENTATIONS:
            for topology in TOPOLOGIES:
                subset = [r for r in rows if (r["model"], r["representation"], r["topology"])
                          == (name, rep, topology)]
                positive = [r for r in subset if cases[r["case_id"]]["gold"]["status"]
                            in baseline_analysis.SUPPORT]
                grouped[name + "/" + rep + "/" + topology] = {
                    "assignments": len(subset),
                    "completed_assignments": sum(r["calls_valid"] == 2 for r in subset),
                    "fully_warranted": sum(r["fully_warranted"] for r in subset),
                    "strong_false_attribution": sum(r["strong_false_attribution"] for r in subset),
                    "wrong_correction": sum(r["wrong_correction"] for r in subset),
                    "analyst_strong_false_attribution": sum(r["analyst_strong_false_attribution"]
                                                               for r in subset),
                    "analyst_wrong_correction": sum(r["analyst_wrong_correction"] for r in subset),
                    "supported_recall": sum(r["supported_recall"] for r in positive),
                    "supported_denominator": len(positive),
                    "decisive_coverage": sum(r["status"] not in (None, "UNDECIDED") for r in subset),
                    "planned_input_bytes": sum(r["planned_input_bytes"] for r in subset),
                    "input_tokens": sum(r["input_tokens"] for r in subset),
                    "output_tokens": sum(r["output_tokens"] for r in subset),
                    "estimated_cost_usd": round(sum(r["cost_usd"] for r in subset), 6),
                    "latency_seconds": round(sum(r["latency_seconds"] for r in subset), 3),
                }
    return {"schema": "eal2-bias-followups-analysis/1",
            "freeze_sha256": frozen["freeze_sha256"],
            "state": "unrun" if not outcomes and not pending else
                     "interrupted" if pending else "complete" if valid else
                     "terminal_with_failures" if complete else "partial",
            "calls_planned": len(frozen["calls"]), "calls_terminal": len(outcomes),
            "calls_valid": sum(e["result"] == "ok" for e in outcomes.values()),
            "calls_pending": pending, "summary": grouped,
            "developmental_reuse_of_stage_a": True,
            "contrasts": _contrasts(rows, frozen) if valid else None,
            "rows": rows}


def _contrasts(rows: list[dict], frozen: dict) -> dict:
    """Paired family means; no population or human inference from reused cases."""
    index = {(r["case_id"], r["model"], r["representation"], r["topology"]): r
             for r in rows}
    cases = baseline.load_cases()[:4 * frozen["families"]]
    result = {}
    for name in frozen["models"]:
        for rep in REPRESENTATIONS:
            deltas = []
            for family in sorted({c["family"] for c in cases}):
                members = [c for c in cases if c["family"] == family]
                deltas.append(sum(int(index[(c["id"], name, rep, "specialised_challenge")]["fully_warranted"])
                                  - int(index[(c["id"], name, rep, "repeat_direct")]["fully_warranted"])
                                  for c in members) / len(members))
            result[name + "/" + rep + "/topology"] = sum(deltas) / len(deltas)
        for topology in TOPOLOGIES:
            deltas = []
            for family in sorted({c["family"] for c in cases}):
                members = [c for c in cases if c["family"] == family]
                deltas.append(sum(int(index[(c["id"], name, "derived_json", topology)]["fully_warranted"])
                                  - int(index[(c["id"], name, "eal2", topology)]["fully_warranted"])
                                  for c in members) / len(members))
            result[name + "/" + topology + "/json_minus_eal"] = sum(deltas) / len(deltas)
    return result


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    commands = p.add_subparsers(dest="command", required=True)
    f = commands.add_parser("freeze")
    f.add_argument("path", type=Path)
    f.add_argument("--families", type=int, default=2)
    f.add_argument("--models", nargs="+", default=["luna", "sol"])
    f.add_argument("--seed", type=int, default=240925)
    f.add_argument("--max-usd", type=float, default=20)
    f.add_argument("--max-output-tokens", type=int, default=1200)
    e = commands.add_parser("execute")
    e.add_argument("freeze", type=Path)
    e.add_argument("ledger", type=Path)
    e.add_argument("--prior-freeze", type=Path)
    e.add_argument("--prior-ledger", type=Path)
    a = commands.add_parser("analyse")
    a.add_argument("freeze", type=Path)
    a.add_argument("ledger", type=Path)
    a.add_argument("report", type=Path)
    a.add_argument("--prior-freeze", type=Path)
    a.add_argument("--prior-ledger", type=Path)
    commands.add_parser("preflight")
    args = p.parse_args(argv)
    try:
        if args.command == "freeze":
            value = freeze(args.path, families=args.families, names=tuple(args.models),
                           seed=args.seed, max_usd=args.max_usd,
                           output_limit=args.max_output_tokens)
            print(json.dumps({"freeze_sha256": value["freeze_sha256"],
                              "calls": len(value["calls"]),
                              "reserved_usd": round(sum(c["reserved_usd"] for c in value["calls"]), 4)}))
        elif args.command == "execute":
            print(json.dumps(execute(args.freeze, args.ledger,
                                     prior_freeze=args.prior_freeze,
                                     prior_ledger=args.prior_ledger)))
        elif args.command == "analyse":
            report = analyse(args.freeze, args.ledger,
                             prior_freeze=args.prior_freeze, prior_ledger=args.prior_ledger)
            fd = os.open(args.report, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                json.dump(report, stream, indent=2, ensure_ascii=False)
                stream.write("\n")
            print(json.dumps({"state": report["state"],
                              "calls_terminal": report["calls_terminal"]}))
        else:
            baseline.preflight()
            print("Endpoint reachable; no key sent or model call made")
        return 0
    except Exception as exc:
        print("Follow-up stopped: " + baseline.redact(str(exc)), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
