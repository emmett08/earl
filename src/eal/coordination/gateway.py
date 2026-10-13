"""Trusted MCP-only acquisition and persisted assessment retrieval.

Registered exposure acquires through ``eal_assess_known`` with entry/claim only.
Separate operator exposure retrieves packets and explanations; it cannot be
selected by a worker. There are no time, context, source or reuse overrides.
"""
from __future__ import annotations

import asyncio
from copy import deepcopy
import os
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from eal.evaluator import canonical_digest
from eal.semantics import parse_time

from .contracts import FINDING_SCHEMA, make_finding, validate_anchor
from .profiles import check_task

_WRAPPER_FIELDS = {"schema", "entry_id", "claim", "source_digest", "context_fingerprint",
                   "collection_id", "assessment_id", "assessed_at", "status", "reused_count",
                   "collected_count", "packet", "full_explanation"}
_FINDING_FIELDS = {"schema", "finding_id", "task_digest", "check", "assessments", "packets",
                   "explanations", "mcp", "collected_count", "reused_count"}
_STATUSES = {"supported", "contested", "unsupported", "out_of_scope"}


class MCPGateway:
    def __init__(self, server, anchor, on_call=None):
        self.server = server
        self.anchor = deepcopy(anchor)
        self.task = validate_anchor(self.anchor)
        self.on_call = on_call
        self.calls = []

    def _parameters(self, exposure):
        args = ["-m", "eal.server", "--workspace", str(self.server.workspace),
                "--database", str(self.server.database), "--transport", "stdio", "--exposure", exposure]
        for name in ("registry", "methods", "limits"):
            value = getattr(self.server, name)
            if value is not None:
                args.extend(["--" + name, str(value)])
        if exposure == "registered":
            args.extend(["--known-entry", self.task.entry_id])
        # An inherited launcher configuration must not change this frozen host.
        env = {key: value for key, value in os.environ.items() if not key.startswith("EAL_MCP_")}
        return StdioServerParameters(command=sys.executable, args=args, env=env)

    async def _call(self, session, name, arguments, exposure):
        trace = {"name": name, "arguments": deepcopy(arguments), "exposure": exposure, "outcome": "not_called"}
        self.calls.append(trace)
        if self.on_call is not None:
            self.on_call(name, deepcopy(arguments), exposure)
        trace["outcome"] = "started"
        try:
            result = await session.call_tool(name, arguments)
            if result.is_error or type(result.structured_content) is not dict:
                raise RuntimeError(f"EAL MCP {name} did not return a successful structured result")
            trace["outcome"] = "success"
            return result.structured_content
        except BaseException:
            trace["outcome"] = "interrupted_or_failed"
            raise

    def _wrapper(self, claim, row, packet, explanation):
        if type(row) is not dict or set(row) != _WRAPPER_FIELDS or row["schema"] != "EAL/registered-assessment/1":
            raise ValueError("Registered assessment wrapper differs from its closed contract")
        if (row["entry_id"] != self.task.entry_id or row["claim"] != claim
                or row["source_digest"] != self.anchor["source_digest"]
                or row["context_fingerprint"] != canonical_digest(self.anchor["registered_context"])):
            raise ValueError("Registered assessment differs from the pinned task")
        if any(type(row[name]) is not int or row[name] < 0 for name in ("collected_count", "reused_count")):
            raise ValueError("Registered acquisition counts require nonnegative integers")
        if row["status"] not in _STATUSES:
            raise ValueError("Registered assessment contains an unknown EAL status")
        parse_time(row["assessed_at"])
        if parse_time(row["assessed_at"]) < parse_time(self.anchor["pinned_at"]):
            raise ValueError("Registered assessment predates this task pin")
        if canonical_digest(row["packet"]) != canonical_digest(packet):
            raise ValueError("Registered assessment packet differs from actual persisted MCP packet")
        if row["full_explanation"] != packet["full_explanation"]:
            raise ValueError("Registered explanation reference differs from its persisted packet")
        for name, expected in (("assessment_id", row["assessment_id"]), ("source_digest", self.anchor["source_digest"]),
                               ("context_fingerprint", row["context_fingerprint"]),
                               ("method_registry_fingerprint", self.anchor["method_registry_fingerprint"])):
            if packet.get(name) != expected:
                raise ValueError("Persisted packet identity differs from the task assessment")
        if packet["claims"][claim]["status"] != row["status"]:
            raise ValueError("Persisted packet status differs from its registered assessment")
        for name, expected in (("assessment_id", row["assessment_id"]), ("claim", claim),
                               ("source_digest", self.anchor["source_digest"]),
                               ("method_registry_fingerprint", self.anchor["method_registry_fingerprint"]),
                               ("assessed_at", row["assessed_at"])):
            if explanation.get(name) != expected:
                raise ValueError("Persisted explanation identity differs from the task assessment")
        if explanation["result"]["status"] != row["status"]:
            raise ValueError("Persisted explanation status differs from its registered assessment")

    async def _retrieve(self, assessments):
        packets, explanations = {}, {}
        if not assessments:
            return packets, explanations
        async with stdio_client(self._parameters("operator")) as (reader, writer):
            async with ClientSession(reader, writer, read_timeout_seconds=60) as session:
                await session.initialize()
                for claim, row in assessments.items():
                    arguments = {"assessment_id": row["assessment_id"], "claim": claim}
                    packet = await self._call(session, "eal_packet", arguments, "operator")
                    explanation = await self._call(session, "eal_explain", arguments, "operator")
                    self._wrapper(claim, row, packet, explanation)
                    packets[claim], explanations[claim] = packet, explanation
        return packets, explanations

    async def _assess(self):
        check = check_task(self.server, self.anchor)
        if not check["ok"]:
            return make_finding(self.anchor, check, calls=self.calls)
        assessments = {}
        async with stdio_client(self._parameters("registered")) as (reader, writer):
            async with ClientSession(reader, writer, read_timeout_seconds=60) as session:
                await session.initialize()
                sources = await self._call(session, "eal_sources", {}, "registered")
                entries = sources.get("sources")
                if (type(entries) is not list or len(entries) != 1 or type(entries[0]) is not dict
                        or entries[0].get("entry_id") != self.task.entry_id
                        or entries[0].get("source_digest") != self.anchor["source_digest"]
                        or type(entries[0].get("claims")) is not list
                        or any(type(claim) is not str for claim in entries[0]["claims"])
                        or len(entries[0]["claims"]) != len(set(entries[0]["claims"]))
                        or set(self.task.claims) - set(entries[0]["claims"])):
                    raise ValueError("Actual MCP discovery differs from the pinned entry and selected claims")
                for claim in self.task.claims:
                    current = check_task(self.server, self.anchor)
                    if not current["ok"]:
                        raise ValueError("Task correspondence changed during registered assessment")
                    assessments[claim] = await self._call(session, "eal_assess_known",
                                                         {"entry_id": self.task.entry_id, "claim": claim}, "registered")
        packets, explanations = await self._retrieve(assessments)
        final_check = check_task(self.server, self.anchor)
        if not final_check["ok"]:
            raise ValueError("Task correspondence changed during persisted assessment retrieval")
        return make_finding(self.anchor, check, assessments, packets, explanations, self.calls)

    def assess(self):
        return asyncio.run(self._assess())

    async def _lookup(self, finding):
        if (type(finding) is not dict or set(finding) != _FINDING_FIELDS
                or finding["schema"] != FINDING_SCHEMA or finding["task_digest"] != self.anchor["task_digest"]
                or finding["finding_id"] != "finding_" + canonical_digest({key: value for key, value in finding.items() if key != "finding_id"})):
            raise ValueError("Finding identity differs from its complete trusted content")
        current = check_task(self.server, self.anchor)
        if current != finding["check"]:
            raise ValueError("Task correspondence differs from the issued finding")
        selected = set(self.task.claims)
        rows = finding["assessments"]
        if type(rows) is not dict or set(rows) not in (set(), selected):
            raise ValueError("Finding must contain either all selected assessments or none")
        if set(finding["packets"]) != set(rows) or set(finding["explanations"]) != set(rows):
            raise ValueError("Finding assessment, packet and explanation selections differ")
        if finding["check"]["ok"] != bool(rows):
            raise ValueError("Finding assessments differ from its correspondence disposition")
        if finding["collected_count"] != sum(row["collected_count"] for row in rows.values()) or finding["reused_count"] != sum(row["reused_count"] for row in rows.values()):
            raise ValueError("Finding acquisition counts differ from its registered assessments")
        packets, explanations = await self._retrieve(rows)
        if (canonical_digest(packets) != canonical_digest(finding["packets"])
                or canonical_digest(explanations) != canonical_digest(finding["explanations"])):
            raise ValueError("Finding differs from actual persisted MCP packets or explanations")
        if check_task(self.server, self.anchor) != current:
            raise ValueError("Task correspondence changed during lookup")
        return deepcopy(finding)

    def lookup(self, finding):
        return asyncio.run(self._lookup(finding))
