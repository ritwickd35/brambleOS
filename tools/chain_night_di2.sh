#!/bin/sh
# remaining takes after the audio device was lost during UI flashing (2026-11-22)
cd "$(dirname "$0")/.."
for k in 3 5 7; do
  echo "$(date +%T) === DI take $k" >> logs/night_di_all.log
  NIGHT_DI=$k NIGHT_OUT=night_di$k nice tools/.venv/bin/python -u tools/night_test.py run 1 >> logs/night_di_all.log 2>&1
done
echo "$(date +%T) NIGHT DI DONE" >> logs/night_di_all.log
