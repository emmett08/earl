"""Bind downloaded workflow artifacts into the frozen 18-episode study ledger.

This does not perform the masked architecture review. An incomplete or
inconsistent acquisition emits a partial record and cannot enter analysis.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import sys
from typing import Any


STUDY = Path(__file__).resolve().parent
V3 = STUDY.parent
REPO = STUDY.parents[2]
sys.path.insert(0, str(V3))
from snapshot_probe import digest_file, tree_manifest  # noqa: E402


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def _time(path: Path) -> float:
    value = float(path.read_text(encoding="utf-8").strip())
    if not math.isfinite(value) or value < 0:
        raise ValueError(f"invalid timestamp: {path}")
    return value


def _packet_state(stage: str, block: str, clone: str, arm: str,
                  hosts: Path, preflight: Path) -> Path | None:
    if arm == "P0":
        return None
    if stage == "B":
        return preflight / f"host-pre-B-{block}-{clone}" / "state"
    previous = "B" if stage == "C" else "C"
    return hosts / f"host-{previous}-{block}-{clone}" / "next-state"


def episode(stage: str, family: str, clone: str, arm: str, block: str,
            episodes: Path, hosts: Path, preflight: Path,
            dispatch: dict[str, Any]) -> dict[str, Any]:
    prefix = f"{block}-{clone}"
    attempt = episodes / f"episode-{stage}-{prefix}"
    host = hosts / f"host-{stage}-{prefix}"
    exposure = read_json(attempt / "exposure.json")
    invocation = read_json(attempt / "invocation.json")
    assessment = read_json(host / "assessment.json")
    source = host / "source"
    manifest = read_json(host / "code-manifest.json")
    verification = read_json(host / "exposure-verification.json")
    if (exposure.get("schema"), exposure.get("arm"), exposure.get("family"),
            exposure.get("feature")) != ("architecture-v3-exposure/1", arm, family, stage):
        raise ValueError("exposure identity differs from assignment")
    if (invocation.get("schema"), invocation.get("family"), invocation.get("clone"),
            invocation.get("arm"), invocation.get("stage")) != (
            "architecture-v3-agent-invocation/1", family, clone, arm, stage):
        raise ValueError("invocation identity differs from assignment")
    block_profile = dispatch["block"]
    selected = stage.lower()
    expected = (block_profile[f"{selected}_class"], block_profile[f"{selected}_model"],
                block_profile[f"{selected}_effort"])
    if tuple(invocation.get(key) for key in ("agent_class", "requested_model", "requested_effort")) != expected:
        raise ValueError("model, agent class or effort differs from predeclared block")
    if any(invocation.get(key) != dispatch[key] for key in ("source_commit", "run_id", "run_attempt")):
        raise ValueError("invocation source or workflow run differs from dispatch")
    version = dispatch["codex_version" if invocation["agent_class"] == "codex_cli"
                       else "claude_version"]
    if version not in str(invocation.get("cli_version", "")):
        raise ValueError("installed agent CLI version differs from predeclared version")
    if (host / "exposure-exit.txt").read_text().strip() != "0" or not verification.get("sidecars_intact"):
        raise ValueError("agent-visible sidecars were not verified after coding")
    trial = attempt / "trial"
    brief = STUDY / "features" / f"{family}-{stage}.md"
    if (digest_file(trial / "FEATURE.md") != exposure.get("brief_sha256")
            or digest_file(brief) != exposure.get("brief_sha256")):
        raise ValueError("current brief digest differs from frozen brief or delivered exposure")
    if verification.get("initial_visible_tree_sha256") != exposure.get("visible_tree_sha256"):
        raise ValueError("exposure verification has a different initial tree")
    state = _packet_state(stage, block, clone, arm, hosts, preflight)
    packet = exposure.get("packet_sha256")
    host_metrics = None
    if state is None:
        if packet is not None or (trial / "architecture-context.json").exists():
            raise ValueError("P0 received an unassigned packet")
    else:
        retained = state / f"packet-{arm}.json"
        metrics = read_json(state / "metrics.json")
        host_metrics = metrics
        digest = digest_file(retained)
        if (packet != digest or digest_file(trial / "architecture-context.json") != digest
                or metrics.get("packet_sha256") != digest
                or read_json(retained).get("candidate_sha256") != exposure.get("source_tree_sha256")):
            raise ValueError("delivered packet differs from host result or input source")
    source_tree = tree_manifest(source)["tree_sha256"]
    if manifest.get("tree_sha256") != source_tree:
        raise ValueError("retained source snapshot differs from its code manifest")
    from assess import source_digest
    if assessment.get("source_sha256") != source_digest(source):
        raise ValueError("independent assessor was not bound to the retained source")
    started = _time(attempt / "agent-start.txt")
    ended = _time(attempt / "agent-end.txt")
    elapsed = ended - started
    if elapsed < 0 or elapsed > 1830 or invocation.get("wall_cap_seconds") != 1800:
        raise ValueError("episode wall cap is not attested by timestamps and timeout configuration")
    if invocation.get("started_unix_seconds") != started or invocation.get("ended_unix_seconds") != ended:
        raise ValueError("invocation timestamps differ from retained runner files")
    if invocation.get("exit_code") != int((attempt / "agent-exit.txt").read_text().strip()):
        raise ValueError("invocation exit code differs from retained runner file")
    if invocation.get("exact_credential_redacted"):
        raise ValueError("provider credential appeared in agent-visible output; this episode needs review")
    usage = read_json(host / "ledger.json")
    if usage.get("schema") != "architecture-v3-workflow-ledger/1":
        raise ValueError("provider trace ledger missing")
    trace = (attempt / "agent.jsonl").read_bytes()
    trace_sha = hashlib.sha256(trace).hexdigest() if trace else None
    if (usage.get("invocation") != invocation
            or usage.get("trace_sha256") != trace_sha):
        raise ValueError("provider usage ledger differs from retained invocation or trace")
    return {"family": family, "arm": arm, "stage": stage, "clone_id": clone,
            "source_sha256": assessment["source_sha256"],
            "input_tree_sha256": exposure["source_tree_sha256"],
            "output_tree_sha256": source_tree,
            "candidate_snapshot_path": str(source.resolve()),
            "model_id": invocation["requested_model"],
            "model_revision": "unknown",
            "agent_class": invocation["agent_class"],
            "packet_sha256": packet,
            "host_assessment_seconds": (host_metrics["wall_seconds"] if host_metrics else 0.0),
            "host_assessment_cpu_seconds": ((host_metrics["host_cpu_seconds"] +
                                             host_metrics["child_cpu_seconds"])
                                            if host_metrics else 0.0),
            "mcp_elapsed_seconds": (host_metrics["mcp_elapsed_seconds"] if host_metrics else None),
            "packet_bytes": (host_metrics["packet_bytes"] if host_metrics else 0),
            "tool_exchange_bytes": (host_metrics.get("tool_exchange_bytes") if host_metrics else 0),
            "assessor": assessment,
            "coding_elapsed_seconds": elapsed,
            "wall_cap_enforced": True,
            "token_usage": usage.get("usage"),
            "cost_gbp": None,
            "artifact_names": {"episode": f"episode-{stage}-{prefix}",
                               "host": f"host-{stage}-{prefix}",
                               "packet_host": (None if state is None else
                                               f"host-pre-B-{prefix}" if stage == "B" else
                                               f"host-{'B' if stage == 'C' else 'C'}-{prefix}")},
            "source_commit": invocation.get("source_commit"),
            "runner": {key: invocation.get(key) for key in
                       ("runner_os", "runner_arch", "cli_version", "binary_sha256",
                        "run_id", "run_attempt", "exit_code")},
            "trace_sha256": usage.get("trace_sha256"),
            "exposure_visible_tree_sha256": exposure["visible_tree_sha256"],
            "brief_sha256": exposure["brief_sha256"]}


def assemble(episodes: Path, hosts: Path, preflight: Path, block: str,
             dispatch: dict[str, Any]) -> dict[str, Any]:
    if dispatch.get("schema") != "architecture-v3-dispatch-block/1" or dispatch.get("block", {}).get("id") != block:
        raise ValueError("dispatch block is absent or differs from requested block")
    allocation = read_json(STUDY / "allocation.json")["family_clone_assignment"]
    rows: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    for family in ("R", "W"):
        for clone, arm in sorted(allocation[family].items()):
            for stage in ("B", "C", "D"):
                try:
                    rows.append(episode(stage, family, clone, arm, block,
                                        episodes, hosts, preflight, dispatch))
                except (OSError, ValueError, KeyError, json.JSONDecodeError) as error:
                    errors.append({"family": family, "clone": clone, "arm": arm,
                                   "stage": stage, "error": f"{type(error).__name__}: {error}"})
    return {"schema_version": "architecture-extension-v3/ledger/1",
            "status": "complete_acquisition" if len(rows) == 18 and not errors else "partial_acquisition",
            "block_id": block, "runs": rows, "missing_or_invalid": errors,
            "masked_review": {"R": "unresolved", "W": "unresolved"},
            "review_status": "not_adjudicated"}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--episodes", type=Path, required=True)
    parser.add_argument("--hosts", type=Path, required=True)
    parser.add_argument("--preflight", type=Path, required=True)
    parser.add_argument("--block-id", required=True)
    parser.add_argument("--block-manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = assemble(args.episodes, args.hosts, args.preflight, args.block_id,
                      read_json(args.block_manifest))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], "episodes": len(result["runs"]),
                      "invalid": len(result["missing_or_invalid"])}))
    if result["status"] != "complete_acquisition":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
