"""Read synthetic external measurement state using EAL's tool envelope."""
import json
from pathlib import Path
import sys

if __name__ == "__main__":
    request = json.load(sys.stdin)
    output = json.loads(Path(sys.argv[1]).read_text())
    output["context"] = request["context"]
    output["request"] = {key: request[key] for key in ("tool", "tool_version", "input", "context")}
    print(json.dumps(output))
