#!/bin/sh
cd "/Users/ritwickdas/Downloads/Pocket Master Firmware V1.3.0/re"
L=logs/work.log; PY=tools/.venv/bin/python
s() { echo "$(date +%H:%M:%S) $*" | tee -a $L; }
for t in t1 t4 t3; do
  s "bisect $t: parking on F01"; timeout 20 $PY tools/pmpreset.py select 50 >> $L 2>&1
  s "bisect $t: flashing"; $PY -u tools/pmflash.py flash "build/bisect-$t/PocketMaster_CFW1.0.2+bisect-$t.bin" --yes > logs/flash-bisect-$t.log 2>&1
  grep -q "DONE in" logs/flash-bisect-$t.log || { s "bisect $t: FLASH FAILED"; s "BISECT STOPPED"; exit 1; }
  n=0; until timeout 9 $PY -u tools/pmmode.py 2>/dev/null | tail -1 | grep -q "APP mode"; do n=$((n+1)); [ $n -gt 30 ] && { s "bisect $t: DID NOT BOOT"; s "BISECT STOPPED"; exit 1; }; sleep 10; done
  sleep 15; if $PY tools/audio_ok.py >> $L 2>&1; then s "bisect $t: BOOTS, AUDIO OK"; else s "bisect $t: BOOTS, NO AUDIO"; fi
done
s "back to the daily firmware"; timeout 20 $PY tools/pmpreset.py select 50 >> $L 2>&1
$PY -u tools/pmflash.py flash "build/daily/PocketMaster_CFW1.0.2+smartgate.bin" --yes > logs/flash-daily3.log 2>&1
n=0; until timeout 9 $PY -u tools/pmmode.py 2>/dev/null | tail -1 | grep -q "APP mode"; do n=$((n+1)); [ $n -gt 60 ] && { s "daily did not come back"; s "BISECT STOPPED"; exit 1; }; sleep 10; done
s "BISECT DONE (daily firmware back)"
