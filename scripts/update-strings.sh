#!/bin/bash
set -e

# Usage: scripts/update-strings.sh de af
LOCALES="$@"
if [ -z "${LOCALES}" ]; then
  echo "Usage: $0 <locale1> [locale2 ...]"
  exit 1
fi

BASE="CustomMapDownloader"

# Collect all Python/UI files
PYTHON_FILES=$(find . -type f \( -name "*.py" -o -name "*.ui" \))

# Determine newest timestamp of source files
CHANGED_FILES=0
for PYTHON_FILE in ${PYTHON_FILES}; do
  CHANGED=$(stat -c %Y "${PYTHON_FILE}")
  if [ ${CHANGED} -gt ${CHANGED_FILES} ]; then
    CHANGED_FILES=${CHANGED}
  fi
done

UPDATE=false
for LOCALE in ${LOCALES}; do
  TRANSLATION_FILE="i18n/${BASE}_${LOCALE}.ts"
  if [ ! -f "${TRANSLATION_FILE}" ]; then
    touch "${TRANSLATION_FILE}"
    UPDATE=true
    continue
  fi
  MODIFICATION_TIME=$(stat -c %Y "${TRANSLATION_FILE}")
  if [ ${CHANGED_FILES} -gt ${MODIFICATION_TIME} ]; then
    UPDATE=true
  fi
done

if [ "${UPDATE}" = true ]; then
  echo "Updating translation sources for locales: ${LOCALES}"
  for LOCALE in ${LOCALES}; do
    OUTFILE="i18n/${BASE}_${LOCALE}.ts"
    echo " -> ${OUTFILE}"
    pylupdate5 -noobsolete ${PYTHON_FILES} -ts "${OUTFILE}"
  done
  echo "Edit the TS files above, then run scripts/compile-strings.sh to build QM files."
else
  echo "Translations up-to-date; no .ts files regenerated."
fi
