"""Execute a frozen v4 allocation as independently assigned B→C→D sequences.

An output directory is single-use. The agent gets only its own current source,
current brief and selected evidence presentation. The assessor, later briefs,
allocation and other arms remain host-only. Live Codex requires a frozen study,
an available provider credential and a closed bubblewrap filesystem view.

Example (one independently allocated block per CI job)::

    python experiments/architecture_extension_v4/study/runner.py \
      --manifest experiments/architecture_extension_v4/study/manifest.json \
      --block fulfilment-01 --output /tmp/earl-v4-fulfilment-01 --agent codex

The stub is a deterministic plumbing test, never an empirical observation.
"""

from __future__ import annotations

import argparse
import collections
import importlib
import json
import os
import random
import shutil
import subprocess
import sys
import tempfile
import time
import traceback
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from runner_capture import (codex_command, codex_preflight,
                            copy_source, digest, execute, json_write, redact, snapshot_candidate,
                            timestamp, tree_digest, tree_entries, usage_from_jsonl)


HERE = Path(__file__).resolve().parent
FIXTURES = HERE.parent / "systems"
DECISION_CASES = HERE / "decision_cases"
# Host-side EAL evaluation always uses this exact checkout, including local
# smoke runs where the project has not been installed as an editable package.
SRC = HERE.parents[2] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
STAGES = ("B", "C", "D")
ARMS = {"P0", "P1", "P2"}
SCHEMA = "architecture-extension-v4/manifest/1"
ALLOCATION_ALGORITHM = (
    "Python 3.12 random.Random(int(seed_hex,16)); for each system in manifest order, "
    "choose orientation with randrange(2): base [P0,P1,P2] if 0 else [P0,P2,P1]; "
    "form three cyclic left rotations; shuffle those three with the same RNG; "
    "map rotations to replicate 01..03 and positions 1..3 to clone IDs "
    "<system>-<replicate:02d>-K<position>. Each arm occurs once in each "
    "position per system."
)


class InfrastructureDeviation(RuntimeError):
    """A run may not continue as valid empirical evidence after this error."""


class ResourceGuardStop(RuntimeError):
    """Stop further paid calls while retaining every completed assignment."""


def _identifier(value: Any) -> bool:
    return (isinstance(value, str) and value and len(value) <= 80 and
            all(c.isalnum() or c in "-_" for c in value) and value not in {".", ".."})


def validate_manifest(manifest: dict[str, Any], fixtures: Path) -> list[dict[str, Any]]:
    if manifest.get("schema") != SCHEMA:
        raise ValueError("unexpected manifest schema")
    systems = manifest.get("systems")
    replicates = manifest.get("replicate_blocks_per_system")
    blocks = manifest.get("blocks")
    if not isinstance(systems, list) or len(systems) < 3 or len(set(systems)) != len(systems):
        raise ValueError("at least three distinct systems are required")
    if any(not _identifier(system) for system in systems):
        raise ValueError("unsafe system identifier")
    if type(replicates) is not int or replicates != 3:
        raise ValueError("position-balanced allocation requires exactly three blocks per system")
    if not isinstance(blocks, list) or len(blocks) != len(systems) * replicates:
        raise ValueError("incomplete system-by-replicate block allocation")
    if not isinstance(manifest.get("seed_hex"), str) or len(manifest["seed_hex"]) != 64:
        raise ValueError("64-character allocation seed required")
    try:
        bytes.fromhex(manifest["seed_hex"])
    except ValueError as exc:
        raise ValueError("allocation seed must be hexadecimal") from exc
    if manifest.get("allocation_algorithm") != ALLOCATION_ALGORITHM:
        raise ValueError("declared allocation algorithm differs from the registered algorithm")
    cap = manifest.get("wall_cap_seconds")
    if type(cap) is not int or not 1 <= cap <= 1800:
        raise ValueError("invalid per-episode wall cap")
    agent = manifest.get("agent")
    if not isinstance(agent, dict) or any(not isinstance(agent.get(k), str) or not agent[k]
                                          for k in ("model", "effort", "cli_version")):
        raise ValueError("exact model, effort and CLI version must be declared")
    schemas = manifest.get("evidence_schema")
    if not isinstance(schemas, dict) or set(schemas) != set(systems) or any(
            not isinstance(schemas[system], dict) or set(schemas[system]) != set(STAGES) or any(
                not isinstance(schemas[system][stage], dict) or not schemas[system][stage]
                for stage in STAGES) for system in systems):
        raise ValueError("each system/stage requires a nonempty evidence_schema entry")
    critical = manifest.get("critical_check_ids")
    if not isinstance(critical, dict) or set(critical) != set(systems) or any(
            not isinstance(critical[system], dict) or set(critical[system]) != set(STAGES) or any(
                not isinstance(critical[system][stage], list) or not critical[system][stage] or
                any(not isinstance(item, str) or not item for item in critical[system][stage]) or
                len(set(critical[system][stage])) != len(critical[system][stage])
                for stage in STAGES) for system in systems):
        raise ValueError("each system/stage requires distinct critical_check_ids")
    probes = manifest.get("decision_probes")
    if (not isinstance(probes, dict) or probes.get("case_ids") != ["clean", "defeated"] or
            probes.get("wall_cap_seconds") != 120):
        raise ValueError("two registered 120-second decision probes are required")
    ceiling = manifest.get("max_block_high_scenario_usd")
    try:
        amount = Decimal(ceiling) if isinstance(ceiling, str) else Decimal("NaN")
    except InvalidOperation as exc:
        raise ValueError("invalid block resource-guard ceiling") from exc
    if not amount.is_finite() or amount <= 0 or amount.as_tuple().exponent < -2:
        raise ValueError("block resource-guard ceiling must be positive USD cents")
    seen: set[str] = set()
    counts: collections.Counter[str] = collections.Counter()
    for block in blocks:
        if not isinstance(block, dict) or not _identifier(block.get("id")) or block["id"] in seen:
            raise ValueError("duplicate or unsafe block identifier")
        seen.add(block["id"])
        system = block.get("system")
        if system not in systems:
            raise ValueError(f"unknown system in block {block['id']}")
        counts[system] += 1
        allocation = block.get("assignments")
        if not isinstance(allocation, list) or len(allocation) != 3:
            raise ValueError(f"block {block['id']} must allocate exactly three clones")
        if {assignment.get("arm") for assignment in allocation if isinstance(assignment, dict)} != ARMS:
            raise ValueError(f"block {block['id']} must allocate one of each arm")
        clones = [assignment.get("clone") for assignment in allocation]
        if any(not _identifier(clone) for clone in clones) or len(set(clones)) != 3:
            raise ValueError(f"unsafe or duplicate clone identifier in {block['id']}")
    if any(counts[system] != replicates for system in systems):
        raise ValueError("system replication counts differ from manifest")
    allocation = random.Random(int(manifest["seed_hex"], 16))
    expected_blocks: list[dict[str, Any]] = []
    for system in systems:
        base = ["P0", "P1", "P2"] if allocation.randrange(2) == 0 else ["P0", "P2", "P1"]
        orders = [base[position:] + base[:position] for position in range(3)]
        allocation.shuffle(orders)
        for replicate, arms in enumerate(orders, 1):
            block_id = f"{system}-{replicate:02d}"
            expected_blocks.append({"id": block_id, "system": system,
                                    "assignments": [{"clone": f"{block_id}-K{position}",
                                                     "arm": arm}
                                                    for position, arm in enumerate(arms, 1)]})
    if blocks != expected_blocks:
        raise ValueError("stored assignment differs from the declared seeded permutation")
    for system in systems:
        base = fixtures / system
        if base.is_symlink() or not (base / "source").is_dir() or not (base / "host/assess.py").is_file():
            raise ValueError(f"missing fixture source or host assessor for {system}")
        for stage in STAGES:
            brief = base / "features" / f"{stage}.md"
            if not brief.is_file() or brief.is_symlink():
                raise ValueError(f"missing current-stage brief for {system}-{stage}")
        for row in tree_entries(base / "source"):
            if "host" in Path(row["path"]).parts or "features" in Path(row["path"]).parts or \
               Path(row["path"]).name in {"assess.py", "freeze.py"}:
                raise ValueError(f"host-only material in agent source: {system}/{row['path']}")
    return blocks


def _packet(source: Path, system: str, stage: str, arm: str,
            evidence_schema: dict[str, Any]) -> tuple[str | None, dict[str, Any], float]:
    if arm == "P0":
        return None, {"status": "no_packet", "selected": None}, 0.0
    packets = importlib.import_module("packets")
    if not callable(getattr(packets, "generate", None)):
        raise InfrastructureDeviation("packets.generate is unavailable")
    selected_start = time.monotonic()
    selected = packets.generate(source, system, stage, arm, evidence_schema)
    acquisition = time.monotonic() - selected_start
    alternative_arm = "P1" if arm == "P2" else "P2"
    parity_start = time.monotonic()
    alternative = packets.generate(source, system, stage, alternative_arm, evidence_schema)
    parity_seconds = time.monotonic() - parity_start
    required = ("facts", "guidance", "status", "selected_action", "shared_material_digest",
                "source_tree_sha256", "packet_text")
    if any(not isinstance(obj, dict) or any(key not in obj for key in required)
           for obj in (selected, alternative)):
        raise InfrastructureDeviation("packet generator omitted a required field")
    shared = ("facts", "guidance", "status", "selected_action", "shared_material_digest",
              "source_tree_sha256")
    if any(selected[key] != alternative[key] for key in shared):
        raise InfrastructureDeviation("P1/P2 source-derived facts, status, action or guidance differ")
    p1 = selected if arm == "P1" else alternative
    p2 = selected if arm == "P2" else alternative
    if "formal" in p1 or not isinstance(p2.get("formal"), dict) or not p2["formal"]:
        raise InfrastructureDeviation("formal argument must be present only in P2")
    if (not isinstance(selected["packet_text"], str) or not selected["packet_text"] or
            selected["packet_text"] == alternative["packet_text"] or
            not isinstance(selected["shared_material_digest"], str) or
            not selected["shared_material_digest"]):
        raise InfrastructureDeviation("packet presentation or shared-material digest invalid")
    metadata = {"status": "matched_shared_material", "selected_arm": arm,
                "shared_material_digest": selected["shared_material_digest"],
                "source_tree_sha256": selected["source_tree_sha256"],
                "selected": selected, "counterfactual_arm": alternative_arm,
                "counterfactual": alternative, "parity_check_seconds": parity_seconds,
                "selected_acquisition_seconds": acquisition}
    return selected["packet_text"], metadata, acquisition


def _prompt(brief: str, packet_text: str | None) -> str:
    if packet_text is None:
        return brief.rstrip() + "\n"
    return brief.rstrip() + "\n\n" + packet_text.rstrip() + "\n"


def _assess(fixture: Path, stage: str, source: Path, episode: Path,
            critical_ids: list[str],
            timeout: int = 180) -> tuple[dict[str, Any], float]:
    result_path = episode / "assessment.json"
    stdout = episode / "assessor.stdout"
    stderr = episode / "assessor.stderr"
    began = time.monotonic()
    with stdout.open("wb") as out, stderr.open("wb") as err:
        try:
            result = subprocess.run([sys.executable, str(fixture / "host/assess.py"),
                                     "--source", str(source), "--stage", stage,
                                     "--output", str(result_path)],
                                    cwd=episode, stdout=out, stderr=err, timeout=timeout,
                                    check=False, env={"PATH": os.environ.get("PATH", "/usr/bin:/bin"),
                                                      "HOME": str(episode)})
        except subprocess.TimeoutExpired as exc:
            raise InfrastructureDeviation("independent assessor exceeded its host timeout") from exc
    duration = time.monotonic() - began
    if result.returncode not in (0, 2) or not result_path.is_file():
        raise InfrastructureDeviation(f"assessor failed (exit {result.returncode}); see assessor.stderr")
    try:
        data = json.loads(result_path.read_text(encoding="utf-8"))
    except (ValueError, UnicodeError) as exc:
        raise InfrastructureDeviation("assessor produced invalid JSON") from exc
    if result.returncode == 2 and data.get("invalid_kind") == "assessor_error":
        raise InfrastructureDeviation("independent assessor reported a host error")
    if result.returncode == 2 and data.get("invalid_kind") != "candidate_source":
        raise InfrastructureDeviation("assessor returned invalid without a classified candidate error")
    findings = data.get("findings")
    checks = data.get("checks")
    if isinstance(checks, list) and checks:
        if any(not isinstance(check, dict) or not isinstance(check.get("id"), str) or
               not check["id"] or len(check["id"]) > 120 for check in checks):
            raise InfrastructureDeviation("malformed assessor check identity")
        check_map = {check["id"]: {key: value for key, value in check.items() if key != "id"}
                     for check in checks}
        if len(check_map) != len(checks):
            raise InfrastructureDeviation("duplicate assessor check identity")
        if findings is None:
            findings = check_map
        elif findings != check_map:
            raise InfrastructureDeviation("assessor checks and findings disagree")
    if result.returncode == 2 and not findings:
        findings = {"candidate.source": {"status": "invalid", "detail": data.get("error", "candidate invalid")}}
    if not isinstance(findings, dict) or not findings or any(
            not isinstance(row, dict) or row.get("status") not in {"pass", "fail", "invalid"}
            for row in findings.values()):
        raise InfrastructureDeviation("assessor findings are absent or malformed")
    missing_critical = sorted(set(critical_ids) - set(findings))
    if missing_critical and "candidate.import" not in findings and \
            data.get("invalid_kind") != "candidate_source":
        raise InfrastructureDeviation("assessor omitted frozen critical checks: " +
                                      ", ".join(missing_critical))
    counts = {status: sum(row["status"] == status for row in findings.values())
              for status in ("pass", "fail", "invalid")}
    if result.returncode == 0 and any(data.get(label) is not None and data[label] != counts[status]
           for label, status in (("passed", "pass"), ("failed", "fail"), ("invalid", "invalid"))):
        raise InfrastructureDeviation("assessor count disagrees with findings")
    if result.returncode == 2 and data.get("valid") is not False:
        raise InfrastructureDeviation("assessor exit and candidate-validity flag disagree")
    return {"findings": findings, "counts": counts,
            "missing_critical_due_to_candidate_import": missing_critical,
            "complete": counts["fail"] == 0 and counts["invalid"] == 0,
            "raw": data, "sha256": digest(result_path)}, duration


def _cli_identity(manifest: dict[str, Any]) -> dict[str, str]:
    executable = shutil.which("codex")
    if not executable:
        raise InfrastructureDeviation("Codex CLI is not installed")
    binary = Path(executable).resolve()
    result = subprocess.run([executable, "--version"], capture_output=True, text=True,
                            timeout=15, check=False)
    if result.returncode:
        raise InfrastructureDeviation("Codex CLI version check failed")
    version = result.stdout.strip()
    if manifest["agent"]["cli_version"] not in version:
        raise InfrastructureDeviation(f"Codex CLI {version!r} differs from declared version")
    return {"cli_version": version, "binary_sha256": digest(binary)}


def _environment(agent: str, home: Path) -> dict[str, str]:
    env = {"PATH": os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin"),
           "HOME": str(home), "LANG": os.environ.get("LANG", "C.UTF-8")}
    if agent == "codex":
        key = os.environ.get("CODEX_API_KEY") or os.environ.get("OPENAI_API_KEY")
        if not key:
            raise InfrastructureDeviation("Codex credential is unavailable")
        env["CODEX_API_KEY"] = key
        if os.environ.get("HTTPS_PROXY"):
            env["HTTPS_PROXY"] = os.environ["HTTPS_PROXY"]
        if os.environ.get("HTTP_PROXY"):
            env["HTTP_PROXY"] = os.environ["HTTP_PROXY"]
        if os.environ.get("NO_PROXY"):
            env["NO_PROXY"] = os.environ["NO_PROXY"]
    return env


def _discard_agent_worktrees(output: Path) -> None:
    """An uploaded result contains safe snapshots, never a raw agent mount."""
    direct = output / "agent-visible"
    candidates = [direct] if direct.is_dir() or direct.is_symlink() else list(
        output.glob("blocks/*/*/*/agent-visible"))
    for path in candidates:
        if path.is_symlink():
            path.unlink()
        elif path.is_dir():
            shutil.rmtree(path)


def _episode(block: dict[str, Any], assignment: dict[str, str], stage: str,
             source: Path, fixtures: Path, result_root: Path,
             manifest: dict[str, Any], agent: str, stub_command: list[str] | None,
             cli: dict[str, str] | None) -> tuple[dict[str, Any], Path]:
    system, arm, clone = block["system"], assignment["arm"], assignment["clone"]
    fixture = fixtures / system
    episode = result_root / "blocks" / block["id"] / clone / stage
    episode.mkdir(parents=True, exist_ok=False)
    trial = episode / "agent-visible"
    input_digest, inputs = copy_source(source, trial)
    brief = (fixture / "features" / f"{stage}.md").read_text(encoding="utf-8")
    packet_text, packet_meta, acquisition = _packet(
        source, system, stage, arm, manifest["evidence_schema"][system][stage])
    if arm != "P0" and packet_meta["source_tree_sha256"] != input_digest:
        raise InfrastructureDeviation("packet observation is not bound to the copied coding source")
    json_write(episode / "packet-host.json", packet_meta)
    (trial / "FEATURE.md").write_text(_prompt(brief, packet_text), encoding="utf-8")
    (trial / "AGENTS.md").write_text(
        "Implement the current FEATURE.md against this source. Preserve existing behaviour. "
        "Keep code and visible tests in this directory.\n", encoding="utf-8")
    if any(path.name in {"assess.py", "freeze.py"} or "host" in path.parts or "features" in path.parts
           for path in trial.rglob("*")):
        raise InfrastructureDeviation("agent worktree contains host-only material")
    json_write(episode / "input.json", {"source_tree_sha256": input_digest, "files": inputs,
                                        "brief_sha256": digest(fixture / "features" / f"{stage}.md"),
                                        "visible_prompt_sha256": digest(trial / "FEATURE.md"),
                                        "agent": agent, "smoke_only": agent == "stub"})
    trace = episode / "agent.jsonl"
    stderr = episode / "agent.stderr"
    with tempfile.TemporaryDirectory(prefix="earl-v4-agent-home-") as private_home:
        home = Path(private_home)
        env = _environment(agent, home)
        env["EARL_STAGE"] = stage
        env["EARL_SYSTEM"] = system
        if agent == "codex":
            codex_preflight(trial, home)
            command = codex_command(trial, home, manifest["agent"]["model"], manifest["agent"]["effort"])
        else:
            command = stub_command or [sys.executable, "-c", "import os; from pathlib import Path; "
                                       "Path('stub-'+os.environ['EARL_STAGE']+'.txt').write_text('smoke')"]
        invocation = execute(command, cwd=trial, env=env, timeout=manifest["wall_cap_seconds"],
                             stdout=trace, stderr=stderr)
    # Redact before copying the source to the host assessor's path. A source
    # credential exposure invalidates this block, even though the copy is safe.
    retained_files = [trace, stderr] + [p for p in trial.rglob("*") if not p.is_symlink()
                                        and p.is_file() and
                                        not any(parent.is_symlink() for parent in p.parents if parent != trial)]
    credential_exposed, raw_sha = redact(retained_files, [env.get("CODEX_API_KEY", "")])
    invocation.update({"schema": "architecture-extension-v4/invocation/1",
                       "system": system, "block": block["id"], "clone": clone,
                       "arm": arm, "stage": stage, "agent_class": agent,
                       "smoke_only": agent == "stub", "model": manifest["agent"]["model"] if agent == "codex" else None,
                       "effort": manifest["agent"]["effort"] if agent == "codex" else None,
                       "cli": cli, "trace_sha256_before_redaction": raw_sha[str(trace)],
                       "exact_credential_redacted": credential_exposed})
    json_write(episode / "invocation.json", invocation)
    if credential_exposed:
        raise InfrastructureDeviation("provider credential appeared in retained output")
    shutil.copyfile(trial / "FEATURE.md", episode / "visible-prompt.md")
    shutil.copyfile(trial / "AGENTS.md", episode / "visible-instructions.md")
    try:
        usage = usage_from_jsonl(trace) if agent == "codex" else {
            "status": "synthetic_stub", "totals": None, "accounting": "not a model trial"}
    except (ValueError, UnicodeError) as exc:
        raise InfrastructureDeviation("Codex JSONL usage trace malformed") from exc
    pricing = importlib.import_module("price")
    price = pricing.price_episode({
        "schema": "architecture-v4-usage/1", "billing_channel": "unknown_codex_channel",
        "model": manifest["agent"]["model"] if agent == "codex" else "synthetic_stub",
        "requests": [], "request_trace_complete": False})
    rate_scenario = pricing.scenario_from_cli_turns(usage)
    json_write(episode / "resource-use.json", {"usage": usage, "provider_bill": None,
                                               "conditional_scenario": rate_scenario,
                                               "agent_trace_sha256": digest(trace),
                                               "agent_trace_bytes": trace.stat().st_size})
    json_write(episode / "price.json", {"exact": price, "conditional_scenario": rate_scenario})
    snapshot = episode / "source"
    output_digest, outputs, rejected = snapshot_candidate(trial, snapshot)
    _discard_agent_worktrees(episode)
    json_write(episode / "output.json", {"source_tree_sha256": output_digest,
                                         "files": outputs, "rejected_candidate_entries": rejected})
    assessment, assessment_seconds = _assess(
        fixture, stage, snapshot, episode, manifest["critical_check_ids"][system][stage])
    complete = (assessment["complete"] and not rejected and invocation["exit_code"] == 0
                and not invocation["timed_out"])
    actual = invocation["actual_wall_seconds"]
    score = acquisition + (min(actual, manifest["wall_cap_seconds"]) if complete
                           else manifest["wall_cap_seconds"])
    row = {"schema": "architecture-extension-v4/episode/1",
           "system": system, "block": block["id"], "clone": clone,
           "arm": arm, "stage": stage, "agent": agent, "smoke_only": agent == "stub",
           "input_source_tree_sha256": input_digest, "output_source_tree_sha256": output_digest,
           "packet_shared_material_digest": packet_meta.get("shared_material_digest"),
           "packet_acquisition_seconds": acquisition,
           "parity_audit_seconds_excluded_from_treatment": packet_meta.get("parity_check_seconds", 0),
           "actual_agent_wall_seconds": actual,
           "assessor_host_seconds_excluded_from_treatment": assessment_seconds,
           "failure_penalised_seconds": score,
           "complete": complete, "assessor_passed": assessment["counts"]["pass"],
           "assessor_failed": assessment["counts"]["fail"],
           "assessor_invalid": assessment["counts"]["invalid"],
           "candidate_invalid_entries": rejected,
           "critical_check_ids": manifest["critical_check_ids"][system][stage],
           "critical_checks_passed": all(
               assessment["findings"].get(name, {}).get("status") == "pass"
               for name in manifest["critical_check_ids"][system][stage]),
           "critical_checks_unrun_due_to_candidate_import":
               assessment["missing_critical_due_to_candidate_import"],
           "assessment_sha256": assessment["sha256"],
           "agent_exit_code": invocation["exit_code"], "agent_timed_out": invocation["timed_out"],
           "resource_use": usage, "price": price,
           "conditional_list_price_scenario": rate_scenario}
    json_write(episode / "episode.json", row)
    return row, snapshot


def _final_response_text(trace: Path, agent: str) -> str:
    raw = trace.read_text(encoding="utf-8")
    if agent == "stub":
        return raw.strip()
    messages: list[str] = []
    for line in raw.splitlines():
        if not line.strip():
            continue
        event = json.loads(line)
        item = event.get("item") if isinstance(event, dict) else None
        if isinstance(item, dict) and item.get("type") == "agent_message" and \
                isinstance(item.get("text"), str):
            messages.append(item["text"])
    return messages[-1] if messages else ""


def _decision_probe(block: dict[str, Any], assignment: dict[str, str], case_id: str,
                    decision_cases: Path, output: Path, manifest: dict[str, Any],
                    agent: str, stub_command: list[str] | None,
                    cli: dict[str, str] | None) -> dict[str, Any]:
    """A fresh, post-D, read-only decision; its source never enters a lineage."""
    system, arm, clone = block["system"], assignment["arm"], assignment["clone"]
    source = decision_cases / system / case_id / "source"
    if not source.is_dir():
        raise InfrastructureDeviation(f"frozen decision case source missing: {system}/{case_id}")
    probe = importlib.import_module("decision_probe")
    if not callable(getattr(probe, "generate", None)) or not callable(getattr(probe, "score", None)):
        raise InfrastructureDeviation("decision-probe generator or oracle unavailable")
    episode = output / "blocks" / block["id"] / clone / f"decision-{case_id}"
    episode.mkdir(parents=True, exist_ok=False)
    trial = episode / "agent-visible"
    source_digest, entries = copy_source(source, trial)
    definitions_path = decision_cases / "cases.json"
    if not definitions_path.is_file():
        raise InfrastructureDeviation("registered decision-case manifest missing")
    definitions = json.loads(definitions_path.read_text(encoding="utf-8"))
    try:
        config = definitions["systems"][system][case_id]["evidence_schema"]
    except (KeyError, TypeError) as exc:
        raise InfrastructureDeviation("decision case has no frozen evidence schema") from exc
    if not isinstance(config, dict):
        raise InfrastructureDeviation("decision evidence schema malformed")
    start = time.monotonic()
    selected = probe.generate(source, system, case_id, arm, config)
    acquisition = time.monotonic() - start
    parity_seconds = 0.0
    if arm in ("P1", "P2"):
        other_arm = "P1" if arm == "P2" else "P2"
        start = time.monotonic()
        alternative = probe.generate(source, system, case_id, other_arm, config)
        parity_seconds = time.monotonic() - start
        shared = ("facts", "guidance", "status", "selected_action", "shared_material_digest",
                  "source_tree_sha256", "expected_action", "allowed_actions")
        if not isinstance(selected, dict) or not isinstance(alternative, dict) or any(
                selected.get(key) != alternative.get(key) for key in shared):
            raise InfrastructureDeviation("decision P1/P2 content parity failed")
        p1, p2 = (selected, alternative) if arm == "P1" else (alternative, selected)
        if "formal" in p1 or not isinstance(p2.get("formal"), dict):
            raise InfrastructureDeviation("decision formal presentation must occur only in P2")
        if selected.get("prompt_text") == alternative.get("prompt_text"):
            raise InfrastructureDeviation("decision presentation contrast is absent")
    if (not isinstance(selected, dict) or
            selected.get("source_tree_sha256") != source_digest or
            not isinstance(selected.get("prompt_text"), str) or not selected["prompt_text"] or
            selected.get("expected_action") not in selected.get("allowed_actions", ())):
        raise InfrastructureDeviation("decision case/source/action contract invalid")
    prompt = selected["prompt_text"]
    (trial / "FEATURE.md").write_text(prompt.rstrip() + "\n", encoding="utf-8")
    (trial / "AGENTS.md").write_text(
        "Read the current decision case. Do not change source files. "
        "Return only the requested JSON action.\n", encoding="utf-8")
    json_write(episode / "packet-host.json", {"selected": selected,
                                              "shared_material_digest": selected.get("shared_material_digest"),
                                              "selected_acquisition_seconds": acquisition,
                                              "parity_check_seconds": parity_seconds})
    json_write(episode / "input.json", {"case_source_tree_sha256": source_digest,
                                        "files": entries, "visible_prompt_sha256": digest(trial / "FEATURE.md"),
                                        "smoke_only": agent == "stub"})
    trace, stderr = episode / "agent.jsonl", episode / "agent.stderr"
    with tempfile.TemporaryDirectory(prefix="earl-v4-decision-home-") as private_home:
        home = Path(private_home)
        env = _environment(agent, home)
        env.update({"EARL_TASK": "decision", "EARL_STAGE": "D", "EARL_SYSTEM": system})
        if agent == "codex":
            codex_preflight(trial, home, read_only_trial=True)
            command = codex_command(trial, home, manifest["agent"]["model"],
                                    manifest["agent"]["effort"], read_only_trial=True)
        else:
            command = stub_command or [sys.executable, "-c",
                                       'print(\'{"action":"inspect_existing"}\')']
        invocation = execute(command, cwd=trial, env=env,
                             timeout=manifest["decision_probes"]["wall_cap_seconds"],
                             stdout=trace, stderr=stderr)
    retained = [trace, stderr] + [p for p in trial.rglob("*") if not p.is_symlink() and p.is_file()
                                  and not any(parent.is_symlink() for parent in p.parents if parent != trial)]
    exposed, sha = redact(retained, [env.get("CODEX_API_KEY", "")])
    invocation.update({"schema": "architecture-extension-v4/decision-invocation/1",
                       "system": system, "block": block["id"], "clone": clone,
                       "arm": arm, "case_id": case_id, "agent_class": agent,
                       "cli": cli, "smoke_only": agent == "stub",
                       "trace_sha256_before_redaction": sha[str(trace)],
                       "exact_credential_redacted": exposed})
    json_write(episode / "invocation.json", invocation)
    if exposed:
        raise InfrastructureDeviation("provider credential appeared in decision output")
    shutil.copyfile(trial / "FEATURE.md", episode / "visible-prompt.md")
    shutil.copyfile(trial / "AGENTS.md", episode / "visible-instructions.md")
    if tree_digest(tree_entries(trial, omit_agent_inputs=True)) != source_digest:
        raise InfrastructureDeviation("decision agent modified the read-only case source")
    _discard_agent_worktrees(episode)
    try:
        usage = usage_from_jsonl(trace) if agent == "codex" else {
            "status": "synthetic_stub", "totals": None, "accounting": "not a model trial"}
        response = _final_response_text(trace, agent)
        scored = probe.score(response, selected["expected_action"], selected["allowed_actions"])
    except (ValueError, UnicodeError) as exc:
        raise InfrastructureDeviation("decision trace or scoring contract malformed") from exc
    if not isinstance(scored, (bool, dict)):
        raise InfrastructureDeviation("decision scorer must return bool or object")
    pricing = importlib.import_module("price")
    price = pricing.price_episode({
        "schema": "architecture-v4-usage/1", "billing_channel": "unknown_codex_channel",
        "model": manifest["agent"]["model"] if agent == "codex" else "synthetic_stub",
        "requests": [], "request_trace_complete": False})
    rate_scenario = pricing.scenario_from_cli_turns(usage)
    json_write(episode / "resource-use.json", {"usage": usage, "price": price,
                                               "conditional_scenario": rate_scenario,
                                               "agent_trace_sha256": digest(trace),
                                               "agent_trace_bytes": trace.stat().st_size})
    successful = invocation["exit_code"] == 0 and not invocation["timed_out"]
    row = {"schema": "architecture-extension-v4/decision-probe/1",
           "system": system, "block": block["id"], "clone": clone,
           "arm": arm, "case_id": case_id, "agent": agent,
           "smoke_only": agent == "stub", "source_tree_sha256": source_digest,
           "packet_shared_material_digest": selected.get("shared_material_digest"),
           "expected_action": selected["expected_action"], "allowed_actions": selected["allowed_actions"],
           "score": scored, "agent_completed": successful,
           "actual_agent_wall_seconds": invocation["actual_wall_seconds"],
           "packet_acquisition_seconds": acquisition,
           "parity_audit_seconds_excluded_from_treatment": parity_seconds,
           "agent_exit_code": invocation["exit_code"], "agent_timed_out": invocation["timed_out"],
           "resource_use": usage, "price": price,
           "conditional_list_price_scenario": rate_scenario}
    json_write(episode / "decision.json", row)
    return row


def _account_budget(row: dict[str, Any], total: Decimal, ceiling: Decimal) -> Decimal:
    scenario = row["conditional_list_price_scenario"]
    if scenario.get("status") != "conditional_scenario" or scenario.get("high_usd") is None:
        raise ResourceGuardStop("reported token classes cannot be priced under the declared scenario")
    high = Decimal(scenario["high_usd"])
    if not high.is_finite() or high < 0:
        raise InfrastructureDeviation("invalid conditional price scenario")
    updated = total + high
    if updated > ceiling:
        raise ResourceGuardStop(f"block conditional high scenario {updated} USD exceeds {ceiling} USD")
    return updated


def run(manifest_path: Path, fixtures: Path, output: Path, agent: str,
        block_id: str | None, stub_command: list[str] | None,
        decision_cases: Path | None = None) -> dict[str, Any]:
    manifest_path, fixtures, output = manifest_path.resolve(), fixtures.resolve(), output.resolve()
    decision_cases = (decision_cases or DECISION_CASES).resolve()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    blocks = validate_manifest(manifest, fixtures)
    if block_id is not None:
        blocks = [block for block in blocks if block["id"] == block_id]
        if not blocks:
            raise ValueError(f"unknown allocated block: {block_id}")
    if output.exists():
        raise FileExistsError(f"single-use output directory already exists: {output}")
    if agent == "codex":
        if manifest_path != (HERE / "manifest.json").resolve() or fixtures != FIXTURES.resolve():
            raise InfrastructureDeviation("live experiment requires the frozen study manifest and fixtures")
        if decision_cases != DECISION_CASES.resolve():
            raise InfrastructureDeviation("live experiment requires frozen decision cases")
        freeze = subprocess.run([sys.executable, str(HERE / "freeze.py"), "verify"],
                                cwd=HERE.parents[2], capture_output=True, text=True,
                                timeout=40, check=False)
        if freeze.returncode:
            raise InfrastructureDeviation("frozen study verification failed: " + freeze.stderr[-500:])
        if not (os.environ.get("CODEX_API_KEY") or os.environ.get("OPENAI_API_KEY")):
            raise InfrastructureDeviation("no Codex provider credential")
        cli = _cli_identity(manifest)
    else:
        cli = None
    output.mkdir(parents=True)
    shutil.copyfile(manifest_path, output / "manifest.json")
    summary: dict[str, Any] = {
        "schema": "architecture-extension-v4/run/1", "started_utc": timestamp(),
        "status": "running", "agent": agent, "smoke_only": agent == "stub",
        "manifest_sha256": digest(manifest_path), "selected_blocks": [block["id"] for block in blocks],
        "episodes": [], "decision_probes": [], "infrastructure_deviation": None,
        "resource_guard": {"max_block_high_scenario_usd": manifest["max_block_high_scenario_usd"],
                           "enforced": agent == "codex", "block_high_scenario_usd": {},
                           "stop_reason": None}}
    json_write(output / "summary.json", summary)
    try:
        for block in blocks:
            block_scenario = Decimal("0")
            for assignment in block["assignments"]:
                source = fixtures / block["system"] / "source"
                for stage in STAGES:
                    row, source = _episode(block, assignment, stage, source, fixtures,
                                           output, manifest, agent, stub_command, cli)
                    summary["episodes"].append(row)
                    json_write(output / "summary.json", summary)
                    if agent == "codex":
                        block_scenario = _account_budget(
                            row, block_scenario, Decimal(manifest["max_block_high_scenario_usd"]))
                        summary["resource_guard"]["block_high_scenario_usd"][block["id"]] = str(block_scenario)
                        json_write(output / "summary.json", summary)
                for case_id in manifest["decision_probes"]["case_ids"]:
                    row = _decision_probe(block, assignment, case_id, decision_cases, output,
                                          manifest, agent, stub_command, cli)
                    summary["decision_probes"].append(row)
                    json_write(output / "summary.json", summary)
                    if agent == "codex":
                        block_scenario = _account_budget(
                            row, block_scenario, Decimal(manifest["max_block_high_scenario_usd"]))
                        summary["resource_guard"]["block_high_scenario_usd"][block["id"]] = str(block_scenario)
                        json_write(output / "summary.json", summary)
    except ResourceGuardStop as exc:
        _discard_agent_worktrees(output)
        summary["status"] = "stopped_resource_guard"
        summary["resource_guard"]["stop_reason"] = str(exc)
        summary["ended_utc"] = timestamp()
        json_write(output / "summary.json", summary)
        raise
    except BaseException as exc:
        _discard_agent_worktrees(output)
        summary["status"] = "stopped_infrastructure_deviation"
        summary["infrastructure_deviation"] = {"type": type(exc).__name__, "detail": str(exc),
                                                "traceback": traceback.format_exc()}
        summary["ended_utc"] = timestamp()
        json_write(output / "summary.json", summary)
        raise
    summary["status"] = "completed_smoke_only" if agent == "stub" else "complete_acquisition"
    summary["ended_utc"] = timestamp()
    json_write(output / "summary.json", summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=HERE / "manifest.json")
    parser.add_argument("--fixtures", type=Path, default=FIXTURES)
    parser.add_argument("--decision-cases", type=Path, default=DECISION_CASES)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--block", help="one preallocated block for a CI job")
    parser.add_argument("--agent", choices=("stub", "codex"), required=True)
    parser.add_argument("--stub-command-json", help="JSON array of command arguments; only with --agent stub")
    args = parser.parse_args()
    if args.stub_command_json and args.agent != "stub":
        parser.error("custom stub command cannot be used in a model trial")
    command = json.loads(args.stub_command_json) if args.stub_command_json else None
    if command is not None and (not isinstance(command, list) or not command or
                                any(not isinstance(part, str) or not part for part in command)):
        parser.error("stub command must be a nonempty JSON array of strings")
    result = run(args.manifest, args.fixtures, args.output, args.agent, args.block, command,
                 args.decision_cases)
    print(json.dumps({"status": result["status"], "episodes": len(result["episodes"]),
                      "decision_probes": len(result["decision_probes"]),
                      "output": str(args.output.resolve())}, sort_keys=True))


if __name__ == "__main__":
    main()
