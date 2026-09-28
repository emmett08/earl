"""Deterministic transport fixture; its answers are not study observations."""

from __future__ import annotations

import json
import sys


def main() -> None:
    request = json.load(sys.stdin)
    if request.get("schema") != "EAL/transfer-model-request/1":
        raise SystemExit("Invalid fixture request")
    content = "Fixture response to: " + request["messages"][-1]["content"].strip()
    print(json.dumps({"schema": "EAL/transfer-model-response/1",
                      "model_version": request["model_version"],
                      "reported_model": request["model_version"],
                      "content": content,
                      "usage": {"input_tokens": 10, "output_tokens": 8},
                      "cost": 0.0}))


if __name__ == "__main__":
    main()
