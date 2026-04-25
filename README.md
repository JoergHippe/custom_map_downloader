# Custom Map Downloader

Custom Map Downloader is a QGIS plugin for exporting map content from raster, vector and web map layers with controlled extent, resolution, target scale, output CRS, optional tiling/VRT output and MBTiles output.

## What It Does

- exports visible QGIS layers including WMS, WMTS, XYZ, raster and vector sources
- uses the native QGIS extent widget for extent selection
- supports two resolution modes:
  - `Ground resolution (m/px)`
  - `Target scale (1:n)` for scale-dependent WMS portrayal
- supports `GeoTIFF`, `PNG`, `JPEG`, optional `VRT` tile mosaics and `MBTiles`
- writes georeferenced output, including sidecars where required
- can load the result back into the current QGIS project

## Installation

### From the QGIS Plugin Repository

1. Open QGIS.
2. Go to `Plugins -> Manage and Install Plugins`.
3. Search for `Custom Map Downloader`.
4. Install and enable the plugin.

### Manual Installation

1. Download the release ZIP.
2. Extract it into your QGIS plugin directory.
3. Restart QGIS and enable the plugin.

## Compatibility

- supported QGIS baseline: `3.34+`
- developed and repeatedly validated with real Windows/QGIS runtime checks
- public WMS/XYZ services can still change portrayal, availability or response behavior upstream
- scale-dependent web-layer validation is covered by the maintained Windows/QGIS `scale_matrix`
- for scale-sensitive exports, prefer a projected CRS with meter units

## Basic Workflow

1. Open the plugin from the toolbar or plugin menu.
2. Choose the source layer.
3. Choose the output file.
4. Select the output CRS.
5. Define the extent.
6. Choose either `Ground resolution (m/px)` or `Target scale (1:n)`.
7. Choose `MBTiles` when you need a Web Mercator tile pyramid for offline/web use.
8. Optionally enable `Create VRT` for tiled raster output.
9. Start the export.

## Important Behavior

### Target Scale and WMS

Some WMS services change portrayal depending on scale. For those services, `Target scale (1:n)` is the correct mode.

- target scale mode requires a projected output CRS with meter units
- web map layers are rendered through the tiled export path for runtime stability
- for stable portrayal, the plugin may render internally in a metric CRS and then reproject the final raster into the requested output CRS
- VRT export is most predictable when render CRS and output CRS are identical

### Output Formats

- `GeoTIFF`: internal georeferencing plus world file
- `PNG` / `JPEG`: world file plus `.prj` sidecar
- `VRT`: tiled GeoTIFF output plus a `.vrt` mosaic
- `MBTiles`: SQLite tile pyramid with PNG tiles in Web Mercator (`EPSG:3857`)

### MBTiles

MBTiles export uses the exact selected QGIS extent. It does not provide a center/radius mode.

- bounds are derived from the selected extent and stored in WGS84
- tiles render as Web Mercator PNG tiles
- zoom range, tile size and optional padding are configurable
- padding defaults to `0` so the tile range stays closest to the selected extent
- the dialog shows live tile count and a rough file size estimate

## Profiles

The plugin can save and restore reusable JSON export profiles.

Profiles store:

- output file path
- selected layer reference
- output CRS
- extent
- resolution mode, GSD and target scale
- VRT / tiling settings
- MBTiles zoom, tile size and padding settings
- `Load as layer`

## Diagnostics

The plugin provides diagnostics in several places:

- progress dialog during export
- success/warning/error dialogs
- expandable `Show Details` section in those dialogs
- QGIS message log under `CustomMapDownloader`

## Language Support

The plugin ships with English source strings and a German translation.
Translations are maintained via the standard Qt Linguist workflow under `custom_map_downloader/i18n/`.

## Documentation

- user operations and support: `docs/TROUBLESHOOTING.md`
- validation status and verified service coverage: `docs/VALIDATION_STATUS.md`
- development workflow: `docs/DEVELOPING.md`
- release process: `docs/RELEASING.md`
- integration test details: `tests/integration/README.md`

## License

GPL v2 or later. See `LICENSE`.
