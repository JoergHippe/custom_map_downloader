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

For Windows/QGIS E2E verification you can also set `CMD_INTEGRATION_REPORT_DIR` before running the integration batch helper. The network suite then writes JSON result artifacts, including scale-matrix hashes. Keep unstable public-service probes in `experimental_scale_matrix`; only stable cases belong in the default release gate.

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
