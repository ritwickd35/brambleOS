#!/bin/sh
# live view of the conversion log: every line gets the time it arrived; warnings hidden
cd "$(dirname "$0")/.."
tail -n 30 -f logs/nam2clo.log | while IFS= read -r l; do
  case "$l" in *Warning*|*warn*|*"if it %"*) continue;; esac
  printf '%s  %s\n' "$(date +%T)" "$l"
done
