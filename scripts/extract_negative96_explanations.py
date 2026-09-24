#!/usr/bin/env python3
"""Extract every completed or failed Stage A explanation for post-call review.

The review packet retains the exact user/system exposure and reference status,
while route/root metadata live in a separate linkage file. Syntax is visible in
the prompt, so reviewers cannot be fully blinded to representation.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import random


def canonical(value):
    return json.dumps(value,sort_keys=True,separators=(",",":"),ensure_ascii=False,allow_nan=False).encode()


def sha(data: bytes):
    return hashlib.sha256(data).hexdigest()


def run(run_dir: Path, output: Path):
    freeze_file, ledger_file=run_dir/"freeze.json",run_dir/"ledger.json"
    freeze=json.loads(freeze_file.read_text())
    ledger_bytes=ledger_file.read_bytes()
    ledger=json.loads(ledger_bytes)
    if ledger["status"]!="complete" or len(ledger["attempts"])!=96 or len(freeze["cases"])!=96:
        raise ValueError("Terminal complete 96-call ledger is required")
    if freeze["sha256"]!=ledger["freeze_sha256"]:
        raise ValueError("Freeze/ledger identity mismatch")
    links=[];items=[]
    for case,row in zip(freeze["cases"],ledger["attempts"]):
        if (case["index"]!=row["index"] or case["stage"]!=row["stage"]
                or case["root"]!=row["root"] or case["state"]!=row["state"]):
            raise ValueError("Attempt/order identity mismatch")
        if case["stage"]!="A":
            continue
        item_id=sha(canonical({"freeze":freeze["sha256"],"index":case["index"]}))[:24]
        response=(row.get("response") or {}).get("text")
        items.append({"item_id":item_id,"prompt":row["messages"],
                      "reference_statuses":case["expected"],
                      "reference_scope":"Submitted synthetic records and sampled finite interval only; no physical or continuous-time assertion",
                      "response_text":response,"response_sha256":sha(response.encode()) if response is not None else None,
                      "attempt_status":row["status"],"recipient_parse":row.get("recipient")})
        links.append({"item_id":item_id,"case_index":case["index"],"root":case["root"],
                      "state":case["state"],"view":case["view"],"response_sha256":items[-1]["response_sha256"]})
    if len(items)!=48:
        raise ValueError("Expected all 48 assigned Stage A items")
    random.Random(96096).shuffle(items)
    header={"schema":"negative-revision-96-explanation-review/1","freeze_sha256":freeze["sha256"],
            "ledger_sha256":sha(ledger_bytes),"assigned_items":48,"blinding":"model and route/root metadata withheld; actual formal syntax remains visible in prompt"}
    packet={**header,"items":items}
    packet["packet_sha256"]=sha(canonical(packet))
    output.mkdir(parents=True,exist_ok=False)
    (output/"reviewer_items.json").write_text(json.dumps(packet,indent=2,sort_keys=True,ensure_ascii=False)+"\n")
    (output/"arm_root_linkage.json").write_text(json.dumps({**header,"packet_sha256":packet["packet_sha256"],"links":links},indent=2,sort_keys=True,ensure_ascii=False)+"\n")
    print(json.dumps({"count":len(items),"packet_sha256":packet["packet_sha256"],"ledger_sha256":header["ledger_sha256"]},sort_keys=True))


if __name__=="__main__":
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("run_dir",type=Path)
    ap.add_argument("output",type=Path)
    a=ap.parse_args()
    run(a.run_dir,a.output)
