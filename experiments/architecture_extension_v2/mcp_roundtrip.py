"""Collect an EAL assessment through the real MCP stdio protocol.

The transcript stores each UTF-8 JSON-RPC line, including its newline, in wire
order.  The packet is the material made available to the specified coding arm;
the feature brief does not contain argument or harness instructions.
"""

from __future__ import annotations

import argparse
import asyncio
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
MAX_LINE = 8 * 1024 * 1024


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False,
                               allow_nan=False) + "\n", encoding="utf-8")


class WireClient:
    """Sequential JSON-RPC client that retains the exact stdio messages."""

    def __init__(self, process: asyncio.subprocess.Process, timeout: float):
        self.process = process
        self.timeout = timeout
        self.next_id = 1
        self.transcript: list[dict[str, Any]] = []

    def _retain(self, direction: str, line: bytes) -> None:
        if len(line) > MAX_LINE or not line.endswith(b"\n"):
            raise ValueError("MCP message exceeds the line limit or lacks a newline")
        self.transcript.append({"direction": direction, "utf8_line": line.decode("utf-8"),
                                "sha256": digest(line)})

    async def send(self, message: dict[str, Any]) -> None:
        if self.process.stdin is None:
            raise RuntimeError("MCP stdin is unavailable")
        line = (json.dumps(message, separators=(",", ":"), ensure_ascii=False,
                           allow_nan=False) + "\n").encode("utf-8")
        self._retain("client_to_server", line)
        self.process.stdin.write(line)
        await asyncio.wait_for(self.process.stdin.drain(), self.timeout)

    async def request(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        request_id = self.next_id
        self.next_id += 1
        message: dict[str, Any] = {"jsonrpc": "2.0", "id": request_id, "method": method}
        if params is not None:
            message["params"] = params
        await self.send(message)
        if self.process.stdout is None:
            raise RuntimeError("MCP stdout is unavailable")
        while True:
            line = await asyncio.wait_for(self.process.stdout.readline(), self.timeout)
            if not line:
                raise RuntimeError(f"MCP server closed stdout before {method} replied")
            self._retain("server_to_client", line)
            response = json.loads(line)
            if response.get("id") != request_id:
                if "id" in response:
                    raise RuntimeError(f"Unexpected MCP response ID during {method}")
                continue  # Server notification; retained in the transcript.
            if "error" in response:
                raise RuntimeError(f"MCP {method} failed: {response['error']}")
            if "result" not in response:
                raise RuntimeError(f"MCP {method} omitted its result")
            return response["result"]

    async def tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        result = await self.request("tools/call", {"name": name, "arguments": arguments})
        if result.get("isError") is True:
            raise RuntimeError(f"MCP {name} returned an error: {result.get('content')}")
        data = result.get("structuredContent")
        if not isinstance(data, dict):
            raise RuntimeError(f"MCP {name} omitted structured content")
        return data


async def exchange(source: str, source_path: Path, registry_path: Path, context: dict[str, Any],
                   goal: str, now: str | None, timeout: float, compile_aspic: bool,
                   output_path: Path, packet_path: Path | None) -> None:
    environment = dict(os.environ)
    environment["PYTHONPATH"] = str(ROOT / "src") + (
        os.pathsep + environment["PYTHONPATH"] if environment.get("PYTHONPATH") else "")
    with tempfile.TemporaryDirectory(prefix="architecture-eal-mcp-") as temporary:
        process = await asyncio.create_subprocess_exec(
            sys.executable, "-m", "eal.server", "--workspace", str(ROOT),
            "--registry", str(registry_path), "--database", str(Path(temporary) / "runs.sqlite3"),
            cwd=ROOT, env=environment, stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, limit=MAX_LINE + 1,
        )
        client = WireClient(process, timeout)
        transcript: dict[str, Any] = {
            "schema": "architecture-extension-mcp-wire/1",
            "source": str(source_path.relative_to(ROOT)),
            "source_sha256": digest(source.encode("utf-8")),
            "registry": str(registry_path.relative_to(ROOT)),
            "registry_sha256": digest(registry_path.read_bytes()),
            "context": context, "goal": goal,
            "server_argv": [sys.executable, "-m", "eal.server", "--workspace", str(ROOT),
                            "--registry", str(registry_path), "--database", "<temporary>/runs.sqlite3"],
            "messages": client.transcript,
        }
        try:
            initialised = await client.request("initialize", {
                "protocolVersion": "2025-11-25", "capabilities": {},
                "clientInfo": {"name": "architecture-extension-trial", "version": "1"},
            })
            transcript["negotiated_protocol_version"] = initialised["protocolVersion"]
            await client.send({"jsonrpc": "2.0", "method": "notifications/initialized"})
            available = await client.request("tools/list")
            required = {"eal_validate", "eal_collect", "eal_reason", "eal_explain"}
            if compile_aspic:
                required.add("eal_compile_aspic")
            names = {item["name"] for item in available["tools"]}
            if missing := required - names:
                raise RuntimeError(f"MCP server is missing tools: {sorted(missing)}")

            validation = await client.tool("eal_validate", {"source": source})
            if validation.get("valid") is not True:
                raise ValueError(f"EAL source failed validation: {validation.get('diagnostics')}")
            collection = await client.tool("eal_collect", {"source": source, "context": context})
            failures = {name: item for name, item in collection["records"].items()
                        if item.get("status") != "ok"}
            if failures:
                raise ValueError(f"EAL collection has failed records: {failures}")
            # A default time chosen before collection would place all freshly
            # acquired observations in the assessment's future.
            now = now or datetime.now(timezone.utc).isoformat()
            transcript["assessed_at"] = now
            assessment = await client.tool("eal_reason", {
                "source": source, "context": context,
                "collection_id": collection["collection_id"], "now": now,
            })
            if goal not in assessment["claims"]:
                raise ValueError(f"EAL assessment has no claim {goal!r}")
            explanation = await client.tool("eal_explain", {
                "assessment_id": assessment["assessment_id"], "claim": goal,
            })
            if explanation["result"]["status"] != assessment["claims"][goal]["status"]:
                raise ValueError("MCP explanation status differs from the assessment")

            packet: dict[str, Any] = {
                "schema": "architecture-extension-agent-context/1", "source": source,
                "source_sha256": transcript["source_sha256"], "context": context,
                "assessed_at": now, "goal": goal,
                "collection_id": collection["collection_id"],
                "assessment_id": assessment["assessment_id"],
                "goal_status": assessment["claims"][goal]["status"],
                "explanation": explanation,
            }
            if compile_aspic:
                formal = await client.tool("eal_compile_aspic", {
                    "source": source, "context": context,
                    "collection_id": collection["collection_id"], "goal": goal, "now": now,
                })
                packet["formal_status"] = formal["formal"]["grounded_status"]
                packet["formal_snapshot_digest"] = formal["snapshot_digest"]
                transcript["formal_result"] = formal
            transcript["status"] = "ok"
            transcript["validation"] = validation
            transcript["collection"] = collection
            transcript["assessment"] = assessment
            transcript["explanation"] = explanation
            if packet_path is not None:
                write_json(packet_path, packet)
                transcript["packet_path"] = str(packet_path)
                transcript["packet_sha256"] = digest(packet_path.read_bytes())
        except Exception as exc:
            transcript["status"] = "error"
            transcript["error"] = f"{type(exc).__name__}: {exc}"
            raise
        finally:
            if process.stdin is not None:
                process.stdin.close()
            try:
                await asyncio.wait_for(process.wait(), timeout)
            except TimeoutError:
                process.kill()
                await process.wait()
            if process.stderr is not None:
                stderr = await process.stderr.read(MAX_LINE + 1)
                transcript["server_stderr"] = stderr.decode("utf-8", errors="replace")
            transcript["server_exit_code"] = process.returncode
            write_json(output_path, transcript)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--registry", type=Path, required=True)
    parser.add_argument("--context", required=True, help="Exact JSON context object")
    parser.add_argument("--goal", required=True, help="A declared EAL claim")
    parser.add_argument("--output", type=Path, required=True, help="Full wire transcript and results")
    parser.add_argument("--packet", type=Path, help="Source and MCP result delivered to a coding arm")
    parser.add_argument("--now", help="Assessment time with UTC offset; defaults to after collection")
    parser.add_argument("--timeout", type=float, default=30.0, help="Per-message deadline")
    parser.add_argument("--compile-aspic", action="store_true")
    args = parser.parse_args()
    source_path, registry_path = args.source.resolve(), args.registry.resolve()
    source_path.relative_to(ROOT)
    registry_path.relative_to(ROOT)
    context = json.loads(args.context)
    if not isinstance(context, dict):
        parser.error("--context must be a JSON object")
    if args.timeout <= 0 or args.timeout > 300:
        parser.error("--timeout must be in (0, 300] seconds")
    asyncio.run(exchange(source_path.read_text(encoding="utf-8"), source_path, registry_path,
                         context, args.goal, args.now, args.timeout, args.compile_aspic,
                         args.output.resolve(), args.packet.resolve() if args.packet else None))


if __name__ == "__main__":
    main()
