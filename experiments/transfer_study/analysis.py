"""Blind independent scoring and paired cross-session effect estimates."""

from __future__ import annotations

import hashlib
import random
from collections import defaultdict
from pathlib import Path
from typing import Any

from .design import TRANSFERS
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
            if path.exists():
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
    for row in ratings["ratings"]:
        _rating(row, known)
        grouped[row["blind_id"]].append(row)
    adjudicated = {}
    for row in ratings["adjudications"]:
        _rating(row, known)
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
    ratings = read_json(Path(source))
    scores = resolve_scores(run, ratings)
    target = run.root / "ratings.json"
    if target.exists():
        raise ValueError("Ratings are locked; create a new run for a changed scoring record")
    write_json(target, ratings)
    return {"scored_answers": len(scores), "adjudications": sum(
        score["adjudicated"] for score in scores.values())}


def _interval(values: list[int], seed: int) -> list[float] | None:
    if len(values) < 4:
        return None
    randomiser = random.Random(seed)
    estimates = sorted(sum(randomiser.choice(values) for _ in values) / len(values)
                       for _ in range(10000))
    return [estimates[249], estimates[9749]]


def _metrics(run: StudyRun, session_id: str) -> dict:
    submission = read_json(run.root / "submissions" / f"{session_id}.json")
    calls_path = run.root / "calls" / f"{session_id}.json"
    event_path = run.root / "events" / f"{session_id}.json"
    calls = read_json(calls_path) if calls_path.exists() else []
    completed = [call for call in calls if "response" in call]
    events = read_json(event_path) if event_path.exists() else []
    return {
        "effort_minutes": submission["effort_minutes"],
        "model_calls": len(calls),
        "model_errors": len(calls) - len(completed),
        "input_tokens": sum(call["response"]["usage"]["input_tokens"] for call in completed),
        "output_tokens": sum(call["response"]["usage"]["output_tokens"] for call in completed),
        "model_seconds": sum(call["elapsed_seconds"] for call in calls),
        "provider_cost": sum(call["response"]["cost"] for call in completed)
        if not calls or (len(completed) == len(calls) and
                         all("cost" in call["response"] for call in completed)) else None,
        "developer_tool_calls": sum(event["kind"] == "developer_tool" for event in events),
        "tool_errors": sum(event["kind"] == "developer_tool_error" for event in events),
        "eal_errors": sum(event["kind"] in ("eal_register_error", "eal_assess_error")
                          for event in events),
        "eal_collected": sum(event.get("collected_count", 0) for event in events),
        "eal_reused": sum(event.get("reused_count", 0) for event in events),
    }


def analyse(run: StudyRun) -> dict:
    """Require every assigned later answer before estimating paired effects."""
    ratings_path = run.root / "ratings.json"
    if not ratings_path.exists():
        raise ValueError("Independent ratings have not been locked")
    scores = resolve_scores(run, read_json(ratings_path))
    groups: dict[str, list[dict]] = defaultdict(list)
    rows = []
    for case in run.design.cases:
        assignment = [run.assignment(case.identifier, slot.identifier) for slot in case.slots]
        results = {}
        for item in assignment:
            session = run.session_id(case.identifier, item["slot_id"], "later")
            initial_session = run.session_id(case.identifier, item["slot_id"], "initial")
            if not (run.root / "submissions" / f"{session}.json").exists():
                raise ValueError(f"Missing later submission: {session}")
            score = scores[blind_id(run, session)]
            results[item["arm"]] = {"session_id": session, "score": score,
                                    "metrics": _metrics(run, session),
                                    "initial_score": scores.get(blind_id(run, initial_session)),
                                    "initial_metrics": _metrics(run, initial_session),
                                    "model_transition": [item["initial_model"], item["later_model"]]}
        difference = int(results["eal"]["score"]["correct"]) - int(
            results["ordinary"]["score"]["correct"])
        row = {"case_id": case.identifier, "transfer": case.transfer,
               "difference": difference, "arms": results}
        rows.append(row)
        groups[case.transfer].append(row)
    summaries = {}
    for group in ("overall", *TRANSFERS):
        included = rows if group == "overall" else groups[group]
        differences = [row["difference"] for row in included]
        summaries[group] = {"pairs": len(included),
                            "correctness_difference": sum(differences) / len(differences)
                            if differences else None,
                            "bootstrap_95_interval": _interval(differences, run.allocation["seed"]),
                            "arm_totals": {arm: {
                                "correct": sum(row["arms"][arm]["score"]["correct"] for row in included),
                                "material_errors": sum(row["arms"][arm]["score"]["material_error"]
                                                       for row in included),
                                "effort_minutes": sum(row["arms"][arm]["metrics"]["effort_minutes"]
                                                      for row in included),
                                "initial_effort_minutes": sum(
                                    row["arms"][arm]["initial_metrics"]["effort_minutes"]
                                    for row in included),
                                "model_calls": sum(row["arms"][arm]["metrics"]["model_calls"]
                                                   for row in included),
                                "initial_model_calls": sum(
                                    row["arms"][arm]["initial_metrics"]["model_calls"]
                                    for row in included),
                                "model_errors": sum(row["arms"][arm]["metrics"]["model_errors"]
                                                    for row in included),
                                "provider_cost": sum(row["arms"][arm]["metrics"]["provider_cost"]
                                                     for row in included)
                                if all(row["arms"][arm]["metrics"]["provider_cost"] is not None
                                       for row in included) else None,
                                "initial_provider_cost": sum(
                                    row["arms"][arm]["initial_metrics"]["provider_cost"]
                                    for row in included)
                                if all(row["arms"][arm]["initial_metrics"]["provider_cost"] is not None
                                       for row in included) else None,
                                "input_tokens": sum(row["arms"][arm]["metrics"]["input_tokens"]
                                                    for row in included),
                                "output_tokens": sum(row["arms"][arm]["metrics"]["output_tokens"]
                                                     for row in included),
                                "developer_tool_calls": sum(
                                    row["arms"][arm]["metrics"]["developer_tool_calls"]
                                    for row in included),
                                "tool_errors": sum(row["arms"][arm]["metrics"]["tool_errors"]
                                                   for row in included),
                                "eal_errors": sum(row["arms"][arm]["metrics"]["eal_errors"]
                                                  for row in included),
                                "eal_collected": sum(row["arms"][arm]["metrics"]["eal_collected"]
                                                     for row in included),
                                "eal_reused": sum(row["arms"][arm]["metrics"]["eal_reused"]
                                                  for row in included),
                            } for arm in ("ordinary", "eal")}}
    primary = summaries["different_developer_different_model"]
    interval = primary["bootstrap_95_interval"]
    decision = "exploratory"
    if run.design.phase == "confirmation":
        decision = "inconclusive"
        if primary["pairs"] >= run.design.primary_min_pairs and interval is not None:
            if interval[0] > run.design.meaningful_difference:
                decision = "meaningful_improvement"
            elif interval[1] < 0:
                decision = "ordinary_practice_advantage"
    return {"schema": "EAL/transfer-analysis/1", "study_id": run.design.study_id,
            "phase": run.design.phase, "meaningful_difference": run.design.meaningful_difference,
            "primary_min_pairs": run.design.primary_min_pairs, "primary_decision": decision,
            "plan_sha256": run.design.digest, "allocation_seed": run.allocation["seed"],
            "primary": "different_developer_different_model",
            "summaries": summaries, "paired_rows": rows,
            "interpretation": "Descriptive paired estimates; intervals require adequate independent cases."}
