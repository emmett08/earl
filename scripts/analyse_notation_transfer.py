#!/usr/bin/env python3
"""Validate and describe a frozen notation diagnostic without making model calls."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
import gzip
import hashlib
import io
import json
import math
from pathlib import Path
import re
import tarfile

SCORING_SCHEMA = "EAL/notation-transfer-scoring/2"
STATUSES = ("supported", "contested", "unsupported", "out_of_scope")
VIEWS = ("answer", "answer_raw", "answer_irrelevant", "answer_assessed")
ORACLES = {"full_information": "score", "available_information": "available_information_score"}
MAX_TRIAL_BYTES = 2 * 1024 * 1024
MAX_ARCHIVE_BYTES = 128 * 1024 * 1024
MAX_ARCHIVE_MEMBERS = 10000
MAX_TAR_STREAM_BYTES = 160 * 1024 * 1024


def require(condition, message):
    if not condition:
        raise ValueError(message)


def strict_json(text):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, "Duplicate JSON key")
            result[key] = value
        return result

    def invalid(_):
        raise ValueError("Non-finite JSON number")

    return json.loads(text, object_pairs_hook=pairs, parse_constant=invalid)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     allow_nan=False).encode()).hexdigest()


def conditions():
    result = []
    for notation in ("eal", "json"):
        for quality in ("correct", "incorrect"):
            for view in VIEWS:
                result.append(dict(id=f"{notation}_{quality}_{view}", notation=notation,
                                   candidate_quality=quality, information=view))
        result.append(dict(id=f"{notation}_raw_only", notation=notation,
                           candidate_quality="absent", information="raw_only"))
    return result


def proposal(expected, quality, repetition):
    if quality == "absent":
        return None
    if quality == "correct":
        return dict(expected)
    return {name: [s for s in STATUSES if s != value][repetition % 3]
            for name, value in expected.items()}


def validate_reference(reference, names=None):
    require(isinstance(reference, dict) and bool(reference), "Missing reference labels")
    require(all(isinstance(k, str) and v in STATUSES for k, v in reference.items()),
            "Invalid reference labels")
    if names is not None:
        require(set(reference) == set(names), "Reference claim identifiers differ")


def admitted_answer(response, expected):
    """Independently reproduce the runner's whole-response admission contract."""
    if not isinstance(response, dict) or not isinstance(response.get("text"), str):
        return None
    try:
        decoded = strict_json(response["text"])
        if (not isinstance(decoded, dict) or set(decoded) != {"claims", "basis"}
                or not isinstance(decoded["basis"], list)
                or not isinstance(decoded["claims"], dict)
                or set(decoded["claims"]) != set(expected)
                or any(v not in STATUSES for v in decoded["claims"].values())):
            return None
        return decoded["claims"]
    except (ValueError, TypeError):
        return None


def expected_score(reference, answer):
    details = {}
    for name, wanted in reference.items():
        actual = answer[name] if answer is not None else "unresolved"
        category = ("correct" if actual == wanted else "unjustified" if actual == "supported"
                    else "unresolved" if actual in {"unresolved", "unsupported", "out_of_scope"}
                    else "incorrect")
        details[name] = dict(expected=wanted, actual=actual, category=category)
    categories = {d["category"] for d in details.values()}
    correct = answer is not None and categories == {"correct"}
    return dict(correct=correct,
                correctly_resolved=correct and all(v == "supported" for v in reference.values()),
                justified_unresolved=correct and any(v != "supported" for v in reference.values()),
                unjustified="unjustified" in categories,
                unresolved=answer is None or "unresolved" in categories,
                unexpected_claims=[], claims=details)


def trial_files(root):
    """Read bounded bytes in memory; archives are never extracted.

    When both representations exist they must contain identical filenames and
    bytes. Archive creation must omit directory entries and other metadata files.
    """
    loose = {}
    for path in sorted((root / "trials").glob("*.json")):
        require(path.is_file() and not path.is_symlink(), "Trial is not a regular file")
        require(path.stat().st_size <= MAX_TRIAL_BYTES, "Trial member size limit exceeded")
        loose["trials/" + path.name] = path.read_bytes()
    archive_path = root / "trials.tar.gz"
    if not archive_path.exists():
        return sorted(loose.items())
    archived, total = {}, 0
    try:
        # Bound headers as well as file contents before tarfile parses GNU/PAX
        # extensions, which it otherwise consumes before yielding a member.
        with gzip.open(archive_path, "rb") as compressed:
            tar_bytes = compressed.read(MAX_TAR_STREAM_BYTES + 1)
        require(len(tar_bytes) <= MAX_TAR_STREAM_BYTES, "Trial archive expanded stream size limit exceeded")
        with tarfile.open(fileobj=io.BytesIO(tar_bytes), mode="r:") as archive:
            for member in archive:
                require(member.isfile() and re.fullmatch(r"trials/trial-[0-9]{5}\.json", member.name),
                        "Unsafe or unexpected trial archive member")
                require(member.name not in archived, "Duplicate trial archive member")
                require(len(archived) < MAX_ARCHIVE_MEMBERS, "Trial archive member count limit exceeded")
                require(0 <= member.size <= MAX_TRIAL_BYTES, "Trial member size limit exceeded")
                total += member.size
                require(total <= MAX_ARCHIVE_BYTES, "Trial archive total size limit exceeded")
                stream = archive.extractfile(member)
                require(stream is not None, "Unreadable trial archive member")
                data = stream.read(MAX_TRIAL_BYTES + 1)
                require(len(data) == member.size, "Trial archive member size mismatch")
                archived[member.name] = data
    except (tarfile.TarError, EOFError, OSError) as exc:
        raise ValueError("Invalid trial archive") from exc
    if loose:
        require(loose == archived, "Loose trials and archive do not match byte for byte")
    return sorted(archived.items())


def load_run(root):
    root = Path(root)
    frozen = strict_json((root / "freeze.json").read_text())
    require(frozen.get("schema") == "EAL/notation-transfer-freeze/2"
            and frozen.get("scoring_schema") == SCORING_SCHEMA, "Unsupported freeze/scoring schema")
    require(frozen.get("freeze_digest") == digest({k: v for k, v in frozen.items() if k != "freeze_digest"}),
            "Freeze digest mismatch")
    tasks, plan = frozen["tasks"], frozen["plan"]
    repetitions = plan["repetitions"]
    require(type(repetitions) is int and repetitions > 0, "Invalid repetitions")
    require(isinstance(tasks, dict) and bool(tasks) and len(plan["task_ids"]) == len(set(plan["task_ids"]))
            and set(tasks) == set(plan["task_ids"]), "Frozen task identities differ")
    condition_map = {c["id"]: c for c in conditions()}
    for task in tasks.values():
        validate_reference(task["expected"])
        require(isinstance(task.get("family"), str) and task["family"], "Missing task family")
        for view in (*VIEWS, "raw_only"):
            validate_reference(task["available_information_references"][view], task["expected"])
        for view in ("answer_raw", "answer_assessed", "raw_only"):
            require(task["available_information_references"][view] == task["expected"],
                    "Full-observation oracle mismatch")
    expected_keys = {(task_id, rep, cid) for task_id in tasks
                     for rep in range(repetitions) for cid in condition_map}
    schedule, seen_keys = {}, set()
    for row in frozen["schedule"]:
        trial_id, condition = row["trial_id"], row["condition"]
        require(isinstance(trial_id, str) and trial_id and trial_id not in schedule,
                "Duplicate or invalid scheduled trial ID")
        require(condition_map.get(condition.get("id")) == condition, "Unknown scheduled condition")
        require(type(row["repetition"]) is int, "Invalid scheduled repetition")
        key = (row["task_id"], row["repetition"], condition["id"])
        require(key in expected_keys and key not in seen_keys, "Duplicate or foreign scheduled endpoint")
        require(isinstance(row.get("messages_digest"), str), "Missing scheduled prompt digest")
        seen_keys.add(key)
        schedule[trial_id] = row
    require(seen_keys == expected_keys, "Frozen schedule does not cover all task/repetition/condition cells")
    records, uncertain, seen_trials = {}, {}, set()
    for filename, content in trial_files(root):
        record = strict_json(content.decode("utf-8"))
        trial_id = record.get("trial_id")
        require(trial_id not in seen_trials, "Duplicate trial ID")
        seen_trials.add(trial_id)
        require(trial_id in schedule, "Unknown trial ID")
        require(Path(filename).stem == trial_id, "Trial filename does not match its ID")
        row = schedule[trial_id]
        require(all(record.get(k) == row[k] for k in ("task_id", "repetition", "condition", "messages_digest")),
                "Trial does not match scheduled endpoint")
        require(type(record["repetition"]) is int, "Invalid trial repetition")
        require(record.get("freeze_digest") == frozen["freeze_digest"], "Trial freeze digest mismatch")
        require(digest(record.get("messages")) == row["messages_digest"], "Trial prompt digest mismatch")
        if record.get("state") == "attempt_started":
            require(not any(k in record for k in (*ORACLES.values(), "cost_usd", "response")),
                    "Uncertain marker contains finalized fields")
            uncertain[trial_id] = record
            continue
        require(record.get("state") in {"responded", "malformed_response", "provider_error"},
                "Unknown trial state")
        require(record.get("scoring_schema") == SCORING_SCHEMA, "Trial scoring schema mismatch")
        task = tasks[row["task_id"]]
        answer = admitted_answer(record.get("response"), task["expected"])
        require(record["state"] != "responded" or answer is not None, "Responded trial violates response contract")
        require(record["state"] != "malformed_response" or answer is None, "Malformed trial has an admissible answer")
        if record["state"] != "responded":
            answer = None
        for oracle, field in ORACLES.items():
            reference = (task["expected"] if oracle == "full_information" else
                         task["available_information_references"][row["condition"]["information"]])
            score = record.get(field)
            require(isinstance(score, dict) and all(type(score.get(k)) is bool for k in
                    ("correct", "correctly_resolved", "justified_unresolved", "unjustified", "unresolved")),
                    "Missing or non-boolean known score")
            require(score == expected_score(reference, answer), f"Stored {field} disagrees with response/reference")
        candidate = proposal(task["expected"], row["condition"]["candidate_quality"], row["repetition"])
        available = task["available_information_references"][row["condition"]["information"]]
        candidate_correct = candidate == available if candidate is not None else None
        stored = record.get("proposal_correct_given_available_information")
        require((stored is None if candidate_correct is None else type(stored) is bool and stored == candidate_correct),
                "Proposal correctness disagrees with available-information reference")
        cost = record.get("cost_usd")
        require("cost_usd" in record and (cost is None or type(cost) in (int, float)
                and math.isfinite(cost) and cost >= 0), "Invalid or missing cost")
        response = record.get("response")
        require(response is None or isinstance(response, dict), "Invalid response metadata")
        metadata = (response or {}).get("metadata", {})
        require(isinstance(metadata, dict), "Invalid response metadata")
        for name in ("input_tokens", "output_tokens"):
            value = (response or {}).get(name)
            require(value is None or type(value) is int and value >= 0, "Invalid token usage")
        for name in ("cached_input_tokens", "reasoning_tokens"):
            value = metadata.get(name)
            require(value is None or type(value) is int and value >= 0, "Invalid token usage")
        require(metadata.get("finish_reason") is None or isinstance(metadata["finish_reason"], str),
                "Invalid finish reason")
        require((response or {}).get("model") is None or isinstance(response["model"], str),
                "Invalid response model")
        model_match = ((response or {}).get("model") == frozen["provider_identity"]["model"]
                       if response is not None else None)
        require(record.get("response_model_matches") is model_match, "Response model match flag disagrees")
        records[trial_id] = record
    missing = sorted(set(schedule) - set(records) - set(uncertain))
    return frozen, schedule, records, uncertain, missing


def rate(count, denominator):
    return dict(count=count, denominator=denominator, rate=count / denominator if denominator else None)


def initial_correct(record, oracle):
    quality = record["condition"]["candidate_quality"]
    if quality == "absent":
        return None
    return quality == "correct" if oracle == "full_information" else record["proposal_correct_given_available_information"]


def transition(record, oracle):
    initial = initial_correct(record, oracle)
    start = "absent" if initial is None else "correct" if initial else "incorrect"
    final = ("correct" if record[ORACLES[oracle]]["correct"] else
             "incorrect_complete" if record["state"] == "responded" else "incomplete")
    return f"{start}_to_{final}"


def summarise(rows, scheduled, uncertain_count):
    n = len(rows)
    result = dict(scheduled=scheduled, finalized_attempts=n, uncertain_attempts=uncertain_count,
                  missing_scheduled=scheduled - n - uncertain_count,
                  complete_responses=sum(r["state"] == "responded" for r in rows),
                  malformed_responses=sum(r["state"] == "malformed_response" for r in rows),
                  provider_errors=sum(r["state"] == "provider_error" for r in rows),
                  provider_errors_length=sum(r["state"] == "provider_error" and
                      ((r.get("response") or {}).get("metadata") or {}).get("finish_reason") == "length" for r in rows))
    result["state_by_finish_reason"] = {
        state: dict(sorted(Counter(((r.get("response") or {}).get("metadata") or {}).get("finish_reason")
                                   or "<unknown>" for r in rows if r["state"] == state).items()))
        for state in ("responded", "malformed_response", "provider_error")}
    result["metrics"] = {}
    for oracle, field in ORACLES.items():
        correct_proposals = [r for r in rows if initial_correct(r, oracle) is True]
        incorrect_proposals = [r for r in rows if initial_correct(r, oracle) is False]
        result["metrics"][oracle] = dict(
            correctness=rate(sum(r[field]["correct"] for r in rows), n),
            false_support=rate(sum(r[field]["unjustified"] for r in rows), n),
            damage=rate(sum(not r[field]["correct"] for r in correct_proposals), len(correct_proposals)),
            correction=rate(sum(r[field]["correct"] for r in incorrect_proposals), len(incorrect_proposals)),
            proposal_correct=len(correct_proposals), proposal_incorrect=len(incorrect_proposals),
            proposal_absent=n - len(correct_proposals) - len(incorrect_proposals),
            transitions={f"{start}_to_{end}": sum(transition(r, oracle) == f"{start}_to_{end}" for r in rows)
                         for start in ("absent", "correct", "incorrect")
                         for end in ("correct", "incorrect_complete", "incomplete")})
    known_cost = [r["cost_usd"] for r in rows if r["cost_usd"] is not None]
    cost_unknown = n - len(known_cost) + uncertain_count
    usage = {name: [(r.get("response") or {}).get(name) for r in rows]
             for name in ("input_tokens", "output_tokens")}
    usage.update({name: [((r.get("response") or {}).get("metadata") or {}).get(name) for r in rows]
                  for name in ("cached_input_tokens", "reasoning_tokens")})
    result["resources"] = dict(known_cost_usd=sum(known_cost), cost_known_attempts=len(known_cost),
                               cost_unknown_attempts=cost_unknown,
                               cost_complete_for_attempted=bool(n) and cost_unknown == 0,
                               attempted_cost_usd=sum(known_cost) if n and cost_unknown == 0 else None,
                               model_verified_attempts=sum(r.get("response_model_matches") is True for r in rows),
                               response_models=dict(sorted(Counter((r.get("response") or {}).get("model") or "<unknown>" for r in rows).items())),
                               finish_reasons=dict(sorted(Counter(((r.get("response") or {}).get("metadata") or {}).get("finish_reason") or "<unknown>" for r in rows).items())))
    for name, values in usage.items():
        known = [v for v in values if v is not None]
        result["resources"][name] = dict(known_total=sum(known), known_attempts=len(known),
                                         unknown_attempts=n - len(known) + uncertain_count,
                                         complete_for_attempted=bool(n) and len(known) == n and not uncertain_count)
    return result


def contrast_specs():
    result = [("notation_raw_only", "eal_raw_only", "json_raw_only")]
    for n in ("eal", "json"):
        result += [(f"{n}_original_incorrect_raw_minus_answer", f"{n}_incorrect_answer_raw", f"{n}_incorrect_answer"),
                   (f"{n}_original_correct_raw_minus_answer", f"{n}_correct_answer_raw", f"{n}_correct_answer")]
        for q in ("correct", "incorrect"):
            result += [(f"{n}_{q}_raw_minus_irrelevant", f"{n}_{q}_answer_raw", f"{n}_{q}_answer_irrelevant"),
                       (f"{n}_{q}_assessed_minus_raw", f"{n}_{q}_answer_assessed", f"{n}_{q}_answer_raw"),
                       (f"{n}_raw_only_minus_{q}_raw", f"{n}_raw_only", f"{n}_{q}_answer_raw"),
                       (f"{n}_raw_only_minus_{q}_answer", f"{n}_raw_only", f"{n}_{q}_answer")]
    return result


def comparisons(frozen, records):
    indexed = {(r["task_id"], r["repetition"], r["condition"]["id"]): r for r in records.values()}
    blocks = [(task, rep) for task in sorted(frozen["tasks"])
              for rep in range(frozen["plan"]["repetitions"])]
    result = []
    for name, left, right in contrast_specs():
        pairs = [(task, rep, indexed[(task, rep, left)], indexed[(task, rep, right)])
                 for task, rep in blocks if (task, rep, left) in indexed and (task, rep, right) in indexed]
        complete = len(pairs) == len(blocks)
        item = dict(name=name, left=left, right=right, scheduled_pairs=len(blocks), paired_finalized_attempts=len(pairs),
                    coverage_complete=complete,
                    missing_pairs=[dict(task_id=t, repetition=r) for t, r in blocks
                                   if (t, r, left) not in indexed or (t, r, right) not in indexed], metrics={})
        for oracle, field in ORACLES.items():
            changes = []
            per_task = defaultdict(list)
            for task, rep, a, b in pairs:
                difference = int(a[field]["correct"]) - int(b[field]["correct"])
                per_task[task].append(difference)
                reference_equal = (frozen["tasks"][task]["available_information_references"][a["condition"]["information"]]
                                   == frozen["tasks"][task]["available_information_references"][b["condition"]["information"]])
                changes.append(dict(task_id=task, repetition=rep, correctness_difference=difference,
                                    left_correct=a[field]["correct"], right_correct=b[field]["correct"],
                                    false_support_difference=int(a[field]["unjustified"]) - int(b[field]["unjustified"]),
                                    reference_equal=True if oracle == "full_information" else reference_equal,
                                    proposal_correctness_equal=initial_correct(a, oracle) == initial_correct(b, oracle)))
            means = {task: sum(values) / len(values) for task, values in per_task.items()}
            false_means = defaultdict(list)
            for change in changes:
                false_means[change["task_id"]].append(change["false_support_difference"])
            pair_counts = Counter((a[field]["correct"], b[field]["correct"]) for _, _, a, b in pairs)
            item["metrics"][oracle] = dict(
                task_weighted_difference=sum(means.values()) / len(means) if complete else None,
                observed_pairs_only_task_weighted_difference=sum(means.values()) / len(means) if means else None,
                false_support_task_weighted_difference=(sum(sum(v) / len(v) for v in false_means.values())
                                                       / len(false_means) if complete else None),
                task_means=means, task_differences=dict(per_task), paired_blocks=changes,
                paired_outcomes=dict(both_correct=pair_counts[(True, True)], left_only_correct=pair_counts[(True, False)],
                                     right_only_correct=pair_counts[(False, True)], neither_correct=pair_counts[(False, False)]),
                reference_changed_pairs=sum(not c["reference_equal"] for c in changes),
                proposal_correctness_changed_pairs=sum(not c["proposal_correctness_equal"] for c in changes))
        result.append(item)
    return result


def constant_baselines(frozen, records):
    result = {}
    for oracle in ORACLES:
        result[oracle] = {}
        for name, rows in (("scheduled", frozen["schedule"]), ("finalized_attempts", records.values())):
            references = []
            for row in rows:
                task = frozen["tasks"][row["task_id"]]
                references.append(task["expected"] if oracle == "full_information" else
                                  task["available_information_references"][row["condition"]["information"]])
            result[oracle][name] = {label: dict(
                correctness=rate(sum(all(value == label for value in ref.values()) for ref in references), len(references)),
                false_support=rate(sum(label == "supported" and any(value != label for value in ref.values())
                                       for ref in references), len(references))) for label in STATUSES}
    return result


def analyse(root):
    root = Path(root)
    frozen, schedule, records, uncertain, missing = load_run(root)
    rows = list(records.values())
    result = dict(schema="EAL/notation-transfer-analysis/1", scoring_schema=SCORING_SCHEMA,
                  freeze_digest=frozen["freeze_digest"], analysis_kind="descriptive dual-oracle diagnostic",
                  configured_model=frozen["provider_identity"]["model"],
                  scheduled=len(schedule), finalized_attempts=len(rows), uncertain_attempts=len(uncertain),
                  missing_scheduled=len(missing), uncertain_trial_ids=sorted(uncertain), missing_trial_ids=missing,
                  all_scheduled_finalized=not uncertain and not missing,
                  task_count=len(frozen["tasks"]), family_count=len({t["family"] for t in frozen["tasks"].values()}),
                  repetitions=frozen["plan"]["repetitions"],
                  families={family: sorted(k for k, t in frozen["tasks"].items() if t["family"] == family)
                            for family in sorted({t["family"] for t in frozen["tasks"].values()})},
                  totals=summarise(rows, len(schedule), len(uncertain)), conditions=[], task_conditions=[],
                  constant_label_baselines=constant_baselines(frozen, records),
                  paired_comparisons=comparisons(frozen, records), proposal_schedule=[], trials=[])
    for condition in conditions():
        selected = [r for r in rows if r["condition"] == condition]
        count_uncertain = sum(r["condition"] == condition for r in uncertain.values())
        result["conditions"].append({**condition, **summarise(selected,
                                    len(frozen["tasks"]) * frozen["plan"]["repetitions"], count_uncertain)})
        for task_id, task in sorted(frozen["tasks"].items()):
            subset = [r for r in selected if r["task_id"] == task_id]
            count = sum(r["condition"] == condition and r["task_id"] == task_id for r in uncertain.values())
            result["task_conditions"].append(dict(task_id=task_id, family=task["family"], **condition,
                                                  **summarise(subset, frozen["plan"]["repetitions"], count)))
    for task_id, task in sorted(frozen["tasks"].items()):
        for rep in range(frozen["plan"]["repetitions"]):
            candidate = proposal(task["expected"], "incorrect", rep)
            result["proposal_schedule"].append(dict(task_id=task_id, repetition=rep,
                    full_information_reference=task["expected"], injected_original_incorrect_proposal=candidate,
                    available_information_references=task["available_information_references"],
                    original_correct_proposal_correct_by_view={view: task["expected"] == ref for view, ref in task["available_information_references"].items()},
                    original_incorrect_proposal_correct_by_view={view: candidate == ref for view, ref in task["available_information_references"].items()}))
    for trial_id, scheduled in schedule.items():
        row = dict(trial_id=trial_id, task_id=scheduled["task_id"], repetition=scheduled["repetition"],
                   condition_id=scheduled["condition"]["id"],
                   state="attempt_started" if trial_id in uncertain else "missing")
        if trial_id in records:
            record = records[trial_id]
            row.update(state=record["state"], cost_usd=record["cost_usd"],
                       response_model=(record.get("response") or {}).get("model"),
                       input_tokens=(record.get("response") or {}).get("input_tokens"),
                       output_tokens=(record.get("response") or {}).get("output_tokens"))
            row.update({key: ((record.get("response") or {}).get("metadata") or {}).get(key)
                        for key in ("cached_input_tokens", "reasoning_tokens", "finish_reason")})
            for oracle, field in ORACLES.items():
                row.update({f"{oracle}_correct": record[field]["correct"],
                            f"{oracle}_false_support": record[field]["unjustified"],
                            f"{oracle}_proposal_correct": initial_correct(record, oracle),
                            f"{oracle}_transition": transition(record, oracle)})
        result["trials"].append(row)
    result["interpretation"] = {
        "full_information": "Agreement with the original full-observation task reference; original correct/incorrect proposal labels refer to this oracle.",
        "available_information": "Correctness under the observations actually supplied, using the frozen interpreter oracle; proposals themselves are not evidence.",
        "contrasts": "Left minus right. Positive correctness differences favour left; positive false-support differences favour right. Available-information targets and proposal strata can change across views; inspect reference_changed_pairs.",
        "transitions": "Each oracle independently classifies the proposed answer. Damage is failure among correct proposals; correction is success among incorrect proposals. Absent proposals have neither rate.",
        "uncertainty": "Uncertain attempts have unknown outcomes and remain outside scored denominators, separately from never-recorded scheduled calls. No complete-schedule contrast is reported without every scheduled pair.",
        "false_support": "Any unjustified supported requested claim per finalized attempt. Malformed/provider-error content is not admitted to the score; zero here does not establish absence of false assertions in that content."}
    result["interpretation"]["constant_label_baselines"] = "Deterministic always-label predictions for every requested claim, scored against each oracle. Scheduled baselines use the entire frozen schedule; finalized-attempt baselines use only measured endpoint positions. These make no model calls."
    result["limitations"] = [
        "Finite exposed diagnostic; no population p-values, equivalence claim or held-out engineering transfer inference.",
        "Five selected tasks in three families in the planned diagnostic; task variants, repetitions and condition pairs are dependent.",
        "Wrong proposals rotate alternative labels with repetition, mixing error type with run variability; they are not natural producer errors.",
        "Status correctness and public justifications do not establish a cognitive mechanism or independent verification.",
        "Scope-mismatched records are not a neutral prompt-length control; computed conclusions carry useful answer information.",
        "Totals pooling conditions are accounting summaries, not a primary treatment estimand. Frozen interpreter oracles are not independent human ratings."]
    return result


def write_outputs(result, output):
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")

    def write_table(suffix, rows):
        path = output.with_name(output.stem + "." + suffix + ".csv")
        fields = list(dict.fromkeys(key for row in rows for key in row))
        with path.open("w", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)

    def summaries(items):
        for item in items:
            for oracle, metric in item["metrics"].items():
                row = {k: item[k] for k in ("task_id", "family", "id", "notation", "candidate_quality", "information",
                       "scheduled", "finalized_attempts", "uncertain_attempts", "missing_scheduled", "complete_responses",
                       "malformed_responses", "provider_errors", "provider_errors_length") if k in item}
                row["oracle"] = oracle
                for name in ("correctness", "false_support", "damage", "correction"):
                    row.update({name + "_" + k: v for k, v in metric[name].items()})
                row.update({k: v for k, v in item["resources"].items() if not isinstance(v, dict)})
                for name in ("input_tokens", "output_tokens", "cached_input_tokens", "reasoning_tokens"):
                    row.update({name + "_" + k: v for k, v in item["resources"][name].items()})
                yield row

    write_table("conditions", list(summaries(result["conditions"])))
    write_table("tasks", list(summaries(result["task_conditions"])))
    contrasts = []
    for item in result["paired_comparisons"]:
        for oracle, metric in item["metrics"].items():
            contrasts.append({**{k: item[k] for k in ("name", "left", "right", "scheduled_pairs", "paired_finalized_attempts", "coverage_complete")},
                              "oracle": oracle, **{k: v for k, v in metric.items() if not isinstance(v, (dict, list))},
                              **metric["paired_outcomes"]})
    write_table("contrasts", contrasts)
    write_table("transitions", [dict(condition_id=item["id"], oracle=oracle,
                finalized_attempts=item["finalized_attempts"], **metric["transitions"])
                for item in result["conditions"] for oracle, metric in item["metrics"].items()])
    write_table("trials", result["trials"])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_directory", type=Path)
    parser.add_argument("--output", type=Path, required=True, help="Analysis JSON; compact CSV tables are written alongside")
    args = parser.parse_args()
    result = analyse(args.run_directory)
    write_outputs(result, args.output)
    print(json.dumps({k: result[k] for k in ("scheduled", "finalized_attempts", "uncertain_attempts", "missing_scheduled", "all_scheduled_finalized")}))


if __name__ == "__main__":
    main()
