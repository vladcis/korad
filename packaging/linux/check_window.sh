#!/bin/sh
# CI: did the native window open and load the UI? On failure the app output goes into a
# GitHub annotation (annotations are public, job logs are not).
#   sh packaging/linux/check_window.sh /tmp/g.log "deb"
LOG="$1"; WHAT="${2:-native window}"
cat "$LOG"
if grep -q '"GET / HTTP' "$LOG" && ! grep -q "opening the browser" "$LOG"; then
  echo "$WHAT: native window OK"
  exit 0
fi
MSG=$(grep -vE '"GET /(static|api)' "$LOG" | tail -30 | sed 's/%/%25/g' | awk '{printf "%s%%0A", $0}')
echo "::error title=$WHAT: native window failed::$MSG"
exit 1
