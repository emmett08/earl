"""Read one pinned GitHub Actions run and all jobs of its latest attempt.

The command accepts only the EAL tool request on stdin and uses GET requests
to api.github.com. It cannot choose a URL, endpoint, verb or workflow action.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone
from urllib.error import HTTPError
from urllib.request import HTTPRedirectHandler, Request, build_opener


_REPOSITORY = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]*/[A-Za-z0-9][A-Za-z0-9_.-]*\Z")
_SHA = re.compile(r"[0-9a-f]{40}\Z")
_MAX_RESPONSE_BYTES = 2 * 1024 * 1024
_MAX_JOBS = 1000
_ROOT = "https://api.github.com"


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        return None


def _pairs(items):
    result = {}
    for key, value in items:
        if key in result:
            raise ValueError(f"Duplicate JSON key {key!r}")
        result[key] = value
    return result


def _parse_json(raw):
    return json.loads(raw, object_pairs_hook=_pairs,
                      parse_constant=lambda value: (_ for _ in ()).throw(ValueError(f"Invalid JSON constant {value}")))


def _get_json(path):
    """Fixed-host HTTPS GET; credentials never enter the URL or result."""
    if not path.startswith("/repos/") or ".." in path or "//" in path:
        raise ValueError("Invalid GitHub API path")
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "eal2-workflow-example/1",
               "X-GitHub-Api-Version": "2022-11-28"}
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    opener = build_opener(_NoRedirect())
    try:
        with opener.open(Request(_ROOT + path, headers=headers, method="GET"), timeout=10) as response:
            if response.status != 200:
                raise ValueError(f"GitHub API returned HTTP {response.status}")
            raw = response.read(_MAX_RESPONSE_BYTES + 1)
    except HTTPError as exc:
        raise ValueError(f"GitHub API returned HTTP {exc.code}") from exc
    if len(raw) > _MAX_RESPONSE_BYTES:
        raise ValueError("GitHub API response exceeds byte limit")
    return _parse_json(raw)


def _positive_int(value, name):
    if type(value) is not int or value < 1:
        raise ValueError(f"{name} must be a positive integer")


def _input(request, *, expected_mode="nondeterministic"):
    if not isinstance(request, dict) or set(request) != {
        "evidence_id", "environment", "tool", "tool_version", "mode", "input", "context"
    }:
        raise ValueError("Expected one EAL acquisition request")
    if (request["evidence_id"] != "workflow_result" or request["environment"] != "github"
            or request["tool"] != "github_workflow" or request["tool_version"] != "1"
            or request["mode"] != expected_mode):
        raise ValueError("Unexpected EAL acquisition identity")
    data, context = request["input"], request["context"]
    if not isinstance(data, dict) or set(data) != {
        "repository", "workflow_id", "workflow_path", "run_id", "run_attempt",
        "head_sha", "created_at", "event", "head_branch", "required_jobs"
    }:
        raise ValueError("Unexpected workflow input")
    if context != {"repository": data["repository"], "decision": "workflow-result"}:
        raise ValueError("Workflow context differs from the requested repository")
    repo = data["repository"]
    if not isinstance(repo, str) or not _REPOSITORY.fullmatch(repo) or any(part in (".", "..") for part in repo.split("/")):
        raise ValueError("Invalid repository identifier")
    for field in ("workflow_id", "run_id", "run_attempt"):
        _positive_int(data[field], field)
    if not isinstance(data["head_sha"], str) or not _SHA.fullmatch(data["head_sha"]):
        raise ValueError("head_sha must be a full lowercase Git SHA")
    if data["workflow_path"] != ".github/workflows/test.yml":
        raise ValueError("This collector example covers only test.yml")
    if data["event"] != "push" or data["head_branch"] != "main":
        raise ValueError("This collector example covers only a push on main")
    if not isinstance(data["created_at"], str) or not re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ", data["created_at"]):
        raise ValueError("created_at must be an exact UTC timestamp")
    jobs = data["required_jobs"]
    if not isinstance(jobs, dict) or not jobs or not all(
        isinstance(name, str) and name and isinstance(steps, list) and steps
        and len(set(steps)) == len(steps) and all(isinstance(step, str) and step for step in steps)
        for name, steps in jobs.items()
    ):
        raise ValueError("required_jobs must map unique job names to named steps")
    return data


def _check_run(run, expected):
    if not isinstance(run, dict) or any(run.get(key) != expected[key] for key in (
        "id", "workflow_id", "head_sha", "created_at", "event", "head_branch", "run_attempt"
    )):
        raise ValueError("Run identity differs from the pinned input")
    if run.get("path") != expected["workflow_path"]:
        raise ValueError("Workflow path differs from the pinned input")
    repository = run.get("repository")
    if not isinstance(repository, dict) or repository.get("full_name") != expected["repository"]:
        raise ValueError("Run repository differs from the pinned input")
    head_repository = run.get("head_repository")
    if head_repository is not None and (not isinstance(head_repository, dict)
                                        or head_repository.get("full_name") != expected["repository"]):
        raise ValueError("Run head repository differs from the pinned input")
    if run.get("status") not in ("completed", "queued", "in_progress", "waiting", "pending", "requested"):
        raise ValueError("Missing or unrecognised workflow run status")


def collect(request, get_json=_get_json, *, offline_receipt=False,
            acquisition_label=None, observed_at=None, expected_mode="nondeterministic"):
    """Return an observation. In tests, inject a deterministic JSON GET function."""
    data = _input(request, expected_mode=expected_mode)
    base = f"/repos/{data['repository']}/actions/runs/{data['run_id']}"
    expected = {"id": data["run_id"], **data}
    current = get_json(base)
    _check_run(current, expected)
    attempt = get_json(f"{base}/attempts/{data['run_attempt']}")
    _check_run(attempt, expected)
    page = 1
    jobs = []
    total = None
    while True:
        response = get_json(f"{base}/attempts/{data['run_attempt']}/jobs?per_page=100&page={page}")
        if not isinstance(response, dict) or type(response.get("total_count")) is not int or not isinstance(response.get("jobs"), list):
            raise ValueError("Malformed attempt jobs response")
        count = response["total_count"]
        if not 0 <= count <= _MAX_JOBS or (total is not None and count != total):
            raise ValueError("Job count exceeds limit or changes between pages")
        total = count
        batch = response["jobs"]
        if len(batch) != min(100, max(0, total - len(jobs))):
            raise ValueError("Incomplete or inconsistent attempt jobs page")
        jobs.extend(batch)
        if len(jobs) == total:
            break
        page += 1
    identifiers = [job.get("id") if isinstance(job, dict) else None for job in jobs]
    if len(set(identifiers)) != len(identifiers) or any(type(identity) is not int or identity < 1 for identity in identifiers):
        raise ValueError("Duplicate or missing job identity")
    if any(job.get("run_id") != data["run_id"] or job.get("head_sha") != data["head_sha"]
           or job.get("run_attempt") != data["run_attempt"] for job in jobs):
        raise ValueError("Job belongs to another run, commit or attempt")
    by_name = {}
    for job in jobs:
        name = job.get("name")
        if not isinstance(name, str) or not name or name in by_name:
            raise ValueError("Duplicate or missing job name")
        by_name[name] = job
    required_ok = True
    for name, named_steps in data["required_jobs"].items():
        job = by_name.get(name)
        if job is None or job.get("status") != "completed" or job.get("conclusion") != "success":
            required_ok = False
            continue
        steps = job.get("steps")
        if not isinstance(steps, list):
            required_ok = False
            continue
        step_names = [step.get("name") if isinstance(step, dict) else None for step in steps]
        if len(set(step_names)) != len(step_names) or any(not isinstance(item, str) for item in step_names):
            raise ValueError("Duplicate or missing step name")
        by_step = {step["name"]: step for step in steps}
        required_ok &= all(name in by_step and by_step[name].get("status") == "completed"
                           and by_step[name].get("conclusion") == "success" for name in named_steps)
    final = get_json(base)
    _check_run(final, expected)
    for field in ("status", "conclusion", "updated_at"):
        if final.get(field) != current.get(field) or attempt.get(field) != current.get(field):
            raise ValueError("Run changed during acquisition")
    all_jobs_success = bool(jobs) and all(job.get("status") == "completed"
                                          and job.get("conclusion") == "success" for job in jobs)
    value = {"identity_matches": True, "latest_attempt": True,
             "acquisition": acquisition_label or ("offline_receipt" if offline_receipt else "live_api"),
             "run_status": final["status"], "run_conclusion": final.get("conclusion"),
             "all_jobs_success": all_jobs_success, "required_steps_success": required_ok,
             "job_count": len(jobs), "job_ids": sorted(identifiers),
             "run_id": data["run_id"], "run_attempt": data["run_attempt"],
             "head_sha": data["head_sha"], "workflow_id": data["workflow_id"]}
    return {"value": value, "context": request["context"],
            "request": {key: request[key] for key in ("tool", "tool_version", "mode", "input", "context")},
            "observed_at": observed_at or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "details": {"api": "https://api.github.com", "offline_receipt": offline_receipt,
                        "attempt_jobs_count": len(jobs),
                        "run_sha256": hashlib.sha256(json.dumps(attempt, sort_keys=True).encode()).hexdigest(),
                        "jobs_sha256": hashlib.sha256(json.dumps(jobs, sort_keys=True).encode()).hexdigest()}}


def main():
    arguments = argparse.ArgumentParser(description="Read one pinned GitHub Actions run")
    arguments.add_argument("--offline-receipt", help="Exercise the adapter with a local projection; cannot satisfy the live evidence predicate")
    options = arguments.parse_args()
    try:
        raw = sys.stdin.buffer.read(_MAX_RESPONSE_BYTES + 1)
        if len(raw) > _MAX_RESPONSE_BYTES:
            raise ValueError("EAL acquisition request exceeds byte limit")
        request = _parse_json(raw)
        if options.offline_receipt:
            with open(options.offline_receipt, "rb") as stream:
                receipt = _parse_json(stream.read(_MAX_RESPONSE_BYTES + 1))
            if receipt.get("schema") != "eal2-github-workflow-receipt/1":
                raise ValueError("Unexpected offline receipt schema")
            urls = receipt.get("provenance", {}).get("urls", [])
            if len(urls) != 3:
                raise ValueError("Offline receipt needs three pinned API endpoints")
            current = receipt["responses"]["current_run"]
            attempt = receipt["responses"]["attempt"]
            jobs = receipt["responses"]["jobs"]
            base = f"/repos/{request['input']['repository']}/actions/runs/{request['input']['run_id']}"
            paths = [base, f"{base}/attempts/{request['input']['run_attempt']}",
                     f"{base}/attempts/{request['input']['run_attempt']}/jobs?per_page=100&page=1"]
            if urls != [_ROOT + path for path in paths]:
                raise ValueError("Offline receipt does not match the requested API endpoints")
            mapping = dict(zip(paths, (current, attempt, jobs)))
            result = collect(request, mapping.__getitem__, offline_receipt=True)
        else:
            result = collect(request)
        print(json.dumps(result, sort_keys=True, allow_nan=False))
    except (ValueError, TypeError, KeyError, OSError) as exc:
        print(f"Workflow collection failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
