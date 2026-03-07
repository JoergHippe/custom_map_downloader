# -*- coding: utf-8 -*-

"""Release-governance helpers for changelog and metadata checks."""

from __future__ import annotations

import re
from pathlib import Path


def read_metadata_version(metadata_path: Path) -> str:
    """Return the plugin version declared in metadata.txt."""
    for line in metadata_path.read_text(encoding="utf-8").splitlines():
        if line.startswith("version="):
            return line.split("=", 1)[1].strip()
    raise ValueError(f"Missing version in {metadata_path}")


def read_metadata_changelog(metadata_path: Path) -> str:
    """Return the metadata changelog field if present."""
    for line in metadata_path.read_text(encoding="utf-8").splitlines():
        if line.startswith("changelog="):
            return line.split("=", 1)[1].strip()
    return ""


def changelog_has_version(changelog_path: Path, version: str) -> bool:
    """Return whether CHANGELOG.md contains a heading for the given version."""
    pattern = re.compile(rf"^##\s+\[{re.escape(version)}\](?:\s|$)", re.MULTILINE)
    return bool(pattern.search(changelog_path.read_text(encoding="utf-8")))


def validate_release_governance(
    metadata_path: Path,
    changelog_path: Path,
) -> list[str]:
    """Validate release-governance expectations and return human-readable errors."""
    errors: list[str] = []

    if not changelog_path.exists():
        return [f"Missing changelog file: {changelog_path}"]

    version = read_metadata_version(metadata_path)
    metadata_changelog = read_metadata_changelog(metadata_path)

    if not changelog_has_version(changelog_path, version):
        errors.append(f"CHANGELOG.md does not contain an entry for version {version}")

    if not metadata_changelog:
        errors.append("metadata.txt is missing a changelog= entry")

    return errors
