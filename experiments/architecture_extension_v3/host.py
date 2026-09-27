"""Host-owned current-snapshot EAL/MCP assessment and paired agent packets.

`assess` emits one arm-specific packet: P1 calls the deterministic collector
directly, while P2 assesses the same declared checks through EAL MCP. The
model receives only its assigned packet. `explain` is a host/reviewer operation
on the retained recipient-only MCP session, not an agent-worktree tool.
"""

from __future__ import annotations

import argparse
import asyncio
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import resource
import shutil
import subprocess
import sys
import time
import tomllib
from typing import Any

from snapshot_probe import digest_file, tree_manifest, EXCLUDED, SIDECARS, CHECKS


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CLAIM = "current_candidate_reviewable"
ARTIFACT = "current"
MAX_PACKET_BYTES = 3072
MAX_CHANGED = 12
NOTICE = ("# Coding session\n\nRead FEATURE.md for the current requirement. "
          "Read architecture-context.json if present for the current-source assessment. "
          "Keep these host files unchanged.\n")


def json_bytes(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, ensure_ascii=False,
                       separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(json_bytes(value))


def _copy_source(source: Path, target: Path) -> dict[str, Any]:
    if any((source / name).exists() for name in SIDECARS):
        raise ValueError("source contains an agent-visible sidecar from another episode")
    allowed = {"ARCHITECTURE.md", "fulfilment", "tests"}
    if {item.name for item in source.iterdir()} - allowed - EXCLUDED:
        raise ValueError("source contains unexpected top-level files or directories")
    if any(item.name == "AGENTS.md" for item in source.rglob("AGENTS.md")):
        raise ValueError("source contains nested agent instructions")
    before = tree_manifest(source)
    shutil.copytree(source, target,
                    ignore=lambda _directory, names: [name for name in names if name in EXCLUDED])
    after = tree_manifest(target)
    if before != after or tree_manifest(source) != before:
        raise ValueError("source tree changed during host snapshot")
    return after


def _visible_manifest(root: Path) -> dict[str, Any]:
    visible = {}
    for item in sorted(root.rglob("*")):
        relative = item.relative_to(root)
        if any(part in EXCLUDED for part in relative.parts):
            continue
        if item.is_symlink():
            raise ValueError("agent-visible tree contains a symlink")
        if item.is_file():
            visible[relative.as_posix()] = digest_file(item)
    return {"schema": "architecture-v3-exposure/1", "files": visible,
            "visible_tree_sha256": hashlib.sha256(json_bytes(visible)).hexdigest()}


def prepare(args: argparse.Namespace) -> dict[str, Any]:
    if args.destination.exists() or args.record.exists():
        raise FileExistsError("trial destination and exposure record must be new")
    if args.arm in ("P1", "P2") and not args.packet:
        raise ValueError("P1 and P2 require their own agent context packet")
    if args.arm == "P0" and args.packet:
        raise ValueError("P0 must not receive a context packet")
    if not args.brief.is_file() or args.brief.is_symlink():
        raise ValueError("current feature brief is absent or a symlink")
    expected_brief = HERE / "study" / "features" / f"{args.family}-{args.feature}.md"
    if args.brief.resolve() != expected_brief.resolve():
        raise ValueError("selected brief differs from declared family and feature")
    source = _copy_source(args.source.resolve(), args.destination)
    (args.destination / "AGENTS.md").write_text(NOTICE, encoding="utf-8")
    (args.destination / "FEATURE.md").write_bytes(args.brief.read_bytes())
    if args.packet:
        content = args.packet.read_bytes()
        packet = json.loads(content)
        if packet.get("schema") != f"architecture-v3-{'plain' if args.arm == 'P1' else 'eal'}-packet/1":
            raise ValueError("wrong packet for assigned arm")
        if (packet.get("candidate_sha256") != source["tree_sha256"]
                or (packet.get("family"), packet.get("feature")) != (args.family, args.feature)):
            raise ValueError("packet source digest differs from prepared code")
        (args.destination / "architecture-context.json").write_bytes(content)
    record = {**_visible_manifest(args.destination), "arm": args.arm,
              "family": args.family, "feature": args.feature,
              "source_tree_sha256": source["tree_sha256"],
              "brief_sha256": digest_file(args.destination / "FEATURE.md"),
              "packet_sha256": (digest_file(args.destination / "architecture-context.json")
                                if args.packet else None)}
    write_json(args.record, record)
    return record


def verify_exposure(args: argparse.Namespace) -> dict[str, Any]:
    record = json.loads(args.record.read_text(encoding="utf-8"))
    current = _visible_manifest(args.trial)
    for name in ("AGENTS.md", "FEATURE.md", "architecture-context.json"):
        if current["files"].get(name) != record["files"].get(name):
            raise ValueError(f"agent-visible sidecar changed: {name}")
    if current["files"].get("FEATURE.md") != record["brief_sha256"]:
        raise ValueError("feature brief digest differs from recorded exposure")
    if record["arm"] == "P0" and "architecture-context.json" in current["files"]:
        raise ValueError("unassigned context packet appeared in P0")
    return {"schema": "architecture-v3-exposure-verification/1", "arm": record["arm"],
            "initial_visible_tree_sha256": record["visible_tree_sha256"],
            "final_visible_tree_sha256": current["visible_tree_sha256"],
            "source_tree_sha256": tree_manifest(args.trial)["tree_sha256"],
            "sidecars_intact": True}


def snapshot(args: argparse.Namespace) -> dict[str, Any]:
    """Carry only verified code to the next episode, never prior context."""
    checked = verify_exposure(argparse.Namespace(trial=args.trial, record=args.record))
    if args.destination.exists() or args.manifest.exists():
        raise FileExistsError("source snapshot or manifest already exists")
    allowed = {"ARCHITECTURE.md", "fulfilment", "tests", *SIDECARS}
    if {item.name for item in args.trial.iterdir()} - allowed - EXCLUDED:
        raise ValueError("trial contains unexpected top-level content")
    shutil.copytree(args.trial, args.destination,
                    ignore=lambda _directory, names: [name for name in names
                                                       if name in EXCLUDED or name in SIDECARS])
    manifest = tree_manifest(args.destination)
    if manifest["tree_sha256"] != checked["source_tree_sha256"]:
        raise ValueError("source-only copy changed while taking snapshot")
    write_json(args.manifest, manifest)
    return {"schema": "architecture-v3-clean-snapshot/1",
            "source_tree_sha256": manifest["tree_sha256"],
            "initial_visible_tree_sha256": checked["initial_visible_tree_sha256"],
            "final_visible_tree_sha256": checked["final_visible_tree_sha256"]}


def _initialise(args: argparse.Namespace) -> dict[str, Any]:
    state = args.state_dir.resolve()
    if state.exists():
        raise FileExistsError("state directory must be new for one immutable candidate")
    state.mkdir(parents=True)
    workspace = state / "workspace"
    workspace.mkdir()
    candidate = _copy_source(args.candidate.resolve(), workspace / "candidate")
    baseline = _copy_source(args.baseline.resolve(), workspace / "baseline")
    shutil.copy2(HERE / "snapshot_probe.py", workspace / "snapshot_probe.py")
    context = {"experiment": "architecture-extension-v3", "stage": "current-snapshot",
               "family": args.family, "feature": args.feature,
               "candidate_sha256": candidate["tree_sha256"],
               "baseline_sha256": baseline["tree_sha256"]}
    source_sha = registry_sha = fingerprint = None
    if args.arm == "P2":
        from eal.runtime import load_method_registry

        for name in ("argument.eal", "tool.toml"):
            shutil.copy2(HERE / name, workspace / name)
        # The checked-in registry pins the collector bytes. A change to the
        # code without a reviewed TOML update fails before MCP collection.
        source_sha = digest_file(workspace / "argument.eal")
        registry_sha = digest_file(workspace / "tool.toml")
        registry = tomllib.loads((workspace / "tool.toml").read_text(encoding="utf-8"))
        pinned = registry["tools"]["snapshot_probe"]["pinned_files"]
        if len(pinned) != 1 or pinned[0] != {"path": "snapshot_probe.py",
                                                   "sha256": digest_file(workspace / "snapshot_probe.py")}:
            raise ValueError("collector does not match the reviewed TOML binding")
        fingerprint = load_method_registry(None).fingerprint
        fields = ", ".join(f"{key} = {json.dumps(value)}" for key, value in context.items())
        (state / "artifacts.toml").write_text(
            "[artifacts.current]\npath = \"argument.eal\"\n"
            f"sha256 = \"{source_sha}\"\n"
            f"method_registry_fingerprint = \"{fingerprint}\"\n"
            f"claims = [\"{CLAIM}\"]\ncontext = {{{fields}}}\n", encoding="utf-8")
    info = {"schema": "architecture-v3-host-binding/1", "context": context,
            "candidate_manifest": candidate, "baseline_manifest": baseline,
            "eal_sha256": source_sha, "registry_sha256": registry_sha,
            "collector_sha256": digest_file(workspace / "snapshot_probe.py"),
            "method_registry_fingerprint": fingerprint,
            "state_dir": str(state)}
    write_json(state / "binding.json", info)
    return info


def _server_args(state: Path, cache: bool) -> tuple[list[str], dict[str, str]]:
    workspace = state / "workspace"
    environment = dict(os.environ)
    environment["PYTHONPATH"] = str(ROOT / "src") + (
        os.pathsep + environment["PYTHONPATH"] if environment.get("PYTHONPATH") else "")
    environment["EAL_V3_CACHE"] = "1" if cache else "0"
    return ([sys.executable, "-m", "eal.server", "--workspace", str(workspace),
              "--registry", str(workspace / "tool.toml"),
              "--database", str(state / "eal.sqlite3"),
              "--artifacts", str(state / "artifacts.toml"),
              "--recipient-only", "--recipient-principal", "architecture_v3_host",
              "--recipient-grant", f"{ARTIFACT}:{CLAIM}"], environment)


class WireClient:
    """Bounded sequential JSON-RPC client retaining each exact stdio line."""

    def __init__(self, process: asyncio.subprocess.Process, timeout: float = 150):
        self.process = process
        self.timeout = timeout
        self.identifier = 0
        self.messages: list[dict[str, Any]] = []

    def _record(self, direction: str, line: bytes) -> None:
        if not line.endswith(b"\n") or len(line) > 8 * 1024 * 1024:
            raise ValueError("MCP line lacks newline or exceeds 8 MiB")
        self.messages.append({"direction": direction, "utf8_line": line.decode("utf-8"),
                              "sha256": hashlib.sha256(line).hexdigest()})

    async def send(self, message: dict[str, Any]) -> None:
        if self.process.stdin is None:
            raise RuntimeError("MCP stdin absent")
        line = json_bytes(message)
        self._record("client_to_server", line)
        self.process.stdin.write(line)
        await asyncio.wait_for(self.process.stdin.drain(), self.timeout)

    async def request(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        self.identifier += 1
        identifier = self.identifier
        message: dict[str, Any] = {"jsonrpc": "2.0", "id": identifier, "method": method}
        if params is not None:
            message["params"] = params
        await self.send(message)
        if self.process.stdout is None:
            raise RuntimeError("MCP stdout absent")
        while True:
            line = await asyncio.wait_for(self.process.stdout.readline(), self.timeout)
            if not line:
                raise RuntimeError(f"MCP server ended before {method} response")
            self._record("server_to_client", line)
            response = json.loads(line)
            if response.get("id") != identifier:
                if "id" in response:
                    raise ValueError("MCP response ID differed from request")
                continue
            if "error" in response:
                raise RuntimeError(f"MCP {method} failed: {response['error']}")
            return response["result"]

    async def tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        result = await self.request("tools/call", {"name": name, "arguments": arguments})
        if result.get("isError") or not isinstance(result.get("structuredContent"), dict):
            raise RuntimeError(f"MCP {name} failed: {result.get('content')}")
        return result["structuredContent"]


async def _mcp(state: Path, operation: str, *, cache: bool = True,
               assessment_id: str | None = None, eager_explain: bool = False) -> dict[str, Any]:
    start = time.perf_counter()
    command, environment = _server_args(state, cache)
    process = await asyncio.create_subprocess_exec(
        *command, cwd=state / "workspace", env=environment,
        stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE, limit=8 * 1024 * 1024 + 1)
    client = WireClient(process)
    result: dict[str, Any] | None = None
    error: str | None = None
    try:
        await client.request("initialize", {"protocolVersion": "2025-11-25", "capabilities": {},
                                            "clientInfo": {"name": "architecture-v3-host", "version": "1"}})
        await client.send({"jsonrpc": "2.0", "method": "notifications/initialized"})
        available = await client.request("tools/list")
        required = {"eal_assess_artifact_claim", "eal_explain_artifact_claim", "eal_finish_artifact_claim"}
        if not required <= {tool["name"] for tool in available["tools"]}:
            raise ValueError("recipient MCP server omitted a required operation")
        if operation == "assess":
            packet = await client.tool("eal_assess_artifact_claim",
                                       {"artifact_id": ARTIFACT, "claim": CLAIM})
            assessment_id = packet["assessment_id"]
            detail = packet.get("decisive", {})
            needs_explanation = (eager_explain or packet.get("status") != "supported"
                                 or detail.get("details_truncated") is True
                                 or any(item.get("status") == "active"
                                        for item in detail.get("objections", [])))
            explanation = (await client.tool("eal_explain_artifact_claim",
                                             {"artifact_id": ARTIFACT, "assessment_id": assessment_id,
                                              "claim": CLAIM}) if needs_explanation else None)
            finished = await client.tool("eal_finish_artifact_claim",
                                         {"artifact_id": ARTIFACT, "assessment_id": assessment_id,
                                          "claim": CLAIM})
            if packet != finished or (explanation is not None and explanation.get("packet") != packet):
                raise ValueError("recipient MCP assessment changed before finalisation")
            result = {"packet": packet, "explanation": explanation,
                      "mcp_elapsed_seconds": time.perf_counter() - start}
        elif operation == "explain" and assessment_id:
            result = await client.tool("eal_explain_artifact_claim",
                                       {"artifact_id": ARTIFACT, "assessment_id": assessment_id,
                                        "claim": CLAIM})
        else:
            raise ValueError("unknown MCP operation")
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
        raise
    finally:
        if process.stdin is not None:
            process.stdin.close()
        try:
            await asyncio.wait_for(process.wait(), timeout=10)
        except TimeoutError:
            process.kill()
            await process.wait()
        stderr = await process.stderr.read(4096) if process.stderr is not None else b""
        transcript = {"schema": "architecture-v3-mcp-wire/1", "operation": operation,
                      "messages": client.messages, "server_exit_code": process.returncode,
                      "stderr_tail": stderr.decode("utf-8", errors="replace"), "error": error}
        write_json(state / ("mcp-wire.json" if operation == "assess" else "mcp-explain-wire.json"), transcript)
    if process.returncode != 0 or result is None:
        raise RuntimeError("recipient MCP session failed after recording its wire transcript")
    return result


def _observations(state: Path, collection_id: str) -> dict[str, dict[str, Any]]:
    from eal.runtime import ReasoningService
    workspace = state / "workspace"
    service = ReasoningService(workspace, workspace / "tool.toml", state / "eal.sqlite3")
    collection = service.store.get(collection_id, kind="collection")
    observed: dict[str, dict[str, Any]] = {}
    for evidence_id, record in collection["records"].items():
        if record.get("status") != "ok" or not isinstance(record.get("value"), dict):
            raise ValueError(f"{evidence_id} lacks a successfully acquired observation")
        value = record["value"]
        check = value.get("check_id")
        if check not in CHECKS or type(value.get("passed")) is not bool:
            raise ValueError(f"{evidence_id} has no explicit Boolean finding")
        if check in observed and observed[check] != value:
            raise ValueError(f"opposed {check} premises received inconsistent observations")
        observed[check] = value
    if set(observed) != CHECKS:
        raise ValueError("current-source check closure is incomplete")
    return observed


def _plain_observations(state: Path, context: dict[str, Any], *, cache: bool) -> dict[str, dict[str, Any]]:
    workspace = state / "workspace"
    observed = {}
    trace = []
    for check in ("source_binding", "visible_tests", "import_cycles", "shared_boundary"):
        request = {"evidence_id": f"plain_{check}", "environment": "fulfilment_change",
                   "tool": "snapshot_probe", "tool_version": "1",
                   "input": {"check_id": check}, "context": context}
        sent = json_bytes(request)
        started = time.perf_counter()
        process = subprocess.run([sys.executable, str(workspace / "snapshot_probe.py")],
                                 input=sent, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                 cwd=workspace, timeout=150, check=False,
                                 env={**os.environ, "EAL_V3_CACHE": "1" if cache else "0"})
        trace.append({"check": check, "request_sha256": hashlib.sha256(sent).hexdigest(),
                      "response_sha256": hashlib.sha256(process.stdout).hexdigest(),
                      "request_bytes": len(sent), "response_bytes": len(process.stdout),
                      "elapsed_seconds": time.perf_counter() - started,
                      "exit_code": process.returncode})
        if process.returncode or len(process.stdout) > 65536:
            raise RuntimeError(f"plain {check} failed: {process.stderr[-300:]!r}")
        envelope = json.loads(process.stdout)
        if envelope.get("context") != context or envelope.get("request") != {
                key: request[key] for key in ("tool", "tool_version", "input", "context")}:
            raise ValueError("plain collector response differs from its request")
        value = envelope["value"]
        if (value.get("check_id") != check or type(value.get("passed")) is not bool
                or value.get("candidate_sha256") != context["candidate_sha256"]):
            raise ValueError("plain collector returned an invalid finding")
        observed[check] = value
    write_json(state / "plain-collector-trace.json",
               {"schema": "architecture-v3-plain-tool-trace/1", "calls": trace})
    return observed


def _packet_pair(binding: dict[str, Any], assessment: dict[str, Any] | None,
                 observations: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    packet = assessment["packet"] if assessment else None
    context = binding["context"]
    before = binding["baseline_manifest"]["files"]
    after = binding["candidate_manifest"]["files"]
    changed = sorted(name for name in before.keys() | after.keys() if before.get(name) != after.get(name))
    checks = [{"id": key, "passed": observations[key]["passed"],
               "detail": observations[key]["detail"][:160]}
              for key in ("source_binding", "visible_tests", "import_cycles", "shared_boundary")]
    failures = [item["id"] for item in checks if not item["passed"]]
    sites = observations["shared_boundary"].get("effect_call_sites", {})
    route_counts = {name: len(locations) for name, locations in sites.items()}
    base = {"candidate_sha256": context["candidate_sha256"],
            "baseline_sha256": context["baseline_sha256"],
            "family": context["family"], "feature": context["feature"],
            "changed_paths": changed[:MAX_CHANGED], "changed_path_count": len(changed),
            "checks": checks,
            "effect_route_counts": route_counts,
            "effect_route_certainty": "unknown: static sites cannot prove a unique mutation or exclude dead code",
            "public_impact_present": observations["shared_boundary"].get("impact_present", []),
            "public_impact_absent": observations["shared_boundary"].get("impact_absent", []),
            "obligations": failures or ["Inspect changed effect routes and compensation before acceptance."],
            "observation_digest": hashlib.sha256(json_bytes(observations)).hexdigest()}
    plain = {"schema": "architecture-v3-plain-packet/1", **base,
             "guidance": "Preserve one order lifecycle through the existing ports, compensation, idempotency and outbox; when a requirement exceeds a seam, revise the shared contract and its dependants together. Review duplicate effect routes and obsolete code. Visible tests do not establish final correctness or future debt reduction."}
    if not observations["visible_tests"]["passed"]:
        choice = "Repair or explain the failing visible tests, then reacquire this candidate's observations."
        selected = ("observed_visible_tests_fail", "current_review")
    elif not observations["import_cycles"]["passed"]:
        choice = "Review the detected import cycle and dependency direction, then reacquire."
        selected = ("observed_cycle", "current_review")
    elif not observations["shared_boundary"]["passed"]:
        choice = "Record the intentional port migration and check all affected callers and effects."
        selected = ("migration_review", "current_review")
    else:
        absent = observations["shared_boundary"].get("impact_absent", [])
        choice = ("Inspect the absent public-change symbols and their shared port effects before implementation: "
                  + ", ".join(absent[:3])) if absent else (
                      "Inspect changed effect paths and compensations, then reassess the next immutable source.")
        selected = ("mapped_public_change_surface", "current_review")
    plain["verification_choice"] = choice
    # Agent-visible argument status comes from the same bounded claim packet
    # whether the host fetched the full explanation or deferred it.
    arguments = ({item["id"]: item for item in packet["decisive"]["arguments"]}
                 if packet else {})
    argued = {"schema": "architecture-v3-eal-packet/1", **base,
              "eal_sha256": binding["eal_sha256"],
              "tool_registry_sha256": binding["registry_sha256"],
              "collector_sha256": binding["collector_sha256"],
              "assessment_id": packet["assessment_id"] if packet else None,
              "collection_id": packet["collection_id"] if packet else None,
              "claim": CLAIM, "claim_status": packet["status"] if packet else None,
              "objections": [{"id": item["id"], "status": item["status"]}
                             for item in packet["decisive"]["objections"]] if packet else [],
              "decisive_routes": [{"id": name, "status": arguments[name]["status"]}
                                   for name in selected if name in arguments],
              "guidance": plain["guidance"],
              "verification_choice": choice,
              "trace_retained_by_host": True}
    for label, candidate in (("P1", plain), ("P2", argued)):
        if label == "P2" and assessment is None:
            continue
        if len(json_bytes(candidate)) > MAX_PACKET_BYTES:
            raise ValueError(f"{label} packet exceeds {MAX_PACKET_BYTES} bytes")
    return {"P1": plain, "P2": argued}


def assess(args: argparse.Namespace) -> dict[str, Any]:
    wall = time.perf_counter()
    cpu = resource.getrusage(resource.RUSAGE_SELF)
    children = resource.getrusage(resource.RUSAGE_CHILDREN)
    binding = _initialise(args)
    state = args.state_dir.resolve()
    result = (asyncio.run(_mcp(state, "assess", cache=not args.disable_cache,
                               eager_explain=getattr(args, "eager_explain", False)))
              if args.arm == "P2" else None)
    observations = (_observations(state, result["packet"]["collection_id"])
                    if result else _plain_observations(state, binding["context"],
                                                       cache=not args.disable_cache))
    pairs = _packet_pair(binding, result, observations)
    if result and result["explanation"] is not None:
        write_json(state / "explanation.json", result["explanation"])
    write_json(state / f"packet-{args.arm}.json", pairs[args.arm])
    own = resource.getrusage(resource.RUSAGE_SELF)
    child = resource.getrusage(resource.RUSAGE_CHILDREN)
    metrics = {"schema": "architecture-v3-host-metrics/1",
               "measured_at": datetime.now(timezone.utc).isoformat(),
               "cache_enabled": not args.disable_cache,
               "arm": args.arm,
               "wall_seconds": time.perf_counter() - wall,
               "mcp_elapsed_seconds": result["mcp_elapsed_seconds"] if result else None,
               "host_cpu_seconds": own.ru_utime + own.ru_stime - cpu.ru_utime - cpu.ru_stime,
               "child_cpu_seconds": child.ru_utime + child.ru_stime - children.ru_utime - children.ru_stime,
               "packet_bytes": len(json_bytes(pairs[args.arm])),
               "packet_sha256": hashlib.sha256(json_bytes(pairs[args.arm])).hexdigest(),
               "trace_sha256": digest_file(state / ("mcp-wire.json" if result else "plain-collector-trace.json")),
               "tool_exchange_bytes": (sum(len(message["utf8_line"].encode("utf-8"))
                                           for message in json.loads((state / "mcp-wire.json").read_text())["messages"])
                                       if result else sum(call["request_bytes"] + call["response_bytes"]
                                                          for call in json.loads((state / "plain-collector-trace.json").read_text())["calls"])),
               "observation_digest": hashlib.sha256(json_bytes(observations)).hexdigest(),
               "collection_id": result["packet"]["collection_id"] if result else None,
               "assessment_id": result["packet"]["assessment_id"] if result else None,
               "claim_status": result["packet"]["status"] if result else None}
    if result:
        metrics["explanation_fetched"] = result["explanation"] is not None
    write_json(state / "metrics.json", metrics)
    return metrics


def explain(args: argparse.Namespace) -> dict[str, Any]:
    state = args.state_dir.resolve()
    retained = json.loads((state / "metrics.json").read_text(encoding="utf-8"))
    if args.assessment_id != retained["assessment_id"]:
        raise ValueError("requested assessment differs from the host's retained assessment")
    current = asyncio.run(_mcp(state, "explain", assessment_id=args.assessment_id))
    retained_path = state / "explanation.json"
    if retained_path.exists() and current != json.loads(retained_path.read_text(encoding="utf-8")):
        raise ValueError("reopened MCP explanation differs from retained trace")
    if current.get("packet", {}).get("assessment_id") != args.assessment_id:
        raise ValueError("MCP explanation differs from retained assessment")
    if not retained_path.exists():
        write_json(retained_path, current)
    if args.output:
        write_json(args.output, current)
    return current


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_subparsers(dest="action", required=True)
    run = actions.add_parser("assess")
    run.add_argument("--baseline", type=Path, required=True)
    run.add_argument("--candidate", type=Path, required=True)
    run.add_argument("--family", choices=("R", "W"), required=True)
    run.add_argument("--feature", choices=("B", "C", "D"), required=True)
    run.add_argument("--arm", choices=("P1", "P2"), required=True)
    run.add_argument("--state-dir", type=Path, required=True)
    run.add_argument("--disable-cache", action="store_true")
    run.add_argument("--eager-explain", action="store_true",
                     help="Benchmark ablation: fetch full scoped explanation on every P2 assessment")
    detail = actions.add_parser("explain")
    detail.add_argument("--state-dir", type=Path, required=True)
    detail.add_argument("--assessment-id", required=True)
    detail.add_argument("--output", type=Path)
    staging = actions.add_parser("prepare")
    staging.add_argument("--source", type=Path, required=True)
    staging.add_argument("--brief", type=Path, required=True)
    staging.add_argument("--arm", choices=("P0", "P1", "P2"), required=True)
    staging.add_argument("--family", choices=("R", "W"), required=True)
    staging.add_argument("--feature", choices=("B", "C", "D"), required=True)
    staging.add_argument("--packet", type=Path)
    staging.add_argument("--destination", type=Path, required=True)
    staging.add_argument("--record", type=Path, required=True)
    verify = actions.add_parser("verify-exposure")
    verify.add_argument("--trial", type=Path, required=True)
    verify.add_argument("--record", type=Path, required=True)
    clean = actions.add_parser("snapshot")
    clean.add_argument("--trial", type=Path, required=True)
    clean.add_argument("--record", type=Path, required=True)
    clean.add_argument("--destination", type=Path, required=True)
    clean.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args()
    response = ({"assess": assess, "explain": explain, "prepare": prepare,
                 "verify-exposure": verify_exposure, "snapshot": snapshot}[args.action])(args)
    print(json.dumps(response, sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()
