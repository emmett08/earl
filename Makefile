.PHONY: install test generate check-generated example build check experiment-check
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

experiment-check:
	$(PYTHON) -m experiments.api_load_test self-check --output experiment-results/self-check
