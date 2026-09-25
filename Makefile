.PHONY: install test generate check-generated example build check
PYTHON ?= python3

install:
	$(PYTHON) -m pip install -e '.[dev]'

test:
	$(PYTHON) -m pytest -q

generate:
	$(PYTHON) scripts/generate_parser.py

check-generated:
	$(PYTHON) scripts/generate_parser.py --check

example:
	$(PYTHON) examples/api-load-test/run.py

build:
	$(PYTHON) -m build

check: check-generated test example
