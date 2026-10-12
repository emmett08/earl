"""The supplied MAS Protocol Lab's local MCP transport, with its Rust codec.

EAL's MCP client and Lab's pinned MCP server run in different interpreters.
The supplied server has no reservation/completion tools: ``reserve`` and
``finish`` deliberately retain the supplied CLI implementation. Each supported
MCP operation owns and closes a bounded stdio session; there is no JSON-bus
fallback, alternate wire parser, hosted service or persistent daemon.
"""
from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
import subprocess
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from .lab import LabTransport


class LabMCPTransport(LabTransport):
    """Use actual Lab MCP tools where supplied, CLI call accounting otherwise.

    Actor identity is a trusted local host assertion, as in the supplied Lab
    adapter. Worker isolation and external authentication are not provided by
    stdio or this bridge. All operation deadlines include server startup.
    """

    operation_timeout = 30
    codec_timeout = 10
    mcp_operations = frozenset({"mas_create_run", "mas_send", "mas_receive", "mas_ack", "mas_status"})

    def __init__(self, runtime: str | Path, database: str | Path, *, python: str | Path | None = None):
        super().__init__(runtime, database, python=python)
        if not (self.runtime / "runtime/mas_protocol/mcp_server.py").is_file():
            raise FileNotFoundError("MAS Protocol Lab runtime/mas_protocol/mcp_server.py is unavailable")

    def _environment(self) -> dict[str, str]:
        # The local server needs no provider credentials. Keep the SDK1 server
        # isolated from EAL's SDK2 imports and inherited database selection.
        environment = {key: value for key, value in os.environ.items()
                       if not any(marker in key.upper() for marker in
                                  ("API_KEY", "TOKEN", "SECRET", "PASSWORD", "CREDENTIAL"))}
        environment.update(PYTHONPATH=str(self.runtime / "runtime"),
                           MAS_PROTOCOL_BIN=str(self.binary), MAS_STATE_DB=str(self.database))
        return environment

    async def _call(self, name: str, arguments: dict[str, Any]):
        parameters = StdioServerParameters(command=self.python, args=["-m", "mas_protocol.mcp_server"],
                                           cwd=str(self.runtime), env=self._environment())
        async with asyncio.timeout(self.operation_timeout):
            async with stdio_client(parameters) as (reader, writer):
                async with ClientSession(reader, writer, read_timeout_seconds=self.operation_timeout) as session:
                    await session.initialize()
                    result = await session.call_tool(name, arguments)
        # Unwrap expected operation rejections after the SDK's task groups close,
        # preserving ordinary ValueError rather than wrapping it in a task group.
        return result

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
        raise ValueError(f"{error['code']}: {error['message']}")

    def mcp_call(self, name: str, arguments: dict[str, Any]) -> Any:
        if name not in self.mcp_operations:
            raise ValueError("Operation is not exposed by this Lab MCP transport")
        return self._result(asyncio.run(self._call(name, arguments)))

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

    def _encode(self, envelope: dict[str, Any]) -> str:
        """Invoke the supplied Rust canonical encoder; never construct wire text."""
        self._string_keys(envelope)
        source = json.dumps(envelope, ensure_ascii=False, allow_nan=False, separators=(",", ":"), sort_keys=True)
        if len(source.encode("utf-8")) > 65536 + 256:
            raise ValueError("Lab codec envelope exceeds its bounded input limit")
        encoded = subprocess.run([str(self.binary), "encode", "--max-bytes", "65536", "--max-depth", "32"],
                                 input=source, capture_output=True, text=True, env=self._environment(),
                                 timeout=self.codec_timeout, check=False)
        if len(encoded.stdout.encode("utf-8")) > 65536 * 4 + 4096:
            raise RuntimeError("MAS Protocol Lab codec exceeded its bounded result size")
        try:
            value = json.loads(encoded.stdout)
        except (json.JSONDecodeError, RecursionError) as exc:
            raise RuntimeError("MAS Protocol Lab codec returned invalid JSON") from exc
        if type(value) is not dict or type(value.get("ok")) is not bool:
            raise RuntimeError("MAS Protocol Lab codec returned an invalid response envelope")
        if not value["ok"]:
            error = value.get("error")
            if type(error) is not dict:
                raise RuntimeError("MAS Protocol Lab codec returned an invalid diagnostic")
            raise ValueError(f"{error.get('code', 'rejected')}: {error.get('message', 'Codec rejected the message')}")
        if encoded.returncode or set(value) != {"ok", "text"} or type(value["text"]) is not str:
            raise RuntimeError("MAS Protocol Lab codec returned an invalid encoded message")
        return value["text"]

    def create(self, run_id: str, *participants: str, max_messages: int = 8,
               max_bytes: int = 65536, max_calls: int = 2) -> Any:
        return self.mcp_call("mas_create_run", {"run_id": run_id, "agents": list(participants),
                                              "max_messages": max_messages, "max_bytes": max_bytes,
                                              "max_calls": max_calls})

    def send(self, run_id: str, payload: dict, *, actor: str) -> Any:
        envelope = {"message_id": payload["message_id"], "run_id": run_id,
                    "sender": payload["sender"], "recipient": payload["recipient"],
                    "version": "1", "kind": payload["kind"], "payload": payload}
        return self.mcp_call("mas_send", {"text": self._encode(envelope), "actor": actor})

    def receive(self, run_id: str, recipient: str, *, limit: int = 8) -> Any:
        return self.mcp_call("mas_receive", {"run_id": run_id, "recipient": recipient, "limit": limit})

    def acknowledge(self, run_id: str, message_id: str, recipient: str) -> Any:
        return self.mcp_call("mas_ack", {"run_id": run_id, "message_id": message_id, "recipient": recipient})

    def status(self, run_id: str) -> Any:
        return self.mcp_call("mas_status", {"run_id": run_id})
