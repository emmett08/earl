"""Collect the frozen architecture observations, assess both sources and export ASPIC+.

Run from any directory with ``python experiments/architecture_extension/run_eal.py``
after installing this repository. The default output directory is
``results/replay``; it never replaces the captured ``results/`` assessment and
browser input. Choose a fresh ``--output-dir`` for another replay.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta
import hashlib
import json
from pathlib import Path
import tempfile

from jsonschema import Draft202012Validator

from eal.aspic_export import export_aspic_view
from eal.runtime import ReasoningService


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
RESULTS = HERE / "results"
CONTEXT = {"experiment": "architecture-extension-v1", "dataset": "local-fixture"}


def write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, sort_keys=True, indent=2, ensure_ascii=False,
                               allow_nan=False) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=RESULTS / "replay",
                        help="New directory for a replay; existing result files are never overwritten")
    args = parser.parse_args()
    output_dir = args.output_dir.resolve()
    targets = ("treatment-collection.json", "treatment-assessment.json",
               "comparison-collection.json", "comparison-assessment.json",
               "compiled-aspic.json", "aspic-view.json", "eal-run.json")
    if any((output_dir / name).exists() for name in targets):
        raise FileExistsError("EAL output already exists; choose a fresh --output-dir")
    output_dir.mkdir(parents=True, exist_ok=True)
    report_bytes = (RESULTS / "observations.json").read_bytes()
    report = json.loads(report_bytes)
    treatment_bytes = (HERE / "architecture.eal").read_bytes()
    comparison_bytes = (HERE / "observed-results.eal").read_bytes()
    treatment_sha = hashlib.sha256(treatment_bytes).hexdigest()
    if treatment_sha != report["provenance"]["eal_sha256"]:
        raise ValueError("Treatment source differs from frozen pre-run EAL digest in report")
    assessed_at = (datetime.fromisoformat(report["provenance"]["observed_at"])
                   + timedelta(seconds=1)).isoformat()

    with tempfile.TemporaryDirectory(prefix="architecture-eal-") as folder:
        service = ReasoningService(ROOT, HERE / "eal-tools.toml",
                                   Path(folder) / "assessment.sqlite3")
        outputs = {}
        for name, source_bytes in (("treatment", treatment_bytes),
                                   ("comparison", comparison_bytes)):
            source = source_bytes.decode("utf-8")
            validation = service.validate(source)
            if not validation["valid"]:
                raise ValueError(f"{name} EAL invalid: {validation['diagnostics']}")
            collection = service.collect(source, CONTEXT)
            if any(record["status"] != "ok" for record in collection["records"].values()):
                raise ValueError(f"{name} observation collection failed: " +
                                 repr({key: value.get("error") for key, value in
                                       collection["records"].items() if value["status"] != "ok"}))
            assessment = service.reason(source, CONTEXT, collection["collection_id"], assessed_at)
            write_json(output_dir / f"{name}-collection.json", collection)
            write_json(output_dir / f"{name}-assessment.json", assessment)
            outputs[name] = {"source_sha256": hashlib.sha256(source_bytes).hexdigest(),
                             "collection_id": collection["collection_id"],
                             "assessment_id": assessment["assessment_id"],
                             "claim_statuses": {key: value["status"] for key, value in
                                                assessment["claims"].items()}}
            if name == "comparison":
                compiled = service.compile_aspic(source, CONTEXT, collection["collection_id"],
                                                  "local_check_tie", assessed_at)
                graph = export_aspic_view(compiled)
                schema = json.loads((ROOT / "docs/aspic-view.schema.json").read_text())
                Draft202012Validator(schema).validate(graph)
                write_json(output_dir / "compiled-aspic.json", compiled)
                write_json(output_dir / "aspic-view.json", graph)
                outputs[name].update({
                    "compiled_profile": compiled["profile"],
                    "formal_goal_status": compiled["formal"]["grounded_status"],
                    "formal_claim_status": compiled["claim_status"],
                    "authored_claim_status": compiled["authored_claim_status"],
                    "argument_count": len(compiled["formal"]["arguments"]),
                    "defeat_count": len(compiled["formal"]["defeats"]),
                    "snapshot_digest": compiled["snapshot_digest"],
                    "route_statuses": {key: value["status"] for key, value in
                                       compiled["routes"].items()},
                })

    run = {"schema": "architecture-eal-run/1", "context": CONTEXT,
           "assessed_at": assessed_at,
           "report_sha256": hashlib.sha256(report_bytes).hexdigest(),
           "treatment_source_sha256_in_report": report["provenance"]["eal_sha256"],
           "outputs": outputs,
           "visualisation_input": str(output_dir / "aspic-view.json")}
    write_json(output_dir / "eal-run.json", run)
    print(json.dumps({"assessed_at": assessed_at,
                      "treatment": outputs["treatment"]["claim_statuses"],
                      "comparison": outputs["comparison"]["claim_statuses"],
                      "formal_goal_status": outputs["comparison"]["formal_goal_status"],
                      "argument_count": outputs["comparison"]["argument_count"],
                      "defeat_count": outputs["comparison"]["defeat_count"],
                      "visualisation_input": str(output_dir / "aspic-view.json")}, indent=2))


if __name__ == "__main__":
    main()
