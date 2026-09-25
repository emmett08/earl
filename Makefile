.PHONY: install test research-tests generate check-generated demo live-demo modes-demo tasks build check
PYTHON ?= python3

install:
	$(PYTHON) -m pip install -e '.[dev]'

test:
	$(PYTHON) -m pytest -q

research-tests:
	$(PYTHON) -m unittest discover -s benchmarks/experiments/bias-mechanisms -p 'test_*.py'
	$(PYTHON) -m unittest discover -s benchmarks/experiments/bias-followups -p 'test_*.py'
	$(PYTHON) -m unittest discover -s benchmarks/experiments/bias-human-trial -p 'test_*.py'
	$(PYTHON) -m unittest discover -s benchmarks/experiments/prospective-real-workflows -p 'test_*.py'

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

tasks:
	$(PYTHON) -m eal.benchmark --check-tasks --suite benchmarks/engineering-v1/suite.json --summary
	$(PYTHON) -m eal.benchmark --check-tasks --suite benchmarks/engineering-v2/suite.json --summary

build:
	$(PYTHON) -m build

check: check-generated test research-tests demo live-demo modes-demo tasks
