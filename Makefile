PYTHON ?= .venv/bin/python
STUDY ?= .venv/bin/polymarket-study
CONFIG ?= configs/study.yaml

.PHONY: install collect build-dataset train power evaluate report run test lint typecheck check

install:
	python3 -m venv .venv
	.venv/bin/python -m pip install --upgrade pip
	.venv/bin/python -m pip install -r requirements.lock
	.venv/bin/python -m pip install -e . --no-deps

collect:
	$(STUDY) collect --config $(CONFIG)

build-dataset:
	$(STUDY) build-dataset --config $(CONFIG)

train:
	$(STUDY) train --config $(CONFIG)

power:
	$(STUDY) power --config $(CONFIG)

evaluate:
	$(STUDY) evaluate --config $(CONFIG)

report:
	$(STUDY) report --config $(CONFIG)

run:
	$(STUDY) run --config $(CONFIG)

test:
	$(PYTHON) -m pytest

lint:
	$(PYTHON) -m ruff check .

typecheck:
	$(PYTHON) -m mypy src

check: lint typecheck test
