# Changelog

All notable changes to this project are documented in this file.

The format follows a pragmatic Keep a Changelog style.

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
