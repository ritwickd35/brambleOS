#!/bin/sh
cd "/Users/ritwickdas/Downloads/Pocket Master Firmware V1.3.0/re"
L=logs/work.log; PY=tools/.venv/bin/python
s() { echo "$(date +%H:%M:%S) $*" | tee -a $L; }
s "cut8b chain: parking on F01"; timeout 20 $PY tools/pmpreset.py select 50 >> $L 2>&1
s "flashing cut8b (engine probe round 2)"; $PY -u tools/pmflash.py flash "build/cut8b/PocketMaster_CFW1.0.2+pm-cut8b.bin" --yes > logs/flash-cut8b.log 2>&1
grep -q "DONE in" logs/flash-cut8b.log || { s "flash failed"; s "CUT8B CHAIN DONE"; exit 1; }
n=0; until timeout 9 $PY -u tools/pmmode.py 2>/dev/null | tail -1 | grep -q "APP mode"; do n=$((n+1)); [ $n -gt 60 ] && { s "pedal did not come back"; s "CUT8B CHAIN DONE"; exit 1; }; sleep 10; done
s "pedal back on cut8b"; sleep 20
s "engine probe"; EPROBE_SECONDS=70 $PY -u tools/eprobe_run.py > logs/eprobe-run3.log 2>&1; grep -E "eprobe|restored|Error" logs/eprobe-run3.log >> $L
timeout 20 $PY tools/pmpreset.py select 50 >> $L 2>&1
s "CUT8B CHAIN DONE"
