# Troubleshooting

## Transparent or Empty Export

Symptoms:

- exported raster is fully transparent
- export fails with a render-empty message

Typical causes:

- WMS/XYZ timeout
- service-side `WIDTH` / `HEIGHT` limits
- extent outside valid layer coverage
- provider throttling
- unstable provider/runtime interaction in direct single-render requests

Actions:

1. Reduce output size or use tiling/VRT mode.
2. Increase ground resolution (larger `m/px`) or use a larger target scale denominator.
3. Verify the chosen extent against the source layer.
4. Retry with a projected metric CRS.

Note:

- the exporter now prefers tiled rendering for web layers to avoid known Windows/QGIS crashes in direct render mode

## VRT Not Portable

Symptoms:

- the exporter rejects a VRT whose tile paths cannot be made relative
- a previously exported VRT does not work after its folder was moved

Causes:

- source paths in the VRT XML could not be rewritten or verified
- tiles were moved separately from the VRT

Actions:

1. Keep the VRT and its referenced tiles in the same folder.
2. Inspect the VRT's `SourceFilename` entries and verify relative paths.
3. Check the QGIS message log and export diagnostics. New VRT exports
   with nonportable tile paths fail before publication instead of being
   reported as successful with a warning.

## Publication or Recovery Failed

The export first writes files to staging and publishes them afterward.
A completed raster render does **not** mean that the target files have
already been replaced.

- `ERR_EXPORT_STAGE_INCOMPLETE`: Staging did not produce a complete
  primary output. The previous target was not replaced.
- `ERR_EXPORT_PUBLISH_ROLLED_BACK`: Publishing failed, but the prior
  target files were restored and newly published files were removed.
- `ERR_EXPORT_PUBLISH_RECOVERY_REQUIRED`: Publishing and rollback both
  failed. Some destination files may be missing or changed.

For recovery-required errors:

1. Do not start another export to the same destination yet.
2. Open **Details** in the error dialog or the QGIS message log to find
   the recovery or preserved staging directory.
3. Compare the target folder with backed-up files; only restore or
   delete files after checking which versions belong together.
4. On Windows, close QGIS layers or other applications holding these
   files open before retrying.

A VRT with multiple tiles and sidecars cannot be published as a single
atomic filesystem operation. A recovery directory must not be
automatically deleted before its contents are inspected.

## Output CRS vs Render CRS

Symptoms:

- export succeeds but internal rendering does not use the selected output CRS

Explanation:

- for stable scale-dependent WMS rendering, the plugin may render in a metric CRS and then reproject into the requested output CRS

Actions:

1. Use a projected metric CRS when target scale matters.
2. Prefer identical render/output CRS for VRT exports.
3. Check the export logs to confirm the effective render/output CRS pair.

## Slow or Repeated Tile Retries

Symptoms:

- progress dialog repeatedly shows tile retries

Typical causes:

- overloaded remote service
- intermittent network problems
- very aggressive target resolution

Actions:

1. Retry later.
2. Use a coarser resolution or larger target scale denominator.
3. Reduce extent size.
4. Prefer tiling for large requests.

## MBTiles Export Is Very Large

Symptoms:

- tile estimate is unexpectedly high
- export is slow or creates a large `.mbtiles` file

Typical causes:

- high maximum zoom
- broad selected extent
- non-zero padding across several zoom levels

Actions:

1. Reduce `Max zoom`.
2. Keep `Padding tiles` at `0` unless the consuming map client needs surrounding tiles.
3. Split the area into smaller exact extents.
4. Use `Auto-detect min zoom` only as a starting point and review the resulting tile estimate.

## Public WMS Changes Style or Content

Symptoms:

- a previously stable map or orthophoto looks different
- a live-service report indicates historical hash `drift`
- the export itself may still have succeeded

Possible causes include changed source data, portrayal, service backend,
cache state, or differences in raster encoding.

Actions:

1. Check the current live WMS/WMTS or scale-matrix report and distinguish
   technical export status from historical hash comparison.
2. Verify raster validity, nonempty pixels, expected extent/CRS and dimensions.
3. Where relevant, compare independent pixel, georeference and file hashes
   with `scripts/raster_diagnostics.py`.
4. Keep prior reference hashes as dated evidence. Never replace them
   silently merely to make a diagnostic report green.

Historical hash changes alone are **not** an automatic test or release
failure. See [OGC_TEST_POLICY.md](OGC_TEST_POLICY.md).

## QGIS CI or Optional Public-Service Validation Failed

Symptoms:

- active Linux/Windows QGIS CI is red
- an opt-in official WMS/WMTS or scale-matrix run fails
- a required test is missing, skipped unexpectedly, or has a nonzero exit code

Actions:

1. Identify which test actually failed: deterministic QGIS/Qt/OGC
   integration or external public-service validation.
2. Check job logs and any saved result artifacts. For local isolated
   network cases, inspect `scale_matrix_report.json`,
   `scenario_catalog_report.json`, `stdout.log`, and `stderr.log`
   when generated.
3. Reproduce technical failures with the matching QGIS environment
   and a minimal case. Public-service availability failures may need
   a separate run to distinguish a service outage from a plugin defect.
4. Investigate incorrect content, extent, CRS, dimensions and child
   process failures before approving a release. A hash-only difference
   with a valid export is advisory, not an automatic blocker.

The old scheduled self-hosted Windows workflow is no longer active.
See [TESTING.md](TESTING.md) for maintained CI and release requirements.

## Export Works But Layer Does Not Reload

Symptoms:

- export completes, but QGIS cannot load the saved raster automatically

Typical causes:

- partial file mismatch
- unsupported sidecar state
- temporary file/permission issue

Actions:

1. Open the saved path manually in QGIS.
2. Check whether the raster file exists and has sidecars where expected.
3. Review the QGIS message log for the saved path and warnings.

## Where to Look for Diagnostics

- Progress dialog: immediate status and warnings
- Success/warning dialogs: export outcome
- Dialog button `Show Details`: technical export context, warning list and error details
- QGIS message log: runtime warnings and errors under `CustomMapDownloader`
- Python logging category:
  - `custom_map_downloader.export`
  - `custom_map_downloader.ui`
