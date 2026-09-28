"""Isolated project copies and fresh-session handovers for paired cases."""

from __future__ import annotations

import json
import hashlib
import shutil
from pathlib import Path
from typing import Any

from .design import StudyDesign


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
        if (self.allocation.get("schema") != "EAL/transfer-allocation/1" or
                self.allocation.get("plan_sha256") != self.design.digest):
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
            for case, raw in zip(source.cases, snapshot["cases"], strict=True):
                relative = f"seeds/{case.identifier}"
                shutil.copytree(case.seed_dir, target / relative)
                raw["seed_dir"] = relative
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
        assignment = self.assignment(case_id, slot_id)
        case = self.case(case_id)
        workspace = self.root / "workspaces" / session_id
        if stage == "initial":
            source = case.seed_dir
            developer = assignment["sender"]
            model_id = assignment["initial_model"]
            question = case.initial_question
        else:
            initial_id = self.session_id(case_id, slot_id, "initial")
            if not (self.root / "submissions" / f"{initial_id}.json").is_file():
                raise ValueError("Initial session must be submitted before the handover")
            source = self.root / "handoffs" / initial_id
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
        }
        write_json(path, packet)
        return packet

    def submit(self, session_id: str, answer: str, effort_minutes: float) -> dict:
        packet = self.packet(session_id)
        path = self.root / "submissions" / f"{session_id}.json"
        if path.exists():
            raise ValueError("Session has already been submitted")
        if not isinstance(answer, str) or not answer.strip():
            raise ValueError("Final answer cannot be empty")
        if (isinstance(effort_minutes, bool) or not isinstance(effort_minutes, (int, float))
                or not 0 <= effort_minutes < 100000):
            raise ValueError("effort_minutes must be finite and non-negative")
        import math
        if not math.isfinite(effort_minutes):
            raise ValueError("effort_minutes must be finite")
        snapshot_digest = None
        if packet["stage"] == "initial":
            project = Path(packet["workspace"])
            if any(path.is_symlink() for path in project.rglob("*")):
                raise ValueError("Handover project contains a symlink")
            snapshot = self.root / "handoffs" / session_id
            if snapshot.exists():
                raise ValueError("Handover snapshot already exists")
            shutil.copytree(project, snapshot)
            digest = hashlib.sha256()
            for item in sorted(path for path in snapshot.rglob("*") if path.is_file()):
                data = item.read_bytes()
                digest.update(str(item.relative_to(snapshot)).encode("utf-8") + b"\0")
                digest.update(hashlib.sha256(data).digest())
            snapshot_digest = digest.hexdigest()
        from datetime import datetime, timezone
        record = {"schema": "EAL/transfer-submission/1", "session_id": session_id,
                  "answer": answer, "effort_minutes": effort_minutes,
                  "submitted_at": datetime.now(timezone.utc).isoformat(),
                  "handoff_sha256": snapshot_digest,
                  "model_calls": len(read_json(self.root / "calls" / f"{session_id}.json"))
                  if (self.root / "calls" / f"{session_id}.json").exists() else 0}
        write_json(path, record)
        return record

    def require_active(self, session_id: str) -> dict:
        packet = self.packet(session_id)
        if (self.root / "submissions" / f"{session_id}.json").exists():
            raise ValueError("Submitted session cannot be changed")
        return packet
