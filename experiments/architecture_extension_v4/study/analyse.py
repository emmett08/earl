"""Analyse a v4 study without dropping assigned but unobserved sequences.

Each B→C→D clone is the assignment unit. A contrast requires all three arms
in every preallocated block and every block in each selected system. Missing
records, invalid independent assessments and synthetic smoke runs cannot be
turned into zero durations or empirical treatment effects.
"""

from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
import math
import subprocess
import sys
import tempfile
from decimal import Decimal
from pathlib import Path
from typing import Any

from runner_capture import digest, tree_digest, tree_entries
from masked_review import COMMON as REVIEW_COMMON, SYSTEM as REVIEW_SYSTEM


HERE = Path(__file__).resolve().parent
SYSTEMS = HERE.parent / "systems"
STAGES = ("B", "C", "D")
ARMS = ("P0", "P1", "P2")
TOKEN_FIELDS = ("input_tokens", "cached_input_tokens", "cache_read_input_tokens",
                "cache_write_input_tokens", "cache_creation_input_tokens",
                "output_tokens", "reasoning_output_tokens")


def _read(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected a JSON object: {path}")
    return value


def _number(value: Any, name: str) -> float:
    if type(value) not in (float, int) or not math.isfinite(value) or value < 0:
        raise ValueError(f"{name} must be a finite non-negative number")
    return float(value)


def _sha(value: Any, name: str) -> str:
    if (not isinstance(value, str) or len(value) != 64 or
            any(c not in "0123456789abcdef" for c in value)):
        raise ValueError(f"{name} must be a lowercase SHA-256 digest")
    return value


def _source_digest(candidate: Path) -> str:
    paths = sorted((path for path in candidate.rglob("*.py")
                    if not any(part in {"__pycache__", ".venv", ".pytest_cache"}
                               for part in path.relative_to(candidate).parts)),
                   key=lambda path: path.relative_to(candidate).as_posix())
    architecture = candidate / "ARCHITECTURE.md"
    if architecture.is_file():
        paths.append(architecture)
    value = hashlib.sha256()
    for path in sorted(paths, key=lambda p: p.relative_to(candidate).as_posix()):
        value.update(path.relative_to(candidate).as_posix().encode("utf-8"))
        value.update(b"\0")
        value.update(hashlib.sha256(path.read_bytes()).hexdigest().encode("ascii"))
        value.update(b"\n")
    return value.hexdigest()


def _assignments(manifest: dict[str, Any]) -> tuple[list[dict[str, str]], int]:
    if manifest.get("schema") != "architecture-extension-v4/manifest/1":
        raise ValueError("unsupported assignment manifest")
    systems = manifest.get("systems")
    repeats = manifest.get("replicate_blocks_per_system")
    blocks = manifest.get("blocks")
    cap = manifest.get("wall_cap_seconds")
    if (not isinstance(systems, list) or len(systems) < 3 or
            len(set(systems)) != len(systems) or
            type(repeats) is not int or repeats < 2 or
            not isinstance(blocks, list) or len(blocks) != len(systems) * repeats or
            type(cap) is not int or not 1 <= cap <= 1800):
        raise ValueError("invalid system, replicate, block or cap allocation")
    counts = {system: 0 for system in systems}
    seen: set[str] = set()
    expected: list[dict[str, str]] = []
    for block in blocks:
        if not isinstance(block, dict):
            raise ValueError("block must be an object")
        block_id, system = block.get("id"), block.get("system")
        if not isinstance(block_id, str) or block_id in seen or system not in counts:
            raise ValueError("duplicate block or unknown system")
        seen.add(block_id)
        counts[system] += 1
        allocation = block.get("assignments")
        if not isinstance(allocation, list) or len(allocation) != 3:
            raise ValueError(f"block {block_id} must have three clones")
        if {row.get("arm") for row in allocation if isinstance(row, dict)} != set(ARMS):
            raise ValueError(f"block {block_id} does not allocate one of each arm")
        clone_ids = [row.get("clone") for row in allocation]
        if any(not isinstance(clone, str) or not clone for clone in clone_ids) or len(set(clone_ids)) != 3:
            raise ValueError(f"block {block_id} has invalid clone identities")
        for row in allocation:
            for stage in STAGES:
                expected.append({"system": system, "block": block_id,
                                 "clone": row["clone"], "arm": row["arm"], "stage": stage})
    if any(count != repeats for count in counts.values()):
        raise ValueError("system block counts differ from registered replication")
    return expected, cap


def _findings(assessment: dict[str, Any]) -> dict[str, dict[str, Any]]:
    findings = assessment.get("findings")
    if findings is None:
        checks = assessment.get("checks")
        if not isinstance(checks, list) or not checks:
            raise ValueError("sealed assessment omitted findings")
        findings = {}
        for check in checks:
            if not isinstance(check, dict) or check.get("id") in findings:
                raise ValueError("duplicate or malformed sealed check")
            findings[check["id"]] = check
    if not isinstance(findings, dict) or not findings or any(
            not isinstance(name, str) or not name or
            not isinstance(value, dict) or value.get("status") not in {"pass", "fail", "invalid"}
            for name, value in findings.items()):
        raise ValueError("malformed sealed findings")
    if isinstance(assessment.get("checks"), list):
        check_statuses = {check.get("id"): check.get("status")
                          for check in assessment["checks"] if isinstance(check, dict)}
        if check_statuses != {name: value["status"] for name, value in findings.items()}:
            raise ValueError("checks and findings disagree")
    return findings


def _replay(fixture: Path, source: Path, stage: str, expected: dict[str, Any]) -> None:
    with tempfile.TemporaryDirectory(prefix="v4-sealed-replay-") as temporary:
        output = Path(temporary) / "assessment.json"
        call = subprocess.run(
            [sys.executable, str(fixture / "host/assess.py"), "--source", str(source),
             "--stage", stage, "--output", str(output)],
            cwd=temporary, capture_output=True, text=True, timeout=180, check=False,
        )
        if call.returncode not in (0, 2) or not output.is_file():
            raise ValueError("independent sealed assessor replay did not produce a record")
        if _read(output) != expected:
            raise ValueError("independent sealed assessor replay differs from retained result")


def _sealed(row: dict[str, Any], episode: Path, cap: int, fixture: Path,
            *, replay: bool) -> dict[str, Any]:
    recorded = _read(episode / "episode.json")
    if recorded.get("schema") != "architecture-extension-v4/episode/1":
        raise ValueError("unexpected episode schema")
    for key in ("system", "block", "clone", "arm", "stage"):
        if recorded.get(key) != row[key]:
            raise ValueError(f"assigned {key} differs from sealed episode")
    source = episode / "source"
    if not source.is_dir():
        raise ValueError("candidate snapshot missing")
    input_record = _read(episode / "input.json")
    output_record = _read(episode / "output.json")
    invocation = _read(episode / "invocation.json")
    assessment = _read(episode / "assessment.json")
    resource = _read(episode / "resource-use.json")
    packet = _read(episode / "packet-host.json")
    input_hash = _sha(recorded.get("input_source_tree_sha256"), "input source")
    output_hash = _sha(recorded.get("output_source_tree_sha256"), "output source")
    if input_record.get("source_tree_sha256") != input_hash or output_record.get("source_tree_sha256") != output_hash:
        raise ValueError("input/output source digest disagrees with episode")
    rejected = output_record.get("rejected_candidate_entries", [])
    if (not isinstance(rejected, list) or any(not isinstance(item, str) for item in rejected) or
            recorded.get("candidate_invalid_entries", []) != rejected):
        raise ValueError("invalid candidate entries differ from retained output snapshot")
    if tree_digest(tree_entries(source)) != output_hash:
        raise ValueError("retained source differs from sealed whole-tree digest")
    if assessment.get("system") != row["system"] or assessment.get("stage") != row["stage"]:
        raise ValueError("assessor identity differs from assigned unit")
    source_hash = _source_digest(source)
    if (assessment.get("source_sha256") != source_hash and not (
            assessment.get("source_sha256") is None and assessment.get("valid") is False and
            assessment.get("invalid_kind") == "candidate_source")):
        raise ValueError("assessor source digest differs from retained candidate")
    assessor_hash = _sha(recorded.get("assessment_sha256"), "assessment")
    if assessor_hash != digest(episode / "assessment.json"):
        raise ValueError("assessor output digest changed after episode seal")
    findings = _findings(assessment)
    statuses = [value["status"] for value in findings.values()]
    counts = {key: statuses.count(key) for key in ("pass", "fail", "invalid")}
    if (assessment.get("passed"), assessment.get("total"), assessment.get("valid")) != (
            counts["pass"], len(statuses), counts["invalid"] == 0):
        raise ValueError("assessor counts or validity disagree with sealed findings")
    if (recorded.get("assessor_passed"), recorded.get("assessor_failed"),
            recorded.get("assessor_invalid")) != (
            counts["pass"], counts["fail"], counts["invalid"]):
        raise ValueError("episode assessor counts disagree with sealed findings")
    if replay:
        _replay(fixture, source, row["stage"], assessment)
    if invocation.get("wall_cap_seconds") != cap or invocation.get("system") != row["system"] or (
            invocation.get("block"), invocation.get("clone"), invocation.get("arm"),
            invocation.get("stage")) != (
            row["block"], row["clone"], row["arm"], row["stage"]):
        raise ValueError("invocation identity or wall cap differs from manifest")
    actual = _number(recorded.get("actual_agent_wall_seconds"), "agent elapsed")
    acquisition = _number(recorded.get("packet_acquisition_seconds"), "packet acquisition")
    host_assessor = _number(recorded.get("assessor_host_seconds_excluded_from_treatment"),
                            "independent assessor elapsed")
    if abs(actual - _number(invocation.get("actual_wall_seconds"), "invocation elapsed")) > 1e-6:
        raise ValueError("episode and invocation elapsed times disagree")
    if (recorded.get("agent_exit_code"), recorded.get("agent_timed_out")) != (
            invocation.get("exit_code"), invocation.get("timed_out")):
        raise ValueError("episode and invocation exit status disagree")
    if type(recorded.get("agent_timed_out")) is not bool or type(recorded.get("complete")) is not bool:
        raise ValueError("episode timeout or completion must be Boolean")
    complete = (counts["fail"] == 0 and counts["invalid"] == 0 and not rejected and
                invocation["exit_code"] == 0 and not invocation["timed_out"])
    if recorded["complete"] != complete:
        raise ValueError("episode completion differs from sealed assessor and exit status")
    q = acquisition + (min(actual, cap) if complete else cap)
    if abs(q - _number(recorded.get("failure_penalised_seconds"), "penalised elapsed")) > 1e-6:
        raise ValueError("failure penalty disagrees with frozen scoring rule")
    if resource.get("usage") != recorded.get("resource_use"):
        raise ValueError("resource-use episode and captured trace disagree")
    if resource.get("conditional_scenario") is not None:
        from price import scenario_from_cli_turns
        if scenario_from_cli_turns(recorded["resource_use"]) != resource["conditional_scenario"]:
            raise ValueError("coding conditional price scenario differs from reported token classes")
    if (episode / "price.json").is_file():
        price = _read(episode / "price.json")
        if price.get("exact") != recorded.get("price") or price.get(
                "conditional_scenario") != resource.get("conditional_scenario"):
            raise ValueError("episode price and conditional scenario disagree with retained resource record")
    trace = episode / "agent.jsonl"
    if not trace.is_file() or resource.get("agent_trace_sha256") != digest(trace):
        raise ValueError("resource trace changed after capture")
    if recorded.get("smoke_only") is not invocation.get("smoke_only"):
        raise ValueError("episode and invocation smoke labels disagree")
    if row["arm"] == "P0":
        if acquisition != 0 or packet.get("status") != "no_packet" or recorded.get("packet_shared_material_digest") is not None:
            raise ValueError("P0 acquired intervention material")
    else:
        if packet.get("status") != "matched_shared_material" or packet.get("selected_arm") != row["arm"]:
            raise ValueError("assigned packet delivery/parity attestation missing")
        shared_hash = packet.get("shared_material_digest")
        if (recorded.get("packet_shared_material_digest") != shared_hash or
                packet.get("source_tree_sha256") != input_hash):
            raise ValueError("agent packet is not bound to its current input source")
        selected, alternative = packet.get("selected"), packet.get("counterfactual")
        if not isinstance(selected, dict) or not isinstance(alternative, dict) or any(
                selected.get(field) != alternative.get(field) for field in
                ("facts", "guidance", "status", "selected_action", "shared_material_digest", "source_tree_sha256")):
            raise ValueError("P1/P2 common material differs within the episode")
    totals = recorded["resource_use"].get("totals")
    if totals is not None:
        if not isinstance(totals, dict):
            raise ValueError("usage totals must be an object or null")
        for field in TOKEN_FIELDS:
            value = totals.get(field)
            if value is not None and (type(value) is not int or value < 0):
                raise ValueError(f"invalid {field} usage")
    critical_ids = recorded.get("critical_check_ids")
    unrun = sorted(set(critical_ids or []) - set(findings))
    if critical_ids is not None and (not isinstance(critical_ids, list) or
            recorded.get("critical_checks_unrun_due_to_candidate_import") != unrun or
            recorded.get("critical_checks_passed") is not all(
                findings.get(name, {}).get("status") == "pass" for name in critical_ids)):
        raise ValueError("episode critical checks or unrun identities disagree with assessor")
    if unrun and not ("candidate.import" in findings or assessment.get("invalid_kind") == "candidate_source"):
        raise ValueError("unrun critical check is not explained by candidate import failure")
    return {**row, "status": "sealed", "source_sha256": source_hash,
            "assessor_source_sha256": assessment.get("source_sha256"),
            "input_source_tree_sha256": input_hash, "output_source_tree_sha256": output_hash,
            "findings": {name: value["status"] for name, value in findings.items()},
            "assessor_passed": counts["pass"], "assessor_failed": counts["fail"],
            "assessor_invalid": counts["invalid"], "verified_complete": complete,
            "actual_agent_wall_seconds": actual, "packet_acquisition_seconds": acquisition,
            "assessor_host_seconds_excluded_from_treatment": host_assessor,
            "failure_penalised_seconds": q, "smoke_only": recorded["smoke_only"],
            "usage_status": recorded["resource_use"].get("status"),
            "token_totals": totals, "provider_bill": resource.get("provider_bill"),
            "critical_check_ids": critical_ids, "critical_unrun_ids": unrun,
            "candidate_invalid_entries": rejected, "price": recorded.get("price"),
            "conditional_rate_scenario": resource.get("conditional_scenario")}


def _critical(manifest: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    mapping = manifest.get("critical_check_ids")
    if not isinstance(mapping, dict):
        return {"status": "not_predeclared", "per_episode": None}
    out = []
    for row in rows:
        system_checks = mapping.get(row["system"])
        names = system_checks.get(row["stage"]) if isinstance(system_checks, dict) else None
        if not isinstance(names, list) or not names or len(set(names)) != len(names) or not all(
                isinstance(name, str) and name for name in names):
            return {"status": "not_predeclared", "per_episode": None}
        findings = row.get("findings")
        if findings is None:
            out.append({"system": row["system"], "block": row["block"], "arm": row["arm"],
                        "clone": row["clone"], "stage": row["stage"], "status": "pending"})
            continue
        if row.get("critical_check_ids") is not None and row["critical_check_ids"] != names:
            raise ValueError("episode and manifest critical check identities differ")
        absent = set(names) - set(findings)
        if absent != set(row.get("critical_unrun_ids", [])):
            raise ValueError("predeclared critical check absent without classified candidate import")
        critical = {name: findings.get(name, "unrun") for name in names}
        status = "invalid_unrun" if "unrun" in critical.values() else (
            "invalid" if "invalid" in critical.values() else (
            "fail" if "fail" in critical.values() else "pass")
            )
        out.append({"system": row["system"], "block": row["block"], "arm": row["arm"],
                    "clone": row["clone"], "stage": row["stage"],
                    "status": status, "findings": critical})
    return {"status": "reported", "per_episode": out}


def _sealed_at(value: Any, name: str) -> datetime:
    if not isinstance(value, str):
        raise ValueError(f"{name} has no seal timestamp")
    try:
        timestamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError(f"{name} has an invalid seal timestamp") from error
    if timestamp.tzinfo is None:
        raise ValueError(f"{name} seal timestamp has no timezone")
    return timestamp


def _review_form(form: dict[str, Any], release_cases: dict[str, dict[str, Any]],
                 label: str) -> dict[str, dict[str, Any]]:
    if form.get("schema") != "architecture-extension-v4/masked-review/1":
        raise ValueError(f"{label} has wrong masked-review schema")
    if not isinstance(form.get("reviewer_id"), str) or not form["reviewer_id"].strip():
        raise ValueError(f"{label} lacks independent reviewer identity")
    _sealed_at(form.get("sealed_at_utc"), label)
    cases = form.get("cases")
    if not isinstance(cases, list) or len(cases) != len(release_cases):
        raise ValueError(f"{label} has incomplete masked cases")
    keyed: dict[str, dict[str, Any]] = {}
    for case in cases:
        if not isinstance(case, dict):
            raise ValueError(f"{label} contains malformed review case")
        case_id = case.get("candidate_id")
        expected = release_cases.get(case_id)
        if expected is None or case_id in keyed:
            raise ValueError(f"{label} has duplicate or unassigned candidate")
        if any(case.get(field) != expected[field] for field in
               ("candidate_id", "sequence_id", "system", "stage", "source_tree_sha256")):
            raise ValueError(f"{label} case differs from masked source identity")
        _sealed_at(case.get("reviewed_at_utc"), f"{label} {case_id}")
        anchors = set(REVIEW_COMMON) | set(REVIEW_SYSTEM[case["system"]])
        findings = case.get("findings")
        if not isinstance(findings, dict) or set(findings) != anchors:
            raise ValueError(f"{label} omitted a predeclared review anchor")
        for anchor, finding in findings.items():
            if not isinstance(finding, dict) or finding.get("status") not in {
                    "present", "absent", "unresolved"}:
                raise ValueError(f"{label} {case_id}/{anchor} has no completed status")
            if finding.get("severity") not in {None, "minor", "major", "critical"}:
                raise ValueError(f"{label} {case_id}/{anchor} has invalid severity")
            if finding["status"] == "present" and (
                    not isinstance(finding.get("locations"), list) or not finding["locations"] or
                    not isinstance(finding.get("mechanism"), str) or not finding["mechanism"].strip()):
                raise ValueError(f"{label} {case_id}/{anchor} lacks location and mechanism")
        if not isinstance(case.get("additional_findings"), list):
            raise ValueError(f"{label} {case_id} additional findings are malformed")
        if not isinstance(case.get("overall_architecture_judgement"), str) or not case[
                "overall_architecture_judgement"].strip():
            raise ValueError(f"{label} {case_id} has no overall architecture judgement")
        if not isinstance(case.get("overall_rationale"), str) or not case["overall_rationale"].strip():
            raise ValueError(f"{label} {case_id} has no review rationale")
        keyed[case_id] = case
    return keyed


def _masked_reviews(releases: list[Path], mappings: list[Path],
                    rows: list[dict[str, Any]], result_dirs: list[Path]) -> dict[str, Any]:
    if not releases and not mappings:
        return {"status": "pending_sealed_adjudication", "result": None,
                "reason": "two independent masked reviews have not been provided"}
    if len(releases) != len(mappings) or not releases:
        raise ValueError("each masked review release needs one separate host-only mapping")
    if any(row["status"] != "sealed" for row in rows):
        return {"status": "pending_incomplete_candidates", "result": None}
    # Validate every blinded report and any necessary adjudication before
    # opening any host-only treatment mapping.
    blinded: list[tuple[Path, dict[str, dict[str, Any]], dict[str, Any], dict[str, Any]]] = []
    for release in releases:
        release = release.resolve()
        try:
            catalogue = _read(release / "release.json")
            cases = catalogue["cases"]
            if catalogue.get("schema") != "architecture-extension-v4/masked-review/1" or not isinstance(cases, list):
                raise ValueError("masked review release has invalid catalogue")
            release_cases = {case["candidate_id"]: case for case in cases}
            if len(release_cases) != len(cases) or not release_cases:
                raise ValueError("masked review release has duplicate candidates")
            reviewer_paths = (release / "reviewer-1/form.json", release / "reviewer-2/form.json")
            originals = [_read(path) for path in reviewer_paths]
            reviews = [_review_form(form, release_cases, str(path))
                       for form, path in zip(originals, reviewer_paths)]
            if originals[0]["reviewer_id"] == originals[1]["reviewer_id"]:
                raise ValueError("same reviewer identity appears twice")
            discrepancies: dict[str, set[str]] = {}
            for case_id in release_cases:
                first, second = reviews[0][case_id], reviews[1][case_id]
                different = {anchor for anchor in first["findings"] if (
                    first["findings"][anchor]["status"], first["findings"][anchor]["severity"]) !=
                    (second["findings"][anchor]["status"], second["findings"][anchor]["severity"])}
                if first["additional_findings"] != second["additional_findings"]:
                    different.add("additional_findings")
                if different:
                    discrepancies[case_id] = different
            resolution: dict[str, Any] = {}
            if discrepancies:
                adjudication = _read(release / "adjudication.json")
                if adjudication.get("schema") != catalogue["schema"] or not isinstance(
                        adjudication.get("adjudicator_id"), str) or not adjudication["adjudicator_id"].strip():
                    raise ValueError("disputed reviews lack a named adjudicator")
                if adjudication["adjudicator_id"] in {form["reviewer_id"] for form in originals}:
                    raise ValueError("adjudicator is one of the independent reviewers")
                seal = _sealed_at(adjudication.get("sealed_at_utc"), "adjudication")
                if any(seal <= _sealed_at(form["sealed_at_utc"], "reviewer") for form in originals):
                    raise ValueError("adjudication was sealed before both original reviews")
                for index, path in enumerate(reviewer_paths, 1):
                    if adjudication.get(f"reviewer_{index}_sealed_sha256") != digest(path):
                        raise ValueError("adjudication does not bind the sealed original review")
                adjudicated = adjudication.get("cases")
                if not isinstance(adjudicated, list):
                    raise ValueError("adjudication omitted masked cases")
                case_map = {case.get("candidate_id"): case for case in adjudicated
                            if isinstance(case, dict)}
                if len(case_map) != len(release_cases):
                    raise ValueError("adjudication omitted a masked case")
                for case_id, disputed in discrepancies.items():
                    item = case_map[case_id]
                    decisions = item.get("resolution")
                    if not isinstance(decisions, dict) or not disputed <= set(decisions):
                        raise ValueError(f"adjudication omitted disputed grounds for {case_id}")
                    if not isinstance(item.get("grounds"), str) or not item["grounds"].strip():
                        raise ValueError(f"adjudication has no grounds for {case_id}")
                    if item.get("unresolved"):
                        raise ValueError(f"adjudication retains unresolved disagreement for {case_id}")
                    for anchor in disputed - {"additional_findings"}:
                        decision = decisions[anchor]
                        if not isinstance(decision, dict) or decision.get("status") not in {
                                "present", "absent", "unresolved"} or decision.get("severity") not in {
                                None, "minor", "major", "critical"}:
                            raise ValueError(f"adjudication has malformed resolution for {case_id}/{anchor}")
                    if "additional_findings" in disputed and not isinstance(
                            decisions["additional_findings"], list):
                        raise ValueError(f"adjudication omitted additional findings for {case_id}")
                resolution = case_map
            blinded.append((release, release_cases, {"reviewer_1": reviews[0],
                                                      "reviewer_2": reviews[1],
                                                      "discrepancies": discrepancies}, resolution))
        except (OSError, ValueError, KeyError, TypeError) as error:
            return {"status": "pending_sealed_adjudication", "result": None,
                    "reason": str(error), "blinded_release": str(release)}
    # Every blinded release is sealed. Only now join its opaque IDs to arms.
    episode_lookup = {(row["block"], row["clone"], row["stage"]): row for row in rows}
    expected_runs = {path.resolve() for path in result_dirs}
    linked: list[dict[str, Any]] = []
    mapped: set[tuple[str, str, str]] = set()
    for (release, release_cases, reviews, resolutions), mapping_path in zip(blinded, mappings):
        mapping = _read(mapping_path.resolve())
        if (mapping.get("schema") != "architecture-extension-v4/masked-review/1" or
                mapping.get("host_only") is not True or
                Path(mapping.get("review_release", "")).resolve() != release or
                Path(mapping.get("source_run", "")).resolve() not in expected_runs):
            raise ValueError("host mapping does not bind this sealed review and source run")
        items = mapping.get("cases")
        if not isinstance(items, list) or len(items) != len(release_cases):
            raise ValueError("host mapping has incomplete candidate identities")
        for item in items:
            if not isinstance(item, dict):
                raise ValueError("host mapping case is malformed")
            case_id = item.get("candidate_id")
            release_case = release_cases.get(case_id)
            if release_case is None or any(item.get(field) != release_case.get(field) for field in (
                    "candidate_id", "sequence_id", "system", "stage", "source_tree_sha256")):
                raise ValueError("host mapping changed masked candidate identity")
            identity = item.get("block"), item.get("clone"), item.get("stage")
            episode = episode_lookup.get(identity)
            if episode is None or identity in mapped or any(item.get(field) != episode.get(field) for field in (
                    "system", "arm")) or item["source_tree_sha256"] != episode["output_source_tree_sha256"]:
                raise ValueError("host mapping differs from sealed assigned source")
            mapped.add(identity)
            first = reviews["reviewer_1"][case_id]
            second = reviews["reviewer_2"][case_id]
            final_findings = {}
            for anchor, finding in first["findings"].items():
                if anchor in reviews["discrepancies"].get(case_id, set()):
                    final_findings[anchor] = resolutions[case_id]["resolution"][anchor]
                else:
                    final_findings[anchor] = {"status": finding["status"], "severity": finding["severity"]}
            linked.append({"system": episode["system"], "block": episode["block"],
                           "clone": episode["clone"], "arm": episode["arm"], "stage": episode["stage"],
                           "source_tree_sha256": episode["output_source_tree_sha256"],
                           "candidate_id": case_id, "reviewer_1": first,
                           "reviewer_2": second, "adjudicated_findings": final_findings,
                           "additional_findings": resolutions[case_id]["resolution"]["additional_findings"]
                           if "additional_findings" in reviews["discrepancies"].get(case_id, set())
                           else first["additional_findings"]})
    if mapped != set(episode_lookup):
        return {"status": "pending_unreviewed_candidates", "result": None,
                "sealed_review_cases": len(mapped), "expected_cases": len(episode_lookup)}
    return {"status": "reported_masked_findings", "result": linked,
            "interpretation": "Source-grounded adjudicated anchors; no automatic architecture or debt score"}


def _decision_response(trace: Path, agent: str) -> str:
    raw = trace.read_text(encoding="utf-8")
    if agent == "stub":
        return raw.strip()
    messages: list[str] = []
    for line in raw.splitlines():
        if not line.strip():
            continue
        event = json.loads(line)
        item = event.get("item") if isinstance(event, dict) else None
        if isinstance(item, dict) and item.get("type") == "agent_message" and isinstance(
                item.get("text"), str):
            messages.append(item["text"])
    return messages[-1] if messages else ""


def _sealed_decision(assignment: dict[str, str], case_id: str, directory: Path,
                     definition: dict[str, Any], case_root: Path, cap: int) -> dict[str, Any]:
    row = _read(directory / "decision.json")
    if row.get("schema") != "architecture-extension-v4/decision-probe/1" or any(
            row.get(key) != assignment[key] for key in ("system", "block", "clone", "arm")) or row.get(
            "case_id") != case_id:
        raise ValueError("decision record differs from preallocated case or arm")
    source = case_root / assignment["system"] / case_id / "source"
    state = case_root / assignment["system"] / case_id / "state.json"
    source_hash = tree_digest(tree_entries(source))
    if (row.get("source_tree_sha256") != source_hash or
            definition.get("source_tree_sha256") != source_hash or
            digest(state) != definition.get("state_sha256")):
        raise ValueError("decision case source or typed state differs from frozen oracle")
    input_record = _read(directory / "input.json")
    if input_record.get("case_source_tree_sha256") != source_hash:
        raise ValueError("agent decision input differs from registered case source")
    if input_record.get("files") != tree_entries(source):
        raise ValueError("decision input file inventory differs from registered case source")
    prompt = directory / "visible-prompt.md"
    instructions = directory / "visible-instructions.md"
    if digest(prompt) != input_record.get("visible_prompt_sha256"):
        raise ValueError("retained decision prompt changed after invocation")
    if instructions.read_text(encoding="utf-8") != (
            "Read the current decision case. Do not change source files. "
            "Return only the requested JSON action.\n"):
        raise ValueError("retained decision instructions differ from registered invocation")
    packet = _read(directory / "packet-host.json")
    selected = packet.get("selected")
    if not isinstance(selected, dict) or any(selected.get(field) != expected for field, expected in (
            ("system", assignment["system"]), ("case_id", case_id),
            ("arm", assignment["arm"]), ("source_tree_sha256", source_hash),
            ("state_sha256", definition["state_sha256"]),
            ("expected_action", definition["expected_action"]),
            ("allowed_actions", definition["allowed_actions"]))):
        raise ValueError("delivered decision packet differs from registered source/state/action")
    shared = _sha(selected.get("shared_material_digest"), "decision common material")
    if packet.get("shared_material_digest") != shared or row.get("packet_shared_material_digest") != shared:
        raise ValueError("decision common material digest changed after delivery")
    registered_state = _read(state)
    visible_state = {key: value for key, value in registered_state.items() if key != "case_id"}
    if selected.get("facts") != visible_state or selected.get("guidance") != definition.get("guidance"):
        raise ValueError("delivered decision facts or guidance differ from registered case")
    if prompt.read_text(encoding="utf-8") != selected["prompt_text"].rstrip() + "\n":
        raise ValueError("agent did not receive the retained selected decision prompt")
    if assignment["arm"] == "P2" and not isinstance(selected.get("formal"), dict):
        raise ValueError("P2 decision packet omitted formal argument")
    if assignment["arm"] in {"P0", "P1"} and "formal" in selected:
        raise ValueError("nonformal arm received extra formal decision argument")
    invocation = _read(directory / "invocation.json")
    if invocation.get("wall_cap_seconds") != cap or any(
            invocation.get(key) != assignment[key] for key in ("system", "block", "clone", "arm")) or (
            invocation.get("case_id") != case_id or invocation.get("smoke_only") is not row.get("smoke_only")):
        raise ValueError("decision invocation differs from assigned case or cap")
    actual = _number(row.get("actual_agent_wall_seconds"), "decision actual elapsed")
    acquisition = _number(row.get("packet_acquisition_seconds"), "decision packet acquisition")
    if abs(actual - _number(invocation.get("actual_wall_seconds"), "decision invocation elapsed")) > 1e-6:
        raise ValueError("decision and invocation elapsed times disagree")
    if (row.get("agent_exit_code"), row.get("agent_timed_out")) != (
            invocation.get("exit_code"), invocation.get("timed_out")):
        raise ValueError("decision invocation status differs from retained record")
    agent_completed = invocation["exit_code"] == 0 and not invocation["timed_out"]
    if row.get("agent_completed") is not agent_completed:
        raise ValueError("decision completion differs from invocation")
    resource = _read(directory / "resource-use.json")
    trace = directory / "agent.jsonl"
    if resource.get("usage") != row.get("resource_use") or resource.get("agent_trace_sha256") != digest(trace):
        raise ValueError("decision resource trace differs from retained record")
    if resource.get("price") != row.get("price"):
        raise ValueError("decision price outcome differs from resource record")
    if resource.get("conditional_scenario") is not None:
        from price import scenario_from_cli_turns
        if scenario_from_cli_turns(row["resource_use"]) != resource["conditional_scenario"]:
            raise ValueError("decision conditional price scenario differs from reported token classes")
    if row.get("conditional_list_price_scenario") != resource.get("conditional_scenario"):
        raise ValueError("decision conditional price scenario differs from retained resource record")
    from decision_probe import score
    replay = score(_decision_response(trace, row.get("agent")),
                   definition["expected_action"], definition["allowed_actions"])
    if replay != row.get("score"):
        raise ValueError("strict decision score differs from retained response")
    if replay.get("status") not in {"correct", "incorrect", "invalid"}:
        raise ValueError("invalid strict decision score")
    return {**assignment, "case_id": case_id, "status": "sealed",
            "source_tree_sha256": source_hash, "state_sha256": definition["state_sha256"],
            "selected_action": replay["selected_action"], "expected_action": definition["expected_action"],
            "score_status": replay["status"] if agent_completed else "invalid_invocation",
            "correct": replay["correct"] if agent_completed and replay["status"] != "invalid" else None,
            "actual_agent_wall_seconds": actual, "packet_acquisition_seconds": acquisition,
            "smoke_only": row["smoke_only"], "token_totals": row["resource_use"].get("totals"),
            "price": row["price"], "conditional_rate_scenario": resource.get("conditional_scenario")}


def _decisions(manifest: dict[str, Any], expected: list[dict[str, str]],
               directories: dict[str, tuple[Path, dict[str, Any]]], case_root: Path,
               *, smoke: bool) -> dict[str, Any]:
    config = manifest.get("decision_probes")
    if (not isinstance(config, dict) or config.get("case_ids") != ["clean", "defeated"] or
            type(config.get("wall_cap_seconds")) is not int or config["wall_cap_seconds"] != 120):
        return {"status": "not_predeclared", "coverage": None, "probes": None,
                "pairs": None, "system_balanced_difference": None}
    cases = _read(case_root / "cases.json")
    if cases.get("schema") != "architecture-v4-decision-cases/1":
        raise ValueError("decision-case oracle schema differs from registered fixture")
    assignments = [row for row in expected if row["stage"] == "D"]
    probe_rows = []
    for row in assignments:
        for case_id in config["case_ids"]:
            identity = {key: row[key] for key in ("system", "block", "clone", "arm")}
            identity["case_id"] = case_id
            selected = directories.get(row["block"])
            if selected is None:
                probe_rows.append({**identity, "status": "missing_block"})
                continue
            result_dir, summary = selected
            directory = result_dir / "blocks" / row["block"] / row["clone"] / f"decision-{case_id}"
            retained = summary.get("decision_probes", [])
            if not isinstance(retained, list):
                raise ValueError("run summary decision-probes field is malformed")
            matched = [item for item in retained if isinstance(item, dict) and all(
                item.get(key) == identity[key] for key in identity)]
            if len(matched) > 1:
                raise ValueError("duplicate assigned decision in run summary")
            if not matched and not directory.exists():
                probe_rows.append({**identity, "status": "missing_probe"})
                continue
            if not matched or not (directory / "decision.json").is_file():
                probe_rows.append({**identity, "status": "unsealed_probe"})
                continue
            try:
                definition = cases["systems"][row["system"]][case_id]
                sealed = _sealed_decision(identity, case_id, directory, definition, case_root,
                                          config["wall_cap_seconds"])
                if _read(directory / "decision.json") != matched[0]:
                    raise ValueError("decision summary differs from retained response record")
            except (OSError, ValueError, KeyError, TypeError) as error:
                probe_rows.append({**identity, "status": "integrity_invalid", "detail": str(error)})
            else:
                probe_rows.append(sealed)
    lookup = {(row["block"], row["clone"], row["case_id"]): row for row in probe_rows}
    pairs = []
    for assignment in assignments:
        clean, defeated = (lookup[(assignment["block"], assignment["clone"], case_id)]
                           for case_id in config["case_ids"])
        both_sealed = clean["status"] == defeated["status"] == "sealed"
        valid = both_sealed and clean["correct"] is not None and defeated["correct"] is not None
        pairs.append({"system": assignment["system"], "block": assignment["block"],
                      "clone": assignment["clone"], "arm": assignment["arm"],
                      "status": "valid_pair" if valid else "pending_or_invalid",
                      "clean": clean["status"], "defeated": defeated["status"],
                      "both_correct": clean["correct"] and defeated["correct"] if valid else None,
                      "changed_to_correct_defeated_action": (clean["correct"] and defeated["correct"] and
                                                             clean["selected_action"] != defeated["selected_action"])
                      if valid else None})
    coverage = {"expected_probes": len(probe_rows),
                "sealed_probes": sum(row["status"] == "sealed" for row in probe_rows),
                "missing_probes": sum(row["status"].startswith("missing") for row in probe_rows),
                "unsealed_probes": sum(row["status"] == "unsealed_probe" for row in probe_rows),
                "integrity_invalid_probes": sum(row["status"] == "integrity_invalid" for row in probe_rows),
                "valid_pairs": sum(pair["status"] == "valid_pair" for pair in pairs)}
    acquisition_complete = (len(directories) == len(manifest["blocks"]) and all(
        summary.get("status") == "complete_acquisition" for _, summary in directories.values()))
    if smoke:
        status = "smoke_only"
    elif not acquisition_complete:
        status = "pending_acquisition_completion"
    elif coverage["valid_pairs"] < len(pairs):
        status = "pending_incomplete_or_invalid_pair"
    else:
        status = "descriptive_complete"
    contrast: dict[str, Any] | None = None
    if status == "descriptive_complete":
        by_block = {(row["block"], row["arm"]): row for row in pairs}
        differences = []
        for block in manifest["blocks"]:
            z = {arm: int(by_block[(block["id"], arm)]["both_correct"]) for arm in ARMS}
            differences.append({"system": block["system"], "block": block["id"],
                                "both_correct": z, "p2_minus_p1": z["P2"] - z["P1"],
                                "p2_minus_p0": z["P2"] - z["P0"]})
        by_system = [{"system": system, **{
            key: sum(b[key] for b in differences if b["system"] == system) / sum(
                b["system"] == system for b in differences)
            for key in ("p2_minus_p1", "p2_minus_p0")}} for system in manifest["systems"]]
        contrast = {"block_differences": differences, "system_differences": by_system,
                    "system_balanced_difference": {key: sum(system[key] for system in by_system) / len(by_system)
                                                  for key in ("p2_minus_p1", "p2_minus_p0")}}
    return {"status": status, "coverage": coverage, "probes": probe_rows,
            "pairs": pairs, "contrast": contrast,
            "interpretation": "Static case-source decision responses, separate from B-C-D implementation"}


def _scenario(rows: list[dict[str, Any]]) -> dict[str, Any]:
    scenarios = [row.get("conditional_rate_scenario") if row.get("status") == "sealed" else None
                 for row in rows]
    if not scenarios or any(not isinstance(value, dict) or value.get("status") != "conditional_scenario"
                            for value in scenarios):
        return {"status": "pending_complete_token_partitions", "low_usd": None,
                "high_usd": None, "covered": sum(isinstance(value, dict) and value.get("status") ==
                                                  "conditional_scenario" for value in scenarios),
                "expected": len(rows)}
    totals = {}
    for field in ("low_usd", "high_usd"):
        try:
            values = [Decimal(row[field]) for row in scenarios]
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError("malformed conditional rate scenario") from error
        if any(not value.is_finite() or value < 0 for value in values):
            raise ValueError("invalid conditional rate scenario amount")
        totals[field] = format(sum(values), "f")
    return {"status": "conditional_scenario", **totals,
            "covered": len(rows), "expected": len(rows),
            "interpretation": "Hypothetical posted Standard API rates; not an invoice bound"}


def analyse(manifest_path: Path, result_dirs: list[Path], *, fixtures: Path = SYSTEMS,
            replay_assessors: bool = True, review_releases: list[Path] | None = None,
            review_mappings: list[Path] | None = None,
            decision_cases: Path = HERE / "decision_cases") -> dict[str, Any]:
    manifest_path, fixtures = manifest_path.resolve(), fixtures.resolve()
    manifest = _read(manifest_path)
    expected, cap = _assignments(manifest)
    manifest_hash = digest(manifest_path)
    keyed = {(row["block"], row["clone"], row["stage"]): row for row in expected}
    directories: dict[str, tuple[Path, dict[str, Any]]] = {}
    deviations: list[dict[str, str]] = []
    smoke = False
    for result_dir in result_dirs:
        result_dir = result_dir.resolve()
        summary = _read(result_dir / "summary.json")
        if summary.get("schema") != "architecture-extension-v4/run/1":
            raise ValueError(f"unsupported result summary: {result_dir}")
        if (summary.get("manifest_sha256") != manifest_hash or
                digest(result_dir / "manifest.json") != manifest_hash):
            raise ValueError(f"result manifest differs from registered allocation: {result_dir}")
        smoke = smoke or summary.get("smoke_only") is True
        selected = summary.get("selected_blocks")
        if not isinstance(selected, list) or not selected:
            raise ValueError("result directory has no selected block identity")
        if summary.get("status") == "stopped_infrastructure_deviation":
            deviations.append({"result_dir": str(result_dir), "detail": "stopped_infrastructure_deviation"})
        for block in selected:
            if block in directories or block not in {row["block"] for row in expected}:
                raise ValueError(f"duplicate or unassigned result block: {block}")
            directories[block] = result_dir, summary
        retained = summary.get("episodes")
        if not isinstance(retained, list):
            raise ValueError("run summary has no episode array")
        identifiers: set[tuple[str, str, str]] = set()
        for item in retained:
            if not isinstance(item, dict):
                raise ValueError("run summary contains malformed episode")
            identity = item.get("block"), item.get("clone"), item.get("stage")
            if identity in identifiers or identity not in keyed or identity[0] not in selected:
                raise ValueError("duplicate or unassigned episode in run summary")
            identifiers.add(identity)
    rows: list[dict[str, Any]] = []
    for row in expected:
        result = directories.get(row["block"])
        if result is None:
            rows.append({**row, "status": "missing_block"})
            continue
        result_dir, summary = result
        episode = result_dir / "blocks" / row["block"] / row["clone"] / row["stage"]
        matched = [item for item in summary["episodes"] if (
            item.get("block"), item.get("clone"), item.get("stage")) == (
            row["block"], row["clone"], row["stage"])]
        if not matched and not episode.exists():
            rows.append({**row, "status": "missing_episode"})
            continue
        if not matched or not (episode / "episode.json").is_file():
            rows.append({**row, "status": "unsealed_episode"})
            continue
        try:
            sealed = _sealed(row, episode, cap, fixtures / row["system"], replay=replay_assessors)
            if _read(episode / "episode.json") != matched[0]:
                raise ValueError("run summary differs from episode record")
        except (ValueError, OSError, KeyError, TypeError, subprocess.TimeoutExpired) as error:
            rows.append({**row, "status": "integrity_invalid", "detail": str(error)})
        else:
            rows.append(sealed)
    by_key = {(row["block"], row["clone"], row["stage"]): row for row in rows}
    baseline = {system: tree_digest(tree_entries(fixtures / system / "source"))
                for system in manifest["systems"]}
    for block in manifest["blocks"]:
        for assigned in block["assignments"]:
            lineage = [by_key[(block["id"], assigned["clone"], stage)] for stage in STAGES]
            for index, episode in enumerate(lineage):
                if episode["status"] != "sealed":
                    continue
                expected_input = baseline[block["system"]] if index == 0 else lineage[index - 1].get(
                    "output_source_tree_sha256")
                if expected_input is not None and episode["input_source_tree_sha256"] != expected_input:
                    episode.update(status="integrity_invalid", detail="B baseline or prior-stage source chain differs")
    lineages = []
    for block in manifest["blocks"]:
        for assigned in block["assignments"]:
            sequence = [by_key[(block["id"], assigned["clone"], stage)] for stage in STAGES]
            ready = all(row["status"] == "sealed" for row in sequence)
            lineages.append({"system": block["system"], "block": block["id"],
                             "clone": assigned["clone"], "arm": assigned["arm"],
                             "status": "sealed" if ready else "pending",
                             "stages": {stage: row["status"] for stage, row in zip(STAGES, sequence)},
                             "q_c_d_seconds": sum(row["failure_penalised_seconds"] for row in sequence[1:])
                             if ready else None,
                             "q_b_c_d_seconds": sum(row["failure_penalised_seconds"] for row in sequence)
                             if ready else None})
    coverage = {"expected_episodes": len(rows),
                "sealed_episodes": sum(row["status"] == "sealed" for row in rows),
                "missing_episodes": sum(row["status"].startswith("missing") for row in rows),
                "unsealed_episodes": sum(row["status"] == "unsealed_episode" for row in rows),
                "integrity_invalid_episodes": sum(row["status"] == "integrity_invalid" for row in rows),
                "invalid_assessor_episodes": sum(row.get("assessor_invalid", 0) > 0 for row in rows)}
    critical = _critical(manifest, rows)
    decisions = _decisions(manifest, expected, directories, decision_cases.resolve(), smoke=smoke)
    reviews = _masked_reviews(review_releases or [], review_mappings or [], rows, result_dirs)
    if smoke:
        contrast: dict[str, Any] = {"status": "smoke_only", "block_differences": None,
                                    "system_differences": None, "system_balanced_difference_seconds": None}
    elif any(summary.get("status") != "complete_acquisition" for _, summary in directories.values()):
        contrast = {"status": "pending_acquisition_completion", "block_differences": None,
                    "system_differences": None, "system_balanced_difference_seconds": None}
    elif coverage["sealed_episodes"] < len(rows):
        contrast = {"status": "pending_incomplete_assignment", "block_differences": None,
                    "system_differences": None, "system_balanced_difference_seconds": None}
    elif coverage["invalid_assessor_episodes"]:
        contrast = {"status": "invalid_assessment", "block_differences": None,
                    "system_differences": None, "system_balanced_difference_seconds": None}
    else:
        by_block = {(row["block"], row["arm"]): row for row in lineages}
        blocks_out = []
        for block in manifest["blocks"]:
            z = {arm: by_block[(block["id"], arm)]["q_c_d_seconds"] for arm in ARMS}
            blocks_out.append({"system": block["system"], "block": block["id"],
                               "q_c_d_seconds": z,
                               "p2_minus_p1_seconds": z["P2"] - z["P1"],
                               "p2_minus_p0_seconds": z["P2"] - z["P0"]})
        systems_out = []
        for system in manifest["systems"]:
            subset = [block for block in blocks_out if block["system"] == system]
            systems_out.append({"system": system, "blocks": len(subset),
                                "p2_minus_p1_seconds": sum(b["p2_minus_p1_seconds"] for b in subset) / len(subset),
                                "p2_minus_p0_seconds": sum(b["p2_minus_p0_seconds"] for b in subset) / len(subset)})
        contrast = {"status": "descriptive_complete", "assignment_unit": "entire B-C-D clone",
                    "block_differences": blocks_out, "system_differences": systems_out,
                    "system_balanced_difference_seconds": {
                        key: sum(system[key] for system in systems_out) / len(systems_out)
                        for key in ("p2_minus_p1_seconds", "p2_minus_p0_seconds")},
                    "uncertainty": "none estimated here; registered cluster/randomisation inference is separate"}
    token_sums: dict[str, int | None] = {}
    for field in TOKEN_FIELDS:
        values = [row.get("token_totals", {}).get(field) if isinstance(row.get("token_totals"), dict)
                  else None for row in rows]
        token_sums[field] = sum(values) if all(value is not None for value in values) else None
    coding_scenario = _scenario(rows)
    probe_scenario = _scenario(decisions.get("probes", []) or [])
    return {"schema": "architecture-extension-v4/analysis/1",
            "manifest_sha256": manifest_hash,
            "status": "complete_descriptive" if contrast["status"] == "descriptive_complete" and
            decisions["status"] == "descriptive_complete" else "pending",
            "coverage": coverage, "episodes": rows, "lineages": lineages,
            "critical_checks": critical, "time_contrast": contrast,
            "decision_probe": decisions,
            "masked_architecture_review": reviews,
            "priced_resource_use": {"status": "pending_verified_request_usage_and_billing",
                                    "list_price_usd": None, "billed_usd": None,
                                    "reported_coding_token_totals": token_sums,
                                    "conditional_coding_rate_scenario": coding_scenario,
                                    "conditional_decision_rate_scenario": probe_scenario},
            "run_deviations": deviations,
            "interpretation": "Assigned-lineage descriptive analysis; no population causal claim or debt valuation"}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--results", action="append", required=True, type=Path,
                        help="Repeat for each single-use runner output directory")
    parser.add_argument("--fixtures", type=Path, default=SYSTEMS)
    parser.add_argument("--decision-cases", type=Path, default=HERE / "decision_cases")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--review-release", action="append", type=Path, default=[],
                        help="Repeat for each completed masked source-review release")
    parser.add_argument("--review-map", action="append", type=Path, default=[],
                        help="Host-only map paired in order with --review-release; read after seals")
    args = parser.parse_args()
    report = analyse(args.manifest, args.results, fixtures=args.fixtures,
                     decision_cases=args.decision_cases,
                     review_releases=args.review_release, review_mappings=args.review_map)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": report["status"], "coverage": report["coverage"],
                      "time_contrast_status": report["time_contrast"]["status"]}, sort_keys=True))


if __name__ == "__main__":
    main()
