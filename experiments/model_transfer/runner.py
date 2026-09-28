"""Bounded automated pilot across low-cost model and native-tool configurations."""
from __future__ import annotations

import argparse
import hashlib
import json
import random
from pathlib import Path
import subprocess
import time

from experiments.transfer_study.workspace import read_json, utc_now, write_json
from .cases import CASES, FIRST, Case, Project
from .provider import BudgetedClient, ExecutionStopped, OpenAITransport, Transport

TOOL = {"type": "function", "name": "probe", "description": "Read the current orders-service latency report.",
        "strict": True, "parameters": {"type": "object", "properties": {}, "required": [],
                                        "additionalProperties": False}}
OUTPUT = ('Return one JSON object with decision (ready, not_ready, or undetermined), '
          'basis (criterion_met, criterion_failed, measurement_missing, assumption_expired, '
          'or evidence_unavailable), explanation (brief text), and files (an object of optional '
          'new .md/.txt project files to retain if useful for the project). Do not return markdown fences. '
          'An EAL unsupported status does not by itself establish not_ready. ')


def load_plan(path: Path) -> dict:
    plan = read_json(path)
    if plan.get("schema") != "EAL/model-transfer-plan/1":
        raise ValueError("Invalid model transfer plan")
    if isinstance(plan.get("budget_usd"), bool) or not isinstance(plan.get("budget_usd"), (int, float)) or not 0 < plan["budget_usd"] <= 2:
        raise ValueError("This pilot permits an API budget in (0, 2] USD")
    for field, maximum in (("max_calls_per_session", 3), ("max_output_tokens", 4096),
                           ("max_request_bytes", 32768), ("request_timeout_seconds", 90)):
        if type(plan.get(field)) is not int or not 1 <= plan[field] <= maximum:
            raise ValueError(f"Invalid {field}")
    if set(plan["models"]) != {"plain", "reasoning"}:
        raise ValueError("Configure the plain and reasoning model families")
    if type(plan.get("seed")) is not int:
        raise ValueError("Seed must be an integer")
    for name, model in plan["models"].items():
        if not isinstance(model.get("version"), str) or not model["version"]:
            raise ValueError("Pinned model version is required")
        expected = None if name == "plain" else "low"
        if model.get("reasoning_effort") != expected:
            raise ValueError("Use no reasoning parameter for plain, low for reasoning")
        for key in ("input_per_million", "output_per_million"):
            if type(model.get(key)) not in (int, float) or not 0 < model[key] <= 10:
                raise ValueError("Positive finite price required")
    if plan["models"]["plain"]["version"] == plan["models"]["reasoning"]["version"]:
        raise ValueError("The reasoning-family comparison needs distinct model versions")
    return plan


class SessionRunner:
    """Replay all response items within one session; create a fresh list for each new session."""

    def __init__(self, client: BudgetedClient, plan: dict):
        self.client, self.plan = client, plan

    def run(self, project: Project, model: dict, native_tools: bool, session_id: str) -> dict:
        start = time.monotonic()
        question = f"Assess the orders service now at {FIRST if project.stage == 'initial' else project.case.later_at}. "
        messages = [{"role": "system", "content": "Complete the engineering task using the supplied project and available tools. Keep unsupported conclusions qualified."}]
        result = {"session_id": session_id, "stage": project.stage, "model": model["version"],
                  "reasoning_effort": model["reasoning_effort"], "native_tools": native_tools,
                  "status": "no_answer", "answer": None}
        try:
            messages.extend(project.context(question))
            messages.append({"role": "user", "content": question + OUTPUT +
                             "\nProject files:\n" + json.dumps(project.files())})
            result["initial_messages"] = messages.copy()
            for _ in range(self.plan["max_calls_per_session"]):
                response = self.client.request(model, messages, [TOOL] if native_tools else [], session_id)
                output = response["output"]
                messages.extend(output)  # Includes opaque reasoning items required for tool continuation.
                calls = [item for item in output if item.get("type") == "function_call"]
                if calls:
                    if not native_tools:
                        raise ValueError("Model requested an unavailable tool")
                    for call in calls:
                        if call.get("name") != "probe" or json.loads(call["arguments"]) != {}:
                            tool_output = {"error": "Only probe with empty arguments is available"}
                        else:
                            tool_output = project.probe()
                        messages.append({"type": "function_call_output", "call_id": call["call_id"],
                                         "output": json.dumps(tool_output)})
                    continue
                text = "".join(part["text"] for item in output if item.get("type") == "message"
                               for part in item.get("content", []) if part.get("type") == "output_text")
                result["raw_answer"] = text
                answer = json.loads(text)
                if (answer.get("decision") not in ("ready", "not_ready", "undetermined") or
                        answer.get("basis") not in ("criterion_met", "criterion_failed", "measurement_missing",
                                                     "assumption_expired", "evidence_unavailable") or
                        not isinstance(answer.get("explanation"), str)):
                    raise ValueError("Answer does not match the declared outcome format")
                project.persist(answer.get("files", {}))
                result.update(status="submitted", answer=answer)
                break
        except ExecutionStopped:
            raise
        except Exception as exc:
            result.update(status="failed", error={"type": type(exc).__name__, "message": str(exc)[:1000]})
        finally:
            result["elapsed_seconds"] = time.monotonic() - start
            result["events"] = [event for event in project.events if event["stage"] == project.stage]
            write_json(project.root / f"{project.stage}.json", result)
        return result


class Pilot:
    def __init__(self, plan: dict, root: Path, transport: Transport):
        self.plan, self.root = plan, root
        self.client = BudgetedClient(root, plan, transport)
        self.sessions = SessionRunner(self.client, plan)

    def run(self) -> dict:
        assignments = [{"case": case.identifier, "receiver": receiver, "native_tools": tools,
                        "arm": arm, "donor": "plain" if index % 2 == 0 else "reasoning"}
                       for index, case in enumerate(CASES) for receiver in self.plan["models"]
                       for tools in (False, True) for arm in ("ordinary", "eal")]
        random.Random(self.plan["seed"]).shuffle(assignments)
        write_json(self.root / "assignments.json", assignments)
        rows, stop = [], None
        for allocation in assignments:
            if stop:
                rows.append({**allocation, "status": "not_run", "reason": stop})
                continue
            case = next(x for x in CASES if x.identifier == allocation["case"])
            identifier = f"{case.identifier}.{allocation['receiver']}.tools{int(allocation['native_tools'])}.{allocation['arm']}"
            setup_started = time.monotonic()
            project = Project(self.root / "sequences" / identifier, case, allocation["arm"])
            setup_seconds = time.monotonic() - setup_started
            try:
                # Initial work has tools in both arms; the recipient's capabilities vary in the new session.
                initial = self.sessions.run(project, self.plan["models"][allocation["donor"]], True, identifier + ".initial")
                write_json(project.root / "initial-files.json", project.files())
                project.set_stage("later")
                later = self.sessions.run(project, self.plan["models"][allocation["receiver"]],
                                          allocation["native_tools"], identifier + ".later")
                oracle = case.oracle("later")
                answer = later["answer"] or {}
                rows.append({**allocation, "status": "complete", "initial": initial, "later": later,
                             "setup_seconds": setup_seconds,
                             "oracle": oracle, "reference_decision_match": answer.get("decision") == oracle["decision"],
                             "reference_decision_and_basis_match": all(answer.get(k) == v for k, v in oracle.items())})
            except ExecutionStopped as exc:
                stop = str(exc)
                rows.append({**allocation, "status": "stopped", "reason": stop})
            write_json(self.root / "rows.json", rows)
            print(f"{len(rows)}/{len(assignments)} sequences recorded", flush=True)
        write_json(self.root / "rows.json", rows)
        summaries = []
        for receiver in self.plan["models"]:
            for tools in (False, True):
                for arm in ("ordinary", "eal"):
                    selected = [row for row in rows if (row["receiver"], row["native_tools"], row["arm"]) == (receiver, tools, arm)]
                    complete = [row for row in selected if row["status"] == "complete"]
                    suffix = f".{receiver}.tools{int(tools)}.{arm}."
                    calls = [row for row in self.client.records if suffix in row["session_id"]]
                    events = [event for row in complete for stage in ("initial", "later")
                              for event in row[stage]["events"]]
                    summaries.append({"receiver": receiver, "native_tools": tools, "arm": arm,
                                      "planned": len(selected), "completed": len(complete),
                                      "reference_decision_matches": sum(row["reference_decision_match"] for row in complete),
                                      "reference_decision_and_basis_matches": sum(row["reference_decision_and_basis_match"] for row in complete),
                                      "failed_later_sessions": sum(row["later"]["status"] != "submitted" for row in complete),
                                      "qualified_unavailable_answers": sum((row["later"]["answer"] or {}).get("basis") == "evidence_unavailable" for row in complete),
                                      "later_seconds": sum(row["later"]["elapsed_seconds"] for row in complete),
                                      "initial_seconds": sum(row["initial"]["elapsed_seconds"] for row in complete),
                                      "setup_seconds": sum(row["setup_seconds"] for row in complete),
                                      "api_attempts": len(calls),
                                      "later_api_attempts": sum(row["session_id"].endswith(".later") for row in calls),
                                      "known_input_tokens": sum(row.get("response", {}).get("usage", {}).get("input_tokens", 0) for row in calls),
                                      "known_output_tokens": sum(row.get("response", {}).get("usage", {}).get("output_tokens", 0) for row in calls),
                                      "known_reasoning_tokens": sum(row.get("response", {}).get("usage", {}).get("output_tokens_details", {}).get("reasoning_tokens", 0) for row in calls),
                                      "cost_estimate_usd": sum(row["cost_estimate_usd"] or 0 for row in calls),
                                      "unknown_cost_attempts": sum(row["cost_estimate_usd"] is None for row in calls),
                                      "native_tool_calls": sum(event["kind"] == "native_probe" for event in events),
                                      "later_eal_reused": sum(event["assessment"]["reused_count"] for event in events if event["kind"] == "eal_assess" and event["stage"] == "later"),
                                      "later_eal_collected": sum(event["assessment"]["collected_count"] for event in events if event["kind"] == "eal_assess" and event["stage"] == "later")})
        report = {"schema": "EAL/model-transfer-result/1", "status": "partial" if stop else "complete",
                  "stop_reason": stop, "created_at": utc_now().isoformat(), "summaries": summaries,
                  "api_attempts": len(self.client.records),
                  "estimated_cost_usd": sum(row["cost_estimate_usd"] or 0 for row in self.client.records),
                  "unknown_cost_attempts": sum(row["cost_estimate_usd"] is None for row in self.client.records),
                  "charged_or_reserved_usd": sum(row["charged_or_reserved_usd"] for row in self.client.records),
                  "scope": "Exploratory selected-case model-session reuse with pre-authored EAL. "
                  "Native tools disabled is an access restriction, not an intrinsic model incapacity. "
                  "Reasoning is confounded with model family; no human-developer or general model-class effect. "
                  "Six cases recur across configurations; prompt calls are not independent samples."}
        write_json(self.root / "report.json", report)
        return report


def main() -> None:
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--plan", type=Path, default=Path(__file__).with_name("plan.json"))
    cli.add_argument("--output", type=Path, required=True)
    args = cli.parse_args()
    plan = load_plan(args.plan)
    if args.output.exists():
        raise ValueError("Use a new run directory; attempts must never be overwritten")
    args.output.mkdir(parents=True)
    write_json(args.output / "plan.json", plan)
    try:
        revision = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        revision = None
    write_json(args.output / "provenance.json", {"revision": revision, "started_at": utc_now().isoformat(),
               "plan_sha256": hashlib.sha256(args.plan.read_bytes()).hexdigest()})
    try:
        result = Pilot(plan, args.output, OpenAITransport()).run()
    except ExecutionStopped as exc:
        write_json(args.output / "report.json", {"status": "blocked", "reason": str(exc), "api_attempts": 0})
        raise SystemExit(str(exc)) from exc
    print(json.dumps(result, indent=2))
    if result["status"] != "complete":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
