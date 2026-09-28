"""Blind independent scoring and paired cross-session effect estimates."""

from __future__ import annotations

import hashlib
from collections import defaultdict
from pathlib import Path
from typing import Any

from .design import TRANSFERS, repeated_developers
from .inference import BoundedPairedEstimator, OutcomeBounds
from .workspace import StudyRun, read_json, write_json


def blind_id(run: StudyRun, session_id: str) -> str:
    digest = hashlib.sha256(f"{run.design.digest}:{session_id}".encode()).hexdigest()
    return digest[:24]


def export_answers(run: StudyRun) -> dict:
    """Give assessors questions and answers without allocation or provider metadata."""
    rows = []
    for assignment in run.allocation["assignments"]:
        for stage in ("initial", "later"):
            session = run.session_id(assignment["case_id"], assignment["slot_id"], stage)
            path = run.root / "submissions" / f"{session}.json"
            if path.exists() and read_json(path)["status"] == "submitted":
                case = run.case(assignment["case_id"])
                rows.append({"blind_id": blind_id(run, session),
                             "case_id": case.identifier, "stage": stage,
                             "question": case.initial_question if stage == "initial" else case.later_question,
                             "answer": read_json(path)["answer"]})
    return {"schema": "EAL/transfer-blind-answers/1", "answers": sorted(
        rows, key=lambda row: row["blind_id"])}


def resolve_scores(run: StudyRun, ratings: dict) -> dict[str, dict[str, Any]]:
    if (not isinstance(ratings, dict) or ratings.get("schema") != "EAL/transfer-ratings/1"
            or not isinstance(ratings.get("ratings"), list)
            or not isinstance(ratings.get("adjudications"), list)):
        raise ValueError("Invalid ratings envelope")
    known = {row["blind_id"] for row in export_answers(run)["answers"]}
    grouped: dict[str, list[dict]] = defaultdict(list)
    participants = {person for item in run.allocation["assignments"]
                    for person in (item["sender"], item["recipient"])}
    for row in ratings["ratings"]:
        _rating(row, known)
        if row["rater"] in participants:
            raise ValueError("Assessors must not be study participants")
        grouped[row["blind_id"]].append(row)
    adjudicated = {}
    for row in ratings["adjudications"]:
        _rating(row, known)
        if row["rater"] in participants:
            raise ValueError("Assessors must not be study participants")
        if row["blind_id"] in adjudicated:
            raise ValueError("Duplicate adjudication")
        adjudicated[row["blind_id"]] = row
    scores = {}
    for identifier in known:
        entries = grouped[identifier]
        if len(entries) != 2 or entries[0]["rater"] == entries[1]["rater"]:
            raise ValueError(f"Two independent ratings required for {identifier}")
        agree = all(entries[0][key] == entries[1][key]
                    for key in ("correct", "material_error"))
        if agree and identifier in adjudicated:
            raise ValueError("Adjudication is reserved for disagreement")
        if not agree and identifier not in adjudicated:
            raise ValueError(f"Unadjudicated disagreement for {identifier}")
        if not agree and adjudicated[identifier]["rater"] in {
                entries[0]["rater"], entries[1]["rater"]}:
            raise ValueError("Adjudicator must be a third assessor")
        selected = entries[0] if agree else adjudicated[identifier]
        scores[identifier] = {"correct": selected["correct"],
                              "material_error": selected["material_error"],
                              "adjudicated": not agree}
    if set(grouped) != known or set(adjudicated) - known:
        raise ValueError("Ratings do not match all submitted answers")
    return scores


def _rating(row: Any, known: set[str]) -> None:
    if (not isinstance(row, dict) or row.get("blind_id") not in known or
            not isinstance(row.get("rater"), str) or not row["rater"] or
            type(row.get("correct")) is not bool or
            type(row.get("material_error")) is not bool or
            not isinstance(row.get("reason"), str) or not row["reason"].strip()):
        raise ValueError("Invalid blind rating")
    if row["correct"] and row["material_error"]:
        raise ValueError("A materially wrong assertion cannot receive a correct rating")


def save_ratings(run: StudyRun, source: str | Path) -> dict:
    for item in run.allocation["assignments"]:
        for stage in ("initial", "later"):
            session = run.session_id(item["case_id"], item["slot_id"], stage)
            if not (run.root / "submissions" / f"{session}.json").exists():
                raise ValueError(f"Resolve every allocated session before locking ratings: {session}")
    ratings = read_json(Path(source))
    scores = resolve_scores(run, ratings)
    target = run.root / "ratings.json"
    if target.exists():
        raise ValueError("Ratings are locked; create a new run for a changed scoring record")
    write_json(target, ratings)
    return {"scored_answers": len(scores), "adjudications": sum(
        score["adjudicated"] for score in scores.values())}


def _metrics(run: StudyRun, session_id: str) -> dict:
    submission = read_json(run.root / "submissions" / f"{session_id}.json")
    calls_path = run.root / "calls" / f"{session_id}.json"
    event_path = run.root / "events" / f"{session_id}.json"
    calls = read_json(calls_path) if calls_path.exists() else []
    completed = [call for call in calls if "response" in call]
    events = read_json(event_path) if event_path.exists() else []
    return {
        "effort_minutes": submission["effort_minutes"],
        "elapsed_seconds": submission["elapsed_seconds"],
        "model_calls": len(calls),
        "model_errors": len(calls) - len(completed),
        "input_tokens": sum(call["response"]["usage"]["input_tokens"] for call in completed)
        if len(calls) == len(completed) else None,
        "output_tokens": sum(call["response"]["usage"]["output_tokens"] for call in completed)
        if len(calls) == len(completed) else None,
        "known_input_tokens": sum(call["response"]["usage"]["input_tokens"] for call in completed),
        "known_output_tokens": sum(call["response"]["usage"]["output_tokens"] for call in completed),
        "model_seconds": sum(call["elapsed_seconds"] for call in calls),
        "provider_cost": sum(call["response"]["cost"] for call in completed)
        if not calls or (len(completed) == len(calls) and
                         all("cost" in call["response"] for call in completed)) else None,
        "developer_tool_calls": sum(event["kind"] == "developer_tool" for event in events),
        "tool_errors": sum(event["kind"] == "developer_tool_error" or
                           (event["kind"] == "developer_tool" and event["returncode"] != 0)
                           for event in events),
        "eal_errors": sum(event["kind"] in ("eal_register_error", "eal_assess_error")
                          for event in events),
        "eal_collected": sum(event.get("collected_count", 0) for event in events),
        "eal_reused": sum(event.get("reused_count", 0) for event in events),
        "eal_seconds": sum(event["duration_seconds"] for event in events if event["kind"].startswith("eal_")),
    }


class OutcomeReader:
    """Join terminal session records to independent judgements and measurements."""

    def __init__(self, run: StudyRun, scores: dict):
        self.run = run
        self.scores = scores

    def read(self, session: str) -> dict:
        path = self.run.root / "submissions" / f"{session}.json"
        if not path.exists():
            raise ValueError(f"Unresolved allocated session; submit or close explicitly: {session}")
        record = read_json(path)
        score = self.scores.get(blind_id(self.run, session))
        status = record["status"]
        if record.get("schema") != "EAL/transfer-submission/2" or status not in (
                "submitted", "withdrawn", "invalid_measurement", "no_answer"):
            raise ValueError(f"Invalid terminal session record: {session}")
        if status == "submitted" and score is None:
            raise ValueError(f"Missing independent score: {session}")
        if status in ("withdrawn", "invalid_measurement"):
            correct = OutcomeBounds(0, 1)
            time = OutcomeBounds(0, record["budget_seconds"])
        else:
            succeeded = status == "submitted" and score["correct"] and record["within_budget"]
            correct = OutcomeBounds(int(succeeded), int(succeeded))
            # Failure receives the full time budget; success-only conditioning is avoided.
            seconds = record["elapsed_seconds"] if succeeded else record["budget_seconds"]
            time = OutcomeBounds(seconds, seconds)
        return {"session_id": session, "status": status, "reason": record["reason"],
                "within_budget": record["within_budget"], "score": score,
                "correct_bounds": [correct.lower, correct.upper],
                "restricted_time_bounds": [time.lower, time.upper],
                "metrics": _metrics(self.run, session)}


def _total(values: list[float | None]) -> dict:
    """A partial sum must not masquerade as a complete total or an observed zero."""
    known = [value for value in values if value is not None]
    return {"total": sum(known) if len(known) == len(values) else None,
            "known_total": sum(known), "missing_sessions": len(values) - len(known)}


def _summary(run: StudyRun, rows: list[dict], independent: bool) -> dict:
    estimates = {}
    for name, support in (("correctness", OutcomeBounds(-1, 1)),
                          ("restricted_time_seconds", OutcomeBounds(
                              -60 * run.design.session_minutes["later"],
                              60 * run.design.session_minutes["later"]))):
        estimates[name] = BoundedPairedEstimator(support).estimate(
            [OutcomeBounds(*row[name + "_difference_bounds"]) for row in rows],
            independent=independent)
    totals = {}
    for arm in ("ordinary", "eal"):
        later = [row["arms"][arm]["later"] for row in rows]
        initial = [row["arms"][arm]["initial"] for row in rows]
        metrics = {key: _total([session["metrics"][key] for session in later])
                   for key in (later[0]["metrics"] if later else ())}
        initial_metrics = {key: _total([session["metrics"][key] for session in initial])
                           for key in (initial[0]["metrics"] if initial else ())}
        totals[arm] = {
            "allocated_sessions": len(later),
            "statuses": {status: sum(x["status"] == status for x in later)
                         for status in ("submitted", "no_answer", "withdrawn", "invalid_measurement")},
            "initial_statuses": {status: sum(x["status"] == status for x in initial)
                                 for status in ("submitted", "no_answer", "withdrawn", "invalid_measurement")},
            "late_answers": sum(x["status"] == "submitted" and not x["within_budget"] for x in later),
            "scored_answers": sum(x["score"] is not None for x in later),
            "raw_correct_answers": sum(bool(x["score"] and x["score"]["correct"]) for x in later),
            "material_errors": sum(bool(x["score"] and x["score"]["material_error"]) for x in later),
            "metrics": metrics, "initial_metrics": initial_metrics,
            "total_effort_minutes": _total([x["metrics"]["effort_minutes"] for x in initial + later]),
        }
    return {"pairs": len(rows), **estimates, "arm_totals": totals}


def analyse(run: StudyRun) -> dict:
    """Estimate on the allocated denominator after every session has a terminal record."""
    ratings_path = run.root / "ratings.json"
    if not ratings_path.exists():
        raise ValueError("Independent ratings have not been locked")
    scores = resolve_scores(run, read_json(ratings_path))
    reader = OutcomeReader(run, scores)
    rows = []
    for case in run.design.cases:
        results = {}
        for slot in case.slots:
            item = run.assignment(case.identifier, slot.identifier)
            results[item["arm"]] = {
                stage: reader.read(run.session_id(case.identifier, slot.identifier, stage))
                for stage in ("initial", "later")}
        eal = results["eal"]["later"]
        ordinary = results["ordinary"]["later"]
        correct = OutcomeBounds(*eal["correct_bounds"]).difference(OutcomeBounds(*ordinary["correct_bounds"]))
        time = OutcomeBounds(*eal["restricted_time_bounds"]).difference(
            OutcomeBounds(*ordinary["restricted_time_bounds"]))
        rows.append({"case_id": case.identifier, "transfer": case.transfer,
                     "model_transition": [case.slots[0].initial_model, case.slots[0].later_model],
                     "correctness_difference_bounds": [correct.lower, correct.upper],
                     "restricted_time_seconds_difference_bounds": [time.lower, time.upper],
                     "arms": results})
    reused = repeated_developers(run.design.cases)
    independent = not reused
    summaries = {group: _summary(run, rows if group == "overall" else
                                [row for row in rows if row["transfer"] == group], independent)
                 for group in ("overall", *TRANSFERS)}
    transitions = {}
    for row in rows:
        key = " -> ".join(row["model_transition"])
        transitions.setdefault(key, []).append(row)
    primary = summaries[TRANSFERS[-1]]
    interval = primary["correctness"]["interval"]
    invalid = [row["case_id"] for row in rows if row["transfer"] == TRANSFERS[-1] and
               any(row["arms"][arm][stage]["status"] == "invalid_measurement"
                   for arm in ("ordinary", "eal") for stage in ("initial", "later"))]
    decision = "exploratory"
    if invalid:
        decision = "invalid_measurement"
    elif run.design.phase == "confirmation":
        decision = "inconclusive"
        if primary["pairs"] >= run.design.primary_min_pairs and interval is not None:
            if interval[0] > run.design.meaningful_difference:
                decision = "meaningful_correctness_improvement"
            elif interval[1] < 0:
                decision = "ordinary_practice_advantage"
    return {"schema": "EAL/transfer-analysis/2", "study_id": run.design.study_id,
            "phase": run.design.phase, "meaningful_difference": run.design.meaningful_difference,
            "primary_min_pairs": run.design.primary_min_pairs, "primary_decision": decision,
            "models": {key: {"version": model.version, "size_class": model.size_class,
                              "adapter_command": list(model.command)}
                       for key, model in run.design.models.items()},
            "plan_sha256": run.design.digest, "allocation_seed": run.allocation["seed"],
            "primary": TRANSFERS[-1], "summaries": summaries, "paired_rows": rows,
            "by_model_transition": {key: _summary(run, values, independent)
                                    for key, values in transitions.items()},
            "diagnostics": {"repeated_developers": reused, "invalid_primary_cases": invalid,
                            "scored_answers": len(scores),
                            "adjudicated_answers": sum(x["adjudicated"] for x in scores.values())},
            "interpretation": "Assigned EAL bundle effect in the specified cases and teams. "
            "Only the primary correctness interval has confirmatory use. Secondary intervals "
            "are marginal, not simultaneous. Repeated developers suppress intervals; "
            "no population-wide model-class or mechanism claim is identified."}
