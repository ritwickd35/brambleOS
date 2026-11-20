#!/bin/sh
cd "/Users/ritwickdas/Downloads/Pocket Master Firmware V1.3.0/re"
L=logs/work.log; PY=tools/.venv/bin/python
s() { echo "$(date +%H:%M:%S) $*" | tee -a $L; }
s "cut6 chain: waiting for cut5 tests"
until grep -q "CUT5 CHAIN DONE" $L; do sleep 15; done
s "parking on F01"; timeout 20 $PY tools/pmpreset.py select 50 >> $L 2>&1
s "flashing cut6 (engine-load probe + engine code test)"; $PY -u tools/pmflash.py flash "build/cut6/PocketMaster_CFW1.0.2+pm-cut6.bin" --yes > logs/flash-cut6.log 2>&1
grep -q "DONE in" logs/flash-cut6.log || { s "flash failed"; exit 1; }
n=0; until timeout 9 $PY -u tools/pmmode.py 2>/dev/null | tail -1 | grep -q "APP mode"; do n=$((n+1)); [ $n -gt 60 ] && { s "pedal did not come back"; exit 1; }; sleep 10; done
s "pedal back on cut6 ($((n*10)) s)"; sleep 20
s "engine load runs"; $PY -u tools/engine_load.py run 2>&1 | tee -a logs/engine-load.log | grep --line-buffered -vE "^\s*$" >> $L
s "engine code test (Bass EQ patched)"; $PY -u tools/engine_patch_test.py 2>&1 | tee -a logs/engine-patch.log | grep --line-buffered -E "level|restored" >> $L
s "DS-1+ / gate retest (fixed modules)"; AUDIT_TAG=-cut6 $PY -u tools/test_cut5.py sound 2>&1 | tee -a logs/cut6.log | grep --line-buffered -E "sound|restored" >> $L
cp cut1/cut5-sound.json cut1/cut6-sound.json
s "CPU cost of DS-1+ / gate"; $PY -u tools/test_cut5.py cpu 2>&1 | tee -a logs/cut6.log | grep --line-buffered -E "free|restored" >> $L
cp cut1/cut5-cpu.json cut1/cut6-cpu.json
timeout 20 $PY tools/pmpreset.py select 50 >> $L 2>&1
s "CUT6 CHAIN DONE"
