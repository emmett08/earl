.PHONY: install test generate check-generated demo live-demo modes-demo build check
PYTHON ?= python3

install:
	$(PYTHON) -m pip install -e '.[dev]'

test:
	$(PYTHON) -m pytest -q

generate:
	$(PYTHON) scripts/generate_parser.py

check-generated:
	$(PYTHON) scripts/generate_parser.py --check

demo:
	$(PYTHON) scripts/demo.py

live-demo:
	$(PYTHON) scripts/demo.py --live

modes-demo:
	$(PYTHON) scripts/demo.py --mixed

build:
	$(PYTHON) -m build

check: check-generated test demo live-demo modes-demo
