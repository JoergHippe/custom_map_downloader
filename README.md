# Custom Map Downloader (QGIS Plugin)

## Overview
Custom Map Downloader is a QGIS plugin to export map content from layers and map services
(WMS, WMTS, XYZ, raster and vector layers) with precise control over extent, resolution
(GSD), output CRS and tiling.

---

## Description

Custom Map Downloader allows users to export **georeferenced GeoTIFF** images from any loaded layer in QGIS.

The plugin works purely **extent-based**:

- The geographic rectangle is selected interactively via the QGIS-native `QgsExtentGroupBox` (layer extent, canvas extent, CRS transformation handled by QGIS).
- The plugin derives the center internally from the selected extent (no separate “Center Mode” in the UI anymore).
- Output resolution is controlled by a single **GSD** value (map units per pixel); pixel width/height are derived from extent and GSD.

The selected layer is rendered at the requested output resolution and stored as a fully georeferenced **GeoTIFF**.  
Optionally, an additional **world file (.tfw)** can be written next to the GeoTIFF.

Typical use cases include:

- Extracting satellite imagery or base maps
- Exporting XYZ/WMTS/WMS layers for offline usage
- Preparing analysis rasters for specific regions
- Generating image datasets for ML/AI workflows

---

## Features

- ✔ **Export any visible QGIS layer** (XYZ/WMTS/WMS, raster, vector, etc.) :contentReference[oaicite:1]{index=1}  
- ✔ **QGIS-native extent control** using `QgsExtentGroupBox`
- ✔ **Extent-based workflow only**:
  - Extent defined via layer extent, canvas extent, or manual extent box
  - Center is derived internally from the chosen extent
- ✔ **Single resolution parameter**:
  - **GSD** (map units per pixel, typically meters per pixel)
  - Pixel **width/height are derived** from extent and GSD
- ✔ **Selectable CRS** via `QgsProjectionSelectionWidget`
- ✔ **Selectable output format: GeoTIFF, PNG, JPEG**
- ✔ **Always georeferenced output**
  - *GeoTIFF*: internal georeferencing + world file
  - *PNG/JPEG*: world file + .prj sidecar
- ✔ **Optional automatic loading of exported raster into QGIS**
- ✔ **Progress reporting** during render/export
- ✔ **LZW-compressed, tiled GeoTIFF output**
- ✔ **Internal tiling support** (large projects are chunked into tiles internally; preview of tile grid in the dialog)

---

## Installation

### From QGIS Plugin Repository (recommended)

1. Open QGIS  
2. Go to `Plugins → Manage and Install Plugins`  
3. Search for **Custom Map Downloader**  
4. Click **Install**

### Manual Install

1. Download the latest ZIP from the repository
2. Extract it
3. Place the folder into your QGIS plugin directory
4. Restart QGIS and enable the plugin

---

## User Interface Overview

The dialog consists of several main sections. The exact layout may evolve, but the semantics remain stable. :contentReference[oaicite:2]{index=2}

### 1. Source and Output

- **Layer selection**
  - Pick the QGIS layer that should be rendered (XYZ/WMTS/WMS, raster, vector, etc.).
- **CRS selection**
  - `QgsProjectionSelectionWidget` for choosing the output/render CRS.
  - By default, the project CRS is used; if it does not use meters, the exporter may fall back to `EPSG:3857` internally.
- **Output path**
  - Output directory (folder)
  - Output file prefix
  - Final file name is typically `<prefix>.tif`.

### 2. Extent

- Uses the native **`QgsExtentGroupBox`**:
  - Buttons for:
    - Current map canvas extent
    - (Where available) extent from a selected layer or other built-in sources
  - Extent CRS and transformations are handled by QGIS.
- Internally, the plugin computes:
  - West/East/South/North in project CRS
  - Center (X/Y) for downstream logic
- A small information label shows:
  - Physical size in meters (`Extent: xx.xx m × yy.yy m`)
  - Derived pixel size (`Size: width_px × height_px`)

There is **no separate “Use Center” / “Center Mode” UI** anymore; extent is the single source of truth.

### 3. Resolution

- **GSD (map units / pixel)**
  - Single `QDoubleSpinBox` for GSD (e.g. meters per pixel).
  - Extent + GSD → derived pixel width/height.
- **Extent information label**
  - Updated whenever extent or GSD changes.
  - Shows physical size and resulting pixel size.

### 4. VRT / Tiling

A dedicated group for **tiling-related settings**:

- **Create VRT / tiling checkbox**
  - Enables/disables tiling related controls.
- **Tile size presets**
  - Combo box with common tile sizes (e.g. 512, 1024, 2048, 4096).
- **Max columns / rows (px)**
  - Numeric fields that define the maximum tile width/height in pixels.
  - Currently used to control internal tile size in the exporter.
- **Tile grid info**
  - Label showing the resulting tile grid:
    - number of columns × rows
    - total number of tiles

Implementation note:
When “Create VRT” is enabled, the exporter operates in **VRT-only mode**:
- equally sized tiles are written
- a `.vrt` file referencing these tiles (via relative paths) is created
- no merged single raster is produced

### 5. Options

- **Load result as layer**
  - When enabled, the exported raster is added to the QGIS project after export.

---

## Usage

### Quick Start

1. Add one or more layers to QGIS.
2. Open the plugin:
   - Toolbar icon  
   - Or `Plugins → MapDownloader → Download GeoTIFF from Map`.
3. In the dialog:
   - Choose the **layer**.
   - Choose **output folder** and **file prefix**.
   - Optionally adjust the **output CRS**.
4. Define the **extent**:
   - Use canvas extent, layer extent, or manually adjust the extent box.
5. Set the **GSD** (map units per pixel).
6. Optionally configure **tiling** and **world file** options.
7. Click **OK**.

A progress dialog appears during rendering.  
After completion, the exported image can optionally be loaded directly into QGIS.

---

## Default Settings

(Default values may be adjusted per implementation.)

| Parameter             | Default (example)          |
|-----------------------|---------------------------|
| GSD                   | 1 map unit/pixel          |
| Load as layer         | Enabled                   |
| VRT / tiling          | Disabled by default       |
| Tile size preset      | 1024 × 1024 px (example)  |

---

## Output Formats

World files are always written.

### GeoTIFF

- Full GDAL georeferencing:
  - GeoTransform
  - Projection (CRS)
- LZW compression
- Internal tiling (`TILED=YES`)
- Compatible with common GIS tools
- Correct pixel → map coordinate transform
- GeoTIFF: internal georeferencing + additional world file

### PNG/JPEG

- PNG/JPEG: world file + .prj sidecar

### World file

- Plain text sidecar file
- Contains pixel size and upper-left pixel center coordinate
- World files are always written

---

## Internal Processing Pipeline

1. **Parameter validation**
   - Checks layer, extent, GSD, output path, etc.
2. **Extent resolution**
   - Extent in project CRS
   - Transformation into render CRS (project CRS if metric, otherwise `EPSG:3857`)
3. **Pixel size computation**
   - GSD × extent → width/height (px)
4. **Tiling decision**
   - If width/height exceed tile limits, internal tiling is used.
5. **Rendering**
   - `QgsMapRendererParallelJob` renders the selected layer for the requested extent at the derived resolution.
6. **GeoTIFF writing (GDAL)**
   - RGBA arrays are written tile by tile (full image or per tile).
   - GeoTransform and projection are stored.
7. **World file (optional)**
   - If enabled, `.tfw` is written next to the GeoTIFF.
8. **Post-processing**
   - Optional layer loading into QGIS.
   - Progress dialog is closed, messages shown.

---

## Requirements

- **QGIS 3.x**
- GDAL, PyQt, Qt, QGIS Python API (bundled with QGIS)

No extra third-party Python dependencies are required.

---

## Development Setup (Optional .venv)

For plugin runtime, QGIS uses its own Python environment.  
A local `.venv` is optional and only recommended for development tooling (linting/formatting and non-QGIS tests).

### 1. Local tooling environment (without QGIS)

Windows (PowerShell):

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
python -m unittest -v test.test_init test.test_validation test.test_exporter_validation test.test_progress_keys
```

Linux/macOS:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
python -m unittest -v test.test_init test.test_validation test.test_exporter_validation test.test_progress_keys
```

### 2. QGIS integration tests (with QGIS Python)

Run these in a QGIS/OSGeo shell (not in the local `.venv`):

```bash
python -m unittest discover -s test/integration -v
```

See also `test/integration/README.md` for Windows helpers and network test flags.

---

## Troubleshooting

### Export is empty / fully transparent

- The source service may restrict resolution or output size.
- Try:
  - Smaller extent
  - Larger GSD (i.e. lower resolution)
  - Enabling tiling with smaller tile sizes

### Export is rejected as too large

- Extremely large rasters are blocked to avoid crashes. Reduce extent or increase GSD. Use VRT/tiling for large areas.

### GSD outside allowed range

- GSD must be within the allowed range (current defaults: 0.1–1000 map units/pixel). Extremely small or large values are rejected; adjust GSD accordingly.

### Output path errors

- Ensure the output directory exists and is writable.
- Only GeoTIFF/PNG/JPEG are supported for single exports; VRT mode always writes `.vrt` plus GeoTIFF tiles.

### Export is shifted or misaligned

- Check that the **output CRS** is correct.
- Ensure the project CRS and layer CRS are correctly defined.
- The plugin assumes all coordinates/extent are in the selected output/project CRS.

### Very slow rendering

- Very small GSD and large extents yield massive rasters.
- Try increasing GSD or enabling tiling with smaller tile sizes.
- Some web services may throttle or slow down large requests.

---

## Changelog

### Version 0.3 (2025-XX-XX, current work)

- Simplified UI to a **pure extent-based workflow** (no explicit “Center Mode”).
- Extent exclusively controlled via `QgsExtentGroupBox`.
- Resolution controlled by **GSD only**; width/height are derived and displayed.
- Introduced **VRT/Tiling section**:
  - Tile size presets
  - Max columns/rows per tile (px)
  - Tile grid preview (columns, rows, total tiles)
- GeoTIFF is **always georeferenced**.
- “Write world file” now means:
  - additionally write a `.tfw` file next to the GeoTIFF.
- Improved error handling and progress reporting.

### Version 0.2

- Major UI redesign with `QgsExtentGroupBox`.
- Added CRS selector (`QgsProjectionSelectionWidget`).
- Reworked parameter model (center and extent).
- Added GSD/extent preview label.
- Improved exporter interface and stability. :contentReference[oaicite:3]{index=3}  

### Version 0.1 (Initial Release)

- Basic center-based export.
- GSD + pixel-size rendering.
- GeoTIFF export with progress dialog.

---

## License

GPL v2 or later  
See `LICENSE` for full terms.

---

## Author

Originally created by **Abhinav Jayswal**  
Extended, redesigned and maintained by project contributors.
