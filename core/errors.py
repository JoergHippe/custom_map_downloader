# CustomMapDownloader/core/errors.py
# -*- coding: utf-8 -*-

"""Error types for export operations (UI-agnostic)."""


class ExportError(Exception):
    """Base exception for export failures.

    Args:
        code: Stable error code for UI mapping / translation.
        details: Optional technical details for logs or advanced display.
    """

    def __init__(self, code: str, details: str = "") -> None:
        super().__init__(code)
        self.code = code
        self.details = details


class ValidationError(ExportError):
    """Raised when input parameters are invalid."""
    pass


class CancelledError(ExportError):
    """Raised when the user cancels the export."""
    pass
