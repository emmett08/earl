"""Durable trial checkpoints and public operational progress."""

from __future__ import annotations

import json
import os
from pathlib import Path

from .api import utc_now


def write_json(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w") as stream:
        stream.write(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n")
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(path)
    descriptor = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def event(path: Path, value):
    record = {"at": utc_now(), **value}
    with path.open("a") as stream:
        stream.write(json.dumps(record, allow_nan=False) + "\n")
        stream.flush()
        os.fsync(stream.fileno())
    # Prompts, answers, credentials and private reasoning do not enter progress.
    fields = ("at", "type", "id", "model", "arm", "turn", "state", "correct",
              "error", "category", "seconds", "estimated_usd", "reserved_usd")
    progress = {key: record[key] for key in fields if key in record}
    response = record.get("response")
    if response:
        progress.update(model=response.get("model"), input_tokens=response.get("input_tokens"),
                        output_tokens=response.get("output_tokens"),
                        response_id=response.get("metadata", {}).get("id"))
    print(json.dumps(progress, allow_nan=False), flush=True)


class TrialRecord:
    """One durable slot per dispatched request, updated without adding retries."""

    def __init__(self, workspace: Path, value: dict):
        self.workspace, self.value = workspace, value
        self.checkpoint()

    def checkpoint(self):
        write_json(self.workspace / "trial.json", self.value)

    def start_call(self, turn: int, reserved: float):
        call = {"turn": turn, "state": "in_flight", "started_at": utc_now(),
                "reserved_usd": reserved, "response": None, "estimated_usd": None}
        self.value["model_calls"].append(call)
        self.checkpoint()
        self._event("model_call_started", call)
        return call

    def finish_call(self, call: dict, *, state: str, **details):
        call.update(state=state, **details)
        self.checkpoint()
        self._event("model_call_completed" if state == "complete" else "model_call_failed", call)

    def _event(self, kind: str, call: dict):
        event(self.workspace / "events.jsonl", {
            "type": kind, "id": self.value["id"], "model": self.value["model"],
            "arm": self.value["arm"], **call})
