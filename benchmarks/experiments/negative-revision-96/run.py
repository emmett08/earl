#!/usr/bin/env python3
"""Frozen 96-call developmental negative-revision pilot, no automatic retries.

Stage A: 8 roots × 3 states × 2 representations, each a fresh one-shot call.
Stage B: 8 roots × 2 formats × 3 linked authoring/revision turns.
The immutable schedule contains dynamic-message templates for linked turns;
every concrete request is hashed and persisted immediately before transmission.
"""
from __future__ import annotations

import argparse
import asyncio
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import random
import sys
import time
from datetime import datetime, timezone
from typing import Any

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(HERE))

import checker
from eal.evaluator import canonical_digest, environment_fingerprint, evaluate
from eal.parser import parse
from eal.providers import ProviderError, load_provider, response_cost
from eal.runtime import strict_json
from eal.sampled_negative import sampled_negative_registry
from eal.semantics import validate

STATES = ("covered_clear", "partial_violation", "wrong_scope_restore")
CLAIMS = ("bounded_property_supported", "violating_sample", "qualified_absence")
STATUSES = {"supported", "unsupported", "contested"}
PLAN = HERE / "plan.json"


def canonical(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode()


def digest(obj: Any) -> str:
    return hashlib.sha256(obj if isinstance(obj, bytes) else canonical(obj)).hexdigest()


def write(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as fh:
        json.dump(obj, fh, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False)
        fh.write("\n")
        fh.flush()
        os.fsync(fh.fileno())
    tmp.replace(path)


def record_for(program, name: str, row: dict, context: dict, now: str,
               required_correction: dict | None = None) -> dict | None:
    e = program.evidence[name]
    tool = program.tools[e.tool]
    # This is a separate acquisition-identity gate. EAL's typed envelope alone
    # would otherwise re-stamp a forged imported record with trusted metadata.
    try:
        request=row["request"]
        current=datetime.fromisoformat(now.replace("Z","+00:00"))
        collected=datetime.fromisoformat(row["observed_at"].replace("Z","+00:00"))
        if (row.get("context")!=context or request.get("context")!=context
                or request.get("tool")!=tool.name or request.get("tool_version")!=tool.version
                or request.get("mode")!=tool.mode or request.get("input")!={}
                or required_correction is not None and (
                    row.get("synthetic_correction")!=required_correction
                    or row.get("observed_at")!="2040-01-31T08:25:00Z")
                or not 0 <= (current-collected).total_seconds() <= 3600):
            return None
    except (KeyError,TypeError,ValueError):
        return None
    value = row["value"]
    return {"evidence_id":name,"source_digest":program.source_digest,
            "tool":tool.name,"tool_version":tool.version,"mode":tool.mode,
            "evidence_kind":e.kind,"environment":e.environment,
            "environment_fingerprint":environment_fingerprint(e.environment,context),
            "input_digest":canonical_digest(e.input),"collected_at":row["observed_at"],
            "run_id":"synthetic-neg96-fixed-acquisition","status":"ok",
            "value":value,"data_digest":canonical_digest(value)}


def eal_assess(source: str, state: dict, graph: dict, now: str) -> tuple[dict | None, list[str], dict]:
    try:
        program = parse(source)
        errors = validate(program, registry=sampled_negative_registry())
        if errors:
            return None, [str(e)[:500] for e in errors][:8], {}
        context = graph["context"]
        rows = {"first_record":record_for(program,"first_record",state["records"].get("first_reader"),context,now),
                "second_record":record_for(program,"second_record",state["records"].get("second_reader"),context,now),
                "trace_record":record_for(program,"trace_record",state["records"].get("trace_reader"),context,now,
                                          state.get("required_synthetic_correction"))}
        if "audit_record" in program.evidence:
            rows["audit_record"] = record_for(program,"audit_record",state["records"]["audit_reader"],context,now)
        records = {name:record for name,record in rows.items() if record is not None}
        report = evaluate(program, records, now=now, context=context, registry=sampled_negative_registry())
        return {c:report["claims"][c]["status"] for c in CLAIMS}, ([] if report["valid"] else report["diagnostics"][:8]), {
            "method_statuses":{n:report["arguments"][n].get("reasoning_result",{}).get("status") for n in ("adverse_route","absence_route")},
            "objections":{n:report["objections"][n]["status"] for n in report["objections"]}}
    except (ValueError, KeyError, TypeError, AttributeError) as exc:
        return None, [type(exc).__name__ + ": " + str(exc)[:500]], {}


def generic_assess(text: str, state: dict, now: str) -> tuple[dict | None, list[str]]:
    try:
        graph = strict_json(text)
        if not isinstance(graph, dict) or set(graph.get("positive_routes",[])) != {"first_reader","second_reader"}:
            raise ValueError("Graph must identify both independent positive routes")
        objections = graph.get("objections",[])
        if not isinstance(objections,list) or not objections or any(
            not isinstance(o,dict) or set(o)!={"target","premise"} or o["target"] not in {"first_reader","second_reader"}
            or o["premise"]!="violating_sample" for o in objections):
            raise ValueError("Graph must give a bounded negative attack on declared routes")
        return checker.evaluate(graph,state["records"],now=now,context=graph["context"],
                                required_correction=state.get("required_synthetic_correction")), []
    except (ValueError, KeyError, TypeError, AttributeError) as exc:
        return None, [type(exc).__name__ + ": " + str(exc)[:500]]


def fixed_materials() -> dict[str,str]:
    paths = [HERE / "plan.json", HERE / "README.md", HERE / "specifications.json", HERE / "build_fixtures.py",
             HERE / "checker.py", HERE / "run.py", HERE / "analyse.py",
             ROOT / "tests/test_negative_revision_96_campaign.py",
             ROOT / "src/eal/sampled_negative.py", ROOT / "src/eal/evaluator.py",
             ROOT / "src/eal/parser.py", ROOT / "src/eal/semantics.py",
             ROOT / "src/eal/providers.py", ROOT / "grammar/EAL.g4"]
    paths += list((HERE / "roots").glob("*/*"))
    plan = strict_json(PLAN.read_text())
    paths.append((HERE / plan["provider"]).resolve())
    return {str(path.relative_to(ROOT)):digest(path.read_bytes()) for path in sorted(paths)}


def _view_message(root: dict, state: dict, view: str, source: str, graph: dict) -> list[dict]:
    required = ("Return one JSON object with exactly 'claims' mapping bounded_property_supported, violating_sample, "
                "qualified_absence to supported, contested or unsupported, and 'explanation' as one sentence. "
                "Judge only the submitted records. Do not assert continuous truth.")
    body = source if view == "eal" else json.dumps(graph,sort_keys=True,ensure_ascii=False)
    return [{"role":"system","content":required},
            {"role":"user","content":f"Brief: {root['brief']}\nFormal {view} source:\n{body}\nAcquired synthetic records:\n"+json.dumps(state["records"],sort_keys=True)}]


def _author_messages(root: dict, state: dict, view: str, turn: int, previous: list[dict], feedback: str) -> list[dict]:
    format_rule = ("Write a complete EAL/2 source as plain text, without Markdown. Use environment run_scope, tools first_reader, second_reader, trace_reader; "
                   "evidence first_record, second_record, trace_record; reasoning provisional_test, witnessed_violation, complete_search; "
                   "claims bounded_property_supported, violating_sample, qualified_absence; arguments first_route, second_route, adverse_route, absence_route; "
                   "objection challenge_first and, if the brief requires, challenge_second; any answered challenges need separate audit evidence and answer objections. The sampled methods are engineering/sampled-negative/1, with mode fixed in each typed proposition, "
                   "and both positive test routes use structured/1. Observe the data contract in the records. Output the whole revised source each turn."
                   if view == "eal" else
                   "Write a complete JSON object as plain text, without Markdown. Schema negative-revision-equal-graph/1: "
                   "id, context, subject, scope, quantity, unit, bound, query, positive_routes, negative_claim, absence_claim, objections, defences, absence_positive_route, explanation. "
                   "query fixes start 0, end 12, max_gap 4, property strict lt or inclusive le as specified by the brief, semantics sampled, and a documented detector_contract whose maximum_detection_limit is no greater than the bound and minimum_sensitivity 0.9. "
                   "Use both first_reader and second_reader routes; declare exactly the brief's objection targets and any independent audit answer. Output the whole revised graph each turn.")
    states = ("Baseline: complete calibrated trace with no violating sample.",
              "Revision: a partial, correctly scoped sample crosses the bound.",
              "Revision: the previously adverse sample belongs to another run, so it cannot challenge this claim.")
    if root["pattern"] == "new_covered_restoration":
        states = (*states[:2], "Revision: the author stipulates withdrawal of the adverse report and substitutes a later complete calibrated no-violation search; this is an asserted synthetic correction, not authenticated physical history.")
    messages = [{"role":"system","content":format_rule}]
    messages += previous
    user = (f"Ordinary brief: {root['brief']}\nCurrent state: {states[turn]}\n"
            f"Synthetic records: {json.dumps(state['records'],sort_keys=True)}\n"
            + (f"Prior deterministic validator feedback: {feedback}\n" if feedback else "")
            + "Create or revise the formal artefact to preserve exactly the brief's claim, scope, two alternatives, both attacks and qualified absence. Return only the artefact.")
    return messages + [{"role":"user","content":user}]


def prepare(provider) -> dict:
    plan = strict_json(PLAN.read_text())
    roots = strict_json((HERE / "specifications.json").read_text())["roots"]
    if len(roots) != 8 or len({r["id"] for r in roots}) != 8 or plan["schema"] != "eal2-negative-revision-96-plan/1":
        raise ValueError("Eight distinct roots and the versioned plan are mandatory")
    snapshots = {}
    for root in roots:
        directory = HERE / "roots" / root["id"]
        source = (directory / "source.eal").read_text()
        graph = strict_json((directory / "graph.json").read_text())
        for state_id in STATES:
            state = strict_json((directory / (state_id + ".json")).read_text())
            eal, errors, trace = eal_assess(source,state,graph,plan["now"])
            equal, generic_errors = generic_assess(json.dumps(graph),state,plan["now"])
            if errors or generic_errors or eal != equal or eal != state["expected"]:
                raise ValueError(f"Canonical parity failed for {root['id']}/{state_id}: EAL {eal} {errors}; generic {equal} {generic_errors}; expected {state['expected']}")
            snapshots[root["id"]+"/"+state_id] = {"eal":eal,"equal":equal,"trace":trace}
        # A forged identity and missing records cannot activate either negative claim.
        for kind in ("forged_version","wrong_context","stale","future","missing_trace"):
            forged = strict_json((directory / "partial_violation.json").read_text())
            trace_record = forged["records"]["trace_reader"]
            if kind=="forged_version":
                trace_record["request"]["tool_version"] = "forged"
            elif kind=="wrong_context":
                trace_record["context"] = {"asset":"unrelated","run":"other"}
            elif kind=="stale":
                trace_record["observed_at"] = "2040-01-31T05:00:00Z"
            elif kind=="future":
                trace_record["observed_at"] = "2040-01-31T09:00:00Z"
            else:
                del forged["records"]["trace_reader"]
            g, error = generic_assess(json.dumps(graph),forged,plan["now"])
            e, e_errors, _ = eal_assess(source,forged,graph,plan["now"])
            if error or e_errors or g != e or g["violating_sample"] != "unsupported":
                raise ValueError(f"Paired acquisition tamper accepted or disagreed: {root['id']} {kind}: {e} {g} {e_errors} {error}")
        for kind in ("short_interval","wrong_query","weak_detector","partial_clear", "wrong_audit_finding", "missing_correction"):
            if kind=="wrong_audit_finding" and "audit_reader" not in strict_json((directory/"partial_violation.json").read_text())["records"]:
                continue
            if kind=="missing_correction" and root["pattern"]!="new_covered_restoration":
                continue
            baseline = "wrong_scope_restore" if kind=="missing_correction" else "covered_clear" if kind in ("weak_detector","partial_clear") else "partial_violation"
            attack = strict_json((directory/(baseline+".json")).read_text())
            if kind=="short_interval":
                attack["records"]["trace_reader"]["value"]["valid_from"]="2040-01-31T08:20:00Z"
            elif kind=="wrong_query":
                attack["records"]["trace_reader"]["value"]["payload"]["property"]["value"] += 1
            elif kind=="weak_detector":
                attack["records"]["trace_reader"]["value"]["payload"]["calibration"]["detection_limit"] = 1.0
            elif kind=="partial_clear":
                attack["records"]["trace_reader"]["value"]["payload"]["events"].pop()
            elif kind=="wrong_audit_finding":
                attack["records"]["audit_reader"]["value"]["finding"]="unrelated"
            else:
                del attack["records"]["trace_reader"]["synthetic_correction"]
            generic, generic_error = generic_assess(json.dumps(graph),attack,plan["now"])
            eal, eal_error, _ = eal_assess(source,attack,graph,plan["now"])
            failed_claim = "bounded_property_supported" if kind=="wrong_audit_finding" else "qualified_absence" if baseline!="partial_violation" else "violating_sample"
            if (generic_error or eal_error or generic!=eal
                    or generic[failed_claim]=="supported" and kind!="wrong_audit_finding"
                    or kind=="wrong_audit_finding" and generic[failed_claim]!="contested"):
                raise ValueError(f"Paired method/binding tamper accepted or disagreed: {root['id']} {kind}: {eal} {generic} {eal_error} {generic_error}")
    rng = random.Random(plan["seed"])
    stage_a = [(root["id"],state_id,view) for root in roots for state_id in STATES for view in ("eal","generic")]
    rng.shuffle(stage_a)
    sessions = [(r["id"],view) for r in roots for view in ("eal","generic")]
    rng.shuffle(sessions)
    stage_b = [(rid,view,turn) for rid,view in sessions for turn in range(3)]
    cases = []
    by_id = {r["id"]:r for r in roots}
    for stage, blocks in (("A",stage_a),("B",stage_b)):
        for rid, state_or_view, maybe_view in blocks:
            if stage == "A":
                state_id,view = state_or_view,maybe_view
                turn = STATES.index(state_id)
            else:
                view,turn = state_or_view,maybe_view
                state_id = STATES[turn]
            root = by_id[rid]
            state = strict_json((HERE / "roots" / rid / (state_id + ".json")).read_text())
            source = (HERE / "roots" / rid / "source.eal").read_text()
            graph = strict_json((HERE / "roots" / rid / "graph.json").read_text())
            messages = _view_message(root,state,view,source,graph) if stage=="A" else None
            case = {"index":len(cases),"stage":stage,"root":rid,"state":state_id,
                    "view":view,"turn":turn,"expected":state["expected"],"messages":messages,
                    "static_prompt_sha256":digest(messages) if messages else None}
            cases.append(case)
    if len(cases)!=96 or sum(c["stage"]=="A" for c in cases)!=48:
        raise ValueError("Schedule must contain precisely 48 Stage A and 48 Stage B calls")
    materials = fixed_materials()
    freeze = {"schema":"eal2-negative-revision-96-freeze/1","plan":plan,
              "provider_identity":provider.identity(),"method_registry_fingerprint":sampled_negative_registry().fingerprint,
              "materials":materials,"snapshots":snapshots,"roots":roots,"cases":cases,
              "frozen_at":datetime.now(timezone.utc).isoformat(),
              "limitations":"Selected, templated synthetic roots; author/reference is not independently human-adjudicated; model authoring is exploratory."}
    freeze["sha256"] = digest(freeze)
    return freeze


def _verify_freeze(freeze: dict, provider) -> None:
    if freeze.get("sha256") != digest({k:v for k,v in freeze.items() if k!="sha256"}):
        raise ValueError("Freeze checksum mismatch")
    if freeze["provider_identity"] != provider.identity():
        raise ValueError("Provider identity drift")
    if freeze["materials"] != fixed_materials():
        raise ValueError("Frozen materials changed")
    for case in freeze["cases"]:
        if case["messages"] is not None and digest(case["messages"]) != case["static_prompt_sha256"]:
            raise ValueError("Static prompt changed")


def _answer(text: str) -> dict:
    try:
        value = strict_json(text)
        if not isinstance(value,dict) or set(value)!={"claims","explanation"} or not isinstance(value["explanation"],str) or set(value["claims"])!=set(CLAIMS) or any(v not in STATUSES for v in value["claims"].values()):
            raise ValueError("Required exact claim-status/explanation JSON contract absent")
        return {"valid":True,"claims":value["claims"],"explanation":value["explanation"]}
    except (ValueError,TypeError) as exc:
        return {"valid":False,"error":str(exc)[:500],"claims":None,"explanation":None}


async def run(output: Path, *, freeze_only: bool, resume: bool, provider_override=None) -> dict:
    output = output.resolve()
    plan = strict_json(PLAN.read_text())
    if "OPENAI_API_KEY" not in os.environ and "OPENAI_API_TOKEN" in os.environ:
        os.environ["OPENAI_API_KEY"] = os.environ["OPENAI_API_TOKEN"]
    provider = provider_override or load_provider((HERE / plan["provider"]).resolve())
    output.mkdir(parents=True,exist_ok=True)
    freeze_file, ledger_file = output/"freeze.json",output/"ledger.json"
    if freeze_file.exists():
        if not resume:
            raise ValueError("Existing frozen directory needs --resume")
        freeze = strict_json(freeze_file.read_text())
        _verify_freeze(freeze,provider)
    else:
        if resume:
            raise ValueError("No frozen schedule to resume")
        freeze = prepare(provider)
        write(freeze_file,freeze)
    ledger = strict_json(ledger_file.read_text()) if ledger_file.exists() else {
        "schema":"eal2-negative-revision-96-ledger/1","freeze_sha256":freeze["sha256"],
        "status":"frozen","attempts":[]}
    if ledger["freeze_sha256"]!=freeze["sha256"]:
        raise ValueError("Ledger differs from freeze")
    if not ledger_file.exists():
        write(ledger_file,ledger)
    if freeze_only:
        return {"status":"frozen","cases":len(freeze["cases"]),"freeze_sha256":freeze["sha256"]}
    if any(row.get("status")!="completed" for row in ledger["attempts"]):
        raise ValueError("Pending/failed call may have been billed; never silently retry")
    if len(ledger["attempts"])>96 or any(row.get("index")!=i for i,row in enumerate(ledger["attempts"])):
        raise ValueError("Ledger attempt order invalid")
    actual_spent = sum(row["usage"]["cost_usd"] for row in ledger["attempts"])
    roots = {r["id"]:r for r in freeze["roots"]}
    history = {}
    for row in ledger["attempts"]:
        c = freeze["cases"][row["index"]]
        if c["stage"]=="B":
            history.setdefault((c["root"],c["view"]),[]).append(row)
    for case in freeze["cases"][len(ledger["attempts"]):]:
        rid,view,turn = case["root"],case["view"],case["turn"]
        previous_rows = history.get((rid,view),[])
        if case["stage"]=="B" and len(previous_rows)!=turn:
            raise ValueError("Linked session predecessor missing")
        state = strict_json((HERE/"roots"/rid/(case["state"]+".json")).read_text())
        messages = case["messages"]
        if case["stage"]=="B":
            previous=[]
            for row in previous_rows:
                previous += [{"role":"user","content":row["messages"][-1]["content"]},
                             {"role":"assistant","content":row["response"]["text"]}]
            feedback = json.dumps(previous_rows[-1]["author_feedback"],sort_keys=True) if previous_rows else ""
            messages = _author_messages(roots[rid],state,view,turn,previous,feedback)
        prompt_size = len(canonical(messages))
        if prompt_size > plan["max_prompt_bytes"]:
            ledger["status"]="stopped_prompt_limit";write(ledger_file,ledger);break
        rates = freeze["provider_identity"]["pricing"]
        reserve = ((prompt_size+256)*rates["input_usd_per_million"]
                   + plan["max_output_tokens"]*rates["output_usd_per_million"])/1_000_000
        if actual_spent+reserve>plan["max_cost_usd"]:
            ledger["status"]="stopped_budget";write(ledger_file,ledger);break
        row={"index":case["index"],"stage":case["stage"],"root":rid,"state":case["state"],
             "view":view,"turn":turn,"messages":messages,"prompt_sha256":digest(messages),
             "status":"pending","retry_count":0,"usage":None}
        ledger["attempts"].append(row);ledger["status"]="running";write(ledger_file,ledger)
        start=time.monotonic()
        try:
            response=await provider.complete(messages,plan["max_output_tokens"])
            cost=response_cost(response,freeze["provider_identity"])
            expected=plan.get("response_model",freeze["provider_identity"]["model"])
            if response.model!=expected or cost is None or response.input_tokens is None or response.output_tokens is None:
                raise ProviderError("Provider identity or usage differed from freeze",response=response)
            row.update(status="completed",response={"text":response.text,"model":response.model,"metadata":response.metadata},
                       usage={"input_tokens":response.input_tokens,"output_tokens":response.output_tokens,
                              "cached_input_tokens":response.metadata.get("cached_input_tokens",0),"cost_usd":cost},
                       duration_seconds=time.monotonic()-start)
            if case["stage"]=="A":
                parsed=_answer(response.text)
                row["recipient"]=parsed
                row["all_claims_correct"]=parsed["valid"] and parsed["claims"]==case["expected"]
                row["false_support"]=bool(parsed["valid"] and any(parsed["claims"][c]=="supported" and case["expected"][c]!="supported" for c in CLAIMS))
            else:
                source=response.text
                target_graph=strict_json((HERE/"roots"/rid/"graph.json").read_text())
                if view=="eal":
                    result,errors,_=eal_assess(source,state,target_graph,plan["now"])
                else:
                    result,errors=generic_assess(source,state,plan["now"])
                row["author_feedback"]={"accepted":not errors and result is not None,"statuses":result,
                                        "errors":[str(x)[:500] for x in errors][:8]}
                row["all_claims_correct"]=not errors and result==case["expected"]
                row["false_support"]=bool(result is not None and any(result[c]=="supported" and case["expected"][c]!="supported" for c in CLAIMS))
                replay=[]
                for state_id in STATES:
                    probe=strict_json((HERE/"roots"/rid/(state_id+".json")).read_text())
                    if view=="eal":
                        found,problems,_=eal_assess(source,probe,target_graph,plan["now"])
                    else:
                        found,problems=generic_assess(source,probe,plan["now"])
                    replay.append({"state":state_id,"statuses":found,"errors":[str(x)[:500] for x in problems][:8],
                                   "matches_reference":not problems and found==probe["expected"]})
                row["finite_suite_replay"]={"all_three":all(x["matches_reference"] for x in replay),"states":replay}
                history.setdefault((rid,view),[]).append(row)
            actual_spent+=cost
        except ProviderError as exc:
            measured=exc.response
            cost=response_cost(measured,freeze["provider_identity"]) if measured else None
            row.update(status="failed",error=type(exc).__name__+": "+str(exc),duration_seconds=time.monotonic()-start,
                       response={"text":measured.text,"model":measured.model,"metadata":measured.metadata} if measured else None,
                       usage={"input_tokens":measured.input_tokens,"output_tokens":measured.output_tokens,"cost_usd":cost} if measured and cost is not None else None)
            ledger["status"]="stopped_provider_failure"
        except Exception as exc:
            row.update(status="failed",error=type(exc).__name__+": "+str(exc)[:500],duration_seconds=time.monotonic()-start)
            ledger["status"]="stopped_unknown_usage"
        write(ledger_file,ledger)
        if row["status"]!="completed":
            break
    else:
        ledger["status"]="complete";write(ledger_file,ledger)
    return {"status":ledger["status"],"attempts":len(ledger["attempts"]),"cases":96,
            "configured_rate_cost_usd":actual_spent,"freeze_sha256":freeze["sha256"]}


def main() -> None:
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("output",type=Path)
    ap.add_argument("--freeze-only",action="store_true")
    ap.add_argument("--resume",action="store_true")
    args=ap.parse_args()
    print(json.dumps(asyncio.run(run(args.output,freeze_only=args.freeze_only,resume=args.resume)),sort_keys=True))


if __name__=="__main__":
    main()
