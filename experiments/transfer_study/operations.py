"""Instrument developer tool use and the registered EAL adapter."""

from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path
from typing import Any

from eal.knowledge import EALKnowledgeBase, ModelContextAdapter

from .workspace import StudyRun, read_json, utc_now, write_json


class SessionOperations:
    """Record effectful operations against one participant's project copy."""

    def __init__(self, run: StudyRun):
        self.run = run

    def _path(self, packet: dict, relative: str) -> Path:
        workspace = Path(packet["workspace"]).resolve()
        path = (workspace / relative).resolve()
        if not path.is_relative_to(workspace):
            raise ValueError("Study file must be inside the session workspace")
        return path

    def _event(self, session_id: str, value: dict) -> None:
        value["recorded_at"] = utc_now().isoformat()
        path = self.run.root / "events" / f"{session_id}.json"
        values = read_json(path) if path.exists() else []
        values.append(value)
        write_json(path, values)

    def tool(self, session_id: str, argv: list[str], timeout_seconds: int = 120) -> dict:
        packet = self.run.require_active(session_id)
        if (not isinstance(argv, list) or not argv or
                any(not isinstance(part, str) or not part for part in argv)):
            raise ValueError("Tool requires a non-empty argv list")
        if type(timeout_seconds) is not int or not 1 <= timeout_seconds <= 600:
            raise ValueError("Tool timeout_seconds must be 1..600")
        start = time.monotonic()
        try:
            result = subprocess.run(argv, cwd=packet["workspace"], capture_output=True,
                                    timeout=min(timeout_seconds, self.run.remaining_seconds(packet)),
                                    check=False)
            if len(result.stdout) + len(result.stderr) > 1024 * 1024:
                raise ValueError("Tool output exceeds 1 MiB")
        except (OSError, subprocess.TimeoutExpired, ValueError) as exc:
            self._event(session_id, {"kind": "developer_tool_error", "argv": argv,
                                     "duration_seconds": time.monotonic() - start,
                                     "error": {"type": type(exc).__name__,
                                               "message": str(exc)[:4000]}})
            raise
        duration = time.monotonic() - start
        record = {"kind": "developer_tool", "argv": argv,
                  "returncode": result.returncode, "duration_seconds": duration,
                  "stdout": result.stdout.decode("utf-8", errors="replace"),
                  "stderr": result.stderr.decode("utf-8", errors="replace")}
        self._event(session_id, record)
        return record

    def register(self, session_id: str, *, source: str, registry: str, entry_id: str,
                 context: dict[str, Any], claim: str) -> dict:
        packet = self.run.require_active(session_id)
        if packet["arm"] != "eal" or packet["stage"] != "initial":
            raise ValueError("EAL registration belongs to the initial EAL session")
        source_path = self._path(packet, source)
        registry_path = self._path(packet, registry)
        if not source_path.is_file() or not registry_path.is_file():
            raise ValueError("Source and TOML binding must exist in the project copy")
        start = time.monotonic()
        try:
            knowledge = EALKnowledgeBase(packet["workspace"], registry_path)
            result = knowledge.register(source, entry_id=entry_id, context=context, claims=[claim])
        except Exception as exc:
            self._event(session_id, {"kind": "eal_register_error", "entry_id": entry_id,
                                     "duration_seconds": time.monotonic() - start,
                                     "error": {"type": type(exc).__name__,
                                               "message": str(exc)[:4000]}})
            raise
        self._event(session_id, {"kind": "eal_register", "entry_id": entry_id,
                                 "claim": claim, "registry": registry,
                                 "duration_seconds": time.monotonic() - start,
                                 "source_digest": result["source_digest"]})
        return result

    def assess(self, session_id: str, *, registry: str, entry_id: str,
               claim: str, prompt: str) -> dict:
        packet = self.run.require_active(session_id)
        if packet["arm"] != "eal":
            raise ValueError("EAL assessment belongs to an EAL session")
        registry_path = self._path(packet, registry)
        if not registry_path.is_file():
            raise ValueError("TOML binding must exist in the project copy")
        start = time.monotonic()
        try:
            knowledge = EALKnowledgeBase(packet["workspace"], registry_path)
            result = ModelContextAdapter(knowledge).prepare(
                prompt, entry_id, claim, now=packet["assessed_at"])
        except Exception as exc:
            self._event(session_id, {"kind": "eal_assess_error", "entry_id": entry_id,
                                     "claim": claim, "duration_seconds": time.monotonic() - start,
                                     "error": {"type": type(exc).__name__,
                                               "message": str(exc)[:4000]}})
            raise
        duration = time.monotonic() - start
        path = self.run.root / "contexts" / f"{session_id}.{len(self._events(session_id))}.json"
        context = {"schema": "EAL/transfer-context/1", "session_id": session_id,
                   "prompt": prompt, "messages": result["messages"],
                   "assessment": result["assessment"]}
        write_json(path, context)
        assessment = result["assessment"]
        self._event(session_id, {"kind": "eal_assess", "entry_id": entry_id,
                                 "claim": claim, "registry": registry,
                                 "duration_seconds": duration,
                                 "reused_count": assessment["reused_count"],
                                 "collected_count": assessment["collected_count"],
                                 "context_path": str(path)})
        return {"context_path": str(path), "assessment": assessment}

    def _events(self, session_id: str) -> list[dict]:
        path = self.run.root / "events" / f"{session_id}.json"
        return read_json(path) if path.exists() else []
