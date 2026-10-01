.PHONY: install test generate check-generated example build check check-distribution scientific
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

check-distribution: build
	$(PYTHON) -m twine check --strict dist/*.whl dist/*.tar.gz
	$(PYTHON) scripts/check_distribution.py dist

scientific:
	$(PYTHON) tools/investigation-validator/scripts/validate_investigation.py --self-test
	$(PYTHON) tools/investigation-validator/scripts/validate_investigation.py experiments/model_transfer/protocol.json
	$(PYTHON) tools/investigation-validator/scripts/validate_investigation.py experiments/transfer_study/protocol.json

check: check-generated scientific test example
