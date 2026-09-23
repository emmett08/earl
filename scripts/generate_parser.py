#!/usr/bin/env python3
"""Reproduce the Python parser with an authenticated ANTLR distribution."""
from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import urllib.request

VERSION = "4.13.2"
SHA256 = "eae2dfa119a64327444672aff63e9ec35a20180dc5b8090b7a6ab85125df4d76"
ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--jar", type=Path, default=os.environ.get("ANTLR_JAR"))
    parser.add_argument("--check", action="store_true", help="Fail on generated-source drift")
    args = parser.parse_args()
    jar = args.jar or ROOT / ".cache" / f"antlr-{VERSION}-complete.jar"
    if not jar.exists():
        jar.parent.mkdir(parents=True, exist_ok=True)
        with urllib.request.urlopen(f"https://www.antlr.org/download/antlr-{VERSION}-complete.jar", timeout=60) as response:
            data = response.read(5 * 1024 * 1024)
        if hashlib.sha256(data).hexdigest() != SHA256:
            raise SystemExit("ANTLR download digest mismatch")
        jar.write_bytes(data)
    if hashlib.sha256(jar.read_bytes()).hexdigest() != SHA256:
        raise SystemExit("ANTLR jar digest mismatch")
    target = ROOT / "src" / "eal" / "generated"
    with tempfile.TemporaryDirectory() as temporary:
        output = Path(temporary)
        subprocess.run(["java", "-jar", str(jar.resolve()), "-Dlanguage=Python3", "-visitor", "-no-listener", "-Xexact-output-dir", "-o", str(output), "grammar/EAL.g4"], cwd=ROOT, check=True)
        files = sorted(file for file in output.iterdir() if file.suffix in {".py", ".tokens", ".interp"})
        if not any(file.suffix == ".py" for file in files):
            raise SystemExit("ANTLR generated no Python sources")
        if args.check:
            differing = [f.name for f in files if not (target / f.name).exists() or f.read_bytes() != (target / f.name).read_bytes()]
            if differing:
                raise SystemExit("Generated sources differ: " + ", ".join(differing))
        else:
            target.mkdir(parents=True, exist_ok=True)
            for file in files:
                shutil.copyfile(file, target / file.name)
            (target / "__init__.py").touch()
    print(f"ANTLR {VERSION} generated sources {'verified' if args.check else 'updated'}")


if __name__ == "__main__":
    main()
