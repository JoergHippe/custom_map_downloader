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

- VRT opens locally but not after moving the folder
- success dialog contains a portability warning

Cause:

- tile paths in the `.vrt` could not be rewritten to relative paths

Actions:

1. Keep the VRT and tiles together in the same folder.
2. Treat the result as locally usable but not safely portable.
3. Check the QGIS message log and Python logs for the rewrite failure details.

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

## Public WMS Changes Style or Content

Symptoms:

- a previously stable topographic map, orthophoto or relief export suddenly looks different
- Windows/QGIS scale matrix starts reporting hash drift
- export still succeeds, but visual portrayal changed

Typical causes:

- upstream provider changed symbology or cartographic rules
- service backend or cache was updated
- the public service now serves different source data

Actions:

1. Check the latest `scale_matrix_report.md` or `scale_matrix_report.json`.
2. Re-run the affected case in real Windows/QGIS runtime.
3. Distinguish between expected upstream change and plugin regression.
4. Only update `expected_hashes` after repeated confirmation on the maintained runtime.

## Windows/QGIS Validation Workflow Failed

Symptoms:

- scheduled or manual Windows/QGIS workflow fails
- CI artifacts contain `scale_matrix_summary.json` but the gate is red
- one or more required matrix rows show `drift`, `missing` or `error`

Actions:

1. Inspect uploaded artifacts, especially:
   - `scale_matrix_summary.json`
   - `scale_matrix_report.json`
   - `scale_matrix_report.md`
   - per-case `stdout.log` / `stderr.log`
2. Re-run the failing case with `scripts/probe_windows_scale_case.py`.
3. If the issue is provider-side drift, keep the release blocked until the baseline decision is explicit.
4. If the issue is a plugin regression, fix the exporter or service handling before promoting a new baseline.

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
