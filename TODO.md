# TODO – Custom Map Downloader

Bereinigte Aufgabenliste mit noch offenen Punkten. Bereits umgesetzte Themen
werden hier nicht mehr als offene Tasks geführt.

---

## 0. Meta

- All comments and docstrings must be in **English**.
- UI object names should remain English; semantics must stay consistent.
- The codebase should remain QGIS-plugin-style and QGIS-compatible.
- Avoid redundant logic; prefer QGIS-native components (e.g. `QgsExtentGroupBox`, `QgsProjectionSelectionWidget`).
- Use **extent-based workflows only** in the UI; center handling is internal.

---

## 1. UI SYSTEM (DIALOG)

### 1.1 Completed / current state

- Replaced manual extent widgets with native `QgsExtentGroupBox`.
- Removed explicit **“Use Center” / Center Mode** from the UI; center is derived internally from extent.
- Added `QgsProjectionSelectionWidget` for CRS selection.
- Reorganized layout into:
  - Source & Output
  - Extent
  - Resolution (GSD)
  - VRT / Tiling
  - Options
- Fixed resizing behavior:
  - Small buttons (browse, refresh, etc.) use fixed size policies.
- Cleaned up tab order.
- Added extent information label showing:
  - physical extent in meters
  - derived pixel width/height.
- Added VRT/Tiling group box:
  - Checkbox to enable tiling
  - Tile size presets (e.g. 512, 1024, 2048, 4096)
  - Max columns/rows spin boxes
  - Tile grid preview label.
- Added warning/strong limit handling for very large raster sizes in the dialog and exporter.

### 1.2 Open tasks / improvements

- [x] World files are always written; checkbox removed
- [ ] Optionally add tooltip/help icons:
  - Explanation of GSD
  - Explanation of tiling / VRT semantics.
- [ ] Add explicit warning label when derived pixel size exceeds a configurable threshold (e.g. > 20k × 20k).
- [ ] Add an option to **lock aspect ratio** or show an explicit aspect ratio indicator between width and height.
- [ ] Add a small “info” popup for advanced users describing the internal tiling/VRT behaviour (current vs. planned).

---

## 2. PARAMETER MODEL (`get_parameters()` + `ExportParams`)

### 2.1 Completed

- Unified parameter model in the dialog:
  - `west`, `east`, `south`, `north` (extent in project CRS)
  - `northing`, `easting` (center, derived from extent)
  - `gsd` (map units per pixel)
  - `width`, `height` (derived pixels)
  - `output_directory`, `output_prefix`, `output_path`
  - `layer`, `load_as_layer`
  - `create_vrt`, `vrt_max_cols`, `vrt_max_rows`, `vrt_preset_size`.
- Mirrored these parameters into `ExportParams` using:
  - `ExtentSpec`
  - `CenterSpec`
  - tiling/VRT-related fields.
- Added exporter-side validation for oversized rasters, GSD min/max, and output path/extension checks.

### 2.2 Open tasks

- [ ] Add validation for:
  - maximum allowed pixel width/height (e.g. to prevent accidental 100k × 100k exports).
- [ ] Query layer/service GSD bounds (min/max) and clamp or warn in UI when outside supported range.

- [ ] Enforce valid file extension:
  - Ensure export always uses `.tif` for GeoTIFF.
- [x] Pre-export summary/confirmation dialog is available

---

## 3. MAIN PLUGIN LOGIC (`CustomMapDownloader.py`)

### 3.1 Completed

- Adapted to the new extent-only parameter model.
- Uses project CRS as base; falls back to `EPSG:3857` if project CRS is not metric.
- Constructs `CenterSpec` and `ExtentSpec` in project CRS.
- Passes tiling parameters (`create_vrt`, `vrt_max_cols`, `vrt_max_rows`, `vrt_preset_size`) into `ExportParams`.
- Provides a progress dialog with a unified progress callback and translated status texts.
- Applies increased network timeout for long running WMS/XYZ requests.

### 3.2 Open tasks

- [ ] Add plugin-settings persistence using `QSettings`:
  - last used layer (by layer ID or name)
  - last used output folder
  - last used CRS
  - last used GSD.
- [x] JSON-based export profiles (save/load) are available
- [ ] Investigate background/non-modal exports:
  - Kick off exports without blocking the main UI (job queuing).

---

## 4. EXPORT ENGINE (`core/exporter.py`)

### 4.1 Completed / current state

- Uses `ExportParams`, `CenterSpec`, `ExtentSpec`.
- Supports two logical modes:
  - Preferred: extent in a given CRS.
  - Fallback: center + GSD + width/height.
- Validates inputs and CRS units (meters).
- Handles rendering via `QgsMapRendererParallelJob`.
- Writes **georeferenced GeoTIFF** using GDAL:
  - `COMPRESS=LZW`
  - `TILED=YES`
  - `BIGTIFF=IF_SAFER`.
- Implements **internal tiling**:
  - Breaks large rasters into tiles.
  - Renders and writes each tile into one **single** GeoTIFF.
  - Includes retry logic + rate-limit wait for problematic tiles.
- Always writes GeoTIFF with GeoTransform + CRS.
- Supports multiple output formats:
  - GeoTIFF (internal georeferencing)
  - PNG / JPEG (world file + .prj)
- VRT-only mode:
  - writes tiles + .vrt
  - no merged raster output

### 4.2 Open tasks

- [x] `vrt_max_cols` / `vrt_max_rows` / `vrt_preset_size` are used for tile size selection
- [ ] Implement **true VRT writer**:
  - Option A: Write a single GeoTIFF plus VRT (mostly redundant).
  - Option B: Write multiple sub-tiles plus a `.vrt` referencing them (classic use case).
  - UI semantics must match actual behaviour.
- [ ] Add WMTS/XYZ-specific **resolution snapping**:
  - Query supported zoom levels.
  - Snap requested GSD to nearest zoom level.
  - “Strict mode”: forbid non-supported GSD ranges.
- [ ] Improve WMS-specific hints:
  - Parse server `ScaleDenominator` and/or `MAXWIDTH`/`MAXHEIGHT` to provide:
    - warnings about exceeding limits
    - suggestions for smaller extent or GSD.
- [ ] Investigate external GDAL pipeline (optional):
  - Use `gdalwarp` or similar for:
    - reprojection
    - resampling
    - advanced compression (ZSTD, JPEG, etc.).
- [ ] Format-specific behavior cleanup:
  - JPEG: alpha handling & background color
  - PNG/JPEG: compression & color depth options
- [ ] Optional palette / color depth reduction for “small file size” exports

---

## 5. CRS HANDLING

### Completed

- Uses project CRS by default.
- Falls back to `EPSG:3857` when project CRS does not use meters.
- Transforms extents using `QgsCoordinateTransform` with proper error handling.
- Validates that render CRS uses meters when GSD is interpreted as meters/pixel.

### Open tasks

- [ ] Add UI warning when the user selects a CRS whose map units are not meters (e.g. degrees).
- [ ] Optionally auto-change CRS to a suggested projected CRS (for known EPSG codes).
- [ ] Add unit tests for CRS transformations:
  - extent transformations
  - center transformations
  - failure paths.

---

## 6. LAYER HANDLING

### Completed

- Layer combo box listing all project layers.
- Refresh button to repopulate the layer list.
- Connects `QgsExtentGroupBox` to the selected layer for “extent from layer”.

### Open tasks

- [ ] Add option: “Export all visible layers as a single stacked raster”:
  - Multi-layer rendering into one raster.
- [ ] Add option: “Export each visible layer separately”:
  - Iterative export using the same extent/GSD.
- [ ] Add option: “Export only selected features” for vector layers:
  - Clip raster to selection.
  - Or pre-filter layer before rendering.

---

## 7. FILE OUTPUT & METADATA

### Completed

- Always writes world files (.tfw/.pgw/.jgw depending on format).
- Optionally loads exported raster into the QGIS project.

### Open tasks

- [ ] Add embedded metadata in GeoTIFF:
  - plugin version
  - render CRS
  - GSD
  - extent
  - timestamp
  - optionally originating layer name/ID.
- [ ] Add optional checksum (e.g. MD5) generation:
  - allows reproducibility checks.
- [ ] Support alternative GDAL compression options:
  - DEFLATE
  - ZSTD
  - JPEG (where appropriate).

---

## 8. PERFORMANCE & NETWORK

### Open tasks

- [ ] Tune retry/backoff strategy for tile rendering:
  - Smarter detection of rate limits vs. network errors.
- [ ] Expose network timeout and backoff parameters as plugin settings.
- [ ] Add optional caching layer for XYZ/WMTS/WMS tiles:
  - Reduce server load
  - Speed up repeated exports.

---

## 9. ERROR HANDLING

### Completed

- Central error mapping in `_format_export_error` (codes + user-friendly messages).
- Distinguishes:
  - validation errors
  - render errors
  - CRS errors
  - cancellation.

### Open tasks

- [ ] Add “technical details” section in error message box:
  - button “Copy details to clipboard”.
- [ ] Add optional “debug log” window or file:
  - record step-by-step exporter actions
  - record GDAL/CRS errors.

---

## 10. TESTING & TOOLING

### Open tasks

- [ ] Create unit tests for:
  - parameter parsing in `get_parameters()`
  - extent/center calculation logic
  - GSD → pixel size conversion
  - tiling grid calculation
  - world file writer.
- [ ] Integration tests using QGIS Python API:
  - end-to-end export of test layers.
- [ ] Provide sample data:
  - simple raster (local GeoTIFF)
  - sample XYZ tile URL
  - vector layer for mixed cases.
- [ ] CI pipeline (GitHub Actions):
  - run tests
  - build plugin ZIP
  - attach artifact to releases.

---

## 11. DOCUMENTATION

### Completed

- README updated for:
  - extent-only workflow
  - GSD-based resolution
  - VRT/Tiling group
  - world file semantics.   

### Open tasks

- [ ] Add `USAGE.md` with concrete step-by-step examples:
  - export of XYZ basemap
  - export of WMS orthophoto
  - large extent with tiling.
- [ ] Add `API.md` documenting:
  - `ExportParams`
  - `ExportError`, `ValidationError`, `CancelledError`
  - exporter lifecycle.
- [ ] Add `CONTRIBUTING.md` with:
  - coding style
  - docstring rules
  - test expectations.
- [ ] Maintain an explicit `CHANGELOG.md` file (mirroring README’s changelog).
- [ ] Add animated GIFs or short screen recordings.

---

## 12. LONG-TERM IDEAS

- [ ] QGIS Processing toolbox integration:
  - expose exporter as processing algorithm.
- [ ] Command-line / headless mode:
  - run exports from a Python console or external scripts.
- [ ] Optional integration with project bookmarks:
  - named extents for quick selection.
- [ ] Optional integration with project layouts:
  - export map extent from a layout map item directly.
