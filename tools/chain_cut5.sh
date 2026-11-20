#!/bin/sh
# after the CFW CPU tests: (boot protection must be off) park on F01, flash cut5, wait for the pedal, run tests
cd "/Users/ritwickdas/Downloads/Pocket Master Firmware V1.3.0/re"
L=logs/work.log; PY=tools/.venv/bin/python
s() { echo "$(date +%H:%M:%S) $*" | tee -a $L; }
s "cut5 chain: waiting for the CFW CPU tests"
until grep -q "CUT4B CHAIN DONE" logs/chain-cut4b.log; do sleep 15; done
if ! grep -q "0205 boot anti-touch protection: .* -> OK" logs/chain-cut4b.log; then s "boot protection not confirmed off - not flashing"; exit 1; fi
s "parking on F01"; timeout 20 $PY tools/pmpreset.py select 50 >> $L 2>&1
s "flashing cut5 (smart gate + DS-1+)"; $PY -u tools/pmflash.py flash "build/cut5/PocketMaster_CFW1.0.2+pm-cut5.bin" --yes > logs/flash-cut5.log 2>&1
grep -q "DONE in" logs/flash-cut5.log || { s "flash failed"; exit 1; }
n=0; until timeout 9 $PY -u tools/pmmode.py 2>/dev/null | tail -1 | grep -q "APP mode"; do n=$((n+1)); [ $n -gt 60 ] && { s "pedal did not come back in 10 min"; exit 1; }; sleep 10; done
s "pedal back on cut5 without a tap ($((n*10)) s)"; sleep 20
timeout 30 $PY tools/pmsettings.py show 2>&1 | grep -E "anti-touch" | tee -a $L
s "cut5 sound tests"; $PY -u tools/test_cut5.py sound 2>&1 | tee -a logs/cut5.log | grep --line-buffered -E "sound|restored" >> $L
s "cut5 CPU tests"; $PY -u tools/test_cut5.py cpu 2>&1 | tee -a logs/cut5.log | grep --line-buffered -E "free|restored" >> $L
timeout 20 $PY tools/pmpreset.py select 50 >> $L 2>&1
s "CUT5 CHAIN DONE"
