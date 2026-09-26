"""Grade retained submissions against the frozen independent reference."""
from __future__ import annotations

from collections import defaultdict
import json
from pathlib import Path
import re

from .protocol import (ILLUSTRATIVE_COMMIT, STAGES, canonical, digest, load_frozen,
                       read_json, verify_oracle)
from .recording import _artefact_digest


def grade(raw: bytes | None, expected: dict) -> dict:
    """Count extra support as an error; do not discard incomplete outputs."""
    observed = {}
    malformed = raw is None
    if raw is not None:
        try:
            value = json.loads(raw)
            if (isinstance(value, dict) and set(value) == {"schema", "cases"}
                    and value["schema"] == "eal-authoring-results/1"
                    and isinstance(value["cases"], dict)):
                observed = value["cases"]
            else:
                malformed = True
        except (UnicodeDecodeError, json.JSONDecodeError):
            malformed = True
    correct_cases = correct_claims = false_support = missing_claims = extra_claims = 0
    for case_id, claims in expected.items():
        actual = observed.get(case_id)
        if not isinstance(actual, dict):
            actual = {}
        if actual == claims:
            correct_cases += 1
        for claim_id, wanted in claims.items():
            outcome = actual.get(claim_id)
            if outcome == wanted:
                correct_claims += 1
            elif claim_id not in actual:
                missing_claims += 1
            if outcome == "supported" and wanted != "supported":
                false_support += 1
        for claim_id, outcome in actual.items():
            if claim_id not in claims:
                extra_claims += 1
                if outcome == "supported":
                    false_support += 1
    for case_id, actual in observed.items():
        if case_id not in expected:
            if isinstance(actual, dict):
                extra_claims += len(actual)
                false_support += sum(outcome == "supported" for outcome in actual.values())
            else:
                extra_claims += 1
    claim_total = sum(len(claims) for claims in expected.values())
    return {
        "case_total": len(expected), "correct_cases": correct_cases,
        "claim_total": claim_total, "correct_claims": correct_claims,
        "false_support": false_support, "missing_claims": missing_claims,
        "extra_claims": extra_claims, "malformed": malformed,
        "complete_correct": (not malformed and correct_cases == len(expected)
                             and extra_claims == 0),
    }


def analyse(run: Path, oracle_path: Path) -> dict:
    plan, assignments = load_frozen(run)
    oracle = verify_oracle(run, oracle_path)
    rows: list[dict] = []
    for assignment in assignments:
        task_id = assignment["task_id"]
        for stage in STAGES:
            submission_id = f"{assignment['id']}-{stage}"
            directory = run / "submissions" / submission_id
            record_path = directory / "record.json"
            record = read_json(record_path) if record_path.exists() else None
            raw = None
            if record is not None:
                if (record.get("assignment_id") != assignment["id"]
                        or record.get("stage") != stage
                        or record.get("submission_id") != submission_id):
                    raise ValueError("Submission identity changed")
                artefact = directory / "artefact"
                if record["artefact_sha256"] is not None and (
                    not artefact.exists() or _artefact_digest(artefact) != record["artefact_sha256"]
                ):
                    raise ValueError("Submitted artefact changed")
                # Participant-supplied results are retained for diagnosis only.
                results = directory / "results.json"
                if record["results_sha256"] is not None:
                    if not results.exists():
                        raise ValueError("Submitted results disappeared")
                    if digest(results.read_bytes()) != record["results_sha256"]:
                        raise ValueError("Submitted results changed")
            replay_dir = run / "replays" / submission_id
            replay_path = replay_dir / "record.json"
            replay_record = read_json(replay_path) if replay_path.exists() else None
            replay_ok = False
            if replay_record is not None:
                if (record is None or replay_record["submission_id"] != submission_id
                        or replay_record["source_sha256"] != record["artefact_sha256"]
                        or replay_record["runner_sha256"] != plan["runner_sha256"][assignment["arm"]]):
                    raise ValueError("Replay source or runner identity differs from frozen plan")
                pinned = plan["source_commit"]
                if pinned == ILLUSTRATIVE_COMMIT:
                    head = replay_record.get("repository_head")
                    head_after = replay_record.get("repository_head_after")
                    if (replay_record.get("source_commit_verification") != "illustrative_placeholder"
                            or any(value is not None and
                                   (not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{40}", value) is None)
                                   for value in (head, head_after))
                            or any(value is not None and type(value) is not bool
                                   for value in (replay_record.get("repository_dirty"),
                                                 replay_record.get("repository_dirty_after")))):
                        raise ValueError("Replay revision provenance differs from frozen plan")
                elif (replay_record.get("source_commit_verification") != "matched_clean"
                      or replay_record.get("repository_head") != pinned
                      or replay_record.get("repository_dirty") is not False
                      or replay_record.get("repository_head_after") != pinned
                      or replay_record.get("repository_dirty_after") is not False):
                    raise ValueError("Replay revision provenance differs from frozen plan")
                expected_cases = {"schema": "eal-authoring-cases/1", "task_id": task_id,
                                  "stage": stage,
                                  "target_claims": next(t for t in plan["tasks"]
                                                        if t["id"] == task_id)["target_claims"][stage],
                                  "cases": next(t for t in plan["tasks"]
                                               if t["id"] == task_id)["inputs"][stage]}
                cases = replay_dir / "cases.json"
                if (not cases.exists() or cases.read_bytes() != canonical(expected_cases)
                        or replay_record["cases_sha256"] != digest(canonical(expected_cases))):
                    raise ValueError("Replay case inputs differ from the frozen plan")
                output_path = replay_dir / "results.json"
                stderr_path = replay_dir / "stderr.txt"
                if (not output_path.exists() or not stderr_path.exists()
                        or digest(output_path.read_bytes()) != replay_record["stdout_sha256"]
                        or digest(stderr_path.read_bytes()) != replay_record["stderr_sha256"]):
                    raise ValueError("Replay output changed")
                replay_ok = replay_record["returncode"] == 0 and replay_record["error"] is None
                if replay_ok:
                    raw = output_path.read_bytes()
            score = grade(raw, oracle["tasks"][task_id][stage])
            if record is None or record["failure"] is not None or not replay_ok:
                score["complete_correct"] = False
            review_dir = run / "reviews" / submission_id
            reviews = []
            if review_dir.exists():
                reviews = [read_json(path) for path in sorted(review_dir.glob("*.json"))
                           if path.name != "adjudication.json"]
            adjudication_path = review_dir / "adjudication.json"
            adjudication = read_json(adjudication_path) if adjudication_path.exists() else None
            rows.append({
                **assignment, "stage": stage, "submission_id": submission_id,
                "submitted": record is not None,
                "replayed": replay_record is not None, "replay_succeeded": replay_ok,
                "score_origin": "independent_replay" if replay_ok else "unscored",
                "active_seconds": record["active_seconds"] if record else None,
                "failure": record["failure"] if record else "missing_submission",
                "review_count": len(reviews),
                "review_seconds": sum(review["review_seconds"] for review in reviews),
                "reported_findings": sum(len(review["findings"]) for review in reviews),
                "adjudicated_defects": (len(adjudication["confirmed_defects"])
                                        if adjudication else None),
                "adjudication_seconds": (adjudication["adjudication_seconds"]
                                          if adjudication else None),
                **score,
            })
    summary = []
    for arm in plan["arms"]:
        for stage in STAGES:
            selected = [row for row in rows if row["arm"] == arm and row["stage"] == stage]
            reviewed = [row for row in selected if row["review_count"]]
            adjudicated = [row for row in selected if row["adjudicated_defects"] is not None]
            summary.append({
                "arm": arm, "stage": stage, "assigned": len(selected),
                "submitted": sum(row["submitted"] for row in selected),
                "replayed": sum(row["replayed"] for row in selected),
                "replay_succeeded": sum(row["replay_succeeded"] for row in selected),
                "complete_correct": sum(row["complete_correct"] for row in selected),
                "correct_cases": sum(row["correct_cases"] for row in selected),
                "assigned_cases": sum(row["case_total"] for row in selected),
                "false_support": sum(row["false_support"] for row in selected),
                "active_seconds_observed": sum(row["active_seconds"] or 0 for row in selected),
                "active_seconds_observations": sum(row["active_seconds"] is not None
                                                   for row in selected),
                "reviewed": len(reviewed),
                "review_seconds_observed": sum(row["review_seconds"] for row in reviewed),
                "adjudicated": len(adjudicated),
                "confirmed_defects_observed": sum(row["adjudicated_defects"]
                                                  for row in adjudicated),
            })
    # Participant/family units preserve the crossover structure; a raw sum of
    # case rows must not be presented as independent engineer replications.
    pairs = []
    groups: dict[tuple, list[dict]] = defaultdict(list)
    for row in rows:
        groups[(row["participant_id"], row["pair_index"], row["stage"])].append(row)
    for (participant, pair_index, stage), group in groups.items():
        if len(group) == 2 and {row["arm"] for row in group} == set(plan["arms"]):
            by_arm = {row["arm"]: row for row in group}
            eal, typed = by_arm["eal2"], by_arm["typed_rules"]
            pairs.append({
                "participant_id": participant, "pair_index": pair_index,
                "family": eal["family"], "stage": stage,
                "eal_minus_typed_correct_case_fraction": (
                    eal["correct_cases"] / eal["case_total"]
                    - typed["correct_cases"] / typed["case_total"]),
                "eal_minus_typed_active_seconds": (
                    eal["active_seconds"] - typed["active_seconds"]
                    if eal["active_seconds"] is not None and typed["active_seconds"] is not None
                    else None),
                "both_submitted": eal["submitted"] and typed["submitted"],
            })
    return {
        "schema": "eal-authoring-analysis/1", "study_id": plan["study_id"],
        "source_commit": plan["source_commit"], "practical_margins": plan["practical_margins"],
        "source_provenance_limited": plan["source_commit"] == ILLUSTRATIVE_COMMIT,
        "interpretation": ("Descriptive assigned-denominator results. Participant results "
                           "are never graded; absent or failed independent replays are unscored "
                           "and count as incomplete. Elapsed and review times are observed-only. "
                           "Task pairs and participants, not individual claims, are replication units. "
                           "Reviewer findings remain unconfirmed until adjudicated."),
        "summary": summary, "participant_pairs": pairs, "rows": rows,
    }
