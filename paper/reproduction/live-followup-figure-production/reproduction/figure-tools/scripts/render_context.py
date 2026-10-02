"""Stage declared local inputs and record an inspectable render manifest."""
from __future__ import annotations

import importlib.metadata
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import sys

from build_profile import load_profile, local_file
from figure_spec import TARGET_DEFAULTS, load_spec, sha256_file


class ContextError(ValueError):
    pass


def file_record(path: Path, *, declared_path=None) -> dict:
    record = {"path": str(path), "sha256": sha256_file(path), "bytes": path.stat().st_size}
    if declared_path is not None:
        record["declared_path"] = declared_path
    return record


def prepare_context(args, source: Path) -> dict:
    """Validate provenance declarations; recipes are recorded, never executed."""
    spec_path = getattr(args, "spec", None)
    spec_path = spec_path.resolve() if spec_path else None
    spec_bytes = spec_path.read_bytes() if spec_path else None
    spec = load_spec(spec_path) if spec_path else None
    if spec_path:
        captured_spec = json.loads(spec_bytes)
        for key, value in TARGET_DEFAULTS.items():
            captured_spec["target"].setdefault(key, value)
        if (spec != captured_spec
                or sha256_file(spec_path) != hashlib.sha256(spec_bytes).hexdigest()):
            raise ContextError("Figure specification changed during validation")
    base = spec_path.parent if spec_path else source.parent
    if spec and source != local_file(base, spec["build"]["source"]):
        raise ContextError("CLI source must equal spec.build.source")
    declared_profile = None
    if spec:
        relative = spec["build"].get("profile") or spec["target"].get("manuscript_profile")
        declared_profile = local_file(base, relative) if relative else None
    requested_profile = getattr(args, "profile", None)
    profile_path = requested_profile.resolve() if requested_profile else declared_profile
    if requested_profile and declared_profile and profile_path != declared_profile:
        raise ContextError("CLI profile conflicts with the declared manuscript profile")
    if spec and profile_path and not profile_path.is_relative_to(base):
        raise ContextError("Manuscript profile escapes the specification root")
    profile_bytes = profile_path.read_bytes() if profile_path else None
    profile = load_profile(profile_path) if profile_path else None
    if profile_path and (profile != json.loads(profile_bytes)
                         or sha256_file(profile_path) != hashlib.sha256(profile_bytes).hexdigest()):
        raise ContextError("Manuscript profile changed during validation")
    recipe_engine = spec["build"].get("engine") if spec else None
    if args.engine and recipe_engine and args.engine != recipe_engine:
        raise ContextError("CLI engine conflicts with spec.build.engine")
    profile_engine = (profile or {}).get("engine")
    selected_engine = args.engine or recipe_engine
    if profile_engine and selected_engine and profile_engine != selected_engine:
        raise ContextError("Selected engine conflicts with manuscript profile.engine")
    engine = selected_engine or profile_engine or "pdflatex"
    outputs = spec["build"]["outputs"] if spec else {}
    def destination(flag, output_key):
        requested = getattr(args, flag, None)
        return requested.resolve() if requested else (base / outputs[output_key]).resolve() if output_key in outputs else None
    records = {"source": file_record(source)}
    if spec_path:
        records["specification"] = {"path": str(spec_path), "sha256": hashlib.sha256(spec_bytes).hexdigest(), "bytes": len(spec_bytes)}
    if profile_path:
        records["profile"] = {"path": str(profile_path), "sha256": hashlib.sha256(profile_bytes).hexdigest(), "bytes": len(profile_bytes)}
    return {
        "source": source, "spec": spec, "spec_path": spec_path, "base": base,
        "profile": profile, "profile_path": profile_path, "engine": engine,
        "output": destination("output", "pdf"), "preview": destination("preview", "preview"),
        "audit": destination("audit", "audit"), "qa_dir": getattr(args, "qa_dir", None),
        "records": records,
    }


def stage_context(context: dict, build: Path) -> tuple[str, str | None, dict[Path, dict]]:
    """Copy only declared files, retaining paths relative to their declared roots."""
    staged: dict[Path, dict] = {}
    spec, base = context["spec"], context["base"]
    if context["spec_path"] and sha256_file(context["spec_path"]) != context["records"]["specification"]["sha256"]:
        raise ContextError("Figure specification changed between validation and staging")
    if context["profile_path"] and sha256_file(context["profile_path"]) != context["records"]["profile"]["sha256"]:
        raise ContextError("Manuscript profile changed between validation and staging")
    def stage(original, relative, role):
        relative = Path(relative)
        if relative.is_absolute() or ".." in relative.parts or any(char in str(relative) for char in "{}\n\r"):
            raise ContextError(f"Unsupported staged local path: {relative}")
        target = build / relative
        record = file_record(original, declared_path=str(relative))
        record["role"] = role
        if original == context["source"] and record["sha256"] != context["records"]["source"]["sha256"]:
            raise ContextError("Source changed between validation and staging")
        if target in staged and staged[target]["sha256"] != record["sha256"]:
            raise ContextError(f"Conflicting declared files at: {relative}")
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(original, target)
        if sha256_file(target) != record["sha256"]:
            raise ContextError(f"Declared input changed during staging: {original}")
        staged[target] = record
        return relative.as_posix()
    source_name = spec["build"]["source"] if spec else "figure-input.tex"
    source_name = stage(context["source"], source_name, "source")
    if spec:
        for item in spec["inputs"]:
            if "path" in item:
                stage(local_file(base, item["path"]), item["path"], "input")
        for relative in spec["build"]["dependencies"]:
            stage(local_file(base, relative), relative, "dependency")
    preamble_name = None
    if context["profile"]:
        profile_root = context["profile_path"].parent
        profile_prefix = profile_root.relative_to(base) if profile_root.is_relative_to(base) else Path("_manuscript_profile")
        for relative in context["profile"]["dependencies"]:
            stage(local_file(profile_root, relative), profile_prefix / relative, "profile_dependency")
        relative = context["profile"].get("preamble")
        if relative:
            original = local_file(profile_root, relative)
            preamble_name = stage(original, profile_prefix / relative, "profile_preamble")
            context["records"]["preamble"] = {key: staged[build / preamble_name][key] for key in ("path", "sha256", "bytes")}
    return source_name, preamble_name, staged


def tex_runtime_roots(run, build, timeout) -> list[Path]:
    """Recognise installed TeX distributions and caches, excluding TEXMFHOME."""
    roots = set()
    for variable in ("TEXMFDIST", "TEXMFDEBIAN", "TEXMFLOCAL", "TEXMFSYSCONFIG", "TEXMFSYSVAR", "TEXMFVAR", "TEXMFCONFIG"):
        result = run(["kpsewhich", f"-var-value={variable}"], build, timeout)
        for value in result.stdout.strip().split(":"):
            if value and "$" not in value and "{" not in value:
                path = Path(value.lstrip("!")).resolve()
                if path != Path("/"):
                    roots.add(path)
    return sorted(roots)


def recorder_dependencies(build: Path, staged: dict, runtime_roots: list[Path]) -> list[dict]:
    recorder = build / "wrapper.fls"
    if not recorder.is_file():
        raise ContextError("TeX recorder output is missing; dependencies cannot be inspected")
    records = []
    seen = set()
    generated = {"wrapper.tex", "wrapper.aux", "wrapper.out", "wrapper.toc"}
    for line in recorder.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.startswith("INPUT "):
            continue
        path = Path(line[6:])
        path = (build / path).resolve() if not path.is_absolute() else path.resolve()
        if path in seen or not path.is_file():
            continue
        seen.add(path)
        if path in staged:
            if sha256_file(path) != staged[path]["sha256"]:
                raise ContextError(f"Declared input changed during TeX execution: {path}")
            record = {**staged[path], "staged_path": str(path), "classification": "declared_local"}
        elif path.is_relative_to(build) and path.name in generated:
            record = file_record(path)
            record["classification"] = "generated_build_file"
        elif any(path.is_relative_to(root) for root in runtime_roots):
            record = file_record(path)
            record["classification"] = "tex_runtime"
        else:
            raise ContextError(f"TeX read an undeclared local dependency: {path}")
        records.append(record)
    return records


def typography_and_warnings(build: Path) -> tuple[dict, list[str]]:
    text = (build / "wrapper.log").read_text(encoding="utf-8", errors="replace")
    measurements = {}
    for key in ("LINEWIDTH", "COLUMNWIDTH"):
        match = re.search(rf"FIGURE-{key}-PT=([0-9.]+)pt", text)
        if match:
            measurements[key.lower() + "_tex_pt"] = float(match.group(1))
    warnings = [line.strip() for line in text.splitlines()
                if re.search(r"Warning|Overfull|Underfull|Missing character", line)]
    return measurements, warnings


def runtime_versions(run, build, engine, timeout) -> dict:
    versions = {"python": sys.version.split()[0], "platform": platform.platform()}
    for executable, flag in (("latexmk", "-v"), (engine, "--version"), ("pdfinfo", "-v"), ("pdftoppm", "-v")):
        result = run([executable, flag], build, timeout)
        versions[executable] = result.stdout.strip().splitlines()[0] if result.stdout.strip() else "unknown"
    for package in ("PyMuPDF", "Pillow", "numpy", "jsonschema"):
        try:
            versions[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            versions[package] = "not installed"
    return versions


def complete_report(report: dict, context: dict, build: Path, staged: dict,
                    dependencies: list[dict], versions: dict, artifacts: list[tuple[Path, Path]]) -> dict:
    dimensions, warnings = typography_and_warnings(build)
    provenance = {key: {"path": item["path"], "sha256": item["sha256"]}
                  for key, item in context["records"].items()}
    pdf, destination = next((source, destination) for source, destination in artifacts if destination.suffix.lower() == ".pdf")
    provenance["pdf"] = {"path": str(destination), "sha256": sha256_file(pdf)}
    report.update({
        "schema_version": "1.0", "figure_id": (context["spec"] or {}).get("figure_id"),
        "provenance_status": "recorded build inputs; scientific provenance requires independent review",
        "inputs": context["records"], "provenance": provenance,
        "declared_local_files": list(staged.values()),
        "actual_tex_dependencies": dependencies, "runtime_versions": versions,
        "recorded_recipe": context["spec"]["build"]["recipe"] if context["spec"] else [],
        "tex_environment": {"TEXINPUTS": str(build) + "//:" + os.environ.get("TEXINPUTS", "")},
        "executed_commands": [json.loads(path.read_text(encoding="utf-8").splitlines()[1].removeprefix("Argv: "))
                              for path in sorted(build.glob("command-*.log"))],
        "typography": dimensions, "typesetting_warnings": warnings,
        "artifacts": [{**file_record(source), "destination": str(destination)} for source, destination in artifacts],
    })
    return report


def write_report(report: dict, path: Path):
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
