.PHONY: help install-dev format format-check lint lint-pylint test test-qgis test-all package precommit

PYTHON ?= python3

help:
	@echo "Available targets:"
	@echo "  install-dev   Install local development dependencies"
	@echo "  format        Apply black formatting"
	@echo "  format-check  Check black formatting"
	@echo "  lint          Run ruff + black checks"
	@echo "  lint-pylint   Run pylint (recommended only in a QGIS-enabled environment)"
	@echo "  test          Run fast local test suite"
	@echo "  test-qgis     Run QGIS-backed integration tests"
	@echo "  test-all      Run lint + fast tests"
	@echo "  precommit     Run pre-commit hooks on all files"
	@echo "  package       Build release ZIP via package_plugin.py"

install-dev:
	$(PYTHON) -m pip install -r requirements-dev.txt

format:
	$(PYTHON) -m black .

format-check:
	$(PYTHON) -m black --check .

lint:
	$(PYTHON) -m ruff check .
	$(PYTHON) -m black --check .

lint-pylint:
	$(PYTHON) -m pylint --rcfile=pylintrc CustomMapDownloader.py CustomMapDownloader_dialog.py core

test:
	$(PYTHON) -m unittest discover -s test -v

test-qgis:
	$(PYTHON) -m unittest discover -s test/integration -v

test-all: lint test

precommit:
	$(PYTHON) -m pre_commit run --all-files

package:
	$(PYTHON) package_plugin.py
