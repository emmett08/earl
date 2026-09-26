"""Trusted operator adapter for the coolant-loop EAL and typed-rule source files.

Execute this through ``python -m experiments.authoring_revision replay`` in an
isolated environment. A submitted typed Python module executes arbitrary code.
"""
from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import sys

from experiments.composition_revision import study


def _typed_module(path: Path):
    name = "submitted_cooling_rules"
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ValueError("Cannot load submitted typed implementation")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def main() -> None:
    source = Path(os.environ["EAL_STUDY_SOURCE"])
    bundle = json.loads(Path(os.environ["EAL_STUDY_CASES"]).read_text(encoding="utf-8"))
    arm = os.environ["EAL_STUDY_ARM"]
    if (bundle.get("schema") != "eal-authoring-cases/1"
            or bundle.get("stage") != os.environ["EAL_STUDY_STAGE"]
            or bundle.get("task_id") != os.environ["EAL_STUDY_TASK"]
            or not isinstance(bundle.get("cases"), dict)
            or not isinstance(bundle.get("target_claims"), list)):
        raise ValueError("Invalid frozen cooling case bundle")
    if arm == "eal2":
        path = source / "cooling.eal"
        if not path.is_file():
            raise ValueError("EAL submission needs cooling.eal")
        kwargs = {"source_path": path}
        study_arm = "eal"
    elif arm == "typed_rules":
        path = source / "baseline.py"
        if not path.is_file():
            raise ValueError("Typed submission needs baseline.py")
        kwargs = {"typed_module": _typed_module(path)}
        study_arm = "typed_rule"
    else:
        raise ValueError("Unknown study arm")
    statuses = {}
    for case_id, case in bundle["cases"].items():
        if not isinstance(case, dict) or not isinstance(case.get("observations"), dict):
            raise ValueError(f"Case {case_id} lacks observations")
        result = study.run_arm(case, study_arm, **kwargs)
        statuses[case_id] = {name: result["claims"][name]
                             for name in bundle["target_claims"] if name in result["claims"]}
    print(json.dumps({"schema": "eal-authoring-results/1", "cases": statuses},
                     sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()
