#!/bin/bash
set -e

# Helper to update and compile translations for all configured locales.

LOCALES="de"

echo "Updating TS files..."
./scripts/update-strings.sh ${LOCALES}

echo "Compiling QM files..."
./scripts/compile-strings.sh ${LOCALES}

echo "Done."
