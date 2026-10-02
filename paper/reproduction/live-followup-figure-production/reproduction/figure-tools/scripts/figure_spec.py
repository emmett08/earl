#!/usr/bin/env python3
"""Validate declared figure meaning and reproducibility, without executing recipes."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
from pathlib import Path
import re
import sys

try:
    import jsonschema
except ImportError:
    jsonschema = None

SCHEMA_PATH = Path(__file__).resolve().parents[1] / "assets" / "figure-spec.schema.json"
TARGET_DEFAULTS = {
    "width_mode": "maximum", "width_tolerance_mm": 0.5,
    "min_math_script_pt": 6, "min_stroke_pt": 0.35,
    "minimum_raster_dpi": 300,
    "expected_labels": [], "prohibit_block_circle_diagrams": True,
}


class SpecError(ValueError):
    """The figure specification or a declared local input failed validation."""


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _finite_errors(value, location="spec"):
    if isinstance(value, float) and not math.isfinite(value):
        return [f"{location}: non-finite number is not valid JSON data"]
    if isinstance(value, dict):
        return [error for key, item in value.items()
                for error in _finite_errors(item, f"{location}.{key}")]
    if isinstance(value, list):
        return [error for index, item in enumerate(value)
                for error in _finite_errors(item, f"{location}[{index}]")]
    return []


def validate_spec(spec, base_dir=None, check_files=False) -> list[str]:
    """Return structural, declared-relation and optional local-file errors.

    Does not mutate the supplied object, retrieve URLs, execute a recipe, or infer
    whether prose, calculations or visual semantics are scientifically correct.
    """
    if jsonschema is None:
        return ["jsonschema is required; install it with python3 -m pip install jsonschema"]
    try:
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        validator = jsonschema.Draft202012Validator(schema)
        errors = [f"spec{''.join(f'[{part!r}]' for part in error.absolute_path)}: {error.message}"
                  for error in sorted(validator.iter_errors(spec), key=lambda e: str(list(e.absolute_path)))]
    except (OSError, json.JSONDecodeError, jsonschema.SchemaError) as exc:
        return [f"cannot load figure specification schema: {exc}"]
    errors.extend(_finite_errors(spec))
    if errors:
        return errors

    namespaces = {}
    for collection in ("inputs", "quantities", "constructions", "encodings"):
        items = spec.get(collection, [])
        ids = [item["id"] for item in items]
        for duplicate in sorted({identifier for identifier in ids if ids.count(identifier) > 1}):
            errors.append(f"{collection}: duplicate id {duplicate!r}")
        namespaces[collection] = set(ids)

    def check_refs(item, field, collection, owner):
        for reference in item.get(field, []):
            if reference not in namespaces[collection]:
                errors.append(f"{owner}.{field}: unknown {collection} reference {reference!r}")

    for quantity in spec.get("quantities", []):
        owner = f"quantity {quantity['id']}"
        check_refs(quantity, "input_ids", "inputs", owner)
        missing = quantity["missingness"]
        fill = missing.get("fill_missing_with")
        explicit_zero = fill == 0 if not isinstance(fill, str) else fill.strip() in {"0", "0.0", "0.00"}
        if explicit_zero and not missing.get("justification", "").strip():
            errors.append(f"{owner}: fill_missing_with=0 requires an explicit justification")
        if quantity.get("status", "available") == "missing" and missing["state"] != "missing":
            errors.append(f"{owner}: missing status requires missingness.state=missing")
        if missing["state"] == "missing" and quantity.get("status", "available") != "missing":
            errors.append(f"{owner}: missingness.state=missing requires status=missing")
        if quantity.get("sample", {}).get("denominator") == 0 and quantity.get("status", "available") != "missing":
            errors.append(f"{owner}: an empty sample must have status=missing, not an available estimate")
        if "coverage" in quantity["uncertainty"] and quantity["uncertainty"]["kind"] != "interval":
            errors.append(f"{owner}: interval coverage requires uncertainty.kind=interval")

    for construction in spec.get("constructions", []):
        check_refs(construction, "input_ids", "inputs", f"construction {construction['id']}")

    blocked = re.compile(r"\b(?:blocks?|box(?:es)?|rectangles?|rectangular|circles?|circular)\b", re.I)
    ban = spec["target"].get("prohibit_block_circle_diagrams", True)
    for encoding in spec["encodings"]:
        owner = f"encoding {encoding['id']}"
        check_refs(encoding, "quantity_ids", "quantities", owner)
        check_refs(encoding, "construction_ids", "constructions", owner)
        if ban and encoding["mark_role"] == "diagram_node" and blocked.search(encoding["marks"]):
            errors.append(f"{owner}: block/box/rectangle/circle diagram nodes are prohibited")
        mapping = encoding["scale_or_mapping"]
        if encoding["interpretation"] == "quantitative":
            if mapping["type"] in {"nominal", "nonmetric"}:
                errors.append(f"{owner}: quantitative interpretation requires a quantitative scale")
            if mapping["type"] in {"linear", "log"}:
                domain = mapping.get("domain", [])
                if (len(domain) != 2 or any(isinstance(value, bool) or not isinstance(value, (int, float)) for value in domain)):
                    errors.append(f"{owner}: {mapping['type']} scale requires a two-number domain")
                elif domain[0] >= domain[1]:
                    errors.append(f"{owner}: scale domain must be increasing")
                elif mapping["type"] == "log" and domain[0] <= 0:
                    errors.append(f"{owner}: logarithmic scale domain must be positive")
        if encoding["interpretation"] == "categorical" and not mapping.get("domain"):
            errors.append(f"{owner}: categorical mapping requires declared domain categories")

    target = spec["target"]
    script_floor = target.get("min_math_script_pt", 6)
    if script_floor > target["min_text_pt"]:
        errors.append("target: min_math_script_pt cannot exceed min_text_pt")
    exceptions = target.get("font_exceptions", [])
    texts = [exception["text"] for exception in exceptions]
    if len(set(texts)) != len(texts):
        errors.append("target.font_exceptions: exact exception text must be unique")
    for exception in exceptions:
        if exception["min_text_pt"] < script_floor:
            errors.append(f"target.font_exceptions: {exception['text']!r} is below min_math_script_pt")

    base = Path(base_dir).resolve() if base_dir is not None else None
    if check_files and base is None:
        errors.append("base_dir is required when check_files=True")
    path_base = base or Path.cwd()
    def resolved(path):
        try:
            return (path_base / path).resolve()
        except (OSError, RuntimeError) as exc:
            errors.append(f"path {path!r}: cannot resolve within the build root: {exc}")
            return (path_base / path).absolute()

    profile_a, profile_b = target.get("manuscript_profile"), spec["build"].get("profile")
    if profile_a and profile_b and resolved(profile_a) != resolved(profile_b):
        errors.append("target.manuscript_profile and build.profile must resolve to the same file")

    input_paths = [(f"input {item['id']}", item["path"], item.get("sha256"))
                   for item in spec["inputs"] if "path" in item]
    required_paths = input_paths + [("build.source", spec["build"]["source"], None)]
    required_paths.extend(("build.dependencies", path, None) for path in spec["build"]["dependencies"])
    if profile_a or profile_b:
        required_paths.append(("manuscript profile", profile_a or profile_b, None))
    all_paths = [(label, path) for label, path, _ in required_paths]
    all_paths.extend((f"build.outputs.{key}", path) for key, path in spec["build"]["outputs"].items())
    for label, path in all_paths:
        if ".." in Path(path).parts:
            errors.append(f"{label}: parent traversal is not permitted; place the spec at the project build root")
        if base is not None and not resolved(path).is_relative_to(base):
            errors.append(f"{label}: resolved path escapes the specification build root")
    outputs = [(key, resolved(path)) for key, path in spec["build"]["outputs"].items()]
    protected = {resolved(path) for _, path, _ in required_paths}
    if len({path for _, path in outputs}) != len(outputs):
        errors.append("build.outputs: output paths must be distinct")
    for key, path in outputs:
        if path in protected:
            errors.append(f"build.outputs.{key}: output would overwrite a source, input, dependency or profile")

    if check_files and base is not None:
        for label, path, digest in required_paths:
            actual = resolved(path)
            try:
                if not actual.is_file():
                    errors.append(f"{label}: local file does not exist: {path}")
                elif digest and sha256_file(actual) != digest.lower():
                    errors.append(f"{label}: SHA-256 mismatch: {path}")
            except OSError as exc:
                errors.append(f"{label}: cannot read local file {path}: {exc}")
    return errors


def load_spec(path, check_files=True) -> dict:
    """Read and validate a specification, returning a copy with target defaults."""
    path = Path(path)
    try:
        spec = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SpecError(f"cannot read figure specification {path}: {exc}") from exc
    errors = validate_spec(spec, path.parent, check_files)
    if errors:
        raise SpecError("\n".join(errors))
    spec = copy.deepcopy(spec)
    for key, value in TARGET_DEFAULTS.items():
        spec["target"].setdefault(key, copy.deepcopy(value))
    return spec


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("spec", type=Path)
    parser.add_argument("--check-files", action="store_true", help="check local paths and supplied input hashes")
    args = parser.parse_args(argv)
    try:
        spec = load_spec(args.spec, check_files=args.check_files)
    except SpecError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(json.dumps({"valid": True, "figure_id": spec["figure_id"], "files_checked": args.check_files,
                      "semantic_correctness": "requires review"}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
