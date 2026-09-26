"""Run an operator-selected evaluator against snapshotted source and frozen cases."""
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

from .protocol import STAGES, canonical, digest, identifier, load_frozen, read_json
from .recording import MAX_ARTIFACT_BYTES, _artefact_digest


def replay(run: Path, submission_id: str, operator_id: str,
           runner_version: str, runner: Path, timeout_seconds: float = 120) -> dict:
    plan, assignments = load_frozen(run)
    if (not identifier(operator_id) or not isinstance(runner_version, str)
            or not runner_version.strip() or not 0 < timeout_seconds <= 3600
            or not runner.is_file() or runner.is_symlink()
            or runner.stat().st_size > MAX_ARTIFACT_BYTES):
        raise ValueError("Specify an operator, ordinary runner script and finite timeout")
    runner_digest = digest(runner.read_bytes())
    command = [sys.executable, str(runner.resolve())]
    match = next(((assignment, stage) for assignment in assignments for stage in STAGES
                  if submission_id == f"{assignment['id']}-{stage}"), None)
    if match is None:
        raise ValueError("Unknown submission")
    assignment, stage = match
    if runner_digest != plan["runner_sha256"][assignment["arm"]]:
        raise ValueError("Runner script differs from the frozen arm contract")
    if operator_id == assignment["participant_id"]:
        raise ValueError("An author cannot replay their own submission")
    submitted = run / "submissions" / submission_id
    if not (submitted / "record.json").exists():
        raise ValueError("Cannot replay missing work")
    record = read_json(submitted / "record.json")
    source = submitted / "artefact"
    if (record["artefact_sha256"] is None or not source.is_dir()
            or _artefact_digest(source) != record["artefact_sha256"]):
        raise ValueError("Submitted source is absent or changed")
    task = next(task for task in plan["tasks"] if task["id"] == assignment["task_id"])
    case_bundle = {"schema": "eal-authoring-cases/1", "task_id": task["id"],
                   "stage": stage, "target_claims": task["target_claims"][stage],
                   "cases": task["inputs"][stage]}
    destination = run / "replays" / submission_id
    destination.mkdir(parents=True, exist_ok=False)
    case_bytes = canonical(case_bundle)
    (destination / "cases.json").write_bytes(case_bytes)
    environment = {key: os.environ[key] for key in ("PATH", "LANG", "LC_ALL", "TZ")
                   if key in os.environ}
    environment["PYTHONPATH"] = os.pathsep.join(filter(None, (str(Path.cwd().resolve()),
                                                              os.environ.get("PYTHONPATH", ""))))
    environment.update({
        "PYTHONDONTWRITEBYTECODE": "1",
        "EAL_STUDY_SOURCE": str(source.resolve()),
        "EAL_STUDY_CASES": str((destination / "cases.json").resolve()),
        "EAL_STUDY_TASK": task["id"], "EAL_STUDY_STAGE": stage,
        "EAL_STUDY_ARM": assignment["arm"],
    })
    started = time.monotonic()
    returncode = None
    error = None
    with tempfile.TemporaryFile() as stdout, tempfile.TemporaryFile() as stderr:
        try:
            completed = subprocess.run(command, cwd=Path.cwd(), env=environment,
                                       stdout=stdout, stderr=stderr, timeout=timeout_seconds,
                                       check=False)
            returncode = completed.returncode
        except subprocess.TimeoutExpired:
            error = "timeout"
        except OSError as exc:
            error = f"launcher_error:{type(exc).__name__}"
        elapsed = time.monotonic() - started
        if stdout.tell() > MAX_ARTIFACT_BYTES or stderr.tell() > MAX_ARTIFACT_BYTES:
            error = "output_limit"
        stdout.seek(0)
        stderr.seek(0)
        output = stdout.read(MAX_ARTIFACT_BYTES)
        diagnostic = stderr.read(MAX_ARTIFACT_BYTES)
    if _artefact_digest(source) != record["artefact_sha256"]:
        error = "source_changed_during_replay"
    (destination / "results.json").write_bytes(output)
    (destination / "stderr.txt").write_bytes(diagnostic)
    provenance = {
        "schema": "eal-authoring-replay/1", "submission_id": submission_id,
        "operator_id": operator_id, "runner_version": runner_version,
        "runner_file": str(runner.resolve()), "runner_sha256": runner_digest,
        "python_version": sys.version.split()[0],
        "command": command, "working_directory": str(Path.cwd().resolve()),
        "source_sha256": record["artefact_sha256"],
        "cases_sha256": digest(case_bytes), "stdout_sha256": digest(output),
        "stderr_sha256": digest(diagnostic), "returncode": returncode,
        "error": error, "elapsed_seconds": elapsed,
    }
    (destination / "record.json").write_bytes(canonical(provenance))
    return provenance
