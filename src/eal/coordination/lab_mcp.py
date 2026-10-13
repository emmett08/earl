"""One bounded local MCP session and Rust codec process per Lab transport."""
from __future__ import annotations

import json
import os
from pathlib import Path
import threading
from typing import Any
import weakref

from mcp import StdioServerParameters

from .persistent_mcp import PersistentMCP


def _close_resources(resources):
    for resource in resources:
        resource.close()


class LabMCPTransport:
    """Reuse the isolated Lab SDK and Store with persistent Rust encoding.

    Actor identity is a trusted local host assertion, as in the supplied Lab
    adapter. Worker isolation and external authentication are not provided by
    stdio or this bridge. First-operation deadlines include server startup.
    Close explicitly or use a context manager. Failed sessions never retry.
    """

    operation_timeout = 30
    mcp_operations = frozenset({"mas_create_run", "mas_receive", "mas_ack", "mas_status",
                                "mas_encode", "mas_validate", "mas_reserve_call", "mas_finish_call",
                                "mas_runtime_info", "mas_send_envelope"})

    def __init__(self, runtime: str | Path, database: str | Path, *, python: str | Path | None = None,
                 binary: str | Path | None = None):
        self.runtime = Path(runtime).resolve()
        self.database = Path(database).resolve()
        # Preserve the venv symlink: resolving it discards Lab's SDK isolation.
        self.python = str(Path(python).absolute() if python is not None
                          else self.runtime / ".venv/bin/python")
        selected_binary = binary if binary is not None else os.environ.get("EAL_MAS_CODEC_BIN", str(
                Path(__file__).parent / "rust_codec/target/release/mas-protocol-codec"))
        self.binary = Path(selected_binary).resolve()
        if not self.binary.is_file():
            raise FileNotFoundError("Build the persistent Rust codec with cargo build --release --locked "
                                    "--manifest-path src/eal/coordination/rust_codec/Cargo.toml, "
                                    "or set EAL_MAS_CODEC_BIN to that executable")
        if not Path(self.python).is_file():
            raise FileNotFoundError(f"Install MAS Protocol Lab in its isolated virtual environment: {self.python}")
        # cli.py supplies response/state-path helpers; no CLI subprocess is used.
        for module in ("cli.py", "mcp_server.py", "protocol.py", "store.py"):
            if not (self.runtime / "runtime/mas_protocol" / module).is_file():
                raise FileNotFoundError(f"MAS Protocol Lab runtime/mas_protocol/{module} is unavailable")
        self.database.parent.mkdir(parents=True, exist_ok=True)
        self._session = None
        self._resources = []
        self._lock = threading.RLock()
        self._closed = False
        self._finalizer = weakref.finalize(self, _close_resources, self._resources)

    def close(self):
        with self._lock:
            self._closed = True
            self._finalizer()

    def __enter__(self):
        if self._closed:
            raise RuntimeError("Lab transport is closed")
        return self

    def __exit__(self, *exception):
        self.close()

    def diagnostics(self):
        return {"server_starts": 0 if self._session is None else self._session.starts,
                "codec_mode": "persistent",
                "admission_mode": "rust",
                "closed": self._closed or (self._session is not None and self._session.closed)}

    def _environment(self) -> dict[str, str]:
        # The local server needs no provider credentials. Keep the SDK1 server
        # isolated from EAL's SDK2 imports and inherited database selection.
        environment = {key: value for key, value in os.environ.items()
                       if not any(marker in key.upper() for marker in
                                  ("API_KEY", "TOKEN", "SECRET", "PASSWORD", "CREDENTIAL"))}
        environment.pop("EAL_MAS_CODEC_MODE", None)
        environment.update(PYTHONPATH=str(self.runtime / "runtime"),
                           MAS_PROTOCOL_BIN=str(self.binary), MAS_STATE_DB=str(self.database))
        return environment

    @staticmethod
    def _result(result) -> Any:
        if result.is_error:
            raise RuntimeError("MAS Protocol Lab MCP tool failed")
        value = result.structured_content
        if value is None:
            if len(result.content) != 1 or result.content[0].type != "text":
                raise RuntimeError("MAS Protocol Lab MCP returned an invalid result")
            try:
                value = json.loads(result.content[0].text)
            except (json.JSONDecodeError, RecursionError) as exc:
                raise RuntimeError("MAS Protocol Lab MCP returned invalid JSON") from exc
        if type(value) is not dict or type(value.get("ok")) is not bool:
            raise RuntimeError("MAS Protocol Lab MCP returned an invalid response envelope")
        if value["ok"]:
            if set(value) != {"ok", "result"}:
                raise RuntimeError("MAS Protocol Lab MCP returned an invalid success envelope")
            return value["result"]
        if set(value) != {"ok", "error"} or type(value["error"]) is not dict:
            raise RuntimeError("MAS Protocol Lab MCP returned an invalid rejection envelope")
        error = value["error"]
        if type(error.get("code")) is not str or type(error.get("message")) is not str:
            raise RuntimeError("MAS Protocol Lab MCP returned an invalid diagnostic")
        if error["code"] == "CODEC_IO":
            raise RuntimeError("Persistent Rust codec connection failed; no operation was retried")
        raise ValueError(f"{error['code']}: {error['message']}")

    def mcp_call(self, name: str, arguments: dict[str, Any]) -> Any:
        if name not in self.mcp_operations:
            raise ValueError("Operation is not exposed by this Lab MCP transport")
        with self._lock:
            if self._closed:
                raise RuntimeError("Lab transport is closed; reopen explicitly")
            if self._session is None:
                parameters = StdioServerParameters(command=self.python,
                    args=[str(Path(__file__).with_name("lab_server.py"))],
                    cwd=str(self.runtime), env=self._environment())
                self._session = PersistentMCP(parameters, self.operation_timeout)
                self._resources.append(self._session)
            try:
                return self._result(self._session.call(name, arguments))
            except (RuntimeError, TimeoutError):
                self.close()
                raise

    @staticmethod
    def _string_keys(value: Any) -> None:
        # JSON encoding would silently turn integer object keys into strings.
        # Reject that conversion before passing an envelope to the real codec.
        if type(value) is dict:
            if any(type(key) is not str for key in value):
                raise ValueError("Lab payload object keys must be strings")
            for item in value.values():
                LabMCPTransport._string_keys(item)
        elif type(value) is list:
            for item in value:
                LabMCPTransport._string_keys(item)

    def _check_envelope(self, envelope):
        self._string_keys(envelope)
        source = json.dumps(envelope, ensure_ascii=False, allow_nan=False, separators=(",", ":"), sort_keys=True)
        if len(source.encode("utf-8")) > 65536 + 256:
            raise ValueError("Lab codec envelope exceeds its bounded input limit")

    def _encode(self, envelope: dict[str, Any]) -> str:
        """Invoke the supplied Rust canonical encoder; never construct wire text."""
        self._check_envelope(envelope)
        value = self.mcp_call("mas_encode", {"envelope": envelope})
        if type(value) is not str or len(value.encode("utf-8")) > 65536:
            raise RuntimeError("MAS Protocol Lab codec returned an invalid encoded message")
        return value

    def create(self, run_id: str, *participants: str, max_messages: int = 8,
               max_bytes: int = 65536, max_calls: int = 2) -> Any:
        return self.mcp_call("mas_create_run", {"run_id": run_id, "agents": list(participants),
                                              "max_messages": max_messages, "max_bytes": max_bytes,
                                              "max_calls": max_calls})

    def send(self, run_id: str, payload: dict, *, actor: str) -> Any:
        envelope = {"message_id": payload["message_id"], "run_id": run_id,
                    "sender": payload["sender"], "recipient": payload["recipient"],
                    "version": "1", "kind": payload["kind"], "payload": payload}
        self._check_envelope(envelope)
        return self.mcp_call("mas_send_envelope", {"envelope": envelope, "actor": actor})

    def receive(self, run_id: str, recipient: str, *, limit: int = 8) -> Any:
        return self.mcp_call("mas_receive", {"run_id": run_id, "recipient": recipient, "limit": limit})

    def acknowledge(self, run_id: str, message_id: str, recipient: str) -> Any:
        return self.mcp_call("mas_ack", {"run_id": run_id, "message_id": message_id, "recipient": recipient})

    def status(self, run_id: str) -> Any:
        return self.mcp_call("mas_status", {"run_id": run_id})

    def reserve(self, run_id, actor, call_id):
        return self.mcp_call("mas_reserve_call", {"run_id": run_id, "actor": actor, "call_id": call_id})

    def finish(self, run_id, actor, call_id, evidence):
        return self.mcp_call("mas_finish_call", {"run_id": run_id, "actor": actor,
                                                "call_id": call_id, "evidence": evidence})

    def validate_wire(self, text):
        return self.mcp_call("mas_validate", {"text": text})
