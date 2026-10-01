"""Reject artefacts whose identity, reuse terms or archive contents are unsafe."""

from io import BytesIO
from pathlib import Path
import tarfile
import zipfile

import pytest

from scripts.check_distribution import check_source, wheel_contents


VERSION = "3.2.1"
PREFIX = f"engineering_argument_language-{VERSION}"
LICENSE_TEXT = (Path(__file__).resolve().parents[1] / "LICENSE").read_bytes()
METADATA = b"""Metadata-Version: 2.4
Name: engineering-argument-language
Version: 3.2.1
Requires-Python: >=3.11
License-Expression: Unlicense
License-File: LICENSE
Description-Content-Type: text/markdown

# Reusable EARL package
"""
ENTRY_POINTS = b"""[console_scripts]
eal = eal.cli:main
eal-mcp = eal.server:main
eal-host = eal.host:main
"""
MODULES = (
    "eal/knowledge.py", "eal/runtime.py", "eal/command_supervisor.py",
    "eal/generated/EALLexer.py", "eal/generated/EALParser.py",
)


def wheel(tmp_path: Path, *, metadata: bytes = METADATA,
          extra_path: str | None = None, scripts: bytes = ENTRY_POINTS,
          licence: bytes = LICENSE_TEXT) -> Path:
    target = tmp_path / f"{PREFIX}-py3-none-any.whl"
    with zipfile.ZipFile(target, "w") as archive:
        archive.writestr(f"{PREFIX}.dist-info/METADATA", metadata)
        archive.writestr(f"{PREFIX}.dist-info/licenses/LICENSE", licence)
        archive.writestr(f"{PREFIX}.dist-info/entry_points.txt", scripts)
        for name in MODULES:
            archive.writestr(name, b"# Synthetic archive fixture\n")
        if extra_path is not None:
            archive.writestr(extra_path, b"excluded contents")
    return target


def source(tmp_path: Path, *, metadata: bytes = METADATA,
           extra_path: str | None = None, symlink: bool = False,
           licence: bytes = LICENSE_TEXT) -> Path:
    target = tmp_path / f"{PREFIX}.tar.gz"
    with tarfile.open(target, "w:gz") as archive:
        for name, contents in (("PKG-INFO", metadata), ("LICENSE", licence)):
            member = tarfile.TarInfo(f"{PREFIX}/{name}")
            member.size = len(contents)
            archive.addfile(member, BytesIO(contents))
        if extra_path is not None:
            member = tarfile.TarInfo(extra_path)
            if symlink:
                member.type = tarfile.SYMTYPE
                member.linkname = "../../outside"
            archive.addfile(member)
    return target


def test_wheel_and_source_agree_on_release_identity(tmp_path):
    version, modules = wheel_contents(wheel(tmp_path), expected_version=VERSION)
    assert version == VERSION
    assert set(modules) == set(MODULES)
    check_source(source(tmp_path), expected_version=version)


@pytest.mark.parametrize("metadata,diagnostic", [
    (METADATA.replace(b"Version: 3.2.1", b"Version: 3.2.0"), "version"),
    (METADATA.replace(b"Name: engineering-argument-language", b"Name: unrelated-package"), "Name"),
    (METADATA.replace(b"License-Expression: Unlicense\n", b""), "License-Expression"),
    (METADATA.replace(b"License-File: LICENSE\n", b""), "LICENSE"),
    (METADATA.split(b"\n\n", 1)[0] + b"\n\n", "README"),
])
@pytest.mark.parametrize("kind", ["wheel", "source"])
def test_both_archive_types_reject_wrong_release_or_missing_reuse_terms(tmp_path, metadata, diagnostic, kind):
    with pytest.raises(ValueError, match=diagnostic):
        if kind == "wheel":
            wheel_contents(wheel(tmp_path, metadata=metadata), expected_version=VERSION)
        else:
            check_source(source(tmp_path, metadata=metadata), expected_version=VERSION)


@pytest.mark.parametrize("path", ["../outside.py", "/absolute.py", "paper/vendor/template.cls",
                                 "annotations/private.json", "runs/observations.json"])
def test_wheel_rejects_unsafe_paths_or_repository_only_material(tmp_path, path):
    with pytest.raises(ValueError, match="Unexpected distribution path"):
        wheel_contents(wheel(tmp_path, extra_path=path), expected_version=VERSION)


def test_source_rejects_traversal_and_links_before_installation(tmp_path):
    with pytest.raises(ValueError, match="Unexpected distribution path"):
        check_source(source(tmp_path, extra_path=f"{PREFIX}/../outside"), expected_version=VERSION)
    with pytest.raises(ValueError, match="special file or link"):
        check_source(source(tmp_path, extra_path=f"{PREFIX}/src/eal/runtime.py", symlink=True),
                     expected_version=VERSION)


def test_wheel_rejects_missing_installed_host_command(tmp_path):
    scripts = ENTRY_POINTS.replace(b"eal-host = eal.host:main\n", b"")
    with pytest.raises(ValueError, match="console scripts"):
        wheel_contents(wheel(tmp_path, scripts=scripts), expected_version=VERSION)


@pytest.mark.parametrize("kind", ["wheel", "source"])
def test_both_archive_types_reject_truncated_licence(tmp_path, kind):
    first_line = LICENSE_TEXT.splitlines(keepends=True)[0]
    with pytest.raises(ValueError, match="complete reviewed Unlicense"):
        if kind == "wheel":
            wheel_contents(wheel(tmp_path, licence=first_line), expected_version=VERSION)
        else:
            check_source(source(tmp_path, licence=first_line), expected_version=VERSION)
