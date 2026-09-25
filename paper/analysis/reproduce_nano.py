"""Extract and replay the historical nano-only v3.1 pilot, without provider calls.

The preserved scorer and summary are verified against the run manifest before
import. Extraction retains every assignment, raw case, response text, protocol
error and tool receipt. Duplicated provider objects and replay handles are omitted.
"""
from __future__ import annotations

import argparse
from collections import Counter
from decimal import Decimal
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import zipfile

PAPER = Path(__file__).resolve().parents[1]
DATA = PAPER / "data" / "nano-v3"
ORIGINAL = PAPER / "analysis" / "nano_v3_original"
ARCHIVE_SHA256 = "186adeb144ccaf4c77f5e36165999f3ad203a98bcfc24a7119c68d5c5eb206c5"
ARMS = ["eal_mcp", "json_prompt", "plain_brief", "plain_explicit", "plain_review", "plain_validator"]
LABELS = ["EAL/MCP", "JSON prompt", "Brief prose", "Explicit prose", "Review prose", "Plain validator"]


def require(condition, message):
    if not condition:
        raise ValueError(message)


def write(path, value):
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n")


def load(path):
    return json.loads(path.read_text())


def extract(archive, data):
    require(hashlib.sha256(archive.read_bytes()).hexdigest() == ARCHIVE_SHA256,
            "Archive differs from the supplied run 36176588712 artefact")
    data.mkdir(parents=True, exist_ok=True)
    members = {}
    with zipfile.ZipFile(archive) as z:
        require(len(z.namelist()) == len(set(z.namelist())), "Duplicate archive member")

        def read(name):
            raw = z.read(name)
            members[name] = hashlib.sha256(raw).hexdigest()
            return json.loads(raw)

        manifest = read("run/manifest.json")
        freeze = read("run/case-manifest.json")
        payloads = {"historical-manifest.json": manifest, "case-manifest.json": freeze,
                    "original-summary.json": read("run/summary.json"),
                    "completion.json": read("run/completion.json"),
                    "budget.json": read("run/budget-gpt-4.1-nano-2025-04-14.json")}
        cases = [read(f"run/cases/{key}/case.json") for key in sorted(freeze["cases"])]
        trials, receipts = [], []
        for assignment in manifest["assignments"]:
            prefix = f"run/trials/{assignment['id']}/"
            original = read(prefix + "trial.json")
            trial = {k: v for k, v in original.items() if k not in {"model_calls", "model_spec"}}
            trial["model_calls"] = []
            for original_call in original.get("model_calls", []):
                call = {k: v for k, v in original_call.items() if k != "response"}
                response = original_call.get("response")
                call["response"] = None
                if response:
                    call["response"] = {k: response[k] for k in
                                        ("model", "input_tokens", "output_tokens", "text")}
                    call["response"]["metadata"] = {k: v for k, v in response.get("metadata", {}).items()
                                                     if k not in {"id", "responses_replay_handle", "visible_output"}}
                trial["model_calls"].append(call)
            trials.append(trial)
            if prefix + "transcript.json" in z.namelist():
                messages = read(prefix + "transcript.json")
                packets, after_turn = [], -1
                for message in messages:
                    if message["role"] == "assistant":
                        after_turn += 1
                    content = message.get("content") or ""
                    if content.startswith("HOST OPERATION RESULT (data):\n"):
                        packets.append({"after_turn": after_turn, "packet": json.loads(content.split("\n", 1)[1])})
                receipts.append({"id": trial["id"], "packets": packets,
                                 "tool_trace": read(prefix + "tool-trace.json")})
    for name, value in payloads.items():
        write(data / name, value)
    for name, values in (("cases.jsonl", cases), ("trials.jsonl", trials), ("receipts.jsonl", receipts)):
        (data / name).write_text("".join(json.dumps(value, sort_keys=True) + "\n" for value in values))
    filenames = [*payloads, "cases.jsonl", "trials.jsonl", "receipts.jsonl"]
    write(data / "provenance.json", {
        "schema": "eal-paper-nano-evidence/1", "archive_sha256": ARCHIVE_SHA256,
        "github_run_id": 36176588712, "github_run_attempt": 1,
        "archive_url": "https://github.com/emmett08/earl/actions/runs/36176588712",
        "run_commit": manifest["commit"], "protocol": manifest["plan"]["version"],
        "projection": "All assignments, raw cases, final answers, scores, protocol errors, response text, accounting, model-visible host packets and full tool traces retained. Provider object duplicates and replay handles omitted. Historical source files verified against manifest.",
        "source_member_sha256": members,
        "derived_file_sha256": {name: hashlib.sha256((data / name).read_bytes()).hexdigest() for name in filenames}})


def original_module(name, manifest):
    for path in ORIGINAL.iterdir():
        if path.is_file():
            require(hashlib.sha256(path.read_bytes()).hexdigest()
                    == manifest["files"]["experiments/api_load_test/" + path.name],
                    f"Changed historical source: {path.name}")
    spec = importlib.util.spec_from_file_location("paper_nano_v3_" + name, ORIGINAL / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def parsed_response(call):
    try:
        value = json.loads((call.get("response") or {}).get("text", ""))
        return value if isinstance(value, dict) else {}
    except ValueError:
        return {}


def reproduce(data, output):
    provenance = load(data / "provenance.json")
    for name, digest in provenance["derived_file_sha256"].items():
        require(hashlib.sha256((data / name).read_bytes()).hexdigest() == digest, "Changed input: " + name)
    manifest = load(data / "historical-manifest.json")
    oracle, analysis = original_module("oracle", manifest), original_module("analysis", manifest)
    cases_list = [json.loads(line) for line in (data / "cases.jsonl").read_text().splitlines()]
    cases = {case["id"]: case for case in cases_list}
    trials = [json.loads(line) for line in (data / "trials.jsonl").read_text().splitlines()]
    receipts_list = [json.loads(line) for line in (data / "receipts.jsonl").read_text().splitlines()]
    receipts = {row["id"]: row for row in receipts_list}
    by_id = {row["id"]: row for row in trials}
    freeze = load(data / "case-manifest.json")
    require(len(cases) == len(cases_list) == 40 and set(cases) == set(freeze["cases"]), "Case identities differ")
    require(len(by_id) == len(trials) == len(manifest["assignments"]) == 240, "Assignment identities differ")
    require(len(receipts) == len(receipts_list), "Duplicate receipt")
    for key, case in cases.items():
        require(hashlib.sha256(json.dumps(case, sort_keys=True).encode()).hexdigest() == freeze["cases"][key],
                "Changed case: " + key)
    host_checks, packet_counts, attempted, known_cost, unknown_cost = 0, Counter(), 0, Decimal(0), 0
    rates = manifest["models"][0]["pricing"]
    for assigned in manifest["assignments"]:
        row = by_id[assigned["id"]]
        require(all(row.get(k) == v for k, v in assigned.items()), "Assignment changed")
        if row["state"] == "not_attempted":
            require(not row.get("answer") and not row.get("model_calls"), "Unattempted assignment has output")
            continue
        attempted += 1
        case = cases[row["case_id"]]
        truth = oracle.reference(case)
        require(truth == row["reference"], "Reference differs: " + row["id"])
        require(row["case_sha256"] == freeze["cases"][row["case_id"]], "Trial case digest differs")
        grade = oracle.grade(row.get("answer"), truth, collected=row.get("collected", False),
                             inspected_report_ids=row.get("inspected_report_ids", []))
        checks = row.get("host_checks", [])
        grade["host_agrees_with_reference"] = all(x["agrees"] for x in checks) if checks else None
        if row.get("failure"):
            grade["correct"] = False
        require(grade == row["outcome"], "Score differs: " + row["id"])
        host_checks += len(checks)
        require(row["id"] in receipts, "Missing attempted receipt")
        checked_packets = {}
        for item in receipts[row["id"]]["packets"]:
            packet = item["packet"]
            if "report_id" not in packet or "metrics" not in packet:
                continue
            report_id = packet["report_id"]
            check = oracle.packet_reference_check(case, report_id, packet,
                checked=row["arm"] in {"eal_mcp", "plain_validator"},
                host_status=row.get("host_assessments", {}).get(report_id, {}).get("host_status"))
            require(check["agrees"], "Host packet disagrees: " + row["id"])
            checked_packets[report_id] = check
            packet_counts[row["arm"]] += 1
        require({x["report_id"]: x for x in checks} == checked_packets, "Recorded host check differs")
        for call in row["model_calls"]:
            response = call.get("response")
            if response is None:
                require(call.get("estimated_usd") is None, "Missing response with settled cost")
                unknown_cost += 1
                continue
            require(response["model"] == row["model"], "Snapshot mismatch")
            cached = response["metadata"].get("cached_input_tokens", 0)
            amount = ((response["input_tokens"] - cached) * Decimal(str(rates["input_usd_per_million"]))
                      + cached * Decimal(str(rates["cached_input_usd_per_million"]))
                      + response["output_tokens"] * Decimal(str(rates["output_usd_per_million"]))) / 1_000_000
            require(abs(amount - Decimal(str(call["estimated_usd"]))) < Decimal("0.0000000001"), "Cost differs")
            known_cost += amount
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        write(root / "manifest.json", manifest)
        write(root / "case-manifest.json", freeze)
        for case in cases.values():
            dest = root / "cases" / case["id"] / "case.json"
            dest.parent.mkdir(parents=True)
            write(dest, case)
        for row in trials:
            dest = root / "trials" / row["id"] / "trial.json"
            dest.parent.mkdir(parents=True)
            write(dest, row)
        summary = analysis.summarise(root)
    require(summary == load(data / "original-summary.json"), "Historical summary differs")
    eal = [t for t in trials if t["arm"] == "eal_mcp"]
    eal_attempted = [t for t in eal if t["state"] != "not_attempted"]
    complete = [t for t in eal if t["state"] == "complete"]
    failed = [t for t in eal if t["state"] == "failed"]
    components = Counter(key for t in complete for key, value in t["outcome"].items()
                         if key.endswith("_correct") and value is False)
    first_success = []
    semantic_partial = []
    for row in eal_attempted:
        first = parsed_response(row["model_calls"][0])
        receipt = receipts[row["id"]]
        trace = receipt["tool_trace"]
        if (first.get("operation") == "assess_load_test"
                and any(item["after_turn"] == 0 and "metrics" in item["packet"] for item in receipt["packets"])
                and all(any(item.get("tool") == name and item.get("is_error") is False for item in trace)
                        for name in ("eal_validate", "eal_collect", "eal_reason", "eal_explain"))):
            first_success.append(row["id"])
        if row["state"] == "failed":
            for call in row["model_calls"]:
                answer = parsed_response(call)
                grade = oracle.grade(answer, row["reference"], collected=True,
                                     inspected_report_ids=row["inspected_report_ids"])
                if grade["correct"]:
                    semantic_partial.append({"id": row["id"], "turn": call["turn"],
                                             "missing_explanation": "explanation" not in answer,
                                             "operation": answer.get("operation")})
    stop_trials = [row for row in trials if row.get("stop_model")]
    require(len(stop_trials) == 1, "Stop count differs")
    stopper = stop_trials[0]
    stop_call = stopper["model_calls"][-1]
    diagnosis = {
        "schema": "eal-paper-nano-diagnosis/1", "run_id": 36176588712, "plan_version": manifest["plan"]["version"],
        "assigned": len(trials), "attempted": attempted, "states": dict(Counter(t["state"] for t in trials)),
        "host_checks_verified": host_checks, "packet_counts_verified": dict(packet_counts),
        "model_calls": sum(len(t.get("model_calls", [])) for t in trials),
        "known_cost_usd": str(known_cost), "unknown_cost_calls": unknown_cost,
        "scores_and_summary": "exact_match", "eal_packets_verified": packet_counts["eal_mcp"],
        "eal_partition": {"assigned": len(eal), "attempted": len(eal_attempted),
                          "correct": sum(t["outcome"]["correct"] for t in complete),
                          "completed_incorrect": sum(not t["outcome"]["correct"] for t in complete),
                          "model_call_limit": sum(t.get("failure") == "model_call_limit" for t in failed),
                          "not_attempted": sum(t["state"] == "not_attempted" for t in eal)},
        "eal_completed_error_components": {key.removesuffix("_correct") + "_incorrect": value
                                            for key, value in components.items()},
        "eal_status_confusion": [{"reference": a, "answer": b, "count": n}
                                  for (a, b), n in sorted(Counter((t["reference"]["status"], t["answer"]["status"])
                                                                for t in complete).items())],
        "eal_first_assessment_success": len(first_success), "eal_first_assessment_trial_ids": first_success,
        "eal_failed_call_counts": dict(Counter(str(len(t["model_calls"])) for t in failed)),
        "eal_second_response_missing_operation": sum("operation" not in parsed_response(t["model_calls"][1])
                                                     for t in eal_attempted),
        "eal_failed_second_response_missing_operation": sum("operation" not in parsed_response(t["model_calls"][1])
                                                            for t in failed),
        "eal_failed_semantically_correct_partial_responses": semantic_partial,
        "eal_failed_semantically_correct_partial_trials": len({x["id"] for x in semantic_partial}),
        "eal_protocol_error_messages": dict(Counter(e["message"].split("\n")[0]
                                                   for t in eal_attempted for e in t.get("protocol_errors", []))),
        "stop": {"trial_id": stopper["id"], "arm": stopper["arm"], "category": stopper["failure"],
                 "http_status": stop_call["diagnostics"]["http_status"], "retryable": stop_call["retryable"],
                 "cost_known": stop_call["estimated_usd"] is not None,
                 "skipped": sum(t["state"] == "not_attempted" for t in trials),
                 "eal_skipped": sum(t["state"] == "not_attempted" for t in eal)},
        "examples": [{"id": t["id"], "case_id": t["case_id"], "reference": t["reference"], "answer": t["answer"]}
                     for t in eal if t["id"] in {"3be13f29f43d8d64481b", "556e92ace9823696be5b",
                                                 "6f7433cdd94abbe33f0b"}]}
    output.mkdir(parents=True, exist_ok=True)
    write(output / "nano-summary.json", summary)
    write(output / "nano-diagnosis.json", diagnosis)
    cells = {cell["arm"]: cell for cell in summary["cells"]}
    lines = [label + " & " + f"{cells[arm]['correct']}/40" + " & "
             + " & ".join(str(cells[arm][k]) for k in ("completed", "failed", "not_attempted")) + r" \\"
             for arm, label in zip(ARMS, LABELS)]
    (output / "nano-outcome-rows.tex").write_text("\n".join(lines) + "\n")
    print(json.dumps({k: diagnosis[k] for k in ("assigned", "attempted", "states", "scores_and_summary",
                                               "eal_partition", "eal_completed_error_components", "stop")}, indent=2))
    return diagnosis


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--extract", type=Path, help="Regenerate curated inputs from the exact supplied ZIP")
    parser.add_argument("--data", type=Path, default=DATA)
    parser.add_argument("--output", type=Path, default=PAPER / "results")
    args = parser.parse_args()
    if args.extract:
        extract(args.extract, args.data)
    reproduce(args.data, args.output)
