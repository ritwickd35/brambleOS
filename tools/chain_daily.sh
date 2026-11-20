#!/bin/sh
cd "/Users/ritwickdas/Downloads/Pocket Master Firmware V1.3.0/re"
L=logs/work.log; PY=tools/.venv/bin/python
s() { echo "$(date +%H:%M:%S) $*" | tee -a $L; }
until grep -q "AFTER7 DONE" $L; do sleep 10; done
s "restoring P08 (original test preset)"
$PY - <<'PY' >> $L 2>&1
import sys, time; sys.path.insert(0, "tools")
from pmflash import Link
from cut1_variants import read_p
from cut1_matrix import send
orig = open("cut1/p08-before-variants.bin", "rb").read()
send(orig); time.sleep(0.5); link = Link(); back = read_p(link); link.close()
print("P08 restored to the original:", back[4:] == orig[4:])
PY
s "parking on F01"; timeout 20 $PY tools/pmpreset.py select 50 >> $L 2>&1
s "flashing the daily firmware (CFW 1.0.2 + smart gate)"; $PY -u tools/pmflash.py flash "build/daily/PocketMaster_CFW1.0.2+smartgate.bin" --yes > logs/flash-daily.log 2>&1
grep -q "DONE in" logs/flash-daily.log || { s "flash failed"; exit 1; }
n=0; until timeout 9 $PY -u tools/pmmode.py 2>/dev/null | tail -1 | grep -q "APP mode"; do n=$((n+1)); [ $n -gt 60 ] && { s "pedal did not come back"; exit 1; }; sleep 10; done
s "DAILY FIRMWARE ON THE PEDAL"
