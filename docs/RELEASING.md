# Release Process

This project uses `qgis-plugin-ci` as the primary packaging path. Legacy packaging paths are intentionally not maintained.

## Preconditions

- Development dependencies installed:
  - `make install-dev`
- Working tree clean:
  - `git status --short`
- Version updated in `custom_map_downloader/metadata.txt`
- Version entry added to `CHANGELOG.md`
- Relevant user-facing documentation updated:
  - `README.md`
  - `docs/TROUBLESHOOTING.md`

## Standard Release Checklist

Run the full local release gate:

```bash
make release-check
```

This runs:

- `ruff`
- `black --check`
- the fast test suite
- translation status validation
- changelog / metadata release-governance validation
- package build via `qgis-plugin-ci`
- package content validation via `scripts/check_package.py`

`make release-check` covers the repository-local gate. It does not replace the Windows/QGIS runtime verification below.

## Recommended Manual Smoke Check

Before publishing, validate the built plugin once in a real QGIS runtime:

1. Deploy the current source tree into a QGIS profile:
   - `make deploy-dev`
2. Start QGIS against that profile:
   - Windows: `start_qgis_dev.bat`
3. Smoke-check:
   - plugin opens
   - extent selection works
   - standard GeoTIFF export works
   - VRT export works
   - target scale mode works
   - output loads back into QGIS
4. Remove the dev deployment if needed:
   - `make undeploy-dev`

For Windows/QGIS E2E verification you can also set `CMD_INTEGRATION_REPORT_DIR` before running the integration batch helper. The network suite then writes JSON result artifacts, including scale-matrix hashes. The required `scale_matrix` now contains only repeatedly validated public-service cases; reserve or newly added probes belong in `experimental_scale_matrix` until they prove stable.

Recommended release-grade runtime validation:

1. Run the Windows/QGIS E2E workflow or the equivalent local batch helper against a real QGIS installation.
2. Generate the scale-matrix summary and report artifacts.
3. Enforce the report gate:
   - required `scale_matrix` cases must all be `ok`
   - `experimental_scale_matrix` may contain `untracked` reserve probes
4. Treat any `drift`, `missing` or `error` status in the required matrix as a release blocker.

Relevant report files:

- `scale_matrix_summary.json`
- `scale_matrix_report.json`
- `scale_matrix_report.md`

Relevant gate:

- `scripts/check_scale_matrix_report.py`

## Package Output

Release archives are built from `custom_map_downloader/` only. The package validator ensures that the ZIP does not accidentally include:

- tests
- CI files
- translation source files (`.ts`)
- other repository-only artifacts

## Publishing Notes

- Commit and push the release-ready state before publishing.
- Keep `CHANGELOG.md` aligned with the version in `custom_map_downloader/metadata.txt`.
- Keep the short `changelog=` summary in `custom_map_downloader/metadata.txt` aligned with the current release.
- If the release changes export semantics or operational behavior, update `docs/TROUBLESHOOTING.md`.
- Keep `experimental_scale_matrix` empty unless you intentionally park non-baselined reserve probes there.
