# -*- coding: utf-8 -*-
"""JSON profile helpers for dialog presets."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping


PROFILE_VERSION = 1
PROFILE_FORMATS = {".tif", ".png", ".jpg", ".vrt"}
PROFILE_RESOLUTION_MODES = {"gsd", "scale"}


def _clean_text(value: Any) -> str:
    return str(value or "").strip()


def _clean_float(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number > 0.0 else None


def _clean_int(value: Any) -> int:
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0


def _clean_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def normalize_profile_data(data: Mapping[str, Any]) -> dict[str, Any]:
    """Return a normalized, forward-compatible profile payload."""
    output_extension = _clean_text(data.get("output_extension") or ".tif").lower()
    if output_extension not in PROFILE_FORMATS:
        output_extension = ".tif"

    resolution_mode = _clean_text(data.get("resolution_mode") or "gsd").lower()
    if resolution_mode not in PROFILE_RESOLUTION_MODES:
        resolution_mode = "gsd"

    extent_in = data.get("extent")
    extent_out: dict[str, float] | None = None
    if isinstance(extent_in, Mapping):
        try:
            west = float(extent_in["west"])
            south = float(extent_in["south"])
            east = float(extent_in["east"])
            north = float(extent_in["north"])
        except (KeyError, TypeError, ValueError):
            extent_out = None
        else:
            if west < east and south < north:
                extent_out = {
                    "west": west,
                    "south": south,
                    "east": east,
                    "north": north,
                }

    return {
        "output_directory": _clean_text(data.get("output_directory")),
        "output_prefix": _clean_text(data.get("output_prefix")),
        "output_extension": output_extension,
        "layer_id": _clean_text(data.get("layer_id")),
        "layer_name": _clean_text(data.get("layer_name")),
        "output_crs_authid": _clean_text(data.get("output_crs_authid")),
        "resolution_mode": resolution_mode,
        "gsd": _clean_float(data.get("gsd")),
        "target_scale_denominator": _clean_float(data.get("target_scale_denominator")),
        "load_as_layer": _clean_bool(data.get("load_as_layer")),
        "create_vrt": _clean_bool(data.get("create_vrt")),
        "vrt_max_cols": _clean_int(data.get("vrt_max_cols")),
        "vrt_max_rows": _clean_int(data.get("vrt_max_rows")),
        "vrt_preset_size": _clean_int(data.get("vrt_preset_size")),
        "extent": extent_out,
    }


def write_profile(path: str | Path, data: Mapping[str, Any]) -> None:
    """Write normalized profile data to JSON."""
    payload = {
        "plugin": "CustomMapDownloader",
        "profile_version": PROFILE_VERSION,
        "profile": normalize_profile_data(data),
    }
    Path(path).write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def read_profile(path: str | Path) -> dict[str, Any]:
    """Read profile data from JSON, supporting wrapped and bare formats."""
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, Mapping):
        raise ValueError("Profile JSON must contain an object.")
    profile_data = raw.get("profile", raw)
    if not isinstance(profile_data, Mapping):
        raise ValueError("Profile data must contain an object.")
    return normalize_profile_data(profile_data)
