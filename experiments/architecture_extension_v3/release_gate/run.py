"""Run paired plain and EAL/MCP decisions over frozen synthetic cases.

The saved result is apparatus validation. It is not a coding-agent trial or
an estimate of technical debt. The collection may contain acquisition errors;
the decision defaults to BLOCK_COMPLETION and records them explicitly.
"""

from __future__ import annotations

import argparse
import asyncio
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import time
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from experiments.architecture_extension_v3.release_gate.tool import CASE_IDS, plain_decision


SOURCE = HERE / "argument.eal"
REGISTRY = HERE / "eal-tools.toml"
OUTCOME = HERE / "results.json"


async def eal_decision(case: str) -> dict[str, Any]:
    source = SOURCE.read_text(encoding="utf-8")
    env = dict(os.environ)
    env["PYTHONPATH"] = str(ROOT / "src") + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    start = time.perf_counter()
    with tempfile.TemporaryDirectory(prefix="release-gate-mcp-") as temporary:
        server = StdioServerParameters(command=sys.executable,
                                       args=["-m", "eal.server", "--workspace", str(ROOT),
                                             "--registry", str(REGISTRY), "--database",
                                             str(Path(temporary) / "assess.sqlite3")], env=env)
        async with stdio_client(server) as (read, write):
            async with ClientSession(read, write) as client:
                await client.initialize()
                names = {item.name for item in (await client.list_tools()).tools}
                required = {"eal_validate", "eal_collect", "eal_reason", "eal_compile_aspic"}
                if not required <= names:
                    raise RuntimeError(f"MCP lacks tools: {sorted(required - names)}")

                async def call(name: str, args: dict[str, Any]) -> dict[str, Any]:
                    result = await client.call_tool(name, arguments=args)
                    if result.isError or not isinstance(result.structuredContent, dict):
                        raise RuntimeError(f"MCP {name} failed: {result.content}")
                    return result.structuredContent

                validation = await call("eal_validate", {"source": source})
                if validation.get("valid") is not True:
                    raise RuntimeError(f"EAL source invalid: {validation.get('diagnostics')}")
                context = {"experiment": "architecture-extension-v3-release-gate", "case_id": case}
                collection = await call("eal_collect", {"source": source, "context": context})
                now = datetime.now(timezone.utc).isoformat()
                assessment = await call("eal_reason", {"source": source, "context": context,
                                                       "collection_id": collection["collection_id"],
                                                       "now": now})
                claims = assessment["claims"]
                safe = claims["completion_safe"]
                retry = claims["same_key_retry_allowed"]
                if safe["status"] == "supported" and safe["grounded_label"] == "accepted":
                    action = "COMPLETE"
                elif retry["status"] == "supported" and retry["grounded_label"] == "accepted":
                    action = "RETRY_SAME_KEY"
                else:
                    action = "BLOCK_COMPLETION"
                formal = await call("eal_compile_aspic", {"source": source, "context": context,
                                                            "collection_id": collection["collection_id"],
                                                            "goal": "candidate_completion", "now": now})
                records = collection["records"]
                return {"action": action, "claim_status": {key: {
                    "status": claims[key]["status"], "grounded_label": claims[key]["grounded_label"]}
                    for key in ("candidate_completion", "completion_safe", "same_key_retry_allowed",
                                "completion_blocked")},
                    "candidate_aspic_status": formal["formal"]["grounded_status"],
                    "aspic_defeats": formal["formal"]["defeats"],
                    "evidence_status": {key: value["status"] for key, value in
                                        assessment["evidence"].items()},
                    "collection_errors": sorted(key for key, value in records.items()
                                                if value["status"] != "ok"),
                    "collection_id": collection["collection_id"],
                    "assessment_id": assessment["assessment_id"],
                    "mcp_elapsed_seconds": time.perf_counter() - start}


async def run() -> dict[str, Any]:
    cases = []
    for case in CASE_IDS:
        plain_start = time.perf_counter()
        plain = plain_decision(case)
        plain_elapsed = time.perf_counter() - plain_start
        eal = await eal_decision(case)
        cases.append({"case_id": case, "basis": "synthetic", "plain_action": plain["action"],
                      "eal_action": eal["action"], "agreement": plain["action"] == eal["action"],
                      "plain_reason": plain["reason"], "plain_elapsed_seconds": plain_elapsed,
                      "plain_packet_bytes": len(json.dumps(plain, sort_keys=True).encode()),
                      **eal})
    return {"schema": "refund-release-gate-apparatus/1", "scope": "synthetic finite decision table",
            "source_sha256": hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
            "registry_sha256": hashlib.sha256(REGISTRY.read_bytes()).hexdigest(),
            "cases": cases, "all_agree": all(case["agreement"] for case in cases),
            "interpretation": ("Observed actions are agreement of two implemented rules on simulated inputs. "
                               "No AI coding, live payment, cost saving, or future debt effect is observed.")}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUTCOME,
                        help="write replay outside the frozen source tree in CI")
    args = parser.parse_args()
    report = asyncio.run(run())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, sort_keys=True, indent=2, allow_nan=False) + "\n",
                           encoding="utf-8")
    print(json.dumps({"cases": len(report["cases"]), "all_agree": report["all_agree"],
                      "actions": {item["case_id"]: item["eal_action"] for item in report["cases"]}},
                     sort_keys=True))
    if not report["all_agree"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
