#!/usr/bin/env python3
"""Compile an include-ready TikZ figure and perform deterministic PDF checks."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))


FORBIDDEN_SOURCE = {
    r"\\documentclass": "document classes belong in the temporary wrapper",
    r"\\begin\s*\{document\}": "the source must be include-ready",
    r"\\begin\s*\{figure\*?\}": "figure floats belong in the manuscript",
    r"\\caption\s*\{": "captions belong in the manuscript",
    r"\\(?:resizebox|scalebox)\s*\{": "design at final size instead of scaling",
}

DISCOURAGED_FONT_COMMANDS = (
    r"\\tiny\b",
    r"\\scriptsize\b",
)

DEFAULT_PACKAGES = ("amsmath", "amssymb", "mathtools", "bm", "xcolor", "tikz")
DEFAULT_COMMAND_TIMEOUT = 120.0
NUMBER = r"(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)"
PHYSICAL_UNITS = {
    "pt": 1.0,
    "pc": 12.0,
    "in": 72.27,
    "bp": 72.27 / 72.0,
    "cm": 72.27 / 2.54,
    "mm": 72.27 / 25.4,
    "dd": 1238.0 / 1157.0,
    "cc": 12.0 * 1238.0 / 1157.0,
    "sp": 1.0 / 65536.0,
}


class RenderError(RuntimeError):
    pass


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Render one include-ready TikZ source as a cropped PDF and optionally "
            "a 300 dpi PNG for visual QA."
        )
    )
    parser.add_argument("source", type=Path, help="Path to figure-name.tikz.tex")
    parser.add_argument("--output", type=Path, help="Destination PDF")
    parser.add_argument("--preview", type=Path, help="Temporary PNG for visual inspection")
    parser.add_argument(
        "--engine",
        choices=("pdflatex", "lualatex", "xelatex"),
        default=None,
        help="TeX engine used by latexmk",
    )
    parser.add_argument(
        "--keep-build",
        type=Path,
        help="Retain wrapper, log, and auxiliary files in this directory",
    )
    parser.add_argument("--spec", type=Path, help="Validated figure specification JSON")
    parser.add_argument("--profile", type=Path, help="Manuscript typography profile JSON")
    parser.add_argument("--audit", type=Path, help="Destination measured audit JSON")
    parser.add_argument("--qa-dir", type=Path, help="Destination colour/accessibility QA previews")
    parser.add_argument(
        "--timeout", type=float, default=DEFAULT_COMMAND_TIMEOUT,
        help="Maximum seconds per external command (default: 120)",
    )
    return parser.parse_args()


def header_value(text: str, label: str) -> str | None:
    pattern = rf"(?im)^\s*%\s*{re.escape(label)}\s*:\s*(.+?)\s*$"
    match = re.search(pattern, text)
    return match.group(1).strip() if match else None


def parse_csv(value: str | None, label: str) -> list[str]:
    if value is None:
        raise RenderError(f"Missing header comment: % {label}: ...")
    if value.lower() in {"none", "n/a", "not applicable"}:
        return []
    items = [item.strip() for item in value.split(",") if item.strip()]
    token = re.compile(r"^[A-Za-z0-9_.-]+$")
    invalid = [item for item in items if not token.fullmatch(item)]
    if invalid:
        raise RenderError(
            f"Unsupported {label} token(s): {', '.join(invalid)}. "
            "Declare simple package or library names."
        )
    return items


def strip_tex_comments(text: str) -> str:
    """Remove TeX comments, preserving escaped percent signs and line boundaries."""
    result: list[str] = []
    for line in text.splitlines(keepends=True):
        for index, character in enumerate(line):
            if character != "%":
                continue
            backslashes = 0
            cursor = index - 1
            while cursor >= 0 and line[cursor] == "\\":
                backslashes += 1
                cursor -= 1
            if backslashes % 2 == 0:
                result.append(line[:index] + ("\n" if line.endswith("\n") else ""))
                break
        else:
            result.append(line)
    return "".join(result)


def physical_length_pt(value: str, *, implicit_pt: bool = False) -> float:
    units = "|".join(PHYSICAL_UNITS)
    match = re.fullmatch(rf"\s*({NUMBER})\s*({units})?\s*", value)
    if not match or (match.group(2) is None and not implicit_pt):
        raise RenderError(f"Expected a literal physical dimension, found: {value!r}")
    return float(match.group(1)) * PHYSICAL_UNITS[match.group(2) or "pt"]


def validate_source(source: Path, text: str, minimum_override: float | None = None) -> tuple[list[str], list[str], str]:
    if not source.name.endswith(".tikz.tex"):
        raise RenderError("Name the include-ready source figure-name.tikz.tex")
    code = strip_tex_comments(text)
    begins = list(re.finditer(r"\\begin\s*\{tikzpicture\}", code))
    ends = list(re.finditer(r"\\end\s*\{tikzpicture\}", code))
    if len(begins) != 1 or len(ends) != 1 or begins[0].start() >= ends[0].start():
        raise RenderError("The source must contain exactly one complete tikzpicture")

    for pattern, reason in FORBIDDEN_SOURCE.items():
        if re.search(pattern, code):
            raise RenderError(f"Forbidden source construct ({reason}): {pattern}")

    packages = parse_csv(header_value(text, "Required packages"), "Required packages")
    libraries = parse_csv(
        header_value(text, "Required TikZ libraries"), "Required TikZ libraries"
    )
    target_width = header_value(text, "Target width")
    minimum_text = header_value(text, "Minimum text size")
    colour_intent = header_value(text, "Colour/greyscale intent")
    if not target_width:
        raise RenderError("Missing header comment: % Target width: ...")
    target_match = re.match(rf"\s*({NUMBER})\s*(mm|cm|pt|in)\b", target_width)
    if not target_match or float(target_match.group(1)) <= 0:
        raise RenderError("Target width must include a positive physical dimension")
    if not minimum_text:
        raise RenderError("Missing header comment: % Minimum text size: ...")
    size_match = re.match(rf"\s*({NUMBER})\s*pt\b", minimum_text)
    if not size_match:
        raise RenderError("Minimum text size must be declared in pt")
    minimum_pt = float(size_match.group(1))
    if minimum_pt < 6.0:
        raise RenderError("Declared minimum text size is below 6 pt")
    if not colour_intent:
        raise RenderError("Missing header comment: % Colour/greyscale intent: ...")

    for pattern in DISCOURAGED_FONT_COMMANDS:
        if re.search(pattern, code):
            raise RenderError("Do not use \\tiny or \\scriptsize; keep final lettering at least 6 pt")
    font_sizes = list(re.finditer(r"\\fontsize\s*\{([^{}]*)\}", code))
    if len(font_sizes) != len(re.findall(r"\\fontsize\b", code)):
        raise RenderError("Use a literal physical dimension in a braced \\fontsize argument")
    for match in font_sizes:
        font_pt = physical_length_pt(match.group(1), implicit_pt=True)
        if font_pt < (minimum_override if minimum_override is not None else minimum_pt):
            raise RenderError(
                f"Explicit font size {font_pt:g} pt is below the declared "
                f"minimum text size {minimum_pt:g} pt"
            )
    for match in re.finditer(rf"line\s+width\s*=\s*({NUMBER})\s*(pt|mm|cm|in|bp|pc|dd|cc|sp)\b", code):
        if physical_length_pt(match.group(1) + match.group(2)) < 0.35:
            raise RenderError("Explicit line width below 0.35 pt")

    return packages, libraries, target_width


def wrapper_text(packages: list[str], libraries: list[str], **options) -> str:
    from build_profile import wrapper_text as build_wrapper
    return build_wrapper(packages, libraries, **options)


def audit_pdf(pdf: Path, target: dict) -> dict:
    from figure_audit import audit_pdf as measured_audit
    return measured_audit(pdf, target)


def create_previews(pdf: Path, destination: Path) -> dict[str, Path]:
    from figure_audit import create_previews as accessibility_previews
    return accessibility_previews(pdf, destination, dpi=150)


def header_target(text: str, target_width: str) -> dict:
    width = re.match(rf"\s*({NUMBER})\s*(mm|cm|pt|in)\b", target_width)
    minimum = re.match(rf"\s*({NUMBER})\s*pt\b", header_value(text, "Minimum text size") or "")
    colour = (header_value(text, "Colour/greyscale intent") or "").lower()
    return {
        "width_mm": length_mm(float(width.group(1)), width.group(2)),
        "width_mode": "maximum", "width_tolerance_mm": 1.0,
        "min_text_pt": float(minimum.group(1)), "min_math_script_pt": 6,
        "min_stroke_pt": .35,
        "colour_intent": "colour_and_greyscale" if "colour" in colour else "greyscale",
    }


def run(
    command: list[str], cwd: Path, timeout: float = DEFAULT_COMMAND_TIMEOUT
) -> subprocess.CompletedProcess[str]:
    executable = shutil.which(command[0])
    if not executable:
        raise RenderError(f"Required executable not found: {command[0]}")
    resolved_command = [executable, *command[1:]]
    if not math.isfinite(timeout) or timeout <= 0:
        raise RenderError("Command timeout must be positive")
    log = cwd / f"command-{len(list(cwd.glob('command-*.log'))) + 1:02d}.log"
    process = subprocess.Popen(
        resolved_command, cwd=cwd, text=True, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, start_new_session=(os.name == "posix"),
        env={**os.environ, "TEXINPUTS": str(cwd) + "//:" + os.environ.get("TEXINPUTS", "")},
    )
    try:
        output, _ = process.communicate(timeout=timeout)
        completed = subprocess.CompletedProcess(resolved_command, process.returncode, output)
    except subprocess.TimeoutExpired as error:
        if os.name == "posix":
            os.killpg(process.pid, signal.SIGKILL)
        else:
            process.kill()
        output, _ = process.communicate()
        log.write_text(
            f"Command: {' '.join(resolved_command)}\nArgv: {json.dumps(resolved_command)}\nTIMEOUT after {timeout:g} s\n{output}",
            encoding="utf-8",
        )
        raise RenderError(f"Command timed out after {timeout:g} s: {command[0]}; log: {log}") from error
    log.write_text(
        f"Command: {' '.join(resolved_command)}\nArgv: {json.dumps(resolved_command)}\nExit: {completed.returncode}\n{completed.stdout}",
        encoding="utf-8",
    )
    if completed.returncode != 0:
        tail = "\n".join(completed.stdout.splitlines()[-50:])
        raise RenderError(f"Command failed: {' '.join(resolved_command)}\n{tail}\nLog: {log}")
    return completed


def compile_pdf(build: Path, engine: str, timeout: float = DEFAULT_COMMAND_TIMEOUT) -> Path:
    engine_flag = {
        "pdflatex": "-pdf",
        "lualatex": "-lualatex",
        "xelatex": "-xelatex",
    }[engine]
    run(
        [
            "latexmk",
            engine_flag,
            "-halt-on-error",
            "-no-shell-escape",
            "-recorder",
            "-interaction=nonstopmode",
            "-file-line-error",
            "wrapper.tex",
        ],
        build, timeout,
    )
    pdf = build / "wrapper.pdf"
    if not pdf.exists() or pdf.stat().st_size == 0:
        raise RenderError("Compilation completed without a non-empty PDF")
    return pdf


def parse_pdfinfo(pdf: Path, cwd: Path, timeout: float = DEFAULT_COMMAND_TIMEOUT) -> tuple[int, str]:
    result = run(["pdfinfo", str(pdf)], cwd, timeout)
    pages_match = re.search(r"(?m)^Pages:\s+(\d+)", result.stdout)
    size_match = re.search(r"(?m)^Page size:\s+(.+)$", result.stdout)
    if not pages_match:
        raise RenderError("Could not determine PDF page count")
    pages = int(pages_match.group(1))
    if pages != 1:
        raise RenderError(f"Expected one page, found {pages}")
    return pages, size_match.group(1).strip() if size_match else "unknown"


def length_mm(value: float, unit: str) -> float:
    factors = {
        "mm": 1.0,
        "cm": 10.0,
        "pt": 25.4 / 72.27,
        "in": 25.4,
    }
    return value * factors[unit]


def check_target_width(target_width: str, page_size: str) -> tuple[float, float]:
    target_match = re.search(
        rf"({NUMBER})\s*(mm|cm|pt|in)\b", target_width
    )
    page_match = re.search(r"([0-9]+(?:\.[0-9]+)?)\s+x\s+", page_size)
    if not target_match or not page_match:
        raise RenderError("Could not compare target and rendered physical widths")

    target_mm = length_mm(float(target_match.group(1)), target_match.group(2))
    rendered_mm = float(page_match.group(1)) * 25.4 / 72.0
    if rendered_mm > target_mm + 1.0:
        raise RenderError(
            f"Rendered width {rendered_mm:.1f} mm exceeds declared target "
            f"{target_mm:.1f} mm by more than the 1 mm preview-border tolerance"
        )
    return target_mm, rendered_mm


def check_fonts(pdf: Path, cwd: Path, timeout: float = DEFAULT_COMMAND_TIMEOUT) -> int:
    result = run(["pdffonts", str(pdf)], cwd, timeout)
    lines = [line for line in result.stdout.splitlines() if line.strip()]
    if len(lines) < 3:
        raise RenderError("No fonts detected; labels may have been converted incorrectly")
    font_rows = lines[2:]
    unembedded: list[str] = []
    for row in font_rows:
        # Font type and encoding may contain spaces. The last five fields are
        # embedding, subset, Unicode, object number and generation number.
        fields = re.search(r"\s+(yes|no)\s+(yes|no)\s+(yes|no)\s+\d+\s+\d+\s*$", row, re.I)
        if not fields:
            raise RenderError(f"Could not parse pdffonts row: {row}")
        if fields.group(1).lower() != "yes":
            unembedded.append(row.split()[0])
    if unembedded:
        raise RenderError(f"Unembedded PDF fonts: {', '.join(unembedded)}")
    return len(font_rows)


def check_selectable_text(pdf: Path, cwd: Path, timeout: float = DEFAULT_COMMAND_TIMEOUT) -> int:
    target = cwd / "extracted.txt"
    run(["pdftotext", str(pdf), str(target)], cwd, timeout)
    text = target.read_text(encoding="utf-8", errors="replace").strip()
    if not text:
        raise RenderError(
            "No selectable text found. Use live TeX labels rather than outlined or raster text."
        )
    return len(text)


def render_preview(
    pdf: Path, preview: Path, cwd: Path, timeout: float = DEFAULT_COMMAND_TIMEOUT
) -> None:
    """Stage rasterisation in a fresh directory; never inspect an old preview."""
    with tempfile.TemporaryDirectory(prefix="preview-", dir=cwd) as temporary:
        prefix = Path(temporary) / "rendered"
        run(
            ["pdftoppm", "-png", "-r", "300", "-singlefile", str(pdf), str(prefix)],
            cwd, timeout,
        )
        generated = Path(str(prefix) + ".png")
        if not generated.is_file() or generated.stat().st_size == 0:
            raise RenderError("Preview rendering completed without a non-empty PNG")
        publish_artifacts([(generated, preview)])


def copy_build_tree(build: Path, destination: Path) -> Path:
    """Retain a build without removing or replacing any existing user data."""
    if destination.exists():
        if not destination.is_dir():
            raise RenderError(f"--keep-build is not a directory: {destination}")
        target = Path(tempfile.mkdtemp(prefix="render-", dir=destination))
        shutil.copytree(build, target, dirs_exist_ok=True)
    else:
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(build, destination)
        target = destination
    return target


def publish_artifacts(artifacts: list[tuple[Path, Path]]) -> None:
    """Prepare every artifact before atomically replacing individual outputs.

    Existing deliverables are restored if publication of a later file fails.
    This is rollback for ordinary I/O failures, not a cross-filesystem transaction.
    """
    prepared: list[tuple[Path, Path, Path | None]] = []
    published: list[tuple[Path, Path | None]] = []
    try:
        for source, destination in artifacts:
            if destination.exists() and not destination.is_file():
                raise RenderError(f"Output is not a regular file: {destination}")
            destination.parent.mkdir(parents=True, exist_ok=True)
            descriptor, stage_name = tempfile.mkstemp(prefix=".tikz-stage-", dir=destination.parent)
            os.close(descriptor)
            stage = Path(stage_name)
            backup: Path | None = None
            try:
                shutil.copy2(source, stage)
                if destination.exists():
                    descriptor, backup_name = tempfile.mkstemp(prefix=".tikz-backup-", dir=destination.parent)
                    os.close(descriptor)
                    backup = Path(backup_name)
                    shutil.copy2(destination, backup)
                prepared.append((stage, destination, backup))
            except BaseException:
                stage.unlink(missing_ok=True)
                if backup:
                    backup.unlink(missing_ok=True)
                raise
        for stage, destination, backup in prepared:
            os.replace(stage, destination)
            published.append((destination, backup))
    except BaseException:
        for destination, backup in reversed(published):
            if backup:
                os.replace(backup, destination)
            else:
                destination.unlink(missing_ok=True)
        raise
    finally:
        for stage, _, backup in prepared:
            stage.unlink(missing_ok=True)
            if backup:
                backup.unlink(missing_ok=True)


def output_path(source: Path, requested: Path | None) -> Path:
    if requested:
        return requested.resolve()
    base = source.name[: -len(".tikz.tex")]
    return source.with_name(f"{base}.pdf").resolve()


def main() -> int:
    from build_profile import ProfileError
    from figure_spec import SpecError
    from render_context import (
        ContextError, prepare_context, stage_context, tex_runtime_roots,
        recorder_dependencies, runtime_versions, complete_report, write_report,
    )
    args = parse_args()
    source = args.source.resolve()
    if not source.is_file():
        print(f"ERROR: source not found: {source}", file=sys.stderr)
        return 2
    build: Path | None = None
    retained: Path | None = None
    succeeded = False
    try:
        if not math.isfinite(args.timeout) or args.timeout <= 0:
            raise RenderError("--timeout must be positive")
        context = prepare_context(args, source)
        source_bytes = source.read_bytes()
        if hashlib.sha256(source_bytes).hexdigest() != context["records"]["source"]["sha256"]:
            raise ContextError("Source changed between provenance capture and source validation")
        text = source_bytes.decode("utf-8")
        spec = context["spec"]
        exceptions = spec["target"].get("font_exceptions", []) if spec else []
        packages, libraries, target_width = validate_source(source, text, 6 if exceptions else None)
        declared_target = header_target(text, target_width)
        target = spec["target"] if spec else declared_target
        if spec and (abs(declared_target["width_mm"] - target["width_mm"]) > target["width_tolerance_mm"]
                     or abs(declared_target["min_text_pt"] - target["min_text_pt"]) > .005):
            raise RenderError("Source target width/text headers conflict with the figure specification")
        destination = output_path(source, context["output"])
        preview = context["preview"]
        audit = context["audit"] or destination.with_name(destination.stem + ".audit.json")
        keep_build = args.keep_build.resolve() if args.keep_build else None
        if destination.suffix.lower() != ".pdf":
            raise RenderError("--output must name a PDF file")
        if preview and preview.suffix.lower() != ".png":
            raise RenderError("--preview must name a PNG file")
        if audit and audit.suffix.lower() != ".json":
            raise RenderError("--audit must name a JSON file")
        if keep_build and keep_build.exists() and not keep_build.is_dir():
            raise RenderError(f"--keep-build is not a directory: {keep_build}")
        build = Path(tempfile.mkdtemp(prefix="tikz-render-"))
        source_name, preamble, staged = stage_context(context, build)
        (build / "wrapper.tex").write_text(
            wrapper_text(packages, libraries, profile=context["profile"], source=source_name, preamble=preamble),
            encoding="utf-8",
        )
        built_pdf = compile_pdf(build, context["engine"], args.timeout)
        _, page_size = parse_pdfinfo(built_pdf, build, args.timeout)
        font_count = check_fonts(built_pdf, build, args.timeout)
        text_characters = check_selectable_text(built_pdf, build, args.timeout)
        report = audit_pdf(built_pdf, target)
        write_report(report, build / "audit.json")
        artifacts = [(built_pdf, destination)]
        if preview:
            staged_preview = build / "preview.png"
            render_preview(built_pdf, staged_preview, build, args.timeout)
            artifacts.append((staged_preview, preview))
        if context["qa_dir"]:
            qa_dir = context["qa_dir"].resolve()
            for name, path in create_previews(built_pdf, build / "qa").items():
                artifacts.append((path, qa_dir / f"{destination.stem}.preview-{name}.png"))
        roots = tex_runtime_roots(run, build, args.timeout)
        dependencies = recorder_dependencies(build, staged, roots)
        versions = runtime_versions(run, build, context["engine"], args.timeout)
        report = complete_report(report, context, build, staged, dependencies, versions, artifacts)
        write_report(report, build / "audit.json")
        if not report["ok"]:
            raise RenderError("Measured PDF audit failed: " + "; ".join(item["message"] for item in report["errors"]))
        if audit:
            artifacts.append((build / "audit.json", audit))
        protected = {Path(item["path"]).resolve() for item in staged.values()} | {source}
        protected.update(Path(item["path"]).resolve() for item in context["records"].values())
        if any(path in protected for _, path in artifacts):
            raise RenderError("An output would overwrite a declared source, input, dependency or profile")
        if len({path for _, path in artifacts}) != len(artifacts):
            raise RenderError("Requested output paths must be distinct")
        if keep_build:
            retained = copy_build_tree(build, keep_build)
        publish_artifacts(artifacts)
        succeeded = True
        print(f"OK: {source.name}")
        print(f"PDF: {destination}")
        if preview:
            print(f"Preview: {preview}")
        if audit:
            print(f"Audit: {audit}")
        if retained:
            print(f"Build retained: {retained}")
        print(f"Rendered page size: {page_size}")
        print(f"Embedded fonts: {font_count}")
        print(f"Selectable text characters: {text_characters}")
        for warning in report.get("warnings", []):
            print(f"WARNING: {warning['message']}")
        for warning in report["typesetting_warnings"]:
            print(f"TYPESETTING: {warning}")
        print("Visual inspection and independent semantic review are still required.")
        return 0
    except (OSError, RenderError, SpecError, ProfileError, ContextError, ImportError, ValueError, RuntimeError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        if build:
            failed_report = build / "audit.json"
            if failed_report.is_file():
                try:
                    report = json.loads(failed_report.read_text(encoding="utf-8"))
                    report["ok"] = False
                    report.setdefault("errors", []).append({"code": "build_failed", "message": str(error)})
                    write_report(report, failed_report)
                except (OSError, ValueError):
                    pass
            if args.keep_build and retained is None:
                try:
                    retained = copy_build_tree(build, args.keep_build.resolve())
                except (OSError, RenderError) as retention_error:
                    print(f"Could not copy diagnostics: {retention_error}", file=sys.stderr)
            print(f"Diagnostics retained: {retained or build}", file=sys.stderr)
        return 1
    finally:
        if build and (succeeded or retained):
            shutil.rmtree(build)


if __name__ == "__main__":
    raise SystemExit(main())
