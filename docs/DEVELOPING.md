# Development Guide

## Development Model

For actual plugin runtime behavior, QGIS Python is the authoritative environment.
A plain isolated `.venv` is not the plugin runtime.

Use:

- Windows: OSGeo4W Shell / QGIS Python Shell
- Linux: system QGIS Python environment
- IDEs: a QGIS-aware environment inheriting QGIS site-packages

A local `.venv` remains useful for tooling only.

## Tooling-Only Environment

Typical tooling in `.venv`:

- `ruff`
- `black`
- `pre-commit`
- `qgis-plugin-ci`
- fast non-QGIS tests

Setup:

```bash
python3 -m venv .venv
. .venv/bin/activate
python3 -m pip install -r requirements-dev.txt
```

Core commands:

```bash
make format
make lint
make test
make dev-check
make package
make package-check
make release-check
```

## QGIS Runtime / Integration Environment

Run QGIS-backed checks in a real QGIS Python environment:

```bash
make test-qgis
```

On Windows, the repository also provides helpers:

```bat
run_integration_tests.bat all myprofile
run_integration_tests.bat smoke myprofile
run_integration_tests.bat network myprofile
```

The chosen profile affects the QGIS runtime context. The tests still import the plugin code directly from the repository.

See also `test/integration/README.md`.

## Local QGIS Dev Loop

Deploy the current source tree into a QGIS profile:

```bash
make deploy-dev
```

Remove it again:

```bash
make undeploy-dev
```

On Windows you can start QGIS directly against a development profile:

```bat
start_qgis_dev.bat
start_qgis_dev.bat myprofile
start_qgis_dev.bat myprofile copy
```

VS Code can be started with the same profile semantics:

```bat
start_vscode_qgis.bat
start_vscode_qgis.bat myprofile
start_vscode_qgis.bat myprofile copy
```

Recommended local loop:

1. deploy the plugin into the target profile
2. start QGIS with that profile
3. change code in the repo
4. restart QGIS or use an explicit plugin reloader if you choose to work that way
5. smoke-check the plugin

## Integration Test Coverage

### Current smoke coverage

`test/integration/test_export_smoke.py` covers these QGIS-backed paths:

- small direct GeoTIFF export
- small export with target scale mode
- small VRT export with tile creation
- small export with render/output CRS reprojection

### Current network coverage

`test/integration/test_export_network.py` covers:

- configurable WMS / XYZ export scenarios
- optional scale-dependent WMS probes via `scale_probe`
- scenario filtering via `SCENARIOS=name1,name2`
- opt-in execution via `ALLOW_INTEGRATION_NETWORK=1`

The scenario source of truth is `test/integration/config.json`.

## Packaging and Release

Primary packaging path:

```bash
make package
```

Archive validation:

```bash
make package-check
```

Full local release gate:

```bash
make release-check
```

Release details are documented in `docs/RELEASING.md`.

## CI

The repository uses two layers of automated validation:

- fast lint + stubbed Python suite on plain CI runners
- QGIS-backed suite inside the official `qgis/qgis` container image

## Troubleshooting for Developers

For runtime issues, also check:

- QGIS message log: `CustomMapDownloader`
- Python logging categories:
  - `custom_map_downloader.export`
  - `custom_map_downloader.ui`
