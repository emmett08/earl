"""Prepare held-out synthetic paired tasks and score retained first attempts.

This harness never authors model responses or starts a model. An external host
must execute separate assessor/reviewer contexts and record their exact bytes.
Reference and preflight calls are explicitly software execution of real EAL MCP.
"""
from __future__ import annotations

import argparse
import base64
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re
import shutil
import sqlite3

from eal.api_load_methods import registry as api_registry
from eal.coordination import Coordinator
from eal.coordination.service import strict_json
from eal.evaluator import canonical_digest
from eal.knowledge import EALKnowledgeBase
from eal.semantics import parse_time

from .coordinator_demo import (_availability_source, _binding, _json_bytes,
                               prepare_demo)

PLAN_PATH = Path(__file__).with_name("accuracy-plan.json")
ANSWER_FIELDS = {"task_digest", "finding_id", "claims", "scope", "conclusion", "qualification"}


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_json_bytes(value))


def digest_file(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _register(workspace, task, context):
    """Rebuild host paths and one selected catalogue entry in an empty DB."""
    workspace = Path(workspace).resolve()
    database = workspace / "knowledge.sqlite"
    if database.exists():
        database.unlink()
    for suffix in ("-wal", "-shm"):
        database.with_name(database.name + suffix).unlink(missing_ok=True)
    api_collector = workspace / "collect_results.py"
    generic_collector = workspace / "collect_availability.py"
    registry = workspace / "tools.toml"
    registry.write_text(_binding("load_test_report", api_collector, "--report", str(workspace / "report.json"))
                        + "\n" + _binding("synthetic_availability", generic_collector), encoding="utf-8")
    kb = EALKnowledgeBase(workspace, registry, database, method_registry=api_registry())
    kb.register("api-load.eal" if task["profile"] == "api_load/1" else "availability.eal",
                entry_id=task["entry_id"], context=context, claims=task["claims"],
                label="held-out synthetic accuracy task")
    return {"workspace": str(workspace), "registry": str(registry), "database": str(database),
            "methods": "eal.api_load_methods:registry", "limits": None}


def prepare_case(directory, case):
    """Prepare inputs only; do not assess a claim or expose computed answers."""
    directory = Path(directory)
    demo = prepare_demo(directory)
    profile_index = 0 if case["profile"] == "api_load/1" else 1
    task = deepcopy(demo["tasks"][profile_index])
    task["task_id"] = "held_out_" + case["case_id"]
    task["claims"] = list(case["expected_statuses"])
    task["question"] = ("Assess every selected claim for this identified synthetic input. Preserve all "
                        "registered scope and qualifications, distinguish scope mismatch from unavailable "
                        "results, and make no conclusions about a deployed service.")
    context = deepcopy(task["requirements"]["context"])
    variation = case["variation"]
    if profile_index == 0:
        report_path = directory / "report.json"
        old_raw = report_path.read_bytes()
        report = json.loads(old_raw)
        report["run_id"] = "held-out-load-" + case["case_id"]
        report["concurrent_clients"] = 37
        if variation == "failed_sample_limits":
            report["requests"] = [{"elapsed_ms": 310 + (index % 13), "status_code": 200 if index % 10 else 503}
                                  for index in range(120)]
        else:
            report["requests"] = [{"elapsed_ms": 200, "status_code": 500 if index == 0 else 200}
                                  for index in range(100)]
        new_raw = _json_bytes(report)
        report_path.write_bytes(new_raw)
        source = (directory / "api-load.eal").read_text()
        source = source.replace(hashlib.sha256(old_raw).hexdigest(), hashlib.sha256(new_raw).hexdigest())
        source = source.replace("coordinator-synthetic-load-001", report["run_id"])
        source = source.replace('"concurrent_clients": 10', '"concurrent_clients": 37')
        source = source.replace("10 concurrent clients", "37 concurrent clients")
        (directory / "api-load.eal").write_text(source)
        task["requirements"]["workload"]["run_id"] = report["run_id"]
        task["requirements"]["workload"]["concurrent_clients"] = 37
        if variation == "requested_workload_scope_mismatch":
            task["requirements"]["workload"]["run_id"] = "requested-other-held-out-load"
    else:
        snapshot = json.loads((directory / "availability.json").read_bytes())
        snapshot["value"] = {"heartbeats": 7, "responsive_nodes": 1, "outage_count": 2}
        if variation == "stale_positive_snapshot":
            snapshot["observed_at"] = "2020-01-01T00:00:00Z"
            snapshot["value"] = {"heartbeats": 8, "responsive_nodes": 5, "outage_count": 0}
        raw = _json_bytes(snapshot)
        (directory / "availability.json").write_bytes(raw)
        source = _availability_source(hashlib.sha256(raw).hexdigest())
        if variation == "contested_route_negative_quorum_unobserved_claim":
            source += ('\ncontext environment demo {\n  claim sample_unobserved_route {\n'
                       '    statement "No authored support route establishes this synthetic routing claim."\n'
                       '  }\n}\n')
        (directory / "availability.eal").write_text(source)
    (directory / "demo.json").unlink()
    server = _register(directory, task, context)
    return {"server": server, "task": task}


def copy_case(source, destination, task):
    destination = Path(destination)
    shutil.copytree(source, destination, ignore=shutil.ignore_patterns("*.sqlite*", ".eal", "tools.toml"))
    context = (json.loads((destination / "availability.json").read_bytes())["context"]
               if task["profile"] == "registered_claims/1"
               else {key: json.loads((destination / "report.json").read_bytes())[key]
                     for key in ("service", "build_id", "dataset")})
    return _register(destination, task, context)


def apply_fault(coordinator, case):
    if case["variation"] == "registered_entry_unavailable_after_pin":
        # Simulate an unavailable operator registration only in this fresh
        # synthetic database after pinning. There are no prior observations or
        # assessments; the real correspondence check returns evidence_unavailable.
        with sqlite3.connect(coordinator.server.database) as connection:
            entry_id = coordinator.anchor["task"]["entry_id"]
            connection.execute("DELETE FROM catalogue_revisions WHERE entry_id = ?", (entry_id,))
            connection.execute("DELETE FROM catalogue_entries WHERE entry_id = ?", (entry_id,))


def prepare_study(output, runtime, *, execution_mode="actual_host_agent"):
    output = Path(output).resolve()
    if output.exists() and any(output.iterdir()):
        raise FileExistsError("Accuracy study output must be empty")
    if execution_mode not in {"actual_host_agent", "provider"}:
        raise ValueError("Accuracy measurements require actual_host_agent or provider execution")
    plan = json.loads(PLAN_PATH.read_bytes())
    units = []
    for case in plan["cases"]:
        original = output / "reference-inputs" / case["case_id"]
        prepared = prepare_case(original, case)
        write_json(original.parent / (case["case_id"] + ".json"), prepared)
        for arm in case["arm_order"]:
            unit_id = case["case_id"] + "-" + arm
            storage_id = "unit" + str(len(units) + 1).zfill(2)
            directory = output / "units" / storage_id
            task = deepcopy(prepared["task"])
            server = copy_case(original, directory / "workspace", task)
            spec = {"server": server, "task": task, "budgets": plan["execution"]["budgets"],
                    "transport": {"kind": arm, **({"runtime": str(Path(runtime).resolve())} if arm == "lab" else {})}}
            write_json(directory / "spec.json", spec)
            units.append({"unit_id": unit_id, "storage_id": storage_id,
                          "case_id": case["case_id"], "arm": arm,
                          "spec": str(directory / "spec.json"), "run": str(directory / "run"),
                          "export": str(directory / "export.json"), "task_digest": canonical_digest(task),
                          "spec_sha256": digest_file(directory / "spec.json"),
                          "input_sha256": {path.name: digest_file(path) for path in original.iterdir()
                                           if path.suffix in {".eal", ".json", ".py"}}})
    write_json(output / "frozen-plan.json", plan)
    manifest = {"schema": "EAL/coordination-accuracy-manifest/1", "study_id": plan["study_id"],
                "prepared_at": datetime.now(timezone.utc).isoformat(), "plan_sha256": digest_file(output / "frozen-plan.json"),
                "source_plan_sha256": digest_file(PLAN_PATH),
                "harness_sha256": digest_file(Path(__file__)), "execution_mode": execution_mode,
                "native_model": None, "native_token_usage": None, "native_billing": None,
                "units": units}
    write_json(output / "manifest.json", manifest)
    return manifest


def read_study(output):
    output = Path(output).resolve()
    manifest = json.loads((output / "manifest.json").read_bytes())
    frozen = output / "frozen-plan.json"
    if digest_file(frozen) != manifest["plan_sha256"]:
        raise ValueError("Frozen plan digest changed")
    if digest_file(Path(__file__)) != manifest["harness_sha256"]:
        raise ValueError("Frozen accuracy harness changed")
    for unit in manifest["units"]:
        spec_path = Path(unit["spec"])
        if digest_file(spec_path) != unit["spec_sha256"]:
            raise ValueError("Frozen unit specification changed")
        spec = json.loads(spec_path.read_bytes())
        if canonical_digest(spec["task"]) != unit["task_digest"]:
            raise ValueError("Frozen task changed")
        for filename, digest in unit["input_sha256"].items():
            for workspace in (Path(spec["server"]["workspace"]), output / "reference-inputs" / unit["case_id"]):
                if digest_file(workspace / filename) != digest:
                    raise ValueError("Frozen paired input bytes changed")
    return output, manifest, json.loads(frozen.read_bytes())


def start_unit(output, unit_id):
    output, manifest, plan = read_study(output)
    selected = [unit for unit in manifest["units"] if unit["unit_id"] == unit_id]
    if len(selected) != 1:
        raise ValueError("Select one frozen unit")
    unit = selected[0]
    spec = json.loads(Path(unit["spec"]).read_bytes())
    case = next(case for case in plan["cases"] if case["case_id"] == unit["case_id"])
    with Coordinator.start(unit["run"], **spec) as coordinator:
        apply_fault(coordinator, case)
        return coordinator.status()


def reference_case(source, task, case, directory):
    """Execute an independent trusted reference; no worker result is authored."""
    directory = Path(directory)
    server = copy_case(source, directory / "workspace", task)
    with Coordinator.start(directory / "run", server, task, budgets={"wall_seconds": 900}) as coordinator:
        apply_fault(coordinator, case)
        reservation = coordinator.reserve_worker("assessor", execution_mode="software_test")
        finding = coordinator.query(reservation["call_id"])
        statuses = {claim: finding["assessments"].get(claim, {}).get("status") for claim in task["claims"]}
        check = finding["check"]["code"]
        if statuses != case["expected_statuses"] or check != case["expected_check"]:
            raise ValueError(f"Frozen fixture reference mismatch in {case['case_id']}: {statuses}, {check}")
        oracle = {"schema": "EAL/coordination-accuracy-reference/1", "case_id": case["case_id"],
                  "execution_mode": "software_reference", "statuses": statuses,
                  "check": check, "conclusion": case["expected_conclusion"], "finding": finding,
                  "fixture_truth": fixture_truth(source, case)}
        write_json(directory / "reference.json", oracle)
        coordinator.export(directory / "export.json")
        return oracle


def fixture_truth(source, case):
    """Retain simple independent arithmetic/route facts, never model judging."""
    source = Path(source)
    if case["profile"] == "api_load/1":
        report = json.loads((source / "report.json").read_bytes())
        requests = report["requests"]
        errors = sum(not 200 <= row["status_code"] < 300 for row in requests)
        p95 = sorted(row["elapsed_ms"] for row in requests)[math.ceil(len(requests) * 0.95) - 1]
        rate = errors / len(requests) * 100
        return {"request_count": len(requests), "error_count": errors, "nearest_rank_sample_p95_ms": p95,
                "error_rate_percent": rate, "inclusive_limits_pass": len(requests) >= 100 and p95 <= 200 and rate <= 1,
                "scope_corresponds": case["variation"] != "requested_workload_scope_mismatch"}
    snapshot = json.loads((source / "availability.json").read_bytes())
    stale = case["variation"] == "stale_positive_snapshot"
    return {"value": snapshot["value"], "observed_at": snapshot["observed_at"],
            "max_age_seconds": 86400, "deliberately_stale": stale,
            "heartbeat_predicate": snapshot["value"]["heartbeats"] >= 3,
            "quorum_predicate": snapshot["value"]["responsive_nodes"] >= 2,
            "outage_objection_predicate": snapshot["value"]["outage_count"] >= 1,
            "unobserved_claim_has_support_route": False,
            "registration_available": case["variation"] != "registered_entry_unavailable_after_pin"}


def references(output, *, preflight=False):
    output, manifest, plan = read_study(output)
    destination = output / ("preflight" if preflight else "references")
    result = {}
    if not preflight:
        # Freeze before any reference execution used in the reported scoring.
        # Missing/failed worker units still belong to the denominator.
        for unit in manifest["units"]:
            if not Path(unit["export"]).is_file():
                raise ValueError("Retain every unit's first-attempt export before post-trial references")
    for case in plan["cases"]:
        prepared = json.loads((output / "reference-inputs" / (case["case_id"] + ".json")).read_bytes())
        result[case["case_id"]] = reference_case(output / "reference-inputs" / case["case_id"],
                                               prepared["task"], case, destination / case["case_id"])
    return {case_id: {"statuses": value["statuses"], "check": value["check"]} for case_id, value in result.items()}


def score_answer(answer, anchor, finding, oracle):
    """Independent strict scorer: correct labels alone never imply correctness."""
    task = anchor["task"]
    selected = task["claims"]
    expected = oracle["statuses"]
    failures = []
    if type(answer) is not dict or set(answer) != ANSWER_FIELDS:
        answer = answer if type(answer) is dict else {}
        failures.append("answer_fields")
    if answer.get("task_digest") != anchor["task_digest"] or answer.get("finding_id") != finding["finding_id"]:
        failures.append("finding_identity")
    expected_scope = {"context": task["requirements"]["context"], "requirements": task["requirements"]}
    if canonical_digest(answer.get("scope")) != canonical_digest(expected_scope):
        failures.append("scope")
    if answer.get("qualification") != "conditional_on_registered_argument":
        failures.append("qualification")
    if answer.get("conclusion") != oracle["conclusion"]:
        failures.append("conclusion")
    claims = answer.get("claims")
    if type(claims) is not dict:
        claims = {}
    if set(claims) != set(selected):
        failures.append("claim_selection")
    fidelity = positives = 0
    for claim in selected:
        row = claims.get(claim)
        reference = finding["assessments"].get(claim)
        reference_status = None if reference is None else reference["status"]
        if reference_status != expected[claim]:
            failures.append("unit_reference_status:" + claim)
        if type(row) is not dict or set(row) != {"assessment_id", "status", "assessed_at"}:
            failures.append("claim_fields:" + claim)
            row = row if type(row) is dict else {}
        if "status" in row and row["status"] == expected[claim]:
            fidelity += 1
        if row.get("status") == "supported" and expected[claim] != "supported":
            positives += 1
        wanted = {name: None if reference is None else reference[name]
                  for name in ("assessment_id", "status", "assessed_at")}
        if canonical_digest(row) != canonical_digest(wanted):
            failures.append("claim_identity_status_time:" + claim)
        if reference is not None:
            try:
                if parse_time(row.get("assessed_at")) < parse_time(anchor["pinned_at"]):
                    failures.append("stale_assessment:" + claim)
            except (TypeError, ValueError):
                failures.append("invalid_assessment_time:" + claim)
    return {"correct": not failures, "failures": failures,
            "claim_status_correct": fidelity, "selected_claims": len(selected),
            "unsupported_positive_claims": positives,
            "unassessed_reference_claims": sum(status is None for status in expected.values())}


def _first_response(effect):
    if effect is None or effect.get("result") is None:
        return None, "missing"
    result = effect["result"]
    try:
        raw = base64.b64decode(result["raw_base64"], validate=True)
        if hashlib.sha256(raw).hexdigest() != result["raw_digest"]:
            return None, "raw_digest_mismatch"
        decoded = strict_json(raw)
        response = decoded["response"] if set(decoded) == {"response", "execution"} else decoded
        if type(response) is not dict:
            return None, "invalid_first_response"
        if result["response"] != response:
            return None, "retained_response_mismatch"
        return response, None
    except (ValueError, TypeError, KeyError, UnicodeError):
        return None, "invalid_first_bytes"


def score_assessor(response, anchor, finding, oracle):
    if type(response) is not dict or set(response) != {"message", "consumed_message_ids"}:
        return ["assessor_response_fields"]
    message = response["message"]
    if type(message) is not dict:
        return ["assessor_message_fields"]
    fields = {"schema", "kind", "message_id", "task_id", "task_digest", "sender", "recipient",
              "reply_to", "attempt", "finding_id"}
    assessed = oracle["check"] is None
    fields |= {"assessment_refs"} if assessed else {"code", "outcome"}
    errors = []
    if set(message) != fields:
        errors.append("assessor_message_fields")
    for name, wanted in {"schema": "EAL/MAS-coordination/3", "kind": "outcome" if assessed else "disposition",
                         "task_id": anchor["task"]["task_id"], "task_digest": anchor["task_digest"],
                         "sender": "assessor", "recipient": "reviewer", "reply_to": "request",
                         "finding_id": finding["finding_id"]}.items():
        if message.get(name) != wanted:
            errors.append("assessor_" + name)
    if type(message.get("attempt")) is not int or message["attempt"] != 0:
        errors.append("assessor_attempt")
    if type(message.get("message_id")) is not str or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:/-]{0,127}", message["message_id"]) is None:
        errors.append("assessor_message_id")
    if assessed:
        expected_refs = {claim: row["assessment_id"] for claim, row in finding["assessments"].items()}
        if message.get("assessment_refs") != expected_refs:
            errors.append("assessor_assessment_refs")
    else:
        if message.get("code") != oracle["check"]:
            errors.append("assessor_code")
        if message.get("outcome") != ("rejected" if oracle["conclusion"] == "out_of_scope" else "incomplete"):
            errors.append("assessor_disposition")
    return errors


def score_export(export, oracle, execution_mode):
    workers = {role: next((effect for effect in export["effects"] if effect["key"] == "worker:" + role), None)
               for role in ("assessor", "reviewer")}
    responses = {role: _first_response(effect) for role, effect in workers.items()}
    rows = {role: {"present": effect is not None and effect.get("result") is not None,
                   "accepted": effect is not None and effect.get("result") is not None
                               and effect["result"].get("accepted") is True,
                   "raw_problem": responses[role][1],
                   "execution_mode": None if effect is None else effect["payload"]["execution_mode"],
                   "execution_id": None if effect is None or effect.get("result") is None else effect["result"]["execution_id"]}
            for role, effect in workers.items()}
    issued = [event["data"]["finding_id"] for event in export["events"] if event["kind"] == "query"]
    effects = [effect for effect in export["effects"] if effect["key"] == "assessment"]
    finding = None
    if effects and effects[0].get("result") is not None:
        finding = effects[0]["result"]
    # The caller supplies the retained exact first issued finding separately.
    finding = export.get("accuracy_finding", finding)
    if finding is None:
        finding = {"finding_id": issued[-1] if issued else None, "assessments": {}}
    reviewer, problem = responses["reviewer"]
    answer = {} if reviewer is None else reviewer.get("answer", {})
    metrics = score_answer(answer, export["config"]["anchor"], finding, oracle)
    role_errors = []
    role_errors.extend(score_assessor(responses["assessor"][0], export["config"]["anchor"], finding, oracle))
    for role, row in rows.items():
        if not row["accepted"] or row["raw_problem"] or row["execution_mode"] != execution_mode:
            role_errors.append(role + "_first_attempt")
        effect = workers[role]
        response = responses[role][0]
        if effect and response:
            expected_consumed = [message["message_id"] for message in effect["payload"]["context"]["received_messages"]]
            if response.get("consumed_message_ids") != expected_consumed:
                role_errors.append(role + "_handoff")
    if rows["assessor"]["execution_id"] == rows["reviewer"]["execution_id"]:
        role_errors.append("independent_execution_identity")
    metrics["semantic_answer_correct"] = metrics["correct"]
    metrics["failures"].extend(role_errors)
    metrics["correct"] = not metrics["failures"]
    metrics.update(workers=rows, repairs=0)
    return metrics


def wilson(successes, total):
    if not total:
        return None
    z = 1.959963984540054
    center = (successes / total + z * z / (2 * total)) / (1 + z * z / total)
    margin = z * math.sqrt(successes / total * (1 - successes / total) / total + z * z / (4 * total * total)) / (1 + z * z / total)
    return [max(0, center - margin), min(1, center + margin)]


def score_study(output):
    output, manifest, plan = read_study(output)
    scored = []
    for unit in manifest["units"]:
        export_path = Path(unit["export"])
        export = json.loads(export_path.read_bytes())
        oracle = json.loads((output / "references" / unit["case_id"] / "reference.json").read_bytes())
        # Read the exact issued finding by identity, rather than invent a null
        # finding for unknown effects or trust a model-supplied result.
        finding_path = export_path.with_name("first-issued-finding.json")
        query_ids = [event["data"]["finding_id"] for event in export["events"] if event["kind"] == "query"]
        if finding_path.is_file():
            export["accuracy_finding"] = json.loads(finding_path.read_bytes())
            if not query_ids or export["accuracy_finding"]["finding_id"] != query_ids[0]:
                raise ValueError("Retained first finding differs from first query event")
        elif query_ids:
            with Coordinator(unit["run"]) as coordinator:
                export["accuracy_finding"] = coordinator.state.finding(query_ids[0])
            write_json(finding_path, export["accuracy_finding"])
        if "accuracy_finding" in export:
            finding = export["accuracy_finding"]
            wanted_id = "finding_" + canonical_digest({key: value for key, value in finding.items() if key != "finding_id"})
            if finding.get("finding_id") != wanted_id:
                raise ValueError("Retained first finding content digest differs from emitted finding ID")
        metrics = score_export(export, oracle, manifest["execution_mode"])
        scored.append({"unit_id": unit["unit_id"], "case_id": unit["case_id"], "arm": unit["arm"],
                       "export_sha256": digest_file(export_path),
                       "first_finding_sha256": digest_file(finding_path) if finding_path.is_file() else None,
                       **metrics})
    summary = {}
    for arm in plan["arms"]:
        values = [row for row in scored if row["arm"] == arm]
        correct = sum(row["correct"] for row in values)
        summary[arm] = {"task_correct": correct, "tasks": len(values),
                        "semantic_answer_correct": sum(row["semantic_answer_correct"] for row in values),
                        "task_accuracy": correct / len(values), "task_accuracy_wilson_95": wilson(correct, len(values)),
                        "claim_status_correct": sum(row["claim_status_correct"] for row in values),
                        "selected_claims": sum(row["selected_claims"] for row in values),
                        "unsupported_positive_claims": sum(row["unsupported_positive_claims"] for row in values),
                        "unassessed_reference_claims": sum(row["unassessed_reference_claims"] for row in values),
                        "missing_worker_responses": sum(not role["present"] for row in values for role in row["workers"].values()),
                        "rejected_worker_responses": sum(role["present"] and not role["accepted"] for row in values for role in row["workers"].values()),
                        "repairs": 0}
    pairs = []
    for case in plan["cases"]:
        pair = {row["arm"]: row["correct"] for row in scored if row["case_id"] == case["case_id"]}
        pairs.append({"case_id": case["case_id"], **pair})
    rust_only = sum(pair["lab"] and not pair["json"] for pair in pairs)
    json_only = sum(pair["json"] and not pair["lab"] for pair in pairs)
    discordant = rust_only + json_only
    pvalue = min(1, 2 * sum(math.comb(discordant, index) for index in range(min(rust_only, json_only) + 1)) / 2 ** discordant) if discordant else 1.0
    report = {"schema": "EAL/coordination-accuracy-report/1", "study_id": manifest["study_id"],
              "plan_sha256": manifest["plan_sha256"], "execution_mode": manifest["execution_mode"],
              "model": None, "token_usage": None, "billing": None, "summary": summary, "pairs": pairs,
              "paired_disagreements": {"lab_only_correct": rust_only, "json_only_correct": json_only,
                                       "exact_sign_test_two_sided_p": pvalue},
              "units": scored, "limitations": plan["analysis"]}
    write_json(output / "report.json", report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("prepare", "start", "preflight", "reference", "score"))
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--runtime", default="/workspace/mas-protocol-lab")
    parser.add_argument("--unit")
    parser.add_argument("--execution-mode", choices=("actual_host_agent", "provider"), default="actual_host_agent")
    args = parser.parse_args()
    if args.operation == "prepare":
        result = prepare_study(args.output, args.runtime, execution_mode=args.execution_mode)
    elif args.operation == "start":
        result = start_unit(args.output, args.unit)
    elif args.operation in {"preflight", "reference"}:
        result = references(args.output, preflight=args.operation == "preflight")
    else:
        result = score_study(args.output)
    print(json.dumps(result, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
