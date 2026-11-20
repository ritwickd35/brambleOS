#!/bin/sh
# Waits for the stock background run to finish, then: flash CFW 1.0.2 + tests, wait for the user's OK tap,
# run the FX1 probe, the CPU matrix + pairs and both quality audits on the CFW. Log: logs/chain-cfw.log
cd "/Users/ritwickdas/Downloads/Pocket Master Firmware V1.3.0/re"
L=logs/chain-cfw.log; PY=tools/.venv/bin/python
say_() { echo "$(date +%H:%M:%S) $*" | tee -a $L; }
say_ "waiting for the stock run to finish (CHAIN DONE in logs/audit-fx.log)"
until grep -q "CHAIN DONE" logs/audit-fx.log 2>/dev/null; do sleep 20; done
say_ "stock run finished; flashing CFW 1.0.2 + tests"
$PY -u tools/pmflash.py flash "build/cut4a/PocketMaster_CFW1.0.2+tests-cut4a.bin" --yes >> logs/flash-cut4a.log 2>&1
tail -c 200 logs/flash-cut4a.log | tr '\r' '\n' | tail -2 >> $L
if ! grep -q "DONE in" logs/flash-cut4a.log; then say_ "FLASH FAILED - stopping"; osascript -e 'display notification "Flash failed - see logs" with title "Pocket Master"'; exit 1; fi
say_ ">>> TAP OK ON THE PEDAL NOW <<<"
osascript -e 'display notification "Tap OK on the pedal now" with title "Pocket Master flash done"'
say "Flash done. Tap OK on the pedal now." 2>/dev/null
n=0; until timeout 9 $PY -u tools/pmmode.py 2>/dev/null | tail -1 | grep -q "APP mode"; do n=$((n+1)); [ $n -gt 90 ] && { say_ "pedal did not come back in 15 min - stopping"; exit 1; }; sleep 10; done
say_ "pedal is back (CFW running); waiting 20 s for it to settle"; sleep 20
say_ "1/5 FX1 probe"; $PY -u tools/fx1probe_run.py run >> logs/fx1probe.log 2>&1; tail -40 logs/fx1probe.log >> $L
say_ "2/5 CPU matrix on CFW"; echo "===== CFW RUN =====" >> logs/cut1-matrix.log
MATRIX_JSON=matrix-results-cfw.json $PY -u tools/cut1_matrix.py > logs/cut1-matrix-cfw.stdout 2>&1
say_ "3/5 CPU pairs on CFW"; echo "===== CFW PAIRS =====" >> logs/cut1-matrix.log
PAIRS_JSON=matrix-results-pairs-cfw.json $PY -u tools/cut1_matrix.py pairs > logs/cut1-matrix-pairs-cfw.stdout 2>&1
say_ "4/5 drive + amp quality audit on CFW"; AUDIT_TAG=-cfw $PY -u tools/audit.py run > logs/audit-cfw.stdout 2>&1
say_ "5/5 effects + amps quality audit on CFW"; AUDIT_TAG=-cfw $PY -u tools/audit_fx.py run > logs/audit-fx-cfw.stdout 2>&1
say_ "CFW CHAIN DONE"; osascript -e 'display notification "All CFW baseline tests finished" with title "Pocket Master"'
