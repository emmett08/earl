"""Scripted client for coordinator command-adapter smoke checks; no model runs.

This program deliberately returns no live execution receipt. Select
software_test mode. Native trials must use genuinely separate worker contexts.
"""
from __future__ import annotations

import json
import subprocess
import sys


def main():
    context = json.load(sys.stdin)
    anchor = context["task"]
    task = anchor["task"]
    incoming = context["received_messages"][0]
    arguments = list(context["gateway"]["argv"])
    if context["role"] == "reviewer":
        arguments.extend(["--finding-id", incoming["finding_id"]])
    result = subprocess.run(arguments, check=True, capture_output=True, text=True, timeout=120)
    finding = json.loads(result.stdout)
    consumed = [incoming["message_id"]]
    if context["role"] == "assessor":
        message = {"schema": "EAL/MAS-coordination/3", "message_id": "finding",
                   "task_id": task["task_id"], "task_digest": anchor["task_digest"],
                   "sender": "assessor", "recipient": "reviewer", "reply_to": incoming["message_id"],
                   "attempt": 0, "finding_id": finding["finding_id"]}
        if finding["check"]["ok"]:
            message.update(kind="outcome", assessment_refs={claim: row["assessment_id"] for claim, row in finding["assessments"].items()})
        else:
            code = finding["check"]["code"]
            message.update(kind="disposition", code=code,
                           outcome="incomplete" if code in {"evidence_unavailable", "effect_outcome_unknown"} else "rejected")
        response = {"message": message, "consumed_message_ids": consumed}
    else:
        claims = {claim: {key: None if claim not in finding["assessments"] else finding["assessments"][claim][key]
                          for key in ("assessment_id", "status", "assessed_at")} for claim in task["claims"]}
        conclusion = ("assessed" if finding["check"]["ok"] else "unresolved" if finding["check"]["code"] in {"evidence_unavailable", "effect_outcome_unknown"} else "out_of_scope")
        answer = {"task_digest": anchor["task_digest"], "finding_id": finding["finding_id"], "claims": claims,
                  "scope": {"context": task["requirements"]["context"], "requirements": task["requirements"]},
                  "conclusion": conclusion, "qualification": "conditional_on_registered_argument"}
        response = {"answer": answer, "consumed_message_ids": consumed}
    print(json.dumps(response, allow_nan=False))


if __name__ == "__main__":
    main()
