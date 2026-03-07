# -*- coding: utf-8 -*-

"""Structured logging helpers for export operations."""

from __future__ import annotations

import logging
from typing import Any

from qgis.core import QgsCoordinateReferenceSystem

from .models import ExportParams

LOGGER = logging.getLogger("custom_map_downloader.export")


def _crs_label(crs: QgsCoordinateReferenceSystem | None) -> str:
    """Return a stable, short label for a CRS."""
    if crs is None:
        return "none"
    try:
        if crs.isValid():
            return crs.authid() or "valid-crs"
    except Exception:
        pass
    return "invalid-crs"


def summarize_params(params: ExportParams, *, render_crs: Any, output_crs: Any) -> dict[str, Any]:
    """Build a compact structured summary of export parameters."""
    return {
        "output_path": params.output_path,
        "width_px": int(params.width_px),
        "height_px": int(params.height_px),
        "create_vrt": bool(params.create_vrt),
        "target_scale": params.target_scale_denominator,
        "output_dpi": params.output_dpi,
        "render_crs": _crs_label(render_crs),
        "output_crs": _crs_label(output_crs),
        "has_extent": params.extent is not None,
    }


def log_event(event: str, **fields: Any) -> None:
    """Emit a structured log line for exporter diagnostics."""
    payload = " ".join(f"{key}={fields[key]!r}" for key in sorted(fields))
    LOGGER.info("%s %s", event, payload)
