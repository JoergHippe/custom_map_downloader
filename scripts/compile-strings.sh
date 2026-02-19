#!/bin/bash
set -e

# Usage: scripts/compile-strings.sh de af
LOCALES="$@"
if [ -z "${LOCALES}" ]; then
  echo "Usage: $0 <locale1> [locale2 ...]"
  exit 1
fi

BASE="CustomMapDownloader"
LRELEASE=${LRELEASE:-lrelease}

for LOCALE in ${LOCALES}; do
    TS_FILE="i18n/${BASE}_${LOCALE}.ts"
    QM_FILE="i18n/${BASE}_${LOCALE}.qm"
    echo "Compiling ${TS_FILE} -> ${QM_FILE}"
    "${LRELEASE}" "${TS_FILE}" -qm "${QM_FILE}"
done
