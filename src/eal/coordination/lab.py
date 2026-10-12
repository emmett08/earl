"""Optional MAS Protocol Lab CLI bridge; no alternate wire parser.

The EAL domain adapter remains independent of this transport. Install/build
the supplied MAS Protocol Lab runtime before selecting the protocol arm.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import tempfile
from typing import Any


class LabTransport:
    """Call the supplied Lab CLI and Rust codec without importing its MCP SDK.

    The runtime uses its own virtual environment because its pinned MCP SDK
    differs from EAL's. Receive retains the runtime's native delivery wrappers;
    the trusted pilot validates envelope/payload correspondence before relaying.
    """

    def __init__(self, runtime: str | Path, database: str | Path, *, python: str | Path | None = None):
        self.runtime = Path(runtime).resolve()
        self.database = Path(database).resolve()
        # Preserve the venv interpreter symlink; resolving it would select the
        # base interpreter and discard the isolated SDK installation.
        self.python = str(Path(python).absolute() if python is not None
                          else self.runtime / ".venv/bin/python")
        self.binary = self.runtime / "rust-protocol/target/release/mas-protocol-codec"
        if not self.binary.is_file():
            raise FileNotFoundError(f"Build the MAS Protocol Lab codec first: {self.binary}")
        if not Path(self.python).is_file():
            raise FileNotFoundError(f"Install MAS Protocol Lab in its isolated virtual environment: {self.python}")
        if not (self.runtime / "runtime/mas_protocol/cli.py").is_file():
            raise FileNotFoundError("MAS Protocol Lab runtime/mas_protocol/cli.py is unavailable")
        self.database.parent.mkdir(parents=True, exist_ok=True)

    def command(self, *arguments: str) -> Any:
        environment = dict(os.environ)
        paths = [str(self.runtime / "runtime")]
        if environment.get("PYTHONPATH"):
            paths.append(environment["PYTHONPATH"])
        environment["PYTHONPATH"] = os.pathsep.join(paths)
        environment["MAS_PROTOCOL_BIN"] = str(self.binary)
        result = subprocess.run(
            [self.python, "-m", "mas_protocol.cli", "--db", str(self.database), *arguments],
            cwd=self.runtime, env=environment, capture_output=True, text=True, timeout=30,
        )
        try:
            value = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"MAS Protocol Lab returned invalid JSON (exit {result.returncode})") from exc
        if not isinstance(value, dict) or type(value.get("ok")) is not bool:
            raise RuntimeError("MAS Protocol Lab returned an invalid response envelope")
        if result.returncode or not value["ok"]:
            error = value.get("error")
            if isinstance(error, dict):
                raise ValueError(f"{error.get('code', 'rejected')}: {error.get('message', 'Operation rejected')}")
            raise ValueError(f"MAS Protocol Lab exited {result.returncode}")
        return value["result"]

    def create(self, run_id: str, *participants: str, max_messages: int = 8,
               max_bytes: int = 65536, max_calls: int = 2) -> Any:
        """Freeze finite budgets for two worker calls and up to eight handoffs.

        The supplied CLI retains its finite 3600-second wall-clock default; it
        exposes message, byte and call budgets as options, not a wall-time flag.
        """
        return self.command("init", run_id, *participants,
                            "--max-messages", str(max_messages), "--max-bytes", str(max_bytes),
                            "--max-calls", str(max_calls))

    def send(self, run_id: str, payload: dict, *, actor: str) -> Any:
        envelope = {
            "message_id": payload["message_id"], "run_id": run_id,
            "sender": payload["sender"], "recipient": payload["recipient"],
            "version": "1", "kind": payload["kind"], "payload": payload,
        }
        with tempfile.TemporaryDirectory(prefix="eal-mas-message-") as temporary:
            source = Path(temporary) / "message.json"
            source.write_text(json.dumps(envelope, ensure_ascii=False, allow_nan=False), encoding="utf-8")
            return self.command("send", "--actor", actor, "--message-file", str(source))

    def receive(self, run_id: str, recipient: str, *, limit: int = 8) -> Any:
        """Return [{message: canonical envelope, sequence, redelivered}, ...]."""
        return self.command("receive", run_id, recipient, "--limit", str(limit))

    def acknowledge(self, run_id: str, message_id: str, recipient: str) -> Any:
        return self.command("ack", run_id, message_id, recipient)

    def reserve(self, run_id: str, actor: str, call_id: str) -> Any:
        return self.command("reserve", run_id, "--actor", actor, "--call-id", call_id)

    def finish(self, run_id: str, actor: str, call_id: str, evidence: dict) -> Any:
        with tempfile.TemporaryDirectory(prefix="eal-mas-execution-") as temporary:
            source = Path(temporary) / "execution.json"
            source.write_text(json.dumps(evidence, ensure_ascii=False, allow_nan=False), encoding="utf-8")
            return self.command("finish", run_id, "--actor", actor, "--call-id", call_id,
                                "--evidence-file", str(source))

    def status(self, run_id: str) -> Any:
        return self.command("status", run_id)

    def validate_wire(self, text: str) -> Any:
        """Ask the supplied Rust recogniser through its CLI; do not route text."""
        with tempfile.TemporaryDirectory(prefix="eal-mas-wire-") as temporary:
            source = Path(temporary) / "message.mas"
            source.write_text(text, encoding="utf-8")
            return self.command("validate", "--text-file", str(source))
