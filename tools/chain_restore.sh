#!/bin/sh
cd "/Users/ritwickdas/Downloads/Pocket Master Firmware V1.3.0/re"
L=logs/work.log; PY=tools/.venv/bin/python
s() { echo "$(date +%H:%M:%S) $*" | tee -a $L; }
s "restore: parking on F01"; timeout 20 $PY tools/pmpreset.py select 50 >> $L 2>&1
s "flashing the daily firmware"; $PY -u tools/pmflash.py flash "build/daily/PocketMaster_CFW1.0.2+smartgate.bin" --yes > logs/flash-daily2.log 2>&1
grep -q "DONE in" logs/flash-daily2.log || { s "flash failed"; s "RESTORE DONE"; exit 1; }
n=0; until timeout 9 $PY -u tools/pmmode.py 2>/dev/null | tail -1 | grep -q "APP mode"; do n=$((n+1)); [ $n -gt 60 ] && { s "pedal did not come back"; s "RESTORE DONE"; exit 1; }; sleep 10; done
s "DAILY FIRMWARE BACK"; s "RESTORE DONE"
