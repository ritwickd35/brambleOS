#!/bin/sh
cd "/Users/ritwickdas/Downloads/Pocket Master Firmware V1.3.0/re"
L=logs/work.log; PY=tools/.venv/bin/python
s() { echo "$(date +%H:%M:%S) $*" | tee -a $L; }
s "cut9 reboot chain: parking on F01"; timeout 20 $PY tools/pmpreset.py select 50 >> $L 2>&1
s "flashing cut9 (gate + multi drive)"; $PY -u tools/pmflash.py flash "build/cut9/PocketMaster_CFW1.0.2+pm-cut9.bin" --yes > logs/flash-cut9.log 2>&1
grep -q "DONE in" logs/flash-cut9.log || { s "flash failed"; s "CUT9R CHAIN DONE"; exit 1; }
n=0; until timeout 9 $PY -u tools/pmmode.py 2>/dev/null | tail -1 | grep -q "APP mode"; do n=$((n+1)); [ $n -gt 60 ] && { s "pedal did not come back"; s "CUT9R CHAIN DONE"; exit 1; }; sleep 10; done
s "pedal back on cut9"; sleep 20
s "isolation test"; $PY -u tools/drv_isolate.py > logs/drv-iso.log 2>&1; grep -E "level|restored|Error" logs/drv-iso.log >> $L
timeout 20 $PY tools/pmpreset.py select 50 >> $L 2>&1
s "CUT9R CHAIN DONE"
