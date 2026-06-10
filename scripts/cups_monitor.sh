#!/usr/bin/env bash
set -euo pipefail

# Simple CUPS monitor for Fireman
# - logs disabled printers and recent pdftops filter errors
# - exits non-zero when an issue is found (useful for systemd timers)

LOG_DIR=/var/log/fireman
LOG_FILE="$LOG_DIR/cups_monitor.log"
mkdir -p "$LOG_DIR"

timestamp=$(date --iso-8601=seconds)

disabled=$(lpstat -p 2>/dev/null | grep -i 'disabled' || true)
pdftops_errors=$(journalctl -u cups --since '1 hour ago' --no-pager 2>/dev/null | grep -i 'pdftops filter function failed' || true)

if [[ -n "$disabled" || -n "$pdftops_errors" ]]; then
  {
    echo "$timestamp - ISSUE DETECTED"
    lpstat -p 2>/dev/null || true
    echo "--- recent cups log ---"
    journalctl -u cups --since '1 hour ago' --no-pager || true
    echo
  } >> "$LOG_FILE"
  exit 1
else
  echo "$timestamp - OK" >> "$LOG_FILE"
  exit 0
fi
