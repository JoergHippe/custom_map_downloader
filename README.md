# Custom Map Downloader (QGIS Plugin)

## Overview

Custom Map Downloader is a QGIS plugin to export map content from layers and map services
(WMS, WMTS, XYZ, raster and vector layers) with precise control over extent, ground resolution,
target scale, output CRS and tiling.

---

## Description

Custom Map Downloader allows users to export **georeferenced GeoTIFF** images from any loaded layer in QGIS.

The plugin works purely **extent-based**:

- The geographic rectangle is selected interactively via the QGIS-native `QgsExtentGroupBox` (layer extent, canvas extent, CRS transformation handled by QGIS).
- The plugin derives the center internally from the selected extent (no separate “Center Mode” in the UI anymore).
- Output resolution can be controlled either by **ground resolution** (`m/px`) or by an explicit **target scale (1:n)**; pixel width/height are derived from extent and the active resolution mode.

The selected layer is rendered at the requested output resolution and stored as a fully georeferenced **GeoTIFF**.
Optionally, an additional **world file (.tfw)** can be written next to the GeoTIFF.

Typical use cases include:

- Extracting satellite imagery or base maps
- Exporting XYZ/WMTS/WMS layers for offline usage
- Preparing analysis rasters for specific regions
- Generating image datasets for ML/AI workflows

---

## Features

- ✔ **Export any visible QGIS layer** (XYZ/WMTS/WMS, raster, vector, etc.)
- ✔ **QGIS-native extent control** using `QgsExtentGroupBox`
- ✔ **Extent-based workflow only**:
  - Extent defined via layer extent, canvas extent, or manual extent box
  - Center is derived internally from the chosen extent
- ✔ **Selectable resolution mode**:
  - **Ground resolution** (`m/px`)
  - **Target scale (1:n)** for scale-dependent WMS portrayal
  - Pixel **width/height are derived** from extent and the active resolution mode
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

The dialog consists of several main sections. The exact layout may evolve, but the semantics remain stable.

### 1. Source and Output

- **Layer selection**
  - Pick the QGIS layer that should be rendered (XYZ/WMTS/WMS, raster, vector, etc.).
- **Profiles**
  - `Load profile...` restores a previously saved JSON preset for recurring exports.
  - `Save profile...` stores the current dialog state as a reusable JSON preset.
- **CRS selection**
  - `QgsProjectionSelectionWidget` for choosing the exported raster CRS.
  - In target scale mode, use a projected CRS with meter units.
  - If a non-metric CRS is chosen in ground-resolution mode, the exporter may still render internally in a metric CRS for stable WMS portrayal and then reproject the final raster into the requested output CRS.
  - Current limitation: VRT export requires identical render CRS and output CRS.
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

- **Resolution mode**
  - Choose between **ground resolution (m/px)** and **target scale (1:n)**.
  - Target scale is internally converted using the OGC standard pixel size (`0.28 mm`).
- **Ground resolution (m/px)**
  - Single `QDoubleSpinBox` for pixel size in meters per pixel.
  - Extent + ground resolution → derived pixel width/height.
- **Target scale (1:n)**
  - Useful for WMS services that switch portrayal by scale.
  - Requires a projected output CRS with meter units.
  - Extent + target scale → derived ground resolution → derived pixel width/height.
- **Extent information label**
  - Updated whenever extent, ground resolution, or target scale changes.
  - Shows physical size, active ground resolution, optional target scale, and resulting pixel size.

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
5. Choose either **ground resolution (m/px)** or **Target scale (1:n)**.
6. Optionally configure **tiling** and **world file** options.
7. Optionally save the setup as a **profile** for repeated exports.
8. Click **OK**.

A progress dialog appears during rendering.
After completion, the exported image can optionally be loaded directly into QGIS.

---

## Default Settings

(Default values may be adjusted per implementation.)

| Parameter             | Default (example)          |
|-----------------------|---------------------------|
| Resolution mode       | Ground resolution         |
| Ground resolution     | 1 m/pixel                 |
| Target scale          | ~1:3571 (equivalent to 1 m/px) |
| Load as layer         | Enabled                   |
| VRT / tiling          | Disabled by default       |
| Tile size preset      | 1024 × 1024 px (example)  |

---

## Export Profiles

- Profiles are stored as JSON (`*.cmdprofile.json`).
- They capture the dialog state relevant for repeated exports:
  - output directory and filename prefix
  - selected layer id/name
  - output CRS
  - extent
  - resolution mode, ground resolution and target scale
  - VRT/tiling settings
  - `Load as layer`
- Profiles are intended as local working presets. They do not embed layer data or credentials.
- When a stored layer id is no longer present in the current QGIS project, the profile still loads and the layer must be selected manually.

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
   - Checks layer, extent, resolution/scale mode, output path, etc.
2. **Extent resolution**
   - Extent in project CRS
   - Transformation into render CRS (project CRS if metric, otherwise `EPSG:3857`)
3. **Pixel size computation**
   - Ground resolution or target scale × extent → width/height (px)
4. **Tiling decision**
   - If width/height exceed tile limits, internal tiling is used.
5. **Rendering**
   - `QgsMapRendererParallelJob` renders the selected layer for the requested extent at the derived resolution.
   - In target-scale mode, the renderer uses the OGC standard pixel size / DPI to stabilize scale-dependent WMS portrayal.
6. **Raster writing / reprojection (GDAL)**
   - RGBA arrays are written in render CRS.
   - If output CRS differs, the rendered raster is reprojected into the requested output CRS before the final file is written.
   - GeoTransform and projection are stored in the final output CRS.
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

## Development Stack

For actual plugin development and runtime behavior, **QGIS Python is the primary environment**.
Do not treat a plain isolated `.venv` as the plugin runtime.

### QGIS runtime / integration environment

Use one of these as the authoritative environment for plugin execution and QGIS-backed tests:

- Windows: OSGeo4W Shell / QGIS Python Shell
- Linux: system QGIS Python environment
- IDE setup: a QGIS-aware virtual environment that inherits global/site packages from the installed QGIS Python stack

Run QGIS-backed tests there:

```bash
make test-qgis
```

### Tooling-only environment

A local `.venv` is still useful, but only for repository tooling that does not define plugin runtime semantics:

- `ruff`
- `black`
- `pre-commit`
- `qgis-plugin-ci`
- fast non-QGIS tests

Setup:

```bash
python3 -m venv .venv
. .venv/bin/activate
python3 -m pip install -r requirements-dev.txt
```

Core tooling commands:

```bash
make format
make lint
make test
make dev-check
make package
```

Local plugin deployment into the real QGIS profile:

```bash
make deploy-dev
```

This links `custom_map_downloader/` into the local QGIS profile as
`.../python/plugins/custom_map_downloader`.
Use copy mode if links/junctions are undesired:

```bash
python scripts/install_dev_plugin.py --mode copy
```

Choose another QGIS profile explicitly if needed:

```bash
python scripts/install_dev_plugin.py --profile myprofile
```

Remove the deployed development plugin again:

```bash
make undeploy-dev
```

On Windows, you can start QGIS directly against a chosen dev profile and deploy
the current plugin source in one step:

```bat
start_qgis_dev.bat
start_qgis_dev.bat myprofile
start_qgis_dev.bat myprofile copy
```

This deploys `custom_map_downloader/` into the selected profile and launches
QGIS with `--profile`.

VS Code can be started with the same QGIS profile semantics:

```bat
start_vscode_qgis.bat
start_vscode_qgis.bat myprofile
start_vscode_qgis.bat myprofile copy
```

This prepares the QGIS environment, deploys the plugin to the selected profile
and opens the repository in VS Code.

Optional extra check in a QGIS-enabled environment:

```bash
make lint-pylint
```

Install local hooks once:

```bash
python3 -m pre_commit install
```

## CI

- GitHub Actions runs two layers of tests:
  - a fast lint + stubbed Python suite on plain `ubuntu-latest`
  - a QGIS-backed suite inside the official `qgis/qgis` Docker image
- The QGIS-backed job runs the repository test suite with `QT_QPA_PLATFORM=offscreen`, which gives real QGIS coverage without requiring a desktop session.

### 1. Tooling-only environment (without QGIS runtime)

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
On Windows, you can choose a QGIS profile explicitly:

```bat
run_integration_tests.bat all myprofile
run_integration_tests.bat smoke myprofile
run_integration_tests.bat network myprofile
```

Das gewählte Profil beeinflusst dabei den QGIS-Kontext. Der getestete Plugin-Code
wird weiterhin direkt aus dem Repository importiert, nicht aus einem deployten
Profil-Plugin-Verzeichnis.

### 3. Practical local dev loop

Recommended workflow in a real QGIS environment:

1. Deploy the plugin into the target profile:
   - `make deploy-dev`
   - or on Windows: `start_qgis_dev.bat`
2. Start QGIS with that profile.
3. Make code/UI changes in the repo.
4. In QGIS:
   - either restart QGIS,
   - or use a plugin reloader if you explicitly choose to work that way.
5. Run a quick smoke check:
   - open the plugin dialog
   - verify layer list loads
   - verify extent control works
   - export a very small raster
   - if relevant, repeat once with `Target scale (1:n)`

For non-GUI validation before reopening QGIS:

```bash
make test
make dev-check
make package-check
```

---

## Packaging

Primary release path:

```bash
make package
```

Validation of the built archive:

```bash
make package-check
```

This uses `qgis-plugin-ci` and repository metadata from `pyproject.toml` plus `custom_map_downloader/metadata.txt`.
Release archives are built directly from the `custom_map_downloader/` plugin source directory.

---

## Troubleshooting

See `TROUBLESHOOTING.md` for the operational troubleshooting guide.

- transparent / empty exports
- VRT portability warnings
- render CRS vs output CRS behavior
- repeated tile retries
- reload failures after export

## Release

See `RELEASING.md` for the release checklist.

Quick path:

```bash
make release-check
```

This runs linting, tests, package build and package validation.

### Export is empty / fully transparent

- The source service may restrict resolution or output size.
- Try:
  - Smaller extent
  - Larger GSD (i.e. lower resolution)
  - Enabling tiling with smaller tile sizes

### Export is rejected as too large

- Extremely large rasters are blocked to avoid crashes. Reduce extent or increase GSD. Use VRT/tiling for large areas.

### Ground resolution outside allowed range

- Ground resolution must be within the allowed range (current defaults: 0.1–1000 m/pixel). Extremely small or large values are rejected; adjust the value accordingly.

### WMS portrayal changes with scale

- Some WMS services render different content depending on scale.
- Use **Target scale (1:n)** if you need a specific scale-dependent portrayal.
- Target scale mode requires a projected output CRS with meter units.

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
