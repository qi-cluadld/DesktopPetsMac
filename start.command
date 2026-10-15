#!/bin/bash
# AI Desktop Pets - macOS launcher
cd "$(dirname "$0")"
REPORT="$HOME/Desktop/pets-report.txt"
PY=$(command -v python3)
{
  echo "=== AI Desktop Pets · macOS ==="
  echo "date: $(date)"
  echo "macOS: $(sw_vers -productVersion 2>/dev/null)"
  echo "arch : $(uname -m)"
  if [ -z "$PY" ]; then
    echo "ERROR: python3 not found."
    echo "Please install Python from python.org (see the README in this folder)."
    osascript -e 'display dialog "python3 not found. Please install Python from python.org first." buttons {"OK"} with icon caution'
  else
    echo "python: $($PY --version 2>&1)"
    echo "---- output ----"
    "$PY" pet.py 2>&1
    echo "---- exit code: $? ----"
  fi
} | tee "$REPORT"
