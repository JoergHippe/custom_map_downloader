.PHONY: help install-dev format format-check lint lint-pylint test test-qgis test-all package package-check precommit

PYTHON ?= python3
PLUGIN_DIR := custom_map_downloader
VERSION := $(shell sed -n 's/^version=//p' $(PLUGIN_DIR)/metadata.txt | head -n 1)

help:
	@echo "Available targets:"
	@echo "  install-dev   Install local development dependencies"
	@echo "  format        Apply black formatting"
	@echo "  format-check  Check black formatting"
	@echo "  lint          Run ruff + black checks"
	@echo "  lint-pylint   Run pylint on plugin sources in a QGIS-enabled environment"
	@echo "  test          Run fast local test suite"
	@echo "  test-qgis     Run QGIS-backed integration tests"
	@echo "  test-all      Run lint + fast tests"
	@echo "  precommit     Run pre-commit hooks on all files"
	@echo "  package       Build release ZIP via qgis-plugin-ci"
	@echo "  package-check Build and validate release ZIP contents"

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
	$(PYTHON) -m pylint --rcfile=pylintrc \
		$(PLUGIN_DIR)/CustomMapDownloader.py \
		$(PLUGIN_DIR)/CustomMapDownloader_dialog.py \
		$(PLUGIN_DIR)/core

test:
	$(PYTHON) -m unittest discover -s test -v

test-qgis:
	$(PYTHON) -m unittest discover -s test/integration -v

test-all: lint test

precommit:
	$(PYTHON) -m pre_commit run --all-files

package:
	@if [ -x "$(dir $(PYTHON))/qgis-plugin-ci" ]; then \
		"$(dir $(PYTHON))/qgis-plugin-ci" package $(VERSION) -c; \
	else \
		qgis-plugin-ci package $(VERSION) -c; \
	fi

package-check: package
	$(PYTHON) scripts/check_package.py
