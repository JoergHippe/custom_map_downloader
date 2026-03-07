# Changelog

All notable changes to this project are documented in this file.

The format follows a pragmatic Keep a Changelog style.

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
