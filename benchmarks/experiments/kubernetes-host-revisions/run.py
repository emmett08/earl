#!/usr/bin/env python3
"""Developmental, offline EAL/2 host and finite-family revision study.

No API calls or cluster access occur here. Synthetic JSON observations are
written into a fresh temporary workspace for each revision.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import statistics
import tempfile
import time
from pathlib import Path

from eal.artifacts import ArtifactRegistry
from eal.families import FamilyRegistry
from eal.routing import TaskFamilyHost
from eal.runtime import ReasoningService


ROOT = Path(__file__).resolve().parent
FILES = ("source.eal", "artifacts.toml", "families.toml", "manifest.json")
ALL_FAMILIES = frozenset(("checkout_latency", "rollout_digest", "service_failover"))
CONTEXT = {"cluster": "prod_east", "namespace": "checkout"}
# The frozen fixture predates the claim route's complete-collection gate. Its
# EAL statuses remain a raw evaluator regression; these revisions now refuse
# recipient delivery because evidence required by the claim is stale.
EXPECTED_REFUSALS = frozenset(("stale_load_record", "stale_pressure_gap"))


def _bytes(value: object) -> int:
    return len(json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))


def _summary(values: list[int]) -> dict[str, float]:
    ordered = sorted(values)
    return {
        "median_ms": round(statistics.median(ordered) / 1e6, 3),
        "p95_ms": round(ordered[min(len(ordered) - 1, int(0.95 * len(ordered) + 0.999999) - 1)] / 1e6, 3),
    }


def _validate_manifest(manifest: dict) -> None:
    if manifest.get("schema") != "eal2-kubernetes-host-revisions/1":
        raise ValueError("Wrong study schema")
    if manifest.get("context") != CONTEXT or manifest.get("artifact_id") != "k8s_checkout":
        raise ValueError("Unexpected host scope")
    revisions, queries = manifest.get("revisions"), manifest.get("queries")
    if not isinstance(revisions, list) or not isinstance(queries, list) or not revisions or not queries:
        raise ValueError("Study requires predeclared revisions and queries")
    if len({row["id"] for row in revisions}) != len(revisions):
        raise ValueError("Duplicate revision")
    if len({row["id"] for row in queries}) != len(queries):
        raise ValueError("Duplicate query")
    for row in revisions:
        if row["expected_status"] not in {"supported", "contested", "unsupported", "out_of_scope"}:
            raise ValueError("Unknown expected status")
        if row.get("expected_record_status") not in {"supported", "contested", "unsupported", "out_of_scope"}:
            raise ValueError("Unknown expected record status")
        for key in ("load", "coverage", "pressure", "isolation"):
            if not isinstance(row[key], dict) or "at" not in row[key]:
                raise ValueError("Missing frozen observation")
    for row in queries:
        if not isinstance(row.get("relevant"), list) or not set(row["relevant"]) <= ALL_FAMILIES:
            raise ValueError("Invalid reference relevance set")


def _record(tool: str, observation: dict, *, fixed: dict | None = None) -> dict:
    contents = fixed if fixed is not None else observation
    return {
        "context": CONTEXT,
        "observed_at": observation["at"],
        "request": {
            "context": CONTEXT, "input": {}, "mode": "deterministic",
            "tool": tool, "tool_version": "1",
        },
        "value": {key: value for key, value in contents.items() if key != "at"},
    }


def _workspace(path: Path, revision: dict) -> None:
    path.mkdir(parents=True)
    observations = path / "observations"
    observations.mkdir()
    for file in FILES[:3]:
        shutil.copy2(ROOT / file, path / file)
    static = {
        "load_reader": revision["load"],
        "coverage_reader": revision["coverage"],
        "pressure_reader": revision["pressure"],
        "isolation_reader": revision["isolation"],
        "digest_reader": {
            "at": "2026-09-24T11:59:00Z", "deployment": "checkout-api",
            "digest": "sha256:ca42", "admission_verified": True,
        },
        "failover_reader": {
            "at": "2026-09-24T11:59:00Z", "service": "checkout-api",
            "endpoint_ready": True, "failover_ms": 170,
        },
    }
    lines = []
    for tool, observation in static.items():
        (observations / f"{tool}.json").write_text(
            json.dumps(_record(tool, observation), sort_keys=True), encoding="utf-8"
        )
        lines.append(
            f'[tools.{tool}]\nkind = "json_file"\nmode = "deterministic"\n'
            f'version = "1"\npath = "observations/{tool}.json"\n'
        )
    (path / "tools.toml").write_text("\n".join(lines), encoding="utf-8")


def _host(path: Path) -> TaskFamilyHost:
    service = ReasoningService(path, path / "tools.toml", database_path=path / "runs.sqlite3")
    artifacts = ArtifactRegistry.load(service, path / "artifacts.toml")
    families = FamilyRegistry.load(artifacts, path / "families.toml")
    return TaskFamilyHost(
        families, principal="synthetic_developmental_runner",
        authorised_families=ALL_FAMILIES,
        authorised_claims={"k8s_checkout": ALL_FAMILIES},
    )


def _retrieval(host: TaskFamilyHost, queries: list[dict]) -> dict:
    rows = []
    tp = fp = fn = 0
    top_one_hits = 0
    zero_target_count = zero_target_abstentions = 0
    times = []
    for item in queries:
        start = time.perf_counter_ns()
        suggestions = host.candidates(item["query"], limit=3)
        times.append(time.perf_counter_ns() - start)
        predicted = {row["family_id"] for row in suggestions}
        relevant = set(item["relevant"])
        tp += len(predicted & relevant)
        fp += len(predicted - relevant)
        fn += len(relevant - predicted)
        top_one_hits += int(bool(suggestions and suggestions[0]["family_id"] in relevant))
        if not relevant:
            zero_target_count += 1
            zero_target_abstentions += int(not suggestions)
        rows.append({
            "id": item["id"], "relevant": sorted(relevant),
            "candidates": suggestions,
            "true_positive": len(predicted & relevant),
            "false_positive": len(predicted - relevant),
            "false_negative": len(relevant - predicted),
        })
    return {
        "queries": rows,
        "micro_precision_at_3": round(tp / (tp + fp), 4) if tp + fp else None,
        "micro_recall_at_3": round(tp / (tp + fn), 4) if tp + fn else None,
        "top_one_hit_rate_over_target_queries": round(top_one_hits / (len(queries) - zero_target_count), 4),
        "abstention_rate_on_zero_target_queries": (
            round(zero_target_abstentions / zero_target_count, 4) if zero_target_count else None
        ),
        "counts": {"tp": tp, "fp": fp, "fn": fn, "zero_target": zero_target_count,
                   "zero_target_abstentions": zero_target_abstentions},
        "retrieval_latency": _summary(times),
        "interpretation": "Single-author relevance labels assess lexical candidate ranking only; suggestions cannot select bindings or assert a claim.",
    }


def _revision(path: Path, row: dict, repetitions: int) -> dict:
    _workspace(path, row)
    host = _host(path)
    timings = {"assess": [], "explain": [], "finish": [], "end_to_end": []}
    packet = trace = refusal_reason = None
    assessment = None
    refused = row["id"] in EXPECTED_REFUSALS
    store = host.families.artifacts.service.store
    for _ in range(repetitions):
        started = time.perf_counter_ns()
        try:
            packet = host.assess("checkout_latency", CONTEXT, "checkout_latency")
        except ValueError as exc:
            if not refused or not str(exc).startswith("Claim assessment unresolved: required evidence "):
                raise
            refusal_reason = str(exc)
            packet = trace = None
            packet_done = time.perf_counter_ns()
            if store.list(kind="artifact_packet") or store.list(kind="artifact_claim_packet"):
                raise AssertionError("Refused revision issued a recipient packet")
            retained = store.list(kind="assessment", limit=1)
            if not retained:
                raise AssertionError("Refused revision did not retain its raw assessment")
            assessment = store.get(retained[0]["id"], kind="assessment")
            timings["assess"].append(packet_done - started)
            timings["end_to_end"].append(packet_done - started)
            continue
        if refused:
            raise AssertionError(f'{row["id"]}: stale required evidence issued a recipient packet')
        packet_done = time.perf_counter_ns()
        trace = host.explain("checkout_latency", CONTEXT, "checkout_latency", packet["assessment_id"])
        trace_done = time.perf_counter_ns()
        finished = host.finish("checkout_latency", CONTEXT, "checkout_latency", packet["assessment_id"])
        done = time.perf_counter_ns()
        if finished != packet:
            raise AssertionError("Host final packet changed after explanation")
        assessment = store.get(packet["assessment_id"], kind="assessment")
        timings["assess"].append(packet_done - started)
        timings["explain"].append(trace_done - packet_done)
        timings["finish"].append(done - trace_done)
        timings["end_to_end"].append(done - started)
    assert assessment is not None
    raw_status = assessment["claims"]["checkout_latency"]["status"]
    record_status = assessment["claims"]["checkout_test_record"]["status"]
    if raw_status != row["expected_status"]:
        raise AssertionError(
            f'{row["id"]}: expected raw status {row["expected_status"]}, saw {raw_status}'
        )
    if record_status != row["expected_record_status"]:
        raise AssertionError(
            f'{row["id"]}: expected historical record {row["expected_record_status"]}, saw {record_status}'
        )
    if refused:
        if packet is not None or trace is not None or refusal_reason is None:
            raise AssertionError("Unresolved revision returned a packet or trace")
        collection = store.get(assessment["collection_id"], kind="collection")
        unavailable = {name: assessment["evidence"][name]["reasons"]
                       for name in sorted(collection["records"])
                       if assessment["evidence"][name]["status"] != "available"}
        if row["expected_cause"] not in unavailable:
            raise AssertionError(f'{row["id"]}: expected stale evidence absent from raw assessment')
        if not any("exceeds max_age" in reason for reasons in unavailable.values() for reason in reasons):
            raise AssertionError(f'{row["id"]}: no stale required observation explains refusal')
        decisive = None
        packet_size = trace_size = ratio = packet_hash = evidence_integrity = None
        refusal = {"reason": refusal_reason, "unavailable_evidence": unavailable}
    else:
        assert packet is not None and trace is not None
        decisive = packet["decisive"]
        if packet["status"] != row["expected_status"] or row["expected_cause"] not in json.dumps(decisive):
            raise AssertionError(f'{row["id"]}: checked packet status or cause differs from fixture')
        if packet["claim"] != "checkout_latency" or packet["artifact_id"] != "k8s_checkout":
            raise AssertionError("Packet escaped its selected claim")
        if (trace["packet"] != packet or set(trace["arguments"]) != {"load_route", "record_route"}
                or set(trace["premises"]) != {"checkout_test_record"}):
            raise AssertionError("Explanation omitted the selected claim's premise chain")
        if _bytes(packet) > 3072:
            raise AssertionError("Packet exceeded its byte contract")
        packet_size, trace_size = _bytes(packet), _bytes(trace)
        ratio = round(packet_size / trace_size, 4)
        packet_hash = hashlib.sha256(
            json.dumps(packet, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        evidence_integrity = packet["evidence_integrity"]
        refusal = None
    return {
        "id": row["id"], "expected_status": row["expected_status"],
        "observed_status": None if refused else packet["status"],
        "raw_assessment_status": raw_status,
        "host_outcome": "refused_unresolved" if refused else "issued",
        "refusal": refusal,
        "expected_record_status": row["expected_record_status"],
        "observed_record_status": record_status,
        "decisive": decisive,
        "packet_bytes": packet_size, "direct_trace_bytes": trace_size,
        "packet_to_trace_byte_ratio": ratio,
        "latency": {key: _summary(samples) if samples else None for key, samples in timings.items()},
        "evidence_integrity": evidence_integrity,
        "packet_hash_sha256": packet_hash,
    }


def run(repetitions: int = 5) -> dict:
    if type(repetitions) is not int or not 1 <= repetitions <= 100:
        raise ValueError("Repetitions must be between 1 and 100")
    manifest = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))
    _validate_manifest(manifest)
    source_hash = hashlib.sha256((ROOT / "source.eal").read_bytes()).hexdigest()
    hashes = {file: hashlib.sha256((ROOT / file).read_bytes()).hexdigest() for file in FILES}
    with tempfile.TemporaryDirectory(prefix="eal2-k8s-revision-") as temporary:
        base = Path(temporary)
        revision_results = []
        for row in manifest["revisions"]:
            revision_results.append(_revision(base / row["id"], row, repetitions))
        retrieval = _retrieval(_host(base / manifest["revisions"][0]["id"]), manifest["queries"])
        route = _host(base / manifest["revisions"][0]["id"])
        rejected = {}
        for key, family, bindings, claim in (
            ("unreviewed_cluster", "checkout_latency", {"cluster": "prod_west", "namespace": "checkout"}, "checkout_latency"),
            ("wrong_family_claim", "rollout_digest", CONTEXT, "checkout_latency"),
            ("unknown_family", "nonexistent", CONTEXT, "checkout_latency"),
        ):
            try:
                route.assess(family, bindings, claim)
            except ValueError as exc:
                rejected[key] = str(exc)
            else:
                raise AssertionError(f"Unreviewed route {key} assessed a claim")
    return {
        "schema": "eal2-kubernetes-host-revisions-result/2",
        "status": "developmental_synthetic_offline",
        "source_sha256": source_hash,
        "input_sha256": hashes,
        "repetitions_per_revision": repetitions,
        "statuses_correct": sum(row["expected_status"] == row["observed_status"] for row in revision_results
                                if row["host_outcome"] == "issued"),
        "raw_statuses_correct": sum(row["expected_status"] == row["raw_assessment_status"]
                                    for row in revision_results),
        "issued_count": sum(row["host_outcome"] == "issued" for row in revision_results),
        "refused_count": sum(row["host_outcome"] == "refused_unresolved" for row in revision_results),
        "record_statuses_correct": sum(row["expected_record_status"] == row["observed_record_status"]
                                       for row in revision_results),
        "revision_count": len(revision_results),
        "revisions": revision_results,
        "retrieval": retrieval,
        "rejected_routes": rejected,
        "limitations": [
            "Records are synthetic local JSON, not authenticated Kubernetes observations.",
            "Reference statuses and relevance sets were specified by the fixture author without independent masked review.",
            "Wall-clock timings describe this local Python host and filesystem, not provider calls, MCP transport or a live cluster.",
            "Packet bytes are not model tokens; no model decision, retries or paid cost is measured.",
            "The selected claim is a provisional operating basis, conditional on unchanged traffic, deployment and resource conditions; supported does not establish actual future SLO compliance.",
            "The historical record-content claim is separately measured from the same assessment and is not exposed in the selected claim packet.",
            "Stale required evidence retains raw evaluator statuses for regression but yields no host packet or explanation under the complete-collection gate.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repetitions", type=int, default=5)
    parser.add_argument("--output", type=Path, help="Write deterministic metrics and local timing measurements")
    arguments = parser.parse_args()
    result = run(arguments.repetitions)
    rendered = json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    if arguments.output:
        arguments.output.parent.mkdir(parents=True, exist_ok=True)
        arguments.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")


if __name__ == "__main__":
    main()
