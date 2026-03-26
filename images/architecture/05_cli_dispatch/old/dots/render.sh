#!/usr/bin/env bash
# Render all DOT files in this directory to PDF in the parent directory.
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
OUTDIR="$(dirname "$DIR")"

for f in "$DIR"/*.dot; do
    base="$(basename "$f" .dot)"
    out="$OUTDIR/${base}.pdf"
    if dot -Tpdf "$f" -o "$out" 2>&1; then
        echo "  OK: ${base}.pdf"
    else
        echo "  FAILED: $f" >&2
    fi
done
