"""Locale helpers for plugin startup."""

from __future__ import annotations


def resolve_locale_code(value: object, default: str = "en") -> str:
    """Return a stable two-letter locale code from a QSettings value."""
    if value is None:
        return default

    text = str(value).strip()
    if not text:
        return default

    # Common QGIS values look like "de_DE" or "de-DE".
    normalized = text.replace("-", "_")
    code = normalized.split("_", 1)[0].lower()
    if len(code) < 2:
        return default
    return code[:2]
