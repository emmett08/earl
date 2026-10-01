"""Verify one release pair and independently install its wheel and source archive."""

from __future__ import annotations

import argparse
import configparser
from email.parser import BytesParser
import hashlib
import os
from pathlib import Path, PurePosixPath
import subprocess
import sys
import tarfile
import tempfile
import venv
import zipfile


PROJECT = "engineering-argument-language"
ENTRY_POINTS = {"eal": "eal.cli:main", "eal-mcp": "eal.server:main", "eal-host": "eal.host:main"}
EXCLUDED = {"paper", "annotations", "runs", "__pycache__"}
LICENSE = Path(__file__).resolve().parents[1] / "LICENSE"


def check_metadata(encoded: bytes, *, expected_version: str | None) -> str:
    metadata = BytesParser().parsebytes(encoded)
    for name, expected in (("Name", PROJECT), ("Requires-Python", ">=3.11"),
                           ("License-Expression", "Unlicense"),
                           ("Description-Content-Type", "text/markdown")):
        if metadata.get(name) != expected:
            raise ValueError(f"Distribution {name} must be {expected!r}")
    version = metadata["Version"]
    if not version or expected_version is not None and version != expected_version:
        raise ValueError("Distribution version differs from the selected release")
    if "LICENSE" not in metadata.get_all("License-File", []):
        raise ValueError("Distribution metadata omits LICENSE")
    if not metadata.get_payload().strip():
        raise ValueError("Distribution metadata omits the README")
    return version


def check_paths(names: list[str]) -> None:
    for name in names:
        path = PurePosixPath(name)
        if path.is_absolute() or ".." in path.parts or set(path.parts) & EXCLUDED:
            raise ValueError(f"Unexpected distribution path: {name}")


def wheel_contents(wheel: Path, *, expected_version: str | None) -> tuple[str, dict[str, str]]:
    with zipfile.ZipFile(wheel) as archive:
        names = archive.namelist()
        check_paths(names)
        metadata_names = [name for name in names if name.endswith(".dist-info/METADATA")]
        if len(metadata_names) != 1:
            raise ValueError("The wheel must contain exactly one package metadata record")
        prefix = metadata_names[0].removesuffix("METADATA")
        version = check_metadata(archive.read(metadata_names[0]), expected_version=expected_version)
        if archive.read(prefix + "licenses/LICENSE") != LICENSE.read_bytes():
            raise ValueError("The wheel does not contain the complete reviewed Unlicense")
        scripts = configparser.ConfigParser()
        scripts.read_string(archive.read(prefix + "entry_points.txt").decode("utf-8"))
        if dict(scripts["console_scripts"]) != ENTRY_POINTS:
            raise ValueError("The wheel console scripts differ from the public interface")
        modules = {name: hashlib.sha256(archive.read(name)).hexdigest()
                   for name in names if name.startswith("eal/") and name.endswith(".py")}
        required = {"eal/knowledge.py", "eal/runtime.py", "eal/command_supervisor.py",
                    "eal/generated/EALLexer.py", "eal/generated/EALParser.py"}
        if not required <= modules.keys():
            raise ValueError("The wheel omits runtime modules")
        return version, modules


def check_source(source: Path, *, expected_version: str) -> None:
    with tarfile.open(source) as archive:
        members = archive.getmembers()
        check_paths([member.name for member in members])
        if any(not member.isfile() and not member.isdir() for member in members):
            raise ValueError("Source distribution contains a special file or link")
        roots = {PurePosixPath(member.name).parts[0] for member in members}
        if len(roots) != 1:
            raise ValueError("Source distribution must have one root directory")
        root = roots.pop()
        metadata = archive.extractfile(root + "/PKG-INFO")
        if metadata is None:
            raise ValueError("Source distribution omits package metadata")
        check_metadata(metadata.read(), expected_version=expected_version)
        license_file = archive.extractfile(root + "/LICENSE")
        if license_file is None or license_file.read() != LICENSE.read_bytes():
            raise ValueError("Source distribution omits the complete reviewed Unlicense")


def run(arguments: list[str], *, cwd: Path, environment: dict[str, str]) -> None:
    subprocess.run(arguments, cwd=cwd, env=environment, check=True, timeout=600)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dist_directory", type=Path, nargs="?", default=Path("dist"))
    parser.add_argument("--expected-version")
    parser.add_argument("--constraints", type=Path)
    arguments = parser.parse_args()
    directory = arguments.dist_directory.resolve()
    wheels, sources = sorted(directory.glob("*.whl")), sorted(directory.glob("*.tar.gz"))
    if len(wheels) != 1 or len(sources) != 1 or set(directory.iterdir()) != set(wheels + sources):
        raise ValueError("Check exactly one wheel and one source distribution in a clean directory")
    version, modules = wheel_contents(wheels[0], expected_version=arguments.expected_version)
    check_source(sources[0], expected_version=version)
    environment = {key: value for key, value in os.environ.items()
                   if key not in {"PYTHONPATH", "PYTHONHOME"} and not key.startswith("EAL_MCP_")}
    smoke = Path(__file__).with_name("distribution_smoke.py").resolve()
    with tempfile.TemporaryDirectory(prefix="eal-distribution-") as temporary:
        root = Path(temporary)
        for label, artifact in (("wheel", wheels[0]), ("source", sources[0])):
            target = root / label
            venv.create(target, with_pip=True)
            python = target / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
            install = [str(python), "-m", "pip", "install", "--disable-pip-version-check"]
            if arguments.constraints is not None:
                install += ["-c", str(arguments.constraints.resolve())]
            run([*install, str(artifact)], cwd=root, environment=environment)
            run([str(python), "-m", "pip", "check"], cwd=root, environment=environment)
            run([str(python), "-I", str(smoke), str(root / (label + "-workspace")),
                 "--expected-version", version], cwd=root, environment=environment)
            if label == "source":
                rebuilt = root / "rebuilt"
                run([str(python), "-m", "pip", "wheel", "--no-deps", "--wheel-dir", str(rebuilt),
                     str(artifact)], cwd=root, environment=environment)
                rebuilt_wheels = list(rebuilt.glob("*.whl"))
                if len(rebuilt_wheels) != 1:
                    raise ValueError("Source distribution did not build exactly one wheel")
                _, rebuilt_modules = wheel_contents(rebuilt_wheels[0], expected_version=version)
                if rebuilt_modules != modules:
                    raise ValueError("Source-built wheel differs from the released runtime sources")
    print(f"Release {version}: metadata, wheel/source installations and source-built runtime equality passed")


if __name__ == "__main__":
    main()
