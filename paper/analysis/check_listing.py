#!/usr/bin/env python3
"""Validate the actual retained EAL/3 program and derive its printed excerpt."""
from pathlib import Path
import argparse
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT.parent))
sys.path.insert(0, str(ROOT.parent / "src"))
from eal.parser import parse
from eal.formatter import format_source, semantic_ir
from eal.methods import default_registry
from experiments.model_transfer.corpus_logic import CONTRACT


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    source = (ROOT / "listings/retained-argument.eal").read_text()
    registry = default_registry().with_method(CONTRACT)
    formatted = format_source(source, registry=registry)
    assert semantic_ir(parse(source)) == semantic_ir(parse(formatted))
    reasoning = re.search(r"^reasoning task_rules \{.*?^\}", formatted, re.M | re.S)
    argument = re.search(r"^argument result = .*?$", formatted, re.M)
    assert reasoning and argument, "Retained EAL/3 declarations were not found"
    excerpt = reasoning.group() + "\n\n" + argument.group() + "\n"
    destination = ROOT / "listings/method-excerpt.eal"
    if args.write:
        destination.write_text(excerpt)
    else:
        assert destination.read_text() == excerpt, "Printed excerpt differs from retained program"
    grammar = (ROOT.parent / "grammar/EAL.g4").read_text()
    keywords = set(re.findall(r"'([a-z][a-z_]*)'", grammar.split("ID :")[0]))
    style = (ROOT / "eal3-listings.tex").read_text()
    declared = set(re.search(r"morekeywords=\{([^}]+)\}", style).group(1).split(","))
    assert declared == keywords, {"missing": sorted(keywords-declared), "extra": sorted(declared-keywords)}
    print("EAL/3 parse, registered method validation, format round-trip, exact excerpt and highlighting keywords: passed.")


if __name__ == "__main__":
    main()
