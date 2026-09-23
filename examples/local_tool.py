"""Real local tools; no model provider or external service is required."""
import hashlib
import json
import sys
import time

request = json.load(sys.stdin)
iterations = request["input"]["iterations"]
if type(iterations) is not int or not 1 <= iterations <= 1000000:
    raise ValueError("iterations must be an integer in [1, 1000000]")
if sys.argv[1] == "inspect":
    value = {"iterations": iterations, "algorithm": "sha256"}
else:
    started = time.perf_counter_ns()
    state = b"EAL example"
    for _ in range(iterations):
        state = hashlib.sha256(state).digest()
    value = {"elapsed_ms": (time.perf_counter_ns() - started) / 1e6, "digest": state.hex()}
print(json.dumps({"value": value, "context": request["context"]}))
