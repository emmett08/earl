#!/usr/bin/env python3
"""Validate the retained EAL/3 pilot and regenerate manuscript numbers and tables.

Python standard library only. No provider client, network call or collection.
The saved report is a cross-check, never the source of the point estimates.
"""
from collections import Counter, defaultdict
from pathlib import Path
import argparse
import gzip
import hashlib
import json
import math
import statistics

ROOT = Path(__file__).resolve().parents[1]
CASES = ["release-three-obligations", "migration-cutover-obligations",
         "database-alternative-read-routes", "dispatch-direct-or-tunnel",
         "firmware-selective-applicability", "migration-multiple-version-bindings"]
NAMES = ["Release", "Cutover", "Read routes", "Dispatch", "Firmware", "Version bindings"]
ARMS = ["eal", "ordinary"]
OUTPUTS = {}


def emit(path, text):
    OUTPUTS[ROOT / path] = text if isinstance(text, bytes) else text.encode()


def read(name):
    return json.loads(gzip.decompress((ROOT / "data" / (name + ".gz")).read_bytes()))


def oracle(case, index):
    """Independent article recomputation from recorded facts, not saved scores."""
    snap = case["timeline"][index]
    spec = case["task_specification"]
    if any(snap["scope"].get(k) != spec["scope"][k] for k in spec["identity_scope_keys"]):
        return "undetermined"
    values = {}
    for requirement in case["rule"]["requirements"]:
        eligible = [fact for fact in snap["facts"]
                    if fact["key"] == requirement["fact_key"] and fact["status"] == "active"
                    and all(k in fact["scope"] and k in snap["scope"] and
                            fact["scope"][k] == snap["scope"][k] for k in requirement["scope_keys"])
                    and 0 <= snap["now_minute"] - fact["observed_at_minute"] <= requirement["max_age_minutes"]]
        if not eligible:
            values[requirement["id"]] = None
            continue
        latest = max(f["observed_at_minute"] for f in eligible)
        newest = [f for f in eligible if f["observed_at_minute"] == latest]
        assert len(newest) == 1, "Ambiguous simultaneous eligible observations"
        a, b = newest[0]["value"], requirement["expected_value"]
        op = requirement["operator"]
        if op == "eq":
            same = type(a) is type(b) or (type(a) in (int, float) and type(b) in (int, float))
            result = same and a == b
        elif op == "lte":
            result = a <= b
        elif op == "gte":
            result = a >= b
        else:
            raise AssertionError(op)
        values[requirement["id"]] = result
    routes = [r["requirement_ids"] for r in case["rule"].get("alternatives", [])]
    if not routes:
        routes = [list(values)]
    if any(all(values[k] is True for k in route) for route in routes):
        return "ready"
    if all(any(values[k] is False for k in route) for route in routes):
        return "not_ready"
    return "undetermined"


def counts(sessions):
    counter = Counter("unknown" if s["article_correct"] is None else
                      "correct" if s["article_correct"] else "incorrect" for s in sessions)
    result = {key: counter[key] for key in ["correct", "incorrect", "unknown"]}
    result["n"] = len(sessions)
    result["bounds"] = [counter["correct"] / len(sessions),
                        (counter["correct"] + counter["unknown"]) / len(sessions)]
    return result


def resource(sessions, calls):
    attempt_ids = [i for session in sessions for i in session["api_attempt_ids"]]
    assert len(attempt_ids) == len(set(attempt_ids))
    selected = [calls[i] for i in attempt_ids]
    result = {k: sum(c["usage"][k] for c in selected) for k in ["input_tokens", "output_tokens"]}
    result["total_tokens"] = result["input_tokens"] + result["output_tokens"]
    result["cached_input_tokens"] = sum(c["usage"]["input_tokens_details"]["cached_tokens"] for c in selected)
    result["reasoning_tokens"] = sum(c["usage"]["output_tokens_details"]["reasoning_tokens"] for c in selected)
    result["cost_usd"] = math.fsum(c["cost_estimate_usd"] for c in selected)
    result["attempts"] = len(selected)
    events = [e for s in sessions for e in s["events"]]
    result["native_probes"] = sum(e["kind"] == "native_probe" for e in events)
    assessments = [e["assessment"] for e in events if e["kind"] == "eal_assess"]
    result["host_collections"] = sum(a["collected_count"] for a in assessments)
    result["host_reuses"] = sum(a["reused_count"] for a in assessments)
    result["summed_session_seconds"] = math.fsum(s["elapsed_seconds"] for s in sessions)
    return result


def radius(lower, upper, width, tail):
    n = len(lower)
    mids = [(a + b) / 2 for a, b in zip(lower, upper)]
    sd = math.sqrt(statistics.variance(mids)) + math.sqrt(sum(((b-a)/2)**2 for a, b in zip(lower, upper)) / (n-1))
    variance = min(sd**2, n*width**2/(4*(n-1)))
    logterm = math.log(2/tail)
    return math.sqrt(2*variance*logterm/n) + 7*width*logterm/(3*(n-1))


def close(a, b):
    assert math.isclose(a, b, rel_tol=1e-10, abs_tol=1e-12), (a, b)


def percent_bounds(values):
    lo, hi = values
    return f"{100*lo:.1f}" if lo == hi else f"{100*lo:.1f}--{100*hi:.1f}"


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check",action="store_true",help="Verify existing outputs without changing them")
    args=parser.parse_args()
    manifest=json.loads((ROOT/"data/manifest.json").read_text())
    for name, sha in manifest["files"].items():
        assert hashlib.sha256((ROOT/"data"/name).read_bytes()).hexdigest()==sha, name
    assert hashlib.sha256((ROOT/"listings/retained-argument.eal").read_bytes()).hexdigest()==manifest["retained_listing_sha256"]
    rows=read("annotated-rows.json"); raw_calls=read("call-accounting.json")
    calls={c["attempt"]:c for c in raw_calls}
    cases={c["identifier"]:c for c in read("cases.json")}
    plan=read("plan.json"); saved=read("analysis-annotated.json")
    provenance=read("provenance.json")
    labels=read("completed-labels.json"); mapping=read("annotation-mapping.json")
    label_items={item["id"]:item for item in labels["items"]}
    mapped_items={item["id"]:item for item in mapping["items"]}
    assert len(label_items)==len(labels["items"])==len(mapped_items)==len(mapping["items"])==4224
    assert set(label_items)==set(mapped_items)
    assert mapping["rows_sha256"]==manifest["source_files"]["rows.json"]
    assert labels["assessor"]["source_items_sha256"]==manifest["source_files"]["annotation-bundle/items.json"]
    assert labels["assessor"]["kind"]=="ai" and labels["assessor"]["collection_changed"] is False
    assert plan["source_language"]==provenance["source_language"]==manifest["source_language"]=="EAL/3"
    assert provenance["run_id"]==saved["practical_decision"]["run_id"]==manifest["run_id"]
    assert provenance["revision"]==manifest["collection_revision"]
    assert saved["processing_provenance"]["revision"]==manifest["processing_revision"]
    assert saved["accounting_complete"] is True and not saved["accounting"]["accounting_errors"]
    assert len(rows)==384 and len(calls)==len(raw_calls)==5442
    assert set(plan["cases"])==set(CASES) and plan["workers"]==4
    pairs=defaultdict(dict); strata=Counter(); all_ids=[]; annotation_ids=[]; statuses=Counter()
    for row in rows:
        assert row["status"]=="complete" and len(row["sessions"])==11
        assert row["arm"] not in pairs[row["pair_id"]]
        pairs[row["pair_id"]][row["arm"]]=row
        strata[(row["case"],row["donor"],row["receiver"],row["native_tools"],row["arm"])]+=1
        for index,s in enumerate(row["sessions"]):
            assert s["session"]==index
            assert s["native_tools"] == (True if index==0 else row["native_tools"])
            expected=oracle(cases[row["case"]],index)
            assert expected==cases[row["case"]]["expected_decisions"][index]==s["score"]["reference"]["decision"]
            annotation=s["annotation"]
            annotation_id=annotation["id"]
            item=label_items[annotation_id]; mapped=mapped_items[annotation_id]
            assert mapped["session_id"]==s["session_id"]
            assert hashlib.sha256(s["raw_answer"].encode()).hexdigest()==mapped["answer_sha256"]
            assert item["text"]==s["raw_answer"] and item["quote"] in item["text"]
            assert annotation["quote"]==item["quote"] and annotation["note"]==item["note"]
            assert annotation["annotator"]==labels["annotator"]
            assert annotation["assessor"]==labels["assessor"]
            assert annotation["status"]==("ambiguous" if item["decision"]=="ambiguous" else "ai")
            annotation_ids.append(annotation_id)
            code=annotation["decision_code"]
            assert code==item["decision"] and code in {"ready","not_ready","undetermined","no_answer","ambiguous"}
            correct=None if code=="ambiguous" else code==expected
            assert s["score"]["task_match"] is correct
            assert s["annotation"]["assessor"]["kind"]=="ai"
            s["article_correct"]=correct
            statuses[code]+=1
            for attempt in s["api_attempt_ids"]:
                c=calls[attempt]
                assert c["session_id"]==s["session_id"] and c["status"]=="completed"
                assert c["model"]==s["model"]
                assert all(type(c["usage"][k]) is int and c["usage"][k]>=0 for k in ["input_tokens","output_tokens"])
                assert c["cost_estimate_usd"] is not None
                assert not c["request_config"].get("previous_response_id")
                all_ids.append(attempt)
    assert len(set(all_ids))==len(all_ids)==len(calls)
    assert len(set(annotation_ids))==len(annotation_ids)==4224 and set(annotation_ids)==set(label_items)
    assert statuses["ambiguous"]==saved["pending_task_annotations"]==25
    assert len(pairs)==192 and all(set(p)==set(ARMS) for p in pairs.values())
    assert len(strata)==96 and set(strata.values())=={4}
    results={"schema":"earl-jss-results/1","run_id":manifest["run_id"],
             "source_language":manifest["source_language"],
             "archive_sha256":manifest["archive_sha256"],
             "collection_run":manifest["collection_run"],"processing_run":manifest["processing_run"],
             "collection_revision":manifest["collection_revision"],"processing_revision":manifest["processing_revision"],
             "artifact_id":manifest["artifact_id"],"api_attempts":len(calls),
             "annotation_provenance":saved["annotation_provenance"],
             "analysis_status":saved["status"],"practical_decision_status":saved["practical_decision"]["status"],
             "sequences":len(rows),"sessions":sum(len(r["sessions"]) for r in rows),
             "paired_blocks":len(pairs),"annotation_codes":dict(sorted(statuses.items())),
             "totals":{},"by_case":{},"by_position":{},"by_configuration":[],"resources":{},"cumulative":[]}
    sessions={arm:[s for r in rows if r["arm"]==arm for s in r["sessions"]] for arm in ARMS}
    for arm in ARMS:
        results["totals"][arm]=counts([s for s in sessions[arm] if s["session"]>0])
        results["resources"][arm]={stage:resource([s for s in sessions[arm] if predicate(s)],calls)
            for stage,predicate in [("initial",lambda s:s["session"]==0),("recipients",lambda s:s["session"]>0),("total",lambda s:True)]}
        results["resources"][arm]["setup_seconds"]=math.fsum(r["setup_seconds"] for r in rows if r["arm"]==arm)
        for stage in ["initial","recipients","total"]:
            current=results["resources"][arm][stage]
            original=saved["resources"][arm][stage]
            for k in ["input_tokens","output_tokens","cached_input_tokens","reasoning_tokens","host_collections","host_reuses"]:
                close(current[k],original[k])
            close(current["cost_usd"],original["known_cost_usd"])
            close(current["attempts"],original["api_attempts"])
            close(current["native_probes"],original["native_tool_calls"])
            close(current["summed_session_seconds"],original["elapsed_seconds"])
    for case in CASES:
        results["by_case"][case]={}; results["by_position"][case]={}
        for arm in ARMS:
            selected=[s for r in rows if r["arm"]==arm and r["case"]==case for s in r["sessions"]]
            results["by_case"][case][arm]=counts([s for s in selected if s["session"]>0])
            results["by_position"][case][arm]=[counts([s for s in selected if s["session"]==h]) for h in range(11)]
    for native in [False,True]:
        for model in ["plain","reasoning"]:
            for arm in ARMS:
                selected=[s for r in rows if r["arm"]==arm and r["native_tools"]==native and r["receiver"]==model for s in r["sessions"][1:]]
                results["by_configuration"].append({"arm":arm,"native_tools":native,"receiver":model,**counts(selected)})
    for h in range(11):
        results["cumulative"].append({arm:resource([s for s in sessions[arm] if s["session"]<=h],calls) for arm in ARMS})
    ratios=[]; qlo=[]; qhi=[]; elo=[]; ehi=[]
    for pair_id,pair in sorted(pairs.items()):
        for key in ["case","donor","receiver","native_tools","repeat"]:
            assert pair["eal"][key]==pair["ordinary"][key]
        e=counts(pair["eal"]["sessions"][1:])["bounds"]
        o=counts(pair["ordinary"]["sessions"][1:])["bounds"]
        qlo.append(e[0]-o[1]);qhi.append(e[1]-o[0]);elo.append(e[0]);ehi.append(e[1])
        er=resource(pair["eal"]["sessions"],calls)["total_tokens"]
        or_=resource(pair["ordinary"]["sessions"],calls)["total_tokens"]
        ratios.append({"pair_id":pair_id,"receiver":pair["eal"]["receiver"],"eal_tokens":er,"ordinary_tokens":or_,"ratio":er/or_})
    results["paired_token_ratios"]=ratios
    results["pairs_using_fewer_eal_tokens"]=sum(r["ratio"]<1 for r in ratios)
    results["quality_difference_bounds"]=[statistics.mean(qlo),statistics.mean(qhi)]
    results["token_reduction"]=1-results["resources"]["eal"]["total"]["total_tokens"]/results["resources"]["ordinary"]["total"]["total_tokens"]
    original=saved["practical_decision"]
    for a,b in zip(results["quality_difference_bounds"],original["quality_difference_bounds"]):close(a,b)
    for a,b in zip(results["totals"]["eal"]["bounds"],original["eal_correctness_bounds"]):close(a,b)
    close(results["token_reduction"],original["token_reduction"])
    results["recomputed_sampling_half_widths"]={}
    for lower,upper,width,key in [(qlo,qhi,2,"quality_sampling_half_width"),(elo,ehi,1,"absolute_quality_sampling_half_width")]:
        half_width=radius(lower,upper,width,.05/6)
        close(half_width,original[key])
        results["recomputed_sampling_half_widths"][key]=half_width
    # The resource interval is retained verbatim and explicitly attributed to
    # the repository's stratified delta-method implementation, not re-estimated.
    results["retained_conditional_intervals"]={k:original[k] for k in ["quality_interval","eal_correctness_interval","token_reduction_interval","resource_degrees_of_freedom","decision_lower_bounds"]}
    results["collection_segment_seconds"]=sum(s["elapsed_seconds"] for s in read("segments.json"))
    results["planner"]={k:read("information-report.json")[k] for k in ["status","blockers"]}
    emit("results/summary.json",json.dumps(results,indent=2,sort_keys=True)+"\n")
    # Small tables are generated as include-ready LaTeX, never edited manually.
    case_lines=[]
    for case,name in zip(CASES,NAMES):
        vals=results["by_case"][case]
        parts=[name]
        for arm in ARMS:
            v=vals[arm];parts += [f"{v['correct']}/{v['incorrect']}/{v['unknown']}",percent_bounds(v['bounds'])]
        case_lines.append(" & ".join(parts)+r" \\")
    emit("results/case-rows.tex",r"\begin{tabular}{@{}l rr rr@{}}\toprule"+"\n"+
         r"& \multicolumn{2}{c}{EAL/3} & \multicolumn{2}{c}{Ordinary notes}\\"+"\n"+
         r"\cmidrule(lr){2-3}\cmidrule(l){4-5}"+"\n"+
         r"Case & C/I/U & Correct (\%) & C/I/U & Correct (\%)\\\midrule"+"\n"+
         "\n".join(case_lines)+"\n"+r"\bottomrule\end{tabular}"+"\n")
    config_lines=[]
    for x in results["by_configuration"]:
        config_lines.append(" & ".join(["On" if x["native_tools"] else "Off","4.1 nano" if x["receiver"]=="plain" else "5 nano (low)","EAL/3" if x["arm"]=="eal" else "Ordinary",str(x["correct"]),str(x["incorrect"]),str(x["unknown"]),percent_bounds(x['bounds'])])+r" \\")
    emit("results/configuration-rows.tex",r"\begin{tabular}{@{}lllrrrr@{}}\toprule"+"\n"+
         r"Tools & Recipient & Workflow & C & I & U & Correct (\%)\\\midrule"+"\n"+
         "\n".join(config_lines)+"\n"+r"\bottomrule\end{tabular}"+"\n")
    resource_lines=[]
    for label,field,fmt in [("Input tokens","input_tokens",",.0f"),("Output tokens","output_tokens",",.0f"),("Input + output tokens","total_tokens",",.0f"),("API attempts","attempts",",.0f"),("Native probe calls","native_probes",",.0f"),("Host acquisitions","host_collections",",.0f"),("Host observation reuses","host_reuses",",.0f"),("Estimated API cost (USD)","cost_usd",".6f")]:
        values=[label]+[format(results["resources"][arm][stage][field],fmt) for arm in ARMS for stage in ["initial","recipients","total"]]
        resource_lines.append(" & ".join(values)+r" \\")
    emit("results/resource-rows.tex",r"\begin{tabular}{@{}lrrrrrr@{}}\toprule"+"\n"+
         r"& \multicolumn{3}{c}{EAL/3} & \multicolumn{3}{c}{Ordinary notes}\\"+"\n"+
         r"\cmidrule(lr){2-4}\cmidrule(l){5-7}"+"\n"+
         r"Measure & Initial & Recipients & Total & Initial & Recipients & Total\\\midrule"+"\n"+
         "\n".join(resource_lines)+"\n"+r"\bottomrule\end{tabular}"+"\n")
    changes=[]
    for path,content in OUTPUTS.items():
        if args.check:
            if not path.exists() or path.read_bytes()!=content:changes.append(str(path.relative_to(ROOT)))
        else:
            path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(content)
    assert not changes,"Stale generated outputs: "+", ".join(changes)
    print(json.dumps({k:results[k] for k in ["sequences","sessions","paired_blocks","totals","token_reduction","pairs_using_fewer_eal_tokens","planner"]},indent=2))
    print(f"{'Checked' if args.check else 'Wrote'} {len(OUTPUTS)} deterministic outputs; every saved score and API attempt reconciled.")


if __name__=="__main__":
    main()
