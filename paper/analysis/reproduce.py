#!/usr/bin/env python3
"""Validate the retained pilot and regenerate all manuscript numbers and plots.

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


HEADER = r"""% Generated by analysis/reproduce.py from retained observations.
% Required packages: pgfplots, amsmath, xcolor, tikz
% Required TikZ libraries: none
% Target width: 160 mm maximum, use at natural size
% Minimum text size: 8.5 pt
% Colour/greyscale intent: one teal accent; shape and dash cues survive greyscale
\begin{tikzpicture}
\definecolor{ealteal}{RGB}{0,102,108}
\pgfplotsset{compat=1.18,ealaxis/.style={font=\fontsize{8.5}{10}\selectfont,
  tick label style={font=\fontsize{8.5}{10}\selectfont},
  axis line style={black!55,line width=0.4pt},tick style={black!55},
  grid style={black!12,line width=0.35pt},axis on top,
  legend style={draw=none,fill=white,font=\fontsize{8.5}{10}\selectfont},legend cell align=left,
  label style={font=\fontsize{8.5}{10}\selectfont}}}
"""


def coords(values):
    return " ".join(f"({x:.8f},{y:.8f})" for x, y in values)


def figure(name, body):
    emit("figures/" + name + ".tikz.tex", HEADER + body + "\n\\end{tikzpicture}\n")


def estimands_figure(results):
    """Explain observed coding bounds, sampling expansion and total-token ratios."""
    lower, upper = results["quality_difference_bounds"]
    ci_lower, ci_upper = results["retained_conditional_intervals"]["quality_interval"]
    eal_tokens = results["resources"]["eal"]["total"]["total_tokens"]
    ordinary_tokens = results["resources"]["ordinary"]["total"]["total_tokens"]
    ratio = eal_tokens / ordinary_tokens
    reduction = results["token_reduction"]
    close(ratio + reduction, 1)
    # Both rulers have a 70 mm unit span, with different, explicitly named units.
    x_lower, x_upper = 2 + 70 * lower, 2 + 70 * upper
    x_ci_lower, x_ci_upper = 2 + 70 * ci_lower, 2 + 70 * ci_upper
    x_ratio = 86 + 70 * ratio
    source = rf"""% Generated by analysis/reproduce.py from retained observations.
% Required packages: amsmath, xcolor, tikz
% Required TikZ libraries: none
% Target width: 160 mm maximum, use at natural size
% Minimum text size: 8.5 pt
% Colour/greyscale intent: one teal accent; direct labels and stroke weights
\begingroup
\definecolor{{ealestimandteal}}{{RGB}}{{0,102,108}}
\begin{{tikzpicture}}[x=1mm,y=1mm,
  every node/.style={{font=\fontsize{{8.5}}{{10}}\selectfont,inner sep=0pt}},
  ealestimandaxis/.style={{black!55,line width=0.4pt}},
  ealestimandcap/.style={{black!70,line width=0.7pt}}]
\node[anchor=west] at (0,62) {{(a) Correctness difference}};
\node[anchor=west] at (84,62) {{(b) Aggregate token use}};

\node[anchor=west] at (0,54) {{Observed coding envelope}};
\node at ({(x_lower+x_upper)/2:.8f},49) {{{100*lower:.2f}--{100*upper:.2f}}};
\draw[ealestimandteal,line width=1.8pt] ({x_lower:.8f},44) -- ({x_upper:.8f},44);
\node[anchor=west] at (0,37) {{Conditional sampling interval}};
\node at ({(x_ci_lower+x_ci_upper)/2:.8f},32) {{{100*ci_lower:.2f}--{100*ci_upper:.2f}}};
\draw[ealestimandcap] ({x_ci_lower:.8f},27) -- ({x_ci_upper:.8f},27);
\draw[ealestimandcap] ({x_ci_lower:.8f},25.5) -- ({x_ci_lower:.8f},28.5);
\draw[ealestimandcap] ({x_ci_upper:.8f},25.5) -- ({x_ci_upper:.8f},28.5);
\draw[ealestimandaxis] (2,20) -- (72,20);
"""
    for tick in range(0, 101, 20):
        x = 2 + .7 * tick
        source += rf"\draw[ealestimandaxis] ({x:.1f},20) -- ({x:.1f},18.5);" + "\n"
        source += rf"\node[anchor=north] at ({x:.1f},16.5) {{{tick}}};" + "\n"
    source += rf"""\node at (37,8) {{EAL/2 $-$ ordinary (percentage points)}};
\node at (37,1) {{$[\bar l,\bar u]\;\mapsto\;[\bar l-r,\bar u+r]$}};

\draw[ealestimandteal,line width=0.8pt] ({x_ratio:.8f},50) -- (156,50);
\draw[ealestimandteal,line width=0.8pt] ({x_ratio:.8f},48.5) -- ({x_ratio:.8f},51.5);
\draw[ealestimandteal,line width=0.8pt] (156,48.5) -- (156,51.5);
\node at ({(x_ratio+156)/2:.8f},56) {{{100*reduction:.2f}\% reduction}};
\node at ({(86+x_ratio)/2:.8f},44) {{EAL/2: {ratio:.5f}}};
\draw[ealestimandcap] (86,37) -- (156,37);
\draw[ealestimandcap] (86,35.5) -- (86,38.5);
\draw[ealestimandcap] (156,35.5) -- (156,38.5);
\draw[ealestimandteal,line width=1.4pt] ({x_ratio:.8f},35) -- ({x_ratio:.8f},39);
\draw[ealestimandaxis,densely dotted] ({x_ratio:.8f},20) -- ({x_ratio:.8f},34);
\node[anchor=east] at (156,31) {{Ordinary $=1$}};
\draw[ealestimandaxis] (86,20) -- (156,20);
"""
    for tick, label in [(0, "0"), (.25, "0.25"), (.5, "0.5"), (.75, "0.75"), (1, "1")]:
        x = 86 + 70 * tick
        source += rf"\draw[ealestimandaxis] ({x:.1f},20) -- ({x:.1f},18.5);" + "\n"
        source += rf"\node[anchor=north] at ({x:.1f},16.5) {{{label}}};" + "\n"
    source += rf"""\node at (121,8) {{Tokens / ordinary total}};
\node at (121,1) {{EAL/2: {eal_tokens:,}; ordinary: {ordinary_tokens:,}}};
\end{{tikzpicture}}
\endgroup
"""
    emit("figures/estimands-uncertainty.tikz.tex", source)


def figures(results):
    estimands_figure(results)
    by_case = results["by_case"]
    body = r"\begin{axis}[ealaxis,width=14.8cm,height=7cm,xmin=0,xmax=103,ymin=.4,ymax=6.7," + "\n"
    body += r"xlabel={Recipient answers matching the reference (\%)},xtick={0,20,40,60,80,100},xmajorgrids," + "\n"
    body += r"ytick={1,2,3,4,5,6},yticklabels={Version bindings,Firmware,Dispatch,Read routes,Cutover,Release}," + "\n"
    body += r"legend style={at={(.5,1.04)},anchor=south,column sep=6pt},legend columns=2]" + "\n"
    for arm, style, offset in [("eal", "ealteal,mark=triangle*", .12), ("ordinary", "black!65,mark=diamond*", -.12)]:
        body += rf"\addplot[only marks,{style},mark size=2pt] coordinates {{" + coords([(100*by_case[c][arm]["bounds"][0], 6-i+offset) for i,c in enumerate(CASES)]) + "};\n"
        body += rf"\addlegendentry{{{'EAL/2' if arm == 'eal' else 'Ordinary notes'}}}" + "\n"
        for i, c in enumerate(CASES):
            lo, hi = by_case[c][arm]["bounds"]
            body += rf"\addplot[forget plot,{'ealteal' if arm=='eal' else 'black!65'},line width=1.4pt] coordinates {{" + coords([(100*lo,6-i+offset),(100*hi,6-i+offset)]) + "};\n"
    body += r"\end{axis}"
    figure("case-correctness", body)

    body = ""
    for i, case in enumerate(CASES):
        x, y = (i % 2) * 7.4, -(i // 2) * 4.7
        body += rf"\begin{{axis}}[ealaxis,at={{({x}cm,{y}cm)}},anchor=north west,width=7.2cm,height=4.3cm," + "\n"
        body += rf"title={{{chr(97+i)}) {NAMES[i]}}},xmin=0,xmax=10,ymin=0,ymax=103,xtick={{0,2,4,6,8,10}},ytick={{0,50,100}},ymajorgrids," + "\n"
        body += r"xlabel={Session (0 = donor)},ylabel={Correct (\%)},legend style={at={(.5,1.05)},anchor=south}]" + "\n"
        for arm, style in [("eal", "ealteal,solid,mark=triangle*"),("ordinary", "black!65,dashed,mark=diamond*")]:
            data = results["by_position"][case][arm]
            body += rf"\addplot[{style},mark size=1.4pt,line width=.8pt] coordinates {{" + coords([(k,100*v["bounds"][0]) for k,v in enumerate(data)]) + "};\n"
            for k,v in enumerate(data):
                lo,hi=v["bounds"]
                if hi>lo:
                    body += rf"\addplot[forget plot,{'ealteal' if arm=='eal' else 'black!65'},line width=1.8pt] coordinates {{" + coords([(k,100*lo),(k,100*hi)]) + "};\n"
        body += r"\end{axis}" + "\n"
    figure("session-profiles",body)

    ratios=results["paired_token_ratios"]
    xmax=max(1.05, math.ceil(max(v["ratio"] for v in ratios)*10)/10)
    body=rf"\begin{{axis}}[ealaxis,width=14.8cm,height=6.8cm,xmin=0,xmax={xmax},ymin=0,ymax=1.02,"+"\n"
    body+=r"xlabel={Cumulative token ratio (EAL/2 / ordinary)},ylabel={Fraction of paired blocks},ytick={0,.25,.5,.75,1},ymajorgrids,legend pos=south east]"+"\n"
    for model,style,label in [("plain","ealteal,solid","GPT-4.1 nano recipients"),("reasoning","black!65,dashed","GPT-5 nano recipients")]:
        values=sorted(v["ratio"] for v in ratios if v["receiver"]==model)
        points=[(0,0)]
        for j,v in enumerate(values):
            points.extend([(v,j/len(values)),(v,(j+1)/len(values))])
        points.append((xmax,1))
        body+=rf"\addplot[{style},line width=.9pt] coordinates {{"+coords(points)+"};\n"
        body+=rf"\addlegendentry{{{label} ($n={len(values)}$)}}"+"\n"
    body+=r"\addplot[black!50,densely dotted,line width=.7pt,forget plot] coordinates {(1,0) (1,1)};"+"\n"
    body+=r"\node[font=\fontsize{8.5}{10}\selectfont,anchor=west] at (axis cs:1.02,.55) {Equal tokens};"+"\n"+r"\end{axis}"
    figure("paired-token-ratios",body)

    body=r"\begin{axis}[ealaxis,width=14.8cm,height=6.8cm,xmin=0,xmax=10,ymin=-5,ymax=55,xtick={0,2,4,6,8,10},ytick={0,10,20,30,40,50},ymajorgrids,"+"\n"
    body+=r"xlabel={Recipient horizon (0 = donor only)},ylabel={Aggregate token reduction (\%)},legend columns=3,legend style={at={(.5,1.04)},anchor=south,column sep=5pt}]"+"\n"
    for field,style,label in [("total_tokens","ealteal,solid,mark=triangle*","Input + output"),("input_tokens","black!50,dashed,mark=diamond*","Input"),("output_tokens","black!80,densely dotted,mark=square*","Output")]:
        points=[(h,100*(1-r["eal"][field]/r["ordinary"][field])) for h,r in enumerate(results["cumulative"])]
        body+=rf"\addplot[{style},line width=.8pt,mark size=1.5pt] coordinates {{"+coords(points)+"};\n"
        body+=rf"\addlegendentry{{{label}}}"+"\n"
    body+=r"\addplot[black!35,dashdotted,line width=.7pt,forget plot] coordinates {(0,20) (10,20)};"+"\n"
    body+=r"\node[anchor=south east,font=\fontsize{8.5}{10}\selectfont] at (axis cs:10,20) {20\% engineering criterion};"+"\n"+r"\end{axis}"
    figure("cumulative-tokens",body)

    gap=100*results["quality_difference_bounds"][0]
    abs_limit=100*(results["totals"]["eal"]["bounds"][0]-.9)
    body=r"\begin{axis}[ealaxis,width=14.8cm,height=7cm,xmin=0,xmax=15,ymin=0,ymax=65,xtick={0,5,10,15},ytick={0,20,40,60},"+"\n"
    body+=r"xlabel={Adverse EAL/2 coding-error allowance (percentage points)},ylabel={Adverse ordinary coding-error allowance (pp)}]"+"\n"
    body+=r"\addplot[draw=none,fill=ealteal!18] coordinates {"+coords([(0,0),(abs_limit,0),(abs_limit,gap-abs_limit),(0,gap)])+"} \\closedcycle;\n"
    body+=r"\addplot[black!65,dashed,line width=.8pt] coordinates {"+coords([(0,gap),(15,gap-15)])+"};\n"
    body+=r"\addplot[ealteal,line width=.9pt] coordinates {"+coords([(abs_limit,0),(abs_limit,65)])+"};\n"
    body+=r"\node[align=center,font=\fontsize{8.5}{10}\selectfont] at (axis cs:3.5,23) {Both descriptive\\conditions hold};"+"\n"
    body+=r"\node[anchor=north west,align=left,font=\fontsize{8.5}{10}\selectfont] at (axis cs:8.0,63) {90\% correctness boundary\\EAL/2 allowance: 7.71 pp};"+"\n"
    body+=r"\node[anchor=north east,align=right,font=\fontsize{8.5}{10}\selectfont] at (axis cs:14.6,42) {Positive correctness gap\\below dashed boundary};"+"\n"+r"\end{axis}"
    figure("coding-sensitivity",body)


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
    assert len(rows)==384 and len(calls)==len(raw_calls)==5453
    assert set(plan["cases"])==set(CASES) and plan["workers"]==5
    pairs=defaultdict(dict); strata=Counter(); all_ids=[]; statuses=Counter()
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
            code=s["annotation"]["decision_code"]
            assert code in {"ready","not_ready","undetermined","ambiguous"}
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
    assert len(pairs)==192 and all(set(p)==set(ARMS) for p in pairs.values())
    assert len(strata)==96 and set(strata.values())=={4}
    results={"schema":"earl-jss-results/1","run_id":manifest["run_id"],
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
    close(results["token_reduction"],original["token_reduction"])
    for lower,upper,width,key,interval_key in [
            (qlo,qhi,2,"quality_sampling_half_width","quality_interval"),
            (elo,ehi,1,"absolute_quality_sampling_half_width","eal_correctness_interval")]:
        allowance = radius(lower,upper,width,.05/6)
        close(allowance,original[key])
        interval = [max(1-width,statistics.mean(lower)-allowance),
                    min(1,statistics.mean(upper)+allowance)]
        for computed,retained in zip(interval,original[interval_key]):close(computed,retained)
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
         r"& \multicolumn{2}{c}{EAL/2} & \multicolumn{2}{c}{Ordinary notes}\\"+"\n"+
         r"\cmidrule(lr){2-3}\cmidrule(l){4-5}"+"\n"+
         r"Case & C/I/U & Correct (\%) & C/I/U & Correct (\%)\\\midrule"+"\n"+
         "\n".join(case_lines)+"\n"+r"\bottomrule\end{tabular}"+"\n")
    config_lines=[]
    for x in results["by_configuration"]:
        config_lines.append(" & ".join(["On" if x["native_tools"] else "Off","4.1 nano" if x["receiver"]=="plain" else "5 nano (low)","EAL/2" if x["arm"]=="eal" else "Ordinary",str(x["correct"]),str(x["incorrect"]),str(x["unknown"]),percent_bounds(x['bounds'])])+r" \\")
    emit("results/configuration-rows.tex",r"\begin{tabular}{@{}lllrrrr@{}}\toprule"+"\n"+
         r"Tools & Recipient & Workflow & C & I & U & Correct (\%)\\\midrule"+"\n"+
         "\n".join(config_lines)+"\n"+r"\bottomrule\end{tabular}"+"\n")
    resource_lines=[]
    for label,field,fmt in [("Input tokens","input_tokens",",.0f"),("Output tokens","output_tokens",",.0f"),("Input + output tokens","total_tokens",",.0f"),("API attempts","attempts",",.0f"),("Native probe calls","native_probes",",.0f"),("Host acquisitions","host_collections",",.0f"),("Host observation reuses","host_reuses",",.0f"),("Estimated API cost (USD)","cost_usd",".6f")]:
        values=[label]+[format(results["resources"][arm][stage][field],fmt) for arm in ARMS for stage in ["initial","recipients","total"]]
        resource_lines.append(" & ".join(values)+r" \\")
    emit("results/resource-rows.tex",r"\begin{tabular}{@{}lrrrrrr@{}}\toprule"+"\n"+
         r"& \multicolumn{3}{c}{EAL/2} & \multicolumn{3}{c}{Ordinary notes}\\"+"\n"+
         r"\cmidrule(lr){2-4}\cmidrule(l){5-7}"+"\n"+
         r"Measure & Initial & Recipients & Total & Initial & Recipients & Total\\\midrule"+"\n"+
         "\n".join(resource_lines)+"\n"+r"\bottomrule\end{tabular}"+"\n")
    figures(results)
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
