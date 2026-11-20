#!/bin/sh
cd "/Users/ritwickdas/Downloads/Pocket Master Firmware V1.3.0/re"
L=logs/work.log; PY=tools/.venv/bin/python
s() { echo "$(date +%H:%M:%S) $*" | tee -a $L; }
s "cut7 chain: waiting for cut6 (second run)"
until [ "$(grep -c 'CUT6 CHAIN DONE' $L)" -ge 2 ]; do sleep 15; done
s "parking on F01"; timeout 20 $PY tools/pmpreset.py select 50 >> $L 2>&1
s "flashing cut7 (engine capacity ramp)"; $PY -u tools/pmflash.py flash "build/cut7/PocketMaster_CFW1.0.2+pm-cut7.bin" --yes > logs/flash-cut7.log 2>&1
grep -q "DONE in" logs/flash-cut7.log || { s "flash failed"; exit 1; }
n=0; until timeout 9 $PY -u tools/pmmode.py 2>/dev/null | tail -1 | grep -q "APP mode"; do n=$((n+1)); [ $n -gt 60 ] && { s "pedal did not come back"; exit 1; }; sleep 10; done
s "pedal back on cut7"; sleep 20
s "engine capacity ramps"; $PY -u tools/engine_ramp.py 2>&1 | tee -a logs/engine-ramp.log | grep --line-buffered -E "engine ramp|restored" >> $L
timeout 20 $PY tools/pmpreset.py select 50 >> $L 2>&1
s "CUT7 CHAIN DONE"
