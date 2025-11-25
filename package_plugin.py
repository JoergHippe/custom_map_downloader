#!/usr/bin/env python3
"""
Package QGIS Plugin for Distribution

This script creates a properly formatted ZIP file for QGIS plugin repository submission.
It respects .gitignore rules and uses PEP 8 compliant directory naming.
"""

import os
import zipfile
import pathlib
import fnmatch

# Plugin directory name (PEP 8 compliant: lowercase with underscores)
PLUGIN_NAME = "custom_map_downloader"

# Read version from metadata.txt
def get_version_from_metadata():
    """Read version from metadata.txt file."""
    metadata_path = os.path.join(os.path.dirname(__file__), 'metadata.txt')
    try:
        with open(metadata_path, 'r', encoding='utf-8') as f:
            for line in f:
                if line.startswith('version='):
                    return line.split('=')[1].strip()
    except Exception as e:
        print(f"Warning: Could not read version from metadata.txt: {e}")
        return "0.1.0"
    return "0.1.0"

VERSION = get_version_from_metadata()

# Files and patterns to exclude (in addition to .gitignore)
EXCLUDE_PATTERNS = [
    '.git',
    '.gitignore',
    '__pycache__',
    '*.pyc',
    '*.pyo',
    '*.qm',
    '.vscode',
    '.idea',
    '*.swp',
    '*.swo',
    '*.zip',
    'build',
    'dist',
    '.DS_Store',
    'Thumbs.db',
    '*.tmp',
    '*.bak',
    '*~',
    '*.md',  # Exclude all .md files
    'package_plugin.py',  # Don't include this script
    'package_plugin.ps1',  # Don't include PowerShell script
    'plugin_upload.py',  # Don't include upload script
    'ICON_UPDATE_INSTRUCTIONS.txt',
]

# Files to explicitly include (exceptions to exclusions)
INCLUDE_EXCEPTIONS = [
    'README.md',  # Keep README.md
]


def should_exclude(file_path, base_path):
    """Check if a file should be excluded based on patterns."""
    rel_path = os.path.relpath(file_path, base_path)
    basename = os.path.basename(file_path)
    
    # Check if file is in exceptions list
    if basename in INCLUDE_EXCEPTIONS:
        return False
    
    # Check if any part of the path matches exclude patterns
    path_parts = rel_path.split(os.sep)
    
    for pattern in EXCLUDE_PATTERNS:
        # Check basename
        if fnmatch.fnmatch(basename, pattern):
            return True
        # Check full relative path
        if fnmatch.fnmatch(rel_path, pattern):
            return True
        # Check if any directory in path matches
        for part in path_parts:
            if fnmatch.fnmatch(part, pattern):
                return True
    
    return False


def create_plugin_package():
    """Create a ZIP package of the plugin."""
    
    # Get the plugin directory (current directory)
    plugin_dir = pathlib.Path(__file__).parent.resolve()
    parent_dir = plugin_dir.parent
    
    # Output ZIP file name
    zip_filename = f"{PLUGIN_NAME}-{VERSION}.zip"
    zip_path = parent_dir / zip_filename
    
    print(f"Creating plugin package: {zip_filename}")
    print(f"Plugin directory: {plugin_dir}")
    print(f"Output path: {zip_path}")
    print()
    
    # Remove old ZIP if exists
    if zip_path.exists():
        print(f"Removing existing ZIP: {zip_path}")
        zip_path.unlink()
    
    # Create ZIP file
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        file_count = 0
        excluded_count = 0
        
        # Walk through all files in plugin directory
        for root, dirs, files in os.walk(plugin_dir):
            # Filter out excluded directories IN-PLACE (modifies dirs list)
            # This prevents os.walk from descending into excluded directories
            dirs_to_remove = []
            for d in dirs:
                dir_path = os.path.join(root, d)
                if should_exclude(dir_path, plugin_dir):
                    dirs_to_remove.append(d)
                    excluded_count += 1
                    print(f"  Excluded directory: {os.path.relpath(dir_path, plugin_dir)}")
            
            for d in dirs_to_remove:
                dirs.remove(d)
            
            for file in files:
                file_path = os.path.join(root, file)
                
                # Check if file should be excluded
                if should_exclude(file_path, plugin_dir):
                    excluded_count += 1
                    print(f"  Excluded file: {os.path.relpath(file_path, plugin_dir)}")
                    continue
                
                # Calculate the archive path (inside the ZIP)
                rel_path = os.path.relpath(file_path, plugin_dir)
                archive_path = os.path.join(PLUGIN_NAME, rel_path)
                
                # Add file to ZIP
                zipf.write(file_path, archive_path)
                file_count += 1
                print(f"  Added: {rel_path}")
        
        print()
        print("Package created successfully!")
        print(f"  Files included: {file_count}")
        print(f"  Files excluded: {excluded_count}")
        print(f"  Output: {zip_path}")
        print()
        print("The ZIP file is ready for upload to QGIS Plugin Repository.")
        print(f"Top-level directory name: {PLUGIN_NAME} (PEP 8 compliant)")


if __name__ == "__main__":
    create_plugin_package()
