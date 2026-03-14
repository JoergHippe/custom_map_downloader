# Validation Status

This document summarizes the currently verified runtime status of the plugin against real Windows/QGIS runs and the maintained automated checks.

## Current Overall Assessment

Current state:

- release-capable
- operationally well structured
- repeatedly validated on real Windows/QGIS runtime
- not risk-free in the absolute sense, because public web services can still change upstream

Practical conclusion:

- the plugin is in a professional and production-ready state for normal release and use
- remaining risks are now mostly external runtime risks, not obvious engineering gaps in the plugin core

## Verified Test Layers

### Local repository checks

Verified locally:

- `ruff` on `custom_map_downloader`, `scripts`, `test`
- `black --check` on `custom_map_downloader`, `scripts`, `test`
- `python3 -m unittest discover -s test -v`

Latest local suite result:

- `67 tests`
- `OK`
- `8 skipped` because QGIS-backed integration tests require real QGIS runtime

### Real Windows/QGIS validation

Verified on host runtime:

- QGIS import path / profile bootstrap
- E2E smoke path
- required scale matrix
- broad official WMS catalog

The broad catalog was first used to reproduce native Windows/QGIS crashes in the direct web-layer render path. After moving web layers to the tiled render path, the same catalog was re-run successfully and then hash-baselined.

## Required Scale Matrix

The following scale-dependent cases are currently part of the strict required `scale_matrix` and are hash-gated:

| Case | Service Type | Source | Status |
| --- | --- | --- | --- |
| `geosn_ortho_gray_scale_matrix` | Orthophoto | Sachsen | verified |
| `basemap_gray_scale_matrix` | Topographic basemap | BKG | verified |
| `basemap_color_scale_matrix` | Topographic basemap | BKG | verified |

Validation model:

- two target scales per case
- real Windows/QGIS runtime
- required hash comparison for `small` and `large`
- CI gate via `scripts/check_scale_matrix_report.py`

## Official Webmaps Catalog

The following broad official-service catalog is now maintained as `scenario_groups.official_webmaps_catalog` and is also hash-gated:

| Scenario | Category | Provider | Region | Result |
| --- | --- | --- | --- | --- |
| `basemap_gray_tif` | Topographic basemap | BKG | Germany | verified |
| `bkg_dgm200_relief_tif` | DGM-derived relief | BKG | Germany | verified |
| `geosn_ortho_color` | Orthophoto | GeoSN | Sachsen | verified |
| `bayern_dop40_tif` | Orthophoto | Bayern | Bayern | verified |
| `nrw_dtk_color_tif` | Topographic map | NRW | Nordrhein-Westfalen | verified |
| `bayern_relief_tif` | DGM-derived relief | Bayern | Bayern | verified |

Verified baseline hashes:

| Scenario | Size | SHA256 |
| --- | --- | --- |
| `basemap_gray_tif` | `1000x1000` | `60f9f19c8757aad1b0d9f354f81033fd740822b2d44c39b243a31bbe7bf9f4f4` |
| `bkg_dgm200_relief_tif` | `200x200` | `a03d06bd4c2c55bb7ff5e908eb742198ed9371ea3e7293976bac0e7850655a7a` |
| `geosn_ortho_color` | `5000x5000` | `a5d18b3a2732435af9ee5bc2a418affcf30e2b47b071a39b0ecde8df8752bfde` |
| `bayern_dop40_tif` | `1250x1250` | `f38c8a896f03412f43143059aea349508e6191621438ed3d894b47c65e5afece` |
| `nrw_dtk_color_tif` | `1000x1000` | `aac68ebef8537087edf05251b617732af96bd582e814b32254debb7ee8d0c1d0` |
| `bayern_relief_tif` | `500x500` | `0299bb2651063ca34a7d01bc7ae0b967475a820f29798a4be4e67791bf7122a9` |

Validation model:

- isolated per-scenario Windows/QGIS child process
- per-scenario `stdout.log` and `stderr.log`
- per-scenario `network_scenarios.json`
- catalog report:
  - `scenario_catalog_report.json`
  - `scenario_catalog_report.md`
- strict gate via `scripts/check_network_catalog_report.py`

## Important Historical Finding

Before the latest exporter change, several real web-map scenarios crashed natively on Windows/QGIS in the small direct render path with `3221225477`.

Affected before the fix:

- `basemap_gray_tif`
- `bayern_dop40_tif`
- `nrw_dtk_color_tif`
- `bayern_relief_tif`

Engineering consequence:

- web layers are now routed through the tiled export path for runtime stability

Re-validation after the fix:

- the same official catalog completed successfully
- the strict hash-gated verification run also completed successfully

## Remaining Risks

There are still residual risks, but they are now mostly external and expected:

1. Public service drift
   - styles, caches, backend software or source data can change upstream
   - this can trigger hash drift even when the plugin code is still correct

2. Environment variation
   - different QGIS / GDAL builds can still behave differently
   - the strongest current assurance is the maintained Windows/QGIS host runtime

3. Uncovered service classes
   - the project now covers a solid set of official WMS types
   - it still does not prove correctness for every possible third-party WMS/WMTS implementation

## Professionalism / Production Readiness

Honest current answer:

- yes, the project is now professionally implemented and production-ready in a serious sense
- no, that does not mean "nothing can ever fail"

More precise wording:

- code structure, tests, CI gates, release governance, diagnostics and real-runtime validation are now at a clearly professional level
- the main remaining failure modes are public-service drift and environment differences, not missing basic engineering discipline

## Recommended Operational Use

Before a release:

1. run the normal local release gate
2. check the latest Windows/QGIS scale matrix report
3. check the latest official webmaps catalog report
4. if either report shows drift or error, stop and classify it before publishing
