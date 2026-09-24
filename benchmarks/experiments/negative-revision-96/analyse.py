"""Read-only summary of all assigned slots, including malformed/failed calls."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
from statistics import median

CLAIMS=("bounded_property_supported","violating_sample","qualified_absence")


def analyse(path: Path) -> dict:
    frozen=json.loads((path/"freeze.json").read_text())
    ledger=json.loads((path/"ledger.json").read_text())
    if frozen["sha256"]!=ledger["freeze_sha256"]:
        raise ValueError("Freeze and ledger mismatch")
    rows=ledger["attempts"]
    if any(row["index"]!=i or row["root"]!=frozen["cases"][i]["root"] for i,row in enumerate(rows)):
        raise ValueError("Attempt identity/order mismatch")
    out={"schema":"eal2-negative-revision-96-analysis/1","status":ledger["status"],
         "freeze_sha256":frozen["sha256"],"assigned":len(frozen["cases"]),"attempted":len(rows),
         "completed":sum(r["status"]=="completed" for r in rows),
         "failed":sum(r["status"]=="failed" for r in rows),
         "unattempted":len(frozen["cases"])-len(rows),
         "stage_counts":{},"limitations":[
            "Eight selected roots share one generated argument scaffold and sampled-negative method; root and turn observations are dependent.",
            "No independently human-adjudicated reference, masked human authoring-fidelity score or authenticated physical acquisition.",
            "Configured provider rates are an estimate; human author/review and acquisition expenditure are unmeasured."]}
    cost=0.;unknown_cost=0;tokens=Counter();durations=[]
    by_root=defaultdict(dict)
    for row in rows:
        usage=row.get("usage")
        if usage and usage.get("cost_usd") is not None:
            cost+=usage["cost_usd"]
            for k in ("input_tokens","output_tokens","cached_input_tokens"):
                tokens[k]+=usage.get(k,0)
        else: unknown_cost+=1
        if row.get("duration_seconds") is not None:
            durations.append(row["duration_seconds"])
        if row["status"]=="completed":
            by_root[(row["stage"],row["view"],row["root"])][row["turn"]]=row
    out["provider_usage"]={"input_tokens":tokens["input_tokens"],"output_tokens":tokens["output_tokens"],
                           "cached_input_tokens":tokens["cached_input_tokens"],
                           "configured_rate_cost_usd":round(cost,9),"missing_cost_records":unknown_cost,
                           "median_api_seconds":median(durations) if durations else None,
                           "total_api_seconds":sum(durations)}
    for stage in ("A","B"):
        for view in ("eal","generic"):
            selected=[r for r in rows if r["stage"]==stage and r["view"]==view]
            complete=[r for r in selected if r["status"]=="completed"]
            key=f"{stage}/{view}"
            out["stage_counts"][key]={"assigned":24,"attempted":len(selected),"completed":len(complete),
                "all_claims_correct":sum(r["all_claims_correct"] for r in complete),
                "false_support":sum(r["false_support"] for r in complete),
                "malformed_or_rejected":sum((not r.get("recipient",{}).get("valid",True)) if stage=="A" else not r["author_feedback"]["accepted"] for r in complete),
                "full_suite_replay_correct":sum(r.get("finite_suite_replay",{}).get("all_three",False) for r in complete) if stage=="B" else None,
                "whole_sequences_correct":sum(
                    len(by_root.get((stage,view,root["id"]),{}))==3 and all(
                        by_root[(stage,view,root["id"])][t]["all_claims_correct"] for t in range(3))
                    for root in frozen["roots"]),
                "per_root":{root["id"]:{"states":{
                    state: (by_root.get((stage,view,root["id"]),{}).get(t) or {}).get("all_claims_correct")
                    for t,state in enumerate(("covered_clear","partial_violation","wrong_scope_restore"))}}
                    for root in frozen["roots"]}}
    out["interpretation"]="Finite developmental outcomes only; canonical checkers matching the same authored oracle do not demonstrate EAL-specific superiority. Stage B syntax and state replay do not measure independent brief fidelity."
    return out


def main() -> None:
    parser=argparse.ArgumentParser()
    parser.add_argument("run_dir",type=Path)
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args()
    result=analyse(args.run_dir)
    if args.output.exists():
        raise SystemExit("Refusing to replace an existing analysis")
    args.output.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
    print(json.dumps({k:result[k] for k in ("status","assigned","completed","provider_usage")},sort_keys=True))


if __name__=="__main__":
    main()
