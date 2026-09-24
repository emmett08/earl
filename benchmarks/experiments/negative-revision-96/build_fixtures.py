"""Materialise authored synthetic roots without translating EAL source to JSON.

The eight briefs and numerical values are fixed in specifications.json. Generated
representations share that external specification and require independent review;
generation itself cannot establish their fidelity to the ordinary briefs.
"""
from __future__ import annotations

import json
import hashlib
from pathlib import Path

HERE = Path(__file__).resolve().parent
SPECS = json.loads((HERE / "specifications.json").read_text(encoding="utf-8"))
QUERY = {"start":0,"end":12,"max_gap":4,"property":{"operator":"lt"},
         "semantics":"sampled","detector_contract":{"maximum_detection_limit":0.1,"minimum_sensitivity":0.9}}


def query(root: dict) -> dict:
    return {**QUERY,"property":{"operator":root.get("operator","lt"),"value":root["bound"]},
            "detector_contract":{"maximum_detection_limit":min(0.1,root["bound"]/2),
                                 "minimum_sensitivity":0.9}}


def expected(root: dict, state: int) -> dict:
    adverse_parent = "supported" if root["pattern"] in ("surviving_route","independent_defence","one_answer_one_open_attack") else "contested"
    return {"bounded_property_supported": "supported" if state != 1 else adverse_parent,
            "violating_sample": "supported" if state == 1 else "unsupported",
            "qualified_absence": "supported" if state == 0 or state == 2 and root["pattern"] == "new_covered_restoration" else "unsupported"}


def targets(root: dict) -> list[str]:
    return ["first"] if root["pattern"] in ("surviving_route","second_route_ineligible") else ["first","second"]


def defended(root: dict) -> list[str]:
    return (["first","second"] if root["pattern"] == "independent_defence" else
            ["first"] if root["pattern"] == "one_answer_one_open_attack" else [])


def _source(root: dict) -> str:
    asset, scope, bound = root["asset"], root["scope"], root["bound"]
    q = query(root)
    subject = f'subject "{asset}"; quantity "{root["quantity"]}"; unit "{root["unit"]}"; scope "{scope}"; valid_from "2040-01-31T08:00:00Z"; valid_until "2040-01-31T09:00:00Z";'
    lines = ['language "EAL/2";',
             f'environment run_scope {{ require "asset" == "{asset}"; require "run" == "{scope}"; }}']
    for tool in ("first_reader", "second_reader", "trace_reader", *(["audit_reader"] if defended(root) else [])):
        lines.append(f'tool {tool} {{ version "1"; mode deterministic; }}')
    for name in ("first_record", "second_record"):
        tool = "first_reader" if name == "first_record" else "second_reader"
        lines.append(f'evidence {name} {{ tool {tool}; kind test; environment run_scope; max_age 3600; '
                     f'require "passed" == true; require "subject" == "{asset}"; '
                     f'require "scope" == "{scope}"; require "property.operator" == "{q["property"]["operator"]}"; '
                     f'require "property.value" == {json.dumps(bound)}; }}')
    if defended(root):
        lines.append(f'evidence audit_record {{ tool audit_reader; kind independent_check; environment run_scope; max_age 3600; require "independently_explained" == true; require "subject" == "{asset}"; require "scope" == "{scope}"; require "sample_time" == 4; require "finding" == "sensor_artifact"; }}')
    lines.extend(['evidence trace_record { tool trace_reader; kind sampled_negative_trace; environment run_scope; max_age 3600; require "schema" == "EAL/typed-input/1"; }',
        'reasoning provisional_test { method "structured/1"; rationale "A submitted matching positive test supports only this sampled run under the authored test warrant."; }',
        'reasoning witnessed_violation { method "engineering/sampled-negative/1"; rationale "One correctly bound violating sample challenges either positive test without establishing values outside the sampled times."; }',
        'reasoning complete_search { method "engineering/sampled-negative/1"; rationale "Qualified non-detection requires all sampled gaps and detector information; physical continuity is not asserted."; }',
        f'claim bounded_property_supported {{ statement "The submitted routes provisionally support the sampled bound for {asset} during {scope}, subject to their declared challenges."; environment run_scope; }}',
        f'claim violating_sample {{ statement "An in-scope sampled value for {asset} violates the declared bound."; environment run_scope; proposition {{ {subject} query {json.dumps({**q,"mode":"counterexample"},separators=(",",":"))}; result "finding" == true; }} }}',
        f'claim qualified_absence {{ statement "The complete calibrated sampled search for {asset} reported no violation within its finite scope."; environment run_scope; proposition {{ {subject} query {json.dumps({**q,"mode":"non_detection"},separators=(",",":"))}; result "finding" == true; }} }}',
        'argument first_route { conclusion bounded_property_supported; reasoning provisional_test; evidence first_record; }',
        'argument second_route { conclusion bounded_property_supported; reasoning provisional_test; evidence second_record; }',
        'argument adverse_route { conclusion violating_sample; reasoning witnessed_violation; evidence trace_record; binding trace_record; }',
        'argument absence_route { conclusion qualified_absence; reasoning complete_search; evidence trace_record; binding trace_record; }'])
    if root["pattern"] == "absence_additional_route":
        lines.append('argument absence_positive_route { conclusion bounded_property_supported; reasoning provisional_test; premises qualified_absence; }')
    for name in targets(root):
        lines.append(f'objection challenge_{name} {{ target argument {name}_route; premises violating_sample; }}')
    for name in defended(root):
        lines.append(f'objection answer_{name} {{ target objection challenge_{name}; evidence audit_record; }}')
    return "\n".join(lines) + "\n"


def _graph(root: dict) -> dict:
    q = query(root)
    return {"schema":"negative-revision-equal-graph/1","id":root["id"],
            "context":{"asset":root["asset"],"run":root["scope"]},
            "subject":root["asset"],"scope":root["scope"],"quantity":root["quantity"],
            "unit":root["unit"],"bound":root["bound"],"query":q,
            "positive_routes":["first_reader","second_reader"],
            "absence_positive_route":root["pattern"] == "absence_additional_route",
            "negative_claim":"violating_sample","absence_claim":"qualified_absence",
            "objections":[{"target":f"{name}_reader","premise":"violating_sample"} for name in targets(root)],
            "defences":[{"target":f"{name}_reader","evidence":"audit_reader"} for name in defended(root)],
            "explanation":"Submitted test routes are provisional. An eligible violating sample challenges both; complete calibrated non-detection is a separate, limited claim."}


def _envelope(tool: str, context: dict, value: dict, observed_at: str) -> dict:
    return {"request":{"tool":tool,"tool_version":"1","mode":"deterministic","input":{},"context":context},
            "context":context,"observed_at":observed_at,"value":value}


def _records(root: dict, state: int) -> dict:
    asset, scope, bound = root["asset"], root["scope"], root["bound"]
    context = {"asset":asset,"run":scope}
    positive = {"passed":True,"subject":asset,"scope":scope,
                "property":{"operator":root.get("operator","lt"),"value":bound}}
    q = query(root)
    covered = state == 0 or state == 2 and root["pattern"] == "new_covered_restoration"
    mode = "non_detection" if covered else "counterexample"
    events = ([{"time":t,"value":v} for t,v in zip((0,4,8,12),root["clear"])] if covered
              else [{"time":4,"value":root["violation"]}])
    payload = {**q,"mode":mode,"events":events}
    if covered:
        payload["calibration"] = {"detection_limit":q["detector_contract"]["maximum_detection_limit"]/2,
                                  "sensitivity_lower_bound":0.95}
    trace = {"schema":"EAL/typed-input/1","method":"engineering/sampled-negative/1",
             "subject":asset,"quantity":root["quantity"],"unit":root["unit"],
             "scope":scope if state != 2 or covered else scope + "-other",
             "valid_from":"2040-01-31T08:00:00Z","valid_until":"2040-01-31T09:00:00Z",
             "payload":payload}
    second = {**positive,"passed":False} if state == 1 and root["pattern"] == "second_route_ineligible" else positive
    trace_time = "2040-01-31T08:25:00Z" if state == 2 and root["pattern"] == "new_covered_restoration" else "2040-01-31T08:20:00Z"
    records = {"first_reader":_envelope("first_reader",context,positive,"2040-01-31T08:18:00Z"),
               "second_reader":_envelope("second_reader",context,second,"2040-01-31T08:19:00Z"),
               "trace_reader":_envelope("trace_reader",context,trace,trace_time)}
    if state == 2 and root["pattern"] == "new_covered_restoration":
        prior = _records(root,1)["trace_reader"]
        prior_digest = hashlib.sha256(json.dumps(prior,sort_keys=True,separators=(",",":"),allow_nan=False).encode()).hexdigest()
        records["trace_reader"]["synthetic_correction"] = {
            "sequence":2,"asserted_by":"fixture_author","supersedes_sha256":prior_digest}
    if defended(root):
        audit = {"independently_explained":state==1,"subject":asset,"scope":scope,"sample_time":4,
                 "finding":"sensor_artifact" if state==1 else "none"}
        records["audit_reader"] = _envelope("audit_reader",context,audit,"2040-01-31T08:21:00Z")
    return records


def build() -> None:
    root_dir = HERE / "roots"
    for root in SPECS["roots"]:
        target = root_dir / root["id"]
        target.mkdir(parents=True, exist_ok=True)
        (target / "source.eal").write_text(_source(root), encoding="utf-8")
        (target / "graph.json").write_text(json.dumps(_graph(root),sort_keys=True,indent=2)+"\n",encoding="utf-8")
        for index, name in enumerate(("covered_clear", "partial_violation", "wrong_scope_restore")):
            body = {"schema":"negative-revision-records/1","root":root["id"],
                    "state":name,"expected":expected(root,index),"records":_records(root,index)}
            if index == 2 and root["pattern"] == "new_covered_restoration":
                body["required_synthetic_correction"] = body["records"]["trace_reader"]["synthetic_correction"]
            (target / f"{name}.json").write_text(json.dumps(body,sort_keys=True,indent=2)+"\n",encoding="utf-8")


if __name__ == "__main__":
    build()
