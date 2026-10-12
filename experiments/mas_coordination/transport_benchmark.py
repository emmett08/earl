"""Reproducible software-only transport benchmark with retained raw evidence.

Run from the repository root with the EAL interpreter, for example::

  .venv/bin/python -m experiments.mas_coordination.transport_benchmark \
    --output experiments/mas_coordination/results/transport-004

The frozen plan is read before execution. Accepted content and useful durable
states must match across arms before any descriptive speed ratios are emitted.
"""
from __future__ import annotations

import argparse
import cProfile
from collections import Counter
from contextlib import contextmanager
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import pstats
import resource
import statistics
import subprocess
import sys
import time
from typing import Any

from eal.coordination.bus import JsonBus, envelope
from eal.coordination.ledger import canonical_json

from .benchmark_instrumentation.sitecustomize import install
from .benchmark_legacy.lab_mcp import LabMCPTransport as LegacyTransport
from .benchmark_controls import make_control


ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
PLAN_PATH = HERE / "transport-benchmark-plan.json"
ARMS = ("legacy_one_shot", "persistent_mcp", "persistent_mcp_codec", "persistent_rust_admission", "json_control")


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")


def cpu_usage() -> float:
    own = resource.getrusage(resource.RUSAGE_SELF)
    children = resource.getrusage(resource.RUSAGE_CHILDREN)
    return own.ru_utime + own.ru_stime + children.ru_utime + children.ru_stime


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def launches(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines()]


@contextmanager
def instrument(bus, log: Path, profile_server=False):
    """Count actual process construction, including isolated server children."""
    original = install(str(log))
    environment = getattr(bus, "_environment", None)
    if environment is not None:
        def traced_environment():
            value = environment()
            value["BENCHMARK_LAUNCH_LOG"] = str(log)
            value["PYTHONPATH"] = os.pathsep.join([str(HERE / "benchmark_instrumentation"), value.get("PYTHONPATH", "")])
            if profile_server:
                value["BENCHMARK_SERVER_PROFILE"] = str(log.parent / "server-profile")
            return value
        bus._environment = traced_environment
    # Legacy reserve/finish uses LabTransport.command's environment directly.
    # The explicit variable propagates its instrumentation through that path.
    prior = {key: os.environ.get(key) for key in ("BENCHMARK_LAUNCH_LOG", "PYTHONPATH")}
    os.environ["BENCHMARK_LAUNCH_LOG"] = str(log)
    os.environ["PYTHONPATH"] = os.pathsep.join([str(HERE / "benchmark_instrumentation"), prior["PYTHONPATH"] or ""])
    try:
        yield
    finally:
        subprocess.Popen.__init__ = original
        if environment is not None:
            bus._environment = environment
        for key, value in prior.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def make_bus(arm: str, runtime: Path, database: Path):
    if arm == "json_control":
        return JsonBus(database)
    if arm == "legacy_one_shot":
        return LegacyTransport(runtime, database)
    if arm in {"persistent_mcp", "persistent_mcp_codec"}:
        return make_control(arm, runtime, database)
    if arm != "persistent_rust_admission":
        raise ValueError("Unknown transport benchmark arm")
    from eal.coordination.lab_mcp import LabMCPTransport
    binary = ROOT / "src/eal/coordination/rust_codec/target/release/mas-protocol-codec"
    return LabMCPTransport(runtime, database, binary=binary)


@contextmanager
def owned_bus(bus):
    """A failed correctness check also tears down owned persistent processes."""
    try:
        yield bus
    finally:
        if hasattr(bus, "close"):
            bus.close()


def fixed_payloads(plan: dict) -> list[dict]:
    return [dict(message_id=f"msg-{index + 1:03}", sender="assessor", recipient="reviewer",
                 kind="assessment", schema="EAL/MAS-coordination/3", task_id="benchmark-task",
                 finding={"status": "supported", "claim_id": "bounded-latency", "evidence_ids": ["synthetic-observation"]},
                 padding="x" * size)
            for index, size in enumerate(plan["message_padding_bytes"])]


def run_cycle(arm: str, repetition: int, directory: Path, runtime: Path, plan: dict, profile_server=False) -> dict:
    directory.mkdir(parents=True, exist_ok=False)
    log = directory / "launches.jsonl"
    timings = []
    run_id = plan["run_id"]
    expected_payloads = fixed_payloads(plan)
    load_average_before = list(os.getloadavg())
    cpu_start = cpu_usage()
    construct_start = time.perf_counter_ns()
    bus = make_bus(arm, runtime, directory / "mailbox.sqlite")
    constructor_ns = time.perf_counter_ns() - construct_start

    def operation(name, function, *, size=None, rejection=False):
        before = len(launches(log))
        start = time.perf_counter_ns()
        try:
            result = function()
        except ValueError as error:
            if not rejection:
                raise
            result = {"rejected": True, "diagnostic": str(error)}
        elapsed = time.perf_counter_ns() - start
        if rejection:
            assert result.get("rejected") is True, "Changed content must be rejected"
        new_launches = launches(log)[before:]
        codec_launches = sum(item["category"] == "rust_codec" for item in new_launches)
        codec_operation = name in {"send", "duplicate_send", "changed_content_rejection"}
        codec_phase = "not_used"
        if codec_operation and arm != "json_control":
            codec_phase = ("oneshot" if arm in {"legacy_one_shot", "persistent_mcp"}
                           else "cold_first_use" if codec_launches else "reused_process")
        timings.append(dict(operation=name, padding_bytes=size, wall_ns=elapsed,
                            subprocesses=len(new_launches), codec_phase=codec_phase,
                            session_phase="oneshot" if arm == "legacy_one_shot" else "cold_first_use" if name == "create" else "post_create"))
        return result

    with instrument(bus, log, profile_server), owned_bus(bus):
        cycle_start = time.perf_counter_ns()
        operation("create", lambda: bus.create(run_id, *plan["participants"], **plan["limits"]))
        reservation = operation("reserve", lambda: bus.reserve(run_id, "assessor", "call-001"))
        assert reservation == {"reserved": True, "call_id": "call-001"}
        completion = operation("finish", lambda: bus.finish(run_id, "assessor", "call-001", plan["worker_evidence"]))
        assert completion == {"recorded": True}
        accepted = []
        for index, payload in enumerate(expected_payloads):
            size = plan["message_padding_bytes"][index]
            sent = operation("send", lambda: bus.send(run_id, payload, actor="assessor"), size=size)
            assert sent == {"accepted": True, "duplicate": False, "sequence": index + 1}
            if index == 0:
                operation("premature_ack_rejection", lambda: bus.acknowledge(run_id, payload["message_id"], "reviewer"), size=size, rejection=True)
            duplicate = operation("duplicate_send", lambda: bus.send(run_id, payload, actor="assessor"), size=size)
            assert duplicate == {"accepted": True, "duplicate": True, "sequence": index + 1}
            changed = dict(payload, padding="y" + payload["padding"][1:])
            operation("changed_content_rejection", lambda: bus.send(run_id, changed, actor="assessor"), size=size, rejection=True)
            wanted = {"message": envelope(run_id, payload), "sequence": index + 1, "redelivered": False}
            received = operation("receive", lambda: bus.receive(run_id, "reviewer", limit=8), size=size)
            assert received == [wanted], "First delivery must preserve exact canonical envelope"
            redelivered = operation("redelivery", lambda: bus.receive(run_id, "reviewer", limit=8), size=size)
            assert redelivered == [dict(wanted, redelivered=True)]
            if index == 0:
                operation("wrong_recipient_ack_rejection", lambda: bus.acknowledge(run_id, payload["message_id"], "assessor"), size=size, rejection=True)
            ack = operation("ack", lambda: bus.acknowledge(run_id, payload["message_id"], "reviewer"), size=size)
            assert ack == {"acknowledged": True, "message_id": payload["message_id"]}
            accepted.append(wanted["message"])
        assert operation("empty_receive", lambda: bus.receive(run_id, "reviewer", limit=8)) == []
        status = operation("status", lambda: bus.status(run_id))
        cycle_ns = time.perf_counter_ns() - cycle_start
        expected_bytes = sum(len(canonical_json(item).encode()) for item in accepted)
        assert status["usage"] == dict(messages=3, bytes=expected_bytes, calls=1)
        assert len(status["messages"]) == 3 and all(item["received"] and item["acked"] for item in status["messages"])
        assert status["calls"] == [{"id": "call-001", "actor": "assessor", "state": "recorded", "evidence": plan["worker_evidence"]}]
        runtime_metrics = None
        if arm.startswith("persistent"):
            # Diagnostic call is excluded from the useful-cycle timing.
            runtime_metrics = bus.mcp_call("mas_runtime_info", {})
        shutdown_start = time.perf_counter_ns()
        if hasattr(bus, "close"):
            bus.close()
        shutdown_ns = time.perf_counter_ns() - shutdown_start

    result = dict(arm=arm, repetition=repetition, operations=timings, constructor_ns=constructor_ns,
                  cold_first_operation_ns=timings[0]["wall_ns"], shutdown_ns=shutdown_ns,
                  cold_first_codec_operation_ns=next((item["wall_ns"] for item in timings if item["codec_phase"] == "cold_first_use"), None),
                  post_create_operations_ns=sum(item["wall_ns"] for item in timings[1:]),
                  useful_cycle_ns=cycle_ns, parent_and_reaped_children_cpu_seconds=cpu_usage() - cpu_start,
                  load_average_before=load_average_before,
                  subprocess_counts=dict(Counter(item["category"] for item in launches(log))),
                  runtime_metrics=runtime_metrics,
                  invariant_checks="passed", canonical_envelopes_sha256=hashlib.sha256(canonical_json(accepted).encode()).hexdigest(),
                  useful_state={"usage": status["usage"], "message_ids": [item["message_id"] for item in accepted],
                                "all_received": True, "all_acknowledged": True, "pending": 0, "calls": status["calls"]})
    write_json(directory / "sample.json", result)
    write_json(directory / "final-status.json", status)
    write_json(directory / "accepted-envelopes.json", accepted)
    return result


def summarize(samples: list[dict]) -> dict:
    states = [canonical_json(item["useful_state"]) for item in samples]
    content = {item["canonical_envelopes_sha256"] for item in samples}
    assert len(set(states)) == 1 and len(content) == 1, "Equivalent outcomes are a prerequisite for speed reporting"
    summary = {}
    for arm in ARMS:
        selected = [item for item in samples if item["arm"] == arm]
        if not selected:
            continue
        by_operation = {}
        for operation in {timing["operation"] for sample in selected for timing in sample["operations"]}:
            values = [timing["wall_ns"] for sample in selected for timing in sample["operations"] if timing["operation"] == operation]
            by_operation[operation] = dict(samples=len(values), median_ms=statistics.median(values) / 1e6,
                                           min_ms=min(values) / 1e6, max_ms=max(values) / 1e6)
            warm = [timing["wall_ns"] for sample in selected for timing in sample["operations"]
                    if timing["operation"] == operation and timing["operation"] != "create"
                    and timing["codec_phase"] != "cold_first_use"]
            by_operation[operation]["excluding_first_use"] = (dict(samples=len(warm), median_ms=statistics.median(warm) / 1e6)
                                                              if warm else None)
        summary[arm] = dict(samples=len(selected), median_cycle_ms=statistics.median(item["useful_cycle_ns"] for item in selected) / 1e6,
                            median_cold_first_operation_ms=statistics.median(item["cold_first_operation_ns"] for item in selected) / 1e6,
                            median_post_create_operations_ms=statistics.median(item["post_create_operations_ns"] for item in selected) / 1e6,
                            median_cpu_seconds=statistics.median(item["parent_and_reaped_children_cpu_seconds"] for item in selected),
                            subprocess_counts=[item["subprocess_counts"] for item in selected], operations=by_operation)
    paired = {}
    for previous, current in (("legacy_one_shot", "persistent_mcp"), ("persistent_mcp", "persistent_mcp_codec"),
                              ("persistent_mcp_codec", "persistent_rust_admission"),
                              ("legacy_one_shot", "persistent_rust_admission"),
                              ("legacy_one_shot", "persistent_mcp_codec")):
        ratios = []
        for repetition in {item["repetition"] for item in samples}:
            selected = {item["arm"]: item for item in samples if item["repetition"] == repetition}
            if previous in selected and current in selected:
                ratios.append(selected[previous]["useful_cycle_ns"] / selected[current]["useful_cycle_ns"])
        if ratios:
            paired[f"{previous}_over_{current}"] = dict(raw_ratios=ratios, median=statistics.median(ratios))
    return dict(equivalent_useful_states=True, identical_canonical_content=True, arms=summary,
                paired_cycle_ratios=paired, statistical_scope="Descriptive finite paired samples; no population or inference-quality claim.")


def codec_microbench(output: Path, runtime: Path, plan: dict, iterations: int = 12) -> dict:
    """Same Rust executable and representation; only execution lifetime varies."""
    from eal.coordination.codec_process import CodecProcess
    binary = ROOT / "src/eal/coordination/rust_codec/target/release/mas-protocol-codec"
    samples = []
    payloads = fixed_payloads(plan)
    for index, payload in enumerate(payloads):
        canonical = envelope(plan["run_id"], payload)
        source = canonical_json(canonical)
        size = plan["message_padding_bytes"][index]
        for mode in (("oneshot", "persistent") if index % 2 == 0 else ("persistent", "oneshot")):
            directory = output / f"{size:05d}-{mode}"
            directory.mkdir(parents=True, exist_ok=False)
            log = directory / "launches.jsonl"
            codec = CodecProcess(binary)
            timings = []

            def invoke(operation, text, iteration):
                started = time.perf_counter_ns()
                if mode == "persistent":
                    result = codec.call(operation, text)
                else:
                    process = subprocess.run([str(binary), operation, "--max-bytes", "65536", "--max-depth", "32"],
                                             input=text, text=True, capture_output=True, timeout=10, check=True)
                    result = json.loads(process.stdout)
                timings.append(dict(operation=operation, iteration=iteration, wall_ns=time.perf_counter_ns() - started,
                                    phase="cold_first" if iteration == 0 and operation == "encode" else "warm"))
                assert result["ok"] is True
                return result

            # Only parent Rust processes start here; no SDK or server involved.
            original = install(str(log))
            cpu_start = cpu_usage()
            try:
                for iteration in range(iterations):
                    wire = invoke("encode", source, iteration)["text"]
                    assert invoke("parse", wire, iteration)["message"] == canonical
            finally:
                codec.close()
                subprocess.Popen.__init__ = original
            sample = dict(codec_mode=mode, padding_bytes=size, iterations=iterations, timings=timings,
                          process_cpu_seconds=cpu_usage() - cpu_start, launches=len(launches(log)),
                          binary_sha256=sha256(binary), representation_roundtrips="passed")
            write_json(directory / "sample.json", sample)
            samples.append(sample)
    summary = {}
    for size in plan["message_padding_bytes"]:
        modes = {}
        for mode in ("oneshot", "persistent"):
            sample = next(item for item in samples if item["padding_bytes"] == size and item["codec_mode"] == mode)
            modes[mode] = {operation: statistics.median(item["wall_ns"] for item in sample["timings"]
                                                      if item["operation"] == operation and item["phase"] == "warm") / 1e6
                           for operation in ("encode", "parse")}
        summary[str(size)] = dict(warm_median_ms=modes,
                                 oneshot_over_persistent={operation: modes["oneshot"][operation] / modes["persistent"][operation]
                                                          for operation in ("encode", "parse")})
    report = dict(scope="Rust codec-only execution modes, same compiled executable; no MCP, SQLite or inference.",
                  samples=samples, summary=summary)
    write_json(output / "report.json", report)
    return report


def manifest(runtime: Path, plan: dict, arguments) -> dict:
    sources = [PLAN_PATH, Path(__file__), HERE / "benchmark_instrumentation/sitecustomize.py",
               HERE / "benchmark_legacy/lab.py", HERE / "benchmark_legacy/lab_mcp.py",
               ROOT / "src/eal/coordination/lab_mcp.py",
               ROOT / "src/eal/coordination/bus.py", ROOT / "src/eal/coordination/ledger.py"]
    sources.extend((HERE / "benchmark_controls").rglob("*.py"))
    sources.append(HERE / "benchmark_controls/source-map.json")
    sources.extend((ROOT / "src/eal/coordination").glob("*codec*.py"))
    sources.extend((ROOT / "src/eal/coordination").glob("lab_server.py"))
    sources.extend((ROOT / "src/eal/coordination").glob("lab_admission.py"))
    sources.append(ROOT / "src/eal/coordination/persistent_mcp.py")
    sources.extend((ROOT / "src/eal/coordination/rust_codec").glob("src/*.rs"))
    sources.extend(ROOT / "src/eal/coordination/rust_codec" / name for name in ("Cargo.toml", "Cargo.lock", "rust-toolchain.toml"))
    sources.append(ROOT / "src/eal/coordination/rust_codec/target/release/mas-protocol-codec")
    sources.extend(runtime / name for name in ("runtime/mas_protocol/store.py", "runtime/mas_protocol/protocol.py", "runtime/mas_protocol/mcp_server.py", "runtime/mas_protocol/cli.py", "rust-protocol/target/release/mas-protocol-codec"))
    versions = {name: importlib.metadata.version(name) for name in ("mcp", "fastmcp")}
    isolated = subprocess.run([str(runtime / ".venv/bin/python"), "-c",
                               "import importlib.metadata,json,sys;print(json.dumps({'python':sys.version,'mcp':importlib.metadata.version('mcp')}))"],
                              text=True, capture_output=True, timeout=10, check=True)
    tool_versions = {}
    for name in ("rustc", "cargo"):
        try:
            result = subprocess.run([name, "--version"], text=True, capture_output=True, timeout=10, check=False)
            tool_versions[name] = result.stdout.strip() if result.returncode == 0 else "unavailable"
        except (FileNotFoundError, subprocess.TimeoutExpired):
            tool_versions[name] = "unavailable"
    return dict(schema=plan["schema"], started_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                command_arguments=vars(arguments), python=sys.version, platform=platform.platform(),
                processor=platform.processor(), logical_cpus=os.cpu_count(), packages=versions,
                isolated_lab=json.loads(isolated.stdout),
                build_tools=tool_versions,
                source_hashes={str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path): sha256(path) for path in sources if path.is_file()},
                launch_instrumentation="Parent Popen constructor and explicitly injected sitecustomize in isolated Python servers/CLI; one record per successful process construction.",
                cpu_accounting="RUSAGE_SELF plus RUSAGE_CHILDREN after persistent server shutdown; excludes still-live unrelated children.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime", default="/workspace/mas-protocol-lab")
    parser.add_argument("--output", required=True)
    parser.add_argument("--repetitions", type=int, default=5)
    parser.add_argument("--arms", default=",".join(ARMS))
    parser.add_argument("--profile", action="store_true", help="Extra diagnostic profile cycles, excluded from headline timings")
    parser.add_argument("--codec-microbench", action="store_true", help="Direct same-binary one-shot versus persistent encode/parse diagnostic")
    arguments = parser.parse_args()
    if not 1 <= arguments.repetitions <= 12:
        parser.error("--repetitions must be 1..12")
    selected = arguments.arms.split(",")
    if not selected or len(selected) != len(set(selected)) or not set(selected) <= set(ARMS):
        parser.error("--arms must be a nonempty unique subset of registered arms")
    plan = json.loads(PLAN_PATH.read_text())
    output = Path(arguments.output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    runtime = Path(arguments.runtime).resolve()
    write_json(output / "plan.json", plan)
    provenance = manifest(runtime, plan, arguments)
    write_json(output / "manifest.json", provenance)
    samples = []
    try:
        for repetition in range(arguments.repetitions):
            order = list(ARMS[repetition % len(ARMS):] + ARMS[:repetition % len(ARMS)])
            for arm in [item for item in order if item in selected]:
                sample = run_cycle(arm, repetition, output / "samples" / f"{repetition:02d}-{arm}", runtime, plan)
                samples.append(sample)
                write_json(output / "raw-samples.json", samples)
                print(f"{repetition:02d} {arm}: {sample['useful_cycle_ns'] / 1e6:.3f} ms; invariants passed", flush=True)
        write_json(output / "report.json", summarize(samples))
        if arguments.codec_microbench:
            codec_microbench(output / "codec-microbench", runtime, plan)
        if arguments.profile:
            for arm in selected:
                profiler = cProfile.Profile()
                profiler.runcall(run_cycle, arm, -1, output / "profiles" / arm, runtime, plan, arm.startswith("persistent"))
                profiler.dump_stats(str(output / "profiles" / arm / "python.prof"))
                with (output / "profiles" / arm / "python-profile.txt").open("w") as stream:
                    pstats.Stats(profiler, stream=stream).strip_dirs().sort_stats("cumulative").print_stats(50)
        changed = []
        for name, digest in provenance["source_hashes"].items():
            path = Path(name) if name.startswith("/") else ROOT / name
            if not path.is_file() or sha256(path) != digest:
                changed.append(name)
        write_json(output / "source-stability.json", {"unchanged": not changed, "changed_paths": changed})
        if changed:
            raise RuntimeError("Benchmark source or executable changed during execution; retain samples as preliminary only")
    except BaseException as error:
        write_json(output / "failure.json", {"type": type(error).__name__, "message": str(error), "completed_samples": len(samples)})
        raise
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
