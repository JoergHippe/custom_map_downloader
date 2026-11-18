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

## Current Runtime and Public-Service Validation

Before a release, use [TESTING.md](TESTING.md) for current test requirements
and [OGC_TEST_POLICY.md](OGC_TEST_POLICY.md) for public-service interpretation.
Historical March 2026 results do not validate the current candidate.

1. Require successful current Linux/QGIS and native Windows/QGIS CI on the
   candidate commit. The Windows CI uses conda-forge, not the official QGIS installer.
2. Smoke-test the **packaged** plugin in a visible official Windows QGIS desktop:
   extent/CRS, raster, VRT, MBTiles, cancellation and supported layer reload.
3. Run the opt-in official WMS/WMTS and scale-matrix checks as needed and assess
   the broader official WMS catalog separately.
4. Treat missing/failed cases, invalid imagery, dimensions or georeferencing,
   and failed subprocesses as blockers until resolved.
5. Treat historical SHA-256 drift from public services as **advisory**, not as
   automatic failure of an otherwise valid export. Never silently reset baselines.
6. Record commit, date, versions, results and limitations in
   [VALIDATION_STATUS.md](VALIDATION_STATUS.md). CI is not a release approval.

Current optional live workflows: `.github/workflows/live-ogc.yml` and
`.github/workflows/live-scale-matrix.yml`. Historical local runner reports
(`scale_matrix_report.json`, `scenario_catalog_report.json`) can still be
generated for diagnosis; their gates permit advisory drift and reject
technical failures.


## Raster and VRT file safety

Raster exports are staged next to the target folder and published only after
their data and georeferencing sidecars are complete. Single-file replacement
uses same-filesystem renaming; files already loaded by QGIS or locked by Windows
may still prevent publication.

A VRT, its tiles and tile sidecars are a **set of files**: the exporter publishes
tiles first, then the VRT, and attempts to roll back all replacements if a
publish operation fails. Multi-file replacement is **not atomic as a group**,
so concurrent readers can briefly observe mixed tile versions. A failed
rollback may leave a separately named recovery directory and requires manual
attention. Old tiles not referenced by the new VRT are deliberately not
deleted automatically.

A VRT with invalid or nonportable source paths fails the export. Before
release, validate overwrite, cancellation, sidecar failure and VRT path
portability using the actual Windows QGIS distribution.

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
