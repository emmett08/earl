"""Validate manuscript profiles and construct faithful cropped TeX wrappers."""
from __future__ import annotations

import json
from pathlib import Path
import re

DEFAULT_PACKAGES = ("amsmath", "amssymb", "mathtools", "bm", "xcolor", "tikz")
ENGINES = {"pdflatex", "lualatex", "xelatex"}
TOKEN = re.compile(r"^[A-Za-z0-9_.-]+$")


class ProfileError(ValueError):
    pass


def local_file(root: Path, relative: str) -> Path:
    """Resolve a declared file inside its root, including symlink containment."""
    if not isinstance(relative, str) or not relative or "\\" in relative or Path(relative).is_absolute():
        raise ProfileError(f"Expected a relative local file path: {relative!r}")
    root = root.resolve()
    path = (root / relative).resolve()
    if not path.is_relative_to(root):
        raise ProfileError(f"Local file escapes its declared root: {relative}")
    if not path.is_file():
        raise ProfileError(f"Declared local file does not exist: {relative}")
    return path


def _strings(value, label, *, tokens=False):
    if not isinstance(value, list) or any(not isinstance(item, str) or not item.strip() for item in value):
        raise ProfileError(f"{label} must be an array of non-empty strings")
    if any(any(character in item for character in "\n\r{}[]") for item in value):
        raise ProfileError(f"{label} contains an invalid TeX option")
    if tokens and any(not TOKEN.fullmatch(item) for item in value):
        raise ProfileError(f"{label} must contain simple names")
    return value


def load_profile(path: Path) -> dict:
    """Load a closed profile format; preamble/dependencies resolve from this file."""
    path = Path(path).resolve()
    try:
        profile = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ProfileError(f"Cannot read manuscript profile: {error}") from error
    required = {"schema_version", "profile_id", "document_class", "class_options", "packages", "dependencies"}
    allowed = required | {"preamble", "engine"}
    if not isinstance(profile, dict) or required - profile.keys() or profile.keys() - allowed:
        raise ProfileError("Profile must contain the required fields and no unknown fields")
    if profile["schema_version"] != "1.0":
        raise ProfileError("Profile schema_version must be 1.0")
    for name in ("profile_id", "document_class"):
        if not isinstance(profile[name], str) or not TOKEN.fullmatch(profile[name]):
            raise ProfileError(f"{name} must be a simple name")
    _strings(profile["class_options"], "class_options")
    if not isinstance(profile["packages"], list):
        raise ProfileError("packages must be an array")
    names = []
    for package in profile["packages"]:
        if not isinstance(package, dict) or set(package) != {"name", "options"}:
            raise ProfileError("Each package must have name and options fields")
        if not isinstance(package["name"], str) or not TOKEN.fullmatch(package["name"]):
            raise ProfileError("Package names must be simple names")
        _strings(package["options"], "package options")
        names.append(package["name"])
    if len(names) != len(set(names)):
        raise ProfileError("Profile package names must be unique")
    _strings(profile["dependencies"], "dependencies")
    if len(profile["dependencies"]) != len(set(profile["dependencies"])):
        raise ProfileError("Profile dependencies must be unique")
    for relative in profile["dependencies"]:
        local_file(path.parent, relative)
    if "preamble" in profile:
        local_file(path.parent, profile["preamble"])
    if profile.get("engine") is not None and profile["engine"] not in ENGINES:
        raise ProfileError("Unsupported manuscript profile engine")
    return profile


def wrapper_text(packages, libraries, *, profile=None, source="figure-input.tex", preamble=None):
    """Use declared manuscript typography; default retains the original wrapper."""
    profile_packages = profile["packages"] if profile else []
    options = ",".join(profile["class_options"]) if profile else "10pt,border=1pt"
    document_class = profile["document_class"] if profile else "standalone"
    lines = [rf"\documentclass[{options}]{{{document_class}}}"]
    if profile:
        lines.append(r"\PassOptionsToPackage{active,tightpage}{preview}")
    if profile is None:
        lines += [r"\usepackage[T1]{fontenc}", r"\usepackage{lmodern}"]
    declared = {item["name"] for item in profile_packages}
    for item in profile_packages:
        option = f"[{','.join(item['options'])}]" if item["options"] else ""
        lines.append(rf"\usepackage{option}{{{item['name']}}}")
    for package in dict.fromkeys((*DEFAULT_PACKAGES, *packages)):
        if package not in declared:
            lines.append(rf"\usepackage{{{package}}}")
    if libraries:
        lines.append(rf"\usetikzlibrary{{{','.join(libraries)}}}")
    if profile:
        if "preview" not in declared:
            lines.append(r"\usepackage[active,tightpage]{preview}")
        lines += [r"\PreviewEnvironment{tikzpicture}", r"\setlength\PreviewBorder{1pt}"]
    if preamble:
        lines.append(rf"\input{{{preamble}}}")
    lines += [
        r"\begin{document}",
        r"\typeout{FIGURE-LINEWIDTH-PT=\the\linewidth}",
        r"\typeout{FIGURE-COLUMNWIDTH-PT=\the\columnwidth}",
        rf"\input{{{source}}}", r"\end{document}",
    ]
    return "\n".join(lines) + "\n"
