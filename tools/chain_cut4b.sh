#!/bin/sh
# After the CFW sound baseline (part 3): park the pedal on factory preset F01 (no test module runs at power-on),
# flash cut4b (CFW 1.0.2 + tests, no size change), wait for the user's OK tap, then: FX1 probe (gentle) first,
# CPU matrix + pairs (overload ramp) last, and park on F01 again at the end.
cd "/Users/ritwickdas/Downloads/Pocket Master Firmware V1.3.0/re"
L=logs/chain-cut4b.log; PY=tools/.venv/bin/python
s() { echo "$(date +%H:%M:%S) $*" | tee -a $L; }
park() { timeout 20 $PY tools/pmpreset.py select 50 >> $L 2>&1; timeout 20 $PY tools/pmpreset.py current >> $L 2>&1; }
s "waiting for part 3 (CFW NEW-EFFECTS BASELINE DONE)"
until grep -q "CFW NEW-EFFECTS BASELINE DONE" logs/chain-cfw.log; do sleep 15; done
s "parking on F01 before the flash"; park
s "flashing cut4b"; $PY -u tools/pmflash.py flash "build/cut4b/PocketMaster_CFW1.0.2+tests-cut4b.bin" --yes > logs/flash-cut4b.log 2>&1
grep -q "DONE in" logs/flash-cut4b.log || { s "FLASH FAILED - stopping"; exit 1; }
s ">>> TAP OK ON THE PEDAL NOW <<<"; osascript -e 'display notification "Tap OK on the pedal now" with title "Pocket Master flash done"'; say "Flash done. Tap OK on the pedal now." 2>/dev/null
n=0; until timeout 9 $PY -u tools/pmmode.py 2>/dev/null | tail -1 | grep -q "APP mode"; do n=$((n+1)); [ $n -gt 90 ] && { s "PEDAL DID NOT COME BACK in 15 min - stopping (recovery needed)"; say "The pedal did not come back." 2>/dev/null; exit 1; }; sleep 10; done
s "pedal is back on cut4b; settling 20 s"; sleep 20
s "1/3 FX1 probe (audio processing + memory speed + A2 layer)"; $PY -u tools/fx1probe_run.py run > logs/fx1probe.log 2>&1; cat logs/fx1probe.log >> $L
timeout 9 $PY -u tools/pmmode.py 2>/dev/null | tail -1 | grep -q "APP mode" || { s "pedal not answering after the probe - stopping"; exit 1; }
s "2/3 CPU matrix on CFW"; echo "===== CFW RUN (cut4b) =====" >> logs/cut1-matrix.log
MATRIX_JSON=matrix-results-cfw.json $PY -u tools/cut1_matrix.py > logs/cut1-matrix-cfw.stdout 2>&1
s "3/3 CPU pairs on CFW"; echo "===== CFW PAIRS (cut4b) =====" >> logs/cut1-matrix.log
PAIRS_JSON=matrix-results-pairs-cfw.json $PY -u tools/cut1_matrix.py pairs > logs/cut1-matrix-pairs-cfw.stdout 2>&1
s "parking on F01"; park
s "CUT4B CHAIN DONE"; osascript -e 'display notification "CPU and speed tests finished" with title "Pocket Master"'
