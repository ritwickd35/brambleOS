#!/bin/sh
cd "/Users/ritwickdas/Downloads/Pocket Master Firmware V1.3.0/re"
L=logs/work.log; PY=tools/.venv/bin/python
s() { echo "$(date +%H:%M:%S) $*" | tee -a $L; }
s "cut8c chain: parking on F01"; timeout 20 $PY tools/pmpreset.py select 50 >> $L 2>&1
s "flashing cut8c (engine cost bench)"; $PY -u tools/pmflash.py flash "build/cut8c/PocketMaster_CFW1.0.2+pm-cut8c.bin" --yes > logs/flash-cut8c.log 2>&1
grep -q "DONE in" logs/flash-cut8c.log || { s "flash failed"; s "CUT8C CHAIN DONE"; exit 1; }
n=0; until timeout 9 $PY -u tools/pmmode.py 2>/dev/null | tail -1 | grep -q "APP mode"; do n=$((n+1)); [ $n -gt 60 ] && { s "pedal did not come back"; s "CUT8C CHAIN DONE"; exit 1; }; sleep 10; done
s "pedal back on cut8c"; sleep 20
s "engine bench"; $PY -u tools/ebench_run.py > logs/ebench-run.log 2>&1; grep -E "ebench|restored|Error" logs/ebench-run.log >> $L
timeout 20 $PY tools/pmpreset.py select 50 >> $L 2>&1
s "CUT8C CHAIN DONE"
