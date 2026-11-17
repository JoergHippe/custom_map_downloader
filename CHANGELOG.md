# Changelog

All notable changes to this project are documented in this file.

The format follows a pragmatic Keep a Changelog style.

## [0.5.0] - Unreleased (working version)

### Added
- Independent GDAL fingerprints for GeoTIFF file bytes, decoded pixel bands,
  and georeferencing; optional CLI to compare original versus current rasters.
  Official WMS diagnostics now retain these independent checksums in reports.
- Explicitly opt-in official WMS smoke workflow with isolated, time-bounded
  service checks and separate export-versus-reference-hash reporting.
- Automated native Windows QGIS 3/4 CI with real Qt GUI interaction,
  raster, MBTiles and local WMS/WMTS end-to-end tests.
- Reproducible loopback OGC test services for WMS GetCapabilities/GetMap
  and WMTS GetCapabilities/GetTile; no external service dependency in CI.
- MBTiles preflight warnings based on estimated tile count and PNG data size
  (including the configurable tile dimensions);
  very large exports require explicit one-time confirmation even when ordinary
  confirmation prompts are disabled. No hard export size limit is imposed.
- MBTiles export with configurable zoom range, tile size, padding, auto zoom and estimates (April 2026)
- unified output-file selection for raster and MBTiles exports

### Fixed
- Explicitly close SQLite reader connections in MBTiles integration tests:
  Windows otherwise locks the file and prevents temporary-directory cleanup.
- Fixed coordinate field aliasing in the QgsExtentGroupBox fallback: X maximum
  no longer resolves to the Y maximum editor.
- Removed guessed, language-sensitive field matching and direct writes into
  private QGIS coordinate editors; exact-name fallback now fails closed.
- Corrected locale-independent parsing of mixed German/English grouped decimals.
- Saved export profiles now restore the actual selected extent, not only the current canvas extent.
- Added real QGIS 3/4 extent-dialog regression tests including map-canvas drawing and CRS changes.
- MBTiles exports now stage SQLite data in the destination folder and replace the
  destination only after a successful commit and closed database connection.
  Existing outputs are preserved when an export fails or is cancelled.
- Removed hard-coded PyQt5 resource loading; added Qt5/Qt6 compatible imports
  and copied QImage buffers to NumPy-owned memory.

### Changed
- Historical SHA-256 differences from regularly updated public WMS data are
  advisory, not failures of technically successful exports. Catalog and
  scale-matrix validators still reject missing/failed reports, while the
  live smoke explicitly does not grant a release approval.
- MBTiles tile plans now compute exact tile counts up front and generate tile
  extents lazily during export instead of allocating a tuple of all tiles.
  `MbtilesPlan.tiles` is now an iterable generator; index access is no longer supported.
- Restored GitHub Actions checks for QGIS 3/4, unit tests and packaging.
- canvas extent reset and draw-on-canvas dialog handling (April 2026)
- Original self-hosted Windows Actions archived in October 2026; new hosted CI enabled in November.

### Validation
- Native Windows/QGIS 3.44.15 and 4.2.3 integration tests passed on 2026-11-17.
- The last **full official public-service and official-installer** release validation
  dates from 2026-03-14; these newer CI tests do not replace it.
- This version is NOT marked as freshly release-validated; see docs/VALIDATION_STATUS.md.

## [0.4.0] - 2026-03-14

### Added
- strict hash-gated validation for the official Windows/QGIS scale matrix
- strict hash-gated validation for the broad official WMS catalog
- isolated Windows/QGIS scenario runner for non-scale web service coverage
- dedicated German validation status documentation

### Changed
- scheduled and hardened Windows/QGIS validation workflow
- web map layers now use the tiled export path for runtime stability
- broader official service coverage across BKG and multiple federal states
- release documentation now treats scale and catalog reports as explicit release gates

### Fixed
- stabilized web map export behavior on Windows/QGIS for previously crashing WMS cases
- hardened deploy/dev helper behavior for Windows junction removal
- corrected deploy-profile E2E import validation semantics on Windows
- aligned final validation and documentation with the real runtime behavior

## [0.3.0] - 2026-03-07

### Added
- target-scale mode for scale-dependent WMS portrayal
- JSON export profiles
- structured export diagnostics in UI dialogs
- local QGIS dev helpers for deploy, undeploy and profile-based startup
- translation maintenance workflow and German translation coverage checks

### Changed
- separated render CRS and output CRS handling
- modularized exporter helpers for rendering, raster operations, tiling and logging
- standardized packaging on `qgis-plugin-ci`
- improved documentation split across user, development, release and troubleshooting guides

### Fixed
- hardened locale startup handling
- robust VRT portability warning behavior
- clearer exporter fallback validation and sidecar error reporting
- removed stale legacy tooling and outdated compatibility metadata
