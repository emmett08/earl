#!/usr/bin/env python3
"""Run both paired synthetic records through EAL and a separate brief-rule checker.

This is a local consistency test written by the fixture author, not masked
review, physical measurement authentication, or a general equal host.
"""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
from datetime import datetime
from fractions import Fraction
from math import hypot, sqrt
from pathlib import Path
from statistics import NormalDist
import json
import math
from tempfile import TemporaryDirectory

from eal.formatter import format_program, semantic_ir
from eal.parser import parse
from eal.runtime import ReasoningService, load_method_registry


HERE = Path(__file__).resolve().parent
OPS = {"<": lambda a,b:a<b, "<=":lambda a,b:a<=b, "==":lambda a,b:a==b,
       "!=":lambda a,b:a!=b, ">=":lambda a,b:a>=b, ">":lambda a,b:a>b}


def when(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def admissible(root, records, evidence):
    datum=records[evidence]
    control=root["valid_records"][evidence]
    if datum.get("context") != root["context"] or datum.get("request") != control["request"]:
        return False
    if not (0 <= (when(root["now"])-when(datum["observed_at"])).total_seconds() <= 1800):
        return False
    return True


def _calculate(method, payload):
    if method=="engineering/rms/1":
        return {"rms":hypot(*(x-payload["origin"] for x in payload["samples"])) / sqrt(len(payload["samples"]))}
    if method=="causal/1":
        mean=lambda xs:sum(map(Fraction,xs),Fraction()) / len(xs)
        return {"estimate":float(mean(payload["treatment"])-mean(payload["control"]))}
    if method=="inductive/1":
        n,k=payload["trials"],payload["successes"]
        z=NormalDist().inv_cdf((1+payload["confidence"])/2)
        p=k/n
        return {"lower":(p+z*z/(2*n)-z*sqrt(p*(1-p)/n+z*z/(4*n*n)))/(1+z*z/n)}
    if method=="counterfactual/1":
        equations=payload["variables"]
        target=payload["intervention"]["variable"]
        setting=payload["intervention"]["value"]
        out={}
        while len(out)<len(equations):
            ready=[(n,e) for n,e in equations.items() if n not in out and set(e["coefficients"])<=out.keys()]
            if not ready: raise ValueError("Cyclic fixture")
            for n,e in ready:
                out[n]=setting if n==target else e["intercept"]+e["noise"]+sum(c*out[parent] for parent,c in e["coefficients"].items())
        return {"counterfactual":out[payload["outcome"]]}
    if method=="abductive/1":
        weights=[c["prior"]*c["likelihood"] for c in payload["candidates"]]
        return {"best_posterior":max(weights)/sum(weights)}
    if method=="analogical/1":
        keys=payload["relevant_features"]
        matched=sum(payload["source"].get(k)==payload["target"].get(k) and k in payload["source"] and k in payload["target"] for k in keys)
        return {"match_fraction":matched/len(keys)}
    raise ValueError(method)


def reference_status(root, records):
    """Apply separately coded brief rules; never parse EAL or call its evaluator."""
    rule=root["reference_rule"]
    family=root["family"]
    if family=="eligibility":
        for evidence, tests in rule["conditions"].items():
            if not admissible(root,records,evidence):return "unsupported"
            data=records[evidence]["value"]
            if any(key not in data or not OPS[op](data[key],expected) for key,op,expected in tests):return "unsupported"
        return "supported"
    if family=="typed_numerical":
        evidence="numerical_input"
        if not admissible(root,records,evidence):return "unsupported"
        value=records[evidence]["value"]
        original=root["valid_records"][evidence]["value"]
        for field in ("schema","method","subject","quantity","unit","scope"):
            if value.get(field)!=original[field]:return "unsupported"
        if when(value["valid_from"]) > when(original["valid_from"]) or when(value["valid_until"]) < when(original["valid_until"]):return "unsupported"
        query=rule["query"]
        if any(value["payload"].get(k)!=v for k,v in query.items()):return "unsupported"
        answer=_calculate(rule["method"],value["payload"])[rule["result_path"]]
        return "supported" if OPS[rule["operator"]](answer,rule["threshold"]) else "unsupported"
    if family=="sampled_negative":
        evidence="trace_input"
        if not admissible(root,records,evidence):return "unsupported"
        val=records[evidence]["value"]
        original=root["valid_records"][evidence]["value"]
        if any(val.get(k)!=original[k] for k in ("schema","method","subject","quantity","unit","scope")):return "unsupported"
        if when(val["valid_from"]) > when(original["valid_from"]) or when(val["valid_until"]) < when(original["valid_until"]):return "unsupported"
        p=val["payload"]
        if any(p.get(k)!=original["payload"][k] for k in ("mode","start","end","max_gap","property","semantics","detector_contract")):return "unsupported"
        events=p["events"]
        if not events or any(a["time"]>=b["time"] for a,b in zip(events,events[1:])):return "unsupported"
        op=p["property"]["operator"]; bound=p["property"]["value"]
        violations=[e for e in events if not (e["value"]<bound if op=="lt" else e["value"]<=bound)]
        if p["mode"]=="counterexample":return "supported" if violations else "unsupported"
        full=(events[0]["time"]==p["start"] and events[-1]["time"]==p["end"] and
              all(b["time"]-a["time"]<=p["max_gap"] for a,b in zip(events,events[1:])))
        c=p["calibration"]; d=p["detector_contract"]
        calibrated=(c["detection_limit"]<=d["maximum_detection_limit"]<=bound and
                    c["sensitivity_lower_bound"]>=d["minimum_sensitivity"]>0)
        return "supported" if full and calibrated and not violations else "unsupported"
    if family=="objection_defence":
        main=rule["primary"]; alert=rule["alert"]; defence=rule["defence"]
        if not admissible(root,records,main):return "unsupported"
        if not admissible(root,records,alert) or records[alert]["value"].get("event") != root["valid_records"][alert]["value"]["event"]:return "supported"
        if defence and admissible(root,records,defence) and records[defence]["value"].get("origin") == root["valid_records"][defence]["value"]["origin"]:
            return "supported"
        return "contested"
    raise ValueError(family)


def eal_status(root, records, source_text=None):
    """Assess exact supplied display bytes when the study requests a canonical view."""
    source=(HERE/root["source"]).read_text(encoding="utf-8") if source_text is None else source_text
    with TemporaryDirectory(prefix="eal2-mechanism-root-") as directory:
        path=Path(directory); (path/'observations').mkdir()
        registry=[]
        for evidence,envelope in records.items():
            tool=envelope["request"]["tool"]
            (path/'observations'/f'{tool}.json').write_text(json.dumps(envelope),encoding="utf-8")
            registry += [f'[tools.{tool}]\nkind="json_file"\nmode="deterministic"\nversion="1"\npath="observations/{tool}.json"\n']
        (path/'tools.toml').write_text('\n'.join(registry),encoding='utf-8')
        service=ReasoningService(path,path/'tools.toml',database_path=path/'runs.sqlite3',
                                 method_registry=load_method_registry(root['method_factory']))
        check=service.validate(source)
        if not check['valid']:raise AssertionError(f"{root['id']}: {check['diagnostics']}")
        collected=service.collect(source,root['context'])
        assessment=service.reason(source,root['context'],collected['collection_id'],root['now'])
        return assessment['claims'][root['claim']]['status'],collected


def main():
    corpus=json.loads((HERE/'manifest.json').read_text(encoding='utf-8'))
    assert corpus['schema']=='eal2-mechanism-roots/1' and len(corpus['roots'])==24
    assert Counter(r['family'] for r in corpus['roots'])==Counter({
        "eligibility":6,"typed_numerical":6,"sampled_negative":6,"objection_defence":6})
    results=[]
    for root in corpus['roots']:
        source=(HERE/root['source']).read_text(encoding='utf-8')
        generated=json.loads((HERE/root['semantic_view']).read_text(encoding='utf-8'))
        assert generated==json.loads(json.dumps(semantic_ir(parse(source)))),root['id']
        displayed=format_program(parse(source),registry=load_method_registry(root['method_factory']))
        assert json.loads(json.dumps(semantic_ir(parse(displayed))))==generated,root['id']
        assert root['wrong_proposal'] not in (root['valid_status'],root['invalid_status'],root['absent_status'])
        for state in ('valid','invalid'):
            evidence=root[f'{state}_records']
            other=root[f'{"invalid" if state=="valid" else "valid"}_records']
            assert set(evidence)==set(other)
            changed=[name for name in evidence if evidence[name]!=other[name]]
            assert len(changed)==1,root['id']
            changed_id=changed[0]
            v=deepcopy(evidence[changed_id]); w=deepcopy(other[changed_id])
            if root['family'] in ('typed_numerical','sampled_negative'):
                v['value'].pop('payload'); w['value'].pop('payload')
                assert v!=w and evidence[changed_id]['value']['payload']==other[changed_id]['value']['payload'],root['id']
            expected=root[f'{state}_status']
            independent=reference_status(root,evidence)
            actual, collected=eal_status(root,evidence)
            assert independent==expected==actual,(root['id'],state,expected,independent,actual)
            displayed_actual,_=eal_status(root,evidence,source_text=displayed)
            assert displayed_actual==expected,(root['id'],state,expected,displayed_actual)
            results.append((root['id'],state,expected))
    print(json.dumps({"roots":24,"paired_states":len(results),"families":dict(Counter(r['family'] for r in corpus['roots'])),
                      "statuses":dict(Counter(row[2] for row in results)),"source_ir_equal":True,
                      "independent_code_reference_parity":True,"canonical_display_parity":True,
                      "human_review":"pending"},sort_keys=True))


if __name__=='__main__':
    main()
