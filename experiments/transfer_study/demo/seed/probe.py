"""Synthetic project collector for the handover harness demo."""

import json
import sys
from pathlib import Path

raw = sys.stdin.read()
request = json.loads(raw) if raw.strip() else None
measurement = json.loads(Path("measurement.json").read_text(encoding="utf-8"))
output = {"value": {"ready": measurement["ready"]},
          "observed_at": measurement["observed_at"]}
if request is not None:
    output["context"] = request["context"]
    output["request"] = {key: request[key] for key in
                         ("tool", "tool_version", "input", "context")}
print(json.dumps(output))
