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
run_integration_tests.bat e2e myprofile
```

The modes `all`, `smoke` and `network` import the plugin code directly from the repository.
The mode `e2e` deploys the plugin into the selected QGIS profile first and then runs the smoke suite against the deployed plugin import path.

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
- explicit scale-dependent WMS probes via `scale_matrix`
- scenario filtering via `SCENARIOS=name1,name2`
- opt-in execution via `ALLOW_INTEGRATION_NETWORK=1`

The scenario source of truth is `test/integration/config.json`.
If `CMD_INTEGRATION_REPORT_DIR` is set, the network suite writes JSON reports for scenario runs and the scale matrix.

## Translations

Plugin translations follow the standard QGIS / Qt Linguist workflow.

Translation source files live in `custom_map_downloader/i18n/*.ts`.
Compiled runtime files live next to them as `*.qm`.

Typical maintainer flow:

```bash
make translations-update LOCALES=de
make translations-status
make translations-compile LOCALES=de
```

Notes:

- keep source strings in code and UI files in English
- route all user-visible strings through `tr(...)`
- prefer `unfinished` entries over fake copied-English translations
- rebuild `.qm` files before packaging or release
- `pylupdate5` and `lrelease` usually come from the QGIS / Qt toolchain, not from the plain tooling-only `.venv`

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
- optional self-hosted Windows/QGIS workflow via `.github/workflows/windows-qgis-e2e.yml`

The Windows workflow runs the required scale matrix in isolated child processes via `scripts/run_windows_qgis_matrix.py` so that a crashing provider case does not hide the outcome of the remaining cases.
Unstable public-service probes stay in `experimental_scale_matrix` and should be executed manually via `--matrix-key experimental_scale_matrix` until they are proven reliable.
For single-case crash analysis, use `scripts/probe_windows_scale_case.py`. It runs `small` and `large` in separate QGIS processes, which is the quickest way to see whether only one scale step is crashing.

## Troubleshooting for Developers

For runtime issues, also check:

- QGIS message log: `CustomMapDownloader`
- Python logging categories:
  - `custom_map_downloader.export`
  - `custom_map_downloader.ui`
