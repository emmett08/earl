"""Retain actual submissions and independent reviews without overwriting attempts."""
from __future__ import annotations

from pathlib import Path
import shutil

from .protocol import STAGES, canonical, digest, identifier, load_frozen, read_json, seconds


MAX_ARTIFACT_BYTES = 16 * 1024 * 1024


def _artefact_digest(path: Path) -> str:
    entries = [(file.relative_to(path).as_posix(), digest(file.read_bytes()))
               for file in sorted(path.rglob("*")) if file.is_file()]
    return digest(canonical(entries))


def _snapshot(source: Path, target: Path) -> str:
    """Copy one file or tree, hashing relative names and contents deterministically."""
    if source.is_symlink() or not source.exists():
        raise ValueError("Artefact must be an existing ordinary file or directory")
    paths = [source] if source.is_file() else sorted(source.rglob("*"))
    files = [path for path in paths if path.is_file()]
    if not files or any(path.is_symlink() for path in paths):
        raise ValueError("Artefact must contain files and no symlinks")
    if any(not path.is_file() and not path.is_dir() for path in paths):
        raise ValueError("Special files cannot be submitted")
    if sum(path.stat().st_size for path in files) > MAX_ARTIFACT_BYTES:
        raise ValueError("Artefact exceeds 16 MiB")
    target.mkdir()
    entries = []
    for path in files:
        name = Path(source.name) if source.is_file() else path.relative_to(source)
        data = path.read_bytes()
        if len(data) > MAX_ARTIFACT_BYTES:
            raise ValueError("Artefact changed during copying")
        destination = target / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(data)
        entries.append((name.as_posix(), digest(data)))
    return digest(canonical(entries))


def submit(run: Path, assignment_id: str, stage: str, active_seconds: float,
           artefact: Path | None, results: Path | None, failure: str = "") -> dict:
    _, assignments = load_frozen(run)
    assignment = next((item for item in assignments if item["id"] == assignment_id), None)
    if assignment is None or stage not in STAGES or not seconds(active_seconds):
        raise ValueError("Unknown assignment, stage or active time")
    if stage == "revision" and not (run / "submissions" / f"{assignment_id}-initial" / "record.json").exists():
        raise ValueError("Record the initial work before its revision")
    if not artefact and not failure:
        raise ValueError("A missing artefact needs an explicit failure reason")
    if failure and (not isinstance(failure, str) or not failure.strip()):
        raise ValueError("Failure reason must be text")
    submission_id = f"{assignment_id}-{stage}"
    destination = run / "submissions" / submission_id
    destination.mkdir(exist_ok=False)
    try:
        artefact_sha = _snapshot(artefact, destination / "artefact") if artefact else None
        results_sha = None
        if results is not None:
            if not results.is_file() or results.is_symlink() or results.stat().st_size > MAX_ARTIFACT_BYTES:
                raise ValueError("Results must be an ordinary file of at most 16 MiB")
            data = results.read_bytes()
            results_sha = digest(data)
            (destination / "results.json").write_bytes(data)
        record = {
            "schema": "eal-authoring-submission/1", "submission_id": submission_id,
            "assignment_id": assignment_id, "stage": stage, "active_seconds": active_seconds,
            "artefact_sha256": artefact_sha, "results_sha256": results_sha,
            "failure": failure or None,
        }
        (destination / "record.json").write_bytes(canonical(record))
        return record
    except Exception:
        shutil.rmtree(destination)
        raise


def review(run: Path, input_path: Path) -> dict:
    _, assignments = load_frozen(run)
    value = read_json(input_path)
    if (not isinstance(value, dict) or set(value) != {
            "schema", "reviewer_id", "submission_id", "review_seconds", "findings"}
            or value["schema"] != "eal-authoring-review/1"
            or not identifier(value["reviewer_id"])
            or not seconds(value["review_seconds"])
            or not isinstance(value["findings"], list)):
        raise ValueError("Expected a complete independent reviewer record")
    submission_id = value["submission_id"]
    if submission_id not in {f"{a['id']}-{stage}" for a in assignments for stage in STAGES}:
        raise ValueError("Unknown submission")
    submission = run / "submissions" / submission_id / "record.json"
    if not submission.exists():
        raise ValueError("Unknown submission")
    record = read_json(submission)
    assignment = next(item for item in assignments if item["id"] == record["assignment_id"])
    if value["reviewer_id"] == assignment["participant_id"]:
        raise ValueError("An author cannot review their own submission")
    finding_ids = set()
    for finding in value["findings"]:
        if (not isinstance(finding, dict) or set(finding) != {"id", "location", "description"}
                or not identifier(finding["id"]) or finding["id"] in finding_ids
                or not all(isinstance(finding[key], str) and finding[key].strip()
                           for key in ("location", "description"))):
            raise ValueError("Findings need unique IDs, locations and descriptions")
        finding_ids.add(finding["id"])
    directory = run / "reviews" / submission_id
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / f"{value['reviewer_id']}.json").open("xb") as stream:
        stream.write(canonical(value))
    return value


def adjudicate(run: Path, input_path: Path) -> dict:
    _, assignments = load_frozen(run)
    value = read_json(input_path)
    if (not isinstance(value, dict) or set(value) != {
            "schema", "adjudicator_id", "submission_id", "adjudication_seconds",
            "confirmed_defects", "rationale"}
            or value["schema"] != "eal-authoring-adjudication/1"
            or not identifier(value["adjudicator_id"])
            or not seconds(value["adjudication_seconds"])
            or not isinstance(value["rationale"], str)
            or not isinstance(value["confirmed_defects"], list)):
        raise ValueError("Expected a complete adjudication record")
    directory = run / "reviews" / value["submission_id"]
    if value["submission_id"] not in {f"{a['id']}-{stage}" for a in assignments for stage in STAGES}:
        raise ValueError("Unknown submission")
    record_path = run / "submissions" / value["submission_id"] / "record.json"
    if not record_path.exists():
        raise ValueError("Unknown submission")
    record = read_json(record_path)
    assignment = next(item for item in assignments if item["id"] == record["assignment_id"])
    if value["adjudicator_id"] == assignment["participant_id"]:
        raise ValueError("An author cannot adjudicate their own submission")
    available = set()
    for path in directory.glob("*.json"):
        if path.name == "adjudication.json":
            continue
        reviewer = read_json(path)
        available.update(f"{reviewer['reviewer_id']}:{finding['id']}" for finding in reviewer["findings"])
    defect_ids = set()
    used_refs = set()
    for defect in value["confirmed_defects"]:
        if (not isinstance(defect, dict) or set(defect) != {"id", "finding_refs", "description"}
                or not identifier(defect["id"]) or defect["id"] in defect_ids
                or not isinstance(defect["description"], str) or not defect["description"].strip()
                or not isinstance(defect["finding_refs"], list) or not defect["finding_refs"]
                or not all(isinstance(ref, str) for ref in defect["finding_refs"])):
            raise ValueError("Each confirmed defect needs an ID, description and reviewer findings")
        refs = set(defect["finding_refs"])
        if (len(refs) != len(defect["finding_refs"]) or refs & used_refs
                or not refs <= available):
            raise ValueError("Each reviewer finding may identify one confirmed defect")
        defect_ids.add(defect["id"])
        used_refs.update(refs)
    with (directory / "adjudication.json").open("xb") as stream:
        stream.write(canonical(value))
    return value
