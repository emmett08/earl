"""Persistent local Lab adapter, executed directly in Lab's isolated SDK venv.

The supplied Store remains the authority for mailbox transactions and budgets.
The wire grammar and codec are Rust; this script does not import EAL's SDK.
"""
from __future__ import annotations

import atexit
import json
import os
import signal
import time

from codec_process import CodecProcess, CodecUnavailable
from lab_admission import send_admitted
from mas_protocol import protocol
from mas_protocol.cli import response, state_path
from mas_protocol.mcp_server import create_server
from mas_protocol.store import Store


def main():
    codec = CodecProcess(os.environ["MAS_PROTOCOL_BIN"])
    metrics = {"encode_calls": 0, "parse_calls": 0, "admit_calls": 0, "codec_ns": 0}

    def rust_call(operation, source, max_bytes, max_depth):
        started = time.perf_counter_ns()
        metrics[operation + "_calls"] += 1
        try:
            try:
                value = codec.call(operation, source, max_bytes, max_depth)
            except CodecUnavailable as error:
                raise protocol.ProtocolError("CODEC_IO", str(error)) from error
            if not value["ok"]:
                error = value["error"]
                raise protocol.ProtocolError(error["code"], error["message"],
                                             line=error.get("line"), column=error.get("column"))
            return value
        finally:
            metrics["codec_ns"] += time.perf_counter_ns() - started

    protocol._rust_call = rust_call
    atexit.register(codec.close)
    def stop(signum, frame):
        # SDK-owned shutdown must also reap a codec stalled in a request.
        raise SystemExit(0)
    signal.signal(signal.SIGTERM, stop)
    path = state_path()
    server = create_server()

    def call(operation):
        return response(lambda: operation(Store(path)))

    @server.tool()
    def mas_encode(envelope: dict) -> dict:
        """Canonical Rust encoding without routing or spending mailbox budgets."""
        return response(lambda: protocol.encode_message(envelope))

    @server.tool()
    def mas_send_envelope(envelope: dict, actor: str) -> dict:
        """Rust admits the complete envelope before the unchanged durable send rules."""
        def send():
            source = json.dumps(envelope, ensure_ascii=False, allow_nan=False, separators=(",", ":"), sort_keys=True)
            canonical = rust_call("admit", source, 65536, 32)["message"]
            if canonical["version"] != protocol.BASE_VERSION:
                raise protocol.ProtocolError("VERSION", "Message version must be '1'")
            return send_admitted(Store(path), canonical, actor)
        return response(send)

    @server.tool()
    def mas_reserve_call(run_id: str, actor: str, call_id: str) -> dict:
        """Reserve once before external execution; uncertain calls are not repeated."""
        return call(lambda store: store.reserve_call(run_id, actor, call_id))

    @server.tool()
    def mas_finish_call(run_id: str, actor: str, call_id: str, evidence: dict) -> dict:
        """Record completion using the supplied mailbox's immutable call ledger."""
        return call(lambda store: store.finish_call(run_id, actor, call_id, evidence))

    @server.tool()
    def mas_runtime_info() -> dict:
        """Inspect local process reuse and codec timings; no provider metadata."""
        return {"ok": True, "result": {"server_pid": os.getpid(),
                "codec_pid": None if codec.process is None else codec.process.pid,
                "codec_starts": codec.starts, "codec_mode": "persistent", **metrics}}

    try:
        server.run(transport="stdio")
    finally:
        codec.close()


if __name__ == "__main__":
    main()
