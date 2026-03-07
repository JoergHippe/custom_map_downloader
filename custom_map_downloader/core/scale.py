# CustomMapDownloader/core/scale.py
# -*- coding: utf-8 -*-

"""Helpers for converting between map scale and GSD."""

from __future__ import annotations

OGC_PIXEL_SIZE_M = 0.00028
OGC_STANDARD_DPI = 25.4 / 0.28


def scale_to_gsd_m_per_px(scale_denominator: float) -> float:
    """Convert OGC scale denominator (1:n) to meters per pixel."""
    return float(scale_denominator) * OGC_PIXEL_SIZE_M


def gsd_to_scale_denominator(gsd_m_per_px: float) -> float:
    """Convert meters per pixel to OGC scale denominator (1:n)."""
    return float(gsd_m_per_px) / OGC_PIXEL_SIZE_M
