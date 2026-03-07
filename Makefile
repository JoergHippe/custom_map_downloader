.PHONY: help install-dev deploy-dev undeploy-dev dev-check format format-check lint lint-pylint test test-qgis test-all package package-check release-check precommit translations-update translations-compile translations-status release-governance-check

PYTHON ?= python3
PLUGIN_DIR := custom_map_downloader
VERSION := $(shell sed -n 's/^version=//p' $(PLUGIN_DIR)/metadata.txt | head -n 1)
LOCALES ?= de

help:
	@echo "Available targets:"
	@echo "  install-dev   Install local development dependencies"
	@echo "  deploy-dev    Link plugin into local QGIS profile for development"
	@echo "  undeploy-dev  Remove plugin from local QGIS profile"
	@echo "  dev-check     Run standard local preflight checks"
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
	@echo "  release-check Run the full release checklist (lint, tests, package validation)"
	@echo "  translations-update   Refresh .ts translation source files for LOCALES=$(LOCALES)"
	@echo "  translations-compile  Build .qm files for LOCALES=$(LOCALES)"
	@echo "  translations-status   Show translation coverage summary"
	@echo "  release-governance-check Validate metadata/changelog release governance"

install-dev:
	$(PYTHON) -m pip install -r requirements-dev.txt

deploy-dev:
	$(PYTHON) scripts/install_dev_plugin.py

undeploy-dev:
	$(PYTHON) scripts/install_dev_plugin.py --remove

dev-check:
	$(PYTHON) scripts/dev_check.py

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

translations-update:
	bash scripts/update-strings.sh $(LOCALES)

translations-compile:
	bash scripts/compile-strings.sh $(LOCALES)

translations-status:
	$(PYTHON) scripts/check_translations.py

release-governance-check:
	$(PYTHON) scripts/check_release_governance.py

package:
	@if [ -x "$(dir $(PYTHON))/qgis-plugin-ci" ]; then \
		"$(dir $(PYTHON))/qgis-plugin-ci" package $(VERSION) -c; \
	else \
		qgis-plugin-ci package $(VERSION) -c; \
	fi

package-check: package
	$(PYTHON) scripts/check_package.py

release-check: lint test translations-status release-governance-check package-check
