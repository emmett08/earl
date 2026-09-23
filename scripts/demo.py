"""Run reproducible reasoning scenarios through the shared production service."""
import argparse
import json
from pathlib import Path
import tempfile

from eal.runtime import ReasoningService


def main():
    parser = argparse.ArgumentParser()
    choice = parser.add_mutually_exclusive_group()
    choice.add_argument("--live", action="store_true")
    choice.add_argument("--mixed", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    prefix = "live" if args.live else "mixed-reasoning" if args.mixed else "latency"
    registry = "live-tools.toml" if args.live else "mixed-tools.toml" if args.mixed else "tools.toml"
    context_file = "live-context.json" if args.live else "mixed-context.json" if args.mixed else "context.json"
    source = (root / "examples" / f"{prefix}.eal").read_text()
    context = json.loads((root / "examples" / context_file).read_text())
    with tempfile.TemporaryDirectory() as temporary:
        service = ReasoningService(root, root / "examples" / registry, Path(temporary) / "runs.sqlite3")
        validation = service.validate(source)
        if not validation["valid"]:
            raise SystemExit(json.dumps(validation, indent=2))
        collection = service.collect(source, context)
        errors = {name:record.get("error") for name,record in collection["records"].items() if record["status"] != "ok"}
        if errors:
            raise SystemExit(json.dumps(errors, indent=2))
        result = service.reason(source, context, collection["collection_id"], None if args.live else "2026-09-23T01:00:00Z")
        print(json.dumps({"scenario":prefix, "claims":result["claims"], "arguments":result["arguments"]}, indent=2))
        if not any(claim["status"] == "supported" for claim in result["claims"].values()):
            raise SystemExit("No supported example conclusion")
        if not args.live and not args.mixed:
            expired = service.reason(source, context, collection["collection_id"], "2026-09-24T01:00:00Z")
            print(json.dumps({"scenario":"expired calibration", "assumptions":expired["assumptions"], "claims":expired["claims"]}, indent=2))
            if any(claim["status"] == "supported" for claim in expired["claims"].values()):
                raise SystemExit("An expired assumption incorrectly retained dependent support")


if __name__ == "__main__":
    main()
