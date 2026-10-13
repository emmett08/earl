"""Actual current-time MCP acquisition, reuse, packet and explanation checks."""
from copy import deepcopy

import pytest

from eal.coordination.contracts import ServerSpec, TaskSpec
from eal.coordination.gateway import MCPGateway
from eal.coordination.profiles import pin_task, validate_answer
from experiments.mas_coordination.coordinator_demo import prepare_demo


def answer(anchor, finding):
    task = anchor["task"]
    return {"task_digest": anchor["task_digest"], "finding_id": finding["finding_id"],
            "claims": {claim: {key: finding["assessments"].get(claim, {}).get(key)
                                for key in ("assessment_id", "status", "assessed_at")}
                       for claim in task["claims"]},
            "scope": {"context": task["requirements"]["context"], "requirements": task["requirements"]},
            "conclusion": "assessed" if finding["check"]["ok"] else "out_of_scope",
            "qualification": "conditional_on_registered_argument"}


@pytest.mark.parametrize("index", [0, 1])
def test_actual_stdio_multiple_claims_acquisition_reuse_lookup_and_answer(tmp_path, index, monkeypatch):
    demo = prepare_demo(tmp_path)
    server = ServerSpec.from_dict({"limits": None, **demo["server"]})
    task = TaskSpec.from_dict(demo["tasks"][index])
    anchor = pin_task(server, task)
    # Parent and child host configuration cannot inherit a competing launcher.
    monkeypatch.setenv("EAL_MCP_EXPOSURE", "operator")
    monkeypatch.setenv("EAL_MCP_KNOWN_ENTRIES", '["unregistered"]')
    monkeypatch.setenv("EAL_MCP_TRANSPORT", "http")
    calls = []
    gateway = MCPGateway(server, anchor, lambda name, arguments, exposure: calls.append((name, arguments, exposure)))
    finding = gateway.assess()
    assert finding["check"]["ok"]
    assert set(finding["assessments"]) == set(task.claims)
    assert finding["collected_count"] > 0
    if index == 0:
        assert finding["reused_count"] > 0
    assert [name for name, _, exposure in calls if exposure == "registered"] == ["eal_sources", "eal_assess_known", "eal_assess_known"]
    assert all(set(arguments) == {"entry_id", "claim"} for name, arguments, _ in calls if name == "eal_assess_known")
    assert calls[0] == ("eal_sources", {}, "registered")
    assert {name for name, _, exposure in calls if exposure == "operator"} == {"eal_packet", "eal_explain"}
    assert all(trace["outcome"] == "success" for trace in finding["mcp"]["calls"])
    assert validate_answer(anchor, finding, answer(anchor, finding)) == []
    lookup = MCPGateway(server, anchor)
    assert lookup.lookup(finding) == finding
    assert {trace["name"] for trace in lookup.calls} == {"eal_packet", "eal_explain"}
    later = MCPGateway(server, anchor).assess()
    assert later["collected_count"] == 0 and later["reused_count"] > 0
    if index == 1:
        assert finding["assessments"][task.claims[0]]["status"] == "contested"
    wrong = answer(anchor, finding)
    wrong["claims"][task.claims[0]]["status"] = "invented proof"
    assert validate_answer(anchor, finding, wrong)[0]["path"].startswith("claims.")
    tampered = deepcopy(finding)
    tampered["assessments"][task.claims[0]]["status"] = "supported"
    tampered["mcp"]["calls"].append({"name": "invented"})
    with pytest.raises(ValueError, match="identity"):
        lookup.lookup(tampered)


@pytest.mark.parametrize("case", ["criteria", "clients", "source"])
def test_invalid_correspondence_makes_no_mcp_calls_or_acquisition(tmp_path, case):
    demo = prepare_demo(tmp_path)
    server = ServerSpec.from_dict({"limits": None, **demo["server"]})
    task = deepcopy(demo["tasks"][0])
    if case == "criteria":
        task["requirements"]["criteria"]["minimum_requests"] = 101
    if case == "clients":
        task["requirements"]["workload"]["concurrent_clients"] = 20
    anchor = pin_task(server, TaskSpec.from_dict(task))
    if case == "source":
        path = server.workspace / "api-load.eal"
        path.write_text(path.read_text().replace("The identified synthetic report", "This identified synthetic report"))
    calls = []
    finding = MCPGateway(server, anchor, lambda *args: calls.append(args)).assess()
    assert not finding["check"]["ok"] and finding["assessments"] == {}
    assert finding["collected_count"] == finding["reused_count"] == 0
    assert calls == finding["mcp"]["calls"] == []
    assert validate_answer(anchor, finding, answer(anchor, finding)) == []


def test_budget_callback_stops_before_effect_and_keeps_attempt_trace(tmp_path):
    demo = prepare_demo(tmp_path)
    server = ServerSpec.from_dict({"limits": None, **demo["server"]})
    task = TaskSpec.from_dict(demo["tasks"][0])
    anchor = pin_task(server, task)

    def stop(*args):
        raise ValueError("tool quota exhausted")

    gateway = MCPGateway(server, anchor, stop)
    with pytest.raises(Exception):
        gateway.assess()
    assert gateway.calls[0]["outcome"] == "not_called"
    from eal.coordination.profiles import knowledge
    assert knowledge(server).history(task.entry_id)["assessments"] == []


@pytest.mark.parametrize("mismatch", ["extra_entry", "source_changed"])
def test_actual_registered_discovery_rejects_wrong_exposure_before_assessment(tmp_path, mismatch):
    demo = prepare_demo(tmp_path)
    server = ServerSpec.from_dict({"limits": None, **demo["server"]})
    task = TaskSpec.from_dict(demo["tasks"][0])
    anchor = pin_task(server, task)

    def before_call(name, arguments, exposure):
        if mismatch == "source_changed" and name == "eal_sources":
            source = server.workspace / "api-load.eal"
            source.write_text(source.read_text() + "\n// Changed immediately before actual discovery.\n")

    gateway = MCPGateway(server, anchor, before_call)
    if mismatch == "extra_entry":
        parameters = gateway._parameters

        def expose_extra(exposure):
            value = parameters(exposure)
            if exposure == "registered":
                value.args.extend(["--known-entry", "availability_sample"])
            return value

        gateway._parameters = expose_extra
    with pytest.raises(Exception):
        gateway.assess()
    assert gateway.calls == [{"name": "eal_sources", "arguments": {}, "exposure": "registered", "outcome": "success"}]
    from eal.coordination.profiles import knowledge
    assert knowledge(server).history(task.entry_id)["assessments"] == []
