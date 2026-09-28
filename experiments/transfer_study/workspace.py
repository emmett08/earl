"""Isolated project copies and fresh-session handovers for paired cases."""

from __future__ import annotations

import json
import hashlib
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .design import StudyDesign


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def project_digest(root: Path) -> str:
    if any(path.is_symlink() for path in root.rglob("*")):
        raise ValueError("Project snapshot contains a symlink")
    digest = hashlib.sha256()
    for item in sorted(path for path in root.rglob("*") if path.is_file()):
        digest.update(str(item.relative_to(root)).encode("utf-8") + b"\0")
        digest.update(hashlib.sha256(item.read_bytes()).digest())
    return digest.hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False,
                                    allow_nan=False) + "\n", encoding="utf-8")
    temporary.replace(path)


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


class StudyRun:
    """Own the plan snapshot, assignments and participant workspaces."""

    def __init__(self, root: str | Path):
        self.root = Path(root).resolve()
        self.design = StudyDesign.load(self.root / "plan.json")
        self.allocation = read_json(self.root / "allocation.json")
        if self.allocation != self.design.allocations(self.allocation.get("seed")):
            raise ValueError("Allocation does not match the frozen plan")
        self.assignments = {
            (item["case_id"], item["slot_id"]): item
            for item in self.allocation["assignments"]
        }

    @classmethod
    def create(cls, plan: str | Path, root: str | Path, seed: int) -> StudyRun:
        source = StudyDesign.load(plan)
        target = Path(root).resolve()
        if target.exists():
            raise ValueError("Study output directory already exists")
        target.mkdir(parents=True)
        try:
            snapshot = read_json(source.source)
            seed_digests = {}
            for case, raw in zip(source.cases, snapshot["cases"], strict=True):
                relative = f"seeds/{case.identifier}"
                shutil.copytree(case.seed_dir, target / relative)
                raw["seed_dir"] = relative
                seed_digests[case.identifier] = project_digest(target / relative)
            write_json(target / "seed_digests.json", seed_digests)
            write_json(target / "plan.json", snapshot)
            frozen = StudyDesign.load(target / "plan.json")
            write_json(target / "allocation.json", frozen.allocations(seed))
            return cls(target)
        except Exception:
            shutil.rmtree(target)
            raise

    def assignment(self, case_id: str, slot_id: str) -> dict:
        try:
            return self.assignments[(case_id, slot_id)]
        except KeyError as exc:
            raise ValueError("Unknown case or participant slot") from exc

    def case(self, case_id: str):
        return next(case for case in self.design.cases if case.identifier == case_id)

    def session_id(self, case_id: str, slot_id: str, stage: str) -> str:
        if stage not in ("initial", "later"):
            raise ValueError("Stage must be initial or later")
        self.assignment(case_id, slot_id)
        return f"{case_id}.{slot_id}.{stage}"

    def packet_path(self, session_id: str) -> Path:
        return self.root / "packets" / f"{session_id}.json"

    def packet(self, session_id: str) -> dict:
        path = self.packet_path(session_id)
        if not path.is_file():
            raise ValueError("Session has not been opened")
        return read_json(path)

    def open(self, case_id: str, slot_id: str, stage: str) -> dict:
        session_id = self.session_id(case_id, slot_id, stage)
        path = self.packet_path(session_id)
        if path.exists():
            return read_json(path)
        if (self.root / "submissions" / f"{session_id}.json").exists():
            raise ValueError("Closed session cannot be opened")
        assignment = self.assignment(case_id, slot_id)
        case = self.case(case_id)
        workspace = self.root / "workspaces" / session_id
        if stage == "initial":
            source = case.seed_dir
            self._check_seed(case_id)
            developer = assignment["sender"]
            model_id = assignment["initial_model"]
            question = case.initial_question
        else:
            initial_id = self.session_id(case_id, slot_id, "initial")
            initial_path = self.root / "submissions" / f"{initial_id}.json"
            if not initial_path.is_file():
                raise ValueError("Initial session must be submitted before the handover")
            source = self.root / "handoffs" / initial_id
            if project_digest(source) != read_json(initial_path)["handoff_sha256"]:
                raise ValueError("Handover snapshot differs from the submitted project")
            developer = assignment["recipient"]
            model_id = assignment["later_model"]
            question = case.later_question
        if workspace.exists():
            raise ValueError("Session workspace exists without its packet")
        shutil.copytree(source, workspace)
        model = self.design.models[model_id]
        packet = {
            "schema": "EAL/transfer-session/1", "session_id": session_id,
            "case_id": case_id, "slot_id": slot_id, "stage": stage,
            "arm": assignment["arm"], "transfer": assignment["transfer"],
            "developer": developer, "model_id": model_id,
            "model_version": model.version, "model_size_class": model.size_class,
            "question": question, "workspace": str(workspace),
            "assessed_at": case.later_now if stage == "later" else None,
            "opened_at": utc_now().isoformat(),
            "budget_seconds": 60 * self.design.session_minutes[stage],
        }
        write_json(path, packet)
        return packet

    def submit(self, session_id: str, answer: str, effort_minutes: float) -> dict:
        if not isinstance(answer, str) or not answer.strip():
            raise ValueError("Final answer cannot be empty")
        return self._finish(session_id, "submitted", answer, effort_minutes, None)

    def close(self, session_id: str, status: str, reason: str,
              effort_minutes: float | None = None) -> dict:
        """Retain an allocated nonresponse without manufacturing an answer or rating."""
        if status not in ("no_answer", "withdrawn", "invalid_measurement"):
            raise ValueError("Closure status must be no_answer, withdrawn or invalid_measurement")
        if not isinstance(reason, str) or not reason.strip():
            raise ValueError("Closure requires a reason")
        return self._finish(session_id, status, None, effort_minutes, reason)

    def _finish(self, session_id: str, status: str, answer: str | None,
                effort_minutes: float | None, reason: str | None) -> dict:
        case_id, slot_id, stage = session_id.split(".")
        self.session_id(case_id, slot_id, stage)
        path = self.root / "submissions" / f"{session_id}.json"
        if path.exists():
            raise ValueError("Session has already been submitted")
        if (effort_minutes is not None and
                (isinstance(effort_minutes, bool) or not isinstance(effort_minutes, (int, float))
                or not 0 <= effort_minutes < 100000)):
            raise ValueError("effort_minutes must be finite and non-negative")
        packet = self.packet(session_id) if self.packet_path(session_id).exists() else None
        if status == "submitted" and packet is None:
            raise ValueError("Session has not been opened")
        now = utc_now()
        elapsed = max(0, (now - datetime.fromisoformat(packet["opened_at"])).total_seconds()
                      ) if packet else None
        budget = 60 * self.design.session_minutes[stage]
        snapshot_digest = None
        if stage == "initial":
            project = Path(packet["workspace"]) if packet else self.case(case_id).seed_dir
            if packet is None:
                self._check_seed(case_id)
            project_digest(project)
            snapshot = self.root / "handoffs" / session_id
            if snapshot.exists():
                raise ValueError("Handover snapshot already exists")
            shutil.copytree(project, snapshot)
            snapshot_digest = project_digest(snapshot)
        record = {"schema": "EAL/transfer-submission/2", "session_id": session_id,
                  "status": status, "reason": reason,
                  "answer": answer, "effort_minutes": effort_minutes,
                  "submitted_at": now.isoformat(), "elapsed_seconds": elapsed,
                  "budget_seconds": budget,
                  "within_budget": elapsed is not None and elapsed <= budget,
                  "handoff_sha256": snapshot_digest,
                  "model_calls": len(read_json(self.root / "calls" / f"{session_id}.json"))
                  if (self.root / "calls" / f"{session_id}.json").exists() else 0}
        write_json(path, record)
        return record

    def require_active(self, session_id: str) -> dict:
        packet = self.packet(session_id)
        if (self.root / "submissions" / f"{session_id}.json").exists():
            raise ValueError("Submitted session cannot be changed")
        if self.remaining_seconds(packet) <= 0:
            raise ValueError("Session time budget exhausted; submit or close the session")
        return packet

    def remaining_seconds(self, packet: dict) -> float:
        return max(0, packet["budget_seconds"] -
                   (utc_now() - datetime.fromisoformat(packet["opened_at"])).total_seconds())

    def _check_seed(self, case_id: str) -> None:
        if project_digest(self.case(case_id).seed_dir) != read_json(
                self.root / "seed_digests.json")[case_id]:
            raise ValueError("Case seed differs from the allocated project")
