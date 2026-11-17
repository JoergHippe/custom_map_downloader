"""GDAL-based raster fingerprinting for official service regression analysis.

File bytes, decoded raster samples, and georeferencing are deliberately
independent signals. A changed GeoTIFF hash alone cannot establish image drift.
"""

from __future__ import annotations

import argparse
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


def compare_fingerprints(reference: dict, current: dict) -> dict[str, object]:
    """Classify a comparison when BOTH actual raster fingerprints exist."""
    file_equal = reference["file_sha256"] == current["file_sha256"]
    pixel_equal = reference["pixel_sha256"] == current["pixel_sha256"]
    georef_equal = reference["georef_sha256"] == current["georef_sha256"]
    if file_equal:
        classification = "identical"
    elif pixel_equal and georef_equal:
        classification = "file_encoding_or_metadata_only"
    elif not pixel_equal:
        classification = "raster_samples_changed"
    else:
        classification = "georeference_changed"
    return {
        "file_equal": file_equal,
        "pixel_equal": pixel_equal,
        "georef_equal": georef_equal,
        "classification": classification,
    }


def main() -> None:
    """Inspect a GeoTIFF or compare a current export with an archived one."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("raster", type=Path, help="Current GeoTIFF")
    parser.add_argument("--reference", type=Path, help="Original archived GeoTIFF, if available")
    args = parser.parse_args()
    current = inspect_raster(args.raster)
    result: dict[str, object] = {"current": current}
    if args.reference is not None:
        previous = inspect_raster(args.reference)
        result["reference"] = previous
        result["comparison"] = compare_fingerprints(previous, current)
    print(json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False))


if __name__ == "__main__":
    main()
