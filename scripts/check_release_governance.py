#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def main() -> int:
    from custom_map_downloader.core.release_governance import validate_release_governance

    metadata_path = REPO_ROOT / "custom_map_downloader" / "metadata.txt"
    changelog_path = REPO_ROOT / "CHANGELOG.md"
    errors = validate_release_governance(metadata_path, changelog_path)

    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1

    print("Release governance OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
