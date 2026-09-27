"""Check a live B pair's common start and retain its unaltered measurements."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re


def read(path: Path) -> dict:
    result = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(result, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return result


def claude_execution(path: Path) -> dict:
    data = path.read_bytes()
    events = json.loads(data)
    if not isinstance(events, list):
        raise ValueError(f"Expected Claude Code execution event array: {path}")
    initial = next((event for event in events if isinstance(event, dict)
                    and event.get("type") == "system" and event.get("subtype") == "init"), None)
    result = next((event for event in reversed(events) if isinstance(event, dict)
                   and event.get("type") == "result"), None)
    if (initial is None or not initial.get("model") or result is None
            or result.get("subtype") != "success" or result.get("is_error")):
        raise ValueError(f"Claude Code run lacks a successful initialisation and result: {path}")
    return {"execution_sha256": hashlib.sha256(data).hexdigest(),
            "initial_model": initial.get("model"),
            "turns": result.get("num_turns")}


def compare(directory: Path, preflight_directory: Path, a_artifact: Path,
            block: dict, codex_version: str) -> dict:
    if set(block) != {"id", "a_class", "b_class", "a_model", "b_model", "a_effort", "b_effort"}:
        raise ValueError("Model block has unexpected keys")
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,40}", block["id"]):
        raise ValueError("Model block ID is not a safe artifact component")
    if (block["a_class"] not in {"codex_action", "claude_code"}
            or block["b_class"] not in {"codex_action", "claude_code"}):
        raise ValueError("Unrecognised executable agent class")
    arms = {name: directory / f"architecture-b-{block['id']}-{name}"
            for name in ("control", "treatment")}
    records = {name: read(path / "preparation.json") for name, path in arms.items()}
    starts = {name: item["source"]["tree_sha256"] for name, item in records.items()}
    if len(set(starts.values())) != 1 or records["control"]["source"] != records["treatment"]["source"]:
        raise ValueError("B arms did not start from the same byte-identified A source")
    a_source = read(a_artifact / "manifest.json")
    if a_source != records["control"]["source"]:
        raise ValueError("B common start does not equal the retained A source")
    if records["control"]["guidance_sha256"] != records["treatment"]["guidance_sha256"]:
        raise ValueError("B arms had different common session guidance")
    if records["control"]["packet_sha256"] is not None or not records["treatment"]["packet_sha256"]:
        raise ValueError("EAL packet exposure differs from the planned B assignment")
    mcp = {name: read(preflight_directory /
                      f"architecture-b-preflight-{block['id']}-{name}" / "pre-b-mcp.json")
           for name in arms}
    if (any(item["status"] != "ok" for item in mcp.values())
            or mcp["control"]["source_sha256"] != mcp["treatment"]["source_sha256"]
            or mcp["control"]["context"] != mcp["treatment"]["context"]):
        raise ValueError("B host MCP acquisitions were unsuccessful or unequal in source/scope")
    if records["treatment"]["packet_sha256"] != mcp["treatment"]["packet_sha256"]:
        raise ValueError("Treatment packet does not match the MCP acquisition")
    results = {name: read(path / "assessment.json") for name, path in arms.items()}
    cognitive = {name: read(path / "cognitive-complexity.json") for name, path in arms.items()}
    if any(item.get("schema") != "python-cognitive-complexity/1" for item in cognitive.values()):
        raise ValueError("A cognitive-complexity observation is missing or invalid")
    final_source = {name: read(path / "manifest.json") for name, path in arms.items()}
    claude_runs = {}
    if block["a_class"] == "claude_code":
        claude_runs["a"] = claude_execution(a_artifact / "agent-execution.json")
    if block["b_class"] == "claude_code":
        claude_runs["b"] = {name: claude_execution(path / "agent-execution.json")
                            for name, path in arms.items()}
        models = {record["initial_model"] for record in claude_runs["b"].values()}
        if len(models) != 1:
            raise ValueError("B arms initialised different or unreported Claude models")
    return {
        "schema": "architecture-extension-live-pair/1",
        "run_id": os.environ.get("GITHUB_RUN_ID"),
        "run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT"),
        "commit": os.environ.get("GITHUB_SHA"),
        "assembled_at": datetime.now(timezone.utc).isoformat(),
        "agent_runners": {
            stage: ({"codex_action":
                     "openai/codex-action@86365089eb2b84e0a8fb0717b304f8bdcb13b20e",
                     "claude_code":
                     "anthropics/claude-code-action/base-action@756cc22e19660d20e8cc9496b4f242475a7f7790"}
                    [block[f"{stage}_class"]])
            for stage in ("a", "b")
        },
        "codex_cli_version_requested_if_used": codex_version,
        "claude_code_version_if_used": "2.1.283",
        "model_block_requested": block,
        "claude_execution_observed": claude_runs,
        "b_start_sha256": starts["control"],
        "a_assessment": read(a_artifact / "assessment.json"),
        "a_cognitive_complexity": read(a_artifact / "cognitive-complexity.json"),
        "common_guidance_sha256": records["control"]["guidance_sha256"],
        "exposure": {name: {"eal_context_delivered": name == "treatment",
                            "packet_sha256": records[name]["packet_sha256"],
                            "pre_b_mcp_source_sha256": mcp[name]["source_sha256"],
                            "pre_b_mcp_status": mcp[name]["status"]}
                     for name in arms},
        "b_final_source_sha256": {name: item["tree_sha256"] for name, item in final_source.items()},
        "assessments": results,
        "cognitive_complexity": cognitive,
        "interpretation": "One unrandomised pair; this is a within-A-snapshot descriptive contrast. "
                          "Engineer 2's EAL exposure is common to both B arms. Requested models and efforts "
                          "are requested inputs; the Claude initialisation and full retained agent logs "
                          "should be inspected for effective runtime details. A and B may use different "
                          "agent classes, but both B conditions in one block share a class and model. "
                          "Concurrent B jobs have no randomised launch order. "
                          "Later debt is unmeasured.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--preflight-directory", type=Path, required=True)
    parser.add_argument("--a-artifact", type=Path, required=True)
    parser.add_argument("--block", required=True, help="Exact JSON object used in the workflow matrix")
    parser.add_argument("--codex-version", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = compare(args.directory, args.preflight_directory, args.a_artifact,
                     json.loads(args.block), args.codex_version)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True,
                                      ensure_ascii=False, allow_nan=False) + "\n",
                           encoding="utf-8")
    print(f"Verified common B start {result['b_start_sha256']} and both observations")


if __name__ == "__main__":
    main()
