"""GDAL-based raster fingerprinting for official service regression analysis.

File bytes, decoded raster samples, and georeferencing are deliberately
independent signals. A changed GeoTIFF hash alone cannot establish image drift.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


def _digest_json(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def inspect_raster(path: str | Path) -> dict[str, object]:
    """Return bounded-memory diagnostics for one successfully written raster.

    Pixel fingerprints cover each band in raster row order. Raster band types,
    dimensions, and band order are included in the digest. Reads are chunked
    to keep memory bounded even for larger exports.
    """
    from osgeo import gdal

    raster_path = Path(path)
    dataset = gdal.Open(str(raster_path), gdal.GA_ReadOnly)
    if dataset is None:
        raise ValueError(f"GDAL cannot open raster for diagnostics: {raster_path}")

    try:
        width = dataset.RasterXSize
        height = dataset.RasterYSize
        band_count = dataset.RasterCount
        if min(width, height, band_count) <= 0:
            raise ValueError("Raster dimensions and band count must be positive")

        digest = hashlib.sha256()
        digest.update(f"{width}x{height}:{band_count}\n".encode("ascii"))
        band_details: list[dict[str, object]] = []
        for index in range(1, band_count + 1):
            band = dataset.GetRasterBand(index)
            data_type = gdal.GetDataTypeName(band.DataType)
            digest.update(f"band:{index}:type:{data_type}\n".encode("ascii"))
            for y in range(0, height, 64):
                row_count = min(64, height - y)
                # Explicit GDAL data type; no automatic color conversion,
                # resampling, or dependence on TIFF compression.
                raw = band.ReadRaster(0, y, width, row_count, buf_type=band.DataType)
                if raw is None:
                    raise RuntimeError(f"Unable to read band {index}, row {y}")
                digest.update(raw)
            band_details.append(
                {
                    "index": index,
                    "data_type": data_type,
                    "color_interpretation": gdal.GetColorInterpretationName(
                        band.GetColorInterpretation()
                    ),
                    "nodata": band.GetNoDataValue(),
                    "metadata": band.GetMetadata(),
                }
            )

        georeference = {
            "width": width,
            "height": height,
            "projection_wkt": dataset.GetProjectionRef(),
            "geotransform": list(dataset.GetGeoTransform()),
            "ground_control_points": dataset.GetGCPCount(),
        }
        encoding = {
            "driver": dataset.GetDriver().ShortName,
            "gdal_version": gdal.VersionInfo("RELEASE_NAME"),
            "metadata": dataset.GetMetadata(),
            "image_structure": dataset.GetMetadata("IMAGE_STRUCTURE"),
            "bands": band_details,
        }
        file_digest = hashlib.sha256()
        with raster_path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                file_digest.update(chunk)
        return {
            "file_sha256": file_digest.hexdigest(),
            "pixel_sha256": digest.hexdigest(),
            "georef_sha256": _digest_json(georeference),
            "georeference": georeference,
            "encoding": encoding,
        }
    finally:
        # Explicit close is required for reliable cleanup on Windows.
        dataset = None
