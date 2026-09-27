"""Validate a completed pilot ledger and calculate bounded local contrasts.

Input schema is documented in README.md. This program never treats a missing
run, unlogged cap, invalid assessor or unmasked review as success. It creates
no p-value from the two deliberately selected task families.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import subprocess
import sys
from typing import Any

from assess import cases_for, source_digest
import freeze

V3 = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(V3))
from snapshot_probe import tree_manifest  # noqa: E402


FAMILIES = ("R", "W")
ARMS = ("P0", "P1", "P2")
STAGES = ("B", "C", "D")
CAP_SECONDS = 30 * 60


def _nonnegative_number(value: Any, name: str, key: tuple[str, str, str],
                        *, optional: bool = False) -> float | None:
    if optional and value is None:
        return None
    if (not isinstance(value, (int, float)) or isinstance(value, bool)
            or not math.isfinite(value) or value < 0):
        raise ValueError(f"invalid {name} for {key}")
    return float(value)


def _nonnegative_integer(value: Any, name: str, key: tuple[str, str, str]) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ValueError(f"invalid {name} for {key}")
    return value


def _record(raw: dict[str, Any], key: tuple[str, str, str]) -> dict[str, Any]:
    family, arm, stage = key
    if (raw.get("family"), raw.get("arm"), raw.get("stage")) != key:
        raise ValueError(f"mismatched assignment record for {key}")
    if not isinstance(raw.get("source_sha256"), str) or len(raw["source_sha256"]) != 64:
        raise ValueError(f"missing source digest for {key}")
    for field in ("input_tree_sha256", "output_tree_sha256"):
        if not isinstance(raw.get(field), str) or len(raw[field]) != 64:
            raise ValueError(f"missing {field} for {key}")
    if not isinstance(raw.get("clone_id"), str):
        raise ValueError(f"missing masked clone ID for {key}")
    snapshot = Path(raw.get("candidate_snapshot_path", "")).resolve()
    if not snapshot.is_dir():
        raise ValueError(f"missing immutable candidate snapshot for {key}")
    if source_digest(snapshot) != raw["source_sha256"]:
        raise ValueError(f"assessor source subset differs from retained snapshot for {key}")
    if tree_manifest(snapshot)["tree_sha256"] != raw["output_tree_sha256"]:
        raise ValueError(f"host whole-tree digest differs from retained snapshot for {key}")
    if not isinstance(raw.get("model_id"), str) or not isinstance(raw.get("agent_class"), str):
        raise ValueError(f"missing model or agent class for {key}")
    if arm == "P0" and raw.get("packet_sha256") is not None:
        raise ValueError(f"unassigned P0 packet for {key}")
    if arm != "P0" and (not isinstance(raw.get("packet_sha256"), str)
                        or len(raw["packet_sha256"]) != 64):
        raise ValueError(f"missing assigned packet for {key}")
    acquisition = _nonnegative_number(raw.get("host_assessment_seconds"),
                                      "host acquisition wall time", key)
    cpu = _nonnegative_number(raw.get("host_assessment_cpu_seconds"),
                              "host acquisition CPU time", key, optional=True)
    mcp = _nonnegative_number(raw.get("mcp_elapsed_seconds"),
                              "MCP elapsed time", key, optional=True)
    packet_bytes = _nonnegative_integer(raw.get("packet_bytes", 0), "packet bytes", key)
    exchange_bytes = _nonnegative_integer(raw.get("tool_exchange_bytes", 0),
                                          "tool exchange bytes", key)
    if arm == "P0" and (acquisition != 0 or cpu not in (None, 0) or mcp is not None
                        or packet_bytes or exchange_bytes):
        raise ValueError(f"P0 has unexpected context acquisition for {key}")
    if arm == "P1" and mcp is not None:
        raise ValueError(f"direct collector arm has an unexpected MCP duration for {key}")
    assessor = raw.get("assessor")
    if not isinstance(assessor, dict) or assessor.get("source_sha256") != raw["source_sha256"]:
        raise ValueError(f"assessor/source mismatch for {key}")
    if assessor.get("schema_version") != "architecture-extension-v3/assessor/1":
        raise ValueError(f"assessor schema mismatch for {key}")
    if assessor.get("family") != family or assessor.get("stage") != stage:
        raise ValueError(f"assessor stage mismatch for {key}")
    replay = subprocess.run(
        [sys.executable, str(Path(__file__).resolve().parent / "assess.py"),
         "--candidate", str(snapshot), "--family", family, "--stage", stage],
        text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        timeout=180, check=False,
    )
    if replay.returncode:
        raise ValueError(f"independent assessor replay failed for {key}: {replay.stderr[-240:]}")
    reproduced = json.loads(replay.stdout)
    if reproduced != assessor:
        raise ValueError(f"retained assessor record differs from replay for {key}")
    findings = assessor.get("findings")
    if not isinstance(findings, dict) or set(findings) != set(cases_for(family, stage)):
        raise ValueError(f"missing independent findings for {key}")
    statuses = [x.get("status") for x in findings.values() if isinstance(x, dict)]
    if len(statuses) != len(findings) or any(x not in ("pass", "fail", "invalid") for x in statuses):
        raise ValueError(f"invalid independent findings for {key}")
    if (assessor.get("passed"), assessor.get("failed"), assessor.get("invalid")) != (
            statuses.count("pass"), statuses.count("fail"), statuses.count("invalid")):
        raise ValueError(f"assessor counts disagree with case statuses for {key}")
    elapsed = _nonnegative_number(raw.get("coding_elapsed_seconds"),
                                  "coding elapsed time", key)
    if elapsed > CAP_SECONDS + 30:
        raise ValueError(f"coding wall cap exceeded by more than clock tolerance for {key}")
    if raw.get("wall_cap_enforced") is not True:
        raise ValueError(f"episode-level wall cap not attested for {key}")
    complete = all(x == "pass" for x in statuses)
    return {
        "source_sha256": raw["source_sha256"],
        "clone_id": raw["clone_id"],
        "input_tree_sha256": raw["input_tree_sha256"],
        "output_tree_sha256": raw["output_tree_sha256"],
        "model_id": raw["model_id"],
        "model_revision": raw.get("model_revision"),
        "agent_class": raw["agent_class"],
        "packet_sha256": raw.get("packet_sha256"),
        "complete": complete,
        "passed": statuses.count("pass"), "failed": statuses.count("fail"),
        "invalid": statuses.count("invalid"),
        "actual_elapsed_seconds": elapsed,
        "restricted_elapsed_seconds": min(elapsed, CAP_SECONDS) if complete else CAP_SECONDS,
        "host_assessment_seconds": acquisition,
        "host_assessment_cpu_seconds": cpu,
        "mcp_elapsed_seconds": mcp,
        "packet_bytes": packet_bytes,
        "tool_exchange_bytes": exchange_bytes,
        "cost_gbp": raw.get("cost_gbp"),
        "token_usage": raw.get("token_usage"),
    }


def validate_family_lineage(
    family: str, keyed: dict[tuple[str, str, str], dict[str, Any]],
    assigned: dict[str, str], expected_a: str,
) -> None:
    b_inputs = {keyed[(family, arm, "B")]["input_tree_sha256"] for arm in ARMS}
    if b_inputs != {expected_a}:
        raise ValueError(f"family {family} B source differs from the frozen A anchor")
    for stage in STAGES:
        configurations = {(keyed[(family, arm, stage)]["model_id"],
                           keyed[(family, arm, stage)]["model_revision"],
                           keyed[(family, arm, stage)]["agent_class"])
                          for arm in ARMS}
        if len(configurations) != 1:
            raise ValueError(f"family {family} {stage} model/agent block is not matched")
    for arm in ARMS:
        for stage in STAGES:
            row = keyed[(family, arm, stage)]
            if assigned.get(row["clone_id"]) != arm:
                raise ValueError(f"family {family} clone allocation differs from frozen assignment")
            if stage != "B":
                prior = "B" if stage == "C" else "C"
                if row["input_tree_sha256"] != keyed[(family, arm, prior)]["output_tree_sha256"]:
                    raise ValueError(f"family {family} {arm} {stage} does not inherit its prior output")


def analyse(ledger: dict[str, Any]) -> dict[str, Any]:
    if ledger.get("schema_version") != "architecture-extension-v3/ledger/1":
        raise ValueError("ledger schema mismatch")
    if ledger.get("status") != "complete_acquisition" or ledger.get("missing_or_invalid"):
        raise ValueError("artifact acquisition incomplete or unverified")
    if not freeze.MANIFEST.is_file():
        raise ValueError("pre-run freeze manifest absent")
    frozen = json.loads(freeze.MANIFEST.read_text())
    current_files, current_tree = freeze.inventory()
    if frozen.get("files") != current_files or frozen.get("tree_sha256") != current_tree:
        raise ValueError("coding/scoring input changed after pre-run freeze")
    runs = ledger.get("runs")
    if not isinstance(runs, list) or len(runs) != 18:
        raise ValueError("exactly 18 assigned episodes are required, including failures")
    keyed: dict[tuple[str, str, str], dict[str, Any]] = {}
    for run in runs:
        if not isinstance(run, dict):
            raise ValueError("run is not an object")
        key = (run.get("family"), run.get("arm"), run.get("stage"))
        if key in keyed or key not in {(f, a, s) for f in FAMILIES for a in ARMS for s in STAGES}:
            raise ValueError(f"duplicate or unexpected assignment {key}")
        keyed[key] = _record(run, key)
    schedule = json.loads((Path(__file__).resolve().parent / "allocation.json").read_text())
    if schedule != freeze.allocation(schedule["seed_hex"]):
        raise ValueError("frozen allocation differs from seed and algorithm")
    assigned = schedule["family_clone_assignment"]
    for family in FAMILIES:
        validate_family_lineage(family, keyed, assigned[family],
                                tree_manifest(freeze.BASE)["tree_sha256"])
    review = ledger.get("masked_review")
    if not isinstance(review, dict) or any(review.get(f) not in ("no_worse", "worse", "unresolved")
                                               for f in FAMILIES):
        raise ValueError("condition-masked review disposition missing")
    by_family: dict[str, Any] = {}
    for family in FAMILIES:
        followup_coding = {arm: sum(keyed[(family, arm, stage)]["restricted_elapsed_seconds"]
                                    for stage in ("C", "D")) for arm in ARMS}
        followup_host = {arm: sum(keyed[(family, arm, stage)]["host_assessment_seconds"]
                                  for stage in ("C", "D")) for arm in ARMS}
        followup = {arm: followup_coding[arm] + followup_host[arm] for arm in ARMS}
        lifecycle_coding = {arm: sum(keyed[(family, arm, stage)]["restricted_elapsed_seconds"]
                                     for stage in STAGES) for arm in ARMS}
        lifecycle_host = {arm: sum(keyed[(family, arm, stage)]["host_assessment_seconds"]
                                   for stage in STAGES) for arm in ARMS}
        lifecycle_cpu = {arm: (sum(keyed[(family, arm, stage)]["host_assessment_cpu_seconds"]
                                   or 0 for stage in STAGES)
                               if all(keyed[(family, arm, stage)]["host_assessment_cpu_seconds"]
                                      is not None for stage in STAGES) else None)
                         for arm in ARMS}
        lifecycle_mcp = {arm: (sum(keyed[(family, arm, stage)]["mcp_elapsed_seconds"]
                                   or 0 for stage in STAGES)
                               if arm == "P2" and all(
                                   keyed[(family, arm, stage)]["mcp_elapsed_seconds"] is not None
                                   for stage in STAGES) else None)
                         for arm in ARMS}
        lifecycle_packet_bytes = {arm: sum(keyed[(family, arm, stage)]["packet_bytes"]
                                           for stage in STAGES) for arm in ARMS}
        lifecycle_tool_bytes = {arm: sum(keyed[(family, arm, stage)]["tool_exchange_bytes"]
                                         for stage in STAGES) for arm in ARMS}
        all_pass = {arm: all(keyed[(family, arm, stage)]["complete"] for stage in STAGES)
                    for arm in ARMS}
        ratios = {arm: followup["P2"] / followup[arm] if followup[arm] > 0 else None
                  for arm in ("P0", "P1")}
        time_threshold = (all_pass["P2"] and
                          all(ratios[arm] is not None and ratios[arm] <= .75
                              for arm in ("P0", "P1")))
        threshold = None if review[family] == "unresolved" else (
            time_threshold and review[family] == "no_worse")
        by_family[family] = {"stages": {arm: {stage: keyed[(family, arm, stage)] for stage in STAGES}
                                      for arm in ARMS},
                             "restricted_followup_elapsed_seconds": followup,
                             "restricted_followup_coding_seconds": followup_coding,
                             "followup_host_assessment_seconds": followup_host,
                             "restricted_lifecycle_elapsed_seconds": {
                                 arm: lifecycle_coding[arm] + lifecycle_host[arm] for arm in ARMS},
                             "lifecycle_host_assessment_seconds": lifecycle_host,
                             "lifecycle_host_cpu_seconds": lifecycle_cpu,
                             "lifecycle_mcp_elapsed_seconds": lifecycle_mcp,
                             "lifecycle_packet_bytes": lifecycle_packet_bytes,
                             "lifecycle_tool_exchange_bytes": lifecycle_tool_bytes,
                             "p2_time_ratio": ratios,
                             "all_stages_complete": all_pass,
                             "time_threshold_met": time_threshold,
                             "masked_review": review[family],
                             "local_threshold_met": threshold}
    values = [by_family[f]["local_threshold_met"] for f in FAMILIES]
    return {"schema_version": "architecture-extension-v3/analysis/1",
            "scope": "two selected task families, one three-arm block each; descriptive local contrasts only",
            "threshold_met_in_both_families": None if None in values else all(values),
            "by_family": by_family,
            "population_effect_estimated": False,
            "technical_debt_measured": False}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("ledger", type=Path)
    args = parser.parse_args()
    print(json.dumps(analyse(json.loads(args.ledger.read_text())), sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
